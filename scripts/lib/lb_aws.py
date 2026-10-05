"""Clientes de AWS del pipeline: S3 y Bedrock (embeddings + LLM).

Todo pasa por aqui para que el medidor de uso (``lb_usage``) vea cada llamada.
Ninguna etapa debe construir un cliente boto3 por su cuenta.

Estado: la cuenta ya tiene credenciales (usuario IAM ``s3-pulso-vri``) pero
todavia SIN permisos de S3/Bedrock/RDS. Los metodos fallan con un mensaje que
dice exactamente que permiso falta; ver README de infraestructura.
"""

from __future__ import annotations

import json
import random
import time

_BOTO_ERROR = None
try:
    import boto3
    import botocore.exceptions
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import ClientError
except ImportError as exc:  # pragma: no cover
    boto3 = None
    BotoConfig = None
    ClientError = Exception
    _BOTO_ERROR = exc


class AwsNotConfigured(RuntimeError):
    """El recurso existe en el codigo pero falta permiso/endpoint en la cuenta."""


def _session(cfg, service: str = ""):
    """Sesion boto3 para un servicio concreto.

    Cada servicio puede usar un perfil de ~/.aws/credentials distinto
    (``s3.profile``, ``bedrock.profile``), porque en esta cuenta S3 y Bedrock
    llegaron como dos pares de claves separados. Si el servicio no define
    perfil propio, cae en ``aws.profile``, y si ese tambien esta vacio, en la
    cadena por defecto de boto3 (perfil [default] o rol de instancia).
    """
    if boto3 is None:
        raise AwsNotConfigured(f"boto3 no esta instalado: {_BOTO_ERROR}")
    profile = (cfg.get(f"{service}.profile") if service else None) or cfg.get("aws.profile")
    region = (cfg.get(f"{service}.region") if service else None) or cfg.get("aws.region")
    try:
        return boto3.Session(profile_name=profile or None, region_name=region)
    except botocore.exceptions.ProfileNotFound as exc:
        raise AwsNotConfigured(
            f"El perfil de AWS '{profile}' (configurado en {service or 'aws'}.profile) no "
            f"existe en ~/.aws/credentials. Crearlo con:\n"
            f"    aws configure --profile {profile}\n"
            f"y pegar el 'Access key ID' y el 'Secret access key' de {service or 'AWS'}. "
            f"Para usar la credencial por defecto en su lugar, dejar "
            f"{service or 'aws'}.profile = \"\" en config/pipeline.toml.") from exc


# ---------------------------------------------------------------------------
# S3
# ---------------------------------------------------------------------------

class S3Store:
    """Artefactos del run en S3. ``enabled=False`` lo vuelve un no-op silencioso.

    Asi las etapas llaman ``s3.put_json(...)`` incondicionalmente y el flujo
    corre igual sin S3 configurado (que es el estado de hoy).
    """

    def __init__(self, cfg, meter_stage=None):
        self.cfg = cfg
        self.enabled = bool(cfg.get("run.use_s3"))
        self.bucket = cfg.get("s3.bucket")
        self.prefix = (cfg.get("s3.prefix") or "").strip("/")
        self.stage = meter_stage
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = _session(self.cfg, "s3").client("s3")
        return self._client

    def key(self, *parts) -> str:
        return "/".join([p for p in (self.prefix, *parts) if p])

    def run_key(self, run_id: str, *parts) -> str:
        return self.key(self.cfg.get("s3.artifacts_prefix", "runs"), run_id, *parts)

    def put_bytes(self, key: str, payload: bytes, content_type="application/octet-stream"):
        if not self.enabled:
            return None
        self.cfg.require("s3.bucket", "Necesario porque run.use_s3 = true.")
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=payload,
                                   ContentType=content_type)
        except ClientError as exc:
            raise AwsNotConfigured(
                f"No se pudo escribir s3://{self.bucket}/{key}: {exc}. "
                f"El rol necesita s3:PutObject sobre arn:aws:s3:::{self.bucket}/*"
            ) from exc
        if self.stage:
            self.stage.record_s3_put(len(payload))
        return f"s3://{self.bucket}/{key}"

    def put_json(self, key: str, data) -> str | None:
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        return self.put_bytes(key, payload, "application/json")

    def get_bytes(self, key: str) -> bytes:
        self.cfg.require("s3.bucket")
        try:
            body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as exc:
            raise AwsNotConfigured(
                f"No se pudo leer s3://{self.bucket}/{key}: {exc}. "
                f"El rol necesita s3:GetObject sobre arn:aws:s3:::{self.bucket}/*"
            ) from exc
        if self.stage:
            self.stage.record_s3_get(len(body))
        return body


# ---------------------------------------------------------------------------
# Bedrock
# ---------------------------------------------------------------------------

def _split_for_embedding(text: str, max_chars: int) -> list[str]:
    """Trocea un texto que excede el limite del modelo, cortando por espacio."""
    if len(text) <= max_chars:
        return [text]
    chunks, rest = [], text
    while len(rest) > max_chars:
        cut = rest.rfind(" ", 0, max_chars)
        if cut <= 0:
            cut = max_chars
        chunks.append(rest[:cut])
        rest = rest[cut:].lstrip()
    if rest:
        chunks.append(rest)
    return chunks


def _mean_pool(matrix):
    """Promedia las filas y renormaliza. Un texto largo = la media de sus trozos."""
    import numpy as np
    if matrix.shape[0] == 1:
        row = matrix[0]
    else:
        row = matrix.mean(axis=0)
    norm = float(np.linalg.norm(row))
    return (row / norm).astype("float32") if norm else row.astype("float32")


class BedrockClient:
    """Embeddings y LLM sobre Bedrock, con reintento exponencial y medicion.

    El throttling de Bedrock es la causa habitual de que una corrida tarde
    horas: se cuenta aparte de los errores para poder decir en el reporte
    cuanto del tiempo de reloj fue espera por cuota y no trabajo real.
    """

    def __init__(self, cfg, meter_stage=None):
        self.cfg = cfg
        self.stage = meter_stage
        self.region = cfg.get("bedrock.region") or cfg.get("aws.region")
        self.max_retries = int(cfg.get("bedrock.max_retries", 8))
        self.base_delay = float(cfg.get("bedrock.retry_base_delay", 1.0))
        self._runtime = None

    @property
    def runtime(self):
        if self._runtime is None:
            if boto3 is None:
                raise AwsNotConfigured(f"boto3 no esta instalado: {_BOTO_ERROR}")
            self._runtime = _session(self.cfg, "bedrock").client(
                "bedrock-runtime", region_name=self.region,
                # Los reintentos los maneja este modulo para poder contarlos.
                config=BotoConfig(retries={"max_attempts": 1}, read_timeout=120),
            )
        return self._runtime

    def _invoke(self, model_id: str, body: dict):
        """Llama a Bedrock reintentando el throttling. Devuelve (respuesta, stats)."""
        def call():
            response = self.runtime.invoke_model(
                modelId=model_id, body=json.dumps(body),
                contentType="application/json", accept="application/json",
            )
            return json.loads(response["body"].read())
        return self._with_retries(model_id, call)

    def _with_retries(self, model_id: str, call):
        """Ejecuta ``call()`` reintentando el throttling. Devuelve (respuesta, stats)."""
        retries = throttles = 0
        start = time.perf_counter()
        last = None
        for attempt in range(self.max_retries):
            try:
                payload = call()
                stats = {"latency": time.perf_counter() - start,
                         "retries": retries, "throttles": throttles}
                return payload, stats
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                last = exc
                if code in ("ThrottlingException", "TooManyRequestsException",
                            "ServiceUnavailableException", "ModelTimeoutException"):
                    throttles += 1
                    retries += 1
                    # backoff exponencial con jitter para no sincronizar los workers
                    time.sleep(self.base_delay * (2 ** attempt) * (0.5 + random.random()))
                    continue
                if code == "AccessDeniedException":
                    raise AwsNotConfigured(
                        f"Sin acceso a Bedrock para '{model_id}' en {self.region}: {exc}. "
                        "Hace falta (a) habilitar el modelo en la consola de Bedrock "
                        "-> Model access, y (b) permiso bedrock:InvokeModel sobre "
                        f"arn:aws:bedrock:{self.region}::foundation-model/{model_id}"
                    ) from exc
                raise
        raise AwsNotConfigured(
            f"Bedrock sigue rechazando por cuota tras {self.max_retries} intentos: {last}")

    # -- embeddings --------------------------------------------------------
    def embed(self, texts: list[str], model_id: str | None = None):
        """Embebe una lista de textos. Agrupa segun el limite del modelo.

        Cohere acepta hasta 96 textos por llamada; Titan acepta uno solo. El
        formato de request/response difiere, de ahi la rama por familia.
        """
        model_id = model_id or self.cfg.require(
            "bedrock.embedding_model_id",
            "Modelo de embeddings; debe estar habilitado en Bedrock -> Model access.")
        batch_size = int(self.cfg.get("bedrock.embedding_batch_size", 96))
        if model_id.startswith("amazon.titan"):
            batch_size = 1

        # Cohere rechaza textos de mas de 2048 caracteres. En vez de truncar
        # (que tiraria el final de los abstracts largos), se trocea y se
        # promedian los vectores de los trozos: mismo criterio de mean pooling
        # que ya se usa para los documentos de politica.
        max_chars = int(self.cfg.get("bedrock.embedding_max_chars", 2048))
        pieces: list[str] = []
        owners: list[int] = []
        for index, text in enumerate(texts):
            for piece in _split_for_embedding(text, max_chars):
                pieces.append(piece)
                owners.append(index)

        # Se acumula en float32 por lotes. Con 35.000 textos, mantener la
        # respuesta como listas de float de Python serian ~1,1 GB; en float32
        # son 143 MB. pgvector guarda float32 igualmente, asi que no se pierde
        # precision util.
        import numpy as np
        raw_chunks: list = []
        for start in range(0, len(pieces), batch_size):
            chunk = pieces[start:start + batch_size]
            if model_id.startswith("cohere."):
                body = {"texts": chunk, "input_type": "clustering",
                        "truncate": "END"}
                payload, stats = self._invoke(model_id, body)
                raw_chunks.append(np.asarray(payload["embeddings"], dtype="float32"))
                tokens = payload.get("meta", {}).get("billed_units", {}).get("input_tokens", 0)
            elif model_id.startswith("amazon.titan"):
                body = {"inputText": chunk[0],
                        "dimensions": int(self.cfg.get("bedrock.embedding_dimensions", 1024)),
                        "normalize": True}
                payload, stats = self._invoke(model_id, body)
                raw_chunks.append(np.asarray([payload["embedding"]], dtype="float32"))
                tokens = payload.get("inputTextTokenCount", 0)
            else:
                raise AwsNotConfigured(
                    f"Familia de modelo de embeddings no soportada: {model_id}. "
                    "Anadir la rama correspondiente en lb_aws.BedrockClient.embed.")
            if self.stage:
                self.stage.record_embeddings(
                    model_id, items=len(chunk), tokens=tokens,
                    latency_seconds=stats["latency"], retries=stats["retries"],
                    throttles=stats["throttles"])

        # Un vector por texto de entrada: la media de los vectores de sus trozos.
        raw = np.concatenate(raw_chunks) if raw_chunks else np.zeros((0, 0), "float32")
        del raw_chunks
        # Un vector por texto de entrada: la media de los vectores de sus trozos.
        owners_arr = np.asarray(owners)
        out = np.empty((len(texts), raw.shape[1]), dtype="float32")
        for index in range(len(texts)):
            out[index] = _mean_pool(raw[owners_arr == index])
        return out

    # -- LLM ---------------------------------------------------------------
    def complete(self, system: str, user: str, model_id: str | None = None,
                 max_tokens: int | None = None, temperature: float | None = None) -> str:
        """Una respuesta de texto del LLM (API Messages de Anthropic en Bedrock)."""
        model_id = model_id or self.cfg.require(
            "bedrock.llm_model_id",
            "Modelo de extraccion de temas; habilitarlo en Bedrock -> Model access.")
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": int(max_tokens or self.cfg.get("bedrock.llm_max_tokens", 2048)),
            "system": system,
            "messages": [{"role": "user", "content": [{"type": "text", "text": user}]}],
        }
        # `temperature` esta eliminado en Claude Opus 5 / Sonnet 5 y la familia
        # 4.7/4.8: enviarlo devuelve ValidationException. Solo se manda si la
        # configuracion lo pide expresamente (modelos antiguos como Haiku 4.5).
        temp = temperature if temperature is not None else self.cfg.get("bedrock.temperature")
        if temp is not None and temp != "":
            body["temperature"] = float(temp)
        # `effort` sustituye a `temperature` como palanca principal: controla
        # cuanto razona el modelo y, con ello, el gasto de tokens. Es la palanca
        # de costo mas importante en las ~14k llamadas de publicaciones.
        effort = self.cfg.get("bedrock.effort")
        if effort:
            body["output_config"] = {"effort": effort}
        payload, stats = self._invoke(model_id, body)
        usage = payload.get("usage", {})
        if self.stage:
            self.stage.record_llm(
                model_id,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                latency_seconds=stats["latency"], retries=stats["retries"],
                throttles=stats["throttles"])
        return "".join(block.get("text", "") for block in payload.get("content", []))

    def converse(self, system: str, user: str, model_id: str,
                 max_tokens: int = 2048) -> str:
        """Una respuesta de texto por la API Converse de Bedrock.

        A diferencia de ``complete`` (formato Messages de Anthropic), Converse
        tiene el mismo request para todos los proveedores (Nova, Llama, Qwen,
        gpt-oss, GLM, Claude...), asi que sirve para comparar modelos sin una
        rama por familia. Los bloques de razonamiento que devuelven algunos
        modelos (gpt-oss, Qwen3) se descartan: solo se devuelve el texto final.
        """
        def call():
            return self.runtime.converse(
                modelId=model_id,
                system=[{"text": system}],
                messages=[{"role": "user", "content": [{"text": user}]}],
                inferenceConfig={"maxTokens": int(max_tokens)},
            )
        payload, stats = self._with_retries(model_id, call)
        usage = payload.get("usage", {})
        if self.stage:
            self.stage.record_llm(
                model_id,
                input_tokens=usage.get("inputTokens", 0),
                output_tokens=usage.get("outputTokens", 0),
                latency_seconds=stats["latency"], retries=stats["retries"],
                throttles=stats["throttles"])
        self.last_usage = {"input_tokens": usage.get("inputTokens", 0),
                           "output_tokens": usage.get("outputTokens", 0),
                           "latency": stats["latency"]}
        blocks = payload.get("output", {}).get("message", {}).get("content", [])
        return "".join(block.get("text", "") for block in blocks if "text" in block)


class OpenAICompatClient:
    """Pasarela con API compatible con OpenAI (LibreChat, LiteLLM, Bedrock
    Access Gateway...), para chat y/o embeddings.

    Es el camino que corresponde cuando el acceso a Bedrock llega como
    ``OPENAI_BASE_URL`` + una API key en vez de como par de claves AWS: por
    detras puede seguir siendo Bedrock, pero se habla HTTP contra
    ``/v1/chat/completions`` y ``/v1/embeddings``, no boto3.

    Expone los mismos metodos que ``BedrockClient`` (``complete`` y ``embed``)
    para que las etapas puedan intercambiarlos sin cambiar nada.
    """

    def __init__(self, cfg, meter_stage=None):
        self.cfg = cfg
        self.stage = meter_stage
        self.max_retries = int(cfg.get("bedrock.max_retries", 8))
        self.base_delay = float(cfg.get("bedrock.retry_base_delay", 1.0))

    def _post(self, path: str, body: dict):
        """POST con reintento ante 429/5xx. Devuelve (payload, stats)."""
        import urllib.error
        import urllib.request

        base = self.cfg.require(
            "gateway.base_url",
            "Es el OPENAI_BASE_URL de la pasarela (sin el /v1 final).").rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        api_key = self.cfg.require(
            "gateway.api_key",
            "Definir en la variable de entorno LB_GATEWAY__API_KEY, no en el TOML.")
        data = json.dumps(body).encode("utf-8")
        retries = throttles = 0
        start = time.perf_counter()
        last = None
        for attempt in range(self.max_retries):
            request = urllib.request.Request(
                f"{base}/v1/{path}", data=data,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {api_key}"})
            try:
                with urllib.request.urlopen(request, timeout=180) as response:
                    payload = json.loads(response.read())
                return payload, {"latency": time.perf_counter() - start,
                                 "retries": retries, "throttles": throttles}
            except urllib.error.HTTPError as exc:
                last = exc
                detail = exc.read().decode("utf-8", "replace")[:300]
                if exc.code in (408, 429, 500, 502, 503, 504):
                    throttles += 1
                    retries += 1
                    time.sleep(self.base_delay * (2 ** attempt) * (0.5 + random.random()))
                    continue
                if exc.code in (401, 403):
                    raise AwsNotConfigured(
                        f"La pasarela rechazo la credencial (HTTP {exc.code}) en "
                        f"{base}/v1/{path}: {detail}. Revisar LB_GATEWAY__API_KEY.") from exc
                raise AwsNotConfigured(
                    f"La pasarela devolvio HTTP {exc.code} en {base}/v1/{path}: "
                    f"{detail}") from exc
            except urllib.error.URLError as exc:
                last = exc
                retries += 1
                time.sleep(self.base_delay * (2 ** attempt) * (0.5 + random.random()))
        raise AwsNotConfigured(
            f"No se pudo hablar con la pasarela tras {self.max_retries} intentos: {last}")

    def balance(self):
        """Saldo de creditos de la pasarela, si lo expone. None si no.

        No hay un estandar: se prueban las rutas habituales (LibreChat y la
        convencion de OpenAI). Sirve para medir cuantos creditos consume la
        corrida de verdad, que es la unica forma de saber en que unidad esta
        denominado el saldo (tokens crudos o micro-dolares ponderados por
        modelo) sin depender de la documentacion.
        """
        import urllib.error
        import urllib.request

        base = (self.cfg.get("gateway.base_url") or "").rstrip("/")
        api_key = self.cfg.get("gateway.api_key")
        if not base or not api_key:
            return None
        if base.endswith("/v1"):
            base = base[:-3]
        for path in ("api/balance", "v1/dashboard/billing/credit_grants", "api/user/balance"):
            request = urllib.request.Request(
                f"{base}/{path}",
                headers={"Authorization": f"Bearer {api_key}",
                         "Accept": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    payload = json.loads(response.read())
            except Exception:
                continue
            for key in ("tokenCredits", "balance", "credits", "total_available"):
                if isinstance(payload, dict) and key in payload:
                    try:
                        return float(payload[key])
                    except (TypeError, ValueError):
                        continue
            if isinstance(payload, (int, float)):
                return float(payload)
        return None

    def complete(self, system: str, user: str, model_id: str | None = None,
                 max_tokens: int | None = None, temperature: float | None = None) -> str:
        model = model_id or self.cfg.require("gateway.chat_model")
        payload, stats = self._post("chat/completions", {
            "model": model,
            "max_tokens": int(max_tokens or self.cfg.get("bedrock.llm_max_tokens", 2048)),
            "temperature": float(temperature if temperature is not None
                                 else self.cfg.get("bedrock.llm_temperature", 0.0)),
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        })
        usage = payload.get("usage") or {}
        if self.stage:
            self.stage.record_llm(
                f"gateway:{model}",
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                latency_seconds=stats["latency"], retries=stats["retries"],
                throttles=stats["throttles"])
        if not usage and self.stage:
            # Sin 'usage' no hay forma de medir el consumo de este paso.
            self.stage.notes.setdefault("avisos", []).append(
                "La pasarela no devuelve 'usage': los tokens de chat quedan sin medir.")
        return payload["choices"][0]["message"]["content"]

    def embed(self, texts: list[str], model_id: str | None = None):
        model = model_id or self.cfg.require("gateway.embedding_model")
        batch_size = int(self.cfg.get("gateway.embedding_batch_size", 96))
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            chunk = texts[start:start + batch_size]
            payload, stats = self._post("embeddings", {"model": model, "input": chunk})
            data = sorted(payload["data"], key=lambda d: d.get("index", 0))
            vectors.extend(item["embedding"] for item in data)  # pasarela: volumen menor
            usage = payload.get("usage") or {}
            if self.stage:
                self.stage.record_embeddings(
                    f"gateway:{model}", items=len(chunk),
                    tokens=usage.get("prompt_tokens", usage.get("total_tokens", 0)),
                    latency_seconds=stats["latency"], retries=stats["retries"],
                    throttles=stats["throttles"])
        return vectors


# Nombre anterior, conservado para no romper importaciones existentes.
LibreChatClient = OpenAICompatClient


def _gateway_handles(cfg, kind: str) -> bool:
    """¿La pasarela se encarga de 'chat' o de 'embeddings'?"""
    if not cfg.get("gateway.enabled"):
        return False
    use_for = (cfg.get("gateway.use_for") or "both").lower()
    return use_for in ("both", kind)


def llm_client(cfg, meter_stage=None):
    """Cliente para el paso de LLM: pasarela si la cubre, si no Bedrock."""
    if _gateway_handles(cfg, "chat"):
        return OpenAICompatClient(cfg, meter_stage)
    return BedrockClient(cfg, meter_stage)


def embedding_client(cfg, meter_stage=None):
    """Cliente para embeddings: pasarela si la cubre, si no Bedrock."""
    if _gateway_handles(cfg, "embeddings"):
        return OpenAICompatClient(cfg, meter_stage)
    return BedrockClient(cfg, meter_stage)

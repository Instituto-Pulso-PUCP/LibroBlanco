#!/usr/bin/env python3
"""Etapa 00 — comprueba que queda por configurar antes de correr el pipeline.

No modifica nada. Prueba de verdad cada recurso (identidad IAM, S3, Bedrock,
RDS) y dice, por cada fallo, que permiso o valor falta. Pensado para correrlo
tras cada cambio de infraestructura.

    python scripts/pipeline_temas/00_check_infra.py
    python scripts/pipeline_temas/00_check_infra.py --domain publications
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))

import lb_config   # noqa: E402
import lb_domains  # noqa: E402

OK, FAIL, SKIP = "  OK  ", " FALTA", " OMIT "


def check(label, fn):
    try:
        detail = fn()
        print(f"[{OK}] {label}" + (f" — {detail}" if detail else ""))
        return True
    except Exception as exc:
        message = str(exc).split("\n")[0]
        print(f"[{FAIL}] {label}\n         {message}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", default=None, choices=sorted(lb_domains.DOMAINS))
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    cfg = lb_config.load(args.config)
    print(f"Configuración leída de: {', '.join(cfg.sources)}")
    if not lb_config.CONFIG_PATH.exists():
        print(f"AVISO: no existe {lb_config.CONFIG_PATH.relative_to(REPO_ROOT)}. "
              "Se está usando solo el ejemplo. Copiarlo y rellenarlo.")
    missing = cfg.missing()
    if missing:
        print(f"\nValores sin rellenar ({len(missing)}):")
        for path in missing:
            print(f"  - {path}")
    print()

    results = {}

    # --- Datos de origen --------------------------------------------------
    for key in ([args.domain] if args.domain else sorted(lb_domains.DOMAINS)):
        domain = lb_domains.get(key)
        def probe(domain=domain):
            rows = lb_domains.read_source(domain)
            units, dropped = lb_domains.to_units(domain, rows, 6000)
            filled = {}
            for column in domain.text_columns:
                count = sum(1 for r in rows if lb_domains.clean_value(r.get(column)))
                filled[column] = count / len(rows) if rows else 0
            weak = [c for c, rate in filled.items() if rate < 0.10]
            note = f"{len(rows):,} filas, {len(units):,} unidades"
            if weak:
                note += f" · columnas casi vacías: {', '.join(weak)}"
            return note
        results[f"datos:{key}"] = check(f"Origen de datos ({key})", probe)

    # --- AWS --------------------------------------------------------------
    import lb_aws

    def identity():
        client = lb_aws._session(cfg).client("sts")
        ident = client.get_caller_identity()
        return f"{ident['Arn']} (cuenta {ident['Account']})"
    results["sts"] = check("Credenciales AWS", identity)

    bucket = cfg.get("s3.bucket")
    if bucket and bucket != lb_config.PLACEHOLDER:
        def s3_probe():
            # No se usa head_bucket: requiere s3:ListBucket, que el pipeline no
            # necesita y que esta credencial no tiene. Se prueba exactamente lo
            # que el pipeline hace: escribir, leer y borrar un objeto.
            client = lb_aws._session(cfg, "s3").client("s3")
            prefix = cfg.get("s3.prefix", "")
            key = f"{prefix}/_lb_check".strip("/")
            client.put_object(Bucket=bucket, Key=key, Body=b"ok")
            body = client.get_object(Bucket=bucket, Key=key)["Body"].read()
            assert body == b"ok", "el objeto leido no coincide con el escrito"
            client.delete_object(Bucket=bucket, Key=key)
            return f"put/get/delete en s3://{bucket}/{prefix}"
        results["s3"] = check("S3", s3_probe)
    else:
        print(f"[{SKIP}] S3 — s3.bucket sin configurar")

    gateway_on = bool(cfg.get("gateway.enabled"))
    use_for = (cfg.get("gateway.use_for") or "both").lower()

    # Embeddings: por la pasarela si la cubre, si no por Bedrock directo.
    if gateway_on and use_for in ("both", "embeddings"):
        def gw_embed():
            client = lb_aws.OpenAICompatClient(cfg)
            vectors = client.embed(["prueba de conectividad"])
            return (f"pasarela · {cfg.get('gateway.embedding_model')} → "
                    f"{len(vectors[0])} dimensiones")
        results["embeddings"] = check("Embeddings (pasarela)", gw_embed)
        if not results["embeddings"]:
            print("         Si la pasarela no expone /v1/embeddings, poner "
                  "gateway.use_for = \"chat\" y dejar los embeddings a Bedrock.")
    else:
        def bedrock_embed():
            client = lb_aws.BedrockClient(cfg)
            vectors = client.embed(["prueba de conectividad"])
            return (f"Bedrock · {cfg.get('bedrock.embedding_model_id')} → "
                    f"{len(vectors[0])} dimensiones")
        results["embeddings"] = check("Embeddings (Bedrock)", bedrock_embed)

    # Chat / LLM
    if gateway_on and use_for in ("both", "chat"):
        def gw_chat():
            client = lb_aws.OpenAICompatClient(cfg)
            reply = client.complete("Responde solo con la palabra ok.", "ping")
            return f"pasarela · {cfg.get('gateway.chat_model')} → {reply.strip()[:30]!r}"
        results["llm"] = check("LLM (pasarela)", gw_chat)
    else:
        def bedrock_llm():
            client = lb_aws.BedrockClient(cfg)
            reply = client.complete("Responde solo con la palabra ok.", "ping")
            return f"Bedrock · {cfg.get('bedrock.llm_model_id')} → {reply.strip()[:30]!r}"
        results["llm"] = check("LLM (Bedrock)", bedrock_llm)

    # --- RDS --------------------------------------------------------------
    if cfg.get("run.store") == "rds" or cfg.get("rds.host") != lb_config.PLACEHOLDER:
        import lb_store

        if (cfg.get("rds.auth") == "password" and not cfg.get("rds.password")
                and not cfg.get("rds.password_secret_arn")):
            print(f"[{FAIL}] RDS — falta la clave de la base")
            print("         Definir LB_RDS__PASSWORD en config/env.sh y hacer "
                  "'source config/env.sh', o usar rds.password_secret_arn.")
            results["rds"] = False
            lb_store = None

        def rds_probe():
            if lb_store is None:
                raise RuntimeError("sin clave")
            conn, driver = lb_store._connect(cfg)
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                version = cur.fetchone()[0]
                cur.execute("SELECT to_regclass(%s)",
                            (f"{cfg.get('rds.schema', 'libroblanco')}.unit_topic_membership",))
                has_schema = cur.fetchone()[0] is not None
            conn.close()
            suffix = "esquema aplicado" if has_schema else "FALTA aplicar sql/schema.sql"
            return f"{driver} · {version.split(',')[0]} · {suffix}"
        if results.get("rds") is not False:
            results["rds"] = check("RDS (PostgreSQL)", rds_probe)
    else:
        print(f"[{SKIP}] RDS — rds.host sin configurar (run.store = "
              f"{cfg.get('run.store')!r})")

    # --- Resumen ----------------------------------------------------------
    failed = [k for k, ok in results.items() if not ok]
    print()
    if failed:
        print(f"Faltan por resolver: {', '.join(failed)}")
        print("El pipeline puede correr igualmente con run.store = 'local' y "
              "--affinity extraction hasta las etapas que no necesitan AWS.")
        return 1
    print("Todo listo: se puede correr scripts/pipeline_temas/run_domain.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

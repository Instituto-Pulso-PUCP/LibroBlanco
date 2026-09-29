"""Carga de configuracion del pipeline (config/pipeline.toml + entorno).

Una sola fuente de verdad para endpoints, modelos y precios, de modo que las
etapas no lean variables de entorno sueltas y el reporte de uso pueda anotar
con que configuracion se corrio cada run.

Precedencia (de menor a mayor): pipeline.example.toml -> pipeline.toml ->
variables de entorno ``LB_<SECCION>__<CLAVE>``.
"""

from __future__ import annotations

import os
import tomllib
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_PATH = REPO_ROOT / "config" / "pipeline.example.toml"
CONFIG_PATH = REPO_ROOT / "config" / "pipeline.toml"

PLACEHOLDER = "RELLENAR"


class ConfigError(RuntimeError):
    """Falta un valor de configuracion obligatorio para la etapa que se corre."""


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _coerce(raw: str, reference):
    """Convierte el string del entorno al tipo del valor de referencia del TOML."""
    if isinstance(reference, bool):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(reference, int) and not isinstance(reference, bool):
        return int(raw)
    if isinstance(reference, float):
        return float(raw)
    return raw


def _apply_env(data: dict) -> dict:
    for env_key, raw in os.environ.items():
        if not env_key.startswith("LB_") or "__" not in env_key:
            continue
        section, _, key = env_key[3:].partition("__")
        section, key = section.lower(), key.lower()
        if section in data and isinstance(data[section], dict) and key in data[section]:
            data[section][key] = _coerce(raw, data[section][key])
        else:
            data.setdefault(section, {})[key] = raw
    return data


class Config:
    def __init__(self, data: dict, sources: list[str]):
        self._data = data
        self.sources = sources

    def section(self, name: str) -> dict:
        return dict(self._data.get(name, {}))

    def get(self, path: str, default=None):
        """``cfg.get("bedrock.llm_model_id")``."""
        node = self._data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def require(self, path: str, hint: str = ""):
        """Igual que ``get`` pero falla si falta o quedo en RELLENAR.

        Se llama al inicio de cada etapa que de verdad necesita el valor, no al
        cargar la configuracion: asi las etapas que corren sin AWS (preparacion
        de texto, cuantificacion, reportes) siguen funcionando con la config a
        medio llenar.
        """
        value = self.get(path)
        if value is None or value == "" or value == PLACEHOLDER:
            suffix = f" {hint}" if hint else ""
            env_key = "LB_" + path.replace(".", "__").upper()
            raise ConfigError(
                f"Falta configurar '{path}' (config/pipeline.toml o {env_key}).{suffix}"
            )
        return value

    def missing(self) -> list[str]:
        """Rutas que siguen en RELLENAR o vacias. Para el reporte de estado."""
        out = []

        def walk(node, prefix=""):
            for key, value in node.items():
                path = f"{prefix}{key}"
                if isinstance(value, dict):
                    walk(value, f"{path}.")
                elif value == PLACEHOLDER:
                    out.append(path)
        walk(self._data)
        return sorted(out)

    def as_dict(self) -> dict:
        """Copia sin secretos, apta para guardar junto al reporte del run."""
        redacted = {"password", "api_key", "secret", "token"}
        def walk(node):
            out = {}
            for key, value in node.items():
                if isinstance(value, dict):
                    out[key] = walk(value)
                elif any(word in key for word in redacted) and value:
                    out[key] = "<redactado>"
                else:
                    out[key] = value
            return out
        return walk(self._data)

    def resolve_run_id(self, domain: str) -> str:
        run_id = self.get("run.run_id", "auto")
        if run_id and run_id != "auto":
            return run_id
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        return f"{domain}-{stamp}"


def load(path: Path | None = None) -> Config:
    sources = []
    data: dict = {}
    if EXAMPLE_PATH.exists():
        data = tomllib.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
        sources.append(str(EXAMPLE_PATH.relative_to(REPO_ROOT)))
    target = path or CONFIG_PATH
    if target.exists():
        data = _deep_merge(data, tomllib.loads(target.read_text(encoding="utf-8")))
        sources.append(str(target.relative_to(REPO_ROOT)) if target.is_relative_to(REPO_ROOT) else str(target))
    data = _apply_env(data)
    if os.environ.get("LB_ENV_APPLIED") != "0":
        sources.append("entorno (LB_*)")
    return Config(data, sources)

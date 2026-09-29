#!/usr/bin/env python3
"""Consulta el saldo de creditos de LibreChat y lo interpreta.

El saldo (p.ej. 20,000,000) es ambiguo: segun la instalacion, LibreChat lo
denomina en tokens crudos o en micro-dolares ponderados por modelo. La
diferencia es de ~100x, asi que decide si una corrida cabe o no. Este script
lee el saldo y lo contrasta con lo que el pipeline necesita, medido en los
pilotos ya ejecutados.

    source config/env.sh
    python scripts/pipeline_temas/librechat_balance.py

Nota: esta instancia de LibreChat no expone un endpoint compatible con OpenAI,
asi que el saldo solo se puede gastar desde la interfaz web. Este script sirve
para planificar, no para habilitar el pipeline.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))

import lb_config   # noqa: E402
import lb_domains  # noqa: E402

# Rutas y cabeceras candidatas: LibreChat no documenta una sola forma.
PATHS = ("api/balance", "api/user/balance")
HEADERS = (
    ("Authorization", "Bearer {key}"),
    ("x-api-key", "{key}"),
)


def fetch_balance(base: str, key: str):
    errors = []
    for path in PATHS:
        for name, template in HEADERS:
            request = urllib.request.Request(
                f"{base.rstrip('/')}/{path}",
                headers={name: template.format(key=key), "Accept": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    raw = response.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as exc:
                errors.append(f"{path} [{name}] -> HTTP {exc.code}")
                continue
            except Exception as exc:
                errors.append(f"{path} [{name}] -> {type(exc).__name__}")
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                errors.append(f"{path} [{name}] -> respuesta no JSON")
                continue
            for field in ("tokenCredits", "balance", "credits", "total_available"):
                if isinstance(payload, dict) and field in payload:
                    return float(payload[field]), f"{path} [{name}] campo '{field}'", errors
            if isinstance(payload, (int, float, str)):
                try:
                    return float(payload), f"{path} [{name}] (valor plano)", errors
                except ValueError:
                    pass
            errors.append(f"{path} [{name}] -> JSON sin campo de saldo: "
                          f"{json.dumps(payload)[:120]}")
    return None, None, errors


def pilot_totals():
    """Tokens que necesita cada dominio, segun los pilotos ya medidos."""
    out = {}
    for domain in sorted(lb_domains.DOMAINS):
        root = REPO_ROOT / "salidas" / "topics" / domain
        if not root.exists():
            continue
        for path in sorted(root.glob("*/estimacion_corrida_completa.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            total = data["total"]
            out[domain] = (total["tin"], total["tout"], data["full_units"])
    return out


def main():
    cfg = lb_config.load()
    base = cfg.get("gateway.base_url") or ""
    key = cfg.get("gateway.api_key") or ""
    if not base or base == lb_config.PLACEHOLDER:
        raise SystemExit("Falta gateway.base_url (LB_GATEWAY__BASE_URL en config/env.sh).")
    if not key or key.startswith("PEGAR_AQUI"):
        raise SystemExit(
            "Falta la API key de LibreChat.\n"
            "Pegarla en config/env.sh -> LB_GATEWAY__API_KEY y hacer "
            "'source config/env.sh'.")
    if key.startswith("ABSK"):
        raise SystemExit(
            "Esa es la API key de Bedrock (empieza por ABSK), no la de LibreChat.\n"
            "La de Bedrock va en AWS_BEARER_TOKEN_BEDROCK; en LB_GATEWAY__API_KEY "
            "va la que se crea desde https://chat.txdpucp.net")

    balance, source, errors = fetch_balance(base, key)
    if balance is None:
        print(f"No se pudo leer el saldo en {base}. Intentos:")
        for item in errors:
            print(f"  - {item}")
        print("\nSi todos devuelven 401, la clave no autoriza esa ruta; si devuelven "
              "404, esta instalacion no expone el saldo por API.")
        return 1

    print(f"Saldo: {balance:,.0f}   (via {source})")
    print()
    totals = pilot_totals()
    if not totals:
        print("Aun no hay estimaciones de pilotos con las que comparar.")
        return 0

    print("Contraste con lo que necesita el pipeline (medido en los pilotos):")
    print(f"{'Dominio':14s} {'Unidades':>9s} {'Tokens':>13s} "
          f"{'% si son tokens':>16s} {'USD si son micro-$':>20s}")
    print("-" * 78)
    for domain, (tin, tout, units) in totals.items():
        tokens = tin + tout
        # lectura B: el saldo en micro-dolares, valorado a las tarifas de [pricing]
        price = cfg.section("pricing")
        usd = tin / 1e6 * price.get("llm_input_per_mtok", 0.0) + \
            tout / 1e6 * price.get("llm_output_per_mtok", 0.0)
        print(f"{domain:14s} {units:>9,} {tokens:>13,.0f} "
              f"{tokens / balance * 100:>15.1f}% {usd:>19,.0f}$")
    print("-" * 78)
    print(f"Si el saldo son micro-dolares, equivale a USD {balance / 1e6:,.2f}.")
    print("Para saber cual de las dos lecturas es la buena: anotar el saldo, mandar "
          "un mensaje en la web y volver a correr este script. Si baja ~1 por token, "
          "son tokens; si baja mucho menos, son micro-dolares.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

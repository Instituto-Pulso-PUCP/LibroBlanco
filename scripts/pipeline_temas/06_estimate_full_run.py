#!/usr/bin/env python3
"""Etapa 06 — estima el costo y la duracion de la corrida completa.

Extrapola a partir de un piloto YA MEDIDO (los uso_*.json que dejo cada etapa),
no de suposiciones. Se corre asi:

    python scripts/pipeline_temas/06_estimate_full_run.py --domain publications \
        --from-run pilot-pubs-40

El modelo NO es una simple regla de tres, porque las etapas escalan distinto:

  - Etapa 02 (extraccion): LINEAL en unidades. Una llamada por unidad.
  - Etapa 03 (embeddings): LINEAL en unidades y en temas extraidos.
  - Etapa 03 (nombrado):   ACOTADO por el numero de temas normalizados, que
    tiende a `topics.target_topics`, no al numero de unidades. En el piloto hay
    pocas unidades y muchos grupos; en la corrida completa el agrupamiento
    converge al objetivo. Tratarlo como lineal sobreestima el costo varias veces.
  - Etapas 01/04/05: coste despreciable, sin llamadas a modelo.

El tiempo de reloj asume la concurrencia de `bedrock.max_concurrency` y no
incluye esperas por cuota: si Bedrock limita, el tiempo sube y los throttles
quedan registrados en el reporte de uso.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _stage import REPO_ROOT, base_parser, main_wrapper  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
import lb_config    # noqa: E402
import lb_domains   # noqa: E402


def load_pilot(domain_key: str, run_id: str) -> dict:
    """Agrega los uso_*.json del piloto en un solo diccionario por etapa."""
    root = REPO_ROOT / "salidas" / "topics" / domain_key / run_id
    if not root.exists():
        raise SystemExit(f"No existe {root}. Correr antes el piloto con --sample N.")
    stages: dict[str, dict] = {}
    for path in sorted(root.glob("uso_*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        for stage in report["stages"]:
            entry = stages.setdefault(stage["stage"], {
                "wall": 0.0, "units": 0, "tin": 0, "tout": 0,
                "emb_items": 0, "emb_tokens": 0, "calls": 0, "throttles": 0})
            entry["wall"] += stage["wall_seconds"]
            entry["units"] = max(entry["units"], stage["units_processed"])
            for model in stage["models"].values():
                entry["tin"] += model["input_tokens"]
                entry["tout"] += model["output_tokens"]
                entry["emb_items"] += model["embedded_items"]
                entry["emb_tokens"] += model["embedded_tokens"]
                entry["calls"] += model["calls"]
                entry["throttles"] += model["throttles"]
    if not stages:
        raise SystemExit(f"No hay uso_*.json en {root}.")
    return {"stages": stages}


def pilot_topic_count(cfg, domain_key: str, run_id: str) -> int:
    """Cuantos temas normalizados produjo el piloto.

    Se consulta al store (con run.store = "rds" no hay 03_topics.json en disco,
    los temas estan en la base). Sin este numero el nombrado se extrapolaria
    con factor 1 y la etapa 03 quedaria subestimada.
    """
    import lb_store
    try:
        store = lb_store.open_store(cfg, domain_key, run_id)
        return len(store.read_topics())
    except Exception:
        local = REPO_ROOT / "salidas" / "topics" / domain_key / run_id / "03_topics.json"
        if local.exists():
            return len(json.loads(local.read_text(encoding="utf-8")))
        return 0


def fmt_usd(value):
    return f"USD {value:,.2f}" if value else "—"


@main_wrapper
def main():
    parser = base_parser(__doc__)
    parser.add_argument("--from-run", required=True,
                        help="run_id del piloto ya medido.")
    parser.add_argument("--full-units", type=int, default=0,
                        help="Unidades de la corrida completa. Por defecto, todas "
                             "las del dominio.")
    args = parser.parse_args()

    cfg = lb_config.load(args.config)
    domain = lb_domains.get(args.domain)
    pilot = load_pilot(args.domain, args.from_run)
    stages = pilot["stages"]
    pilot_topics = pilot_topic_count(cfg, args.domain, args.from_run)

    rows = lb_domains.read_source(domain)
    units, _ = lb_domains.to_units(
        domain, rows, int(cfg.get("topics.max_text_chars", 6000)))
    full_n = args.full_units or len(units)
    pilot_n = max((s["units"] for s in stages.values()), default=0)
    if not pilot_n:
        raise SystemExit("El piloto no registro unidades procesadas.")
    scale = full_n / pilot_n

    target_topics = cfg.get("topics.target_topics") or 0
    # Nombrado: acotado por el objetivo de temas, no por las unidades.
    naming_full = min(target_topics, pilot_topics * scale) if target_topics else pilot_topics * scale
    naming_scale = (naming_full / pilot_topics) if pilot_topics else 1.0

    price = cfg.section("pricing")
    est = {}
    for name, s in stages.items():
        if name.startswith("03"):
            # el LLM de esta etapa es el nombrado (acotado); los embeddings escalan lineal
            tin, tout = s["tin"] * naming_scale, s["tout"] * naming_scale
            emb_tokens = s["emb_tokens"] * scale
            wall = s["wall"] * max(naming_scale, scale)
        else:
            tin, tout = s["tin"] * scale, s["tout"] * scale
            emb_tokens = s["emb_tokens"] * scale
            wall = s["wall"] * scale
        cost = (tin / 1e6 * price.get("llm_input_per_mtok", 0.0)
                + tout / 1e6 * price.get("llm_output_per_mtok", 0.0)
                + emb_tokens / 1e6 * price.get("embedding_per_mtok", 0.0))
        est[name] = {"tin": tin, "tout": tout, "emb": emb_tokens,
                     "emb_items": s["emb_items"] * scale,
                     "wall": wall, "cost": cost}

    total = {k: sum(v[k] for v in est.values())
             for k in ("tin", "tout", "emb", "emb_items", "wall", "cost")}
    priced = any(price.get(k) for k in
                 ("llm_input_per_mtok", "llm_output_per_mtok", "embedding_per_mtok"))

    print(f"\nEstimacion de la corrida completa — {domain.label}")
    print(f"Piloto `{args.from_run}`: {pilot_n} unidades"
          + (f", {pilot_topics} temas normalizados" if pilot_topics else ""))
    print(f"Corrida completa: {full_n:,} unidades  (factor x{scale:,.1f})")
    if target_topics and pilot_topics:
        print(f"Llamadas de nombrado: {pilot_topics} -> {naming_full:,.0f} "
              f"(acotado por topics.target_topics={target_topics}, no por las unidades)")
    print()
    print(f"{'Etapa':24s} {'Tokens in':>13s} {'Tokens out':>12s} "
          f"{'Textos embeb':>13s} {'Horas':>8s} {'Costo':>12s}")
    print("-" * 86)
    for name in sorted(est):
        e = est[name]
        print(f"{name:24s} {e['tin']:>13,.0f} {e['tout']:>12,.0f} "
              f"{e['emb_items']:>13,.0f} {e['wall']/3600:>8.2f} {fmt_usd(e['cost']):>12s}")
    print("-" * 86)
    print(f"{'TOTAL':24s} {total['tin']:>13,.0f} {total['tout']:>12,.0f} "
          f"{total['emb_items']:>13,.0f} {total['wall']/3600:>8.2f} {fmt_usd(total['cost']):>12s}")
    print()
    if total["emb_items"] and not total["emb"]:
        print("AVISO: Bedrock no devuelve tokens facturados para este modelo de "
              "embeddings, asi que su costo NO esta incluido arriba. Se reporta el "
              f"numero de textos a embeber ({total['emb_items']:,.0f}).")
    if not priced:
        print("AVISO: [pricing] esta en 0. Los tokens son reales y medidos; el costo no.")
        print("       Rellenar config/pipeline.toml con las tarifas vigentes de Bedrock.")
    if any(s["throttles"] for s in stages.values()):
        print("AVISO: el piloto sufrio throttling. El tiempo real sera mayor que el estimado.")
    print(f"Concurrencia asumida: {cfg.get('bedrock.max_concurrency')} "
          f"(subirla reduce el tiempo, no el costo).")

    out = REPO_ROOT / "salidas" / "topics" / args.domain / args.from_run / "estimacion_corrida_completa.json"
    out.write_text(json.dumps({
        "domain": args.domain, "pilot_run": args.from_run,
        "pilot_units": pilot_n, "full_units": full_n, "scale": scale,
        "pilot_topics": pilot_topics, "naming_calls_full": naming_full,
        "per_stage": est, "total": total, "pricing_configured": priced,
        "pricing": price,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

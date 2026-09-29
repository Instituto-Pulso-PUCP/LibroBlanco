#!/usr/bin/env python3
"""Reusa temas extraidos y embeddings de unidad de una corrida anterior.

Cuando cambia el UNIVERSO (que unidades entran) pero no el TEXTO de las
unidades que sobreviven, no hace falta volver a pagar la extraccion por LLM
(etapa 02) ni el embedding de texto completo (parte de la etapa 03) para esas
unidades: son deterministas en funcion del texto, no del resto del corpus. Solo
la normalizacion (agrupar los temas extraidos) y la cuantificacion cambian de
verdad, porque dependen de que otras unidades hay en el universo.

Este script copia, para las unidades que la corrida NUEVA ya tiene en
`units`/`run_units` (correr la etapa 01 primero, es barata, no llama a AWS),
los `extracted_topics` y `unit_embeddings` de la corrida VIEJA que compartan
ese unit_id -- bajo el run_id nuevo, sin tocar la corrida vieja.

Requisito: la corrida nueva debe ser (para las unidades que copia) un
SUBCONJUNTO textualmente identico de la vieja -- mismo dominio, mismo CSV de
origen, mismo modelo de embeddings. Si el texto de una unidad cambio entre
las dos corridas, este script lo copiaria igual: es responsabilidad de quien
lo invoca no usarlo cuando el insumo cambio, solo cuando cambio el universo.

Uso:

    python scripts/pipeline_temas/01_prep_units.py --domain projects --run-id full-proj-409
    python scripts/pipeline_temas/seed_from_run.py --domain projects \\
        --from-run full-proj-975 --to-run full-proj-409
    python scripts/pipeline_temas/run_domain.py --domain projects \\
        --run-id full-proj-409 --from 03
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
import lb_config  # noqa: E402
import lb_store   # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--from-run", required=True, help="Corrida de donde se copia.")
    parser.add_argument("--to-run", required=True,
                        help="Corrida nueva. Debe existir ya (correr la etapa 01 antes).")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = lb_config.load()
    dst = lb_store.open_store(cfg, args.domain, args.to_run)
    src = lb_store.open_store(cfg, args.domain, args.from_run)

    dst_units = {u["unit_id"] for u in dst.read_units()}
    if not dst_units:
        raise SystemExit(
            f"La corrida destino '{args.to_run}' no tiene unidades todavia. "
            f"Correr antes: python scripts/pipeline_temas/01_prep_units.py "
            f"--domain {args.domain} --run-id {args.to_run}")

    src_units = {u["unit_id"] for u in src.read_units()}
    not_in_src = dst_units - src_units
    if not_in_src:
        raise SystemExit(
            f"{len(not_in_src)} unidades de '{args.to_run}' no existen en '{args.from_run}' "
            f"(ej. {sorted(not_in_src)[:5]}) -- no se puede reusar para esas. Revisar que "
            "--from-run sea de verdad un superconjunto de --to-run.")

    extracted = [r for r in src.read_extracted_topics() if r["unit_id"] in dst_units]
    embeddings = [r for r in src.read_unit_embeddings() if r["unit_id"] in dst_units]

    covered_extracted = len({r["unit_id"] for r in extracted})
    covered_emb = len(embeddings)
    print(f"  unidades en '{args.to_run}': {len(dst_units):,}")
    print(f"  temas extraidos a copiar de '{args.from_run}': {len(extracted):,} filas "
          f"({covered_extracted:,}/{len(dst_units):,} unidades cubiertas)")
    print(f"  embeddings de unidad a copiar: {covered_emb:,}/{len(dst_units):,}")

    missing_extracted = dst_units - {r["unit_id"] for r in extracted}
    if missing_extracted:
        print(f"  AVISO: {len(missing_extracted)} unidades sin temas extraidos en el origen "
              "(no extrajeron ningun tema con confianza > 0 en esa corrida) -- "
              "quedaran sin cubrir; la etapa 03 las reportara sin agrupar en ningun tema.")
    missing_emb = dst_units - {r["unit_id"] for r in embeddings}
    if missing_emb:
        print(f"  AVISO: {len(missing_emb)} unidades sin embedding en el origen -- "
              "la etapa 03 las embebera de nuevo (llamada real a Bedrock, pero solo esas).")

    if args.dry_run:
        print("  --dry-run: no se escribe nada.")
        return

    if extracted:
        dst.write_extracted_topics(extracted)
    if embeddings:
        dst.write_unit_embeddings(embeddings)

    note = {
        "seeded_from_run": args.from_run,
        "to_run": args.to_run,
        "domain": args.domain,
        "units_total": len(dst_units),
        "extracted_topics_rows_copied": len(extracted),
        "unit_embeddings_copied": covered_emb,
        "units_missing_extracted_topics": sorted(missing_extracted),
        "units_missing_embeddings": sorted(missing_emb),
    }
    out_dir = REPO_ROOT / "salidas" / "topics" / args.domain / args.to_run
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "seed_from_run.json").write_text(
        json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  listo. Provenencia -> {(out_dir / 'seed_from_run.json').relative_to(REPO_ROOT)}")
    print(f"  Ahora: python scripts/pipeline_temas/run_domain.py --domain {args.domain} "
          f"--run-id {args.to_run} --from 03")


if __name__ == "__main__":
    main()

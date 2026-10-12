#!/usr/bin/env python3
"""Reusa extraccion y embeddings de una corrida anterior SOLO donde el texto no cambio.

Variante segura de seed_from_run.py: aquel copia por unit_id sin mirar el
texto, asi que no sirve cuando el insumo cambio (nuevo export CRIS, abstracts
descartados o agregados). Este compara el texto de cada unidad entre las dos
corridas y copia solo las identicas:

  - la extraccion (etapa 02): se precarga el cache de la corrida nueva
    (salidas/topics/<dominio>/<run>/02_extraction_cache.jsonl), asi que la
    etapa 02 solo consulta al LLM por las unidades nuevas o con texto distinto;
  - el embedding de unidad (etapa 03): se copia al store; la etapa 03 embebe
    solo las que falten.

La normalizacion y la cuantificacion se recalculan completas, porque dependen
del universo entero. La extraccion y el embedding de una unidad dependen solo
de su texto (mismo modelo y prompt), por eso reusarlos es equivalente.

    python scripts/pipeline_temas/01_prep_units.py --domain projects --run-id <nuevo>
    python scripts/pipeline_temas/seed_same_text.py --domain projects \\
        --from-run full-proj-646 --to-run <nuevo>
    python scripts/pipeline_temas/run_domain.py --domain projects --run-id <nuevo> --from 02
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

TOPIC_KEYS = ("unit_id", "topic", "description", "evidence", "confidence", "evidence_verbatim")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--from-run", required=True)
    parser.add_argument("--to-run", required=True, help="Debe tener ya la etapa 01 corrida.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = lb_config.load()
    src = lb_store.open_store(cfg, args.domain, args.from_run)
    dst = lb_store.open_store(cfg, args.domain, args.to_run)
    new_units = {u["unit_id"]: u["text"] for u in dst.read_units()}
    if not new_units:
        raise SystemExit(f"'{args.to_run}' no tiene unidades: correr antes 01_prep_units.py.")
    old_units = {u["unit_id"]: u["text"] for u in src.read_units()}
    same = {uid for uid, text in new_units.items() if old_units.get(uid) == text}
    changed = {uid for uid in new_units if uid in old_units} - same
    added = set(new_units) - set(old_units)

    # Extraccion: del cache de la corrida vieja; si falta ahi, del store.
    src_cache = REPO_ROOT / "salidas" / "topics" / args.domain / args.from_run / "02_extraction_cache.jsonl"
    records = {}
    if src_cache.exists():
        for line in src_cache.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                if rec["unit_id"] in same and not rec.get("error"):
                    records[rec["unit_id"]] = rec
    by_unit = {}
    for row in src.read_extracted_topics():
        if row["unit_id"] in same and row["unit_id"] not in records:
            by_unit.setdefault(row["unit_id"], []).append({k: row.get(k) for k in TOPIC_KEYS})
    for uid, topics in by_unit.items():
        records[uid] = {"unit_id": uid, "topics": topics, "seeded_from": args.from_run}
    embeddings = [e for e in src.read_unit_embeddings() if e["unit_id"] in same]

    print(f"  unidades en '{args.to_run}': {len(new_units):,}")
    print(f"    mismo texto que en '{args.from_run}': {len(same):,}")
    print(f"    texto distinto: {len(changed):,}   nuevas: {len(added):,}")
    print(f"  extraccion reusada: {len(records):,}   embeddings reusados: {len(embeddings):,}")
    print(f"  la etapa 02 consultara al LLM por ~{len(new_units) - len(records):,} unidades")
    if args.dry_run:
        print("  --dry-run: no se escribe nada.")
        return

    out_dir = REPO_ROOT / "salidas" / "topics" / args.domain / args.to_run
    out_dir.mkdir(parents=True, exist_ok=True)
    cache = out_dir / "02_extraction_cache.jsonl"
    existing = set()
    if cache.exists():
        existing = {json.loads(l)["unit_id"] for l in cache.read_text(encoding="utf-8").splitlines() if l.strip()}
    with cache.open("a", encoding="utf-8") as handle:
        for uid, rec in records.items():
            if uid not in existing:
                handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if embeddings:
        dst.write_unit_embeddings(embeddings)
    (out_dir / "seed_same_text.json").write_text(json.dumps({
        "from_run": args.from_run, "to_run": args.to_run, "domain": args.domain,
        "units": len(new_units), "same_text": len(same), "changed_text": sorted(changed),
        "added": sorted(added), "extraction_reused": len(records),
        "embeddings_reused": len(embeddings)}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  listo -> {cache.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Carga los temas ya producidos a mano en el formato del pipeline nuevo.

Puente temporal. Los temas de proyectos que el equipo ya tiene
(`salidas/topics/projects_topics_consolidated.json`: 893 proyectos, 985 temas
extraidos, 49 temas normalizados) se produjeron leyendo cada proyecto, antes de
que hubiera Bedrock. Este script los importa como si fueran la salida de las
etapas 01-03, de modo que las etapas 04 (cuantificacion) y 05 (reportes) se
pueden correr HOY sobre datos reales, sin esperar a que AWS este configurado.

Cuando Bedrock este disponible, se corre el pipeline de verdad desde la etapa
01 y este script deja de hacer falta. Sirve entonces para comparar: los temas
del LLM contra los que ya se revisaron a mano.

No calcula centroides (no hay embeddings), asi que la etapa 04 solo puede
correrse con --affinity extraction sobre un run sembrado asi.

    python scripts/pipeline_temas/seed_from_legacy.py --domain projects \
        --source salidas/topics/projects_topics_consolidated.json --run-id legacy-49
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _stage import REPO_ROOT, StageContext, base_parser, git_commit, main_wrapper  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
import lb_domains  # noqa: E402

DEFAULT_SOURCE = REPO_ROOT / "salidas" / "topics" / "projects_topics_consolidated.json"


def slug(index: int) -> str:
    return f"tema-{index:03d}"


@main_wrapper
def main():
    parser = base_parser(__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                        help="JSON de temas ya consolidados.")
    args = parser.parse_args()

    with StageContext(args, "00_seed_from_legacy", new_run=not args.run_id) as ctx:
        data = json.loads(args.source.read_text(encoding="utf-8"))
        normalized = data["normalized_topics"]
        unit_topics = data.get("project_topics") or data.get("unit_topics") or []

        # nombre de tema extraido -> topic_id consolidado
        lookup: dict[str, str] = {}
        topics = []
        for index, entry in enumerate(normalized):
            topic_id = slug(index)
            topics.append({
                "topic_id": topic_id,
                "label": entry["normalized_topic"],
                "description": entry.get("description", ""),
                "num_variants": entry.get("count", len(entry.get("variants", []))),
                "centroid": None,   # sin embeddings en la version manual
                "variants": entry.get("variants", []),
            })
            for name in entry.get("variants", []) + entry.get("component_topics", []):
                lookup.setdefault(name.strip().lower(), topic_id)

        # Unidades: se reusa el CSV de origen del dominio para tener el texto y
        # los metadatos reales, restringido a las que tienen temas.
        rows = lb_domains.read_source(ctx.domain)
        all_units, _ = lb_domains.to_units(
            ctx.domain, rows, int(ctx.cfg.get("topics.max_text_chars", 6000)))
        by_id = {u["unit_id"]: u for u in all_units}

        units, extracted, topic_map, unmapped, missing_units = [], [], [], [], []
        for entry in unit_topics:
            unit_id = str(entry.get("project_id") or entry.get("unit_id"))
            unit = by_id.get(unit_id)
            if unit is None:
                # El JSON manual se hizo con otra version del CSV; se conserva
                # lo que trae el propio JSON para no perder la fila.
                missing_units.append(unit_id)
                unit = {"unit_id": unit_id, "title": entry.get("title", ""),
                        "year": entry.get("year"), "grouping": entry.get("executing_unit", ""),
                        "knowledge_area": entry.get("knowledge_area", ""),
                        "text": entry.get("title", ""), "text_sources": ["title"],
                        "source_row": {}}
            units.append(unit)
            for item in entry.get("topics", []):
                topic_id = lookup.get(item["topic"].strip().lower())
                if topic_id is None:
                    unmapped.append(item["topic"])
                    continue
                topic_map.append({"extracted_index": len(extracted),
                                  "unit_id": unit_id, "topic_id": topic_id,
                                  "similarity": None})
                extracted.append({
                    "unit_id": unit_id,
                    "topic": item["topic"],
                    "description": item.get("description", ""),
                    "evidence": item.get("evidence", ""),
                    "confidence": float(item.get("confidence") or 0.0),
                    "evidence_verbatim": None,   # no verificable a posteriori
                })

        print(f"  unidades={len(units):,}  temas extraidos={len(extracted):,}  "
              f"temas normalizados={len(topics)}")
        if unmapped:
            print(f"  AVISO: {len(unmapped)} temas extraidos sin tema normalizado "
                  f"(p.ej. {unmapped[0]!r}); no entran en la cuantificacion.")
        if missing_units:
            print(f"  AVISO: {len(missing_units)} unidades del JSON no estan en "
                  f"{ctx.domain.source_csv.name}; se usa el texto del propio JSON.")
        if args.dry_run:
            print("  --dry-run: no se escribe nada.")
            return

        ctx.stage.units_processed = len(units)
        ctx.store.start_run(ctx.cfg.as_dict(), git_commit())
        ctx.store.write_units(units)
        ctx.store.write_extracted_topics(extracted)
        ctx.store.write_topics(topics)
        ctx.store.write_topic_map(topic_map)
        ctx.store.write_unit_embeddings([])
        print(f"  sembrado en salidas/topics/{ctx.domain_key}/{ctx.run_id}/")
        print("  siguiente: python scripts/pipeline_temas/04_quantify.py "
              f"--domain {ctx.domain_key} --run-id {ctx.run_id} --affinity extraction")


if __name__ == "__main__":
    main()

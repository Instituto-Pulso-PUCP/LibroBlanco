# -*- coding: utf-8 -*-
"""Aggregates the pilot + every processed batch into one growing topics
dataset. Each batch is a self-contained `build_batchNN_topics_data.py` module
(see build_batch01_topics_data.py for the pattern) exposing:

    EXTRACTED_BATCHNN        project_id -> [(topic, description, evidence, confidence), ...]
    REUSE_BATCHNN             [(existing_normalized_topic_name, [(project_id, topic_text), ...]), ...]
    NEW_NORMALIZED_BATCHNN    {normalized_topic_name: (description, [(project_id, topic_text), ...])}

This script just merges them in order (pilot first, then batch01, batch02,
...), applies REUSE extensions before NEW_NORMALIZED so an earlier batch's
new topic can be reused by a later one, and runs the same sanity checks as
before. To add a batch: write its build_batchNN_topics_data.py, add its
number to BATCH_NUMBERS below, run this script.

See docs/topic_normalization_pipeline.md.
"""
import importlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOPICS_DIR = REPO_ROOT / "salidas" / "topics"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_pilot_topics_data as pilot  # noqa: E402  (side effect: loads pilot units)

BATCH_NUMBERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # extend as new batches are added, e.g. [1, 2, 3]
OUT_PATH = TOPICS_DIR / "projects_topics_current.json"

units = list(pilot.units)
units_by_id = {u["project_id"]: u for u in units}
EXTRACTED = dict(pilot.EXTRACTED)
NORMALIZED = {name: (desc, list(variants)) for name, (desc, variants) in pilot.NORMALIZED.items()}


def extend(name, new_variants):
    desc, variants = NORMALIZED[name]
    NORMALIZED[name] = (desc, variants + new_variants)


for n in BATCH_NUMBERS:
    tag = f"batch{n:02d}"
    units_path = TOPICS_DIR / f"projects_units_{tag}.json"
    with open(units_path, encoding="utf-8") as f:
        batch_units = json.load(f)
    for u in batch_units:
        u["project_id"] = u.pop("unit_id")
    units.extend(batch_units)
    units_by_id.update({u["project_id"]: u for u in batch_units})

    mod = importlib.import_module(f"build_{tag}_topics_data")
    EXTRACTED.update(getattr(mod, f"EXTRACTED_{tag.upper()}"))
    for name, new_variants in getattr(mod, f"REUSE_{tag.upper()}"):
        extend(name, new_variants)
    NORMALIZED.update(getattr(mod, f"NEW_NORMALIZED_{tag.upper()}"))


def main():
    missing = [pid for pid in EXTRACTED if pid not in units_by_id]
    assert not missing, f"unit ids missing from units file: {missing}"
    assert set(EXTRACTED) == set(units_by_id), (
        f"mismatch between extracted project ids and units file: "
        f"extra_in_units={set(units_by_id)-set(EXTRACTED)} extra_in_extracted={set(EXTRACTED)-set(units_by_id)}"
    )

    project_topics = []
    total_extracted = 0
    for pid, topics in EXTRACTED.items():
        u = units_by_id[pid]
        entry = {
            "project_id": pid,
            "title": u["title"],
            "executing_unit": u["executing_unit"],
            "knowledge_area": u["knowledge_area"],
            "year": u["year"],
            "topics": [
                {"topic": t, "description": d, "evidence": e, "confidence": c}
                for (t, d, e, c) in topics
            ],
        }
        project_topics.append(entry)
        total_extracted += len(topics)

    topic_lookup = {}
    for pid, topics in EXTRACTED.items():
        for (t, d, e, c) in topics:
            topic_lookup[(pid, t)] = (d, e, c)

    normalized_topics = []
    variant_to_norm_count = {}
    for name, (description, variants) in NORMALIZED.items():
        confidences = []
        project_ids = []
        executing_units = []
        evidences = []
        variant_texts = []
        for pid, topic_text in variants:
            d, e, c = topic_lookup[(pid, topic_text)]
            confidences.append(c)
            if pid not in project_ids:
                project_ids.append(pid)
            eu = units_by_id[pid]["executing_unit"]
            if eu not in executing_units:
                executing_units.append(eu)
            variant_texts.append(topic_text)
            evidences.append({
                "project_id": pid,
                "title": units_by_id[pid]["title"],
                "topic": topic_text,
            })
            variant_to_norm_count[topic_text] = variant_to_norm_count.get(topic_text, 0) + 1

        normalized_topics.append({
            "normalized_topic": name,
            "description": description,
            "variants": variant_texts,
            "project_ids": project_ids,
            "executing_units": executing_units,
            "count": len(variants),
            "avg_confidence": round(sum(confidences) / len(confidences), 2),
            "evidences": evidences,
        })

    all_topic_texts = [t for topics in EXTRACTED.values() for (t, d, e, c) in topics]
    dupes = [t for t in set(all_topic_texts) if all_topic_texts.count(t) > 1]
    assert not dupes, f"duplicate topic text across projects (ambiguous): {dupes}"
    unmapped = [t for t in all_topic_texts if variant_to_norm_count.get(t, 0) == 0]
    assert not unmapped, f"extracted topics not mapped to any normalized topic: {unmapped}"
    multi_mapped = [t for t, n in variant_to_norm_count.items() if n > 1]
    assert not multi_mapped, f"topics mapped to more than one normalized topic: {multi_mapped}"

    last_batch = f"lote {BATCH_NUMBERS[-1]:02d}" if BATCH_NUMBERS else "piloto"
    data = {
        "metadata": {
            "dataset_title": "Proyectos de investigación PUCP cerrados (2010-2020) — cobertura completa",
            "source_file": "salidas/01_projects_closed_con_cris.csv",
            "num_projects": len(project_topics),
            "num_extracted_topics": total_extracted,
            "num_normalized_topics": len(normalized_topics),
            "note": (
                f"Piloto (36 proyectos) + lotes {BATCH_NUMBERS} ({len(project_topics)-36} "
                "proyectos adicionales) = cobertura completa del universo de proyectos con "
                "texto utilizable (una muestra adicional con --sample 100 tras el lote 10 "
                "devolvió 0 proyectos nuevos). Extraccion y normalizacion realizadas leyendo "
                "cada proyecto (no hay API de LLM configurada en este entorno); temas "
                "normalizados reusados donde un tema nuevo encajaba claramente en uno "
                "existente, y creados nuevos para areas tematicas no cubiertas antes. "
                "Pendiente: consolidacion de temas normalizados cercanos y el contraste con "
                "un objetivo (ODS / plan CEPLAN) una vez definido — ver "
                "docs/topic_normalization_pipeline.md."
            ),
        },
        "projects": units,
        "project_topics": project_topics,
        "normalized_topics": normalized_topics,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"OK: {len(project_topics)} projects, {total_extracted} extracted topics, "
          f"{len(normalized_topics)} normalized topics -> {OUT_PATH}")


if __name__ == "__main__":
    main()

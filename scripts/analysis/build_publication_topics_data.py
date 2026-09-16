# -*- coding: utf-8 -*-
"""Aggregates every processed publication batch into one growing topics
dataset, mirroring build_topics_data.py for projects but over publication
"units" (see publication_extraction_prep.py) and a separate normalized-topic
pool (team decision: publications are not merged into the projects taxonomy
yet). Each batch is a self-contained `build_pub_batchNN_topics_data.py`
module exposing:

    EXTRACTED_PUBBATCHNN        unit_id -> [(topic, description, evidence, confidence), ...]
    REUSE_PUBBATCHNN             [(existing_normalized_topic_name, [(unit_id, topic_text), ...]), ...]
    NEW_NORMALIZED_PUBBATCHNN    {normalized_topic_name: (description, [(unit_id, topic_text), ...])}

Output shape matches projects_topics_current.json (reusing the same
"projects"/"project_topics" field names, with unit_id standing in for
project_id) so build_topic_explorer.py renders it unchanged.
"""
import importlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOPICS_DIR = REPO_ROOT / "salidas" / "topics"
sys.path.insert(0, str(Path(__file__).resolve().parent))

BATCH_NUMBERS = [1, 2, 3, 4, 5, 6, 7, 8]  # extend as new batches are added, e.g. [1, 2, 3]
OUT_PATH = TOPICS_DIR / "publications_topics_current.json"

units = []
units_by_id = {}
EXTRACTED = {}
NORMALIZED = {}


def extend(name, new_variants):
    desc, variants = NORMALIZED[name]
    NORMALIZED[name] = (desc, variants + new_variants)


for n in BATCH_NUMBERS:
    tag = f"pubbatch{n:02d}"
    units_path = TOPICS_DIR / f"publications_units_batch{n:02d}.json"
    with open(units_path, encoding="utf-8") as f:
        batch_units = json.load(f)
    units.extend(batch_units)
    units_by_id.update({u["unit_id"]: u for u in batch_units})

    mod = importlib.import_module(f"build_pub_batch{n:02d}_topics_data")
    EXTRACTED.update(getattr(mod, f"EXTRACTED_{tag.upper()}"))
    for name, new_variants in getattr(mod, f"REUSE_{tag.upper()}"):
        extend(name, new_variants)
    NORMALIZED.update(getattr(mod, f"NEW_NORMALIZED_{tag.upper()}"))


def main():
    missing = [uid for uid in EXTRACTED if uid not in units_by_id]
    assert not missing, f"unit ids missing from units file: {missing}"
    assert set(EXTRACTED) == set(units_by_id), (
        f"mismatch between extracted unit ids and units file: "
        f"extra_in_units={set(units_by_id)-set(EXTRACTED)} extra_in_extracted={set(EXTRACTED)-set(units_by_id)}"
    )

    publication_topics = []
    total_extracted = 0
    for uid, topics in EXTRACTED.items():
        u = units_by_id[uid]
        entry = {
            "project_id": uid,
            "title": u["title"],
            "executing_unit": u["executing_unit"],
            "knowledge_area": u["knowledge_area"],
            "year": u["year"],
            "result_type": u["result_type"],
            "journal": u["journal"],
            "source_project_id": u["project_id"],
            "source_project_title": u["project_title"],
            "topics": [
                {"topic": t, "description": d, "evidence": e, "confidence": c}
                for (t, d, e, c) in topics
            ],
        }
        publication_topics.append(entry)
        total_extracted += len(topics)

    topic_lookup = {}
    for uid, topics in EXTRACTED.items():
        for (t, d, e, c) in topics:
            topic_lookup[(uid, t)] = (d, e, c)

    normalized_topics = []
    variant_to_norm_count = {}
    for name, (description, variants) in NORMALIZED.items():
        confidences = []
        project_ids = []
        executing_units = []
        evidences = []
        variant_texts = []
        for uid, topic_text in variants:
            d, e, c = topic_lookup[(uid, topic_text)]
            confidences.append(c)
            if uid not in project_ids:
                project_ids.append(uid)
            eu = units_by_id[uid]["executing_unit"]
            if eu not in executing_units:
                executing_units.append(eu)
            variant_texts.append(topic_text)
            evidences.append({
                "project_id": uid,
                "title": units_by_id[uid]["title"],
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
    assert not dupes, f"duplicate topic text across units (ambiguous): {dupes}"
    unmapped = [t for t in all_topic_texts if variant_to_norm_count.get(t, 0) == 0]
    assert not unmapped, f"extracted topics not mapped to any normalized topic: {unmapped}"
    multi_mapped = [t for t, n in variant_to_norm_count.items() if n > 1]
    assert not multi_mapped, f"topics mapped to more than one normalized topic: {multi_mapped}"

    projects_field = [
        {**u, "project_id": u["unit_id"]} for u in units
    ]

    data = {
        "metadata": {
            "dataset_title": "Publicaciones vinculadas a proyectos PUCP cerrados (2010-2020)",
            "source_file": "salidas/07_project_publication_ground_truth.csv",
            "num_projects": len(publication_topics),
            "num_extracted_topics": total_extracted,
            "num_normalized_topics": len(normalized_topics),
            "note": (
                f"Lote(s) {BATCH_NUMBERS} ({len(publication_topics)} de 562 resultados declarados "
                "con texto utilizable). Pool de temas normalizados independiente del de proyectos "
                "(432 extraidos / 49 consolidados) por decision del equipo; pendiente reconciliar "
                "ambas taxonomias. Extraccion y normalizacion hechas leyendo cada resultado (no hay "
                "API de LLM configurada en este entorno)."
            ),
        },
        "projects": projects_field,
        "project_topics": publication_topics,
        "normalized_topics": normalized_topics,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"OK: {len(publication_topics)} publications, {total_extracted} extracted topics, "
          f"{len(normalized_topics)} normalized topics -> {OUT_PATH}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Maps publications' 352 normalized topics onto projects' existing 49
consolidated normalized topics (instead of clustering publications into a
new, separate set), producing one unified taxonomy across both tracks.

Rationale: publications are declared results of the same 893 tracked
projects, so most publication topics should already be thematically close
to their own source project's topic. This assigns each of the 352
publication-topic buckets to its single best-matching bucket among the 49
(embedding cosine similarity, minilm-multilingual — same validated model
used for policy alignment), folding in every underlying paper-level
extracted topic. The 49 set itself is never expanded or renamed; every
publication topic is force-assigned to its best fit, with the match score
kept visible so a weak forced fit isn't presented as confidently as a
strong one.

Usage::

    python scripts/analysis/consolidate_publications_into_49.py
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))
from embeddings import compute_embeddings  # noqa: E402

ROOT = SCRIPTS_DIR.parent
PROJECTS_PATH = ROOT / "salidas" / "topics" / "projects_topics_consolidated.json"
PUBLICATIONS_PATH = ROOT / "salidas" / "topics" / "publications_topics_current.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="minilm-multilingual",
                         help="Embedding model key from scripts/lib/embeddings.py registry")
    args = parser.parse_args()
    model_key = args.model

    out_path = ROOT / "salidas" / "topics" / f"atlas_temas_unificado_{model_key}.json"
    review_path = ROOT / "salidas" / "topics" / f"publications_to_49_mapping_review_{model_key}.md"

    proj = json.load(open(PROJECTS_PATH, encoding="utf-8"))
    pub = json.load(open(PUBLICATIONS_PATH, encoding="utf-8"))

    proj_norms = proj["normalized_topics"]  # 49
    pub_norms = pub["normalized_topics"]  # 352
    print(f"{len(proj_norms)} temas de proyectos (destino), {len(pub_norms)} temas de publicaciones (a mapear)")

    proj_texts = [f"{n['normalized_topic']}. {n['description']}" for n in proj_norms]
    pub_texts = [f"{n['normalized_topic']}. {n['description']}" for n in pub_norms]
    all_emb, meta = compute_embeddings(proj_texts + pub_texts, model_key)
    print("embeddings:", meta)
    proj_emb = all_emb[: len(proj_norms)]
    pub_emb = all_emb[len(proj_norms):]

    sim = pub_emb @ proj_emb.T  # (352, 49)
    order = np.argsort(-sim, axis=1)
    best_idx = order[:, 0]
    best_score = sim[np.arange(len(pub_norms)), best_idx]
    runner_up_score = sim[np.arange(len(pub_norms)), order[:, 1]]
    margin = best_score - runner_up_score
    # jina-v5-nano compresses every top score into a narrow high band (~0.55-0.97
    # across this whole corpus, even for topics with no real thematic home), so
    # raw top1 score can't be used as a confidence signal for that model — the
    # margin to the runner-up can. For minilm-multilingual (and other models
    # with a well-spread score distribution) raw score already discriminates
    # fine, so we still report both and let the review file sort on whichever
    # is more informative for this model.
    confidence = margin if model_key == "jina-v5-nano" else best_score

    # --- Confidence lookups (per-unit, per-topic-text) from both sources ---
    def build_topic_lookup(units_topics_field):
        lookup = {}
        for entry in units_topics_field:
            for t in entry["topics"]:
                lookup[(entry["project_id"], t["topic"])] = t["confidence"]
        return lookup

    proj_conf_lookup = build_topic_lookup(proj["project_topics"])
    pub_conf_lookup = build_topic_lookup(pub["project_topics"])

    # --- Build the 49 merged buckets, starting from the projects' own data ---
    merged = []
    for n in proj_norms:
        merged.append({
            "normalized_topic": n["normalized_topic"],
            "description": n["description"],
            "variants": list(n["variants"]),
            "project_ids": list(n["project_ids"]),
            "executing_units": list(n["executing_units"]),
            "evidences": [{**e, "track": "proyecto"} for e in n["evidences"]],
            "component_topics": n.get("component_topics", []),
            "publication_component_topics": [],
        })

    review_rows = []
    for i, n in enumerate(pub_norms):
        target = int(best_idx[i])
        score = round(float(best_score[i]), 4)
        conf = round(float(confidence[i]), 4)
        bucket = merged[target]
        bucket["variants"].extend(n["variants"])
        for uid in n["project_ids"]:
            if uid not in bucket["project_ids"]:
                bucket["project_ids"].append(uid)
        for eu in n["executing_units"]:
            if eu not in bucket["executing_units"]:
                bucket["executing_units"].append(eu)
        bucket["evidences"].extend([{**e, "track": "publicacion"} for e in n["evidences"]])
        bucket["publication_component_topics"].append({
            "normalized_topic": n["normalized_topic"],
            "description": n["description"],
            "count": n["count"],
            "match_score": score,
            "match_confidence": conf,
        })

        review_rows.append((conf, score, n["normalized_topic"], proj_norms[target]["normalized_topic"], n["count"]))

    # --- Recompute count / avg_confidence from the underlying (unit, topic) confidences ---
    for bucket in merged:
        confidences = []
        for e in bucket["evidences"]:
            uid, topic_text = e["project_id"], e["topic"]
            lookup = proj_conf_lookup if e["track"] == "proyecto" else pub_conf_lookup
            c = lookup.get((uid, topic_text))
            if c is not None:
                confidences.append(c)
        bucket["count"] = len(bucket["variants"])
        bucket["avg_confidence"] = round(sum(confidences) / len(confidences), 2) if confidences else None

    # --- Unified projects/project_topics lists (both tracks, tagged) ---
    projects_field = []
    for p in proj["projects"]:
        projects_field.append({**p, "track": "proyecto"})
    for p in pub["projects"]:
        projects_field.append({**p, "track": "publicacion"})

    project_topics_field = list(proj["project_topics"]) + list(pub["project_topics"])

    data = {
        "metadata": {
            "dataset_title": "Atlas de Temas PUCP — taxonomia unificada (proyectos + publicaciones)",
            "num_projects_units": len(proj["projects"]),
            "num_publication_units": len(pub["projects"]),
            "num_normalized_topics": len(merged),
            "embedding_model": model_key,
            "confidence_measure": "margin (top1 - top2)" if model_key == "jina-v5-nano" else "raw top1 score",
            "note": (
                "Los 352 temas normalizados de publicaciones se asignaron (forzado, "
                "mejor-match) a uno de los 49 temas normalizados de proyectos via "
                "similitud coseno de embeddings; el set de 49 no se modifico ni "
                "se amplio. 'publication_component_topics' en cada tema normalizado "
                "guarda match_score (similitud cruda top1) y match_confidence (medida "
                "usada para juzgar que tan forzada es la asignacion; con jina-v5-nano "
                "es el margen top1-top2 porque el score crudo esta comprimido hacia "
                "arriba y no discrimina, con otros modelos es el score crudo)."
            ),
        },
        "projects": projects_field,
        "project_topics": project_topics_field,
        "normalized_topics": merged,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"OK: {len(projects_field)} unidades ({len(proj['projects'])} proyectos + {len(pub['projects'])} publicaciones), "
          f"{len(merged)} temas normalizados -> {out_path}")

    review_rows.sort(key=lambda r: r[0])
    conf_label = "margen (top1 - top2)" if model_key == "jina-v5-nano" else "score (top1)"
    with open(review_path, "w", encoding="utf-8") as f:
        f.write(f"# Revision: mapeo de temas de publicaciones a los 49 temas de proyectos ({model_key})\n\n")
        f.write(f"{len(review_rows)} temas de publicaciones mapeados. Ordenado por confianza ascendente ")
        f.write(f"(confianza = {conf_label}; los primeros son los ajustes mas debiles/forzados, revisar primero).\n\n")
        if model_key == "jina-v5-nano":
            f.write(
                "Nota: con jina-v5-nano el score top1 crudo esta comprimido hacia arriba "
                "(0.56-0.97 en todo el corpus, incluso para temas sin relacion real) y no "
                "sirve como senal de confianza; se usa en su lugar el margen entre el mejor "
                "match y el segundo mejor.\n\n"
            )
        f.write("| confianza | score top1 | tema de publicacion (352) | asignado a (49) | # papers |\n")
        f.write("|---|---|---|---|---|\n")
        for conf, score, pub_name, proj_name, count in review_rows:
            f.write(f"| {conf:.3f} | {score:.3f} | {pub_name} | {proj_name} | {count} |\n")
    print(f"Revision escrita en {review_path}")


if __name__ == "__main__":
    main()

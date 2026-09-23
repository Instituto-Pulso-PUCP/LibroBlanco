"""Adds publication counts to a proyectos-only policy alignment JSON, using
the already-done 352->49 consolidation (see consolidate_publications_into_49.py)
instead of scoring publications against policies separately.

Rationale: publications were already mapped onto the same 49 canonical
topics as projects (`publications_to_49_mapping_review_<modelo>.md`). A
publication doesn't need its own topic-vs-policy embedding score — it
inherits the alignment of whichever of the 49 topics it was consolidated
into. This script just attaches that publication coverage as metadata on
top of an existing proyectos-scoped alignment file, it does not recompute
any embeddings or scores.

Uso:
    python scripts/analysis/enrich_policy_alignment_publications.py \
        --alignment salidas/topics/topic_policy_alignment_minilm-multilingual_proyectos.json \
        --mapping salidas/topics/publications_to_49_mapping_review_minilm-multilingual.md
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROW_RE = re.compile(
    r"^\|\s*([\d.]+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(\d+)\s*\|$"
)


def parse_mapping(path: Path) -> dict[str, list[dict]]:
    """asignado_a (49) -> [{publication_topic, score, count}]"""
    by_target: dict[str, list[dict]] = defaultdict(list)
    with path.open(encoding="utf-8") as f:
        for line in f:
            m = ROW_RE.match(line.strip())
            if not m:
                continue
            score, pub_topic, target, count = m.groups()
            if pub_topic == "tema de publicacion (352)":  # header row
                continue
            by_target[target].append({
                "publication_topic": pub_topic,
                "score": float(score),
                "count": int(count),
            })
    return by_target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alignment", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    args = parser.parse_args()

    by_target = parse_mapping(args.mapping)

    with args.alignment.open(encoding="utf-8") as f:
        data = json.load(f)

    unmatched = set(by_target.keys())
    for topic in data["topics"]:
        entries = by_target.get(topic["normalized_topic"], [])
        unmatched.discard(topic["normalized_topic"])
        entries = sorted(entries, key=lambda e: -e["count"])
        topic["publication_topics"] = entries
        topic["num_publications"] = sum(e["count"] for e in entries)

    data["metadata"]["publications_source"] = str(
        args.mapping.resolve().relative_to(REPO_ROOT)
    )
    data["metadata"]["num_publications_linked"] = sum(
        t["num_publications"] for t in data["topics"]
    )

    with args.alignment.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    zero = [t["normalized_topic"] for t in data["topics"] if t["num_publications"] == 0]
    print(f"{len(data['topics'])} temas enriquecidos con conteos de publicaciones.")
    print(f"Total publicaciones vinculadas: {data['metadata']['num_publications_linked']}")
    if zero:
        print(f"{len(zero)} temas sin ninguna publicacion mapeada: {zero}")
    if unmatched:
        print(f"AVISO: {len(unmatched)} temas del mapping no calzaron con ningun "
              f"normalized_topic del archivo de alineacion: {sorted(unmatched)}")


if __name__ == "__main__":
    main()

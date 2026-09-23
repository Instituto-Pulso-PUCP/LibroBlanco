#!/usr/bin/env python3
"""Clusters CEPLAN's 762 atomic megatendencias into ~k candidate groups for
manual review, mirroring cluster_normalized_topics.py's approach for the
projects taxonomy.

Only CEPLAN is clustered: PN/PESEM/PEDN/CONCYTEC/PP (184 documents) are
already few and heterogeneous enough that consolidating them further would
likely just collapse distinct policies together (see conversation that
motivated this script).

Uses jina-v5-nano for the clustering assignment itself (intra-domain
trend-vs-trend similarity, the kind of task jina-v5-nano already wins at per
EXPERIMENTS.md), reusing the already-computed full-corpus chunk embeddings
cache instead of re-embedding anything. This is independent of the fact that
the topic<->policy *alignment* itself uses minilm-multilingual (a
cross-domain task) -- build_ceplan_consolidation.py re-derives each cluster's
alignment-facing vector from the minilm cache, not from these jina vectors.

Usage::

    python scripts/analysis/cluster_ceplan_policies.py --k 60
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster

ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = ROOT / "datos" / "corpus_politicas_chunks.jsonl"
CACHE_DIR = ROOT / "salidas" / "topics" / "policy_alignment_cache"
OUT_DIR = ROOT / "salidas" / "topics" / "consolidation"


def load_corpus():
    chunks = []
    with open(CORPUS_PATH, encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))
    return chunks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=60)
    parser.add_argument("--cluster-model", default="jina-v5-nano",
                         help="Modelo usado solo para decidir agrupacion (tarea intra-dominio)")
    args = parser.parse_args()

    chunks = load_corpus()
    ceplan_idx = [i for i, c in enumerate(chunks) if c["fuente"] == "CEPLAN"]
    print(f"{len(ceplan_idx)} tendencias CEPLAN de {len(chunks)} chunks totales.")

    cache_path = CACHE_DIR / f"chunk_embeddings_{args.cluster_model}.npy"
    all_embeddings = np.load(cache_path)
    embeddings = all_embeddings[ceplan_idx]
    print(f"Usando embeddings cacheados de {args.cluster_model}: {cache_path.name}, "
          f"shape filtrada={embeddings.shape}")

    Z = linkage(embeddings, method="ward")
    labels = fcluster(Z, t=args.k, criterion="maxclust") - 1
    n_clusters = len(set(labels.tolist()))
    print(f"Cut tree at k={args.k} -> {n_clusters} actual clusters.")

    rows = []
    for local_i, label in zip(range(len(ceplan_idx)), labels):
        c = chunks[ceplan_idx[local_i]]
        rows.append({
            "cluster": int(label),
            "doc_id": c["doc_id"],
            "titulo": c["titulo"],
            "texto": c["texto"],
        })
    df = pd.DataFrame(rows)

    cluster_size = df.groupby("cluster").size().sort_values(ascending=False)
    order_map = {c: i for i, c in enumerate(cluster_size.index)}
    df["cluster_order"] = df["cluster"].map(order_map)
    df = df.sort_values(["cluster_order", "doc_id"]).drop(columns="cluster_order")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    review_path = OUT_DIR / "ceplan_cluster_review.csv"
    df.to_csv(review_path, index=False, encoding="utf-8-sig")
    print(f"Wrote review file: {review_path} ({len(df)} rows, {n_clusters} clusters)")

    md_lines = [f"# CEPLAN cluster review — {len(ceplan_idx)} tendencias -> {n_clusters} clusters (target k={args.k})", ""]
    for c in cluster_size.index:
        sub = df[df["cluster"] == c]
        md_lines.append(f"## Cluster {c} — {len(sub)} tendencias")
        for _, row in sub.iterrows():
            md_lines.append(f"- **{row['titulo']}** ({row['doc_id']})")
        md_lines.append("")
    md_path = OUT_DIR / "ceplan_cluster_review.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Wrote markdown summary: {md_path}")


if __name__ == "__main__":
    main()

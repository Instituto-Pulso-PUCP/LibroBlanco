#!/usr/bin/env python3
"""Cluster the 432 normalized topics into ~50 candidate groups for manual review.

Embeds each normalized topic's name + description, cuts a ward linkage tree at
--k groups, and writes a review CSV (one row per normalized topic, grouped by
cluster) plus a markdown summary so a human can merge each cluster into one
final consolidated topic.

Usage::

    python cluster_normalized_topics.py --k 50 --model minilm-multilingual
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR / 'lib'))

from embeddings import compute_embeddings  # noqa: E402

ROOT = SCRIPTS_DIR.parent
DATA_PATH = ROOT / 'salidas' / 'topics' / 'projects_topics_current.json'
OUT_DIR = ROOT / 'salidas' / 'topics' / 'consolidation'


def load_normalized_topics():
    with open(DATA_PATH, encoding='utf-8') as f:
        data = json.load(f)
    return data['normalized_topics']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--k', type=int, default=50)
    parser.add_argument('--model', default='minilm-multilingual')
    args = parser.parse_args()

    norms = load_normalized_topics()
    texts = [f"{n['normalized_topic']}. {n['description']}" for n in norms]
    print(f'{len(norms)} normalized topics loaded.', flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    emb_path = OUT_DIR / f'embeddings_{args.model}.npy'
    if emb_path.exists():
        embeddings = np.load(emb_path)
        print(f'Using cached embeddings ({emb_path.name}), shape={embeddings.shape}', flush=True)
    else:
        embeddings, meta = compute_embeddings(texts, args.model)
        np.save(emb_path, embeddings)
        print(f'Computed embeddings, shape={embeddings.shape}', flush=True)

    Z = linkage(embeddings, method='ward')
    labels = fcluster(Z, t=args.k, criterion='maxclust') - 1
    n_clusters = len(set(labels.tolist()))
    print(f'Cut tree at k={args.k} -> {n_clusters} actual clusters.', flush=True)

    rows = []
    for n, label in zip(norms, labels):
        rows.append({
            'cluster': int(label),
            'normalized_topic': n['normalized_topic'],
            'description': n['description'],
            'count': n['count'],
            'n_projects': len(n['project_ids']),
            'avg_confidence': n['avg_confidence'],
        })
    df = pd.DataFrame(rows)

    # order clusters by total project coverage (biggest clusters first), and
    # within a cluster by variant count (most-covered topic first) so the
    # review file reads largest-and-most-important-first.
    cluster_size = df.groupby('cluster')['n_projects'].sum().sort_values(ascending=False)
    order_map = {c: i for i, c in enumerate(cluster_size.index)}
    df['cluster_order'] = df['cluster'].map(order_map)
    df = df.sort_values(['cluster_order', 'n_projects'], ascending=[True, False]).drop(columns='cluster_order')

    review_path = OUT_DIR / 'cluster_review.csv'
    df.to_csv(review_path, index=False, encoding='utf-8-sig')
    print(f'Wrote review file: {review_path} ({len(df)} rows, {n_clusters} clusters)', flush=True)

    md_lines = [f'# Consolidation review — {len(norms)} normalized topics -> {n_clusters} clusters (target k={args.k})', '']
    for c in cluster_size.index:
        sub = df[df['cluster'] == c]
        total_projects = sub['n_projects'].sum()
        md_lines.append(f'## Cluster {c} — {len(sub)} topics, {total_projects} project-mentions')
        for _, row in sub.iterrows():
            md_lines.append(f"- **{row['normalized_topic']}** ({row['n_projects']} proj, conf {row['avg_confidence']}) — {row['description']}")
        md_lines.append('')
    md_path = OUT_DIR / 'cluster_review.md'
    md_path.write_text('\n'.join(md_lines), encoding='utf-8')
    print(f'Wrote markdown summary: {md_path}', flush=True)


if __name__ == '__main__':
    main()

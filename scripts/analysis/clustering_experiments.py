#!/usr/bin/env python3
"""Compare embedding models x clustering methods on the project/publication text.

Runs every (embedding model, clustering method) combination on one dataset,
evaluates each with silhouette / Davies-Bouldin / Calinski-Harabasz, and writes
a comparison table plus per-combination cluster labels (with a 3D PCA
projection for plotting) — so the results can be scanned to see which
combinations actually found structure vs. which just returned noise or one
giant cluster.

Usage::

    python clustering_experiments.py --dataset projects
    python clustering_experiments.py --dataset publications
    python clustering_experiments.py --dataset publications --models tfidf,jina-v5-nano --limit 500
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR / 'lib'))

from embeddings import EMBEDDING_MODELS, compute_embeddings
from clustering import CLUSTERING_METHODS, run_clustering

ROOT = SCRIPTS_DIR.parent
OUT = ROOT / 'salidas'

DATASETS = {
    'projects': {
        'source': OUT / '01_projects_closed.csv',
        'id_col': 'project_id',
        'text_columns': ['title', 'project_type', 'knowledge_area', 'research_line', 'funding_type', 'funder'],
    },
    'publications': {
        'source': OUT / '03_publications_master.csv',
        'id_col': 'publication_id',
        'text_columns': ['title', 'abstract', 'keywords'],
    },
}


def clean_text(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''
    return str(value).strip()


def build_text(row, columns):
    parts = [clean_text(row.get(col)) for col in columns]
    return ' '.join(part for part in parts if part)


def load_dataset(name, limit=None):
    config = DATASETS[name]
    df = pd.read_csv(config['source'], dtype=str, keep_default_na=False)
    df['cluster_text'] = df.apply(lambda row: build_text(row, config['text_columns']), axis=1)
    df = df[df['cluster_text'].str.strip() != ''].reset_index(drop=True)
    if limit:
        df = df.head(limit).reset_index(drop=True)
    return df, config['id_col']


def get_or_compute_embeddings(texts, model_key, cache_dir):
    cache_dir.mkdir(parents=True, exist_ok=True)
    emb_path = cache_dir / f'embeddings_{model_key}.npy'
    meta_path = cache_dir / f'embeddings_{model_key}.meta.json'
    if emb_path.exists() and meta_path.exists():
        metadata = json.loads(meta_path.read_text(encoding='utf-8'))
        if metadata.get('n_samples') == len(texts):
            print(f'  [{model_key}] using cached embeddings ({emb_path.name})', flush=True)
            return np.load(emb_path), metadata
    print(f'  [{model_key}] computing embeddings for {len(texts)} texts...', flush=True)
    started = time.time()
    embeddings, metadata = compute_embeddings(texts, model_key)
    metadata['seconds'] = round(time.time() - started, 1)
    np.save(emb_path, embeddings)
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  [{model_key}] done in {metadata["seconds"]}s, shape={embeddings.shape}', flush=True)
    return embeddings, metadata


def run_experiment(dataset_name, model_keys, method_names, limit=None, output_dir=None):
    df, id_col = load_dataset(dataset_name, limit=limit)
    print(f'Dataset "{dataset_name}": {len(df)} rows with usable text.', flush=True)

    cache_dir = output_dir or (OUT / 'clustering' / dataset_name)
    cache_dir.mkdir(parents=True, exist_ok=True)
    df[[id_col, 'cluster_text']].to_csv(cache_dir / 'row_texts.csv', index=False, encoding='utf-8-sig')

    results = []
    for model_key in model_keys:
        embeddings, emb_meta = get_or_compute_embeddings(df['cluster_text'].tolist(), model_key, cache_dir)
        pca_coords = PCA(n_components=3, random_state=42).fit_transform(embeddings)

        for method in method_names:
            print(f'  [{model_key}] running {method}...', flush=True)
            started = time.time()
            labels, metrics, params = run_clustering(embeddings, method)
            seconds = round(time.time() - started, 1)

            labels_df = pd.DataFrame({
                id_col: df[id_col],
                'cluster_label': labels,
                'pca_1': pca_coords[:, 0],
                'pca_2': pca_coords[:, 1],
                'pca_3': pca_coords[:, 2],
            })
            labels_path = cache_dir / f'labels_{model_key}__{method}.csv'
            labels_df.to_csv(labels_path, index=False, encoding='utf-8-sig')

            row = {
                'embedding_model': model_key,
                'embedding_label': EMBEDDING_MODELS[model_key]['label'],
                'clustering_method': method,
                'seconds': seconds,
                'params': json.dumps(params, ensure_ascii=False),
                **metrics,
            }
            results.append(row)
            print(
                f'    -> n_clusters={metrics["n_clusters"]} silhouette={metrics["silhouette"]} '
                f'davies_bouldin={metrics["davies_bouldin"]} noise_pct={metrics["noise_pct"]}% ({seconds}s)',
                flush=True,
            )

    comparison = pd.DataFrame(results).sort_values(
        by='silhouette', ascending=False, na_position='last'
    ).reset_index(drop=True)
    comparison.to_csv(cache_dir / 'comparison_metrics.csv', index=False, encoding='utf-8-sig')
    write_markdown_summary(comparison, dataset_name, len(df), cache_dir / 'comparison_metrics.md')
    print(f'\nWrote comparison table to {cache_dir / "comparison_metrics.csv"}', flush=True)
    return comparison


def write_markdown_summary(comparison, dataset_name, n_rows, path):
    lines = [
        f'# Clustering comparison — {dataset_name} ({n_rows} rows)',
        '',
        '| Embedding | Method | n_clusters | silhouette | davies_bouldin | calinski_harabasz | noise % | seconds |',
        '|---|---|---|---|---|---|---|---|',
    ]
    for _, row in comparison.iterrows():
        lines.append(
            f'| {row["embedding_label"]} | {row["clustering_method"]} | {row["n_clusters"]} | '
            f'{row["silhouette"]} | {row["davies_bouldin"]} | {row["calinski_harabasz"]} | '
            f'{row["noise_pct"]} | {row["seconds"]} |'
        )
    path.write_text('\n'.join(lines), encoding='utf-8')


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True, choices=sorted(DATASETS.keys()))
    parser.add_argument('--models', default=None, help=f'Comma-separated subset of {sorted(EMBEDDING_MODELS.keys())}')
    parser.add_argument('--methods', default=None, help=f'Comma-separated subset of {CLUSTERING_METHODS}')
    parser.add_argument('--limit', type=int, default=None, help='Use only the first N rows (for quick smoke tests).')
    parser.add_argument('--output-dir', type=Path, default=None)
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    model_keys = args.models.split(',') if args.models else list(EMBEDDING_MODELS.keys())
    method_names = args.methods.split(',') if args.methods else list(CLUSTERING_METHODS)
    run_experiment(args.dataset, model_keys, method_names, limit=args.limit, output_dir=args.output_dir)

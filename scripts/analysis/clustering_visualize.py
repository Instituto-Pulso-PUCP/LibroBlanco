#!/usr/bin/env python3
"""Render plots for a clustering_experiments.py run.

Reads comparison_metrics.csv and the per-combo labels_<model>__<method>.csv
files under salidas/clustering/<dataset>/, and writes:

- silhouette_comparison.png: every (embedding, method) combo ranked by silhouette.
- pca_scatter_<model>__<method>.png: 2D PCA projection colored by cluster, for
  the top combo (and any others passed via --scatter-for).

Usage::

    python clustering_visualize.py --dataset projects
    python clustering_visualize.py --dataset publications --scatter-for jina-v5-nano__hdbscan,gte-multilingual-base__hdbscan
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR / 'lib'))
from embeddings import EMBEDDING_MODELS
from clustering import CLUSTERING_METHODS

ROOT = SCRIPTS_DIR.parent
OUT = ROOT / 'salidas' / 'clustering'

# Validated categorical slots (dataviz skill palette, light mode, all-pairs safe
# up to 4 series — see references/palette.md). Noise (-1) is muted gray, not a slot.
CLUSTER_COLORS = ['#2a78d6', '#1baf7a', '#008300', '#4a3aa7', '#eb6834']
NOISE_COLOR = '#c3c2b7'
BAR_COLOR = '#2a78d6'
INK_PRIMARY = '#0b0b0b'
INK_SECONDARY = '#52514e'
INK_MUTED = '#898781'
GRIDLINE = '#e1e0d9'
AXIS = '#c3c2b7'
SURFACE = '#fcfcfb'


def _style_axes(ax):
    ax.set_facecolor(SURFACE)
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    for spine in ('left', 'bottom'):
        ax.spines[spine].set_color(AXIS)
    ax.tick_params(colors=INK_MUTED, labelsize=9)


def plot_silhouette_comparison(comparison, dataset_name, output_path):
    df = comparison.dropna(subset=['silhouette']).sort_values('silhouette', ascending=True)
    labels = [f'{row.embedding_label} — {row.clustering_method}' for row in df.itertuples()]

    fig, ax = plt.subplots(figsize=(9, max(3, 0.35 * len(df) + 1)))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    bars = ax.barh(labels, df['silhouette'], color=BAR_COLOR, height=0.6, zorder=3)
    best_idx = len(df) - 1
    bars[best_idx].set_color('#184f95')  # darker step: same hue, marks the winner

    for i, (bar, value) in enumerate(zip(bars, df['silhouette'])):
        ax.text(value + 0.004, bar.get_y() + bar.get_height() / 2, f'{value:.3f}',
                 va='center', ha='left', fontsize=8, color=INK_SECONDARY)

    ax.set_xlabel('Silhouette score (higher = more separated clusters)', color=INK_SECONDARY, fontsize=9)
    fig.suptitle(f'Clustering comparison — {dataset_name} ({len(comparison)} combinations tested)',
                 color=INK_PRIMARY, fontsize=13, fontweight='bold', x=0.02, ha='left')
    ax.xaxis.grid(True, color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    _style_axes(ax)
    ax.spines['left'].set_visible(False)
    ax.tick_params(axis='y', length=0)

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def plot_pca_scatter(labels_df, id_col, title, output_path):
    fig, ax = plt.subplots(figsize=(8, 6.5))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    noise = labels_df[labels_df['cluster_label'] == -1]
    if len(noise):
        ax.scatter(noise['pca_1'], noise['pca_2'], s=10, color=NOISE_COLOR,
                   alpha=0.5, linewidths=0, label=f'noise (n={len(noise)})', zorder=2)

    real = labels_df[labels_df['cluster_label'] != -1]
    for i, cluster_id in enumerate(sorted(real['cluster_label'].unique(), key=int)):
        sub = real[real['cluster_label'] == cluster_id]
        color = CLUSTER_COLORS[i % len(CLUSTER_COLORS)]
        ax.scatter(sub['pca_1'], sub['pca_2'], s=16, color=color, alpha=0.85,
                   linewidths=0, label=f'cluster {cluster_id} (n={len(sub)})', zorder=3)

    ax.set_title(title, color=INK_PRIMARY, fontsize=11, fontweight='bold', loc='left', wrap=True)
    ax.set_xlabel('PCA 1', color=INK_SECONDARY, fontsize=9)
    ax.set_ylabel('PCA 2', color=INK_SECONDARY, fontsize=9)
    ax.grid(True, color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    _style_axes(ax)
    legend = ax.legend(fontsize=8, frameon=False, labelcolor=INK_SECONDARY, loc='best')

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def _cluster_color(cluster_id, n_clusters):
    if n_clusters <= len(CLUSTER_COLORS):
        return CLUSTER_COLORS[int(cluster_id) % len(CLUSTER_COLORS)]
    # Beyond the validated all-pairs cap (4), fall back to a many-hue qualitative
    # colormap: past that count no ordering clears the CVD floors anyway, so here
    # color is a rough visual differentiator, not a validated identity channel —
    # the subplot title (n_clusters, silhouette) carries the actual comparison.
    return plt.get_cmap('tab20')(int(cluster_id) % 20)


def plot_combo_grid(dataset_name, comparison, cache_dir, output_path):
    """One figure, one subplot per (embedding, method) combo — everything at a glance."""
    model_keys = [k for k in EMBEDDING_MODELS if k in comparison['embedding_model'].unique()]
    methods = [m for m in CLUSTERING_METHODS if m in comparison['clustering_method'].unique()]

    fig, axes = plt.subplots(len(model_keys), len(methods),
                             figsize=(3.4 * len(methods), 3.0 * len(model_keys)),
                             squeeze=False)
    fig.patch.set_facecolor(SURFACE)

    for row_i, model_key in enumerate(model_keys):
        for col_i, method in enumerate(methods):
            ax = axes[row_i][col_i]
            ax.set_facecolor(SURFACE)
            for spine in ax.spines.values():
                spine.set_color(GRIDLINE)
            ax.set_xticks([])
            ax.set_yticks([])

            combo = f'{model_key}__{method}'
            labels_path = cache_dir / f'labels_{combo}.csv'
            match = comparison[(comparison['embedding_model'] == model_key) &
                               (comparison['clustering_method'] == method)]
            if not labels_path.exists() or match.empty:
                ax.text(0.5, 0.5, 'missing', ha='center', va='center',
                        color=INK_MUTED, fontsize=8, transform=ax.transAxes)
                continue

            labels_df = pd.read_csv(labels_path)
            row = match.iloc[0]
            noise = labels_df[labels_df['cluster_label'] == -1]
            real = labels_df[labels_df['cluster_label'] != -1]
            n_clusters = real['cluster_label'].nunique()

            if len(noise):
                ax.scatter(noise['pca_1'], noise['pca_2'], s=3, color=NOISE_COLOR,
                          alpha=0.4, linewidths=0, zorder=2)
            for cluster_id in sorted(real['cluster_label'].unique(), key=int):
                sub = real[real['cluster_label'] == cluster_id]
                ax.scatter(sub['pca_1'], sub['pca_2'], s=4,
                          color=_cluster_color(cluster_id, n_clusters), alpha=0.8, linewidths=0, zorder=3)

            sil = row['silhouette']
            sil_text = f'{sil:.3f}' if pd.notna(sil) else 'n/a'
            ax.set_title(f'{method} · k={n_clusters} · sil {sil_text}',
                        fontsize=8, color=INK_PRIMARY, loc='left')

            if col_i == 0:
                ax.set_ylabel(EMBEDDING_MODELS[model_key]['label'], fontsize=9,
                              color=INK_SECONDARY, fontweight='bold')

    fig.suptitle(f'All embedding × clustering combinations — {dataset_name}',
                color=INK_PRIMARY, fontsize=14, fontweight='bold', x=0.01, ha='left')
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(output_path, dpi=140)
    plt.close(fig)
    return output_path


RESEARCH_LINE_COLUMNS = ['research_line', 'research_line_1', 'research_line_2', 'research_line_3', 'research_line_4']
HAS_LINE_COLOR = '#2a78d6'
NO_LINE_COLOR = '#eb6834'


def plot_research_line_coverage(labels_df, title, output_path):
    """Colors the same PCA projection by whether the project had any research-line
    text filled in, to check whether that sparse field (not the topical content) is
    what's driving cluster separation."""
    fig, ax = plt.subplots(figsize=(8, 6.5))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    for has_line, color, label in ((False, NO_LINE_COLOR, 'sin línea de investigación'),
                                    (True, HAS_LINE_COLOR, 'con línea de investigación')):
        sub = labels_df[labels_df['has_research_line'] == has_line]
        ax.scatter(sub['pca_1'], sub['pca_2'], s=14, color=color, alpha=0.7,
                   linewidths=0, label=f'{label} (n={len(sub)})', zorder=3)

    ax.set_title(title, color=INK_PRIMARY, fontsize=11, fontweight='bold', loc='left', wrap=True)
    ax.set_xlabel('PCA 1', color=INK_SECONDARY, fontsize=9)
    ax.set_ylabel('PCA 2', color=INK_SECONDARY, fontsize=9)
    ax.grid(True, color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    _style_axes(ax)
    ax.legend(fontsize=8, frameon=False, labelcolor=INK_SECONDARY, loc='best')

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def run(dataset_name, scatter_for=None):
    cache_dir = OUT / dataset_name
    comparison = pd.read_csv(cache_dir / 'comparison_metrics.csv')
    plots_dir = cache_dir / 'plots'
    plots_dir.mkdir(parents=True, exist_ok=True)

    bar_path = plot_silhouette_comparison(comparison, dataset_name, plots_dir / 'silhouette_comparison.png')
    print(f'Wrote {bar_path}')

    grid_path = plot_combo_grid(dataset_name, comparison, cache_dir, plots_dir / 'all_combos_grid.png')
    print(f'Wrote {grid_path}')

    if scatter_for is None:
        best = comparison.dropna(subset=['silhouette']).sort_values('silhouette', ascending=False).iloc[0]
        combos = [f"{best['embedding_model']}__{best['clustering_method']}"]
    else:
        combos = scatter_for

    id_col = 'project_id' if dataset_name == 'projects' else 'publication_id'
    for combo in combos:
        labels_path = cache_dir / f'labels_{combo}.csv'
        if not labels_path.exists():
            print(f'  WARNING: no labels file for {combo}, skipping ({labels_path.name})')
            continue
        labels_df = pd.read_csv(labels_path)
        model_key, method = combo.split('__', 1)
        row = comparison[(comparison['embedding_model'] == model_key) & (comparison['clustering_method'] == method)].iloc[0]
        title = f'{row["embedding_label"]} + {method} · silhouette {row["silhouette"]}'
        scatter_path = plot_pca_scatter(labels_df, id_col, title, plots_dir / f'pca_scatter_{combo}.png')
        print(f'Wrote {scatter_path}')

        if dataset_name == 'projects':
            projects_path = ROOT / 'salidas' / '01_projects_closed.csv'
            projects_df = pd.read_csv(projects_path, dtype=str)
            has_line = pd.Series(False, index=projects_df.index)
            for col in RESEARCH_LINE_COLUMNS:
                if col in projects_df.columns:
                    has_line |= projects_df[col].fillna('').str.strip().ne('')
            projects_df = projects_df[['project_id', ]].copy()
            projects_df['project_id'] = projects_df['project_id'].astype(str)
            projects_df['has_research_line'] = has_line.values

            merged = labels_df.copy()
            merged['project_id'] = merged['project_id'].astype(str)
            merged = merged.merge(projects_df, on='project_id', how='left')

            rl_title = f'{row["embedding_label"]} + {method} · con vs. sin línea de investigación'
            rl_path = plot_research_line_coverage(
                merged, rl_title, plots_dir / f'research_line_coverage_{combo}.png'
            )
            print(f'Wrote {rl_path}')


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True, choices=['projects', 'publications'])
    parser.add_argument('--scatter-for', default=None,
                        help='Comma-separated model__method combos to plot (default: best by silhouette).')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    scatter_for = args.scatter_for.split(',') if args.scatter_for else None
    run(args.dataset, scatter_for=scatter_for)

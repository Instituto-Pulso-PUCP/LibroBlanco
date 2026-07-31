"""Clustering methods and evaluation metrics shared by the analysis scripts.

Every method in ``CLUSTERING_METHODS`` takes an embedding matrix and returns
the best labeling it found (searching over a small k grid for methods that
need one) plus the metrics used to pick it, so callers can compare methods
on equal footing via ``run_clustering``.
"""

from __future__ import annotations

import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from sklearn.cluster import KMeans, HDBSCAN
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score

K_GRID = (5, 8, 10, 12)

CLUSTERING_METHODS = ['kmeans', 'agglomerative', 'gaussian_mixture', 'hdbscan']


def evaluate_labels(embeddings, labels):
    """Cluster-quality metrics for a labeling. Noise points (-1, from HDBSCAN)
    are excluded from the quality scores but reported via noise_pct."""
    labels = np.asarray(labels)
    mask = labels != -1
    n_clusters = len(set(labels[mask].tolist()))
    noise_pct = round(100.0 * (~mask).sum() / len(labels), 2) if len(labels) else 0.0

    if n_clusters < 2 or mask.sum() < n_clusters + 1:
        return {
            'n_clusters': n_clusters,
            'noise_pct': noise_pct,
            'silhouette': None,
            'davies_bouldin': None,
            'calinski_harabasz': None,
        }

    X, y = embeddings[mask], labels[mask]
    return {
        'n_clusters': n_clusters,
        'noise_pct': noise_pct,
        'silhouette': round(float(silhouette_score(X, y)), 4),
        'davies_bouldin': round(float(davies_bouldin_score(X, y)), 4),
        'calinski_harabasz': round(float(calinski_harabasz_score(X, y)), 2),
    }


def _best_over_k(embeddings, label_fn, k_grid=K_GRID):
    """Try each k in k_grid, score with evaluate_labels, keep the best silhouette."""
    best = None
    for k in k_grid:
        labels = label_fn(k)
        metrics = evaluate_labels(embeddings, labels)
        if metrics['silhouette'] is None:
            continue
        if best is None or metrics['silhouette'] > best[1]['silhouette']:
            best = (labels, metrics, k)
    if best is None:
        # Every k collapsed to <2 clusters; fall back to the smallest k's raw labels.
        k = k_grid[0]
        labels = label_fn(k)
        return labels, evaluate_labels(embeddings, labels), {'k': k}
    labels, metrics, k = best
    return labels, metrics, {'k': k}


def run_kmeans(embeddings, k_grid=K_GRID, random_state=42):
    def label_fn(k):
        return KMeans(n_clusters=k, random_state=random_state, n_init='auto').fit_predict(embeddings)
    return _best_over_k(embeddings, label_fn, k_grid)


def run_agglomerative(embeddings, k_grid=K_GRID):
    # Compute the linkage tree once, then cut it at each k in the grid — far
    # cheaper than refitting AgglomerativeClustering per k (each fit is O(n^2)).
    Z = linkage(embeddings, method='ward')

    def label_fn(k):
        return fcluster(Z, t=k, criterion='maxclust') - 1

    return _best_over_k(embeddings, label_fn, k_grid)


def run_gaussian_mixture(embeddings, k_grid=K_GRID, random_state=42):
    def label_fn(k):
        # diag covariance keeps this tractable at embedding dimensionality
        # (full covariance is O(d^2) per component and blows up past ~100 dims).
        gmm = GaussianMixture(n_components=k, covariance_type='diag', random_state=random_state)
        return gmm.fit_predict(embeddings)
    return _best_over_k(embeddings, label_fn, k_grid)


def run_hdbscan(embeddings, min_cluster_size=None, max_dims=50):
    n = len(embeddings)
    min_cluster_size = min_cluster_size or max(5, n // 100)

    # Density-based clustering degrades badly in high dimensions (everything
    # looks equidistant). Fit on a PCA-reduced view, but evaluate quality
    # metrics on the original embeddings so scores stay comparable across methods.
    n_components = min(max_dims, n - 1, embeddings.shape[1])
    fit_space = PCA(n_components=n_components, random_state=42).fit_transform(embeddings) \
        if n_components < embeddings.shape[1] else embeddings

    labels = HDBSCAN(min_cluster_size=min_cluster_size).fit_predict(fit_space)
    metrics = evaluate_labels(embeddings, labels)
    return labels, metrics, {'min_cluster_size': min_cluster_size, 'pca_dims': n_components}


_RUNNERS = {
    'kmeans': run_kmeans,
    'agglomerative': run_agglomerative,
    'gaussian_mixture': run_gaussian_mixture,
    'hdbscan': run_hdbscan,
}


def run_clustering(embeddings, method):
    """Run a registered clustering method by name.

    Returns ``(labels, metrics, params)`` where metrics is the dict from
    evaluate_labels and params records what was chosen (e.g. k).
    """
    if method not in _RUNNERS:
        raise ValueError(f'Unknown clustering method: {method}')
    return _RUNNERS[method](embeddings)

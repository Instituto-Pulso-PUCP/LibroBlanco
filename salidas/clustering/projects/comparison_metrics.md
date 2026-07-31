# Clustering comparison — projects (938 rows)

| Embedding | Method | n_clusters | silhouette | davies_bouldin | calinski_harabasz | noise % | seconds |
|---|---|---|---|---|---|---|---|
| paraphrase-multilingual-mpnet-base-v2 | hdbscan | 2 | 0.2758 | 1.1172 | 24.71 | 85.82 | 0.0 |
| jina-embeddings-v5-text-nano | hdbscan | 2 | 0.1988 | 1.2889 | 17.1 | 43.18 | 0.1 |
| multilingual-e5-base | hdbscan | 2 | 0.1204 | 2.1911 | 23.37 | 40.41 | 0.1 |
| bge-m3 | hdbscan | 2 | 0.1076 | 2.2378 | 39.67 | 33.05 | 0.1 |
| jina-embeddings-v5-text-nano | kmeans | 5 | 0.1046 | 2.6644 | 86.1 | 0.0 | 0.2 |
| jina-embeddings-v5-text-nano | gaussian_mixture | 5 | 0.0957 | 2.7444 | 84.73 | 0.0 | 1.3 |
| jina-embeddings-v5-text-nano | agglomerative | 5 | 0.0905 | 2.7953 | 74.33 | 0.0 | 0.1 |
| paraphrase-multilingual-mpnet-base-v2 | kmeans | 10 | 0.0636 | 2.8019 | 42.3 | 0.0 | 0.2 |
| paraphrase-multilingual-mpnet-base-v2 | gaussian_mixture | 12 | 0.0561 | 2.844 | 37.64 | 0.0 | 1.8 |
| paraphrase-multilingual-mpnet-base-v2 | agglomerative | 8 | 0.0518 | 3.0278 | 41.61 | 0.0 | 0.1 |
| bge-m3 | kmeans | 5 | 0.0436 | 4.0717 | 31.49 | 0.0 | 0.2 |
| bge-m3 | gaussian_mixture | 5 | 0.0436 | 4.0717 | 31.49 | 0.0 | 0.4 |
| multilingual-e5-base | kmeans | 5 | 0.0343 | 3.8936 | 29.85 | 0.0 | 0.2 |
| multilingual-e5-base | gaussian_mixture | 5 | 0.0316 | 3.9151 | 29.72 | 0.0 | 0.5 |
| bge-m3 | agglomerative | 5 | 0.0275 | 4.8375 | 26.61 | 0.0 | 0.2 |
| multilingual-e5-base | agglomerative | 5 | 0.0259 | 4.3161 | 25.07 | 0.0 | 0.2 |
| TF-IDF (baseline) | kmeans | 12 | 0.0162 | 6.2248 | 6.35 | 0.0 | 3.2 |
| TF-IDF (baseline) | gaussian_mixture | 12 | 0.0143 | 6.5448 | 6.02 | 0.0 | 0.6 |
| TF-IDF (baseline) | agglomerative | 5 | 0.0072 | 7.828 | 7.77 | 0.0 | 0.3 |
| TF-IDF (baseline) | hdbscan | 3 | 0.0034 | 3.1812 | 4.99 | 67.38 | 0.1 |
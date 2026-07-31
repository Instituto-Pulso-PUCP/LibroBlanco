# Clustering comparison — publications (13995 rows)

| Embedding | Method | n_clusters | silhouette | davies_bouldin | calinski_harabasz | noise % | seconds |
|---|---|---|---|---|---|---|---|
| jina-embeddings-v5-text-nano | hdbscan | 4 | 0.2603 | 1.4884 | 705.2 | 68.75 | 7.1 |
| paraphrase-multilingual-mpnet-base-v2 | hdbscan | 2 | 0.2329 | 1.6302 | 1073.29 | 67.7 | 8.1 |
| multilingual-e5-base | hdbscan | 2 | 0.1496 | 2.2118 | 118.38 | 77.32 | 7.0 |
| jina-embeddings-v5-text-nano | kmeans | 10 | 0.1138 | 2.5654 | 756.74 | 0.0 | 9.7 |
| jina-embeddings-v5-text-nano | gaussian_mixture | 10 | 0.107 | 2.585 | 740.99 | 0.0 | 14.8 |
| jina-embeddings-v5-text-nano | agglomerative | 5 | 0.0911 | 2.73 | 916.87 | 0.0 | 32.9 |
| paraphrase-multilingual-mpnet-base-v2 | kmeans | 5 | 0.0585 | 3.2227 | 714.54 | 0.0 | 9.8 |
| paraphrase-multilingual-mpnet-base-v2 | gaussian_mixture | 5 | 0.0483 | 3.1793 | 700.37 | 0.0 | 14.6 |
| paraphrase-multilingual-mpnet-base-v2 | agglomerative | 8 | 0.042 | 4.0601 | 416.77 | 0.0 | 33.7 |
| multilingual-e5-base | kmeans | 5 | 0.0392 | 4.1278 | 509.69 | 0.0 | 9.7 |
| multilingual-e5-base | gaussian_mixture | 5 | 0.0328 | 3.9902 | 499.25 | 0.0 | 18.5 |
| multilingual-e5-base | agglomerative | 5 | 0.0304 | 3.9762 | 426.97 | 0.0 | 33.4 |
| TF-IDF (baseline) | kmeans | 5 | 0.0274 | 5.3837 | 237.18 | 0.0 | 16.5 |
| bge-m3 | kmeans | 5 | 0.0232 | 4.9664 | 384.42 | 0.0 | 12.3 |
| TF-IDF (baseline) | agglomerative | 5 | 0.0217 | 3.8481 | 217.55 | 0.0 | 72.9 |
| bge-m3 | gaussian_mixture | 5 | 0.0203 | 4.9272 | 380.42 | 0.0 | 19.3 |
| TF-IDF (baseline) | hdbscan | 2 | 0.0172 | 2.5604 | 96.91 | 67.85 | 7.5 |
| bge-m3 | agglomerative | 8 | 0.0152 | 5.7507 | 216.63 | 0.0 | 42.5 |
| TF-IDF (baseline) | gaussian_mixture | 5 | 0.0139 | 8.2589 | 196.43 | 0.0 | 21.1 |
| bge-m3 | hdbscan | 0 | nan | nan | nan | 100.0 | 7.2 |
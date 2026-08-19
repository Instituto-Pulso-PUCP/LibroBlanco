# Clustering comparison — publications_linked (850 rows)

| Embedding | Method | n_clusters | silhouette | davies_bouldin | calinski_harabasz | noise % | seconds |
|---|---|---|---|---|---|---|---|
| jina-embeddings-v5-text-nano | hdbscan | 15 | 0.3634 | 1.1584 | 58.74 | 66.35 | 0.0 |
| paraphrase-multilingual-MiniLM-L12-v2 | hdbscan | 4 | 0.2047 | 1.8796 | 31.64 | 41.18 | 0.0 |
| nomic-embed-text-v2-moe | hdbscan | 4 | 0.1321 | 1.9504 | 14.17 | 60.94 | 0.0 |
| jina-embeddings-v5-text-nano | kmeans | 10 | 0.1299 | 2.3225 | 56.33 | 0.0 | 0.2 |
| jina-embeddings-v5-text-nano | gaussian_mixture | 8 | 0.1294 | 2.3444 | 62.41 | 0.0 | 0.5 |
| jina-embeddings-v5-text-nano | agglomerative | 8 | 0.1192 | 2.4497 | 57.64 | 0.0 | 0.1 |
| TF-IDF (baseline) | hdbscan | 3 | 0.094 | 2.379 | 19.12 | 67.76 | 0.1 |
| snowflake-arctic-embed-l-v2.0 | hdbscan | 8 | 0.083 | 2.2097 | 9.51 | 70.12 | 0.0 |
| multilingual-e5-small | hdbscan | 3 | 0.0828 | 2.2096 | 13.89 | 82.0 | 0.0 |
| bge-m3 | hdbscan | 5 | 0.0536 | 3.0736 | 8.56 | 77.41 | 0.1 |
| paraphrase-multilingual-MiniLM-L12-v2 | kmeans | 5 | 0.0498 | 3.4253 | 47.76 | 0.0 | 0.1 |
| paraphrase-multilingual-MiniLM-L12-v2 | agglomerative | 12 | 0.0381 | 3.3328 | 25.78 | 0.0 | 0.1 |
| nomic-embed-text-v2-moe | agglomerative | 8 | 0.0376 | 3.9676 | 19.56 | 0.0 | 0.1 |
| nomic-embed-text-v2-moe | kmeans | 10 | 0.0367 | 3.741 | 17.87 | 0.0 | 0.2 |
| paraphrase-multilingual-MiniLM-L12-v2 | gaussian_mixture | 5 | 0.0338 | 3.4857 | 47.11 | 0.0 | 0.3 |
| snowflake-arctic-embed-l-v2.0 | kmeans | 12 | 0.0336 | 4.2528 | 12.84 | 0.0 | 0.2 |
| snowflake-arctic-embed-l-v2.0 | gaussian_mixture | 12 | 0.0335 | 4.2506 | 12.84 | 0.0 | 0.5 |
| nomic-embed-text-v2-moe | gaussian_mixture | 8 | 0.0323 | 4.0139 | 20.65 | 0.0 | 0.5 |
| multilingual-e5-small | kmeans | 8 | 0.0312 | 4.3579 | 20.58 | 0.0 | 0.1 |
| multilingual-e5-small | gaussian_mixture | 8 | 0.0307 | 4.3679 | 20.6 | 0.0 | 0.2 |
| snowflake-arctic-embed-l-v2.0 | agglomerative | 8 | 0.029 | 4.3803 | 14.69 | 0.0 | 0.2 |
| multilingual-e5-small | agglomerative | 5 | 0.0289 | 4.6869 | 25.14 | 0.0 | 0.1 |
| TF-IDF (baseline) | kmeans | 5 | 0.0253 | 5.7311 | 26.04 | 0.0 | 3.4 |
| bge-m3 | kmeans | 5 | 0.0233 | 5.1948 | 19.64 | 0.0 | 0.2 |
| bge-m3 | gaussian_mixture | 5 | 0.0232 | 5.1919 | 19.64 | 0.0 | 0.5 |
| TF-IDF (baseline) | gaussian_mixture | 5 | 0.0222 | 6.4444 | 25.17 | 0.0 | 0.6 |
| bge-m3 | agglomerative | 5 | 0.0215 | 5.4518 | 17.84 | 0.0 | 0.2 |
| TF-IDF (baseline) | agglomerative | 10 | 0.0111 | 4.663 | 13.43 | 0.0 | 0.3 |
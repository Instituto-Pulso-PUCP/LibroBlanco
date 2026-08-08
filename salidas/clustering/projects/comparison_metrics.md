# Clustering comparison — projects (938 rows)

| Embedding | Method | n_clusters | silhouette | davies_bouldin | calinski_harabasz | noise % | seconds |
|---|---|---|---|---|---|---|---|
| jina-embeddings-v5-text-nano | hdbscan | 9 | 0.259 | 1.3308 | 51.15 | 57.89 | 0.2 |
| jina-embeddings-v5-text-nano | kmeans | 12 | 0.1495 | 2.0591 | 67.84 | 0.0 | 0.3 |
| jina-embeddings-v5-text-nano | gaussian_mixture | 12 | 0.1482 | 2.0674 | 67.58 | 0.0 | 0.6 |
| jina-embeddings-v5-text-nano | agglomerative | 12 | 0.1399 | 2.0899 | 63.81 | 0.0 | 0.2 |
| paraphrase-multilingual-MiniLM-L12-v2 | hdbscan | 7 | 0.1184 | 1.5339 | 24.39 | 68.02 | 0.1 |
| bge-m3 | hdbscan | 5 | 0.1039 | 2.486 | 12.49 | 80.49 | 0.1 |
| paraphrase-multilingual-MiniLM-L12-v2 | kmeans | 12 | 0.0982 | 2.7095 | 47.41 | 0.0 | 0.2 |
| paraphrase-multilingual-MiniLM-L12-v2 | gaussian_mixture | 12 | 0.0963 | 2.7217 | 47.2 | 0.0 | 0.4 |
| paraphrase-multilingual-MiniLM-L12-v2 | agglomerative | 12 | 0.0938 | 2.5384 | 44.65 | 0.0 | 0.1 |
| snowflake-arctic-embed-l-v2.0 | hdbscan | 6 | 0.0694 | 2.5971 | 11.69 | 68.87 | 0.1 |
| nomic-embed-text-v2-moe | hdbscan | 2 | 0.056 | 2.4496 | 14.61 | 44.99 | 0.1 |
| multilingual-e5-small | hdbscan | 2 | 0.054 | 2.4455 | 7.9 | 63.43 | 0.1 |
| TF-IDF (baseline) | hdbscan | 8 | 0.053 | 3.1361 | 7.8 | 49.57 | 0.2 |
| nomic-embed-text-v2-moe | kmeans | 12 | 0.0459 | 3.6867 | 21.04 | 0.0 | 0.2 |
| nomic-embed-text-v2-moe | gaussian_mixture | 12 | 0.0459 | 3.6862 | 21.05 | 0.0 | 0.6 |
| TF-IDF (baseline) | kmeans | 12 | 0.0433 | 4.3339 | 10.46 | 0.0 | 3.8 |
| TF-IDF (baseline) | gaussian_mixture | 12 | 0.0408 | 4.45 | 10.13 | 0.0 | 0.8 |
| TF-IDF (baseline) | agglomerative | 12 | 0.0398 | 4.2657 | 10.3 | 0.0 | 0.4 |
| nomic-embed-text-v2-moe | agglomerative | 12 | 0.0389 | 3.8286 | 19.84 | 0.0 | 0.2 |
| bge-m3 | agglomerative | 12 | 0.0382 | 3.6984 | 17.3 | 0.0 | 0.2 |
| snowflake-arctic-embed-l-v2.0 | kmeans | 12 | 0.0381 | 4.2474 | 15.28 | 0.0 | 0.3 |
| snowflake-arctic-embed-l-v2.0 | gaussian_mixture | 12 | 0.0381 | 4.2442 | 15.28 | 0.0 | 0.7 |
| bge-m3 | gaussian_mixture | 12 | 0.0369 | 4.1392 | 17.2 | 0.0 | 0.9 |
| bge-m3 | kmeans | 12 | 0.0369 | 4.1392 | 17.2 | 0.0 | 0.3 |
| snowflake-arctic-embed-l-v2.0 | agglomerative | 12 | 0.0347 | 4.0762 | 14.65 | 0.0 | 0.2 |
| multilingual-e5-small | kmeans | 8 | 0.0324 | 4.3777 | 19.96 | 0.0 | 0.2 |
| multilingual-e5-small | gaussian_mixture | 8 | 0.0323 | 4.3806 | 19.97 | 0.0 | 0.6 |
| multilingual-e5-small | agglomerative | 12 | 0.0308 | 4.5525 | 14.5 | 0.0 | 0.1 |
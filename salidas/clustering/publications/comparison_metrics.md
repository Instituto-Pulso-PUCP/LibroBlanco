# Clustering comparison — publications (13995 rows)

| Embedding | Method | n_clusters | silhouette | davies_bouldin | calinski_harabasz | noise % | seconds |
|---|---|---|---|---|---|---|---|
| paraphrase-multilingual-MiniLM-L12-v2 | hdbscan | 2 | 0.2871 | 1.2901 | 1074.21 | 72.43 | 7.1 |
| jina-embeddings-v5-text-nano | hdbscan | 4 | 0.2522 | 1.332 | 712.92 | 67.78 | 6.1 |
| nomic-embed-text-v2-moe | hdbscan | 2 | 0.2333 | 1.6454 | 537.52 | 88.61 | 7.0 |
| jina-embeddings-v5-text-nano | kmeans | 12 | 0.1188 | 2.4627 | 703.52 | 0.0 | 8.7 |
| jina-embeddings-v5-text-nano | gaussian_mixture | 12 | 0.1126 | 2.4621 | 689.48 | 0.0 | 11.9 |
| jina-embeddings-v5-text-nano | agglomerative | 5 | 0.0957 | 2.7283 | 953.27 | 0.0 | 30.1 |
| TF-IDF (baseline) | hdbscan | 2 | 0.0595 | 3.4818 | 93.64 | 91.01 | 6.2 |
| paraphrase-multilingual-MiniLM-L12-v2 | kmeans | 10 | 0.0402 | 3.7599 | 395.13 | 0.0 | 7.5 |
| nomic-embed-text-v2-moe | kmeans | 5 | 0.0376 | 4.1883 | 436.29 | 0.0 | 9.3 |
| TF-IDF (baseline) | kmeans | 5 | 0.0337 | 5.9664 | 331.38 | 0.0 | 14.7 |
| nomic-embed-text-v2-moe | gaussian_mixture | 5 | 0.0319 | 4.2468 | 431.45 | 0.0 | 11.4 |
| nomic-embed-text-v2-moe | agglomerative | 5 | 0.0295 | 4.5316 | 362.75 | 0.0 | 31.8 |
| bge-m3 | kmeans | 5 | 0.0294 | 4.7455 | 349.89 | 0.0 | 10.5 |
| TF-IDF (baseline) | gaussian_mixture | 5 | 0.0292 | 7.7434 | 282.99 | 0.0 | 25.5 |
| multilingual-e5-small | kmeans | 5 | 0.0291 | 4.8095 | 420.83 | 0.0 | 7.4 |
| multilingual-e5-small | gaussian_mixture | 5 | 0.0291 | 4.756 | 415.66 | 0.0 | 8.4 |
| bge-m3 | gaussian_mixture | 5 | 0.0282 | 4.7278 | 348.96 | 0.0 | 14.8 |
| snowflake-arctic-embed-l-v2.0 | kmeans | 5 | 0.0275 | 4.6935 | 345.38 | 0.0 | 10.9 |
| snowflake-arctic-embed-l-v2.0 | gaussian_mixture | 5 | 0.0264 | 4.665 | 343.97 | 0.0 | 12.0 |
| paraphrase-multilingual-MiniLM-L12-v2 | gaussian_mixture | 5 | 0.0262 | 3.6084 | 616.7 | 0.0 | 9.2 |
| multilingual-e5-small | agglomerative | 5 | 0.0251 | 4.9606 | 357.48 | 0.0 | 17.7 |
| paraphrase-multilingual-MiniLM-L12-v2 | agglomerative | 5 | 0.0224 | 4.4015 | 464.64 | 0.0 | 19.1 |
| snowflake-arctic-embed-l-v2.0 | agglomerative | 5 | 0.0186 | 5.5619 | 278.27 | 0.0 | 38.9 |
| bge-m3 | agglomerative | 5 | 0.0153 | 5.5959 | 277.5 | 0.0 | 39.2 |
| TF-IDF (baseline) | agglomerative | 12 | 0.0017 | 6.0877 | 122.46 | 0.0 | 64.3 |
| bge-m3 | hdbscan | 0 | nan | nan | nan | 100.0 | 7.1 |
| snowflake-arctic-embed-l-v2.0 | hdbscan | 0 | nan | nan | nan | 100.0 | 7.0 |
| multilingual-e5-small | hdbscan | 0 | nan | nan | nan | 100.0 | 6.8 |
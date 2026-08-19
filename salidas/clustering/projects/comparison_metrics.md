# Clustering comparison — projects (975 rows)

| Embedding | Method | n_clusters | silhouette | davies_bouldin | calinski_harabasz | noise % | seconds |
|---|---|---|---|---|---|---|---|
| jina-embeddings-v5-text-nano | hdbscan | 9 | 0.27 | 1.2587 | 53.86 | 60.1 | 0.1 |
| jina-embeddings-v5-text-nano | agglomerative | 12 | 0.1389 | 2.1234 | 63.93 | 0.0 | 0.2 |
| jina-embeddings-v5-text-nano | kmeans | 12 | 0.1382 | 2.1538 | 65.44 | 0.0 | 0.2 |
| jina-embeddings-v5-text-nano | gaussian_mixture | 12 | 0.1349 | 2.1779 | 65.14 | 0.0 | 0.4 |
| paraphrase-multilingual-MiniLM-L12-v2 | hdbscan | 7 | 0.1202 | 1.5256 | 24.2 | 69.95 | 0.0 |
| paraphrase-multilingual-MiniLM-L12-v2 | kmeans | 10 | 0.1023 | 2.5993 | 52.76 | 0.0 | 0.1 |
| paraphrase-multilingual-MiniLM-L12-v2 | gaussian_mixture | 10 | 0.0989 | 2.6208 | 52.44 | 0.0 | 0.4 |
| bge-m3 | hdbscan | 5 | 0.0925 | 2.56 | 12.64 | 78.36 | 0.1 |
| multilingual-e5-small | hdbscan | 4 | 0.0906 | 2.6879 | 10.42 | 84.51 | 0.0 |
| paraphrase-multilingual-MiniLM-L12-v2 | agglomerative | 12 | 0.0864 | 2.6025 | 43.65 | 0.0 | 0.1 |
| snowflake-arctic-embed-l-v2.0 | hdbscan | 6 | 0.0741 | 2.619 | 12.4 | 69.54 | 0.0 |
| nomic-embed-text-v2-moe | hdbscan | 2 | 0.052 | 2.473 | 14.81 | 43.79 | 0.0 |
| nomic-embed-text-v2-moe | kmeans | 8 | 0.0477 | 3.8012 | 28.04 | 0.0 | 0.2 |
| nomic-embed-text-v2-moe | gaussian_mixture | 8 | 0.0471 | 3.798 | 28.04 | 0.0 | 0.6 |
| nomic-embed-text-v2-moe | agglomerative | 12 | 0.0411 | 3.9954 | 20.09 | 0.0 | 0.1 |
| TF-IDF (baseline) | kmeans | 12 | 0.0397 | 4.6895 | 10.44 | 0.0 | 3.4 |
| snowflake-arctic-embed-l-v2.0 | kmeans | 8 | 0.0393 | 4.2614 | 20.61 | 0.0 | 0.2 |
| snowflake-arctic-embed-l-v2.0 | gaussian_mixture | 8 | 0.0392 | 4.2631 | 20.61 | 0.0 | 0.6 |
| TF-IDF (baseline) | gaussian_mixture | 12 | 0.0378 | 4.795 | 10.23 | 0.0 | 0.5 |
| TF-IDF (baseline) | agglomerative | 12 | 0.0375 | 4.3438 | 10.27 | 0.0 | 0.3 |
| bge-m3 | kmeans | 12 | 0.0363 | 3.8058 | 18.57 | 0.0 | 0.2 |
| bge-m3 | gaussian_mixture | 12 | 0.0357 | 3.8021 | 18.56 | 0.0 | 0.6 |
| bge-m3 | agglomerative | 12 | 0.0332 | 3.7666 | 17.14 | 0.0 | 0.2 |
| multilingual-e5-small | kmeans | 8 | 0.0311 | 4.6504 | 20.28 | 0.0 | 0.1 |
| multilingual-e5-small | gaussian_mixture | 8 | 0.0303 | 4.6625 | 20.24 | 0.0 | 0.4 |
| snowflake-arctic-embed-l-v2.0 | agglomerative | 12 | 0.0302 | 4.1746 | 14.39 | 0.0 | 0.2 |
| multilingual-e5-small | agglomerative | 12 | 0.0292 | 4.4033 | 14.19 | 0.0 | 0.1 |
| TF-IDF (baseline) | hdbscan | 4 | 0.0195 | 2.9981 | 7.04 | 31.59 | 0.1 |
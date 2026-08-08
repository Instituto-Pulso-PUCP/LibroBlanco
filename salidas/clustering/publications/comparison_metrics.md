# Clustering comparison — publications (13995 rows)

| Embedding | Method | n_clusters | silhouette | davies_bouldin | calinski_harabasz | noise % | seconds |
|---|---|---|---|---|---|---|---|
| paraphrase-multilingual-MiniLM-L12-v2 | hdbscan | 2 | 0.3033 | 1.288 | 1336.56 | 70.57 | 6.9 |
| jina-embeddings-v5-text-nano | hdbscan | 5 | 0.2629 | 1.2433 | 603.09 | 65.71 | 6.5 |
| jina-embeddings-v5-text-nano | kmeans | 12 | 0.1201 | 2.474 | 712.2 | 0.0 | 10.0 |
| jina-embeddings-v5-text-nano | gaussian_mixture | 12 | 0.1136 | 2.3892 | 700.38 | 0.0 | 13.6 |
| jina-embeddings-v5-text-nano | agglomerative | 10 | 0.092 | 2.6657 | 669.12 | 0.0 | 33.6 |
| paraphrase-multilingual-MiniLM-L12-v2 | kmeans | 5 | 0.0579 | 3.4413 | 730.46 | 0.0 | 7.4 |
| nomic-embed-text-v2-moe | kmeans | 5 | 0.0366 | 4.1441 | 454.14 | 0.0 | 9.0 |
| nomic-embed-text-v2-moe | gaussian_mixture | 5 | 0.0351 | 4.1459 | 452.2 | 0.0 | 11.4 |
| paraphrase-multilingual-MiniLM-L12-v2 | gaussian_mixture | 5 | 0.0342 | 3.3954 | 701.58 | 0.0 | 10.0 |
| paraphrase-multilingual-MiniLM-L12-v2 | agglomerative | 5 | 0.0333 | 4.2186 | 568.38 | 0.0 | 19.0 |
| snowflake-arctic-embed-l-v2.0 | kmeans | 5 | 0.029 | 4.8294 | 341.22 | 0.0 | 10.8 |
| multilingual-e5-small | kmeans | 5 | 0.0287 | 4.9963 | 427.35 | 0.0 | 7.5 |
| snowflake-arctic-embed-l-v2.0 | gaussian_mixture | 5 | 0.0275 | 4.8227 | 339.39 | 0.0 | 13.0 |
| nomic-embed-text-v2-moe | agglomerative | 5 | 0.0272 | 4.6048 | 379.38 | 0.0 | 30.2 |
| TF-IDF (baseline) | agglomerative | 5 | 0.0251 | 4.0316 | 218.0 | 0.0 | 75.8 |
| multilingual-e5-small | gaussian_mixture | 5 | 0.025 | 4.8978 | 423.25 | 0.0 | 8.4 |
| bge-m3 | kmeans | 5 | 0.0224 | 4.5348 | 388.14 | 0.0 | 11.7 |
| snowflake-arctic-embed-l-v2.0 | agglomerative | 5 | 0.0213 | 5.6374 | 280.34 | 0.0 | 36.4 |
| TF-IDF (baseline) | kmeans | 12 | 0.0213 | 6.1944 | 125.73 | 0.0 | 18.5 |
| multilingual-e5-small | agglomerative | 5 | 0.0199 | 4.9515 | 375.9 | 0.0 | 18.0 |
| bge-m3 | gaussian_mixture | 8 | 0.0174 | 4.9331 | 276.13 | 0.0 | 16.2 |
| bge-m3 | agglomerative | 5 | 0.0142 | 5.4261 | 309.53 | 0.0 | 43.6 |
| TF-IDF (baseline) | gaussian_mixture | 5 | 0.0124 | 8.5754 | 195.42 | 0.0 | 22.0 |
| TF-IDF (baseline) | hdbscan | 0 | nan | nan | nan | 100.0 | 6.9 |
| bge-m3 | hdbscan | 0 | nan | nan | nan | 100.0 | 7.2 |
| snowflake-arctic-embed-l-v2.0 | hdbscan | 0 | nan | nan | nan | 100.0 | 6.9 |
| multilingual-e5-small | hdbscan | 0 | nan | nan | nan | 100.0 | 6.6 |
| nomic-embed-text-v2-moe | hdbscan | 0 | nan | nan | nan | 100.0 | 6.9 |
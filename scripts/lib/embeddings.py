"""Text embedding backends shared by the clustering analysis scripts.

Provides a small registry of embedding methods (a TF-IDF baseline plus a
handful of local, open-weight sentence-transformers models) behind one
``compute_embeddings`` entry point, so analysis scripts can loop over
multiple embedding backends without duplicating model-loading code.
"""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer

# key -> (method, model_name, kwargs for SentenceTransformer.encode / model init)
EMBEDDING_MODELS = {
    'tfidf': {
        'method': 'tfidf',
        'label': 'TF-IDF (baseline)',
    },
    'jina-v5-nano': {
        'method': 'sentence-transformers',
        'model_name': 'jinaai/jina-embeddings-v5-text-nano',
        'label': 'jina-embeddings-v5-text-nano',
        'model_kwargs': {'trust_remote_code': True, 'model_kwargs': {'dtype': None}},
        'encode_kwargs': {'task': 'clustering'},
    },
    'bge-m3': {
        'method': 'sentence-transformers',
        'model_name': 'BAAI/bge-m3',
        'label': 'bge-m3',
    },
    'snowflake-arctic-l-v2': {
        'method': 'sentence-transformers',
        'model_name': 'Snowflake/snowflake-arctic-embed-l-v2.0',
        'label': 'snowflake-arctic-embed-l-v2.0',
    },
    'minilm-multilingual': {
        'method': 'sentence-transformers',
        'model_name': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
        'label': 'paraphrase-multilingual-MiniLM-L12-v2',
    },
    'e5-small-multilingual': {
        'method': 'sentence-transformers',
        'model_name': 'intfloat/multilingual-e5-small',
        'label': 'multilingual-e5-small',
        # e5's FAQ: use "query: " (not "passage: ") when embeddings are used
        # as features for clustering/classification rather than retrieval.
        'text_prefix': 'query: ',
    },
    'nomic-v2-moe': {
        'method': 'sentence-transformers',
        'model_name': 'nomic-ai/nomic-embed-text-v2-moe',
        'label': 'nomic-embed-text-v2-moe',
        'model_kwargs': {'trust_remote_code': True},
        'encode_kwargs': {'prompt_name': 'passage'},
    },
}


def embed_with_tfidf(texts, max_features=2000):
    vectorizer = TfidfVectorizer(max_features=max_features, stop_words=None)
    X = vectorizer.fit_transform(texts)
    return X.toarray(), vectorizer


def embed_with_sentence_transformers(texts, model_name, model_kwargs=None,
                                      encode_kwargs=None, text_prefix=''):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ImportError(
            "sentence-transformers is not installed. "
            "Install it with: pip install sentence-transformers"
        ) from exc

    model_kwargs = dict(model_kwargs or {})
    model_kwargs.setdefault('device', 'cpu')
    model = SentenceTransformer(model_name, **model_kwargs)

    prefixed = [f'{text_prefix}{t}' for t in texts] if text_prefix else list(texts)
    encode_kwargs = dict(encode_kwargs or {})
    # Unit-normalize so downstream clustering (euclidean-based) behaves like cosine
    # similarity, matching TfidfVectorizer's default L2 normalization.
    encode_kwargs.setdefault('normalize_embeddings', True)
    embeddings = model.encode(
        prefixed,
        show_progress_bar=True,
        convert_to_numpy=True,
        **encode_kwargs,
    )
    return embeddings, model


def compute_embeddings(texts, model_key):
    """Compute embeddings for ``texts`` using the model registered under ``model_key``.

    Returns ``(embeddings, metadata)`` where ``metadata`` records what was used
    (method, model name, dimensionality) for provenance in saved outputs.
    """
    if model_key not in EMBEDDING_MODELS:
        raise ValueError(f'Unknown embedding model key: {model_key}')
    config = EMBEDDING_MODELS[model_key]

    if config['method'] == 'tfidf':
        embeddings, _ = embed_with_tfidf(texts)
        metadata = {'model_key': model_key, 'method': 'tfidf', 'label': config['label']}
    elif config['method'] == 'sentence-transformers':
        embeddings, _ = embed_with_sentence_transformers(
            texts,
            model_name=config['model_name'],
            model_kwargs=config.get('model_kwargs'),
            encode_kwargs=config.get('encode_kwargs'),
            text_prefix=config.get('text_prefix', ''),
        )
        metadata = {
            'model_key': model_key,
            'method': 'sentence-transformers',
            'model_name': config['model_name'],
            'label': config['label'],
        }
    else:
        raise ValueError(f"Unknown embedding method: {config['method']}")

    metadata['n_samples'] = int(len(texts))
    metadata['n_dimensions'] = int(embeddings.shape[1])
    return embeddings, metadata

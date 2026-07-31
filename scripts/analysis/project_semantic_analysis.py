import argparse
from pathlib import Path
import json
import pandas as pd

try:
    from sklearn.decomposition import PCA
    from sklearn.cluster import KMeans
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError as exc:
    raise ImportError(
        "scikit-learn is required for project_semantic_analysis.py. "
        "Install it with: pip install scikit-learn"
    ) from exc

MODEL_FALLBACK = "tfidf"

PROJECT_SHEET = "PROYECTOS"
TEXT_COLUMNS = [
    'Título',
    'Tipo de Proyecto',
    'LÍNEA EN CENTURIA',
    'Linea de Investigación 1',
    'Linea de Investigación 2',
    'Linea de Investigación 3',
    'Linea de Investigación 4',
    'LÍNEA DE INVESTIGACIÓN HOMOLOGADA',
    'Tipo de Convocatoria',
    'Entidad Financiadora',
]


def clean_text(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def build_project_text(row, extra_fields=None):
    fields = TEXT_COLUMNS.copy()
    if extra_fields:
        fields.extend(extra_fields)
    parts = [clean_text(row.get(col)) for col in fields]
    return " ".join([part for part in parts if part])


def load_projects(workbook_path: Path, text_columns=None):
    text_columns = text_columns or TEXT_COLUMNS
    df = pd.read_excel(workbook_path, sheet_name=PROJECT_SHEET, dtype=str)
    df = df.fillna("")
    df['project_text'] = df.apply(lambda row: build_project_text(row, extra_fields=[]), axis=1)
    return df


def embed_with_tfidf(texts, max_features=2000):
    vectorizer = TfidfVectorizer(max_features=max_features, stop_words=None)
    X = vectorizer.fit_transform(texts)
    return X.toarray(), vectorizer


def embed_with_sentence_transformers(texts, model_name='jinaai/jina-embeddings-v5-text-nano', task='clustering'):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ImportError(
            "sentence-transformers is not installed. "
            "Install it with: pip install sentence-transformers"
        ) from exc

    model = SentenceTransformer(
        model_name,
        trust_remote_code=True,
        device='cpu',
        model_kwargs={"dtype": None},
    )
    embeddings = model.encode(
        texts,
        show_progress_bar=True,
        convert_to_numpy=True,
        task=task,
    )
    return embeddings, model


def compute_embeddings(texts, method='tfidf', model_name=None, sentence_task='retrieval'):
    if method == 'sentence-transformers':
        model_name = model_name or 'jinaai/jina-embeddings-v5-text-nano'
        embeddings, model = embed_with_sentence_transformers(
            texts,
            model_name=model_name,
            task=sentence_task,
        )
        return embeddings, {'method': method, 'model_name': model_name, 'task': sentence_task}
    if method == 'tfidf':
        embeddings, vectorizer = embed_with_tfidf(texts)
        return embeddings, {'method': method, 'vectorizer': 'tfidf', 'max_features': 2000}
    raise ValueError(f"Unknown embedding method: {method}")


def apply_pca(embeddings, n_components=3):
    pca = PCA(n_components=n_components)
    coords = pca.fit_transform(embeddings)
    explained_variance = pca.explained_variance_ratio_
    return coords, explained_variance, pca


def apply_kmeans(embeddings, n_clusters=8, random_state=42):
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init='auto')
    labels = kmeans.fit_predict(embeddings)
    return labels, kmeans


def save_analysis_results(df, pca_coords, labels, output_csv: Path, prefix='pca'):
    df_out = df.copy()
    for dim in range(pca_coords.shape[1]):
        df_out[f'{prefix}_{dim+1}'] = pca_coords[:, dim]
    df_out['cluster_label'] = labels
    df_out.to_csv(output_csv, index=False, encoding='utf-8-sig')
    return df_out


def run_analysis(
    workbook_path: Path,
    output_csv: Path,
    embedding_method: str = 'tfidf',
    embedding_model: str = None,
    sentence_task: str = 'retrieval',
    n_components: int = 3,
    n_clusters: int = 8,
):
    df = load_projects(workbook_path)
    if df['project_text'].str.strip().eq('').all():
        raise ValueError('No descriptive project text found. Please add summary/keywords/explanation fields to TEXT_COLUMNS.')

    print(f'Loaded {len(df)} projects. Computing embeddings with method={embedding_method}...')
    embeddings, embed_metadata = compute_embeddings(
        df['project_text'].tolist(),
        method=embedding_method,
        model_name=embedding_model,
        sentence_task=sentence_task,
    )
    print('Embeddings shape:', embeddings.shape)

    print(f'Running PCA with n_components={n_components}...')
    pca_coords, explained_variance, pca = apply_pca(embeddings, n_components=n_components)
    print('Explained variance ratio:', explained_variance)

    print(f'Running KMeans with n_clusters={n_clusters}...')
    labels, kmeans = apply_kmeans(embeddings, n_clusters=n_clusters)
    print('Cluster centers shape:', kmeans.cluster_centers_.shape)

    output = save_analysis_results(df, pca_coords, labels, output_csv)
    print(f'Wrote analysis results to {output_csv}')

    metadata = {
        'embedding_method': embed_metadata,
        'pca_explained_variance_ratio': explained_variance.tolist(),
        'n_clusters': n_clusters,
        'project_count': len(df),
    }
    metadata_path = output_csv.with_suffix('.metadata.json')
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f'Wrote metadata to {metadata_path}')

    return output, metadata


def parse_args():
    parser = argparse.ArgumentParser(description='Project semantic analysis by vectorizing project descriptions.')
    parser.add_argument('--workbook', default='datos/informacion_proyecto_pulso.xlsx', help='Path to project Excel workbook')
    parser.add_argument('--output', default='salidas/project_semantic_analysis.csv', help='Output CSV path')
    parser.add_argument('--embedding-method', default='tfidf', choices=['tfidf', 'sentence-transformers'], help='Embedding method')
    parser.add_argument('--embedding-model', default=None, help='SentenceTransformer model name when using sentence-transformers')
    parser.add_argument('--sentence-task', default='clustering', help='Task for sentence-transformers models (e.g. retrieval, text-matching, classification, clustering)')
    parser.add_argument('--n-components', type=int, default=3, help='Number of PCA components')
    parser.add_argument('--n-clusters', type=int, default=8, help='Number of clusters for KMeans')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    workbook_path = Path(args.workbook)
    output_csv = Path(args.output)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    run_analysis(
        workbook_path=workbook_path,
        output_csv=output_csv,
        embedding_method=args.embedding_method,
        embedding_model=args.embedding_model,
        sentence_task=args.sentence_task,
        n_components=args.n_components,
        n_clusters=args.n_clusters,
    )

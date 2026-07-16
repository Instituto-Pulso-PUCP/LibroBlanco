import argparse
from pathlib import Path
import json
import pandas as pd

from openalex_helpers import fetch_openalex_enrichment
from run_pipeline import (
    PUBLICATION_RESULT_TYPES,
    norm_doi,
)

RETRY_ERROR_KEYWORDS = ["429", "Too Many Requests"]


def should_retry_error(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    text = str(value)
    return any(keyword in text for keyword in RETRY_ERROR_KEYWORDS)


def build_title_hint(row):
    title_hint = row.get('result_title') or row.get('result_other') or row.get('project_title') or ''
    title_hint = str(title_hint).strip()
    if title_hint.upper() in {'', '-', 'NO APLICA', 'NO APLICA '}:
        return ''
    return title_hint


def build_doi_hint(row):
    doi_hint = row.get('doi_norm') or row.get('doi_raw') or ''
    doi_hint = doi_hint if norm_doi(doi_hint) else ''
    return doi_hint


def repair_openalex_csv(input_path: Path, output_path: Path, drop_old_columns: bool = True):
    df = pd.read_csv(input_path, dtype=str)

    if 'openalex_enrichment_error' not in df.columns:
        raise ValueError('Input CSV must contain openalex_enrichment_error column')

    if drop_old_columns:
        for col in ['openalex_query', 'openalex_suggested_fields']:
            if col in df.columns:
                df.drop(columns=[col], inplace=True)

    if 'openalex_work_id' not in df.columns:
        df['openalex_work_id'] = None
    if 'openalex_doi' not in df.columns:
        df['openalex_doi'] = None
    if 'openalex_is_oa' not in df.columns:
        df['openalex_is_oa'] = None
    if 'openalex_oa_status' not in df.columns:
        df['openalex_oa_status'] = None
    if 'openalex_oa_url' not in df.columns:
        df['openalex_oa_url'] = None
    if 'openalex_publication_year' not in df.columns:
        df['openalex_publication_year'] = None
    if 'openalex_cited_by_count' not in df.columns:
        df['openalex_cited_by_count'] = None
    if 'openalex_source_display_name' not in df.columns:
        df['openalex_source_display_name'] = None
    if 'openalex_authors' not in df.columns:
        df['openalex_authors'] = None
    if 'openalex_enrichment_raw_json' not in df.columns:
        df['openalex_enrichment_raw_json'] = None

    rows_to_retry = []
    for idx, row in df.iterrows():
        if row.get('result_type') in PUBLICATION_RESULT_TYPES and should_retry_error(row.get('openalex_enrichment_error')):
            rows_to_retry.append(idx)

    print(f'Retrying OpenAlex enrichment for {len(rows_to_retry)} rows...')

    for idx in rows_to_retry:
        row = df.loc[idx]
        title_hint = build_title_hint(row)
        doi_hint = build_doi_hint(row)
        enrichment = fetch_openalex_enrichment(doi=doi_hint, title=title_hint)

        df.at[idx, 'openalex_work_id'] = enrichment.get('openalex_work_id')
        df.at[idx, 'openalex_doi'] = enrichment.get('openalex_doi')
        df.at[idx, 'openalex_is_oa'] = enrichment.get('openalex_is_oa')
        df.at[idx, 'openalex_oa_status'] = enrichment.get('openalex_oa_status')
        df.at[idx, 'openalex_oa_url'] = enrichment.get('openalex_oa_url')
        df.at[idx, 'openalex_publication_year'] = enrichment.get('openalex_publication_year')
        df.at[idx, 'openalex_cited_by_count'] = enrichment.get('openalex_cited_by_count')
        df.at[idx, 'openalex_source_display_name'] = enrichment.get('openalex_source_display_name')
        df.at[idx, 'openalex_authors'] = enrichment.get('openalex_authors')
        df.at[idx, 'openalex_enrichment_error'] = enrichment.get('openalex_enrichment_error')
        df.at[idx, 'openalex_enrichment_raw_json'] = enrichment.get('openalex_enrichment_raw_json')

    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f'Wrote repaired CSV to {output_path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Retry OpenAlex enrichment for rows that failed with HTTP 429')
    parser.add_argument('input_csv', help='Already enriched CSV file with openalex_enrichment_error column')
    parser.add_argument('output_csv', nargs='?', help='Output CSV path (defaults to input with .repaired.csv suffix)')
    parser.add_argument('--keep-old-columns', action='store_true', help='Keep openalex_query and openalex_suggested_fields columns if present')
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    if not input_path.exists():
        raise FileNotFoundError(f'Input file not found: {input_path}')

    output_path = Path(args.output_csv) if args.output_csv else input_path.with_name(input_path.stem + '.repaired.csv')
    repair_openalex_csv(input_path, output_path, drop_old_columns=not args.keep_old_columns)

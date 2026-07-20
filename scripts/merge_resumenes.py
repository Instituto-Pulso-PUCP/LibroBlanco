#!/usr/bin/env python3
"""Merge the pre-computed abstract/keyword results from the folder
"Obtencion de resumenes" into the pipeline outputs, matching by DOI.

The abstracts tool (`resumenes_por_doi.py`) and the Scopus-web integrator
(`integrar_scopus.py`) produce a CSV keyed by DOI with columns such as
``resumen``, ``palabras_clave`` and their provenance. This step folds those
columns into our ground-truth outputs (06 / 07) so the readable XLSX gains
abstracts and keywords without re-querying any API.

Merged columns are namespaced so the XLSX exporter colors them as the
"resumenes" source and they never collide with existing pipeline columns:

    doi           (base) -> match key only
    titulo               -> resumen_titulo
    fuente_titulo        -> resumen_titulo_fuente
    resumen              -> resumen
    fuente_resumen       -> resumen_fuente
    palabras_clave       -> palabras_clave
    fuente_palabras_clave-> palabras_clave_fuente
    scopus_id            -> resumen_scopus_id
    eid                  -> resumen_eid
    pubmed_id            -> resumen_pubmed_id
    openalex_id          -> resumen_openalex_id

Usage::

    # merge into both 06 and 07 using the CSV found in the Obtencion folder
    python merge_resumenes.py

    # explicit files
    python merge_resumenes.py --main salidas/06_...csv --resumenes ruta/doi-resultados.csv \
        --output salidas/06_..._con_resumenes.csv
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from export_xlsx import write_colored_xlsx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'salidas'
RESUMENES_DIR = ROOT / 'Obtención de resúmenes'

_DOI_PREFIX_RE = re.compile(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', re.IGNORECASE)

# base column -> output column
_COLUMN_MAP = {
    'titulo': 'resumen_titulo',
    'fuente_titulo': 'resumen_titulo_fuente',
    'resumen': 'resumen',
    'fuente_resumen': 'resumen_fuente',
    'palabras_clave': 'palabras_clave',
    'fuente_palabras_clave': 'palabras_clave_fuente',
    'scopus_id': 'resumen_scopus_id',
    'eid': 'resumen_eid',
    'pubmed_id': 'resumen_pubmed_id',
    'openalex_id': 'resumen_openalex_id',
}


def norm_doi(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''
    text = str(value).strip()
    if text.lower() in {'', '-', 'nan', 'none'}:
        return ''
    text = _DOI_PREFIX_RE.sub('', text)
    return text.strip().rstrip(' .;,').lower()


def find_default_resumenes_csv() -> Path | None:
    """Locate a doi-resultados-style CSV inside the Obtencion folder."""
    if not RESUMENES_DIR.exists():
        return None
    # Prefer files that look like final abstract results.
    preferred = list(RESUMENES_DIR.rglob('doi-resultados*.csv'))
    if preferred:
        return sorted(preferred)[0]
    candidates = list(RESUMENES_DIR.rglob('*.csv'))
    # Keep only CSVs that actually carry a 'resumen' column.
    for path in sorted(candidates):
        try:
            head = pd.read_csv(path, nrows=0)
        except Exception:
            continue
        cols = {str(c).strip().lower() for c in head.columns}
        if 'resumen' in cols and ('doi' in cols):
            return path
    return None


def load_resumenes(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    # Find the DOI column regardless of case/spacing.
    doi_col = next((c for c in df.columns if str(c).strip().lower() == 'doi'), None)
    if doi_col is None:
        raise ValueError(f'El CSV de resumenes no tiene columna DOI: {path}')
    df = df.rename(columns={doi_col: 'doi'})
    df['_doi_key'] = df['doi'].map(norm_doi)
    df = df[df['_doi_key'] != ''].copy()

    # Consolidate duplicate DOIs: keep first non-empty value per column.
    def first_nonempty(series):
        for v in series:
            if str(v).strip():
                return v
        return ''

    agg = {c: first_nonempty for c in df.columns if c not in ('_doi_key',)}
    df = df.groupby('_doi_key', as_index=False).agg(agg)
    return df


def apply_resumenes(main: pd.DataFrame, resumenes_df: pd.DataFrame) -> tuple[pd.DataFrame, int, list]:
    """Merge namespaced resumenes columns into ``main`` by normalized DOI.

    Returns ``(merged_df, matched_count, added_columns)``. Only adds columns;
    a re-run refreshes them cleanly. Non-matching rows get empty strings.
    """
    main = main.copy()
    doi_source = 'doi_norm' if 'doi_norm' in main.columns else (
        'doi_raw' if 'doi_raw' in main.columns else None)
    if doi_source is None:
        raise ValueError('El DataFrame no tiene columna doi_norm ni doi_raw para cruzar.')
    main['_doi_key'] = main[doi_source].map(norm_doi)

    # Build the right-hand frame with namespaced columns.
    right_cols = {'_doi_key': '_doi_key'}
    for base_col, out_col in _COLUMN_MAP.items():
        if base_col in resumenes_df.columns:
            right_cols[base_col] = out_col
    right = resumenes_df[list(right_cols.keys())].rename(columns=right_cols)

    # Drop any pre-existing merged columns so a re-run refreshes cleanly.
    added_cols = [c for c in _COLUMN_MAP.values() if c in right.columns]
    main = main.drop(columns=[c for c in added_cols if c in main.columns], errors='ignore')

    merged = main.merge(right, on='_doi_key', how='left')
    if added_cols:
        probe = merged[added_cols[0]]
        matched = int((probe.notna() & (probe.astype(str).str.strip() != '')).sum())
    else:
        matched = 0
    merged = merged.drop(columns=['_doi_key'])
    # Fill only the newly added columns to avoid touching existing NaN semantics.
    for col in added_cols:
        merged[col] = merged[col].fillna('')
    return merged, matched, added_cols


def merge_into(main_csv: Path, resumenes_df: pd.DataFrame, output_csv: Path,
               make_xlsx: bool = True, xlsx_title: str | None = None) -> dict:
    main = pd.read_csv(main_csv, dtype=str, keep_default_na=False)
    merged, matched, added_cols = apply_resumenes(main, resumenes_df)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_csv, index=False, encoding='utf-8-sig')

    xlsx_path = None
    if make_xlsx:
        xlsx_path = output_csv.with_suffix('.xlsx')
        write_colored_xlsx(merged, xlsx_path, title=xlsx_title)

    stats = {
        'main_csv': str(main_csv),
        'output_csv': str(output_csv),
        'output_xlsx': str(xlsx_path) if xlsx_path else None,
        'rows': int(len(merged)),
        'rows_with_abstract_data': matched,
        'columns_added': added_cols,
    }
    return stats


def _default_targets():
    """Return [(main_csv, output_csv, title)] for 06 and 07 when present."""
    targets = []
    mapping = [
        ('06_project_results_ground_truth.csv', 'Resultados de proyectos + resumenes'),
        ('07_project_publication_ground_truth.csv', 'Publicaciones declaradas + resumenes'),
    ]
    for name, title in mapping:
        main = OUT / name
        if main.exists():
            out = main.with_name(main.stem + '_con_resumenes.csv')
            targets.append((main, out, title))
    return targets


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Integra los resumenes/palabras clave de "Obtencion de resumenes" en las salidas del pipeline (cruce por DOI).')
    parser.add_argument('--main', type=Path, default=None,
                        help='CSV del pipeline a enriquecer (por defecto, 06 y 07 en salidas/).')
    parser.add_argument('--resumenes', type=Path, default=None,
                        help='CSV de resumenes por DOI (por defecto, se busca en la carpeta "Obtencion de resumenes").')
    parser.add_argument('--output', type=Path, default=None,
                        help='CSV de salida (por defecto, <main>_con_resumenes.csv).')
    parser.add_argument('--no-xlsx', action='store_true', help='No genera el XLSX coloreado.')
    args = parser.parse_args(argv)

    resumenes_path = args.resumenes or find_default_resumenes_csv()
    if resumenes_path is None or not Path(resumenes_path).exists():
        parser.error(
            'No se encontro un CSV de resumenes. Indique --resumenes con la ruta al '
            'archivo doi-resultados.csv.')
    print(f'Usando resumenes: {resumenes_path}', flush=True)
    resumenes_df = load_resumenes(Path(resumenes_path))
    print(f'  {len(resumenes_df)} DOIs con datos de resumen/palabras clave.', flush=True)

    if args.main:
        output = args.output or args.main.with_name(args.main.stem + '_con_resumenes.csv')
        targets = [(args.main, output, None)]
    else:
        targets = _default_targets()
        if not targets:
            parser.error('No se encontraron 06/07 en salidas/. Indique --main.')

    for main_csv, output_csv, title in targets:
        stats = merge_into(main_csv, resumenes_df, output_csv,
                           make_xlsx=not args.no_xlsx, xlsx_title=title)
        print(
            f'- {Path(stats["main_csv"]).name}: {stats["rows_with_abstract_data"]}/{stats["rows"]} '
            f'filas con datos de resumen -> {Path(stats["output_csv"]).name}'
            + (f' (+ {Path(stats["output_xlsx"]).name})' if stats['output_xlsx'] else ''),
            flush=True,
        )


if __name__ == '__main__':
    main()

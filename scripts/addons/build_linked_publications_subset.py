#!/usr/bin/env python3
"""Build the text corpus for the project-linked publications clustering experiment.

Uses all 1,192 rows of 07_project_publication_ground_truth.csv (every
declared result a tracked project reported), not just the 376/386 rows that
matched into the full publications catalog by DOI. For matched rows, reuses
the already-vetted title/abstract/keywords/journal from
03_publications_master.csv (proper WOS/RI-preferred abstract, deduped
keywords, OpenAlex backfill). For the rest, falls back to the ground-truth
file's own columns:

- `result_title`/`journal_raw` use a literal "-" as a missing-value
  placeholder in a large fraction of rows; treated as empty here.
- `source_abstract` has the same Scopus-URL-junk bug fixed in
  01_build_pipeline.py (raw scopus.com links, not real text) - excluded in
  favor of `resumen` (human-supplied abstract) then `openalex_abstract`
  (OpenAlex-reconstructed).
- Keywords: `source_keywords` and `palabras_clave` combined (both sparse;
  no reliable way to detect the single-AI-tag pattern here the way the main
  pipeline does for Scopus, so both are kept as-is).

Usage::

    python scripts/addons/build_linked_publications_subset.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'salidas'
GROUND_TRUTH_CSV = OUT / '07_project_publication_ground_truth.csv'
MASTER_CSV = OUT / '03_publications_master.csv'
LINKED_CSV = OUT / '07_publications_linked_full.csv'

PLACEHOLDER = '-'


def clean(value):
    value = (value or '').strip()
    return '' if value == PLACEHOLDER else value


def main():
    gt = pd.read_csv(GROUND_TRUTH_CSV, dtype=str, keep_default_na=False)
    master = pd.read_csv(MASTER_CSV, dtype=str, keep_default_na=False)
    master_by_id = master.set_index('publication_id')[['title', 'abstract', 'keywords', 'journal']]

    rows = []
    for _, r in gt.iterrows():
        pub_id = r['publication_id'].strip()
        if pub_id and pub_id in master_by_id.index:
            m = master_by_id.loc[pub_id]
            title, abstract, keywords, journal = m['title'], m['abstract'], m['keywords'], m['journal']
            row_id = pub_id
        else:
            title = clean(r['result_title'])
            abstract = clean(r['resumen']) or clean(r['openalex_abstract'])
            keywords = ' '.join(k for k in (clean(r['source_keywords']), clean(r['palabras_clave'])) if k)
            journal = clean(r['journal_raw'])
            row_id = f"gt_{r['project_id']}_{r['cod_prod']}"
        rows.append({
            'publication_id': row_id,
            'title': title,
            'abstract': abstract,
            'keywords': keywords,
            'journal': journal,
        })

    out = pd.DataFrame(rows)
    n_with_text = (out[['title', 'abstract', 'keywords', 'journal']].apply(lambda c: c.str.strip()).sum(axis=1).str.len() > 0).sum()
    print(f'{len(out)} declared results; {n_with_text} have at least one non-empty text field.')
    out.to_csv(LINKED_CSV, index=False, encoding='utf-8-sig')
    print(f'Wrote {len(out)} rows to {LINKED_CSV}')


if __name__ == '__main__':
    main()

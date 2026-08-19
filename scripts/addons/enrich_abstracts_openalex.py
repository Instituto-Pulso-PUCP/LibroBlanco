#!/usr/bin/env python3
"""Backfill missing/empty abstracts in 03_publications_master.csv via OpenAlex.

Targets only rows whose ``abstract`` is currently empty (after the Scopus
URL-junk cleanup) - looks each one up by DOI (preferred) or title fallback,
and fills in the OpenAlex-reconstructed abstract when found. Real WOS/RI
abstracts already in the file are never overwritten.

Resumable: uses the existing OpenAlexCache (salidas/openalex_cache.jsonl), so
a restart after an interruption skips already-fetched rows almost instantly.
Also checkpoints the merged output every --checkpoint-every rows so partial
progress is visible/usable without waiting for the full run to finish.

Usage::

    python scripts/addons/enrich_abstracts_openalex.py
"""

from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

import pandas as pd

# Windows can hang indefinitely on DNS resolution without honoring the
# per-request `timeout=` passed to urlopen (the socket timeout only reliably
# covers the connect/read phase on some platforms). This global default
# timeout covers the DNS phase too, so a single bad lookup can't freeze the
# whole run - it raises socket.timeout instead, which the existing
# URLError/retry handling in fetch_openalex_enrichment already deals with.
socket.setdefaulttimeout(15)

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR / 'lib'))
from openalex_helpers import fetch_openalex_enrichment_cached, OpenAlexCache, enrichment_cache_key  # noqa: E402

ROOT = SCRIPTS_DIR.parent
OUT = ROOT / 'salidas'
MASTER_CSV = OUT / '03_publications_master.csv'
CACHE_PATH = OUT / 'openalex_cache.jsonl'
CHECKPOINT_EVERY = 200


def main():
    df = pd.read_csv(MASTER_CSV, dtype=str, keep_default_na=False)
    empty_mask = df['abstract'].str.strip() == ''
    todo_idx = df.index[empty_mask].tolist()
    print(f'Total rows: {len(df)}; empty abstract: {len(todo_idx)}', flush=True)

    cache = OpenAlexCache(CACHE_PATH)
    filled = 0
    checked = 0
    started = time.time()

    for i, idx in enumerate(todo_idx, start=1):
        doi = (df.at[idx, 'doi'] or '').strip()
        title = (df.at[idx, 'title'] or '').strip()
        key = enrichment_cache_key(doi=doi or None, title=title or None)
        if key and key not in cache:
            # About to make a real network call (not a cache hit) - log it so a
            # stall shows exactly which row/DOI it was stuck on.
            print(f'  ...fetching #{i} doi={doi!r} title={title[:60]!r}', flush=True)
        result, was_cached = fetch_openalex_enrichment_cached(doi=doi or None, title=title or None, cache=cache)
        checked += 1
        abstract = (result or {}).get('openalex_abstract') or ''
        if abstract:
            df.at[idx, 'abstract'] = abstract
            filled += 1

        if i % CHECKPOINT_EVERY == 0 or i == len(todo_idx):
            elapsed = time.time() - started
            rate = i / elapsed if elapsed > 0 else 0
            remaining = (len(todo_idx) - i) / rate if rate > 0 else float('nan')
            print(
                f'  [{i}/{len(todo_idx)}] filled={filled} cached_hits_skip_rate_limit='
                f'{"n/a" if not was_cached else "yes"} elapsed={elapsed/60:.1f}min '
                f'eta={remaining/60:.1f}min',
                flush=True,
            )
            df.to_csv(MASTER_CSV, index=False, encoding='utf-8-sig')

    print(f'Done. Checked {checked}, filled {filled} new real abstracts.', flush=True)
    total_real = (df['abstract'].str.strip() != '').sum()
    print(f'Total rows with a real abstract now: {total_real}/{len(df)} ({100*total_real/len(df):.1f}%)', flush=True)


if __name__ == '__main__':
    main()

# Libro Blanco — Embeddings & Clustering Experiment Log

Living reference for the embeddings/clustering work. Updated as runs complete —
see "Run history" at the bottom for traceability across changes.

**Status as of this update:** all three experiments are current/final —
projects (975 rows, CRIS-merged), publications (13,995 rows, full catalog,
post-OpenAlex-backfill), and publications restricted to project-linked
declared results (850/1,192 rows). See §5.

---

## 1. Input data, filters, and merges

### Source files
- `datos/informacion_proyecto_pulso.xlsx` — VRI Excel, sheets: `PROYECTOS`,
  `PROY_RESULTADOS`, `Pubs_SCOPUS`, `Pubs_WoS`, `Pubs_RI`, `ORCID PUCP`.
- `datos/ProyectosPUCPCRIS-20260721.csv` — DSpace-CRIS project export (new
  source, merged in this round).
- `datos/cris_overrides.csv` — human-reviewed match/new/skip decisions for
  CRIS rows the automatic matcher couldn't confidently resolve.

### Projects pipeline
1. `PROYECTOS` sheet filtered to `Año ≥ 2010 AND Estado = "5. Cerrado"` →
   **938 proyectos cerrados** (from 1,928 total).
2. Merged with `datos/ProyectosPUCPCRIS-20260721.csv`
   (`scripts/addons/merge_cris.py`), matching by internal code → exact title →
   fuzzy title (Jaccard ≥ 0.65) → manual overrides. Adds `cris_*` columns
   (abstract, keywords, OCDE/FOS classification, coordinator, co-investigator
   roster, start/end dates) and appends CRIS-only projects that meet the same
   closed/2010+ filter but aren't in the VRI Excel at all.
   - 932/938 original projects matched (39 code, 867 exact title, 15 fuzzy
     title, 11 manual override); 37 new projects added from CRIS.
   - 912 CRIS rows excluded (901 legitimately outside the universe — real
     projects, just not closed/2010+; 7 manual skip; 4 no valid year/status).
   - **Known data-quality flag:** 154 of 975 projects have a co-investigator
     name/role count mismatch in the CRIS export
     (`cris_coinvestigator_count_mismatch=True`).
3. → **`salidas/01_projects_closed.csv`, 975 rows** (canonical, single file).

### Publications pipeline
1. All records from `Pubs_SCOPUS` + `Pubs_WoS` + `Pubs_RI` (24,616 source
   rows), deduplicated by `doi:<doi>` or `titleyear:<title>|<year>` →
   **13,995 unique publications**. This is the *entire* PUCP publication
   catalog captured in those exports — **not** filtered to publications
   linked to the 938/975 tracked projects (only ~376 of the 13,995 have a
   confirmed project link via the ground-truth linkage).
2. **Data-quality fix applied this round:** `Pubs_SCOPUS`'s "Abstract" column
   is a link to the scopus.com record page in every row, not real text (and
   was being picked over real WOS/RI abstracts by a first-non-empty merge
   rule). Fixed by excluding Scopus's abstract from the merge and backfilling
   from WOS/RI where available; same fix applied to `keywords` (Scopus's
   field is a single AI-generated topic tag, not an author keyword list —
   now deprioritized behind real WOS/RI keyword lists). Root cause fixed in
   `scripts/pipeline/01_build_pipeline.py`; existing
   `03_publications_master.csv` patched directly (heavy full pipeline rerun
   not required for this fix).
   - Real abstract coverage: 69.3% (fake, URL-polluted) → **40.1%** (5,614/13,995, honest) → OpenAlex backfill in progress for the remaining 8,381 empty rows.
3. **OpenAlex abstract backfill** (`scripts/addons/enrich_abstracts_openalex.py`,
   in progress): looks up each publication with an empty abstract by DOI
   (preferred) or title fallback via the OpenAlex API (free, no key needed),
   reconstructs the abstract text, fills gaps only — never overwrites an
   existing real abstract. Resumable via `salidas/openalex_cache.jsonl`.
4. → **`salidas/03_publications_master.csv`, 13,995 rows** (canonical).

---

## 2. What we consider "final" data

| Dataset | File | Rows | Universe |
|---|---|---|---|
| Projects | `salidas/01_projects_closed.csv` | 975 | Closed projects, year ≥ 2010 (VRI) + CRIS-only closed/2010+ projects not in the VRI Excel |
| Publications | `salidas/03_publications_master.csv` | 13,995 | All deduplicated Scopus+WoS+RI publication records — full PUCP catalog captured in those exports, **not** restricted to project-linked publications |

Decision explicitly made: use the **full publications catalog**, not the
smaller project-linked subset (~376 unique / 1,192 declared-result rows),
because it has far better title/abstract/keyword coverage and gives more
statistical power — see prior discussion for the tradeoff (narrative
consistency with "these are our tracked projects' outputs" vs. data richness;
richness won).

---

## 3. What was sent to the embeddings

### Projects (`text_columns` in `scripts/analysis/clustering_experiments.py`)
```
title, project_type, knowledge_area,
research_line_1, research_line_2, research_line_3, research_line_4,
research_line, executing_unit, executing_section
```
Chosen by explicit request; excludes `funding_type`/`funder` (previously
included, dropped). CRIS columns (`cris_abstract`, `cris_keywords`,
`cris_ocde_subject`, `cris_fos`, `cris_type_ocde`, `cris_coinvestigators`)
are **not yet** included — fill rates are mostly too low to matter
(`cris_abstract` 0.9%, `cris_keywords` 0.1%, `cris_fos`/`cris_ocde_subject`
4.5%) except `cris_type_ocde` (43.9%, a project-type-like classification) and
`cris_coinvestigators` (48.8%, not topical content) — open question, not
yet decided.

Missing-column handling: empty fields are dropped, not padded with
placeholder text (`clean_text`/`build_text` in `clustering_experiments.py`).
Confirmed via a dedicated diagnostic plot
(`research_line_coverage_*.png`) that sparse research-line fields are **not**
driving the cluster split — con/sin línea de investigación points are fully
intermixed in PCA space across all embeddings checked.

### Publications
```
title, abstract, keywords, journal
```
Chosen by explicit request over the narrower `title, abstract, keywords`.
`journal` was not previously embedded despite 97.3% coverage.

---

## 4. Embedding models and clustering algorithms

### Embedding models (registry: `scripts/lib/embeddings.py`)

| Key | Model | Dim | Notes |
|---|---|---|---|
| `tfidf` | TF-IDF (baseline) | 2000 | sklearn, max_features=2000 |
| `jina-v5-nano` | jinaai/jina-embeddings-v5-text-nano | 768 | `task='clustering'` |
| `bge-m3` | BAAI/bge-m3 | 1024 | |
| `snowflake-arctic-l-v2` | Snowflake/snowflake-arctic-embed-l-v2.0 | 1024 | |
| `minilm-multilingual` | sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 | 384 | |
| `e5-small-multilingual` | intfloat/multilingual-e5-small | 384 | `"query: "` prefix (e5 FAQ: use query-prefix for clustering/feature use, not passage-prefix) |
| `nomic-v2-moe` | nomic-ai/nomic-embed-text-v2-moe | 768 | `trust_remote_code=True`, `prompt_name='passage'` |

Removed from the registry: `mpnet-multilingual`, `e5-base-multilingual`
(explicitly dropped), `gte-multilingual-base` (added, then removed — hit an
unresolved open bug in `sentence-transformers`'s remote-code loader,
[huggingface/sentence-transformers#3717](https://github.com/huggingface/sentence-transformers/issues/3717)).

All sentence-transformer embeddings are L2-normalized so downstream
Euclidean-based clustering behaves like cosine similarity.

### Clustering algorithms (`scripts/lib/clustering.py`)
- **HDBSCAN** — density-based, can leave points unassigned as noise (`-1`).
- **K-Means**
- **Agglomerative** (hierarchical)
- **Gaussian Mixture**

Every (embedding × method) combination is run and scored on silhouette,
Davies-Bouldin, and Calinski-Harabasz.

---

## 5. Numbers — current

### Projects (975 rows, CRIS-merged) — top result per embedding

| Embedding | Best method | k | silhouette | noise % |
|---|---|---|---|---|
| jina-v5-nano | HDBSCAN | 9 | **0.270** | 60.1% |
| minilm-multilingual | HDBSCAN | 7 | 0.120 | 70.0% |
| bge-m3 | HDBSCAN | 5 | 0.093 | 78.4% |
| e5-small-multilingual | HDBSCAN | 4 | 0.091 | 84.5% |
| snowflake-arctic-l-v2 | HDBSCAN | 6 | 0.074 | 69.5% |
| nomic-v2-moe | HDBSCAN | 2 | 0.052 | 43.8% |
| TF-IDF | K-Means | 12 | 0.040 | 0.0% |

Full table: `salidas/clustering/projects/comparison_metrics.md`.
jina-v5-nano wins K-Means/GMM/Agglomerative too (0.134-0.139, 0% noise).

### Publications (13,995 rows, full catalog) — **current**

Post-OpenAlex-backfill run (73.2% real abstract coverage) — top result per
embedding:

| Embedding | Best method | k | silhouette | noise % |
|---|---|---|---|---|
| minilm-multilingual | HDBSCAN | 2 | **0.287** | 72.4% |
| jina-v5-nano | HDBSCAN | 4 | 0.252 | 67.8% |
| nomic-v2-moe | HDBSCAN | 2 | 0.233 | 88.6% |
| TF-IDF | HDBSCAN | 2 | 0.059 | 91.0% |
| e5-small-multilingual | K-Means | 5 | 0.029 | 0.0% (HDBSCAN found 0 clusters, 100% noise) |
| bge-m3 | K-Means | 5 | 0.029 | 0.0% (HDBSCAN found 0 clusters, 100% noise) |
| snowflake-arctic-l-v2 | K-Means | 5 | 0.028 | 0.0% (HDBSCAN found 0 clusters, 100% noise) |

Full table: `salidas/clustering/publications/comparison_metrics.md`.
minilm-multilingual and jina-v5-nano are the only embeddings where HDBSCAN
finds real structure; bge-m3, snowflake-arctic-l-v2, and e5-small-multilingual
collapse to either one giant cluster or 100% noise under HDBSCAN on this
dataset — same qualitative pattern as the earlier (invalid) run, but now on
clean, real abstract text.

### Publications, project-linked declared results (850 rows) — **current**

All 1,192 declared results a tracked project reported (articles, congress
papers, book chapters, books) — not just the 376 that matched into the full
publications catalog by DOI. For matched rows, reuses the vetted
title/abstract/keywords/journal from `03_publications_master.csv`; for the
rest, falls back to the ground-truth file's own columns (`result_title`,
`resumen`/`openalex_abstract`, `source_keywords`+`palabras_clave`,
`journal_raw`), with the literal `"-"` missing-value placeholder cleaned to
empty and the Scopus-URL-junk `source_abstract` field excluded (same bug as
the one fixed in `01_build_pipeline.py`). Built via
`scripts/addons/build_linked_publications_subset.py` →
`salidas/07_publications_linked_full.csv`. 850/1,192 rows have at least one
non-empty text field; the other 342 have no title, abstract, keywords, or
journal at all and are dropped rather than embedded as empty text.

| Embedding | Best method | k | silhouette | noise % |
|---|---|---|---|---|
| jina-v5-nano | HDBSCAN | 15 | **0.363** | 66.4% |
| minilm-multilingual | HDBSCAN | 4 | 0.205 | 41.2% |
| nomic-v2-moe | HDBSCAN | 4 | 0.132 | 60.9% |
| TF-IDF | HDBSCAN | 3 | 0.094 | 67.8% |
| snowflake-arctic-l-v2 | HDBSCAN | 8 | 0.083 | 70.1% |
| e5-small-multilingual | HDBSCAN | 3 | 0.083 | 82.0% |
| bge-m3 | HDBSCAN | 5 | 0.054 | 77.4% |

Full table: `salidas/clustering/publications_linked/comparison_metrics.md`.
Highest silhouette of any experiment run so far (jina-v5-nano 0.363) — likely
an artifact of the much smaller, more topically homogeneous sample (850 rows
vs 13,995) rather than genuinely tighter clusters; take the comparison across
experiments with a grain of salt rather than reading it as "this subset
clusters better."

For reference, the **invalid** first full-catalog publications run (before
the Scopus abstract-URL bug was found/fixed — abstract field was 91.4% junk
URLs for Scopus-sourced rows) gave jina-v5-nano+HDBSCAN silhouette 0.263 and
minilm+HDBSCAN 0.303 (2 clusters, 70.6% noise) — kept here only as a
historical data point; **do not present these numbers**, they're
contaminated by the URL bug.

---

## Run history

| # | Dataset | Rows | Text columns | Registry | Result | Status |
|---|---|---|---|---|---|---|
| 1 | projects | 938 | title, project_type, knowledge_area, research_line, funding_type, funder | 8 models (incl. gte) | minilm+HDBSCAN 0.244 | superseded |
| 2 | publications | 13,995 | title, abstract, keywords | 5 models (incl. mpnet, e5-base) | jina+HDBSCAN 0.26 | superseded |
| 3 | projects | 938 | +research_line_1-4, executing_unit/section; -funding/funder | 7 models (gte removed) | jina+HDBSCAN 0.259 | superseded |
| 4 | publications | 13,995 | +journal | 7 models | minilm+HDBSCAN 0.303 (jina 0.263) | **invalid — Scopus abstract-URL bug** |
| 5 | projects | 975 (CRIS-merged) | same as #3 | 7 models | jina+HDBSCAN 0.270 | **current** |
| 6 | publications | 13,995 | same as #4 | 7 models | Scopus URLs cleaned, WOS/RI backfilled (40.1% real abstract) | superseded |
| 7 | publications | 13,995 | same as #4 | 7 models | + OpenAlex backfill (73.2% real abstract); minilm+HDBSCAN 0.287 (jina 0.252) | **current** |
| 8 | publications, project-linked declared results | 850 (of 1,192) | same as #4, master text where matched else ground-truth columns | 7 models | jina+HDBSCAN 0.363 (minilm 0.205) | **current** |

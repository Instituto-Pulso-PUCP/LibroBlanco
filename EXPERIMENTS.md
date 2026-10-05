# Libro Blanco — Embeddings & Clustering Experiment Log

Living reference for the embeddings/clustering work. Updated as runs complete —
see "Run history" at the bottom for traceability across changes.

**Status as of this update:** all three experiments are current/final (plus the CEPLAN sub-temática linking work in §6) —
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
   complete, stopped by explicit choice rather than exhausting the queue):
   looks up each publication with an empty abstract by DOI (preferred) or
   title fallback via the OpenAlex API (free, no key needed), reconstructs
   the abstract text, fills gaps only — never overwrites an existing real
   abstract. Resumable via `salidas/openalex_cache.jsonl`. Final abstract
   coverage: **10,245/13,995 (73.2%)** — 3,750 rows have no recoverable
   abstract from any source (no DOI match, or OpenAlex has none either).
   - **Provenance tracked**: `abstract_source` column added to
     `03_publications_master.csv` (WOS/RI: 5,614; OpenAlex: 4,631; empty:
     3,750) — reconstructed from `publication_sources` in
     `libro_blanco.db` (which source rows had a real, non-Scopus abstract)
     rather than tracked live during the backfill, since the fix and the
     backfill both predate this column existing.
   - Ran into repeated multi-hour stalls mid-run (Windows DNS resolution
     hanging past the per-request timeout) — fixed with
     `socket.setdefaulttimeout(15)` and resumed from the on-disk cache each
     time; no data was lost, each stall just cost wall-clock time.
4. → **`salidas/03_publications_master.csv`, 13,995 rows** (canonical).

### Project-linked publications subset (third experiment)
Built from `07_project_publication_ground_truth.csv` (all 1,192 declared
results across the 361 ground-truth projects — not just the 376/386 that
resolved into the full catalog by DOI) via
`scripts/addons/build_linked_publications_subset.py`. For rows that matched
into the master catalog, reuses its vetted title/abstract/keywords/journal;
for the rest, falls back to the ground-truth file's own columns (`result_title`,
`resumen`/`openalex_abstract`, `source_keywords`+`palabras_clave`,
`journal_raw`), with the `"-"` placeholder cleaned to empty and the same
Scopus-URL-junk pattern excluded from `source_abstract`. → **`salidas/07_publications_linked_full.csv`, 1,192 rows, 850 with at least one non-empty text field** (342 dropped — no title, abstract, keywords, or journal at all).

---

## 2. What we consider "final" data

| Dataset | File | Rows | Universe |
|---|---|---|---|
| Projects | `salidas/01_projects_closed.csv` | 975 | Closed projects, year ≥ 2010 (VRI) + CRIS-only closed/2010+ projects not in the VRI Excel |
| Publications (full catalog) | `salidas/03_publications_master.csv` | 13,995 | All deduplicated Scopus+WoS+RI publication records — full PUCP catalog captured in those exports, **not** restricted to project-linked publications |
| Publications (project-linked) | `salidas/07_publications_linked_full.csv` | 1,192 (850 embedded) | Every declared result of the 361 ground-truth-linked closed projects, not just the 376/386 that resolved into the full catalog by DOI |

Three separate experiments, kept separate rather than merged, because they
answer three different questions: **projects** = what topics did our closed
projects work on (from project metadata, no publication text at all);
**publications, full catalog** = what does PUCP's entire captured research
output look like, most of it unconnected to any tracked project (richer text,
far more statistical power, but only ~2.7% of it traces back to a tracked
project); **publications, project-linked** = what did *specifically* our
tracked projects' declared results look like, at the cost of a much smaller,
patchier-text sample (850 usable of 1,192). See §5 for results side by side.

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
are **not yet** included in the clustering embeddings — open question, not
yet decided. **Correction (2026-08-31):** the fill rates previously noted
here (`cris_abstract` 0.9%, `cris_keywords` 0.1%, `cris_fos`/`cris_ocde_subject`
4.5%) reflected a run against an older/thinner CRIS export and were wrong for
the current data — measured against the current
`datos/ProyectosPUCPCRIS-20260814.csv` + `salidas/01_projects_closed_con_cris.csv`
(984 rows): `cris_abstract` 66.6%, `cris_keywords` 93.1%, `cris_fos` 93.2%,
`cris_ocde_subject` 93.2%, `cris_type_ocde` 44.2%, `cris_coinvestigators`
62.4%. `cris_abstract`/`cris_keywords` in particular are strong candidates
for the topic-normalization pipeline in
[docs/topic_normalization_pipeline.md](docs/topic_normalization_pipeline.md),
which does use them.

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

## 6. CEPLAN sub-temáticas ↔ projects/publications (2026-10-04/05)

Goal: answer "which PEDN 2050 sub-temáticas does this project/publication
develop?" (top 5 with a minimum threshold) and the reverse ("which units
develop this sub-temática?", including which ones nobody covers). This
replaces the topic ↔ sub-temática view (`ceplan_alignment.py`), judged
unnecessary. Universe: `full-proj-646` (646 projects) and
`publications_linked-529` (529 publications); taxonomy: `Líneas de Inv.`
sheet, 126 sub-temáticas on 4 ON.

Design (agreed): **embeddings propose candidates, an LLM confirms each one**
with a grade 0/1/2 (0 = no real relation, 1 = tangential/indirect, 2 =
clearly develops it or contributes directly useful knowledge). Grades ≥ 1
are kept and weighted into containment/contribution with `lb_membership`,
as with topics.

### 6.1 Embedding calibration (Cohere multilingual v3, same model as the topics)

- **Embeddings alone are not enough.** Unit × sub-temática cosine scores are
  compressed (projects: median 0.50, a unit's top-5 within ~0.04 of each
  other). A few sub-temáticas behave as hubs that score moderately against
  everything ("Política monetaria", "Gestión Territorial", "Vigilancia
  ambiental", "Movilidad Urbana"): pure-math projects land on them. An
  LLM-labelled sample (400 pairs) gave AUC 0.76 for the raw score, with
  precision stuck at 60–70% at any floor. A per-sub-temática z-score (hub
  correction) did no better (AUC 0.76) and dropped real matches.
- **Language penalty.** English texts score ~0.15 lower than Spanish ones
  against the Spanish CEPLAN text with equivalent content (345 of 529
  publications are in English). Embedding an English translation of each
  sub-temática (LLM-translated once, cached in
  `salidas/topics/ceplan/subtematicas_en.json`, `lb_ceplan.translate_texts`)
  and taking max(es, en) only partly closes it (median top score of English
  publications 0.451 → 0.470); the rest is real content (basic science with
  no policy link).
- **Floor.** Below ~0.45 almost nothing is related per the LLM labels (5%);
  the human labels (§6.2) found relations down to ~0.40, almost all
  tangential (37% of pairs below 0.50 related, only 7% graded 2). Decision:
  **floor 0.40, up to 8 candidates per unit**, and let the LLM filter.

### 6.2 LLM judge benchmark (`scripts/analysis/ceplan_judge_benchmark.py`)

Same prompt for every model (`SYSTEM` in the script): unit text (≤ 3 000
chars) + its 5 candidate sub-temáticas → JSON array of grades. 80 units (40
projects, 40 publications, stratified across score levels) × 5 = 400 pairs.
Reference: Claude Sonnet 5 (the pipeline's model, labelled during
calibration). Non-Claude models through the Bedrock Converse API
(`lb_aws.BedrockClient.converse`). Prices: AWS public price list, on-demand
us-east-1, published 2026-09-30/10-03 (`PRICES` in the script). Total cost of
the benchmark ≈ USD 0.30.

**Human gold set:** 100 of the 400 pairs (20 units: 10 projects, 10
publications, spread across score levels), graded by one annotator (the
project lead) without seeing model grades or scores, through a private
claude.ai artifact; merged into `salidas/topics/ceplan/benchmark/gold_humano.csv`.
Distribution: 36 × 0, 32 × 1, 32 × 2 (64% related).

| Model | Bedrock ID | κ vs Sonnet 5 (400) | κ vs human (100) | 95% CI, unit bootstrap | κ on "= 2" vs human | % marked related | Invalid answers | USD / 1 000 units |
|---|---|---:|---:|---|---:|---:|---:|---:|
| Sonnet 5 | `us.anthropic.claude-sonnet-5` | — | 0.51 | 0.33–0.68 | 0.35 | 52% | — | ~2.66 (est.) |
| Haiku 4.5 | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.63 | **0.61** | 0.35–0.81 | 0.43 | 64% | 0% | 2.26 |
| **Llama 4 Maverick** | `us.meta.llama4-maverick-17b-instruct-v1:0` | 0.62 | 0.59 | 0.37–0.76 | **0.48** | 72% | 0% | **0.29** |
| Nova Pro | `us.amazon.nova-pro-v1:0` | 0.73 | 0.56 | 0.37–0.73 | 0.39 | 57% | 2.5% | 0.52 |
| gpt-oss-120b | `openai.gpt-oss-120b-1:0` | 0.60 | 0.50 | 0.23–0.71 | 0.39 | 70% | 0% | 0.28 |
| Qwen3 32B | `qwen.qwen3-32b-v1:0` | 0.72 | 0.50 | 0.27–0.69 | 0.33 | 51% | 0% | 0.11 |
| GLM 4.7 | `zai.glm-4.7` | 0.71 | 0.44 | 0.26–0.59 | 0.40 | 45% | 0% | 0.40 |

κ = Cohen's kappa on related (grade ≥ 1) vs not, unless noted. Percent
"marked related" is measured on the 100 gold pairs.

Findings:
- **Agreement with Sonnet is not accuracy.** The models that agree most with
  Sonnet (Nova Pro, Qwen3, GLM) are not the ones that agree most with the
  human. All model pairs agree with each other at κ 0.50–0.73, so ~0.7 is
  the inter-LLM ceiling on this task.
- **The models are stricter than the human.** Most disagreements are pairs
  the human graded 1 (tangential) and the model graded 0 (Sonnet: 16 of 32;
  Qwen3: 15). Models confirm the human's 0s well (Sonnet 30 of 36).
- **Sonnet 5 is never better than the cheap models against the human**: it
  is the best model in only 2% of unit-bootstrap resamples, and Llama 4
  Maverick beats it in 77%.
- **The ranking among the cheap models is not settled by this sample**: best
  model across resamples is Haiku 47%, Llama 31%, Nova Pro 13%; and it flips
  by domain (projects: Haiku 0.75, Qwen3 0.65, Llama 0.56; publications:
  Llama 0.62, Haiku 0.47, Qwen3 0.33).
- Haiku 4.5 writes explanations despite the instruction (≈ 270 output
  tokens/unit), so it costs about as much as Sonnet. Nova Pro sometimes adds
  `//` comments inside the JSON array.
- A 7-model majority vote reaches κ 0.62 vs the human — no gain over Llama
  alone at 7× the cost.

### 6.3 Decision

**Llama 4 Maverick** (`us.meta.llama4-maverick-17b-instruct-v1:0`) as the
verifier, with floor 0.40 and up to 8 candidates per unit. Reasons: it sits
in the top group against the human (κ 0.59), it has the best agreement on
clear relations (κ 0.48 on "= 2", and it never graded 0 a pair the human
graded 2: 0 of 32), its leniency is close to the human's, and the full run
costs ≈ USD 0.30 (vs ≈ 2.7 with Sonnet 5).

### 6.4 Limits of the evidence and required validation

The gold set is enough to drop Sonnet 5 for a cheaper model, **not** to
claim Llama is the best cheap model, and **not** to report the pipeline's
precision:
- 20 units and 52 of the 126 sub-temáticas; one annotator (no human-human
  agreement measured, so the human ceiling is unknown);
- it only contains each unit's top 5 by score (the final pipeline uses up to
  8 with floor 0.40; only 18 gold pairs score below 0.45).

**Required before publishing results:** grade a random sample of the
production links (~30 units balanced across domains, ~100–150 links) with
the same criterion, to report precision on the real output and check for a
domain where Llama fails (rerunning with Haiku 4.5 or Nova Pro costs cents).
Optional: a second annotator on ~40 of the 100 gold pairs, to measure the
human ceiling.

Side finding: the `us.` inference profile for Sonnet 5 bills the regional
rate ($2.20 / $11 per M tokens); `global.anthropic.claude-sonnet-5` bills
$2 / $10. Switching `bedrock.llm_model_id` saves 10% on future topic
extractions.

Files: `scripts/analysis/ceplan_judge_benchmark.py` (gold / run / report),
`scripts/analysis/ceplan_gold_label.py` (terminal labelling alternative),
`salidas/topics/ceplan/benchmark/` (`unidades.jsonl`, `gold_humano.csv`,
`respuestas/<model>.jsonl`, `reporte.md`).

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
| 9 | CEPLAN calibration: projects + publications_linked × 126 sub-temáticas | 646 + 529 units | title, cris_abstract, cris_keywords / title, abstract (unit embeddings) vs sub-temática + temática + OE/AE text, es + en | Cohere multilingual v3 | AUC 0.76 vs LLM labels; floor 0.40, top-8 | **current** |
| 10 | CEPLAN LLM-judge benchmark (§6.2) | 400 pairs (100 human-graded) | unit text ≤ 3 000 chars + 5 candidates | 7 LLMs on Bedrock | Llama 4 Maverick chosen (κ 0.59 vs human, USD 0.29 / 1 000 units) | **current** |

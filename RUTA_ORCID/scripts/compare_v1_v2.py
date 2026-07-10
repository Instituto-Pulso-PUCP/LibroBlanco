"""
Comparison: v1 (coordinator name matching) vs v2 (PROY_RESULTADOS direct linking).
Reads the current DB + Excel and prints a summary without modifying any outputs.
"""
from pathlib import Path
import sqlite3, re, unicodedata, pandas as pd, json

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "datos" / "informacion_proyecto_pulso.xlsx"
DB    = ROOT / "salidas" / "libro_blanco.db"

def norm_doi(x):
    s = str(x).strip().lower() if x and not (isinstance(x, float) and pd.isna(x)) else ""
    if s in {"", "-", "nan", "none"}: return ""
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s)
    return s.strip().rstrip('.')

# ── Load existing v1 candidates ───────────────────────────────────────────────
con = sqlite3.connect(DB)
v1 = pd.read_sql("SELECT project_id, publication_id, score, confidence FROM project_publication_candidates", con)
pubs = pd.read_sql("SELECT publication_id, doi, title, year, RI, SCOPUS, WOS FROM publications", con)
proj = pd.read_sql("SELECT project_id, codigo_actividad, coordinator_original, year AS project_year FROM projects", con)
con.close()

pubs["doi_norm"] = pubs["doi"].map(norm_doi)
doi_to_pub = {d: pid for d, pid in zip(pubs["doi_norm"], pubs["publication_id"]) if d}

v1_pairs = set(zip(v1["project_id"].astype(int), v1["publication_id"].astype(int)))

# ── Build v2 direct matches via PROY_RESULTADOS ───────────────────────────────
res = pd.read_excel(INPUT, sheet_name="PROY_RESULTADOS")
res["doi_norm"] = res["DOI"].map(norm_doi)

# Join projects to get project_id via COD_AERI
proj_keys = pd.read_excel(INPUT, sheet_name="PROYECTOS")[["CÓDIGO DE PROYECTO", "COD_AERI", "Estado", "Año"]]
proj_keys = proj_keys[
    proj_keys["COD_AERI"].notna() &
    (proj_keys["COD_AERI"].astype(str).str.strip() != "-")
].copy()
proj_keys["year"] = pd.to_numeric(proj_keys["Año"], errors="coerce").astype("Int64")
proj_keys["status"] = proj_keys["Estado"].astype(str).str.strip()
closed_keys = proj_keys[
    (proj_keys["year"] >= 2010) & (proj_keys["status"] == "5. Cerrado")
]

# Rebuild COD_AERI → project_id by replicating run_pipeline.py's filter + row order
proj_full = pd.read_excel(INPUT, sheet_name="PROYECTOS")
proj_full["year"] = pd.to_numeric(proj_full["Año"], errors="coerce").astype("Int64")
proj_full["status"] = proj_full["Estado"].astype(str).str.strip()
closed_full = proj_full[
    (proj_full["year"] >= 2010) & (proj_full["status"] == "5. Cerrado")
].copy()
closed_full["project_id"] = range(1, len(closed_full) + 1)
cod_to_pid = {
    str(row["COD_AERI"]).strip(): int(row["project_id"])
    for _, row in closed_full.iterrows()
    if pd.notna(row["COD_AERI"]) and str(row["COD_AERI"]).strip() not in ("", "-")
}

# Direct DOI matches
v2_direct = []
for _, row in res.iterrows():
    cod = str(row["COD_AERI"]).strip() if pd.notna(row["COD_AERI"]) else ""
    doi = row["doi_norm"]
    if not cod or cod == "-" or not doi:
        continue
    pid = cod_to_pid.get(cod)
    pub_id = doi_to_pub.get(doi)
    if pid and pub_id:
        v2_direct.append((int(pid), int(pub_id), "DOI_direct"))

# Deduplicate
v2_direct_df = pd.DataFrame(v2_direct, columns=["project_id", "publication_id", "method"]).drop_duplicates(
    ["project_id", "publication_id"]
)
v2_pairs = set(zip(v2_direct_df["project_id"], v2_direct_df["publication_id"]))

# ── Coverage analysis ─────────────────────────────────────────────────────────
in_both      = v1_pairs & v2_pairs        # both methods find the same link
v2_only      = v2_pairs - v1_pairs        # direct link NOT found by v1 name matching
v1_only      = v1_pairs - v2_pairs        # v1 name match NOT confirmed by direct link

# Projects covered by PROY_RESULTADOS with at least one DOI match
proj_covered_v2 = v2_direct_df["project_id"].nunique()
proj_covered_v1 = v1["project_id"].nunique()

# Score distribution of v1-only (unconfirmed by direct) vs v1 overall
v1_only_scores = v1[v1.apply(lambda r: (int(r.project_id), int(r.publication_id)) in v1_only, axis=1)]["score"]

# PROY_RESULTADOS rows with DOI that couldn't be matched (DOI not in publications master)
res_with_doi = res[res["doi_norm"].str.len() > 0] if "doi_norm" in res.columns else pd.DataFrame()
res_doi_matched = res_with_doi[res_with_doi["doi_norm"].isin(doi_to_pub)]
res_doi_unmatched = res_with_doi[~res_with_doi["doi_norm"].isin(doi_to_pub)]

# ── Print summary ─────────────────────────────────────────────────────────────
sep = "─" * 60
print(sep)
print("  COMPARISON: v1 (name matching) vs v2 (PROY_RESULTADOS direct)")
print(sep)

print(f"\n{'V1 RESULTS':}")
print(f"  Total candidates          : {len(v1_pairs):>6}")
print(f"  Projects with ≥1 candidate: {proj_covered_v1:>6}")
print(f"  High confidence (≥85)     : {(v1.confidence=='Alta').sum():>6}")
print(f"  Medium confidence (65-84) : {(v1.confidence=='Media').sum():>6}")

print(f"\n{'V2 DIRECT (PROY_RESULTADOS + DOI)':}")
print(f"  Total direct links        : {len(v2_pairs):>6}")
print(f"  Projects with ≥1 direct   : {proj_covered_v2:>6}")

print(f"\n{'OVERLAP':}")
print(f"  Confirmed by both methods : {len(in_both):>6}  (v1 found these correctly)")
print(f"  Direct-only (new in v2)   : {len(v2_only):>6}  (v1 missed these — no author name match)")
print(f"  v1-only (unconfirmed)     : {len(v1_only):>6}  (v1 found but no direct DOI link exists)")

print(f"\n{'PROY_RESULTADOS DOI COVERAGE':}")
print(f"  PROY_RESULTADOS rows w/ DOI        : {len(res_with_doi):>6}")
print(f"  DOIs matched to publications master: {len(res_doi_matched):>6}")
print(f"  DOIs NOT in publications master    : {len(res_doi_unmatched):>6}  ← publications missing from Excel sheets")

print(f"\n{'WHAT V2 WOULD REPLACE / IMPROVE':}")
print(f"  Step replaced : coordinator exact-name loop → direct COD_AERI+DOI join")
print(f"  Still needed  : name-matching fallback for {len(v1_only)} v1-only pairs")
print(f"                  and for projects not in PROY_RESULTADOS")
gain_pct = 100 * len(v2_only) / max(len(v1_pairs), 1)
print(f"  Net gain      : +{len(v2_only)} new links ({gain_pct:.1f}% increase over v1)")
print(sep)

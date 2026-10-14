#!/usr/bin/env python3
"""Reconstruye los resultados declarados (06/07) para el maestro de proyectos vigente.

Los vínculos DECLARADOS proyecto <-> publicación salen de la hoja PROY_RESULTADOS
del Excel de PULSO: lo que cada proyecto reportó como producto, cruzado por
COD_AERI. Hasta 2026-10-13 esa tabla la armaba scripts/pipeline/01_build_pipeline.py
solo para los proyectos "5. Cerrado" de PULSO. Con el universo definido por CRIS
(scripts/addons/build_projects_from_cris.py) entran proyectos nuevos, y sus
resultados tienen que entrar también.

  - Las filas que ya estaban (mismo project_id + cod_prod) se conservan tal cual,
    con su enriquecimiento (OpenAlex, resúmenes por DOI).
  - Las nuevas se arman desde PROY_RESULTADOS, con el DOI cruzado contra el
    catálogo (03_publications_master.csv) como en 01_build_pipeline; las
    columnas de OpenAlex quedan vacías (el paso externo de
    rebuild_linked_publications.py recupera resúmenes verificados por título).
  - Se descartan las filas de proyectos que ya no están en el maestro.

Escribe 06_project_results_ground_truth.csv (todos los resultados) y
07_project_publication_ground_truth.csv (solo tipos publicación). Solo stdlib + openpyxl.

    python scripts/addons/build_declared_results.py
    python scripts/addons/build_declared_results.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "salidas"
XLSX = ROOT / "datos" / "informacion_proyecto_pulso.xlsx"

# Misma lista que scripts/pipeline/01_build_pipeline.py
PUBLICATION_RESULT_TYPES = {
    "Artículo indizado", "Artículo arbitrado", "Capítulo de libro arbitrado", "Capítulo de libro indizado",
    "Libro arbitrado", "Libro indizado", "Editor de libro",
    "Memoria en anales de congreso arbitrado", "Memoria en anales de congreso indizado",
}
# PROY_RESULTADOS -> columnas de la tabla 06 (renombre de 01_build_pipeline)
RENAME = {
    "tipo": "result_type", "cat_e": "result_category", "producto_e": "result_title", "otros_e": "result_other",
    "año_pub": "result_year", "equivalencia": "equivalencia", "DOI": "doi_raw", "issn": "issn_raw",
    "isbn": "isbn_raw", "estado": "result_status", "evidencia": "result_evidence", "eid": "scopus_eid",
    "journal": "journal_raw", "quartil": "quartile_raw", "citation": "citation_raw",
    "citation_fw": "citation_fw_raw", "citation_fa": "citation_fa_raw", "cit_policy": "citation_policy_raw",
    "conv": "call_name", "idperson": "result_idperson", "coordinador": "result_coordinator",
}


def read_csv(path: Path) -> list[dict]:
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    with path.open(encoding="utf-8-sig", newline="") as h:
        return list(csv.DictReader(h))


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    with path.open("w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def norm_doi(x) -> str:
    s = str(x or "").strip().lower()
    if s in {"", "-", "nan", "none", "sin doi"}:
        return ""
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", s).strip().rstrip(".")


def cell(v) -> str:
    """Como los valores que pandas dejó en la tabla anterior: 2014.0 -> 2014."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def norm_prod(v) -> str:
    text = cell(v)
    return str(int(text)) if text.isdigit() else text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--projects", type=Path, default=OUT / "01_projects_closed_con_cris.csv")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    projects = read_csv(args.projects)
    old06 = read_csv(OUT / "06_project_results_ground_truth.csv")
    fields = list(old06[0].keys())
    master = read_csv(OUT / "03_publications_master.csv")
    by_doi = {}
    for m in master:
        d = norm_doi(m.get("doi"))
        if d and d not in by_doi:
            by_doi[d] = m

    import openpyxl
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    it = wb["PROY_RESULTADOS"].iter_rows(values_only=True)
    header = next(it)
    results = {}
    for values in it:
        r = dict(zip(header, values))
        results.setdefault(cell(r.get("COD_AERI")), []).append(r)

    keep_pids = {p["project_id"] for p in projects}
    kept = {(r["project_id"], norm_prod(r["cod_prod"])): r for r in old06 if r["project_id"] in keep_pids}
    dropped_old = sum(1 for r in old06 if r["project_id"] not in keep_pids)

    rows, added, stats = [], 0, Counter()
    for p in projects:
        aeri = (p.get("cod_aeri") or "").strip()
        if not aeri or aeri == "-":
            continue
        for r in results.get(aeri, []):
            key = (p["project_id"], norm_prod(r.get("cod_prod")))
            if key in kept:
                rows.append(kept.pop(key)); continue
            row = {f: "" for f in fields}
            row.update({"project_id": p["project_id"], "cod_aeri": aeri, "codigo_campus": p.get("codigo_campus", ""),
                        "project_year": p.get("year", ""), "project_title": p.get("title", ""),
                        "coordinator_original": p.get("coordinator_original", ""), "cod_prod": key[1]})
            for src, dst in RENAME.items():
                row[dst] = cell(r.get(src))
            row["doi_norm"] = norm_doi(r.get("DOI"))
            hit = by_doi.get(row["doi_norm"]) if row["doi_norm"] else None
            if hit:
                row.update({"publication_id": hit["publication_id"], "match_method": "doi",
                            "source_abstract": hit.get("abstract", ""), "source_keywords": hit.get("keywords", "")})
            rows.append(row); added += 1
            stats["nuevas tipo publicación" if row["result_type"] in PUBLICATION_RESULT_TYPES else "nuevas otro tipo"] += 1
            if hit and row["result_type"] in PUBLICATION_RESULT_TYPES:
                stats["nuevas tipo publicación con DOI en el catálogo"] += 1
    # Filas viejas que ya no salen de PROY_RESULTADOS (no deberia pasar): se conservan.
    rows.extend(kept.values())
    rows.sort(key=lambda r: (int(r["project_id"]), int(r["cod_prod"]) if str(r["cod_prod"]).isdigit() else 0))
    pubs = [dict(r, result_is_publication_like="True") for r in rows if r["result_type"] in PUBLICATION_RESULT_TYPES]

    print(f"Proyectos en el maestro: {len(projects)} (con COD_AERI: "
          f"{sum(1 for p in projects if (p.get('cod_aeri') or '').strip() not in ('', '-'))})")
    print(f"06 resultados declarados: {len(old06)} -> {len(rows)} (nuevos {added}; descartados por proyecto fuera: {dropped_old})")
    print(f"07 publicaciones declaradas: {len(pubs)} de {len({r['project_id'] for r in pubs})} proyectos")
    for k, v in stats.items():
        print(f"   {k}: {v}")
    if args.dry_run:
        print("--dry-run: no se escribe nada."); return
    write_csv(OUT / "06_project_results_ground_truth.csv", rows, fields)
    old07 = read_csv(OUT / "07_project_publication_ground_truth.csv")
    write_csv(OUT / "07_project_publication_ground_truth.csv", pubs, list(old07[0].keys()))
    print("-> salidas/06_project_results_ground_truth.csv, salidas/07_project_publication_ground_truth.csv")


if __name__ == "__main__":
    main()

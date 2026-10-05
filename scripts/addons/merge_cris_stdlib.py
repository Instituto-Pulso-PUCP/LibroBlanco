#!/usr/bin/env python3
"""Enriquece el maestro de proyectos con un nuevo export de CRIS, sin pandas.

Puerto a stdlib de `merge_cris.py` (que necesita pandas, no instalado en este
servidor). Misma estrategia de match, en el mismo orden de prioridad:

  1. Codigo interno: `oairecerif.internalid` de CRIS vs `codigo_actividad` o
     `codigo_campus` del proyecto.
  2. Titulo normalizado exacto.
  3. Titulo normalizado difuso (Jaccard de tokens >= --fuzzy-threshold,
     0.65 por defecto) -- solo si no es ambiguo.

Diferencias deliberadas frente al original:
  - No agrega filas nuevas automaticamente (proyectos CRIS que no matchean
    con ningun proyecto existente pero parecen cerrados/2010+): se listan en
    el reporte para decidir aparte, porque agregar filas cambia el tamano del
    universo, no solo lo enriquece.
  - Si una fila del export nuevo no matchea nada, pero el proyecto YA tenia
    cris_abstract/cris_keywords/etc. de una corrida anterior, esos valores se
    conservan en vez de borrarse -- nunca se pierde dato que ya se tenia.
  - No genera el XLSX coloreado (needs pandas/openpyxl con estilos); solo el
    CSV enriquecido y los reportes.

Uso:
    python scripts/addons/merge_cris_stdlib.py
    python scripts/addons/merge_cris_stdlib.py --cris datos/ProyectosPUCPCRIS-20260929.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "salidas"
DATOS = ROOT / "datos"
XLSX_INPUT = DATOS / "informacion_proyecto_pulso.xlsx"

_EMPTY_CODES = {"", "NO APLICA", "-", "NAN", "NONE"}
_URI_FRAGMENT_RE = re.compile(r".*[#/]")

CRIS_COLUMN_MAP = {
    "id": "cris_uuid",
    "oairecerif.internalid": "internalid",
    "dc.title": "cris_title",
    "dc.description.abstract": "cris_abstract",
    "dc.subject": "cris_keywords",
    "perucris.subject.ocde": "cris_ocde_subject",
    "datacite.subject.fos": "cris_fos",
    "perucris.project.typeOcde": "cris_type_ocde_raw",
    "oairecerif.project.status": "cris_status_raw",
    "oairecerif.project.startDate": "cris_start_date",
    "oairecerif.project.endDate": "cris_end_date",
    "crispj.coordinator": "cris_coordinator",
    "crispj.coinvestigators": "cris_coinvestigators",
    "crispj.coinvestigators.role": "cris_coinvestigator_roles",
}
CRIS_ENRICH_COLS = [
    "internalid", "cris_abstract", "cris_keywords", "cris_ocde_subject", "cris_fos",
    "cris_type_ocde", "cris_status", "cris_start_date", "cris_end_date",
    "cris_coordinator", "cris_coinvestigators", "cris_coinvestigator_roles",
    "cris_coinvestigator_count_mismatch",
]


def norm_text(x) -> str:
    if x is None:
        return ""
    s = str(x).strip().upper()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_code(x) -> str:
    if x is None:
        return ""
    s = str(x).strip().upper().replace(".", "-")
    return "" if s in _EMPTY_CODES else s


def clean_uri_fragment(x) -> str:
    if x is None:
        return ""
    parts = [p.strip() for p in str(x).split("||") if p.strip()]
    return "||".join(_URI_FRAGMENT_RE.sub("", p) for p in parts)


def title_tokens(t: str) -> set:
    return {w for w in t.split() if len(w) > 3}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_default_cris_csv() -> Path | None:
    candidates = sorted(DATOS.glob("ProyectosPUCPCRIS*.csv"))
    return candidates[-1] if candidates else None


def read_csv(path: Path) -> list[dict]:
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_cris(path: Path) -> list[dict]:
    raw = read_csv(path)
    rows = []
    for r in raw:
        row = {}
        for src, dst in CRIS_COLUMN_MAP.items():
            row[dst] = (r.get(src) or "").strip()
        row["code"] = norm_code(row["internalid"])
        row["t"] = norm_text(row["cris_title"])
        row["cris_status"] = clean_uri_fragment(row.pop("cris_status_raw", ""))
        row["cris_type_ocde"] = clean_uri_fragment(row.pop("cris_type_ocde_raw", ""))
        row["cris_coinvestigator_roles"] = clean_uri_fragment(row["cris_coinvestigator_roles"])
        names = [p for p in row["cris_coinvestigators"].split("||") if p.strip()]
        roles = [p for p in row["cris_coinvestigator_roles"].split("||") if p.strip()]
        row["cris_coinvestigator_count_mismatch"] = (
            len(names) != len(roles) and (names or roles))
        rows.append(row)

    # Duplicados: misma (titulo, fecha inicio) bajo dos codigos internos
    # distintos. Se queda la fila mas completa.
    def completeness(r):
        return sum(1 for c in ("cris_abstract", "cris_keywords", "cris_coinvestigators") if r[c])

    by_key: dict[tuple, dict] = {}
    for r in rows:
        key = (r["t"], r["cris_start_date"])
        if key not in by_key or completeness(r) > completeness(by_key[key]):
            by_key[key] = r
    deduped = list(by_key.values())
    if len(deduped) != len(rows):
        print(f"  {len(rows) - len(deduped)} filas CRIS descartadas por duplicar titulo+fecha.")
    return deduped


def load_full_project_index(xlsx_path: Path) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb["PROYECTOS"]
    headers = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
    idx = {h: i for i, h in enumerate(headers)}
    codes, titles, title_toks = set(), set(), []
    for row in ws.iter_rows(min_row=2, values_only=True):
        for col in ("CÓDIGO DE PROYECTO", "CÓDIGO CAMPUS"):
            c = norm_code(row[idx[col]]) if col in idx else ""
            if c:
                codes.add(c)
        t = norm_text(row[idx["Título"]]) if "Título" in idx else ""
        if t and t not in titles:
            titles.add(t)
            title_toks.append(title_tokens(t))
    return {"codes": codes, "titles": titles, "title_tokens_list": title_toks}


def exists_in_full_xlsx(cris_row, full_index, fuzzy_threshold) -> bool:
    if cris_row["code"] and cris_row["code"] in full_index["codes"]:
        return True
    if cris_row["t"] and cris_row["t"] in full_index["titles"]:
        return True
    if cris_row["t"]:
        toks = title_tokens(cris_row["t"])
        best = max((jaccard(toks, m) for m in full_index["title_tokens_list"]), default=0.0)
        if best >= fuzzy_threshold:
            return True
    return False


def match_and_merge(main: list[dict], cris: list[dict], full_index, fuzzy_threshold, new_row_min_score):
    code_to_pid: dict[str, list[str]] = {}
    title_to_pid: dict[str, list[str]] = {}
    main_titles = []
    for r in main:
        pid = r["project_id"]
        for code in (norm_code(r.get("codigo_actividad")), norm_code(r.get("codigo_campus"))):
            if code:
                code_to_pid.setdefault(code, []).append(pid)
        t = r.get("title_norm", "")
        if t:
            title_to_pid.setdefault(t, []).append(pid)
            main_titles.append((pid, title_tokens(t)))

    match_of_pid: dict[str, dict] = {}
    method_of_pid: dict[str, str] = {}
    stats = {"code": 0, "title_exact": 0, "title_fuzzy": 0,
             "ambiguous_code": 0, "ambiguous_title": 0}
    new_candidates, report_rows = [], []

    for cr in cris:
        target_pid, method = None, None
        if cr["code"] and cr["code"] in code_to_pid:
            pids = code_to_pid[cr["code"]]
            if len(pids) == 1:
                target_pid, method = pids[0], "code"
            else:
                stats["ambiguous_code"] += 1
                report_rows.append(report_row(cr, "ambiguous_code_match", best_pid=",".join(pids)))
                continue
        elif cr["t"] and cr["t"] in title_to_pid:
            pids = title_to_pid[cr["t"]]
            if len(pids) == 1:
                target_pid, method = pids[0], "title_exact"
            else:
                stats["ambiguous_title"] += 1
                report_rows.append(report_row(cr, "ambiguous_title_match", best_pid=",".join(pids)))
                continue
        elif cr["t"]:
            toks = title_tokens(cr["t"])
            best_pid, best_score = None, 0.0
            for pid, mtoks in main_titles:
                score = jaccard(toks, mtoks)
                if score > best_score:
                    best_pid, best_score = pid, score
            if best_score >= fuzzy_threshold:
                target_pid, method = best_pid, "title_fuzzy"
            elif best_score >= new_row_min_score:
                report_rows.append(report_row(cr, "ambiguous_title_fuzzy", best_score=best_score, best_pid=best_pid))
                continue
            elif exists_in_full_xlsx(cr, full_index, fuzzy_threshold):
                report_rows.append(report_row(cr, "exists_in_xlsx_but_not_closed"))
                continue
            else:
                new_candidates.append(cr)
                continue
        else:
            if exists_in_full_xlsx(cr, full_index, fuzzy_threshold):
                report_rows.append(report_row(cr, "exists_in_xlsx_but_not_closed"))
                continue
            new_candidates.append(cr)
            continue

        if target_pid in match_of_pid:
            prev = match_of_pid[target_pid]
            prev_score = sum(1 for c in ("cris_abstract", "cris_keywords") if prev.get(c))
            new_score = sum(1 for c in ("cris_abstract", "cris_keywords") if cr.get(c))
            if new_score <= prev_score:
                continue
        match_of_pid[target_pid] = cr
        method_of_pid[target_pid] = method

    for m in ("code", "title_exact", "title_fuzzy"):
        stats[m] = sum(1 for v in method_of_pid.values() if v == m)

    merged = []
    preserved = 0
    for r in main:
        row = dict(r)
        pid = r["project_id"]
        cr = match_of_pid.get(pid)
        if cr:
            for col in CRIS_ENRICH_COLS:
                row[col] = cr.get(col, "")
            row["cris_match_method"] = method_of_pid[pid]
        else:
            # Sin match en esta corrida: conservar lo que ya hubiera de una
            # corrida anterior, en vez de borrarlo.
            had_before = any(row.get(c) for c in ("cris_abstract", "cris_keywords"))
            if had_before:
                preserved += 1
            # (no se toca row: ya trae sus valores previos de `main`)
        merged.append(row)

    return merged, stats, new_candidates, report_rows, preserved


def report_row(cr, reason, best_score=None, best_pid=None):
    return {
        "cris_uuid": cr.get("cris_uuid", ""), "cris_internalid": cr.get("internalid", ""),
        "cris_title": cr.get("cris_title", ""), "cris_start_date": cr.get("cris_start_date", ""),
        "cris_status": cr.get("cris_status", ""), "reason": reason,
        "best_match_project_id": best_pid or "",
        "best_match_score": round(best_score, 3) if best_score is not None else "",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--main", type=Path, default=OUT / "01_projects_closed_con_cris.csv",
                        help="Maestro a enriquecer (por defecto, el que ya usa el pipeline).")
    parser.add_argument("--cris", type=Path, default=None,
                        help="Export CRIS nuevo (por defecto, el mas reciente en datos/).")
    parser.add_argument("--xlsx", type=Path, default=XLSX_INPUT)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--fuzzy-threshold", type=float, default=0.65)
    parser.add_argument("--new-row-min-score", type=float, default=0.35)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    cris_path = args.cris or find_default_cris_csv()
    if not cris_path or not Path(cris_path).exists():
        parser.error("No se encontro un export de CRIS en datos/.")
    output = args.output or args.main

    print(f"Maestro: {args.main}")
    print(f"CRIS nuevo: {cris_path}")

    main_rows = read_csv(args.main)
    cris_rows = load_cris(Path(cris_path))
    full_index = load_full_project_index(args.xlsx)

    merged, stats, new_candidates, report_rows, preserved = match_and_merge(
        main_rows, cris_rows, full_index, args.fuzzy_threshold, args.new_row_min_score)

    before_abs = sum(1 for r in main_rows if r.get("cris_abstract"))
    after_abs = sum(1 for r in merged if r.get("cris_abstract"))
    before_kw = sum(1 for r in main_rows if r.get("cris_keywords"))
    after_kw = sum(1 for r in merged if r.get("cris_keywords"))

    print(f"- {len(merged)} proyectos  ({stats['code']} por código, {stats['title_exact']} por "
          f"título exacto, {stats['title_fuzzy']} por título difuso)")
    print(f"- {stats['ambiguous_code']} código ambiguo, {stats['ambiguous_title']} título ambiguo "
          f"({len(report_rows)} filas CRIS sin resolver -> reporte)")
    print(f"- {len(new_candidates)} filas CRIS sin match que parecen proyecto nuevo (NO se agregan; "
          "revisar aparte)")
    print(f"- {preserved} proyectos sin match esta vez pero con dato previo, conservado")
    print(f"- cris_abstract: {before_abs} -> {after_abs} de {len(merged)} "
          f"({after_abs/len(merged)*100:.1f}%)")
    print(f"- cris_keywords: {before_kw} -> {after_kw} de {len(merged)} "
          f"({after_kw/len(merged)*100:.1f}%)")

    if args.dry_run:
        print("\n--dry-run: no se escribe nada.")
        return

    fieldnames = list(merged[0].keys()) if merged else list(main_rows[0].keys())
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)
    print(f"\n-> {output}")

    if report_rows:
        report_path = output.with_name(output.stem + "_cris_review.csv")
        with report_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(report_rows[0].keys()))
            writer.writeheader()
            writer.writerows(report_rows)
        print(f"-> {report_path} ({len(report_rows)} filas ambiguas para revisar)")

    if new_candidates:
        new_path = output.with_name(output.stem + "_cris_new_candidates.json")
        new_path.write_text(json.dumps(
            [{"cris_title": r["cris_title"], "cris_start_date": r["cris_start_date"],
              "cris_status": r["cris_status"], "internalid": r["internalid"]}
             for r in new_candidates], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"-> {new_path} ({len(new_candidates)} proyectos CRIS sin match, no agregados)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Arma el maestro de proyectos a partir de las filas de Proyectos CRIS.

Decision del equipo (2026-10-13): el universo de proyectos lo definen las filas
del export CRIS, no la hoja PROYECTOS de PULSO. Antes era al reves: se partia de
PULSO (estado "5. Cerrado", año >= 2010) y CRIS solo enriquecia. Con eso
quedaban fuera ~480 proyectos que CRIS ya da por concluidos pero PULSO aun tiene
"en proceso de cierre", "concluido" o "en ejecucion", y los 43 que solo estan en
CRIS.

Universo:
  - estado CRIS = concluido;
  - año de inicio >= 2010. Año de inicio = el de CRIS; si CRIS no lo tiene, el
    año de PULSO del proyecto; si tampoco, el año de fin de CRIS.
El minimo de calidad (titulo + resumen) se sigue aplicando despues, en
lb_domains.filter_min_requirements().

De PULSO se conservan las columnas que CRIS no tiene (codigo AERI, unidad
ejecutora, area, lineas, financiamiento...), que hacen falta para los vinculos
declarados (PROY_RESULTADOS se cruza por COD_AERI) y como metadato del atlas.

Identificadores estables: un proyecto que ya estaba en el maestro conserva su
project_id (se reconoce por cris_uuid o, si el maestro no lo tenia, con el mismo
emparejamiento de merge_cris_stdlib.py); los nuevos reciben ids a continuacion
del mayor existente. Correr el script sobre su propia salida no cambia ningun id.

    python scripts/addons/build_projects_from_cris.py              # escribe el maestro
    python scripts/addons/build_projects_from_cris.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import merge_cris_stdlib as mc  # noqa: E402

OUT = ROOT / "salidas"
YEAR_START = 2010

# Columnas de la hoja PROYECTOS -> columnas del maestro (las mismas que usa
# scripts/pipeline/01_build_pipeline.py).
PULSO_COLS = {
    "CÓDIGO DE PROYECTO": "codigo_actividad", "COD_AERI": "cod_aeri", "CÓDIGO CAMPUS": "codigo_campus",
    "Título": "title", "Estado": "status", "Tipo de Proyecto": "project_type",
    "Área de Conocimiento": "knowledge_area", "Linea de Investigación 1": "research_line_1",
    "Linea de Investigación 2": "research_line_2", "Linea de Investigación 3": "research_line_3",
    "Linea de Investigación 4": "research_line_4", "LÍNEA DE INVESTIGACIÓN HOMOLOGADA": "research_line",
    "UNIDAD EJECUTORA": "executing_unit", "SECCIÓN EJECUTORA": "executing_section",
    "COORDINADOR DE LA INVESTIGACIÓN": "coordinator_original", "UNIDAD DE GESTIÓN": "management_unit",
    "Tipo de Financiamiento": "funding_type", "Entidad Financiadora": "funder",
}


def year(value) -> int | None:
    text = str(value or "").strip()[:4]
    return int(text) if text.isdigit() else None


def load_pulso(xlsx: Path) -> tuple[dict, dict]:
    """Filas de PROYECTOS por codigo (actividad o campus) y por titulo normalizado unico."""
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    it = wb["PROYECTOS"].iter_rows(values_only=True)
    header = next(it)
    by_code, by_title, dup_title = {}, {}, set()
    for values in it:
        row = {h: ("" if v is None else str(v).strip()) for h, v in zip(header, values)}
        for col in ("CÓDIGO DE PROYECTO", "CÓDIGO CAMPUS"):
            code = mc.norm_code(row.get(col))
            if code:
                by_code.setdefault(code, row)
        t = mc.norm_text(row.get("Título"))
        if t:
            if t in by_title:
                dup_title.add(t)
            by_title[t] = row
    for t in dup_title:
        by_title.pop(t, None)   # titulo repetido en PULSO: no se puede decidir solo
    return by_code, by_title


def existing_by_uuid(main_rows, cris_rows, xlsx, overrides_path) -> dict[str, dict]:
    """cris_uuid -> fila del maestro actual (con sus columnas PULSO y project_id)."""
    out = {}
    pending = []
    for r in main_rows:
        if (r.get("cris_uuid") or "").strip():
            out.setdefault(r["cris_uuid"].strip(), r)
        else:
            pending.append(r)
    if not pending:
        return out
    # Maestro anterior sin cris_uuid: mismo emparejamiento que merge_cris_stdlib.
    cols = list(mc.CRIS_ENRICH_COLS)
    if "cris_uuid" not in cols:
        mc.CRIS_ENRICH_COLS = cols + ["cris_uuid"]
    remaining, manual, _ = mc.apply_overrides(
        cris_rows, mc.load_overrides(overrides_path), {r["project_id"] for r in pending})
    merged, stats, *_ = mc.match_and_merge(pending, remaining, mc.load_full_project_index(xlsx), 0.65, 0.35)
    by_pid = {r["project_id"]: r for r in merged}
    for cr, pid in manual:
        if pid not in stats["matched_pids"]:
            by_pid[pid]["cris_uuid"] = cr["cris_uuid"]
    for r in merged:
        u = (r.get("cris_uuid") or "").strip()
        if u and r["project_id"] in stats["matched_pids"] | {pid for _, pid in manual}:
            out.setdefault(u, r)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cris", type=Path, default=None, help="Export de Proyectos CRIS (por defecto el más reciente en datos/).")
    ap.add_argument("--main", type=Path, default=OUT / "01_projects_closed_con_cris.csv",
                    help="Maestro actual: de él se conservan los project_id y las columnas de PULSO.")
    ap.add_argument("--xlsx", type=Path, default=mc.XLSX_INPUT)
    ap.add_argument("--overrides", type=Path, default=mc.DATOS / "cris_overrides.csv")
    ap.add_argument("--output", type=Path, default=None, help="Por defecto, sobrescribe --main.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    cris_path = args.cris or mc.find_default_cris_csv()
    output = args.output or args.main
    print(f"CRIS: {cris_path}\nMaestro actual: {args.main}")
    cris_rows = mc.load_cris(Path(cris_path))
    main_rows = mc.read_csv(args.main)
    prev = existing_by_uuid(main_rows, cris_rows, args.xlsx, args.overrides)
    by_code, by_title = load_pulso(args.xlsx)

    fields = list(main_rows[0].keys())
    for extra in ("cris_uuid", "pulso_match"):
        if extra not in fields:
            fields.append(extra)
    next_id = max(int(r["project_id"]) for r in main_rows) + 1

    out, origin, excluded = [], Counter(), Counter()
    claimed = set()
    for cr in sorted(cris_rows, key=lambda r: (r["cris_start_date"], r["cris_uuid"])):
        uuid = cr["cris_uuid"]
        old = prev.get(uuid)
        # PULSO se busca siempre: aunque el proyecto ya esté en el maestro, su
        # fila vieja puede no tener año (p.ej. una fila que vino solo de CRIS).
        pulso = by_code.get(cr["code"]) if cr["code"] else None
        how = "code" if pulso else ""
        if not pulso and cr["t"] in by_title:
            pulso, how = by_title[cr["t"]], "title_exact"
        start = (year(cr["cris_start_date"]) or (year(old.get("year")) if old else None)
                 or (year(pulso.get("Año")) if pulso else None) or year(cr["cris_end_date"]))
        if cr["cris_status"] != "concluido":
            excluded[f"estado CRIS: {cr['cris_status'] or 'vacío'}"] += 1
            continue
        if not start or start < YEAR_START:
            excluded["inicio antes de 2010 o sin año"] += 1
            continue
        if old:
            row = dict(old)
            row.setdefault("pulso_match", "")
            row["pulso_match"] = row["pulso_match"] or "maestro anterior"
            if not year(row.get("year")):
                row["year"] = str(start)
            origin["ya estaba en el maestro"] += 1
            claimed.add(old["project_id"])
        else:
            row = {f: "" for f in fields}
            row["project_id"] = str(next_id); next_id += 1
            if pulso:
                for src, dst in PULSO_COLS.items():
                    row[dst] = pulso.get(src, "")
                row["year"] = str(year(pulso.get("Año")) or start)
                row["source"] = "VRI+CRIS"
                row["pulso_match"] = how
                origin[f"nuevo, en PULSO ({pulso.get('Estado') or 'sin estado'})"] += 1
            else:
                row["title"] = cr["cris_title"]
                row["year"] = str(start)
                row["coordinator_original"] = cr["cris_coordinator"]
                row["source"] = "CRIS"
                origin["nuevo, solo en CRIS"] += 1
            row["title_norm"] = mc.norm_text(row["title"])
            row["coordinator_norm"] = mc.norm_text(row["coordinator_original"])
            row["cris_match_method"] = "cris_base"
        for col in mc.CRIS_ENRICH_COLS + ["cris_uuid"]:
            row[col] = cr.get(col, "")
        out.append(row)

    dropped = [r for r in main_rows if r["project_id"] not in claimed]
    print(f"\nUniverso CRIS (concluido, inicio >= {YEAR_START}): {len(out)} proyectos")
    for k, v in origin.most_common():
        print(f"  {v:5d}  {k}")
    print("Filas CRIS fuera del universo:")
    for k, v in excluded.most_common():
        print(f"  {v:5d}  {k}")
    with_text = sum(1 for r in out if r.get("title") and r.get("cris_abstract"))
    print(f"Con título y resumen CRIS (mínimo del atlas): {with_text}")
    print(f"Proyectos del maestro anterior que quedan fuera: {len(dropped)} "
          f"(con resumen: {sum(1 for r in dropped if r.get('cris_abstract'))})")
    if args.dry_run:
        print("\n--dry-run: no se escribe nada.")
        return
    out.sort(key=lambda r: int(r["project_id"]))
    with output.open("w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(out)
    print(f"\n-> {output}")
    if dropped:
        rep = output.with_name(output.stem + "_fuera_de_cris.csv")
        with rep.open("w", encoding="utf-8-sig", newline="") as h:
            w = csv.DictWriter(h, fieldnames=["project_id", "title", "year", "status", "cris_uuid", "cris_status"],
                               extrasaction="ignore")
            w.writeheader(); w.writerows(dropped)
        print(f"-> {rep} (proyectos del maestro anterior que no entran)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Adaptador ECOTEC: datos/ecotec/*.xlsx -> CSV estandar en salidas/datasets/ecotec/.

Cada dataset nuevo tiene su adaptador; lo que sale de aqui es el formato comun
que consume el resto del pipeline:

  projects.csv      project_id, title, abstract, keywords, year, start_date,
                    end_date, research_line, amount
  publications.csv  publication_id, title, abstract, keywords, doi, year,
                    journal, abstract_source, openalex_keywords
                    (`keywords` es solo de autor; ECOTEC no las trae. Las de
                    OpenAlex las genera OpenAlex, a veces equivocadas -- "travel
                    permits" en un articulo de learning analytics --, y van
                    aparte para que nunca entren al embedding)
  links.csv         project_id, publication_id, link_type
  policies.csv      policy_id, label, text, l1_id, l1_label, l2_id, l2_label
                    (+ columnas propias del plan). Una fila por hoja de la
                    taxonomia nacional; `text` es lo que se embebe.

No filtra nada: el universo lo decide quien entrega los datos. Solo descarta
filas vacias. Los ids salen del titulo normalizado (no del orden de la hoja),
asi que se mantienen si el Excel se reordena o crece.

Los articulos llegan solo con titulo. Sus abstracts se buscan aparte y se
integran al volver a correr este script:

    python scripts/datasets/ecotec.py
    python scripts/addons/recover_abstracts_external.py \
        --publications salidas/datasets/ecotec/publications.csv \
        --out salidas/datasets/ecotec/abstracts_recuperados/busqueda.jsonl
    python scripts/addons/build_external_candidates.py \
        --busqueda salidas/datasets/ecotec/abstracts_recuperados/busqueda.jsonl \
        --out salidas/datasets/ecotec/abstracts_recuperados/candidatos.csv
    python scripts/addons/enrich_publications_metadata.py \
        --publications salidas/datasets/ecotec/publications.csv \
        --out-dir salidas/datasets/ecotec/abstracts_recuperados
    python scripts/addons/build_external_candidates.py \
        --busqueda salidas/datasets/ecotec/abstracts_recuperados/busqueda_landing.jsonl \
        --out salidas/datasets/ecotec/abstracts_recuperados/candidatos.csv
    # revisar a mano las filas "revisar" -> aceptar / rechazar
    python scripts/datasets/ecotec.py     # integra "aceptar" y los metadatos
"""
from __future__ import annotations

import csv
import hashlib
import sys
from collections import Counter
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import lb_titles  # noqa: E402

SRC = ROOT / "datos" / "ecotec"
PROJECTS_XLSX = SRC / "DATASET 1- Registro de Proyectos.xlsx"
LINKS_XLSX = SRC / "DATASET 2- Proyectos - Artículos.xlsx"
PND_XLSX = SRC / "anexoPND25-29.xlsx"
PND_HEADER_ROW = 3  # las dos primeras filas son el titulo de la Secretaria
OUT = ROOT / "salidas" / "datasets" / "ecotec"
CANDIDATES = OUT / "abstracts_recuperados" / "candidatos.csv"

PROJECT_FIELDS = ["project_id", "title", "abstract", "keywords", "year", "start_date",
                  "end_date", "research_line", "amount"]
PUBLICATION_FIELDS = ["publication_id", "title", "abstract", "keywords", "doi", "year",
                      "journal", "abstract_source", "openalex_keywords"]
METADATA = OUT / "abstracts_recuperados" / "metadatos.csv"
LINK_FIELDS = ["project_id", "publication_id", "link_type"]
POLICY_FIELDS = ["policy_id", "label", "text", "l1_id", "l1_label", "l2_id", "l2_label",
                 "metas", "ods", "etn_lineamientos"]


def clean(v) -> str:
    return " ".join(str(v).split()) if v is not None else ""


def make_id(prefix: str, title: str) -> str:
    return f"{prefix}-{hashlib.sha1(lb_titles.norm_title(title).encode()).hexdigest()[:10]}"


def read_sheet(path: Path, header_row: int = 1) -> list[dict]:
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
    rows = ws.iter_rows(min_row=header_row, values_only=True)
    header = [clean(h) for h in next(rows)]
    return [dict(zip(header, r)) for r in rows if any(clean(c) for c in r)]


def load_policies() -> list[dict]:
    """PND 2025-2029: Eje -> Objetivo -> Politica (hoja) -> Meta. La hoja de la
    taxonomia es la Politica (46); las metas son cifras ("reducir la tasa de X
    a Y% en 2029") y no se parecen al texto de un proyecto, asi que solo
    enriquecen el texto de su politica, junto con el indicador y el
    lineamiento ETN. El id es el numero de la politica: "2.6" aparece con dos
    redacciones casi iguales y es la misma."""
    by_id: dict[str, dict] = {}
    for r in read_sheet(PND_XLSX, PND_HEADER_ROW):
        politica = clean(r["Política"])
        if not politica:
            continue  # nota al pie "* Metas de la ETN..."
        number = politica.split()[0]
        objetivo = clean(r["Objetivo"]).replace("⁠", "")  # "4.⁠ Impulsar..."
        node = by_id.setdefault(number, {
            "policy_id": f"pnd-{number}", "label": politica,
            "l1_id": clean(r["Eje"]), "l1_label": clean(r["Eje"]),
            "l2_id": objetivo.split(".")[0].strip(), "l2_label": objetivo,
            "metas": [], "indicadores": [], "ods": [], "etn_lineamientos": []})
        for key, col in (("metas", "Meta"), ("indicadores", "Indicador"),
                         ("ods", "OBEJTIVO ODS"), ("etn_lineamientos", "Lineamientos ETN")):
            value = clean(r.get(col))
            if value and value not in node[key]:
                node[key].append(value)
    out = []
    for node in by_id.values():
        text = ". ".join(p.rstrip(". ") for p in [node["label"], node["l2_label"],
                                                  *node["indicadores"], *node["etn_lineamientos"]])
        out.append({**{k: node[k] for k in POLICY_FIELDS if k in node and not isinstance(node[k], list)},
                    "text": text, "metas": " | ".join(node["metas"]),
                    "ods": " | ".join(node["ods"]),
                    "etn_lineamientos": " | ".join(node["etn_lineamientos"])})
    return out


def load_projects() -> list[dict]:
    out = []
    for r in read_sheet(PROJECTS_XLSX):
        title = clean(r["Título"])
        start = r["Fecha de inicio"]
        out.append({
            "project_id": make_id("ecotec-proj", title), "title": title,
            "abstract": clean(r["Descripción"]), "keywords": clean(r["Palabras clave"]),
            "year": str(start)[:4] if start else "",
            "start_date": str(start)[:10] if start else "",
            "end_date": str(r["Fecha de finalización"])[:10] if r["Fecha de finalización"] else "",
            "research_line": clean(r["Líneas de Investigación"]),
            "amount": clean(r["Cantidad concedida"]),
        })
    return out


def resolve_project(name: str, projects: list[dict]) -> dict | None:
    """Nombre de proyecto en la hoja de articulos -> fila de projects. Exacto
    por titulo normalizado; si no, el de mayor lb_titles.title_match sobre el
    umbral (un nombre trae un caracter matematico de mas: 'E.coli𝘪')."""
    norm = lb_titles.norm_title(name)
    for p in projects:
        if lb_titles.norm_title(p["title"]) == norm:
            return p
    best = max(projects, key=lambda p: lb_titles.title_match(name, p["title"]))
    return best if lb_titles.same_work(name, best["title"]) else None


def load_accepted_abstracts() -> dict[str, dict]:
    if not CANDIDATES.exists():
        return {}
    with CANDIDATES.open(encoding="utf-8-sig", newline="") as h:
        return {r["publication_id"]: r for r in csv.DictReader(h)
                if r["veredicto"].strip() == "aceptar" and r["abstract"].strip()}


def load_metadata() -> dict[str, dict]:
    """doi/year/journal/keywords de enrich_publications_metadata.py (OpenAlex)."""
    if not METADATA.exists():
        return {}
    with METADATA.open(encoding="utf-8-sig", newline="") as h:
        return {r["publication_id"]: r for r in csv.DictReader(h)}


def main():
    projects = load_projects()
    accepted = load_accepted_abstracts()
    metadata = load_metadata()
    policies = load_policies()

    # La hoja de articulos usa celdas combinadas: el nombre del proyecto solo
    # va en la primera fila de su bloque.
    links, pubs, unresolved, current = [], {}, [], None
    for r in read_sheet(LINKS_XLSX):
        if clean(r["Proyectos"]):
            current = clean(r["Proyectos"])
        title = clean(r["Título"])
        if not title:
            continue
        project = resolve_project(current, projects)
        if project is None:
            unresolved.append(current)
            continue
        pid = make_id("ecotec-pub", title)
        if pid not in pubs:
            hit, meta = accepted.get(pid, {}), metadata.get(pid, {})
            pubs[pid] = {"publication_id": pid, "title": title,
                         "abstract": hit.get("abstract", ""), "keywords": "",
                         "doi": meta.get("doi", ""), "year": meta.get("year", ""),
                         "journal": meta.get("journal", ""),
                         "abstract_source": hit.get("fuente", ""),
                         "openalex_keywords": meta.get("keywords", "")}
        link = {"project_id": project["project_id"], "publication_id": pid,
                "link_type": "declarado"}
        if link not in links:
            links.append(link)

    OUT.mkdir(parents=True, exist_ok=True)
    for name, fields, rows in (("projects.csv", PROJECT_FIELDS, projects),
                               ("publications.csv", PUBLICATION_FIELDS, list(pubs.values())),
                               ("links.csv", LINK_FIELDS, links),
                               ("policies.csv", POLICY_FIELDS, policies)):
        with (OUT / name).open("w", encoding="utf-8-sig", newline="") as h:
            w = csv.DictWriter(h, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    linked_projects = Counter(l["project_id"] for l in links)
    with_abstract = sum(1 for p in pubs.values() if p["abstract"])
    print(f"proyectos: {len(projects)} ({len(linked_projects)} con al menos un articulo)")
    print(f"publicaciones: {len(pubs)} distintas, {with_abstract} con abstract")
    print(f"vinculos: {len(links)}")
    print(f"politicas PND: {len(policies)} en {len({p['l2_id'] for p in policies})} objetivos")
    if unresolved:
        print(f"AVISO: {len(unresolved)} filas con proyecto sin resolver: {sorted(set(unresolved))}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()

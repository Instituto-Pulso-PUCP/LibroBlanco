#!/usr/bin/env python3
"""Reconstruye salidas/07_publications_linked_full.csv recuperando abstracts.

Corrige un fallo del script original (`build_linked_publications_subset.py`):
cuando una fila cruzaba con `03_publications_master.csv`, tomaba el abstract
del master y DESCARTABA el `resumen` / `openalex_abstract` del ground truth,
incluso cuando el del master venia vacio. Se perdian 153 abstracts que ya
estaban en disco.

Cascada de procedencia (se para en la primera que da texto util, >80 chars):

  1. master          `03_publications_master.csv` (texto ya depurado)
  2. doi_resultados  `datos/doi-resultados-final.csv`, cruzado por DOI
                     (9 371 DOIs con resumen/palabras clave de Scopus/
                     OpenAlex/PubMed; llegó despues del resto de las fuentes,
                     asi que no estaba disponible cuando se armaron)
  3. resumen         `07_..._ground_truth.csv`, resumen humano por DOI
  4. openalex        idem, reconstruido del abstract_inverted_index. Solo si la
                     obra se emparejo por DOI, o por titulo con
                     lb_titles.same_work: la busqueda por titulo de la
                     etapa de enriquecimiento toma el primer resultado sin
                     verificarlo, y en ~3 de cada 4 casos es otra obra (p.ej.
                     el titulo de relleno "EXONERADO" trajo el resumen de un
                     articulo sobre Carlos II).
  5. source          idem, abstract de la fuente original (WoS/RI)
  6. pulso_wos       hoja `Pubs_WoS` del Excel de PULSO, por DOI o titulo
  7. vri_dfi         `datos/Publicaciones - VRI-DFI ....csv`, cruzado por titulo
  8. cris            `datos/Publicaciones - CRIS - <fecha>.csv` (el mas reciente),
                     por DOI o por titulo normalizado identico en cualquiera de
                     sus columnas de titulo (es, en, pt...). Desde 2026-10-13.
  9. externo         `salidas/abstracts_recuperados/candidatos.csv`, filas con
                     veredicto "aceptar": abstracts buscados por DOI/titulo en
                     Semantic Scholar, Crossref, OpenAlex y Google Books
                     (scripts/addons/recover_abstracts_external.py), con el
                     titulo hallado verificado contra el declarado.

Palabras clave, cuando faltan en master/ground-truth, en este orden:
doi-resultados-final.csv (por DOI), hojas `Pubs_RI` (`key_words`) y `Pubs_WoS`
(`keywords` + `keywords_plus`) del Excel de PULSO (por DOI o titulo), y los
`dc.subject*` del CSV VRI-DFI (por titulo) y los `dc.subject*` de Publicaciones
CRIS (por DOI o titulo).

El paso 6 y las hojas de PULSO importan sobre todo para los resultados que no
cruzaron al catalogo maestro por DOI (ids `gt_*`): para ellos el master no
aporta nada, pero la misma publicacion suele estar en las hojas por titulo.

Anade las columnas `abstract_source` y `keywords_source` con la procedencia,
para poder auditar despues de donde salio cada texto. Solo stdlib + openpyxl
(el script original usaba pandas, que no esta instalado en este servidor).

    python scripts/addons/rebuild_linked_publications.py
    python scripts/addons/rebuild_linked_publications.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import lb_domains  # noqa: E402
import lb_titles   # noqa: E402

GT = ROOT / "salidas" / "07_project_publication_ground_truth.csv"
MASTER = ROOT / "salidas" / "03_publications_master.csv"
VRI = ROOT / "datos" / "Publicaciones - VRI-DFI 20260721.csv"
DOI_RESULTADOS = ROOT / "datos" / "doi-resultados-final.csv"
PULSO_XLSX = ROOT / "datos" / "informacion_proyecto_pulso.xlsx"
OPENALEX_RAW = ROOT / "salidas" / "06_project_results_ground_truth_openalex_raw_payload.jsonl"
OUT = ROOT / "salidas" / "07_publications_linked_full.csv"

MIN_CHARS = 80   # por debajo de esto no es un abstract, es un resto
# Revisado a mano contra los 113 emparejamientos por titulo: por debajo de esto
# eran todos otra obra; los emparejados por DOI con similitud baja eran la
# misma obra con el titulo traducido, por eso el DOI no pasa por este filtro.
OPENALEX_MIN_TITLE_SIM = lb_titles.MIN_SEQUENCE
EXTERNAL = ROOT / "salidas" / "abstracts_recuperados" / "candidatos.csv"
CRIS_PUBS_GLOB = "Publicaciones - CRIS - *.csv"


def norm_title(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def useful(value) -> str:
    """Texto util, o cadena vacia. clean_value ya descarta los enlaces (la
    columna Abstract de Scopus es un enlace en todas sus filas)."""
    text = lb_domains.clean_value(value)
    return text if len(text) >= MIN_CHARS else ""


def read_csv(path: Path) -> list[dict]:
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def norm_doi(value) -> str:
    text = lb_domains.clean_value(value).lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text


def load_doi_resultados() -> dict[str, dict]:
    if not DOI_RESULTADOS.exists():
        return {}
    out = {}
    for row in read_csv(DOI_RESULTADOS):
        doi = norm_doi(row.get("doi"))
        if doi:
            out[doi] = row
    return out


def title_similarity(a: str, b: str) -> float:
    """Ver lb_titles.title_match. La version anterior medía el solapamiento de
    palabras sobre el titulo mas corto sin minimo de palabras y aceptaba
    titulos cortos contenidos en otra obra ("EPICICLOS" -> un articulo sobre
    Copernico y Kepler)."""
    return lb_titles.title_match(a, b)


def load_external() -> dict[str, dict]:
    """publication_id -> {abstract, fuente} de los abstracts recuperados aceptados."""
    if not EXTERNAL.exists():
        return {}
    out = {}
    for row in read_csv(EXTERNAL):
        if (row.get("veredicto") or "").strip() == "aceptar" and useful(row.get("abstract")):
            out[row["publication_id"]] = {"abstract": row["abstract"], "fuente": row.get("fuente", "")}
    return out


def load_cris_publications() -> tuple[dict, dict, str]:
    """(por DOI, por titulo normalizado) -> {abstract, keywords} desde el export
    de Publicaciones CRIS mas reciente. Los titulos estan repartidos en columnas
    por idioma (dc.title[es_PE], dc.title[en_US]...): se indexan todas."""
    files = sorted((ROOT / "datos").glob(CRIS_PUBS_GLOB))
    if not files:
        return {}, {}, ""
    by_doi, by_title = {}, {}
    for r in read_csv(files[-1]):
        abstract = ""
        for col in ("dc.description.abstract[es_PE]", "dc.description.abstract[en_US]",
                    "dc.description.abstract"):
            abstract = useful(r.get(col))
            if abstract:
                break
        if not abstract:
            abstract = next((useful(v) for c, v in r.items()
                             if c.startswith("dc.description.abstract") and useful(v)), "")
        keywords = "; ".join(v.strip() for c, v in r.items()
                             if c.startswith("dc.subject") and c != "dc.subject.ocde"
                             and lb_domains.clean_value(v))
        if not abstract and not keywords:
            continue
        entry = {"abstract": abstract, "keywords": keywords}
        doi = norm_doi(r.get("dc.identifier.doi"))
        if doi:
            by_doi.setdefault(doi, entry)
        for c, v in r.items():
            if c.startswith("dc.title"):
                t = norm_title(lb_domains.clean_value(v))
                if len(t) > 15:
                    by_title.setdefault(t, entry)
    return by_doi, by_title, files[-1].name


def load_openalex_titles() -> dict[tuple[str, str], str]:
    """(project_id, cod_prod) -> titulo de la obra OpenAlex emparejada."""
    if not OPENALEX_RAW.exists():
        return {}
    out = {}
    with OPENALEX_RAW.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            payload = row.get("openalex_raw_payload")
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except ValueError:
                    continue
            if isinstance(payload, dict) and payload.get("id"):
                out[(str(row["project_id"]), str(row["cod_prod"]))] = payload.get("title") or ""
    return out


def load_pulso_sheets() -> tuple[dict, dict]:
    """(por DOI, por titulo) -> lista de aportes {sheet, abstract, keywords} desde
    las hojas Pubs_WoS y Pubs_RI del Excel de PULSO.

    La columna Abstract de Pubs_SCOPUS no se lee: es un enlace en todas sus filas.
    """
    if not PULSO_XLSX.exists():
        return {}, {}
    import openpyxl
    wb = openpyxl.load_workbook(PULSO_XLSX, read_only=True, data_only=True)

    def rows(name):
        it = wb[name].iter_rows(values_only=True)
        header = next(it)
        for r in it:
            yield dict(zip(header, ["" if v is None else str(v) for v in r]))

    by_doi, by_title = {}, {}

    def add(sheet, doi, title, abstract, keywords):
        entry = {"sheet": sheet, "abstract": useful(abstract),
                 "keywords": lb_domains.clean_value(keywords)}
        if not entry["abstract"] and not entry["keywords"]:
            return
        if norm_doi(doi):
            by_doi.setdefault(norm_doi(doi), []).append(entry)
        if len(norm_title(title)) > 15:
            by_title.setdefault(norm_title(title), []).append(entry)

    for r in rows("Pubs_WoS"):
        kw = "; ".join(k for k in (lb_domains.clean_value(r.get("keywords")),
                                    lb_domains.clean_value(r.get("keywords_plus"))) if k)
        add("pulso_wos", r.get("doi"), r.get("title"), r.get("abstract"), kw)
    for r in rows("Pubs_RI"):
        add("pulso_ri", r.get("doi"), r.get("titulo"), "", r.get("key_words"))
    return by_doi, by_title


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    ground = read_csv(GT)
    master = {r["publication_id"]: r for r in read_csv(MASTER)}
    doi_resultados = load_doi_resultados()
    print(f"doi-resultados-final.csv: {len(doi_resultados):,} DOIs cargados"
          if doi_resultados else "doi-resultados-final.csv no encontrado; se omite ese paso.")
    pulso_by_doi, pulso_by_title = load_pulso_sheets()
    openalex_titles = load_openalex_titles()
    if not openalex_titles:
        print(f"AVISO: no se encontro {OPENALEX_RAW.name}; no se puede verificar el titulo de los "
              "emparejamientos OpenAlex por titulo, asi que se descartan todos los que no sean por DOI.")
    openalex_rejected = 0
    cris_by_doi, cris_by_title, cris_file = load_cris_publications()
    print(f"Publicaciones CRIS ({cris_file}): {len(cris_by_doi):,} por DOI, {len(cris_by_title):,} títulos"
          if cris_file else "Publicaciones CRIS no encontrado en datos/; se omite ese paso.")
    external = load_external()
    print(f"abstracts recuperados externamente (aceptados): {len(external)}"
          if external else f"{EXTERNAL.name} no encontrado o sin aceptados; se omite el paso externo.")
    vri, vri_kw = {}, {}
    if VRI.exists():
        for row in read_csv(VRI):
            title = norm_title(lb_domains.clean_value(row.get("dc.title[es_ES]"))
                               or lb_domains.clean_value(row.get("dc.title[en_US]")))
            text = (useful(row.get("dc.description.abstract[en_US]"))
                    or useful(row.get("dc.description.abstract[es_ES]")))
            if title and text:
                vri[title] = text
            subjects = "; ".join(k for k in (lb_domains.clean_value(row.get(c)) for c in (
                "dc.subject", "dc.subject[en_US]", "dc.subject[es_ES]")) if k)
            if title and subjects:
                vri_kw[title] = subjects

    rows, provenance, kw_provenance = [], Counter(), Counter()
    for record in ground:
        pub_id = lb_domains.clean_value(record.get("publication_id"))
        matched = master.get(pub_id, {})
        if matched:
            title = lb_domains.clean_value(matched.get("title"))
            keywords = lb_domains.clean_value(matched.get("keywords"))
            journal = lb_domains.clean_value(matched.get("journal"))
            row_id = pub_id
        else:
            title = lb_domains.clean_value(record.get("result_title"))
            keywords = " ".join(k for k in (
                lb_domains.clean_value(record.get("source_keywords")),
                lb_domains.clean_value(record.get("palabras_clave"))) if k)
            journal = lb_domains.clean_value(record.get("journal_raw"))
            row_id = f"gt_{record.get('project_id','')}_{record.get('cod_prod','')}"

        doi = norm_doi(record.get("doi_norm")) or norm_doi(matched.get("doi") if matched else "")
        doi_hit = doi_resultados.get(doi, {})
        pulso_hits = (pulso_by_doi.get(doi, []) if doi else []) + (
            pulso_by_title.get(norm_title(title), []) if title else [])
        cris_hit = (cris_by_doi.get(doi) if doi else None) or (
            cris_by_title.get(norm_title(title)) if title else None) or {}

        # OpenAlex: por DOI vale siempre; por titulo, solo si el titulo coincide.
        openalex_abstract = record.get("openalex_abstract")
        if useful(openalex_abstract) and not norm_doi(record.get("doi_norm")):
            key = (lb_domains.clean_value(record.get("project_id")),
                   lb_domains.clean_value(record.get("cod_prod")))
            declared = lb_domains.clean_value(record.get("result_title")) or title
            if title_similarity(declared, openalex_titles.get(key, "")) < OPENALEX_MIN_TITLE_SIM:
                openalex_abstract = ""
                openalex_rejected += 1

        # La cascada: el fallo original era pararse en el primer paso.
        abstract, source = "", ""
        for candidate, label in (
            (matched.get("abstract") if matched else "", "master"),
            (doi_hit.get("resumen"), "doi_resultados"),
            (record.get("resumen"), "resumen"),
            (openalex_abstract, "openalex"),
            (record.get("source_abstract"), "source"),
            (next((h["abstract"] for h in pulso_hits if h["abstract"]), ""), "pulso_wos"),
            (vri.get(norm_title(title)) if title else "", "vri_dfi"),
            (cris_hit.get("abstract"), "cris"),
            ((external.get(row_id) or {}).get("abstract"), "externo"),
        ):
            text = useful(candidate)
            if text:
                abstract, source = text, label
                break

        keywords_source = "master_o_ground_truth" if keywords else ""
        if not keywords:
            for candidate, label in (
                (doi_hit.get("palabras_clave"), "doi_resultados"),
                (next((h["keywords"] for h in pulso_hits
                       if h["sheet"] == "pulso_ri" and h["keywords"]), ""), "pulso_ri"),
                (next((h["keywords"] for h in pulso_hits
                       if h["sheet"] == "pulso_wos" and h["keywords"]), ""), "pulso_wos"),
                (vri_kw.get(norm_title(title)) if title else "", "vri_dfi"),
                (cris_hit.get("keywords"), "cris"),
            ):
                keywords = lb_domains.clean_value(candidate)
                if keywords:
                    keywords_source = label
                    break
        kw_provenance[keywords_source or "sin_keywords"] += 1

        provenance[source or "sin_abstract"] += 1
        rows.append({
            "publication_id": row_id,
            "title": title,
            "abstract": abstract,
            "abstract_source": source,
            "keywords": keywords,
            "keywords_source": keywords_source,
            "journal": journal,
            # trazabilidad hacia el proyecto que declaro este resultado
            "project_id": lb_domains.clean_value(record.get("project_id")),
        })

    with_abstract = sum(1 for r in rows if r["abstract"])
    with_text = sum(1 for r in rows
                    if any(r[c] for c in ("title", "abstract", "keywords")))
    print(f"{len(rows)} resultados declarados")
    print(f"  con abstract        : {with_abstract} ({with_abstract/len(rows)*100:.1f}%)")
    print(f"  con algo de texto   : {with_text}")
    print(f"  resumenes OpenAlex descartados (otra obra, emparejada por titulo): {openalex_rejected}")
    print("  procedencia del abstract:")
    for label, count in provenance.most_common():
        print(f"    {label:14s} {count:5d}")
    print("  procedencia de las palabras clave:")
    for label, count in kw_provenance.most_common():
        print(f"    {label:22s} {count:5d}")

    if args.dry_run:
        print("\n--dry-run: no se escribe nada.")
        return

    fields = ["publication_id", "title", "abstract", "abstract_source",
              "keywords", "keywords_source", "journal", "project_id"]
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Metadatos y abstracts faltantes para un publications.csv estandar, sin Scopus.

Para datasets que llegan solo con el titulo de cada publicacion (ECOTEC).
Dos pasos, ambos con el titulo verificado por lb_titles (misma obra):

1. OpenAlex por titulo -> doi, year, journal, keywords. Las keywords de
   OpenAlex las asigna OpenAlex, no los autores: se guardan con su fuente
   (keywords_source = "openalex_auto") para que quede a la vista.
2. Para las que siguen sin abstract y tienen DOI: la pagina del editor
   (doi.org -> landing). Muchas revistas publican el abstract en etiquetas
   meta (citation_abstract, DC.Description) aunque no lo entreguen a
   OpenAlex/Crossref. Se acepta solo si la pagina trae un titulo que pasa el
   mismo control de misma obra.

Salidas (no toca publications.csv; el adaptador del dataset las integra):
  <dir>/metadatos.csv            publication_id, doi, year, journal, keywords,
                                 keywords_source, openalex_id, sim
  <dir>/busqueda_landing.jsonl   mismo formato que recover_abstracts_external.py,
                                 para pasarlo por build_external_candidates.py

    python scripts/addons/enrich_publications_metadata.py \
        --publications salidas/datasets/ecotec/publications.csv \
        --out-dir salidas/datasets/ecotec/abstracts_recuperados
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT / "scripts" / "addons"))
import lb_titles  # noqa: E402
from recover_abstracts_external import MIN_CHARS, get, oa_abstract, paper_title, strip_jats  # noqa: E402

META_FIELDS = ["publication_id", "doi", "year", "journal", "keywords", "keywords_source",
               "openalex_id", "sim"]
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
              "Accept": "text/html,application/xhtml+xml"}
# Orden de preferencia: las dos primeras son el abstract completo; og/description
# suelen venir recortadas y solo se aceptan largas y sin puntos suspensivos.
ABSTRACT_META = ("citation_abstract", "dc.description", "dcterms.abstract", "eprints.abstract")
LOOSE_META = ("og:description", "description")
TITLE_META = ("citation_title", "dc.title", "og:title")
META_RE = re.compile(r"<meta\s[^>]*>", re.I | re.S)
ATTR_RE = re.compile(r'(name|property|content)\s*=\s*("([^"]*)"|\'([^\']*)\')', re.I | re.S)


def openalex_by_title(title):
    q = paper_title(title)
    r = get("https://api.openalex.org/works?per-page=5&select=id,doi,title,publication_year,"
            "primary_location,keywords,abstract_inverted_index&search=" + urllib.parse.quote(q[:300]))
    best, best_sim = None, 0.0
    for x in (r or {}).get("results", []):
        sim = max(lb_titles.title_match(q, x.get("title") or ""),
                  lb_titles.title_match(title, x.get("title") or ""))
        if sim >= lb_titles.MIN_SEQUENCE and sim > best_sim:
            best, best_sim = x, sim
    return best, best_sim


def page_meta(doi):
    """{nombre_meta_en_minusculas: [valores]} de la landing del DOI, o {}."""
    try:
        req = urllib.request.Request("https://doi.org/" + urllib.parse.quote(doi, safe="/:"),
                                     headers=BROWSER_UA)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read(3_000_000).decode(resp.headers.get_content_charset() or "utf-8",
                                               errors="replace")
    except Exception:
        return {}
    out = {}
    for tag in META_RE.findall(body):
        attrs = {m.group(1).lower(): (m.group(3) if m.group(3) is not None else m.group(4))
                 for m in ATTR_RE.finditer(tag)}
        key = (attrs.get("name") or attrs.get("property") or "").lower()
        if key and attrs.get("content"):
            out.setdefault(key, []).append(html.unescape(attrs["content"]).strip())
    return out


def landing_abstract(doi, title):
    """(abstract, titulo_hallado, fuente) desde la landing, o vacios."""
    meta = page_meta(doi)
    found_title = next((meta[k][0] for k in TITLE_META if meta.get(k)), "")
    if not found_title or not lb_titles.same_work(title, found_title):
        return "", found_title, ""
    for key in ABSTRACT_META:
        text = strip_jats(max(meta.get(key, [""]), key=len))
        if len(text) >= MIN_CHARS:
            return text, found_title, "landing_" + key
    for key in LOOSE_META:
        text = strip_jats(max(meta.get(key, [""]), key=len))
        if len(text) >= 400 and not text.rstrip().endswith(("...", "…")):
            return text, found_title, "landing_" + key
    return "", found_title, ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--publications", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    with args.publications.open(encoding="utf-8-sig", newline="") as h:
        pubs = list(csv.DictReader(h))

    meta_rows, landing = [], []
    for n, p in enumerate(pubs, 1):
        title = p["title"].strip()
        work, sim = openalex_by_title(title)
        doi = (p.get("doi") or "").strip()
        row = {"publication_id": p["publication_id"], "doi": doi, "year": "", "journal": "",
               "keywords": "", "keywords_source": "", "openalex_id": "", "sim": round(sim, 3)}
        if work:
            row.update(doi=doi or (work.get("doi") or "").replace("https://doi.org/", ""),
                       year=work.get("publication_year") or "",
                       journal=((work.get("primary_location") or {}).get("source") or {}).get(
                           "display_name") or "",
                       openalex_id=work.get("id", ""))
            kws = [k.get("display_name", "") for k in work.get("keywords") or [] if k.get("display_name")]
            if kws:
                row.update(keywords=" | ".join(kws), keywords_source="openalex_auto")
        meta_rows.append(row)

        if len((p.get("abstract") or "").strip()) < MIN_CHARS and row["doi"]:
            abstract, found_title, source = landing_abstract(row["doi"], title)
            landing.append({"publication_id": p["publication_id"], "title": title,
                            "query": paper_title(title), "doi": row["doi"], "found": bool(abstract),
                            "source": source, "matched_title": found_title, "abstract": abstract,
                            "tried": ["landing"]})
            time.sleep(1.0)
        if n % 25 == 0:
            print(f"  {n}/{len(pubs)}", flush=True)

    with (args.out_dir / "metadatos.csv").open("w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=META_FIELDS)
        w.writeheader()
        w.writerows(meta_rows)
    with (args.out_dir / "busqueda_landing.jsonl").open("w", encoding="utf-8") as h:
        for rec in landing:
            h.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"OpenAlex: {sum(1 for r in meta_rows if r['openalex_id'])}/{len(pubs)} verificadas, "
          f"{sum(1 for r in meta_rows if r['doi'])} con DOI, "
          f"{sum(1 for r in meta_rows if r['keywords'])} con keywords")
    print(f"Landing: {sum(1 for r in landing if r['found'])}/{len(landing)} sin abstract recuperadas")
    print(f"-> {args.out_dir}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Reconstruye salidas/07_publications_linked_full.csv recuperando abstracts.

Corrige un fallo del script original (`build_linked_publications_subset.py`):
cuando una fila cruzaba con `03_publications_master.csv`, tomaba el abstract
del master y DESCARTABA el `resumen` / `openalex_abstract` del ground truth,
incluso cuando el del master venia vacio. Se perdian 153 abstracts que ya
estaban en disco.

Cascada de procedencia (se para en la primera que da texto util, >80 chars):

  1. master        `03_publications_master.csv` (texto ya depurado)
  2. resumen       `07_..._ground_truth.csv`, resumen humano por DOI
  3. openalex      idem, reconstruido del abstract_inverted_index
  4. source        idem, abstract de la fuente original (WoS/RI)
  5. vri_dfi       `datos/Publicaciones - VRI-DFI ....csv`, cruzado por titulo

Anade la columna `abstract_source` con la procedencia, para poder auditar
despues de donde salio cada texto. Sin dependencias externas: solo stdlib
(el script original usaba pandas, que no esta instalado en este servidor).

    python scripts/addons/rebuild_linked_publications.py
    python scripts/addons/rebuild_linked_publications.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import lb_domains  # noqa: E402

GT = ROOT / "salidas" / "07_project_publication_ground_truth.csv"
MASTER = ROOT / "salidas" / "03_publications_master.csv"
VRI = ROOT / "datos" / "Publicaciones - VRI-DFI 20260721.csv"
OUT = ROOT / "salidas" / "07_publications_linked_full.csv"

MIN_CHARS = 80   # por debajo de esto no es un abstract, es un resto


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    ground = read_csv(GT)
    master = {r["publication_id"]: r for r in read_csv(MASTER)}
    vri = {}
    if VRI.exists():
        for row in read_csv(VRI):
            title = norm_title(lb_domains.clean_value(row.get("dc.title[es_ES]"))
                               or lb_domains.clean_value(row.get("dc.title[en_US]")))
            text = (useful(row.get("dc.description.abstract[en_US]"))
                    or useful(row.get("dc.description.abstract[es_ES]")))
            if title and text:
                vri[title] = text

    rows, provenance = [], Counter()
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

        # La cascada: el fallo original era pararse en el primer paso.
        abstract, source = "", ""
        for candidate, label in (
            (matched.get("abstract") if matched else "", "master"),
            (record.get("resumen"), "resumen"),
            (record.get("openalex_abstract"), "openalex"),
            (record.get("source_abstract"), "source"),
            (vri.get(norm_title(title)) if title else "", "vri_dfi"),
        ):
            text = useful(candidate)
            if text:
                abstract, source = text, label
                break

        provenance[source or "sin_abstract"] += 1
        rows.append({
            "publication_id": row_id,
            "title": title,
            "abstract": abstract,
            "abstract_source": source,
            "keywords": keywords,
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
    print("  procedencia del abstract:")
    for label, count in provenance.most_common():
        print(f"    {label:14s} {count:5d}")

    if args.dry_run:
        print("\n--dry-run: no se escribe nada.")
        return

    fields = ["publication_id", "title", "abstract", "abstract_source",
              "keywords", "journal", "project_id"]
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n-> {args.out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

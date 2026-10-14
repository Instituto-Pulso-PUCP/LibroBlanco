#!/usr/bin/env python3
"""Convierte la búsqueda externa de abstracts en candidatos.csv, con veredicto.

recover_abstracts_external.py escribe un JSONL con lo que encontró para cada
publicación declarada sin abstract. rebuild_linked_publications.py solo usa las
filas de salidas/abstracts_recuperados/candidatos.csv con veredicto "aceptar".
Este script arma (o completa) ese CSV:

  - aceptar: los títulos se parecen carácter a carácter (similitud de secuencia
    >= 0.85, con o sin el prefijo de congreso que limpia la búsqueda).
  - revisar: solo coinciden por palabras de contenido (lb_titles.same_work por
    solapamiento) o se halló por el DOI de nuestro registro con otro título. Es
    el patrón de los 12 casos que se revisaron a mano el 2026-10-11: ponencia
    publicada luego como artículo, capítulo "EN: <libro>", título traducido.
    Lo decide una persona cambiando el veredicto en el CSV.
  - rechazar: el resto.

Las filas que ya estaban en candidatos.csv NO se tocan (pueden tener una
decisión manual); solo se agregan publicaciones nuevas.

    python scripts/addons/build_external_candidates.py
    python scripts/addons/build_external_candidates.py --busqueda salidas/abstracts_recuperados/busqueda.jsonl
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import lb_titles  # noqa: E402

DIR = ROOT / "salidas" / "abstracts_recuperados"
FIELDS = ["publication_id", "veredicto", "similitud", "secuencia", "fuente",
          "titulo_nuestro", "titulo_hallado", "abstract"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--busqueda", type=Path, default=DIR / "busqueda.jsonl")
    ap.add_argument("--out", type=Path, default=DIR / "candidatos.csv")
    args = ap.parse_args(argv)

    existing = []
    if args.out.exists():
        with args.out.open(encoding="utf-8-sig", newline="") as h:
            existing = list(csv.DictReader(h))
    have = {r["publication_id"] for r in existing}

    new, seen = [], set()
    with args.busqueda.open(encoding="utf-8") as h:
        for line in h:
            rec = json.loads(line)
            pid = rec["publication_id"]
            if not rec.get("found") or pid in have or pid in seen:
                continue
            seen.add(pid)
            ours = rec.get("query") or rec.get("title") or ""
            found = rec.get("matched_title") or ""
            sim = max(lb_titles.title_match(ours, found), lb_titles.title_match(rec.get("title", ""), found))
            seq = SequenceMatcher(None, lb_titles.norm_title(rec.get("title", "")),
                                  lb_titles.norm_title(found)).ratio()
            by_own_doi = rec.get("source", "").endswith("_doi") and "+" not in rec.get("source", "")
            seq_best = max(seq, SequenceMatcher(None, lb_titles.norm_title(ours),
                                                lb_titles.norm_title(found)).ratio())
            if seq_best >= lb_titles.MIN_SEQUENCE:
                verdict = "aceptar"
            elif sim >= lb_titles.MIN_SEQUENCE or by_own_doi:
                verdict = "revisar"
            else:
                verdict = "rechazar"
            new.append({"publication_id": pid, "veredicto": verdict, "similitud": round(sim, 3),
                        "secuencia": round(seq, 3), "fuente": rec.get("source", ""),
                        "titulo_nuestro": rec.get("title", ""), "titulo_hallado": found,
                        "abstract": rec.get("abstract", "")})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader(); w.writerows(existing + new)
    print(f"candidatos.csv: {len(existing)} filas previas (sin tocar) + {len(new)} nuevas")
    print("  nuevas por veredicto:", dict(Counter(r["veredicto"] for r in new)))
    print("  total por veredicto: ", dict(Counter(r["veredicto"] for r in existing + new)))
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

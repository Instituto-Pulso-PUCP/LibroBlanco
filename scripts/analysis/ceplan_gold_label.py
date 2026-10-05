#!/usr/bin/env python3
"""Etiquetado interactivo en terminal del gold humano CEPLAN.

Recorre salidas/topics/ceplan/benchmark/gold_humano.csv unidad por unidad:
muestra el titulo y el texto del proyecto/publicacion una vez, y luego cada
sub-tematica candidata para calificarla 0/1/2. Guarda en el mismo CSV despues
de cada respuesta, asi que se puede salir en cualquier momento y retomar
donde quedo.

    python scripts/analysis/ceplan_gold_label.py            # retoma lo pendiente
    python scripts/analysis/ceplan_gold_label.py --revisar  # recorre todo, tambien lo ya calificado

Teclas en cada sub-tematica:
    0 / 1 / 2   calificar y pasar a la siguiente
    c           agregar o editar un comentario (no avanza)
    t           volver a mostrar el texto de la unidad
    b           volver al par anterior
    s           saltar (queda pendiente)
    q           guardar y salir
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

GOLD_PATH = ROOT / "salidas" / "topics" / "ceplan" / "benchmark" / "gold_humano.csv"

CRITERIO = ("2 = la investigación desarrolla claramente la sub-temática o aporta "
            "conocimiento directamente útil para ella\n"
            "1 = relación tangencial o indirecta\n"
            "0 = sin relación real")

_TTY = sys.stdout.isatty()


def _ansi(code, text):
    return f"\033[{code}m{text}\033[0m" if _TTY else text


def bold(t): return _ansi("1", t)
def dim(t): return _ansi("2", t)
def cyan(t): return _ansi("36", t)
def yellow(t): return _ansi("33", t)
def green(t): return _ansi("32", t)


def width():
    return min(shutil.get_terminal_size((100, 30)).columns, 110) - 2


def wrap(text, indent=""):
    return "\n".join(textwrap.fill(p, width(), initial_indent=indent, subsequent_indent=indent)
                     for p in text.split("\n") if p.strip())


def clear():
    if _TTY:
        os.system("clear")


def load_descriptions():
    """Acciones Estrategicas (AE) de CEPLAN por (tematica, sub-tematica), para
    tener a mano que significa cada una. Son mas especificas que el Objetivo
    Especifico, que se repite en todas las sub-tematicas de un mismo ON. Si el
    libro no esta disponible se sigue sin descripciones."""
    try:
        import lb_ceplan
        import openpyxl
        wb = openpyxl.load_workbook(lb_ceplan.PEDN_XLSX, read_only=True, data_only=True)
        enrichment = lb_ceplan._load_on_sheet_enrichment(wb)
    except Exception:  # noqa: BLE001 -- es solo ayuda visual
        return {}
    return {key: [t for t in texts if t.upper().startswith("AE")]
            for key, texts in enrichment.items()}


def clean(text):
    """Quita los 'nan' que dejo el armado del texto de la unidad con campos vacios."""
    text = re.sub(r"(?:^|(?<=[.|]))\s*nan\s*(?=[.|]|$)", "", text)
    text = re.sub(r"\.{2,}", ".", re.sub(r"(?:\s*\|)+\s*", " | ", text))
    return text.strip(" .|")


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


def save_rows(path, fields, rows):
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)  # atomico: un corte a mitad de escritura no rompe el CSV


def unit_key(row):
    return row["par_id"].rsplit("|", 1)[0]


def show_unit(rows, i, unit_order, done):
    row = rows[i]
    key = unit_key(row)
    siblings = [r for r in rows if unit_key(r) == key]
    clear()
    n_unit = unit_order.index(key) + 1
    print(dim(f"Unidad {n_unit}/{len(unit_order)} · {row['tipo']} · "
              f"calificados {done}/{len(rows)} pares"))
    print()
    print(bold(wrap(clean(row["titulo"]))))
    print()
    body = row["texto"]
    if body.startswith(row["titulo"]):
        body = body[len(row["titulo"]):].lstrip(". ")
    print(wrap(clean(body)))
    print()
    print(dim("Sub-temáticas candidatas de esta unidad:"))
    for r in siblings:
        grade = r["grado_0_1_2"].strip()
        mark = green(f"[{grade}]") if grade else dim("[ ]")
        print(f"  {mark} {r['sub_tematica']}")
    print()


def prompt_pair(row, pos, total, desc):
    print(dim("─" * width()))
    print(f"{cyan(f'[{pos}/{total}]')} {bold(row['sub_tematica'])}")
    on_code = row["objetivo_nacional"].split(".")[0].strip()
    print(dim(wrap(f"Temática: {row['tematica']} · {on_code}", "  ")))
    for ae in desc.get((row["tematica"], row["sub_tematica"]), [])[:2]:
        if len(ae) > 260:
            ae = ae[:260].rsplit(" ", 1)[0] + " …"
        print(dim(wrap(f"CEPLAN {ae}", "  ")))
    if row["grado_0_1_2"].strip():
        print(yellow(f"  grado actual: {row['grado_0_1_2']}"))
    if row["comentario"].strip():
        print(yellow(f"  comentario: {row['comentario']}"))
    return input(f"  grado {bold('0/1/2')}  "
                 f"{dim('c=comentario t=texto b=atrás s=saltar ?=criterio q=salir')} > ").strip().lower()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--revisar", action="store_true",
                        help="Recorrer todos los pares, tambien los ya calificados.")
    parser.add_argument("--archivo", type=Path, default=GOLD_PATH)
    args = parser.parse_args()

    if not args.archivo.exists():
        raise SystemExit(f"No existe {args.archivo}. Generarlo con "
                         "`python scripts/analysis/ceplan_judge_benchmark.py gold`.")
    fields, rows = read_rows(args.archivo)
    desc = load_descriptions()
    unit_order = list(dict.fromkeys(unit_key(r) for r in rows))

    def pending(i):
        return args.revisar or not rows[i]["grado_0_1_2"].strip()

    clear()
    print(bold("Etiquetado del gold humano CEPLAN"))
    print(wrap(CRITERIO, "  "))
    print(dim(f"\nArchivo: {args.archivo}"))
    print(dim("Se guarda después de cada respuesta; q para salir y retomar luego."))
    input(dim("\nEnter para empezar > "))

    i = next((k for k in range(len(rows)) if pending(k)), None)
    shown_unit = None
    while i is not None and i < len(rows):
        row = rows[i]
        done = sum(1 for r in rows if r["grado_0_1_2"].strip())
        if unit_key(row) != shown_unit:
            show_unit(rows, i, unit_order, done)
            shown_unit = unit_key(row)
        siblings = [k for k in range(len(rows)) if unit_key(rows[k]) == shown_unit]
        try:
            answer = prompt_pair(row, siblings.index(i) + 1, len(siblings), desc)
        except (EOFError, KeyboardInterrupt):
            print()
            answer = "q"

        if answer in ("0", "1", "2"):
            row["grado_0_1_2"] = answer
            save_rows(args.archivo, fields, rows)
            i = next((k for k in range(i + 1, len(rows)) if pending(k)), None)
        elif answer == "c":
            try:
                row["comentario"] = input("  comentario (Enter vacío lo borra) > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
            save_rows(args.archivo, fields, rows)
        elif answer == "t":
            shown_unit = None
        elif answer == "b":
            if i > 0:
                i -= 1
            if unit_key(rows[i]) != shown_unit:
                shown_unit = None
        elif answer == "s":
            i = next((k for k in range(i + 1, len(rows)) if pending(k)), None)
        elif answer == "?":
            print(wrap(CRITERIO, "  "))
        elif answer == "q":
            break
        else:
            print(yellow("  respuesta no reconocida"))

    done = sum(1 for r in rows if r["grado_0_1_2"].strip())
    print()
    print(bold(f"Calificados {done}/{len(rows)} pares.") +
          (" Listo: correr `python scripts/analysis/ceplan_judge_benchmark.py report`."
           if done == len(rows) else " Volver a ejecutar para retomar."))


if __name__ == "__main__":
    main()

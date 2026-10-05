#!/usr/bin/env python3
"""Validacion humana de la salida real del cruce unidad <-> sub-tematica CEPLAN.

El benchmark (ceplan_judge_benchmark.py) eligio el modelo; esto mide lo que
de verdad se publica (EXPERIMENTS.md §6.4): una muestra aleatoria de unidades
alineadas por ceplan_units.py, con sus vinculos confirmados (los que se
listan: hasta top_n por unidad) mas la candidata rechazada de mayor
similitud, para tener tambien una lectura de lo que el verificador descarta.
La persona califica sin ver el grado del modelo.

    python scripts/analysis/ceplan_validation.py sample   # muestra + datos de la pagina
    python scripts/analysis/ceplan_validation.py report   # precision cuando esta calificado
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

import lb_config  # noqa: E402
import lb_store   # noqa: E402

RUNS = {"projects": "full-proj-646", "publications_linked": "publications_linked-529"}
OUT = ROOT / "salidas" / "topics" / "ceplan" / "validacion"
SAMPLE = OUT / "muestra.jsonl"           # con el grado del modelo (no se muestra)
CSV_PATH = OUT / "validacion_humana.csv"  # se llena con las calificaciones humanas
UNITS_PER_DOMAIN = 12


def load_domain(domain):
    base = ROOT / "salidas" / "topics" / domain / RUNS[domain]
    return json.loads((base / "07_ceplan_units.json").read_text(encoding="utf-8"))


def cmd_sample(_args):
    from ceplan_gold_label import clean, load_descriptions
    if CSV_PATH.exists():
        raise SystemExit(f"{CSV_PATH.relative_to(ROOT)} ya existe: no se sobrescribe.")
    cfg = lb_config.load()
    desc = load_descriptions()
    rng = random.Random(2026)
    OUT.mkdir(parents=True, exist_ok=True)
    rows, page_units = [], []
    for domain in RUNS:
        payload = load_domain(domain)
        subs = payload["subtematicas"]
        texts = {u["unit_id"]: u for u in lb_store.open_store(cfg, domain, RUNS[domain]).read_units()}
        aligned = sorted(u for u, v in payload["units"].items() if v["status"] == "alineada")
        for unit_id in rng.sample(aligned, UNITS_PER_DOMAIN):
            unit = payload["units"][unit_id]
            pairs = [(s["sub_id"], s["grade"], s["sim"]) for s in unit["subs"] if s.get("top")]
            # las candidatas van en orden de similitud: la primera rechazada es la mas cercana
            rejected = [c for c in unit["judged"] if c["grade"] == 0]
            if rejected:
                pairs.append((rejected[0]["sub_id"], 0, rejected[0]["sim"]))
            rng.shuffle(pairs)
            text = texts[unit_id]["text"]
            title = texts[unit_id].get("title", "")
            body = text[len(title):].lstrip(". ") if text.startswith(title) else text
            page_subs = []
            for sid, grade, sim in pairs:
                n = len(rows) + 1
                s = subs[sid]
                on_label = payload["on_labels"][s["on"]]
                par_id = f"{domain}|{unit_id}|{sid}"
                rows.append({"par_id": par_id, "domain": domain, "unit_id": unit_id,
                             "sub_id": sid, "model_grade": grade, "sim": sim})
                page_subs.append({"id": f"v{n:03d}", "par_id": par_id, "sub": s["label"],
                                  "tema": s["tema"], "on": s["on"], "on_label": on_label,
                                  "ae": desc.get((s["tema"], s["label"]), [])[:2]})
            page_units.append({"tipo": "proyecto" if domain == "projects" else "publicacion",
                               "titulo": clean(title), "texto": clean(body)[:4000],
                               "subs": page_subs})
    rng.shuffle(page_units)
    with SAMPLE.open("w", encoding="utf-8") as handle:
        for r in rows:
            handle.write(json.dumps(r, ensure_ascii=False) + "\n")
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["par_id", "grado_0_1_2", "comentario"])
        for r in rows:
            w.writerow([r["par_id"], "", ""])
    (OUT / "pagina_datos.json").write_text(json.dumps(page_units, ensure_ascii=False),
                                           encoding="utf-8")
    n_conf = sum(1 for r in rows if r["model_grade"] >= 1)
    print(f"{len(page_units)} unidades, {len(rows)} pares ({n_conf} confirmados por el modelo, "
          f"{len(rows) - n_conf} rechazados) -> {OUT.relative_to(ROOT)}")


def cmd_report(_args):
    sample = {json.loads(l)["par_id"]: json.loads(l) for l in SAMPLE.open(encoding="utf-8")}
    human = {}
    with CSV_PATH.open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row["grado_0_1_2"].strip() in ("0", "1", "2"):
                human[row["par_id"]] = int(row["grado_0_1_2"])
    if not human:
        raise SystemExit("Aun no hay calificaciones humanas en el CSV.")
    lines = ["# Validación humana de la salida CEPLAN", "",
             f"{len(human)} de {len(sample)} pares calificados.", "",
             "| Dominio | Vínculos del modelo | Precisión (humano ≥ 1) | Precisión grado 2 "
             "(humano = 2 entre los grado 2 del modelo) | Rechazados que el humano ve relacionados |",
             "|---|---:|---:|---:|---:|"]
    for domain in list(RUNS) + ["todos"]:
        keys = [k for k in human if domain == "todos" or sample[k]["domain"] == domain]
        conf = [k for k in keys if sample[k]["model_grade"] >= 1]
        g2 = [k for k in keys if sample[k]["model_grade"] == 2]
        rej = [k for k in keys if sample[k]["model_grade"] == 0]

        def rate(ks, ok):
            return f"{sum(1 for k in ks if ok(k)) / len(ks):.0%} ({len(ks)})" if ks else "—"
        lines.append(f"| {domain} | {len(conf)} | {rate(conf, lambda k: human[k] >= 1)} | "
                     f"{rate(g2, lambda k: human[k] == 2)} | {rate(rej, lambda k: human[k] >= 1)} |")
    (OUT / "reporte_validacion.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sample")
    sub.add_parser("report")
    args = parser.parse_args()
    {"sample": cmd_sample, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()

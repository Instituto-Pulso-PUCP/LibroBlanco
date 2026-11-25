#!/usr/bin/env python3
"""Plan «Riesgos de IA (MIT)»: policies.csv desde el MIT AI Risk Repository.

Fuente: https://airisk.mit.edu/risks (CC BY 4.0; Slattery et al. 2024,
arXiv:2408.12622). Se descarga la hoja de Google Sheets como .xlsx y se deja
en datos/plans/mit_airisk/ (datos/ no se versiona):

    curl -L -o datos/plans/mit_airisk/AI_Risk_Repository_v4.xlsx \\
      "https://docs.google.com/spreadsheets/d/15LeHcpeuZC9txkvcaMoh3sUhkMvdMMry69xxXL46DT0/export?format=xlsx"
    python scripts/plans/mit_airisk.py

Que se toma (ver lb_plans, plan `mit_airisk`):
  - Hojas: los 24 sub-dominios de la Domain Taxonomy (hoja «Domain Taxonomy
    of AI Risks v1»). Nivel 1: los 7 dominios. Dos niveles, sin l2.
  - `label`: el nombre en espanol de LABELS_ES, con «de la IA» explicito: el
    verificador solo ve label + dominio, y sin la IA en el nombre «Daño
    ambiental» o «Discriminación» calzarian con investigacion que no trata
    de IA.
  - `text` (lo que se embebe): dominio, sub-dominio y descripcion oficiales
    del MIT, mas hasta N_EXAMPLES nombres de riesgos de la base («AI Risk
    Database v4») clasificados en ese sub-dominio. En ingles, como la
    fuente: ceplan_units traduce cada hoja con Plan.translate_system (aqui al
    espanol) y toma la mejor de las dos similitudes, asi que el sentido de la
    traduccion no cambia nada.
  - No se toman: la Causal Taxonomy (entidad / intencion / momento: dice como
    ocurre un riesgo, no de que tema es), los riesgos sueltos como hojas
    (~1.800, muy solapados, ~200 sin descripcion), las categorias del MIT
    «X.0 Other» / «X.1 Excluded» ni las clasificadas solo a nivel dominio.

Si el MIT cambia la taxonomia (p.ej. paso de 23 a 24 sub-dominios entre
versiones), el script falla en vez de escribir un plan a medias: hay que
revisar LABELS_ES.
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

import openpyxl

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_DIR = REPO_ROOT / "datos" / "plans" / "mit_airisk"
DEFAULT_XLSX = PLAN_DIR / "AI_Risk_Repository_v4.xlsx"
TAXONOMY_SHEET = "Domain Taxonomy of AI Risks v1"
DATABASE_SHEET = "AI Risk Database v4"
N_EXAMPLES = 6

DOMAINS_ES = {
    "1": "Discriminación y toxicidad",
    "2": "Privacidad y seguridad",
    "3": "Desinformación",
    "4": "Actores maliciosos",
    "5": "Interacción humano-IA",
    "6": "Socioeconómico y ambiental",
    "7": "Seguridad, fallas y limitaciones de los sistemas de IA",
}

LABELS_ES = {
    "1.1": "Discriminación injusta y representación sesgada por la IA",
    "1.2": "Exposición a contenido tóxico generado o difundido por la IA",
    "1.3": "Desempeño desigual de la IA entre grupos",
    "2.1": "Vulneración de la privacidad por la IA",
    "2.2": "Vulnerabilidades y ataques a sistemas de IA",
    "3.1": "Información falsa o engañosa producida por la IA",
    "3.2": "Contaminación del ecosistema informativo por la IA",
    "4.1": "Desinformación, vigilancia e influencia a gran escala con IA",
    "4.2": "Ciberataques, armas y daño masivo con IA",
    "4.3": "Fraude, estafas y manipulación dirigida con IA",
    "5.1": "Dependencia excesiva y uso inseguro de la IA",
    "5.2": "Pérdida de agencia y autonomía humana ante la IA",
    "6.1": "Concentración de poder y reparto injusto de los beneficios de la IA",
    "6.2": "Desigualdad y deterioro del empleo por la IA",
    "6.3": "Devaluación económica y cultural del trabajo humano por la IA",
    "6.4": "Carrera competitiva por desarrollar IA",
    "6.5": "Fallas de gobernanza de la IA",
    "6.6": "Daño ambiental de la IA",
    "7.1": "IA con objetivos en conflicto con los valores humanos (desalineamiento)",
    "7.2": "IA con capacidades peligrosas",
    "7.3": "Falta de capacidad o robustez de la IA",
    "7.4": "Falta de transparencia o interpretabilidad de la IA",
    "7.5": "Bienestar y derechos de la IA",
    "7.6": "Riesgos de sistemas multiagente de IA",
}

FIELDS = ["policy_id", "label", "text", "l1_id", "l1_label", "l2_id", "l2_label",
          "name_en", "domain_en", "description_en", "examples_en", "num_risks"]

_SUB_ID = re.compile(r"^(\d)\.(\d)$")
# Prefijos de numeracion de los marcos de origen: «Type 1:», «Risk area 5:», «1.2», «(a)»...
_ENUM = re.compile(r"^\s*(?:(?:type|risk area|area|category|harm|risk)\s*\d+[a-z]?\s*[:.\-–]\s*"
                   r"|\(?[0-9ivx]+(?:\.[0-9]+)*[.)]\s+|\([a-z]\)\s+)", re.I)


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def read_taxonomy(wb) -> tuple[dict, dict]:
    """{sub_id: (nombre, descripcion)}, {dominio_id: nombre} desde la hoja de la taxonomia."""
    subs, domains, current = {}, {}, None
    for row in wb[TAXONOMY_SHEET].iter_rows(values_only=True):
        cells = [clean(c) for c in row]
        for i, cell in enumerate(cells):
            m = re.fullmatch(r"(\d)\.0", cell)
            if m and i + 1 < len(cells) and cells[i + 1]:
                current = m.group(1)
                domains[current] = cells[i + 1]
            m = _SUB_ID.match(cell)
            if m and m.group(2) != "0" and i + 2 < len(cells) and cells[i + 1]:
                if m.group(1) != current:
                    raise ValueError(f"sub-dominio {cell} fuera de su dominio ({current})")
                subs[cell] = (cells[i + 1], cells[i + 2])
    return subs, domains


def read_examples(wb) -> tuple[dict, dict]:
    """{sub_id: [nombres de riesgo]} (hasta N_EXAMPLES) y {sub_id: num. de riesgos}.

    Orden: primero los nombres que aparecen en mas marcos distintos (los mas
    generales), despues uno por marco, en el orden de la base (Ev_ID). Solo
    riesgos con descripcion; sin repetir nombres."""
    rows = list(wb[DATABASE_SHEET].iter_rows(values_only=True))
    header_at = next(i for i, r in enumerate(rows) if r and "Ev_ID" in r)
    header = rows[header_at]
    col = {name: header.index(name) for name in
           ("Paper_ID", "Category level", "Risk category", "Risk subcategory", "Description",
            "Sub-domain")}
    counts = defaultdict(int)
    by_name = defaultdict(lambda: {"papers": set(), "first": None, "label": ""})
    for order, r in enumerate(rows[header_at + 1:]):
        if r[col["Category level"]] not in ("Risk Category", "Risk Sub-Category"):
            continue
        sub = clean(r[col["Sub-domain"]]).split(" ", 1)[0]
        if not _SUB_ID.match(sub) or sub.endswith(".0"):
            continue
        counts[sub] += 1
        if not clean(r[col["Description"]]):
            continue
        name = _ENUM.sub("", clean(r[col["Risk subcategory"]]) or clean(r[col["Risk category"]]))
        name = name.strip(" .:;-–")
        if not 4 <= len(name) <= 80:
            continue
        entry = by_name[(sub, name.lower())]
        entry["papers"].add(r[col["Paper_ID"]])
        entry["label"] = entry["label"] or name
        entry["first"] = order if entry["first"] is None else entry["first"]
    picked = defaultdict(list)
    ranked = sorted(by_name.items(), key=lambda kv: (-len(kv[1]["papers"]), kv[1]["first"]))
    used_papers = defaultdict(set)
    picked_words = defaultdict(list)
    for (sub, _key), e in ranked:
        if len(picked[sub]) >= N_EXAMPLES:
            continue
        if len(e["papers"]) == 1 and e["papers"] <= used_papers[sub]:
            continue  # un nombre de un marco que ya aporto ejemplo: diversidad de fuentes
        words = _words(e["label"])
        # «Hallucinations» tras «Hallucination», «Copyright infringement» tras «Copyright»:
        # no agregan nada al embedding.
        if any(words <= w or w <= words for w in picked_words[sub]):
            continue
        picked[sub].append(e["label"])
        picked_words[sub].append(words)
        used_papers[sub] |= e["papers"]
    return picked, counts


_STOP = {"and", "of", "the", "to", "for", "by", "in", "on", "with", "a", "an", "or", "due"}


def _words(name: str) -> frozenset:
    return frozenset(w.rstrip("s") for w in re.findall(r"[a-z]+", name.lower()) if w not in _STOP)


def leaf_text(domain_en: str, name_en: str, description: str, examples: list[str]) -> str:
    text = (f"Risks of artificial intelligence. Domain: {domain_en}. Subdomain: {name_en}. "
            f"{description.rstrip('.')}.")
    if examples:
        text += " Examples of risks: " + "; ".join(examples) + "."
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    parser.add_argument("--out", type=Path, default=PLAN_DIR / "policies.csv")
    args = parser.parse_args()

    wb = openpyxl.load_workbook(args.xlsx, read_only=True, data_only=True)
    subs, domains = read_taxonomy(wb)
    if set(subs) != set(LABELS_ES) or set(domains) != set(DOMAINS_ES):
        raise SystemExit(
            "La taxonomia del MIT no coincide con LABELS_ES / DOMAINS_ES:\n"
            f"  sub-dominios nuevos: {sorted(set(subs) - set(LABELS_ES))}\n"
            f"  sub-dominios que faltan: {sorted(set(LABELS_ES) - set(subs))}\n"
            f"  dominios: {sorted(domains)}")
    examples, counts = read_examples(wb)

    rows = []
    for sub_id in sorted(subs, key=lambda s: tuple(map(int, s.split(".")))):
        name_en, desc = subs[sub_id]
        dom = sub_id.split(".")[0]
        rows.append({
            "policy_id": sub_id, "label": LABELS_ES[sub_id],
            "text": leaf_text(domains[dom], name_en, desc, examples[sub_id]),
            "l1_id": dom, "l1_label": DOMAINS_ES[dom], "l2_id": "", "l2_label": "",
            "name_en": name_en, "domain_en": domains[dom], "description_en": desc,
            "examples_en": " | ".join(examples[sub_id]), "num_risks": counts[sub_id],
        })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"-> {args.out} ({len(rows)} categorias de riesgo, {len(domains)} dominios, "
          f"{sum(counts.values())} riesgos de la base clasificados en ellas)")


if __name__ == "__main__":
    main()

"""Prepara "unidades" de texto por publicación para el pipeline de extraccion
y normalizacion tematica (ver docs/topic_normalization_pipeline.md), version
publicaciones.

Analogo a topic_extraction_prep.py (que hace lo mismo para proyectos), pero
usando como fuente los resultados declarados y vinculados de los proyectos
cerrados 2010-2020: `salidas/07_project_publication_ground_truth.csv`
(1,192 resultados declarados de 335 de los 893 proyectos cerrados; subconjunto
vetted/deduplicado de `06_project_results_ground_truth.csv`, que tiene 2,908
filas sin vetear). Se usa ground truth y no el catalogo general de
publicaciones PUCP (`03_publications_master.csv`, 14,062 filas no ligadas a
proyectos especificos) porque el objetivo es trazar temas desde un resultado
declarado hasta su proyecto de origen, igual que con los proyectos.

Cada fila de la fuente es un resultado declarado (articulo, capitulo de
libro, memoria de congreso, etc.), no necesariamente con datos bibliograficos
completos: el titulo (`result_title`) siempre esta presente, pero el resumen
y las palabras clave -la fuente real de senal tematica- solo en 562 de las
1,192 filas (47%), proviniendo de hasta 5 fuentes posibles por campo
(resumen/palabras_clave "ground truth" > OpenAlex > Scopus/fuente original),
de ahi el fallback chain en `build_text`.

Uso:
    python scripts/analysis/publication_extraction_prep.py
    python scripts/analysis/publication_extraction_prep.py --sample 60 --seed 42
    python scripts/analysis/publication_extraction_prep.py --full --out salidas/topics/all_publication_units.json
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = REPO_ROOT / "salidas" / "07_project_publication_ground_truth.csv"
DEFAULT_PROJECTS = REPO_ROOT / "salidas" / "01_projects_closed_con_cris.csv"
DEFAULT_OUTPUT = REPO_ROOT / "salidas" / "topics" / "publications_units_sample.json"
DEFAULT_PROCESSED_IDS = REPO_ROOT / "salidas" / "topics" / "publications_processed_ids.json"

UNIT_FIELDS = [
    "unit_id",
    "title",
    "year",
    "result_type",
    "journal",
    "project_id",
    "project_title",
    "executing_unit",
    "knowledge_area",
    "text",
    "text_sources",
]

# Fallback chains: prefer the ground-truth-curated field, then OpenAlex, then
# the original matched source (Scopus/RI/WOS via source_abstract/keywords).
ABSTRACT_FIELDS = ["resumen", "openalex_abstract", "source_abstract"]
KEYWORD_FIELDS = ["palabras_clave", "source_keywords"]


def load_executing_units(path: Path) -> dict[str, dict]:
    """project_id -> {executing_unit, knowledge_area}, para dar contexto a
    cada publicacion igual que lo tiene cada proyecto."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return {
        row["project_id"].strip(): {
            "executing_unit": row.get("executing_unit", "").strip(),
            "knowledge_area": row.get("knowledge_area", "").strip(),
        }
        for row in rows
    }


def clean_pipe_list(value: str) -> str:
    """source_keywords viene de un merge de listas con huecos; algunos huecos
    quedaron como el literal "nan" (103 filas) en vez de string vacio."""
    tokens = [tok.strip() for tok in value.split("|")]
    return " | ".join(tok for tok in tokens if tok and tok.lower() != "nan")


def first_nonempty(row: dict, fields: list[str]) -> tuple[str, str]:
    """Devuelve (valor, nombre_del_campo) del primer campo no vacio en
    `fields`, o ("", "") si ninguno tiene texto util."""
    for field in fields:
        value = row.get(field, "").strip()
        if value and value != "-":
            if "|" in value:
                value = clean_pipe_list(value)
            if value:
                return value, field
    return "", ""


def has_text(row: dict) -> bool:
    abstract, _ = first_nonempty(row, ABSTRACT_FIELDS)
    keywords, _ = first_nonempty(row, KEYWORD_FIELDS)
    return bool(abstract or keywords)


def build_unit(row: dict, project_context: dict[str, dict]) -> dict:
    title = row.get("result_title", "").strip()
    abstract, abstract_source = first_nonempty(row, ABSTRACT_FIELDS)
    keywords, keywords_source = first_nonempty(row, KEYWORD_FIELDS)

    text_parts = []
    text_sources = []
    if title:
        text_parts.append(title)
        text_sources.append("result_title")
    if abstract:
        text_parts.append(abstract)
        text_sources.append(abstract_source)
    if keywords:
        text_parts.append(f"Palabras clave: {keywords}")
        text_sources.append(keywords_source)

    project_id = row.get("project_id", "").strip()
    context = project_context.get(project_id, {})

    return {
        "unit_id": f"{project_id}_{row.get('cod_prod', '').strip()}",
        "title": title,
        "year": row.get("result_year", "").strip(),
        "result_type": row.get("result_type", "").strip(),
        "journal": row.get("journal_raw", "").strip(),
        "project_id": project_id,
        "project_title": row.get("project_title", "").strip(),
        "executing_unit": context.get("executing_unit", ""),
        "knowledge_area": context.get("knowledge_area", ""),
        "text": "\n\n".join(text_parts),
        "text_sources": text_sources,
    }


def load_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_processed_ids(path: Path) -> set[str]:
    """Union de todos los unit_id ya extraidos en lotes previos (mismo
    formato que el manifest de proyectos: {"pilot": [...], "batch01": [...]})."""
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as f:
        manifest = json.load(f)
    ids: set[str] = set()
    for batch_ids in manifest.values():
        ids.update(batch_ids)
    return ids


def stratified_sample(rows: list[dict], n: int, seed: int, by: str) -> list[dict]:
    """Muestreo aleatorio estratificado proporcional por columna `by`,
    limitado a filas con texto disponible (ver `has_text`)."""
    pool = [r for r in rows if has_text(r)]
    groups: dict[str, list[dict]] = {}
    for row in pool:
        groups.setdefault(row.get(by, "").strip(), []).append(row)

    rng = random.Random(seed)
    total = len(pool)
    sample: list[dict] = []
    for key, group_rows in groups.items():
        if not key:
            continue
        rng.shuffle(group_rows)
        quota = max(1, round(n * len(group_rows) / total))
        sample.extend(group_rows[:quota])
    return sample[:n]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--projects", type=Path, default=DEFAULT_PROJECTS,
                         help="CSV de proyectos, usado para anotar executing_unit/knowledge_area por publicacion")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample", type=int, default=60, help="tamano de la muestra (ignorado con --full)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--stratify-by", default="result_type")
    parser.add_argument("--full", action="store_true", help="exporta todas las filas con texto disponible, sin muestrear")
    parser.add_argument("--processed-ids", type=Path, default=DEFAULT_PROCESSED_IDS,
                         help="JSON con los unit_id ya procesados en lotes anteriores; se excluyen del muestreo/export.")
    parser.add_argument("--no-exclude-processed", action="store_true",
                         help="no excluir los unit_id ya listados en --processed-ids")
    args = parser.parse_args()

    rows = load_rows(args.input)
    project_context = load_executing_units(args.projects)

    if not args.no_exclude_processed:
        processed = load_processed_ids(args.processed_ids)
        if processed:
            before = len(rows)
            rows = [
                r for r in rows
                if f"{r.get('project_id', '').strip()}_{r.get('cod_prod', '').strip()}" not in processed
            ]
            print(f"Excluidos {before - len(rows)} resultados ya procesados (de {args.processed_ids.name})")

    if args.full:
        selected = [r for r in rows if has_text(r)]
    else:
        selected = stratified_sample(rows, args.sample, args.seed, args.stratify_by)

    units = [build_unit(row, project_context) for row in selected]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(units, f, ensure_ascii=False, indent=2)

    print(f"{len(units)} unidades escritas en {args.out}")


if __name__ == "__main__":
    main()

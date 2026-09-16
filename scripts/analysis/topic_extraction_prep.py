"""Prepara "unidades" de texto por proyecto para el pipeline de extraccion y
normalizacion tematica (ver docs/topic_normalization_pipeline.md).

Este es el primer paso de un sistema pensado para ser replicable con otros
datasets: fija un esquema de columnas de salida estable (ver UNIT_FIELDS)
independiente de las columnas de origen, para que el resto del pipeline
(extraccion de temas, normalizacion, contraste con un objetivo) no dependa
del esquema crudo del CSV de proyectos.

Uso:
    python scripts/analysis/topic_extraction_prep.py
    python scripts/analysis/topic_extraction_prep.py --sample 40 --seed 42
    python scripts/analysis/topic_extraction_prep.py --full --out salidas/topics/all_units.json

Por defecto usa `salidas/01_projects_closed_con_cris.csv` y genera una
muestra estratificada por `executing_unit` (mismo criterio usado para el
piloto de 36 proyectos en `salidas/topics/`), porque extraer y normalizar
temas es hoy un paso hecho por un LLM leyendo cada unidad (no hay una
API/clave configurada en este entorno para automatizarlo por script) y
conviene validar calidad en una muestra chica antes de escalar a las ~980
filas del universo completo.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = REPO_ROOT / "salidas" / "01_projects_closed_con_cris.csv"
DEFAULT_RESULTS = REPO_ROOT / "salidas" / "06_project_results_ground_truth.csv"
DEFAULT_OUTPUT = REPO_ROOT / "salidas" / "topics" / "projects_units_sample.json"
DEFAULT_PROCESSED_IDS = REPO_ROOT / "salidas" / "topics" / "processed_ids.json"
MAX_RESULTS_PER_PROJECT = 5

# Columnas fijas de salida (el "esquema" replicable). Cualquier dataset nuevo
# solo necesita mapear sus propias columnas a estos nombres antes de este
# paso para reusar el resto del pipeline.
UNIT_FIELDS = [
    "unit_id",
    "title",
    "year",
    "project_type",
    "knowledge_area",
    "executing_unit",
    "executing_section",
    "funding_type",
    "research_lines",
    "text",
    "text_sources",
]

TEXT_SOURCE_COLUMNS = ["cris_abstract", "cris_keywords", "cris_fos"]
RESEARCH_LINE_COLUMNS = [
    "research_line_1",
    "research_line_2",
    "research_line_3",
    "research_line_4",
    "research_line",
]


def load_results_by_project(path: Path) -> dict[str, list[dict]]:
    """Agrupa resultados declarados (salidas/06_project_results_ground_truth.csv)
    por project_id, para usarlos como texto adicional/de respaldo: son los
    "resultados publicados" que, junto con el resumen y las keywords, Enrique
    pidio explicitamente como insumo de la extraccion de temas."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    by_project: dict[str, list[dict]] = {}
    for row in rows:
        by_project.setdefault(row.get("project_id", "").strip(), []).append(row)
    return by_project


def declared_results_text(rows: list[dict]) -> str:
    """Para cada resultado declarado de un proyecto, arma una linea
    "titulo: resumen" usando el mejor texto disponible (openalex_abstract >
    source_abstract > solo el titulo), limitado a MAX_RESULTS_PER_PROJECT
    para no diluir el resto de la unidad en proyectos con muchos resultados."""
    lines = []
    for row in rows[:MAX_RESULTS_PER_PROJECT]:
        title = row.get("result_title", "").strip()
        if not title or title == "-":
            continue
        abstract = (
            row.get("openalex_abstract", "").strip()
            or row.get("source_abstract", "").strip()
        )
        if abstract and abstract != "-":
            lines.append(f"{title}: {abstract}")
        else:
            lines.append(title)
    return "\n".join(lines)


def build_unit(row: dict, results_by_project: dict[str, list[dict]] | None = None) -> dict:
    research_lines = sorted(
        {row.get(c, "").strip() for c in RESEARCH_LINE_COLUMNS if row.get(c, "").strip()}
    )

    text_parts = []
    text_sources = []
    for col in TEXT_SOURCE_COLUMNS:
        value = row.get(col, "").strip()
        if value:
            text_parts.append(value.replace("||", "; "))
            text_sources.append(col)

    if results_by_project:
        result_rows = results_by_project.get(row["project_id"], [])
        results_text = declared_results_text(result_rows)
        if results_text:
            text_parts.append(results_text)
            text_sources.append("declared_results")

    return {
        "unit_id": row["project_id"],
        "title": row.get("title", "").strip(),
        "year": row.get("year", "").strip(),
        "project_type": row.get("project_type", "").strip(),
        "knowledge_area": row.get("knowledge_area", "").strip(),
        "executing_unit": row.get("executing_unit", "").strip(),
        "executing_section": row.get("executing_section", "").strip(),
        "funding_type": row.get("funding_type", "").strip(),
        "research_lines": research_lines,
        "text": "\n\n".join(text_parts),
        "text_sources": text_sources,
    }


def load_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_processed_ids(path: Path) -> set[str]:
    """Union of all project_ids already extracted in prior batches (see
    `processed_ids.json`: {"pilot": [...], "batch01": [...], ...}), so a new
    batch never re-samples an already-processed project."""
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as f:
        manifest = json.load(f)
    ids: set[str] = set()
    for batch_ids in manifest.values():
        ids.update(batch_ids)
    return ids


def has_text(row: dict, results_by_project: dict[str, list[dict]] | None = None) -> bool:
    if any(row.get(c, "").strip() for c in TEXT_SOURCE_COLUMNS):
        return True
    if results_by_project:
        return bool(declared_results_text(results_by_project.get(row["project_id"], [])))
    return False


def stratified_sample(
    rows: list[dict], n: int, seed: int, by: str, results_by_project: dict[str, list[dict]] | None = None
) -> list[dict]:
    """Muestreo aleatorio estratificado proporcional por columna `by`,
    limitado a filas con texto disponible (ver `has_text`)."""
    pool = [r for r in rows if has_text(r, results_by_project)]
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
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS,
                         help="CSV de resultados declarados por proyecto, usado como texto de respaldo/enriquecimiento")
    parser.add_argument("--no-results", action="store_true", help="no usar resultados declarados como texto")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample", type=int, default=36, help="tamano de la muestra (ignorado con --full)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--stratify-by", default="executing_unit")
    parser.add_argument("--full", action="store_true", help="exporta todas las filas con texto disponible, sin muestrear")
    parser.add_argument("--processed-ids", type=Path, default=DEFAULT_PROCESSED_IDS,
                         help="JSON con los project_id ya procesados en lotes anteriores "
                              "(ver processed_ids.json); se excluyen del muestreo/export para "
                              "no repetir proyectos entre lotes.")
    parser.add_argument("--no-exclude-processed", action="store_true",
                         help="no excluir los project_id ya listados en --processed-ids")
    args = parser.parse_args()

    rows = load_rows(args.input)
    results_by_project = {} if args.no_results else load_results_by_project(args.results)

    if not args.no_exclude_processed:
        processed = load_processed_ids(args.processed_ids)
        if processed:
            before = len(rows)
            rows = [r for r in rows if r.get("project_id", "").strip() not in processed]
            print(f"Excluidos {before - len(rows)} proyectos ya procesados (de {args.processed_ids.name})")

    if args.full:
        selected = [r for r in rows if has_text(r, results_by_project)]
    else:
        selected = stratified_sample(rows, args.sample, args.seed, args.stratify_by, results_by_project)

    units = [build_unit(row, results_by_project) for row in selected]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(units, f, ensure_ascii=False, indent=2)

    print(f"{len(units)} unidades escritas en {args.out}")


if __name__ == "__main__":
    main()

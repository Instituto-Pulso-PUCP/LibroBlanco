"""Renders the topic-explorer HTML (temas extraidos -> temas normalizados,
con trazabilidad completa) from a topics JSON produced by
`topic_extraction_prep.py` + a manual/LLM extraction+normalization pass.

Uso:
    python scripts/analysis/build_topic_explorer.py
    python scripts/analysis/build_topic_explorer.py \
        --data salidas/topics/projects_topics_pilot.json \
        --out salidas/topics/explorador_temas_proyectos_piloto.html
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = REPO_ROOT / "scripts" / "analysis" / "templates" / "topic_explorer_template.html"
DEFAULT_DATA = REPO_ROOT / "salidas" / "topics" / "projects_topics_pilot.json"
DEFAULT_OUT = REPO_ROOT / "salidas" / "topics" / "explorador_temas_proyectos_piloto.html"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--page-title", default="Explorador de temas — Proyectos PUCP")
    parser.add_argument("--subtitle", default="Proyecto → tema extraído (con evidencia) → tema normalizado",
                         help="Texto bajo el titulo, describe el flujo de trazabilidad")
    parser.add_argument("--stat-label", default="proyectos",
                         help="Palabra junto al conteo total en la cabecera")
    parser.add_argument("--search-placeholder", default="Buscar proyecto, tema, evidencia o tema normalizado")
    parser.add_argument("--list-heading", default="Proyectos y temas extraídos")
    parser.add_argument("--empty-message", default="No hay proyectos que coincidan con la búsqueda o filtro.")
    parser.add_argument("--count-unit", default="proyectos",
                         help="Palabra usada en los chips '<N> <count-unit>'")
    parser.add_argument("--item-label", default="Proyecto",
                         help="Etiqueta por defecto para una unidad individual sin campo 'track'")
    parser.add_argument("--connected-label", default="Proyectos conectados")
    args = parser.parse_args()

    with args.data.open(encoding="utf-8") as f:
        data = json.load(f)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template.replace("__PAGE_TITLE__", args.page_title)
    html = html.replace("__SUBTITLE__", args.subtitle)
    html = html.replace("__STAT_LABEL__", args.stat_label)
    html = html.replace("__SEARCH_PLACEHOLDER__", args.search_placeholder)
    html = html.replace("__LIST_HEADING__", args.list_heading)
    html = html.replace("__EMPTY_MESSAGE__", args.empty_message)
    html = html.replace("__COUNT_UNIT__", args.count_unit)
    html = html.replace("__ITEM_LABEL__", args.item_label)
    html = html.replace("__CONNECTED_LABEL__", args.connected_label)
    html = html.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"Explorador escrito en {args.out}")


if __name__ == "__main__":
    main()

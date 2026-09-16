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
    args = parser.parse_args()

    with args.data.open(encoding="utf-8") as f:
        data = json.load(f)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template.replace("__PAGE_TITLE__", args.page_title)
    html = html.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"Explorador escrito en {args.out}")


if __name__ == "__main__":
    main()

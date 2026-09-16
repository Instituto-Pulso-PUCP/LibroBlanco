"""Renders the topic <-> national-policy alignment explorer HTML from
`topic_policy_alignment_<model>.json` (see build_topic_policy_alignment.py).

Uso:
    python scripts/analysis/build_policy_alignment_explorer.py
    python scripts/analysis/build_policy_alignment_explorer.py \
        --data salidas/topics/topic_policy_alignment_minilm-multilingual.json \
        --out salidas/topics/explorador_alineacion_politicas.html
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = REPO_ROOT / "scripts" / "analysis" / "templates" / "policy_alignment_explorer_template.html"
DEFAULT_DATA = REPO_ROOT / "salidas" / "topics" / "topic_policy_alignment_minilm-multilingual.json"
DEFAULT_OUT = REPO_ROOT / "salidas" / "topics" / "explorador_alineacion_politicas.html"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--page-title", default="Atlas de Temas: Alineación con Políticas Nacionales")
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

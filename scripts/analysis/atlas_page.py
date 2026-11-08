"""Arma la pagina del Atlas Temático a partir de sus fuentes.

Las fuentes viven separadas para poder mantenerlas:

    templates/atlas/index.html   estructura (enlaza atlas.css y atlas.js)
    templates/atlas/atlas.css    estilos (identidad PUCP)
    templates/atlas/atlas.js     comportamiento

La salida es un solo HTML con el CSS y el JS incrustados, para que
atlas_<dataset>.html siga funcionando como archivo unico abierto desde el disco.
La usan build_atlas.py (al construir) y serve_atlas.py (en cada pedido).
"""
from __future__ import annotations

import json
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "templates" / "atlas"

CSS_LINK = '<link rel="stylesheet" href="atlas.css">'
JS_LINK = '<script src="atlas.js"></script>'
BUNDLE = "__BUNDLE__"


def _source(name: str) -> str:
    text = (SRC_DIR / name).read_text(encoding="utf-8").rstrip("\n")
    # Cerraria antes de tiempo el <style> o el <script> que la incrusta.
    if "</style" in text.lower() or "</script" in text.lower():
        raise ValueError(f"{name} contiene </style o </script")
    return text


def _replace_once(html: str, old: str, new: str) -> str:
    if html.count(old) != 1:
        raise ValueError(f"index.html debe tener exactamente un {old!r}")
    return html.replace(old, new)


def render(bundle=None) -> str:
    """La pagina completa. bundle=None: la pagina carga datasets.json."""
    blob = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
    blob = blob.replace("</", "<\\/")   # romperia el <script> que la incrusta
    html = (SRC_DIR / "index.html").read_text(encoding="utf-8")
    html = _replace_once(html, CSS_LINK, "<style>\n" + _source("atlas.css") + "\n</style>")
    html = _replace_once(html, JS_LINK, "<script>\n" + _source("atlas.js") + "\n</script>")
    return _replace_once(html, BUNDLE, blob)

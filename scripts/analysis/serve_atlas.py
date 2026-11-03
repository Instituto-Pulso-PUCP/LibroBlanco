#!/usr/bin/env python3
"""Servidor local para trabajar en la plantilla del Atlas Temático.

Sirve templates/atlas_template.html leida de nuevo en cada pedido (con
__BUNDLE__ = null, igual que el index.html que escribe build_atlas.py) y los
datos ya construidos de salidas/topics/atlas/. Editar la plantilla, guardar y
recargar el navegador: no hace falta volver a construir.

    python scripts/analysis/serve_atlas.py          # http://localhost:8000/?ds=ecotec

Los datos (datasets.json, data/<id>.json) salen de build_atlas.py, que necesita
RDS: se construyen en el servidor y se copian a salidas/topics/atlas/. Solo hay
que traerlos de nuevo si cambian las corridas o atlas_profiles.py.
"""
from __future__ import annotations

import argparse
import functools
import http.server
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).resolve().parent / "templates" / "atlas_template.html"


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html"):
            body = TEMPLATE.read_text(encoding="utf-8").replace("__BUNDLE__", "null").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def end_headers(self):
        # Los JSON tambien sin cache: tras traer datos nuevos basta con recargar.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "salidas" / "topics" / "atlas")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not (args.data_dir / "datasets.json").exists():
        raise SystemExit(f"Falta {args.data_dir / 'datasets.json'}: construir con build_atlas.py "
                         "(en el servidor) y copiar la carpeta aqui.")
    handler = functools.partial(Handler, directory=str(args.data_dir))
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as srv:
        print(f"Atlas en http://localhost:{args.port}/  (plantilla: {TEMPLATE.relative_to(ROOT)})")
        print("Editar la plantilla y recargar. Ctrl+C para parar.")
        srv.serve_forever()


if __name__ == "__main__":
    main()

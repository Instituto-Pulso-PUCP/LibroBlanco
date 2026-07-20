#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${ELSEVIER_API_KEY:-}" ]]; then
  echo "ERROR: defina ELSEVIER_API_KEY antes de ejecutar." >&2
  exit 2
fi

python resumenes_por_doi.py doi_ejemplo.csv \
  -o resultados.csv \
  --timeout 30 \
  --reintentos 2

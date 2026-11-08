#!/usr/bin/env bash
#
# Actualiza el atlas del servidor en un solo paso: trae el codigo, reconstruye
# cada dataset publicado con las mismas corridas y lo publica.
#
#   ./scripts/analysis/rebuild_atlas.sh
#
# Las corridas salen de salidas/topics/atlas/datasets.json (lo que esta
# publicado ahora). Para cambiar de corrida, construir ese dataset a mano una
# vez con build_atlas.py --run ...; desde ahi este script usa la nueva.
set -euo pipefail
cd "${LIBROBLANCO_DIR:-$(dirname "$0")/../..}"

# git pull puede cambiar este mismo archivo mientras bash lo lee: se trae el
# codigo primero y se vuelve a lanzar el script ya actualizado.
if [ -z "${ATLAS_PULLED:-}" ]; then
  git pull --ff-only
  ATLAS_PULLED=1 exec "$0" "$@"
fi

[ -f config/env.sh ] || { echo "Falta config/env.sh (ver config/env.example.sh)." >&2; exit 1; }
# shellcheck disable=SC1091
source config/env.sh

MANIFEST=salidas/topics/atlas/datasets.json
[ -f "$MANIFEST" ] || { echo "Falta $MANIFEST: construir cada dataset una vez con build_atlas.py." >&2; exit 1; }

# Una linea por dataset: "id --run dominio=corrida --run ..."
mapfile -t BUILDS < <(python3 - "$MANIFEST" <<'EOF'
import json, sys
for d in json.load(open(sys.argv[1], encoding="utf-8"))["datasets"]:
    print(d["id"], " ".join(f"--run {dom}={run}" for dom, run in d["runs"].items()))
EOF
)

for line in "${BUILDS[@]}"; do
  read -r id args <<<"$line"
  echo "== $id"
  # shellcheck disable=SC2086
  python3 scripts/analysis/build_atlas.py $args
done

./scripts/analysis/deploy_atlas.sh

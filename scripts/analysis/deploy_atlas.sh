#!/usr/bin/env bash
#
# Publica el atlas ya construido (salidas/topics/atlas/, de build_atlas.py) en
# el nginx del servidor: http://44.195.204.129/ (con usuario y clave).
#
#   python3 scripts/analysis/build_atlas.py --run ...     # uno por dataset
#   ./scripts/analysis/deploy_atlas.sh
#
# Cada publicacion es una carpeta nueva en /var/www/atlas-releases/<fecha> y
# /var/www/atlas es un enlace que se cambia de un golpe: nadie ve una version a
# medias. Se guardan las 3 ultimas; volver a la anterior:
#   sudo ln -sfn /var/www/atlas-releases/<anterior> /var/www/atlas.tmp && sudo mv -T /var/www/atlas.tmp /var/www/atlas
#
# Configuracion de nginx: /etc/nginx/sites-available/atlas (ver docs/servidor_atlas.md).
set -euo pipefail
cd "${LIBROBLANCO_DIR:-$(dirname "$0")/../..}"

SRC=salidas/topics/atlas
RELEASES=/var/www/atlas-releases
LINK=/var/www/atlas
for f in index.html datasets.json; do
  [ -f "$SRC/$f" ] || { echo "Falta $SRC/$f: correr antes build_atlas.py." >&2; exit 1; }
done

STAMP=$(date +%Y%m%d-%H%M%S)
sudo mkdir -p "$RELEASES/$STAMP"
sudo cp -r "$SRC"/. "$RELEASES/$STAMP"/
sudo chmod -R a+rX "$RELEASES/$STAMP"
sudo ln -sfn "$RELEASES/$STAMP" "$LINK.tmp"
sudo mv -T "$LINK.tmp" "$LINK"

# Solo las 3 ultimas.
ls -1d "$RELEASES"/*/ | sort | head -n -3 | xargs -r sudo rm -rf

echo "Publicado $STAMP: $(python3 -c "import json;print(', '.join(d['label'] for d in json.load(open('$SRC/datasets.json'))['datasets']))")"
echo "-> http://44.195.204.129/"

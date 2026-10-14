#!/usr/bin/env bash
# Re-corre todo el pipeline para projects y publications_linked tras un cambio
# de insumos, sin sesion interactiva. Reusa la extraccion y los embeddings de
# las corridas anteriores SOLO para unidades con texto identico
# (seed_same_text.py), asi que solo paga LLM por lo nuevo o cambiado.
#
# Uso (sobrevive al cierre de la terminal):
#   cd ~/LibroBlanco
#   setsid nohup scripts/pipeline_temas/rerun_universos.sh > /dev/null 2>&1 &
#   tail -f salidas/topics/rerun_universos.log
#
# Variables opcionales (con sus valores por defecto):
#   OLD_PROJ=full-proj-646           corrida de projects de donde se reusa
#   OLD_PUBS=publications_linked-529 corrida de publications_linked de donde se reusa
#   TAG=$(date +%Y%m%d)              sufijo de las corridas nuevas
#
# Pasos: 1 maestro de proyectos desde CRIS + resultados declarados de PULSO ->
# 2 rebuild publicaciones ligadas -> 3 por dominio:
# etapa 01, seed por texto identico, etapas 02-05 -> 4 cruce CEPLAN ->
# 5 atlas (salidas/topics/atlas.html; publicarlo es aparte).
# Al terminar escribe salidas/topics/rerun_universos.DONE (o .FAILED).
set -euo pipefail
cd "$(dirname "$0")/../.."
source config/env.sh

OLD_PROJ=${OLD_PROJ:-full-proj-646}
OLD_PUBS=${OLD_PUBS:-publications_linked-529}
TAG=${TAG:-$(date +%Y%m%d)}
NEW_PROJ="full-proj-${TAG}"
NEW_PUBS="publications_linked-${TAG}"
LOG=salidas/topics/rerun_universos.log
mkdir -p salidas/topics
rm -f salidas/topics/rerun_universos.DONE salidas/topics/rerun_universos.FAILED
exec >> "$LOG" 2>&1
trap 'echo "FALLO en la linea $LINENO ($(date))"; echo "linea $LINENO" > salidas/topics/rerun_universos.FAILED' ERR

step() { echo; echo "=== $(date '+%F %T') · $*"; }

step "inicio: $OLD_PROJ -> $NEW_PROJ · $OLD_PUBS -> $NEW_PUBS"
BK="salidas/backup_${TAG}"
mkdir -p "$BK"
for f in salidas/01_projects_closed_con_cris.csv salidas/06_project_results_ground_truth.csv \
         salidas/07_project_publication_ground_truth.csv salidas/07_publications_linked_full.csv; do
  [ -f "$BK/$(basename "$f")" ] || cp "$f" "$BK/"
done

# Desde 2026-10-13 el universo de proyectos lo definen las filas de Proyectos CRIS
# (concluido, inicio >= 2010); PULSO aporta COD_AERI y metadatos. Reemplaza a
# merge_cris_stdlib.py, que partia de los "5. Cerrado" de PULSO.
step "1/5 proyectos desde CRIS y resultados declarados"
python3 scripts/addons/build_projects_from_cris.py
python3 scripts/addons/build_declared_results.py

step "2/5 rebuild publicaciones ligadas"
python3 scripts/addons/rebuild_linked_publications.py

for pair in "projects:$OLD_PROJ:$NEW_PROJ" "publications_linked:$OLD_PUBS:$NEW_PUBS"; do
  IFS=: read -r dom old new <<< "$pair"
  step "3/5 $dom: etapa 01 ($new)"
  python3 scripts/pipeline_temas/01_prep_units.py --domain "$dom" --run-id "$new"
  step "3/5 $dom: reusar extraccion/embeddings con texto identico desde $old"
  python3 scripts/pipeline_temas/seed_same_text.py --domain "$dom" --from-run "$old" --to-run "$new"
  step "3/5 $dom: etapas 02-05"
  python3 scripts/pipeline_temas/run_domain.py --domain "$dom" --run-id "$new" --from 02
done

step "4/5 cruce CEPLAN"
for pair in "projects:$OLD_PROJ:$NEW_PROJ" "publications_linked:$OLD_PUBS:$NEW_PUBS"; do
  IFS=: read -r dom old new <<< "$pair"
  src="salidas/topics/$dom/$old/07_ceplan_judge_cache.jsonl"
  dst="salidas/topics/$dom/$new/07_ceplan_judge_cache.jsonl"
  # mismas preguntas (texto + candidatas) -> misma respuesta: no se repagan
  [ -f "$src" ] && [ ! -f "$dst" ] && cp "$src" "$dst"
done
python3 scripts/analysis/ceplan_units.py --run "projects=$NEW_PROJ" --run "publications_linked=$NEW_PUBS"

step "5/5 atlas"
python3 scripts/analysis/build_atlas.py --run "projects=$NEW_PROJ" --run "publications_linked=$NEW_PUBS"

step "listo"
echo "corridas: $NEW_PROJ · $NEW_PUBS" | tee salidas/topics/rerun_universos.DONE

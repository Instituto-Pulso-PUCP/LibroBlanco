#!/usr/bin/env bash
#
# Lanza el pipeline de temas para un dominio.
#
#   ./lanzar.sh publications_linked     # publicaciones ligadas a un proyecto (850)
#   ./lanzar.sh projects                # proyectos cerrados 2010+ (975)
#   ./lanzar.sh publications            # catalogo completo (13.995)
#
# Cada dominio tiene su PROPIO espacio de temas: no se mezclan ni se comparan.
#
# Para dominios grandes (> UMBRAL_PILOTO unidades) corre antes un piloto y una
# puerta de validacion, y solo sigue a la corrida completa si el piloto es sano.
# Para dominios chicos va directo: un piloto seria media corrida.
#
# Dejarlo corriendo y cerrar la terminal:
#   setsid nohup ./lanzar.sh publications_linked > /dev/null 2>&1 &
#
# Ver progreso:  ./estado.sh
set -uo pipefail
cd "$(dirname "$0")"

DOMINIO=${1:-}
if [ -z "$DOMINIO" ]; then
  echo "Uso: ./lanzar.sh <projects|publications|publications_linked>" >&2; exit 1
fi
UMBRAL_PILOTO=${UMBRAL_PILOTO:-2000}
PRUEBA=${PRUEBA:-}            # PRUEBA=5 -> ensaya el lanzador con 5 unidades
MUESTRA=${MUESTRA:-400}
STAMP=$(date +%Y%m%d-%H%M%S)
RUN=${RUN:-${DOMINIO}-${STAMP}}
LOG_DIR="salidas/topics/$DOMINIO"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/lanzamiento_${STAMP}.log"
ln -sfn "$(basename "$LOG")" "$LOG_DIR/ultimo.log"

[ -f config/env.sh ] || { echo "Falta config/env.sh. Ver config/env.example.sh." >&2; exit 1; }
# shellcheck disable=SC1091
source config/env.sh
export PYTHONUNBUFFERED=1     # sin esto el log parece vacio durante horas

paso () { printf '\n===== [%s] %s =====\n' "$(date +%H:%M:%S)" "$1"; }

{
  UNIDADES=$(python3 -c "
import sys; sys.path.insert(0,'scripts/lib'); import lb_domains as d
dom=d.get('$DOMINIO'); print(len(d.to_units(dom, d.read_source(dom), 6000)[0]))")
  echo "Dominio: $DOMINIO · $UNIDADES unidades · run: $RUN"

  paso "Comprobacion de infraestructura"
  python3 scripts/pipeline_temas/00_check_infra.py --domain "$DOMINIO" \
    || { echo "FALLO: infraestructura incompleta. No se lanza nada."; exit 1; }

  if [ "$UNIDADES" -gt "$UMBRAL_PILOTO" ]; then
    PILOTO="${RUN}-piloto"
    paso "Piloto de $MUESTRA unidades (run: $PILOTO)"
    python3 scripts/pipeline_temas/run_domain.py \
        --domain "$DOMINIO" --sample "$MUESTRA" --run-id "$PILOTO" \
      || { echo "FALLO en el piloto. No se lanza la corrida completa."; exit 1; }

    paso "Validacion del piloto"
    python3 scripts/pipeline_temas/validar_piloto.py \
        --domain "$DOMINIO" --run-id "$PILOTO" \
      || { echo "El piloto no pasa. No se lanza la corrida completa."; exit 1; }
  else
    echo "($UNIDADES unidades: por debajo de $UMBRAL_PILOTO, se va directo)"
  fi

  ARGS_FINAL=()
  if [ -n "$PRUEBA" ]; then
    echo "MODO PRUEBA: solo $PRUEBA unidades (quitar PRUEBA= para la corrida real)"
    ARGS_FINAL=(--sample "$PRUEBA")
  fi
  paso "Corrida completa de $UNIDADES unidades (run: $RUN)"
  echo "Interrumpible: la etapa 02 cachea cada unidad, un rerun no vuelve a pagarlas."
  python3 scripts/pipeline_temas/run_domain.py --domain "$DOMINIO" --run-id "$RUN" \
      "${ARGS_FINAL[@]}" \
    || { echo "FALLO. Reanudar con:"
         echo "  source config/env.sh"
         echo "  python3 scripts/pipeline_temas/run_domain.py --domain $DOMINIO \\"
         echo "      --run-id $RUN --from 02"; exit 1; }

  paso "LISTO"
  python3 scripts/pipeline_temas/06_estimate_full_run.py \
      --domain "$DOMINIO" --from-run "$RUN" || true
  echo "Salidas en $LOG_DIR/$RUN/"
} 2>&1 | tee -a "$LOG"

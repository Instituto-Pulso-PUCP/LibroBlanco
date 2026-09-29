#!/usr/bin/env bash
# Estado del pipeline de temas. Seguro de correr en cualquier momento.
cd "$(dirname "$0")"
DOM=${1:-publications_linked}
LOG_DIR="salidas/topics/$DOM"

echo "===== PROCESOS ====="
pgrep -af 'pipeline_temas' | grep -v estado.sh || echo "  (ninguno corriendo)"

echo; echo "===== MEMORIA ====="
free -m | awk 'NR<=2{printf "  %s\n",$0}'

echo; echo "===== ULTIMAS LINEAS DEL LOG ====="
if [ -e "$LOG_DIR/ultimo.log" ]; then
  tail -n "${2:-15}" "$LOG_DIR/ultimo.log"
else
  echo "  (aun no hay log)"
fi

echo; echo "===== FILAS EN RDS POR CORRIDA ====="
[ -f config/env.sh ] && source config/env.sh
python3 - <<'PY' 2>/dev/null || echo "  (no se pudo consultar RDS)"
import sys; sys.path.insert(0,'scripts/lib')
import lb_config, lb_store
c=lb_config.load(); conn,_=lb_store._connect(c); cur=conn.cursor()
cur.execute("""SELECT r.run_id, r.status,
                      (SELECT count(*) FROM libroblanco.extracted_topics e WHERE e.run_id=r.run_id),
                      (SELECT count(*) FROM libroblanco.topics t WHERE t.run_id=r.run_id),
                      (SELECT count(*) FROM libroblanco.unit_topic_membership m WHERE m.run_id=r.run_id)
               FROM libroblanco.pipeline_runs r ORDER BY r.started_at DESC LIMIT 6""")
print(f"  {'run_id':22s} {'estado':8s} {'temas':>8s} {'norm':>6s} {'celdas':>8s}")
for r in cur.fetchall():
    print(f"  {r[0]:22s} {r[1]:8s} {r[2]:>8,} {r[3]:>6,} {r[4]:>8,}")
conn.close()
PY

echo; echo "===== PROGRESO DE EXTRACCION (etapa 02) ====="
for f in salidas/topics/*/*/02_extraction_cache.jsonl; do
  [ -e "$f" ] || continue
  printf "  %-34s %s unidades resueltas\n" "$(echo "$f"|cut -d/ -f3-4)" "$(wc -l < "$f")"
done

# Estado del pipeline de temas — 2026-09-29

## Corridas vigentes (las que usa el atlas publicado)

| | proyectos | publicaciones ligadas |
|---|---|---|
| run_id | `full-proj-409` | `publications_linked-308` |
| unidades | 409 | 300 |
| temas normalizados | 121 | 85 |
| `PC` normalizado | 0.4426 | 0.4777 |

Universo **filtrado por el mínimo declarado** (no todo lo que hay en PULSO
entra): proyectos con `title` + `knowledge_area` + al menos una línea de
investigación (975 → 409); publicaciones ligadas con `title` + `abstract` +
`keywords`, y proyecto padre que también califique (1 192 → 300). Detalle
completo del embudo y por qué se decidió así: `docs/cuantificacion_temas.md`
§7, o la pestaña **Datos de origen** del atlas.

La corrida anterior al filtro (975 proyectos / 840 publicaciones, 160 / 136
temas: `full-proj-975` / `publications_linked-20260924-002153`) sigue intacta
en RDS, sin tocar, por si hace falta comparar antes/después.

## Cruce con Objetivos Nacionales (PEDN 2050 / CEPLAN): hecho

`scripts/lib/lb_ceplan.py` + `scripts/analysis/ceplan_alignment.py`. Cada tema
normalizado (de ambos dominios, por separado) comparado contra las 126
sub-temáticas de `Líneas de Inv.` del PEDN 2050. Salidas en
`salidas/topics/<dominio>/<run>/06_ceplan_alignment.json` y
`reporte_ceplan_alignment.md`. Detalle metodológico y un hallazgo a reportar
(la lectura fina y la gruesa discrepan ~1/3 de las veces): §8 del mismo doc.
No integrado todavía al atlas HTML — son archivos aparte.

## Cómo relanzar algo desde cero

```bash
cd ~/LibroBlanco
source config/env.sh
python3 scripts/pipeline_temas/run_domain.py --domain projects --run-id <nuevo>
```

Sobrevive al cierre de la terminal si se lanza con
`setsid nohup ... > /dev/null 2>&1 &`. Progreso: `./estado.sh`,
`tail -f salidas/topics/<dominio>/ultimo.log`.

## Cómo relanzar tras cambiar el universo (sin repagar Bedrock)

Si solo cambia QUÉ unidades entran (no su texto), reusar la extracción y los
embeddings de una corrida anterior en vez de volver a pagarlos:

```bash
python3 scripts/pipeline_temas/01_prep_units.py --domain <dominio> --run-id <nuevo>
python3 scripts/pipeline_temas/seed_from_run.py --domain <dominio> \
    --from-run <corrida_anterior> --to-run <nuevo>
python3 scripts/pipeline_temas/run_domain.py --domain <dominio> --run-id <nuevo> --from 03
```

`seed_from_run.py` copia `extracted_topics` y `unit_embeddings` para las
unidades que sobreviven al cambio de universo; solo se recalcula lo que
depende del resto del corpus (agrupamiento, cuantificación).

## El problema de memoria: resuelto (hallazgo permanente, no cambia con las corridas)

Los vectores se guardaban como listas de float de Python (~33 bytes por
número): a escala de 14 000 unidades eran ~1.6 GB en una máquina de 1.8 GB.
Ahora son matrices `numpy` float32 de extremo a extremo (Bedrock → agrupamiento
→ pgvector), sin pérdida de precisión (pgvector guarda `vector` en float32 de
por sí). Medido a escala real: 1 638 MB → 201 MB, ~13 h proyectadas → 8.7 s.

## LibreChat: descartado como vía de ejecución (hallazgo permanente)

No expone API compatible con OpenAI (`/v1/chat/completions` devuelve el HTML de
la web) y `/api/balance` rechaza la API key con 401. La clave de la OTD es una
API key de Bedrock (factura igual que boto3); el endpoint compatible con
OpenAI de Bedrock no sirve modelos Claude, solo de peso abierto.

## Pendiente

- **`datos/doi-resultados-final.csv`**: revisado, **no aporta nada nuevo al
  universo actual**. Trae 9 371 DOIs con resumen/palabras clave, y se conectó
  como fuente en la cascada de `scripts/addons/rebuild_linked_publications.py`
  (paso `doi_resultados`, verificado con `--dry-run`, sin escribir nada). De
  los 172 registros de `publications_linked` donde tiene un abstract útil,
  **los 172 ya lo tenían** por otra fuente (master/resumen/openalex/source) —
  se solapa por completo con enriquecimientos anteriores del mismo tipo
  (Scopus/OpenAlex/PubMed). Sí hay ~347 abstracts recuperables en el catálogo
  general de publicaciones (13 995, no ligadas a un proyecto), pero eso no es
  parte del universo que se usa hoy. No hace falta volver a correr nada.
- **CRIS**: pedido de datos diferido explícitamente por el equipo.
- **Limpieza de disco pendiente de decisión** (nada de esto está en git, es
  solo espacio en el servidor): `salidas/libro_blanco.db` (74 MB, DB pre-RDS),
  `salidas/openalex_cache.jsonl` (126 MB, caché de API), ~50 MB de CSV
  intermedios de la cadena de build legada.
- **`docs/formulas_cuantificacion.tex`**: escrito, no compilado (sin
  `pdflatex`/`xelatex` en este servidor). Verificar en un entorno con LaTeX
  antes de distribuirlo.
- Sin comenzar: benchmark Cohere vs. Titan embeddings; comparación
  cruzada proyecto↔publicación ("¿publicaron lo que propusieron?").

## Avisos que deben acompañar cualquier informe

- El export CRIS en disco es delgado: `cris_abstract` 0.9% de los proyectos
  (975), `cris_keywords` 0.1%. La mayor parte del texto de un proyecto sale de
  `title` + líneas de investigación + resultados declarados (publicaciones que
  produjo), no de su propia ficha CRIS.
- `[pricing]` en `config/pipeline.toml` lleva tarifas de primera parte de
  Anthropic para Sonnet 5, no las de Bedrock — confirmar en la consola de
  facturación antes de publicar un costo.
- El coste de embeddings no está incluido: Bedrock no devuelve tokens
  facturados para Cohere. Se reporta el número de textos embebidos.

## Git

Commits recientes en `main`, ya en sync con `origin/main`. Lo de esta sesión
(CEPLAN + LaTeX + esta actualización de docs) sigue sin commitear — ver
`git status`.

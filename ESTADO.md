# Estado del pipeline de temas — 2026-09-30

## Corridas vigentes (las que usa el atlas publicado)

| | proyectos | publicaciones ligadas |
|---|---|---|
| run_id | `full-proj-646` | `publications_linked-529` |
| unidades | 646 | 529 |
| temas normalizados | 136 | 101 |
| `PC` normalizado | 0.3887 | 0.4612 |

Universo **filtrado por el mínimo declarado** (no todo lo que hay en PULSO
entra): proyectos con `title` + `cris_abstract` (975 → 646); publicaciones
ligadas con `title` + `abstract`, sin exigir que el proyecto que la declaró
también califique (1 192 → 529). Detalle completo del embudo y por qué se
decidió así: `docs/cuantificacion_temas.md` §7, o la pestaña **Datos de
origen** del atlas.

**Cambio de criterio 2026-09-29**: un nuevo export CRIS
(`datos/ProyectosPUCPCRIS-20260929.csv`) llevó `cris_abstract` de 0.9 % a
66.3 % de los 975 proyectos. El criterio de proyectos pasó de
`title`+`knowledge_area`+línea de investigación (409 proyectos, corrida
`full-proj-409`) a `title`+`cris_abstract` (646 proyectos, `full-proj-646`):
medido por longitud de texto, el abstract es casi el doble de rico que esos
metadatos. El texto embebido también cambió: ahora es
`title`+`cris_abstract`+`cris_keywords` únicamente (se sacaron
`knowledge_area`/líneas de investigación del embedding, y `cris_fos`/
`cris_ocde_subject` quedaron excluidos por no aportar señal real). Detalle:
`docs/cuantificacion_temas.md` §7.

**Cambio de criterio 2026-09-30 en `publications_linked`**: se sacaron dos
exigencias del universo mínimo. (1) `keywords` — de las 1 192 filas
candidatas, `title` estaba lleno en 71.3%, `abstract` en 45.1% y `keywords`
en solo 30.8%: era el cuello de botella real, no una señal de calidad
adicional. (2) "el proyecto que declaró la publicación también califica" —
esto acoplaba el universo de publicaciones a un criterio de `projects` sin
necesidad real; la pregunta relevante es si la publicación misma tiene
suficiente texto propio. Con solo `title`+`abstract`, la población casi se
duplicó: 300 → **529** (corrida `publications_linked-529`, reemplaza a
`publications_linked-308`). Reextraído desde cero (etapa 02 completa, ~USD
3.38); no hay reuso posible entre corridas porque el universo cambió de forma
sustancial en las dos correcciones seguidas del filtro.

Corridas anteriores, intactas en RDS por si hace falta comparar: proyectos
sin ningún filtro de calidad (975, 160 temas: `full-proj-975`), proyectos con
el criterio viejo (409, 121 temas: `full-proj-409`), publicaciones sin filtro
(840, 136 temas: `publications_linked-20260924-002153`), publicaciones con el
criterio intermedio title+abstract+keywords+proyecto-padre-409 (300, 85
temas: `publications_linked-308`).

## Cruce con Objetivos Nacionales (PEDN 2050 / CEPLAN): hecho e integrado al atlas

`scripts/lib/lb_ceplan.py` + `scripts/analysis/ceplan_alignment.py`. Cada tema
normalizado (de ambos dominios, por separado) comparado contra las 126
sub-temáticas de `Líneas de Inv.` del PEDN 2050. Salidas en
`salidas/topics/<dominio>/<run>/06_ceplan_alignment.json` y
`reporte_ceplan_alignment.md`. Detalle metodológico y un hallazgo a reportar
(la lectura fina y la gruesa discrepan ~1/3 de las veces): §8 de
`docs/cuantificacion_temas.md`. Integrado al atlas HTML: chip "ON" en el
detalle de cada tema, más pestaña propia **Objetivos Nacionales**
(`build_atlas.py::attach_ceplan`/`renderCeplan`). Re-corrido el 2026-09-30
contra `full-proj-646` (antes `full-proj-409`) y `publications_linked-529`
(antes `publications_linked-308`).

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
embeddings de una corrida anterior en vez de volver a pagarlos. **No aplica**
si también cambia el texto embebido (p.ej. columnas nuevas o quitadas del
embedding, como pasó el 2026-09-29 con `projects`): ahí hay que reextraer
desde cero con `run_domain.py` sin `--from 03`.

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

- El export CRIS del 2026-09-29 (`datos/ProyectosPUCPCRIS-20260929.csv`)
  reemplazó al del 2026-07-21: `cris_abstract` subió de 0.9% a 66.3% de los
  975 proyectos, `cris_keywords` de 0.1% a 93.0%. Antes de este export, la
  mayor parte del texto de un proyecto salía de `title` + líneas de
  investigación + resultados declarados (publicaciones que produjo); ahora
  sale mayormente de su propio `cris_abstract`. `cris_fos` también mejoró
  (texto legible en inglés) pero sigue excluido del embedding por baja
  discriminación (6 valores posibles); `cris_ocde_subject` sigue siendo URIs
  puras (0% usable tras `clean_value()`) en ambos exports.
- `[pricing]` en `config/pipeline.toml` lleva tarifas de primera parte de
  Anthropic para Sonnet 5, no las de Bedrock — confirmar en la consola de
  facturación antes de publicar un costo.
- El coste de embeddings no está incluido: Bedrock no devuelve tokens
  facturados para Cohere. Se reporta el número de textos embebidos.

## Git

Commits recientes en `main`, ya en sync con `origin/main` hasta `8dec04b`. Lo
de esta sesión (merge del export CRIS 2026-09-29, cambio de criterio de
`projects` y de `publications_linked`, re-corridas `full-proj-646` y
`publications_linked-529`, re-alineación CEPLAN, esta actualización de docs)
sigue sin commitear — ver `git status`.

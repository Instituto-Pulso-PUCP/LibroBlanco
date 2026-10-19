# Estado del pipeline de temas — 2026-10-18

## Corridas vigentes (las que usa el atlas publicado)

| | proyectos | publicaciones ligadas |
|---|---|---|
| run_id | `full-proj-20261018` | `publications_linked-20261018` |
| unidades | 1 189 | 817 |
| temas extraídos | 4 382 | 2 876 |
| temas normalizados | 202 | 137 |
| `PC` normalizado | 0.3468 | 0.4232 |
| temas efectivos por unidad | 3.33 | 2.78 |
| unidades efectivas por tema | 18.3 | 15.7 |

Atlas publicado (versión 25, 2026-10-18): https://claude.ai/artifact/2NWxFbYtfyhtLhjPMUYyFU
— compartido con cualquiera que tenga el enlace.

Universo **filtrado por el mínimo declarado**: proyectos de CRIS concluidos
desde 2010 con `title` + `cris_abstract` (1 891 filas CRIS → 1 687 → 1 189);
publicaciones declaradas por esos proyectos con `title` + `abstract`
(2 312 → 835 filas → 817 publicaciones distintas). Detalle del embudo:
`docs/cuantificacion_temas.md` §7, o la pestaña **Datos de origen** del atlas.

**Cambio 2026-10-18 — re-corrida con el universo CRIS, extracción por
LibreChat.** Terminó la búsqueda externa (577 publicaciones buscadas, 71 con
hallazgo; 22 nuevas en `candidatos.csv`). Las 21 filas `revisar` se
decidieron a mano: 14 aceptadas y 7 rechazadas (capítulo con el abstract del
libro o del congreso, o título distinto sin certeza de misma obra; ante la
duda, rechazar). `candidatos.csv` queda en 57 `aceptar` / 14 `rechazar`
(respaldos `candidatos_2026-10-11.csv` y `candidatos_pre_revision_20261018.csv`).
Re-corrida con `REEXTRACT=1`: **todas** las unidades se extrajeron de nuevo
con Sonnet 5 vía LibreChat (ver sección LibreChat), para no mezclar dos vías en
un mismo atlas; los embeddings de unidad se reusaron (Cohere, sin cambios).
Un grupo de proyectos quedó nombrado con su tema principal porque LibreChat
devolvió una respuesta vacía tres veces. Costo en Bedrock (Cohere + Llama):
menos de USD 1; los ~USD 20 que muestran los reportes de uso para extracción y
nombre están valorizados a precio de Bedrock pero pasaron por LibreChat.

**Cambio 2026-10-13 — universo de proyectos desde CRIS (código listo, sin
correr en el servidor).** Los proyectos ya no parten de la hoja PROYECTOS de
PULSO («5. Cerrado», año ≥ 2010) sino de las filas de
`datos/ProyectosPUCPCRIS-20261013.csv`: estado CRIS «concluido» e inicio ≥ 2010
(año de CRIS; si falta, el de PULSO). PULSO sigue aportando `COD_AERI` y
metadatos. Script: `scripts/addons/build_projects_from_cris.py` (conserva los
`project_id` existentes; idempotente). Resultado: 1 686 proyectos, **1 189** con
título y resumen (antes 653; los 653 siguen dentro). Entran 670 que PULSO tiene
con otro estado (634 «en proceso de cierre» o «concluido», 27 «en ejecución», 5
«cancelado», 2 «en proceso de cierre» escrito en minúscula, 1 «pendiente de
reactivación», 1 «cerrado») y 54 que solo están en CRIS; salen 13 del maestro anterior, ninguno con resumen. Los vínculos
declarados se reconstruyen para el universo nuevo desde `PROY_RESULTADOS`
(`scripts/addons/build_declared_results.py`): 1 192 → **2 315** publicaciones
declaradas de 668 proyectos; con el mínimo título + resumen, 693 publicaciones
distintas en local (más en el servidor con los resúmenes externos). Solo dos
tipos de vínculo: **declarado** (PROY_RESULTADOS) e **inferido** (todo lo
demás, incluido un código de proyecto citado en la financiación de una
publicación). `rerun_universos.sh` ya usa los dos scripts nuevos en el paso 1.
Antes de relanzar: correr `recover_abstracts_external.py` para las ~1 100
publicaciones declaradas nuevas (manual, horas) y revisar sus candidatos.

**2026-10-14: aplicado en el servidor y búsqueda externa lanzada.** La cascada
de publicaciones suma `datos/Publicaciones - CRIS - <fecha>.csv` (paso `cris`,
por DOI o título idéntico: +72 resúmenes y +65 listas de palabras clave sobre
las 2 315 declaradas). En el servidor ya se corrieron
`build_projects_from_cris.py`, `build_declared_results.py` y
`rebuild_linked_publications.py` (respaldo en `salidas/backup_20261014/`). La
búsqueda externa corre sola, sin sesión, y agrega a
`salidas/abstracts_recuperados/busqueda.jsonl` (copia de la del 10-11, así que
salta las 369 ya buscadas):

```bash
# progreso (una línea por publicación buscada; "listo" y EXIT=0 al terminar)
tail -3 salidas/abstracts_recuperados/busqueda.log
wc -l salidas/abstracts_recuperados/busqueda.jsonl
pgrep -af recover_abstracts_external     # vacío = terminó
```

Al terminar: `python3 scripts/addons/build_external_candidates.py` (agrega los
hallazgos nuevos a `candidatos.csv` con veredicto; no toca las 49 filas ya
decididas), revisar a mano las filas `revisar` y dejar `aceptar` o
`rechazar`, y `python3 scripts/addons/rebuild_linked_publications.py`. Después
recién relanzar `rerun_universos.sh` y publicar el atlas (pendiente, no
autorizado aún).

**Cambio 2026-10-11 (re-corridas `*-20261011`)**: (1) el merge CRIS aplica los
overrides manuales → 646 a 653 proyectos; (2) la cascada de publicaciones
descarta los abstracts de OpenAlex emparejados por título que eran de otra obra
(98) y suma 30 abstracts recuperados de Semantic Scholar/Crossref/OpenAlex con
el título verificado → 529 a 462 publicaciones. Control de "misma obra" en
`scripts/lib/lb_titles.py` (más estricto que la primera versión del 10-10, que
dejaba pasar «EPICICLOS» → un artículo sobre Copérnico). Reuso por texto
idéntico (`seed_same_text.py`): solo se extrajeron 32 unidades; ~USD 1.25 y 14
min en total con `scripts/pipeline_temas/rerun_universos.sh`. Las corridas
`full-proj-646` y `publications_linked-529` siguen en RDS.

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

## Cruce unidad ↔ sub-temática del PEDN 2050 (CEPLAN): hecho, validado y en el atlas

Responde «¿qué sub-temáticas desarrolla este proyecto/publicación?» (hasta 5) y
«¿quién desarrolla esta sub-temática, y cuál no desarrolla nadie?», con
porcentajes en las dos direcciones. `scripts/analysis/ceplan_units.py`:
candidatas por embeddings (piso 0.40, en las dos direcciones) verificadas por
Llama 4 Maverick (grado 0/1/2). Método: `docs/cuantificacion_temas.md` §8;
calibración, benchmark de 7 modelos contra 100 pares humanos y validación:
`EXPERIMENTS.md` §6.

- **Precisión validada a mano: 84 %** de los vínculos listados (130 vínculos,
  24 unidades al azar). El «clara» del modelo equivale a «relación real» (91 %),
  no a desarrollo claro (53 %).
- Corridas `*-20261018`: proyectos 1 156/1 189 con alguna sub-temática (97 %),
  publicaciones 651/817 (80 %). Sub-temáticas desarrolladas / débiles / sin
  desarrollo: 114/11/1 en proyectos, 95/25/6 en publicaciones (antes, con las
  `*-20261011`: 102/22/2 y 76/37/13). Una sola sub-temática no tiene relación
  clara en ningún dominio.
- Salidas: `salidas/topics/<dominio>/<run>/07_ceplan_units.json`,
  `ceplan_por_unidad.csv`, `ceplan_por_subtematica.csv`,
  `reporte_ceplan_unidades.md`; conjunta en `salidas/topics/ceplan/`.
- **Retirado** del atlas el cruce anterior tema ↔ sub-temática
  (`ceplan_alignment.py`, `06_ceplan_alignment.json`); el script se conserva.
- Páginas de etiquetado usadas (privadas): gold
  https://claude.ai/artifact/DiqPaU5KD9onDuJrjJzxMp, validación
  https://claude.ai/artifact/HSpqRsCk1Demg2PNxFCrgM.

## Cómo relanzar algo desde cero

```bash
cd ~/LibroBlanco
source config/env.sh
python3 scripts/pipeline_temas/run_domain.py --domain projects --run-id <nuevo>
```

Sobrevive al cierre de la terminal si se lanza con
`setsid nohup ... > /dev/null 2>&1 &`. Progreso: `./estado.sh`,
`tail -f salidas/topics/<dominio>/ultimo.log`.

## Cómo relanzar tras cambiar insumos o universo (sin repagar Bedrock)

Todo de una vez, sin sesión interactiva (merge CRIS → cascada de
publicaciones → etapas 01–05 de ambos dominios → cruce CEPLAN → atlas):

```bash
cd ~/LibroBlanco
OLD_PROJ=full-proj-20261018 OLD_PUBS=publications_linked-20261018 \
  setsid -f bash scripts/pipeline_temas/rerun_universos.sh > salidas/topics/rerun_launch.out 2>&1 < /dev/null
tail -f salidas/topics/rerun_universos.log   # termina en rerun_universos.DONE o .FAILED
```

Lanzado por ssh desde otra máquina, usar `setsid -f` (con `setsid nohup ... &`
el proceso muere al cerrarse la sesión). Los errores de arranque, antes de que
el script abra su log, quedan en `rerun_launch.out`. Si el script se copió
desde Windows, quitarle los CRLF (`sed -i 's/\r$//'`): con ellos falla en
`set -o pipefail`.

Reusa la extracción y el embedding **solo de las unidades con texto idéntico**
(`seed_same_text.py`), así que es correcto aunque cambie el texto de algunas.
`REEXTRACT=1` descarta la extracción reusada (todas las unidades pasan otra vez
por el LLM, p.ej. al cambiar de modelo o de vía) y conserva los embeddings.
Si falla, relanzar con el mismo `TAG=<fecha>`: cada paso retoma desde su cache,
también con `REEXTRACT=1` (el cache que ya existe es de la misma corrida y no
se borra).
Publicar el atlas (`salidas/topics/atlas.html`) es aparte, desde una sesión.

Por dominio, a mano:

```bash
python3 scripts/pipeline_temas/01_prep_units.py --domain <dominio> --run-id <nuevo>
python3 scripts/pipeline_temas/seed_same_text.py --domain <dominio> \
    --from-run <corrida_anterior> --to-run <nuevo>
python3 scripts/pipeline_temas/run_domain.py --domain <dominio> --run-id <nuevo> --from 02
```

`seed_from_run.py` (el original) copia por unit_id sin mirar el texto: usarlo
solo si el texto de las unidades que sobreviven no cambió.

## El problema de memoria: resuelto (hallazgo permanente, no cambia con las corridas)

Los vectores se guardaban como listas de float de Python (~33 bytes por
número): a escala de 14 000 unidades eran ~1.6 GB en una máquina de 1.8 GB.
Ahora son matrices `numpy` float32 de extremo a extremo (Bedrock → agrupamiento
→ pgvector), sin pérdida de precisión (pgvector guarda `vector` en float32 de
por sí). Medido a escala real: 1 638 MB → 201 MB, ~13 h proyectadas → 8.7 s.

## LibreChat: vía de extracción y nombre de temas (desde 2026-10-18)

LibreChat PUCP (https://chat.txdpucp.net) expone el **Agents API**, compatible
con OpenAI, en `/api/agents/v1/chat/completions`. El 2026-10-11 se descartó
porque se probó la raíz (`/v1/chat/completions` devuelve el HTML de la web);
esa conclusión era incorrecta.

- Configuración (`config/env.sh` del servidor):
  `LB_GATEWAY__BASE_URL='https://chat.txdpucp.net/api/agents'`,
  `LB_GATEWAY__API_KEY` (clave de LibreChat, no la de Bedrock que empieza por
  `ABSK`) y `LB_GATEWAY__CHAT_MODEL` = id del agente (`agent_...`, no su
  nombre). En `config/pipeline.toml`: `[gateway] enabled = true`,
  `use_for = "chat"`.
- El agente (*LibroBlancoTest*) usa **Sonnet 5**, sin instrucciones ni
  herramientas, para que no se mezclen con el prompt de extracción.
- Solo chat: extracción (etapa 02), nombre de grupos (etapa 03) y traducción
  de sub-temáticas. Los embeddings (Cohere) y el verificador CEPLAN (Llama 4
  Maverick, `BedrockClient` directo) siguen en Bedrock.
- Comparación previa con 8 unidades contra la extracción de Bedrock: mismo
  formato, mismos temas principales; LibreChat agrega a veces un tema
  secundario más (29 vs. 25 temas; 28 vs. 24 con cita literal).
- Devuelve `usage`, así que los tokens se miden. A veces responde 200 con
  `content` vacío: `OpenAICompatClient.complete` reintenta 3 veces y luego
  devuelve "" (cada etapa aplica su respaldo).
- Sin datos aún sobre límites de uso o tope de créditos de la instancia.

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
- **Avisar al equipo de las 98 publicaciones** con abstract de otra obra: el
  archivo de datos faltantes que se compartió las cuenta como "con abstract".
- **Corregir en origen la búsqueda de OpenAlex por título**
  (`openalex_helpers.build_openalex_query`: `search.exact`, `per-page=1`, toma
  el primer resultado sin verificarlo) usando `lb_titles.same_work`. Ya está
  filtrado aguas abajo (cascada de publicaciones y texto auxiliar de
  `projects`, que hoy no afecta a ningún proyecto), pero las columnas siguen
  sucias en `salidas/06_*` y `07_*_ground_truth.csv`: además del abstract, 84
  publicaciones tienen un `openalex_doi` que viene de ese emparejamiento sin
  verificar (solo 2 coinciden). Revisar también las cifras de OpenAlex de las
  láminas del 15-08 (autores, revista, país).
- **59 publicaciones con palabras clave pero sin abstract** quedan fuera del
  universo; entrarían si el mínimo aceptara título + palabras clave. Decisión
  de criterio pendiente.
- **Limpieza de disco pendiente de decisión** (nada de esto está en git, es
  solo espacio en el servidor). Ojo antes de borrar: `salidas/libro_blanco.db`
  (74 MB) no es solo histórico, la leen `pipeline/02_match_candidates.py` y
  `analysis/compare_v1_v2.py`; `salidas/openalex_cache.jsonl` (126 MB) evita
  repetir ~7 000 llamadas a OpenAlex si se re-corre `01_build_pipeline.py`.
  Sugerencia: mover ambos a S3 en vez de borrarlos; los ~50 MB de CSV
  intermedios de la cadena legada sí se pueden borrar.
- **Benchmark de embeddings (2026-10-10, parcial).** Tarea: ordenar los
  vínculos gold proyecto↔publicación por encima de los demás candidatos del
  mismo coordinador (169 proyectos, 3 694 pares). Titan v2 AUC 0.763 vs.
  bge-m3 local 0.754: empate práctico. **Cohere no se pudo medir**: desde la
  cuenta local (usuario IAM `HARVY`) Bedrock devuelve `AccessDeniedException`
  por falta de permisos de AWS Marketplace (`aws-marketplace:Subscribe`);
  hay que pedirlos o correr el benchmark desde el EC2. Scripts en el
  scratchpad de la sesión, no en el repo.
- **¿Publicaron lo que propusieron? (2026-10-10, piloto local con bge-m3).**
  Sí, de forma muy clara: comparando el texto del proyecto (título + resumen
  CRIS + palabras clave) con cada publicación que declaró, la propia
  publicación queda en el top 10% de las 433 publicaciones ligadas en el 94%
  de los 363 vínculos (mediana: percentil 99.8), sin diferencias entre áreas.
  Los casos menos alineados son desplazamientos dentro del mismo campo, no
  errores. Falta repetirlo con los embeddings de Cohere del pipeline.
- `docs/formulas_cuantificacion.tex` compilado (MiKTeX); PDF en
  `docs/formulas_cuantificacion.pdf`. El ejemplo trabajado es de
  `full-proj-409`; el texto ahora lo dice, pero sus números no son los del
  atlas actual.

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

`main` en sync con `origin/main` hasta `d2806ad` (2026-10-10). Sin commitear
(2026-10-12): control de títulos `lb_titles.py`, paso `externo` de la cascada,
`seed_same_text.py`, `rerun_universos.sh`, `recover_abstracts_external.py`,
conteos del atlas calculados, aviso de precisión en la pestaña CEPLAN,
EXPERIMENTS.md §6.5 y esta actualización de docs — ver `git status`.

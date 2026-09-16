# Pipeline de extracción y normalización temática

Replica, para los proyectos de investigación de la PUCP, la metodología usada
en un explorador de referencia (`explorador_temas.html`, aportado por el
equipo) sobre otro documento: por cada unidad de texto se extraen temas con
evidencia y confianza, y luego se agrupan en un conjunto más chico de temas
normalizados con trazabilidad completa (proyecto → tema extraído → tema
normalizado).

Distinto de la clusterización por embeddings ya existente
(`scripts/analysis/clustering_experiments.py`, ver `EXPERIMENTS.md`): esto es
"contraste con un objetivo determinado" en germen, no categorización
automática — cada tema normalizado nace de una lectura del contenido
conceptual real (abstract, keywords, línea OCDE/FOS) de los proyectos, no de
similitud vectorial.

## Estado actual (piloto)

- **36 de 983** proyectos cerrados (2010+) con `cris_abstract` disponible,
  muestreados de forma estratificada por `executing_unit`.
- **67 temas extraídos**, **18 temas normalizados**.
- Extracción y normalización hechas leyendo cada proyecto (no hay una clave
  de API de LLM configurada en este entorno para automatizarlo por script;
  ver más abajo). Por eso el alcance es una muestra, no las ~983 filas.
- **No incluye** todavía el contraste con un objetivo (ODS / plan CEPLAN):
  según la reunión del equipo, ese objetivo aún no está definido (Enrique
  propone ODS por defecto; Gabriel va a proponer el contraste contra el plan
  estratégico de CEPLAN 2010-2020). Este pipeline se detiene en "temas
  normalizados" a la espera de esa definición.

## Pasos

1. **`scripts/analysis/topic_extraction_prep.py`** — exporta proyectos del
   CSV crudo a un esquema fijo de columnas (`unit_id`, `title`, `year`,
   `project_type`, `knowledge_area`, `executing_unit`, `executing_section`,
   `funding_type`, `research_lines`, `text`, `text_sources`), para que el
   resto del pipeline no dependa del esquema del CSV de origen y sea
   replicable con otros datasets.
   - `--full` exporta todas las filas con texto disponible (~663 de 983
     tienen `cris_abstract`); por defecto genera una muestra estratificada.
   - Fuente de texto: `cris_abstract` + `cris_keywords` + `cris_fos`
     (cobertura real: 67.4% / 94.3% / 94.4% sobre 983 proyectos — la nota en
     `EXPERIMENTS.md` de fill rates <1% para estas columnas está desactualizada).
2. **Extracción + normalización** — hoy es un paso manual/asistido por LLM
   (no programático): se lee `text` de cada unidad y se producen temas con
   `{topic, description, evidence, confidence}`; luego se agrupan en temas
   normalizados con `{normalized_topic, description, variants, project_ids,
   executing_units, count, avg_confidence, evidences}`. El resultado del
   piloto está en `salidas/topics/projects_topics_pilot.json` (no versionado,
   como el resto de `salidas/`).
3. **`scripts/analysis/build_topic_explorer.py`** — renderiza el HTML
   interactivo (`scripts/analysis/templates/topic_explorer_template.html`)
   a partir del JSON de temas, embebiendo los datos como JSON estático (sin
   backend). Salida por defecto:
   `salidas/topics/explorador_temas_proyectos_piloto.html`.

## Para escalar a las ~983 filas

El cuello de botella es el paso 2. Para automatizarlo por script hace falta
una clave de API de LLM configurada en el entorno de ejecución (no presente
hoy — solo se detectó `ANTHROPIC_BASE_URL`, sin key utilizable desde un
script standalone). Una vez que haya presupuesto/clave definidos:

1. Correr `topic_extraction_prep.py --full` para las ~663 filas con texto.
2. Reemplazar el paso manual por llamadas a la API con el mismo esquema de
   salida (`{topic, description, evidence, confidence}` por unidad).
3. Reusar `build_topic_explorer.py` sin cambios — solo cambia el JSON de
   entrada.

## Contraste con un objetivo: alineación con políticas nacionales (completado)

El objetivo pendiente en la sección anterior se definió al recibir
`datos/corpus_politicas_chunks.jsonl`: 30,963 chunks de nivel página
extraídos de 946 documentos oficiales de política pública peruana, más
amplio que las opciones originalmente evaluadas (ODS o solo CEPLAN):

| `fuente` | Qué es | # docs | chunks/doc |
|---|---|---|---|
| PN | Política Nacional (política sectorial completa) | 50 | 11–1780 (prom. 396) |
| PESEM | Plan Estratégico Sectorial Multianual (por ministerio) | 18 | 147–766 (prom. 385) |
| PEDN | Plan Estratégico de Desarrollo Nacional | 4 | 5–930 (prom. 403) |
| CONCYTEC | Documentos estratégicos de ciencia/tecnología | 11 | 45–481 (prom. 159) |
| PP | Programa Presupuestal | 101 | 1 (ya es un resumen atómico) |
| CEPLAN | Tendencia/megatendencia de CEPLAN | 762 | 1 (una frase-tendencia, atómica) |

Cada chunk trae `fuente, doc_id, titulo, chunk_id, paginas, texto,
num_chars`. Un `doc_id` (p. ej. `PN_01`) agrupa todos los chunks de un mismo
documento, cortados aproximadamente por página.

### Script: `scripts/analysis/build_topic_policy_alignment.py`

Implementa exactamente la idea que quedó pendiente arriba ("embeddings de
`normalized_topics` + texto del objetivo → índice de compatibilidad 0-1"),
con las siguientes decisiones concretas (ninguna estaba especificada de
antemano; se documentan aquí para no tener que re-derivarlas):

1. **Qué se compara.** Un vector por cada uno de los 401 temas normalizados
   (49 de `projects_topics_consolidated.json` + 352 de
   `publications_topics_current.json`, embebiendo `normalized_topic + ". " +
   description`) contra un vector por cada uno de los 946 documentos de
   política. Un documento se representa por el **promedio de los embeddings
   de todos sus chunks** (mean pooling) — comparar contra chunks individuales
   no es viable porque un documento de 400 páginas cubre demasiados
   subtemas para que un solo chunk lo represente, y comparar contra el
   documento completo sin trocear tampoco es viable (excede el límite de
   contexto del modelo de embeddings).
2. **El score** es similitud coseno entre esos dos vectores (0-1 en la
   práctica, aunque el rango teórico es -1 a 1): 1 = mismo significado, 0 =
   sin relación. El modelo de embeddings (entrenado con pares de
   parafraseo/traducción/entailment) aprende a acercar textos
   semánticamente similares aunque no compartan vocabulario — por eso
   "documentación gramatical del idioma kakataibo" sí matchea con "Política
   Nacional de Lenguas Originarias" pese a casi no compartir palabras.
3. **Evidencia.** Para cada (tema, top-5 políticas), se guarda también el
   chunk individual con mayor similitud dentro de ese documento, como texto
   de evidencia — mitiga (sin eliminar) la dilución del mean-pooling en
   documentos largos y heterogéneos.
4. **Salida:** `salidas/topics/topic_policy_alignment_<modelo>.json`, con
   `topics` (cada tema → sus top-K políticas con score y evidencia) y
   `policies` (índice inverso: cada política → los temas que más la tocan).

### Elección de modelo de embeddings: por qué NO se usó el "mejor" del registro

`EXPERIMENTS.md` señala a `jina-v5-nano` como el modelo más fuerte y
consistente en los experimentos de clustering ya existentes (proyecto vs.
proyecto, publicación vs. publicación). Para este paso se probó primero con
`minilm-multilingual` por pragmatismo de cómputo, y luego se intentó
reproducir con `jina-v5-nano` para no quedarnos con una elección no
validada. Dos hallazgos cambiaron la decisión:

- **Costo prohibitivo en CPU.** Los chunks de política son mucho más largos
  (~1,900 caracteres en promedio, hasta 26,630) que los textos de
  clustering usados en `EXPERIMENTS.md`. Embeber los 30,963 chunks con
  `jina-v5-nano` en esta máquina (CPU-only) proyecta a **~14+ horas**
  (medido: 43/968 lotes en poco más de una hora, convergiendo a
  ~50-56s/lote). `minilm-multilingual` procesa el mismo corpus completo en
  minutos.
- **Peor discriminación cruzada de dominio, no solo más lento.** Se validó
  con una muestra dirigida (14 temas — 7 claramente relevantes a alguna
  política, 7 claramente no — contra los 64 documentos candidatos que ya
  aparecían en el top-5 de `minilm` para esos temas) re-embebiendo esa
  muestra con `jina-v5-nano`. Resultado: `jina-v5-nano` infla **todos** los
  scores, relevantes e irrelevantes por igual (score promedio del mejor
  match: temas relevantes 0.80 vs. irrelevantes 0.62 — brecha
  proporcionalmente menor que la de `minilm`: 0.535 vs. 0.32). Con
  `minilm`, un tema de matemática pura sin ninguna conexión de política
  (p. ej. "corrección de aberración de fase adaptativa para formación de
  haz en imágenes ultrasónicas") queda claramente abajo (~0.22); con
  `jina-v5-nano` el mismo tema sube a ~0.57, peligrosamente cerca del rango
  de matches genuinos. El ranking de top-3 entre ambos modelos solo
  coincidió ~33% de las veces, y peor precisamente en los temas
  irrelevantes (donde no hay señal real que ambos deban encontrar por
  igual).
  - Advertencia de alcance (de esta primera validación): usó como
    candidatos solo los documentos que `minilm` ya había puesto en su propio
    top-5 — no podía revelar si `jina-v5-nano` habría encontrado, en el
    corpus completo, una política mejor que `minilm` pasó por alto.
  - Script de validación (no versionado, vivió en el scratchpad de la
    sesión): embebe una submuestra de temas + solo los documentos candidatos
    relevantes con el modelo alternativo, y compara el top-5 resultante
    contra el ya calculado.

- **Repetido a escala completa tras habilitar GPU** (ver siguiente
  subsección): se corrió `jina-v5-nano` sobre los 30,963 chunks completos
  (`salidas/topics/topic_policy_alignment_jina-v5-nano.json`, generado para
  comparación — no es la salida canónica) y se comparó contra `minilm`
  para los 401 temas × 946 políticas completos, sin el sesgo de candidatos
  de la primera validación. La conclusión se sostiene y con evidencia más
  fuerte:
  - Solapamiento promedio del top-3 entre ambos modelos: **0.80/3 (~27%)**
    en los 401 temas — 159/401 (40%) sin ningún documento en común en el
    top-3, y esto **no mejora** para los temas donde `minilm` está más
    seguro (score top-1 ≥ 0.55): siguen sin coincidir en ningún documento
    del top-3 el 39% de las veces. No es solo ruido en el margen de baja
    confianza.
  - Distribución de scores del mejor match por tema: `minilm` media 0.489,
    mediana 0.505, **rango 0.130–0.786** (desviación 0.149) — usa la parte
    baja de la escala para temas sin relación real. `jina-v5-nano` media
    0.764, mediana 0.771, **rango 0.430–0.969** (desviación 0.106) — ni el
    tema con *menor* score de todo el corpus baja de 0.43, confirmando a
    escala completa que este modelo comprime todo hacia arriba y no separa
    señal de ruido por magnitud.

**Conclusión:** se usa `minilm-multilingual` para este paso — no por ser el
"mejor" modelo del registro en general, sino porque en esta tarea específica
(contrastar texto de investigación académica contra texto de política
pública, dominios muy distintos) discrimina mejor señal de ruido que la
alternativa más cara, además de ser ~100x más rápido en CPU. Que un modelo
gane en clustering intra-dominio no garantiza que gane en similitud
cross-dominio — son tareas distintas y no deberían asumirse intercambiables
sin volver a medir.

### GPU disponible (descubierto durante esta validación)

Esta máquina tiene una NVIDIA GeForce GTX 1650 Ti (4GB VRAM, driver con
soporte CUDA 13.1) que estaba sin usar porque el PyTorch instalado
originalmente era la build `+cpu`. Se reinstaló como `torch==2.6.0+cu124`
(`pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cu124`)
y `scripts/lib/embeddings.py` ahora detecta CUDA automáticamente
(`model_kwargs['device'] = 'cuda' if torch.cuda.is_available() else 'cpu'`)
en lugar de forzar `'cpu'`.

Con GPU, `jina-v5-nano` pasó de ~1.7s/texto a ~0.2s/texto (~8x), bajando la
corrida completa de 30,963 chunks de ~14h a ~35-40 min reales. Cuidado si se
reintenta con otro modelo o batch size: los chunks más largos del corpus
(hasta 26,630 caracteres) provocan **OOM** en los 4GB de VRAM con
`batch_size=16` sin límite de secuencia (necesita ~9.3GB). La mitigación ya
aplicada en el script es capar `model.max_seq_length = 2048` antes de
codificar en GPU (cubre el percentil 99.9 de chunks sin truncar nada;
p99.9 = 7,884 caracteres) — verificar con los chunks más largos reales del
corpus antes de subir el batch size si se cambia de modelo.

### Robustez: checkpointing

`build_topic_policy_alignment.py` guarda los embeddings de chunks en grupos
de 1000 (`salidas/topics/policy_alignment_cache/chunk_embeddings_<modelo>_parts/part*.npy`)
a medida que se calculan, no solo al final. Si el proceso se interrumpe
(Ctrl-C, cierre de laptop, error), un rerun retoma desde el último grupo
completo en vez de recalcular todo desde cero — relevante porque con
modelos lentos en CPU (ver arriba) una corrida completa puede tardar horas.

### Limitaciones conocidas (léanse antes de citar un score como si fuera un hecho)

1. **Sin conjunto de validación humana.** Los scores nunca se contrastaron
   contra un juicio humano de "esto sí/no está relacionado" a escala — solo
   se revisaron ~15-20 pares a ojo (incluidos en la conversación que originó
   este documento). Parecen razonables, pero no están auditados.
2. **El mean-pooling diluye documentos largos.** Un documento PN de 400
   páginas que cubre diez subtemas distintos obtiene un solo vector
   promediado; un tema que matchea con *una* sección específica puede
   quedar con un score más bajo del que "debería" tener a nivel de esa
   sección. La evidencia (mejor chunk individual) es el paliativo, pero el
   score de ranking sigue siendo el promedio del documento completo.
3. **No hay un umbral validado de "relevante".** Los scores son señal
   relativa dentro de este dataset (un 0.6 es más alto que un 0.3), no una
   escala absoluta calibrada. No se ha fijado ni validado un punto de corte
   tipo "arriba de 0.45 = relevante para política pública".

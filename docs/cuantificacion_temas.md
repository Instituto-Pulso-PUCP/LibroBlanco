# Cuantificación bidireccional proyecto/publicación ↔ tema

Cómo se responden las dos preguntas del equipo, con la misma matriz, cambiando
solo la dirección en que se normaliza:

| Pregunta | Nombre aquí | Normalización | Suma 1 por |
|---|---|---|---|
| ¿Cuánto del Proyecto 1 es del Tema 1? | **contención** | por fila | proyecto |
| ¿Cuánto del Tema 1 lo aporta el Proyecto 1? | **contribución** | por columna | tema |

Implementación: [`scripts/lib/lb_membership.py`](../scripts/lib/lb_membership.py).
Etapa que la ejecuta: [`scripts/pipeline_temas/04_quantify.py`](../scripts/pipeline_temas/04_quantify.py).

---

## 1. Sobre el "coeficiente de partición" que sugirió el profesor

Conviene separar dos cosas que se confunden fácil, porque la sugerencia es útil
pero no responde directamente lo que se le pidió.

El **coeficiente de partición** (*partition coefficient*, Bezdek 1974) es un
**índice de validez** de una partición difusa completa:

$$PC = \frac{1}{N}\sum_{d}\sum_{t} u_{dt}^{2}$$

Da **un solo número por corrida**, no un número por par (proyecto, tema). Vale
1 cuando cada unidad pertenece a un único tema (partición nítida) y $1/T$
cuando cada unidad se reparte por igual entre los $T$ temas (máxima difusión).

Lo que sí responde las dos preguntas es la **matriz de pertenencia difusa**
$u_{dt}$ que el índice evalúa. Es decir: el profesor señaló el marco correcto
—lógica difusa en lugar de asignar cada proyecto a un solo tema— y el
coeficiente es la herramienta de ese marco para saber **si la asignación tiene
información o no**. Por eso aquí se calculan las dos cosas por separado:

- la **matriz** (contención y contribución) es el dato que se muestra;
- **PC y la entropía de partición** son el control de calidad: dicen si esa
  matriz está diciendo algo o es trivial.

## 2. Definiciones

Sea $w_{dt} \ge 0$ la **afinidad** cruda entre la unidad $d$ y el tema $t$
(§3 explica de dónde sale).

**Contención** — qué fracción de la unidad corresponde al tema:

$$C_{dt} = \frac{w_{dt}}{\sum_{t'} w_{dt'}} \qquad \sum_{t} C_{dt} = 1$$

**Tamaño del tema en unidades-equivalentes** — cuántos proyectos "enteros" vale
el tema, descontando que cada proyecto se reparte:

$$E_t = \sum_{d} C_{dt} \qquad \sum_{t} E_t = N$$

Este número es el que hay que citar como "tamaño del tema", no el conteo de
proyectos que lo tocan. Un tema que aparece en 40 proyectos pero siempre como
tema secundario al 20% vale 8 proyectos-equivalentes, no 40. Y los equivalentes
de todos los temas suman exactamente el número de proyectos, así que los
porcentajes de corpus se pueden sumar sin doble conteo.

**Contribución** — qué fracción del tema aporta la unidad:

$$K_{dt} = \frac{C_{dt}}{E_t} \qquad \sum_{d} K_{dt} = 1$$

### Las dos variantes de contribución

`quantification.contribution_mode` en `config/pipeline.toml`:

- **`share`** (por defecto) — la fórmula de arriba. Cada unidad aporta como
  máximo 1 unidad-equivalente, repartida entre sus temas. Es la lectura
  simétrica: ninguna unidad pesa más por haber tenido más texto o más temas
  extraídos.
- **`mass`** — normaliza la afinidad cruda por columna, sin pasar por la
  contención. Las unidades con más masa de afinidad (más temas, más evidencia,
  más abstract) aportan proporcionalmente más. Es defendible si se quiere que
  un proyecto grande *deba* pesar más, pero mezcla "cuánto del tema aporta" con
  "cuánto texto tenía el proyecto", y eso último es un artefacto de la calidad
  del export, no del contenido.

Se recomienda `share` para reportar y `mass` solo como contraste.

## 3. De dónde sale la afinidad $w_{dt}$

`quantification.affinity_source`, tres opciones:

| Modo | Peso | Ventaja | Límite |
|---|---|---|---|
| `extraction` | suma de las confianzas de los temas extraídos por el LLM que cayeron en ese tema normalizado | cada celda tiene evidencia textual citable | muy dispersa: 1–3 temas por unidad, la contención queda casi cruda |
| `embedding` | coseno entre el vector de la unidad y el centroide del tema, recortado | gradación fina, cubre afinidades débiles que la extracción no nombró | sin evidencia, y sensible a la calibración del modelo |
| `hybrid` | mezcla de ambas, cada una normalizada por fila primero, con peso `hybrid_alpha` | evidencia donde la hay, gradación donde no | hay que elegir `alpha` |

**El recorte de la similitud no es opcional.** El coseno entre textos del mismo
dominio rara vez baja de 0.3, así que sin recortar, toda unidad tendría
pertenencia no nula a todos los temas, la contención tendería a $1/T$ y el
coeficiente de partición caería a su mínimo: información cero. Por eso
`similarity_floor` descarta por debajo del piso, `similarity_top_k` conserva
los k temas más cercanos y `similarity_power` agudiza lo que queda. Estos tres
valores son los que hay que calibrar mirando el PC resultante (§4), no a ojo.

Esto conecta con un hallazgo ya documentado en
[EXPERIMENTS.md](../EXPERIMENTS.md): `jina-v5-nano` comprime todos los scores
hacia arriba (ningún tema baja de 0.43) mientras `minilm` usa el rango bajo
para los temas sin relación. Un modelo así obliga a un `similarity_floor` mucho
más alto, o no discrimina nada.

## 4. Cómo leer los índices

Se reportan por los dos lados:

- **lado unidad**, sobre $C$: ¿cada proyecto pertenece nítidamente a un tema o
  se reparte?
- **lado tema**, sobre $K$: ¿cada tema está sostenido por pocas unidades o por
  muchas?

| | Interpretación | Qué hacer |
|---|---|---|
| `PC_normalizado` > 0.95 | partición prácticamente nítida | la contención no aporta nada sobre una asignación simple; usar espacio de temas más fino o afinidad híbrida |
| 0.2 – 0.8 | rango informativo | reportar |
| < 0.05 | prácticamente uniforme | subir `similarity_floor`/`similarity_power`, bajar `similarity_top_k` |

Se usa **PC normalizado** (normalización de Dunn/Backer,
$(PC - 1/T)/(1 - 1/T)$) porque el PC crudo depende del número de temas: un
0.45 con 49 temas y un 0.45 con 350 no significan lo mismo, y los dos dominios
tienen distinto número de temas por construcción.

Complementos más intuitivos que el índice, y que se reportan junto a él:

- **temas efectivos por unidad** $= 1/\sum_t C_{dt}^2$ — un proyecto repartido
  50/30/20 tiene 2.6 temas efectivos.
- **unidades efectivas por tema** $= 1/\sum_d K_{dt}^2$ — un tema con 40
  proyectos pero 3 efectivos está sostenido por tres.

## 5. Estado medido con los datos actuales

Dos corridas, cada una con su propio espacio de temas (no se mezclan ni se
comparan):

| | proyectos (`full-proj-975`) | publicaciones ligadas (`publications_linked-20260924-002153`) |
|---|---:|---:|
| unidades | 975 | 840 |
| temas extraídos por el LLM | 1 928 | 1 795 |
| temas normalizados | **160** | **136** |
| umbrales calibrados (líder / fusión) | 0.577 / 0.636 | 0.567 / 0.641 |
| tamaño de grupo (máx / mediana) | 77 / 8 | 96 / 9 |
| celdas no nulas · densidad | 7 871 · 5.05 % | 6 770 · 5.93 % |
| `PC` (normalizado) | 0.4872 (0.4839) | 0.4966 (0.4929) |
| entropía normalizada | 0.2345 | 0.2337 |
| temas efectivos por unidad | 2.47 | 2.40 |
| unidades efectivas por tema | 13.3 | 13.2 |

Los dos `PC` normalizados caen en la franja informativa (0.2 – 0.8): la
partición es difusa de verdad, y las dos lecturas dicen cosas distintas.

### Por qué no se fija un número de temas

`topics.target_topics = 0` — sin objetivo. El número de temas lo decide el
umbral de fusión, calibrado sobre el p99 de las similitudes del propio corpus.
Cada fusión que se acepta está por encima de ese umbral.

Forzar un objetivo bajo obliga a aceptar fusiones por debajo del umbral. Medido
sobre los 1 928 temas extraídos de proyectos, con umbral 0.636:

| objetivo | fusiones forzadas | similitud más baja aceptada | grupo mayor |
|---:|---:|---:|---:|
| 49 | 111 | 0.525 | 303 |
| 60 | 100 | 0.530 | 162 |
| 100 | 60 | 0.550 | 112 |
| 140 | 20 | 0.574 | 77 |
| sin objetivo | 0 | — | 77 |

El salto está entre 60 y 49: el grupo mayor pasa de 162 a 303 miembros —el 16 %
de todos los temas extraídos bajo una sola etiqueta—, mezclando quechua, lengua
de señas y derechos humanos. Bajar el percentil de calibración en vez de forzar
no arregla nada: al 85 % salen 47 grupos con uno de 294. El problema no es el
mecanismo, es el número: la estructura de similitud de este corpus no sostiene
~49 temas.

Si hace falta una lista corta para presentar, se construye como **segunda capa
explícita** sobre estos temas finos, y las dos capas quedan auditables por
separado.

## 6. Qué NO hace este método

- **No valida los temas.** Que la matriz cumpla sus identidades no dice nada
  sobre si los temas extraídos son correctos. Eso requiere revisión humana de
  una muestra, que sigue pendiente (misma limitación que ya registra
  `docs/topic_normalization_pipeline.md` §Limitaciones).
- **No compara dominios.** Los temas de proyectos y los de publicaciones se
  calculan por separado y no comparten espacio vectorial ni identificadores. Un
  "12%" en proyectos y un "12%" en publicaciones no son comparables entre sí.
- **No tiene umbral absoluto.** Una contención de 0.30 es más alta que una de
  0.10 dentro de la misma corrida; no hay un punto de corte calibrado de
  "pertenece de verdad".

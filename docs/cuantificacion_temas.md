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
comparan). Población tras el **universo mínimo declarado** (\S7): proyectos
con `title` + `cris_abstract`; publicaciones ligadas con `title` + `abstract`,
sin exigir que el proyecto que la declaró también califique. El detalle de
por qué se llega a esta población —de dónde sale cada número del embudo,
cuántos caracteres de texto quedó por unidad— está en la pestaña **Datos de
origen** del atlas publicado, no repetido aquí.

| | proyectos (`full-proj-646`) | publicaciones ligadas (`publications_linked-529`) |
|---|---:|---:|
| unidades | 646 | 529 |
| temas extraídos por el LLM | 1 951 | 1 456 |
| temas normalizados | **136** | **101** |
| umbrales calibrados (líder / fusión) | 0.570 / 0.631 | 0.555 / 0.623 |
| tamaño de grupo (máx / mediana) | 80 / 11 | 57 / 10 |
| celdas no nulas · densidad | 5 261 · 5.99 % | 4 273 · 8.00 % |
| `PC` (normalizado) | 0.3932 (0.3887) | 0.4665 (0.4612) |
| entropía normalizada | 0.2743 | 0.2568 |
| temas efectivos por unidad | 2.96 | 2.53 |
| unidades efectivas por tema | 12.9 | 12.3 |

Los dos `PC` normalizados caen en la franja informativa (0.2 – 0.8): la
partición es difusa de verdad, y las dos lecturas dicen cosas distintas.

*(Corridas anteriores, intactas en RDS por si hace falta comparar: proyectos
sin filtro de calidad —975, 160 temas: `full-proj-975`—; proyectos con el
criterio viejo —409, `title`+`knowledge_area`+línea de investigación, 121
temas: `full-proj-409`—, reemplazado el 2026-09-29 cuando un nuevo export
CRIS hizo `cris_abstract` una señal mucho mejor que esos metadatos (ver \S7);
publicaciones sin filtro —840, 136 temas:
`publications_linked-20260924-002153`—; publicaciones con el criterio
intermedio —300, `title`+`abstract`+`keywords`+proyecto-padre-calificaba, 85
temas: `publications_linked-308`—, reemplazado el 2026-09-30 (ver \S7).)*

### Por qué no se fija un número de temas

`topics.target_topics = 0` — sin objetivo. El número de temas lo decide el
umbral de fusión, calibrado sobre el p99 de las similitudes del propio corpus.
Cada fusión que se acepta está por encima de ese umbral.

Forzar un objetivo bajo obliga a aceptar fusiones por debajo del umbral. Medido
sobre los 1 928 temas extraídos de proyectos de la corrida `full-proj-975`
(el universo sin el filtro de calidad, más grande; el argumento es sobre la
estructura de similitud del corpus, no cambia con el filtro), con umbral
0.636:

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

## 7. Universo mínimo declarado

Decisión del equipo, separada de `required_any` (que solo evita unidades sin
texto en absoluto): una unidad puede tener texto suficiente para construirse y
aun así no ser parte del universo si no cumple un mínimo de calidad de dato.

- **Proyectos**: cerrado (`Estado = "5. Cerrado"`) y `year ≥ 2010` (ya
  aplicado en `salidas/01_projects_closed_con_cris.csv`), **y** `title`, **y**
  `cris_abstract`. De 1 928 proyectos registrados en PULSO, 975 quedan
  cerrados/2010+, y de esos, **646** cumplen las dos.

  Este criterio reemplazó, el 2026-09-29, al que exigía `title` +
  `knowledge_area` + al menos una línea de investigación (dejaba 409). El
  motivo: un nuevo export CRIS (`datos/ProyectosPUCPCRIS-20260929.csv`) llevó
  la cobertura de `cris_abstract` de 0.9 % a 66.3 % de los 975 proyectos —con
  el export anterior, exigir abstract habría dejado casi nada, así que
  `knowledge_area`/línea de investigación eran la mejor señal disponible de
  "hay contenido real". Medido por longitud de texto tras el cambio: los
  proyectos que calificaban *solo* por `knowledge_area`+línea (sin abstract)
  tenían una mediana de 801 caracteres; los que calificarían *solo* por
  abstract (sin esos metadatos) tenían 1 547 — casi el doble. El texto
  embebido también se redujo a `title` + `cris_abstract` + `cris_keywords`:
  con el abstract presente, `knowledge_area` y las líneas de investigación
  aportaban poco texto nuevo (siguen guardadas como metadato/filtro, no como
  texto embebido). `cris_fos` y `cris_ocde_subject` quedaron excluidos del
  embedding: el primero por discriminar casi nada (6 valores posibles en toda
  la universidad); el segundo porque son URIs (`.../ford#5.07.03`), no texto
  — `clean_value()` las descarta en cualquier export, nunca aportaron un
  carácter.
- **Publicaciones ligadas**: `title` **y** `abstract`, aplicado directo sobre
  las 1 192 publicaciones declaradas como resultado de un proyecto del
  universo. De esas, 538 filas cumplían las dos por su propio texto, y tras
  deduplicar por publicación (9 comparten `publication_id` con otra)
  quedaban **529** distintas.

  Hasta el 2026-09-29 (`publications_linked-308`) el criterio era más
  estricto en dos sentidos, ambos revertidos el 2026-09-30: (1) exigía
  además `keywords` — de las 1 192 filas candidatas, `title` estaba lleno en
  71.3%, `abstract` en 45.1% y `keywords` en solo 30.8%; medido así,
  `keywords` era el cuello de botella real, no una señal de calidad
  adicional. (2) exigía que el proyecto que declaró la publicación también
  calificara bajo el criterio de `projects` vigente en ese momento
  (`title`+`knowledge_area`+línea de investigación, 409 proyectos) — esto
  acoplaba el universo de publicaciones a un criterio de otro dominio sin
  necesidad real: la pregunta relevante para esta unidad es si tiene
  suficiente texto propio, no si el proyecto que la declaró pasa hoy un
  umbral pensado para otro análisis. Con las dos exigencias, quedaban 308
  filas / 300 distintas (de esas 308, 351 habrían pasado sin exigir el
  proyecto padre). Sacar ambas casi duplicó la población: 300 → 529.

Implementación: `lb_domains.filter_min_requirements()` (para `projects`
delega en `qualifying_project_ids()`; `publications_linked` ya no depende de
esa función — su gate es directo sobre sus propias columnas), aplicado en la
etapa 01. El embudo completo, con la distribución de caracteres por unidad
resultante, está en la pestaña **Datos de origen** del atlas.

Al cambiar el universo se reusan, para las unidades que sobreviven, la
extracción por LLM y el embedding de texto completo ya calculados en la
corrida anterior (`scripts/pipeline_temas/seed_from_run.py`): son deterministas
en función del texto, no del resto del corpus, así que no hace falta volver a
pagarlos. Solo se recalculan la normalización (agrupamiento, que sí depende de
qué otras unidades hay) y la cuantificación. Esto vale cuando cambia *qué*
unidades entran pero no *su texto*, y tal como está escrito el script exige
que la corrida VIEJA sea superconjunto de la nueva (población que se achica o
se reordena, no que crece). No aplicó para ninguno de los dos cambios del
2026-09-29/30: en `projects` porque además cambió el texto embebido en sí
(nuevo `cris_abstract`, columnas de metadato removidas); en
`publications_linked` porque, aunque el texto de las 300 unidades que
sobreviven no cambió, la corrida nueva (529) es superconjunto de la vieja
(300), no al revés — el caso que este script no cubre. Se reextrajo desde
cero en ambos casos: `full-proj-646` (~USD 4.74) y `publications_linked-529`
(~USD 3.38); ninguno de los dos es costoso a esta escala, así que no se
invirtió en extender el script para este caso.

## 8. Cruce con los Objetivos Nacionales (PEDN 2050 / CEPLAN)

Encargo del equipo: introducir la matriz CEPLAN/PEDN 2050
(`datos/PEDN2050.xlsx`) y ver dónde se clasifica mejor cada tema normalizado
—de proyectos y de publicaciones, por separado— contra los 4 Objetivos
Nacionales (ON).

CEPLAN no pasa por el pipeline de extracción por LLM: su taxonomía (ON →
Temática → Sub-temática, hoja `Líneas de Inv.` del libro, 126 sub-temáticas
sobre 4 ON) ya es oficial y está nombrada por CEPLAN mismo, así que solo hace
falta embeberla con el mismo modelo que embebió los temas
(`cohere.embed-multilingual-v3`) para poder comparar. Implementación:
`scripts/lib/lb_ceplan.py` (parseo) y
`scripts/analysis/ceplan_alignment.py` (comparación + reporte).

Por cada tema normalizado se reporta su mejor sub-temática (la lectura más
específica), la Temática y el ON que implica, el score contra el centroide
del ON directamente, y el top-3. Antes de confiar en el ranking se valida que
los scores no estén comprimidos (ya pasó con otro modelo, en otro corpus:
`salidas/topics/policy_alignment_model_comparison_summary.md`, ahora
retirado) — en esta corrida el rango es 0.46–0.78, comparable al de la
similitud interna del propio agrupamiento, así que el ranking es señal real.

Un hallazgo a tener en cuenta al reportar: el ON implicado por la mejor
sub-temática solo coincide con el ON de mayor similitud directa en 92/136
temas de proyectos (68 %) y 59/101 de publicaciones (58 %) — las dos lecturas
(fina y gruesa) genuinamente discrepan en cerca de un tercio de los casos; los
reportes (`06_ceplan_alignment.json` / `reporte_ceplan_alignment.md` por
dominio) marcan cada discrepancia en vez de resolverla en silencio.

No se compara con ningún otro plan o política más allá del PEDN 2050 — eso
sigue fuera de alcance.

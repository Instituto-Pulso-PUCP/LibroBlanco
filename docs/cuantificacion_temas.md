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

| | proyectos (`full-proj-20261011`) | publicaciones ligadas (`publications_linked-20261011`) |
|---|---:|---:|
| unidades | 653 | 462 |
| temas extraídos por el LLM | 1 969 | 1 309 |
| temas normalizados | **137** | **93** |
| umbrales calibrados (líder / fusión) | 0.570 / 0.636 | 0.556 / 0.631 |
| tamaño de grupo (máx / mediana) | 72 / 11 | 56 / 10 |
| celdas no nulas · densidad | 5 327 · 5.95 % | 3 736 · 8.70 % |
| `PC` (normalizado) | 0.3945 (0.3901) | 0.4705 (0.4647) |
| entropía normalizada | 0.2731 | 0.2583 |
| temas efectivos por unidad | 2.92 | 2.49 |
| unidades efectivas por tema | 12.9 | 11.6 |

Los dos `PC` normalizados caen en la franja informativa (0.2 – 0.8): la
partición es difusa de verdad, y las dos lecturas dicen cosas distintas.

*(Corridas anteriores, intactas en RDS por si hace falta comparar:
`full-proj-646` —646 proyectos, 136 temas, antes de aplicar los overrides
manuales de CRIS— y `publications_linked-529` —529 publicaciones, 101 temas;
98 de ellas tenían un abstract de OpenAlex que era de otra obra, ver \S7—;
proyectos
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
  cerrados/2010+, y de esos, **653** cumplen las dos (646 hasta el
  2026-10-11, cuando `merge_cris_stdlib.py` empezó a aplicar los overrides
  manuales de `datos/cris_overrides.csv`).

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
  universo. Hoy 471 filas cumplen las dos y, tras deduplicar por publicación,
  quedan **462** distintas (corrida `publications_linked-20261011`).

  Hasta el 2026-10-10 eran 529, pero 98 de ellas tenían un abstract que no
  era suyo: la etapa de enriquecimiento buscaba la obra en OpenAlex por
  título y tomaba el primer resultado sin verificarlo (p.ej. el título de
  relleno «EXONERADO» trajo el resumen de un artículo sobre Carlos II). Desde
  entonces, un abstract obtenido por título solo se acepta si el título de la
  obra hallada coincide con el declarado (`scripts/lib/lb_titles.py`: misma
  obra si la similitud de secuencia ≥ 0.85, o si el título corto tiene al
  menos 3 palabras de contenido, al menos la mitad del largo del otro y el
  85 % de ellas aparecen en él; la primera versión de este control aceptaba
  títulos cortos contenidos en otra obra, como «EPICICLOS» → un artículo sobre
  Copérnico y Kepler). Se sumaron 30 abstracts buscados por DOI o título en
  Semantic Scholar, Crossref y OpenAlex con ese mismo control
  (`scripts/addons/recover_abstracts_external.py`, paso `externo` de la
  cascada): de 369 publicaciones sin abstract pero con algo con qué buscar,
  49 dieron resultado; 30 coincidían sin duda, 12 eran probablemente la misma
  obra con otro título y no se incluyeron, y 7 eran otra obra.

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

Desde el 2026-10-11 hay una variante que cubre los dos casos:
`scripts/pipeline_temas/seed_same_text.py` compara el texto de cada unidad
entre la corrida vieja y la nueva y reusa la extracción y el embedding **solo
de las idénticas**, sin importar si el universo crece, se achica o cambia de
texto; la etapa 02 consulta al LLM solo por las nuevas o cambiadas.
`scripts/pipeline_temas/rerun_universos.sh` encadena todo (merge CRIS →
cascada de publicaciones → etapas 01–05 por dominio con ese reuso → cruce
CEPLAN → atlas) y corre sin sesión interactiva. Así se hicieron
`full-proj-20261011` (7 unidades nuevas de 653) y
`publications_linked-20261011` (25 nuevas de 462): ~USD 1.25 en total, 14
minutos.

## 8. Cruce con los Objetivos Nacionales (PEDN 2050 / CEPLAN)

Preguntas del encargo, por dominio (proyectos y publicaciones, por separado):

- **¿Qué sub-temáticas del PEDN 2050 desarrolla este proyecto?** Hasta 5, con
  un mínimo de relación, no una sola.
- **¿Qué proyectos desarrollan esta sub-temática?** Y cuáles no desarrolla
  nadie.

Taxonomía: hoja `Líneas de Inv.` de `datos/PEDN2050.xlsx`, 126 sub-temáticas
sobre 4 Objetivos Nacionales (ON) → Temática → Sub-temática, enriquecidas con
el Objetivo Específico y las Acciones Estratégicas de las hojas `ON 1`..`ON 4`
(`scripts/lib/lb_ceplan.py`). CEPLAN no pasa por la extracción por LLM: su
taxonomía ya es oficial.

### 8.1 Método (`scripts/analysis/ceplan_units.py`)

1. **Candidatas por embeddings, en las dos direcciones.** Similitud coseno
   entre el embedding de cada unidad (el mismo de la etapa 03) y el de cada
   sub-temática, tomando la mayor entre su texto en español y una traducción
   al inglés (las publicaciones en inglés puntúan ~0.15 menos contra texto en
   español; traducción cacheada en `salidas/topics/ceplan/subtematicas_en.json`).
   - Por unidad: sus 8 sub-temáticas más cercanas con similitud ≥ 0.40.
   - Por sub-temática: sus 10 unidades más cercanas sobre el piso, con un
     tope de 6 agregadas por unidad. Sin esta vía inversa, las sub-temáticas
     que puntúan bajo contra todo (p.ej. «Saneamiento») no entraban al top de
     ninguna unidad aunque un proyecto de agua potable puntuara 0.65 contra
     ellas: aparecían como huecos que eran solo de recuperación.
2. **Verificación por LLM.** `us.meta.llama4-maverick-17b-instruct-v1:0` lee
   el texto de la unidad y califica cada candidata: 2 = la desarrolla
   claramente, 1 = relación tangencial, 0 = sin relación. Elegido con un
   benchmark de 7 modelos contra 100 pares calificados a mano
   (EXPERIMENTS.md §6): ningún modelo resultó mejor que otro con significancia,
   Sonnet 5 nunca fue mejor que los baratos, y Llama 4 Maverick quedó en el
   grupo de arriba al costo más bajo útil (~USD 0.30 por corrida completa).
3. **Cuantificación bidireccional**, la misma de §2 sobre otra matriz:
   `w[u,s] = peso(grado) × (similitud − 0.40)`, con peso 1 para grado 2 y 0.5
   para grado 1, solo en vínculos confirmados. *Cuánto de la unidad es la
   sub-temática* suma 100 % por unidad; *cuánto de la sub-temática aporta la
   unidad* suma 100 % por sub-temática. El listado por unidad muestra sus 5
   vínculos de mayor contención, pero el 100 % se reparte entre todos los
   confirmados, y la pregunta inversa usa todos.
4. **Cobertura** de cada sub-temática, contando solo vínculos de grado 2:
   *desarrollada* (≥ 3 unidades), *débil* (1–2), *sin desarrollo* (ninguna;
   puede tener tangenciales).

Salidas por dominio y corrida: `07_ceplan_units.json` (con todas las
candidatas evaluadas y su grado), `ceplan_por_unidad.csv`,
`ceplan_por_subtematica.csv`, `reporte_ceplan_unidades.md`; cobertura conjunta
en `salidas/topics/ceplan/reporte_cobertura.md`. En el atlas: pestaña
**Objetivos Nacionales** y bloque de sub-temáticas en el detalle de cada unidad.

### 8.2 Validación (EXPERIMENTS.md §6.5)

130 vínculos de 24 unidades elegidas al azar, calificados a ciegas:

- **84 % de los vínculos listados tienen una relación real** (proyectos 82 %,
  publicaciones 86 %).
- De los que el modelo marca «clara», el 91 % tiene relación real, pero solo
  el 53 % es «clara» para la persona. Por eso *desarrollada* se lee como
  «al menos 3 unidades con una relación de alta confianza», no como desarrollo
  claro.
- Lo que el modelo rechaza es casi siempre tangencial: de 24 candidatas
  rechazadas, solo 2 eran relaciones claras.

La validación se hizo sobre las corridas `full-proj-646` /
`publications_linked-529`; el método no cambió en las de 2026-10-11.

### 8.3 Resultado actual (corridas `full-proj-20261011`, `publications_linked-20261011`)

| | Proyectos | Publicaciones |
|---|---|---|
| Con al menos una sub-temática | 624 / 653 (96 %) | 325 / 462 (70 %) |
| Vínculos claros / tangenciales | 1 722 / 1 460 | 757 / 857 |
| Sub-temáticas desarrolladas / débiles / sin desarrollo | 102 / 22 / 2 | 76 / 37 / 13 |

Entre los dos dominios, solo *Minería ilegal* (ON3) no tiene ninguna relación
clara. Los huecos de publicaciones se concentran en ON3 (empleo decente,
MIPYME, turismo, transporte).

### 8.4 Qué no hace

- No mide si un proyecto *debería* desarrollar una sub-temática: solo si su
  texto (título, resumen, palabras clave) la toca.
- Una unidad sin candidatas sobre el piso queda sin sub-temática (4 proyectos,
  sobre todo matemática pura); es lo esperable en investigación básica.
- No se compara con ningún otro plan o política más allá del PEDN 2050.

**Retirado**: la versión anterior de este cruce comparaba cada *tema
normalizado* con las sub-temáticas (`scripts/analysis/ceplan_alignment.py`,
`06_ceplan_alignment.json`). Respondía otra pregunta (¿a qué sub-temática se
parece este tema?) y no decía qué desarrolla cada proyecto; ya no se muestra en
el atlas. El script y sus salidas se conservan.

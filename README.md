# Libro Blanco / Proyecto Pulso

Pipeline reproducible para estimar publicaciones potencialmente derivadas de proyectos de investigación cerrados desde 2010.

## Uso

1. Colocar el Excel original en `datos/informacion_proyecto_pulso.xlsx`.
2. Ejecutar todo el flujo:

```bash
python scripts/run_all.py
```

O por etapas:

```bash
python scripts/pipeline/01_build_pipeline.py
python scripts/pipeline/02_match_candidates.py
python scripts/pipeline/03_ground_truth_metrics.py
```

## Enriquecimiento OpenAlex: detener y reanudar

El paso lento del pipeline es el enriquecimiento con OpenAlex (limitado por la
tasa de la API). Ahora es **reanudable** y muestra una **barra de progreso** con
porcentaje, ETA y aciertos de cache:

- Cada resultado consultado se guarda de inmediato en `salidas/openalex_cache.jsonl`.
- Puede detener la ejecucion con **Ctrl-C** en cualquier momento; lo ya consultado
  queda en cache.
- Al volver a ejecutar, las filas en cache se sirven al instante y solo se
  consultan las pendientes (los errores transitorios como HTTP 429 se reintentan
  automaticamente; no se cachean).

Opciones de `pipeline/01_build_pipeline.py` (tambien disponibles en `run_all.py`):

```bash
python scripts/pipeline/01_build_pipeline.py --no-openalex   # construccion rapida, sin OpenAlex
python scripts/pipeline/01_build_pipeline.py --limit 50      # enriquece solo las primeras 50 filas (pruebas)
python scripts/pipeline/01_build_pipeline.py --no-cache      # ignora el cache y reconsulta todo
python scripts/pipeline/01_build_pipeline.py --skip-xlsx     # no genera los XLSX coloreados
```

Si el enriquecimiento se detuvo con errores transitorios (HTTP 429), se puede
reintentar sobre un CSV ya generado sin re-ejecutar todo el pipeline:

```bash
python scripts/addons/refresh_openalex_enrichment.py salidas/06_project_results_ground_truth.csv
```

## Salida XLSX con encabezados coloreados por fuente

Ademas de los CSV, el pipeline genera un XLSX legible para `06` y `07` con el
mismo contenido, pero con los **encabezados coloreados segun la fuente** de cada
columna (Proyecto/VRI, resultados declarados VRI, enlace del pipeline, OpenAlex,
resumenes). Incluye una hoja **Leyenda**, fila de encabezado congelada y filtros.

- `salidas/06_project_results_ground_truth.xlsx`
- `salidas/07_project_publication_ground_truth.xlsx`

Para exportar cualquier CSV manualmente:

```bash
python scripts/lib/export_xlsx.py salidas/06_project_results_ground_truth.csv salida.xlsx
```

## Integrar resumenes y palabras clave ("Obtencion de resumenes")

La carpeta `Obtención de resúmenes` contiene herramientas para recuperar
titulo/resumen/palabras clave por DOI (Scopus, PubMed, OpenAlex, Crossref) y para
integrar exportaciones de Scopus Web. Para **fusionar** esos resultados ya
calculados (`doi-resultados.csv`) con las salidas del pipeline, cruzando por DOI:

```bash
python scripts/addons/merge_resumenes.py                 # integra en 06 y 07 (busca el CSV automaticamente)
python scripts/addons/merge_resumenes.py --resumenes ruta/doi-resultados.csv
python scripts/run_all.py --with-resumenes                # como parte del flujo completo
```

Genera `*_con_resumenes.csv` y su XLSX coloreado. Solo agrega columnas de
resumen/palabras clave (con su procedencia); no modifica los datos existentes.

### Tres fuentes de resumen/palabras clave en `06`/`07`

`01_build_pipeline.py` puebla `06`/`07` con resumen y palabras clave desde
tres fuentes independientes, sin sobrescribirse entre sí:

- `resumen` / `palabras_clave` (+ `*_fuente`): resultado de la consulta por
  DOI a Scopus/PubMed/OpenAlex/Crossref ("Obtención de resúmenes"), integrado
  con `--with-resumenes`.
- `source_abstract` / `source_keywords`: **ya vienen en el Excel original**
  (columnas `Abstract`/`Author Keywords` de `Pubs_SCOPUS`, `abstract`/`keywords`
  de `Pubs_WoS`), agregadas en `03_publications_master.csv` y unidas a `06`/`07`
  por `publication_id`. No requieren ninguna llamada a API.
- `openalex_abstract`: reconstruido a partir de `abstract_inverted_index` en
  la respuesta de OpenAlex que el enriquecimiento estándar ya guarda en
  `06_..._openalex_raw_payload.jsonl`. Tampoco requiere una consulta adicional.

Como `source_abstract` y `openalex_abstract` provienen de datos que el
pipeline ya descarga/lee de todas formas, conviene revisarlas antes de volver
a ejecutar "Obtención de resúmenes": suelen cubrir la mayoría de los huecos
sin gastar cuota de la API de Elsevier.

## Salidas principales

- `salidas/libro_blanco.db`: base SQLite con las tablas normalizadas.
- `salidas/01_projects_closed.csv`: proyectos cerrados desde 2010.
- `salidas/02_investigators_master.csv`: investigadores normalizados desde ORCID y RI.
- `salidas/03_publications_master.csv`: publicaciones consolidadas RI + Scopus + WoS.
- `salidas/04_authorships.csv`: relación publicación-autor.
- `salidas/05_project_publication_candidates_v1.csv`: primera estimación proyecto-publicación.
- `salidas/06_project_results_ground_truth.csv`: resultados declarados por proyecto, enlazados a publicaciones por DOI cuando es posible.
- `salidas/07_project_publication_ground_truth.csv`: subconjunto de resultados declarados que corresponden a productos de publicación.
- `salidas/00_summary.json`: resumen de ejecución.

## Scripts

`scripts/` está organizado por rol:

- `scripts/run_all.py`: orquestador de entrada; ejecuta las tres etapas de `pipeline/` en orden.
- `scripts/pipeline/` — **etapa principal, secuencial**:
  - `01_build_pipeline.py`: construye la base normalizada, consolida publicaciones y genera los archivos `01` a `04`, además de `06`, `07` y un `00_summary.json` inicial.
  - `02_match_candidates.py`: genera `05_project_publication_candidates_v1.csv` y actualiza `00_summary.json` con métricas de matching contra el ground truth.
  - `03_ground_truth_metrics.py`: calcula métricas de precisión/recall contra el ground truth y escribe `00_ground_truth_metrics.json` / `.md`.
- `scripts/addons/` — pasos opcionales, ejecutables por separado o vía flags de `run_all.py`:
  - `refresh_openalex_enrichment.py`: reintenta el enriquecimiento OpenAlex sobre un CSV ya generado, para filas que fallaron con HTTP 429.
  - `merge_resumenes.py`: integra resúmenes/palabras clave desde "Obtención de resúmenes" en `06`/`07` (cruce por DOI).
- `scripts/lib/` — utilidades compartidas, no se ejecutan directamente:
  - `openalex_helpers.py`: cliente OpenAlex (query building, fetch, cache persistente).
  - `pipeline_utils.py`: barra de progreso reanudable sin dependencias externas.
  - `export_xlsx.py`: exporta un CSV/DataFrame a XLSX con encabezados coloreados por fuente.
- `scripts/analysis/` — análisis puntuales, no forman parte del flujo automatizado y no modifican las salidas:
  - `compare_v1_v2.py`: compara la cobertura de v1 contra un enlace directo `COD_AERI + DOI` usando `PROY_RESULTADOS`.
  - `efficacy_analysis.py`: resume cobertura, distribución de puntajes y patrones de evidencia a partir de las salidas ya generadas.
  - `project_semantic_analysis.py`: vectoriza los proyectos (TF-IDF o sentence-transformers) y aplica PCA + KMeans para explorar clusters temáticos.

## Nota metodológica

La versión 1 hace matching conservador: exige que el responsable del proyecto aparezca como autor por coincidencia normalizada exacta. Scopus usa nombres de autores y Scopus Author IDs; RI usa `idperson` y nombre del profesor. La hoja WoS entregada no incluye nombres de autores, por lo que WoS solo enriquece registros cuando se consolida por DOI o título/año.

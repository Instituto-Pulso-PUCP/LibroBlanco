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
python scripts/run_pipeline.py
python scripts/02_match_candidates.py
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

Opciones de `run_pipeline.py` (tambien disponibles en `run_all.py`):

```bash
python scripts/run_pipeline.py --no-openalex   # construccion rapida, sin OpenAlex
python scripts/run_pipeline.py --limit 50      # enriquece solo las primeras 50 filas (pruebas)
python scripts/run_pipeline.py --no-cache      # ignora el cache y reconsulta todo
python scripts/run_pipeline.py --skip-xlsx     # no genera los XLSX coloreados
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
python scripts/export_xlsx.py salidas/06_project_results_ground_truth.csv salida.xlsx
```

## Integrar resumenes y palabras clave ("Obtencion de resumenes")

La carpeta `Obtención de resúmenes` contiene herramientas para recuperar
titulo/resumen/palabras clave por DOI (Scopus, PubMed, OpenAlex, Crossref) y para
integrar exportaciones de Scopus Web. Para **fusionar** esos resultados ya
calculados (`doi-resultados.csv`) con las salidas del pipeline, cruzando por DOI:

```bash
python scripts/merge_resumenes.py                 # integra en 06 y 07 (busca el CSV automaticamente)
python scripts/merge_resumenes.py --resumenes ruta/doi-resultados.csv
python scripts/run_all.py --with-resumenes        # como parte del flujo completo
```

Genera `*_con_resumenes.csv` y su XLSX coloreado. Solo agrega columnas de
resumen/palabras clave (con su procedencia); no modifica los datos existentes.

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

- `scripts/run_all.py`: ejecuta `run_pipeline.py` y luego `02_match_candidates.py`.
- `scripts/run_pipeline.py`: construye la base normalizada, consolida publicaciones y genera los archivos `01` a `04`, además de `06`, `07` y un `00_summary.json` inicial.
- `scripts/02_match_candidates.py`: genera `05_project_publication_candidates_v1.csv` y actualiza `00_summary.json` con métricas de matching contra el ground truth.
- `scripts/compare_v1_v2.py`: compara la cobertura de v1 contra un enlace directo `COD_AERI + DOI` usando `PROY_RESULTADOS`; es un análisis auxiliar y no modifica las salidas principales.
- `scripts/efficacy_analysis.py`: resume cobertura, distribución de puntajes y patrones de evidencia a partir de las salidas ya generadas; usa rutas relativas al repositorio.

## Nota metodológica

La versión 1 hace matching conservador: exige que el responsable del proyecto aparezca como autor por coincidencia normalizada exacta. Scopus usa nombres de autores y Scopus Author IDs; RI usa `idperson` y nombre del profesor. La hoja WoS entregada no incluye nombres de autores, por lo que WoS solo enriquece registros cuando se consolida por DOI o título/año.

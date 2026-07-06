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

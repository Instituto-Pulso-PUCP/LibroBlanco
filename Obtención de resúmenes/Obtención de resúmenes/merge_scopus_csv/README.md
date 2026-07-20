# Integración de exportaciones de Scopus Web

Este programa cruza el CSV producido por el script de recuperación de
resúmenes con uno o varios archivos CSV exportados manualmente desde la
interfaz web de Scopus.

## Qué completa

Solo completa campos vacíos:

- `titulo`
- `scopus_id`
- `eid`
- `resumen`
- `palabras_clave`
- `pubmed_id`

Cuando completa título, resumen o palabras clave, registra `Scopus Web` como
fuente.

## Archivos generados

Si la salida se llama `doi-resultados-final.csv`, se generan:

- `doi-resultados-final.csv`: resultado integrado.
- `doi-resultados-final_scopus_unificado.csv`: todos los registros exportados
  de Scopus, consolidados por DOI.
- `doi-resultados-final_duplicados_scopus.csv`: DOI repetidos entre las
  exportaciones.
- `doi-resultados-final_log_archivos.csv`: archivos procesados y errores.
- `doi-resultados-final_estadisticas.csv`: resumen cuantitativo.
- `doi-resultados-final_pendientes.csv`: registros que aún no tienen resumen
  o palabras clave.

## Columnas necesarias en la exportación de Scopus

Seleccione como mínimo:

- Document title
- EID
- DOI
- Abstract
- Author keywords
- Indexed keywords

PubMed ID es opcional.

El script reconoce automáticamente nombres frecuentes de columnas en inglés y
español.

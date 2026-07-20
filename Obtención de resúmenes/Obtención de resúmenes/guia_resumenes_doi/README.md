# Recuperación de resúmenes y palabras clave por DOI

Este paquete permite consultar una lista de DOI y recuperar:

- título;
- Scopus ID;
- EID;
- resumen;
- palabras clave;
- PubMed ID;
- OpenAlex ID;
- fuente de cada campo recuperado;
- estado de la consulta a Scopus.

## Orden de consulta

1. Scopus
2. PubMed
3. OpenAlex
4. Crossref

Las fuentes secundarias solo completan campos que continúan vacíos.

## Archivos incluidos

- `resumenes_por_doi.py`: script principal.
- `requirements.txt`: dependencias.
- `doi_ejemplo.csv`: archivo de entrada de ejemplo.
- `GUIA_WINDOWS.md`: instalación y ejecución en Windows.
- `GUIA_LINUX.md`: instalación y ejecución en Linux.
- `ejecutar_windows.bat`: ejemplo de ejecución en Windows.
- `ejecutar_linux.sh`: ejemplo de ejecución en Linux.

## Salida

El resultado se guarda únicamente en CSV con codificación UTF-8 con BOM,
compatible con Excel.

## Seguridad

Nunca escriba la API Key dentro del script ni la comparta en capturas,
mensajes o repositorios públicos.

# Metodología del ejercicio

## Objetivo

Recuperar metadatos descriptivos de publicaciones a partir de una lista de DOI.

## Campos obtenidos

- título;
- Scopus ID;
- EID;
- resumen;
- palabras clave;
- identificadores PubMed y OpenAlex;
- fuente utilizada para cada campo.

## Jerarquía de fuentes

1. Scopus: fuente principal.
2. PubMed: respaldo para publicaciones biomédicas.
3. OpenAlex: respaldo multidisciplinario abierto.
4. Crossref: último respaldo basado en metadatos depositados por las editoriales.

## Regla de integración

Una fuente posterior no reemplaza un campo recuperado por una fuente anterior.
Solo completa campos vacíos.

## Consideraciones de calidad

- Un DOI válido no garantiza que el registro exista en todas las fuentes.
- Un registro puede existir sin resumen o sin palabras clave.
- Los términos MeSH de PubMed no son necesariamente palabras clave del autor.
- Los temas de OpenAlex son términos calculados y deben distinguirse de las
  palabras clave editoriales.
- Los metadatos de Crossref dependen de lo depositado por cada editorial.
- La procedencia de cada campo debe conservarse para auditoría y control de calidad.

## Evidencia y trazabilidad

Las columnas `fuente_resumen` y `fuente_palabras_clave` permiten saber qué
servicio proporcionó cada dato. No deben eliminarse durante la etapa de
validación.

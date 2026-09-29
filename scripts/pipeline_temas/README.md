# Pipeline de temas

Extrae temas de cada proyecto/publicación, los normaliza, y cuantifica la
relación en **las dos direcciones**: cuánto de cada unidad es de cada tema, y
cuánto de cada tema lo aporta cada unidad.

**Proyectos y publicaciones son dominios separados con espacios de temas
independientes.** No se mezclan ni se comparan. Para procesar los dos, se corre
el pipeline dos veces.

El contraste contra planes nacionales / políticas **está pausado** y no forma
parte de este flujo; ver el aviso en
[`docs/topic_normalization_pipeline.md`](../../docs/topic_normalization_pipeline.md).

## Uso

```bash
# 0. Qué falta configurar (correr tras cada cambio de infraestructura)
python scripts/pipeline_temas/00_check_infra.py

# Pipeline completo de un dominio
python scripts/pipeline_temas/run_domain.py --domain projects
python scripts/pipeline_temas/run_domain.py --domain publications

# Prueba barata antes de gastar en el LLM
python scripts/pipeline_temas/run_domain.py --domain projects --limit 20
python scripts/pipeline_temas/run_domain.py --domain projects --dry-run

# Reanudar desde una etapa (reusa el run_id anterior del dominio)
python scripts/pipeline_temas/run_domain.py --domain projects --from 04
```

## Etapas

| | Script | Qué hace | ¿Necesita AWS? |
|---|---|---|---|
| 00 | `00_check_infra.py` | Diagnostica configuración y permisos | no |
| 01 | `01_prep_units.py` | Unidades de texto + **reporte de insumos** (filas, columnas embebidas, tasa de llenado) | no |
| 02 | `02_extract_topics.py` | Temas por unidad con LLM, con evidencia literal verificada | **sí** (Bedrock/LibreChat) |
| 03 | `03_normalize_topics.py` | Agrupa temas extraídos en temas normalizados y los nombra | **sí** (Bedrock) |
| 04 | `04_quantify.py` | Contención, contribución e índices de partición | no |
| 05 | `05_report.py` | Reportes de temas, cuantificación y **consumo de recursos** | no |
| — | `seed_from_legacy.py` | Importa los temas ya hechos a mano, para probar 04–05 sin AWS | no |

La etapa 02 es reanudable: cada unidad resuelta se escribe al instante en
`02_extraction_cache.jsonl` y un rerun salta lo que ya está. Se puede cortar
con Ctrl-C sin perder lo pagado.

## Salidas

En `salidas/topics/<dominio>/<run_id>/`:

| Archivo | Contenido |
|---|---|
| `reporte_insumos.md` | Filas usadas, columnas que entran al embedding y su tasa de llenado |
| `reporte_temas.md` | Temas normalizados, tamaño en unidades-equivalentes, quién los sostiene |
| `reporte_cuantificacion.md` | Índices de partición y las dos lecturas con ejemplos |
| `reporte_uso.md` | Tokens, llamadas, bytes y costo por etapa; extrapolación por unidad |
| `cuantificacion.csv` | Tabla larga `unidad × tema` con afinidad, contención y contribución |
| `uso_*.json` | Medición cruda de cada etapa |

Con `run.store = "rds"` todo va además a las tablas de
[`sql/schema.sql`](../../sql/schema.sql); con `run.use_s3 = true`, a S3.

## Configuración

`config/pipeline.toml` (copiar de `config/pipeline.example.toml`). Cualquier
valor se puede sobrescribir por entorno: `LB_BEDROCK__LLM_MODEL_ID=...`.

Qué falta rellenar hoy: [`docs/infraestructura_aws.md`](../../docs/infraestructura_aws.md).

## Añadir otro dataset

Una entrada en `DOMAINS` de [`scripts/lib/lb_domains.py`](../lib/lb_domains.py)
—CSV de origen, columna de id, columnas de texto, columnas excluidas con su
motivo— y el resto del pipeline funciona sin cambios. El reporte de insumos y
el de consumo permiten comparar la corrida nueva contra las anteriores.

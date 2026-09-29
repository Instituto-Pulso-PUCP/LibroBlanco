# Infraestructura: qué falta configurar

Estado medido en este servidor el 2026-09-23 por
`python scripts/pipeline_temas/00_check_infra.py`. Ese script es la fuente de
verdad: vuelve a correrlo después de cada cambio, no confíes en esta lista.

## Lo que hay hoy

| | Estado |
|---|---|
| Servidor | aarch64, 2 vCPU, **1 GB RAM**, sin GPU |
| Python | 3.14.4 del sistema, **sin pip, sin numpy, sin pandas** |
| Paquetes disponibles | `boto3` 1.40.72, `awscli` 2.31.35 |
| Credenciales AWS | usuario IAM `s3-pulso-vri`, cuenta `861677364255`, región `us-east-1` |
| S3 | credencial válida, **sin permisos** (`s3:ListAllMyBuckets` denegado) |
| Bedrock | **sin permisos** (`bedrock:InvokeModel` denegado) |
| RDS | **sin permisos** (`rds:DescribeDBInstances` denegado), sin endpoint |
| LibreChat | sin endpoint configurado |

Con 1 GB de RAM y sin numpy, **el cómputo local no es una opción**: cargar un
modelo de embeddings en este servidor no cabe en memoria. Por eso el pipeline
delega embeddings y LLM en Bedrock, y todo el código propio es stdlib pura.

## Lo que hay que rellenar

Copia la plantilla y edítala:

```bash
cp config/pipeline.example.toml config/pipeline.toml
```

`config/pipeline.toml` está en `.gitignore` y no se versiona.

### 1. Permisos IAM

El usuario `s3-pulso-vri` (o mejor, un **rol de instancia** adjunto a este EC2,
para no tener claves de larga duración en disco) necesita:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "S3",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
      "Resource": ["arn:aws:s3:::EL-BUCKET", "arn:aws:s3:::EL-BUCKET/*"] },
    { "Sid": "Bedrock",
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
      "Resource": ["arn:aws:bedrock:us-east-1::foundation-model/*"] },
    { "Sid": "BedrockListado",
      "Effect": "Allow",
      "Action": ["bedrock:ListFoundationModels", "bedrock:GetFoundationModel"],
      "Resource": "*" },
    { "Sid": "RDSIAM",
      "Effect": "Allow",
      "Action": ["rds-db:connect"],
      "Resource": ["arn:aws:rds-db:us-east-1:861677364255:dbuser:RESOURCE-ID/pulso_app"] }
  ]
}
```

Además, en la consola de **Bedrock → Model access**, hay que **solicitar acceso
a cada modelo**: tener el permiso IAM no basta, son dos cosas distintas y es el
error más común al empezar.

### 2. Valores de `config/pipeline.toml`

| Clave | Qué poner | Cómo se obtiene |
|---|---|---|
| `s3.bucket` | nombre del bucket | crearlo (`aws s3 mb`) o pedir el existente |
| `rds.host` | endpoint de la instancia | consola RDS → Connectivity → Endpoint |
| `rds.database` | nombre de la base | el que se dio al crearla, p.ej. `libroblanco` |
| `rds.user` | usuario de aplicación | crearlo en la base, ver abajo |
| `bedrock.llm_model_id` | id del modelo de extracción | ver §3 |
| `bedrock.embedding_model_id` | id del modelo de embeddings | viene puesto `cohere.embed-multilingual-v3`; confirmar que está habilitado |
| `pricing.*` | precios vigentes | https://aws.amazon.com/bedrock/pricing/ y la consola de facturación |
| `librechat.*` | solo si se usa LibreChat como pasarela | opcional, ver §4 |

Después, cambiar `run.store = "rds"` y `run.use_s3 = true`.

**Los precios importan.** Mientras `[pricing]` esté en 0, el reporte de consumo
sale con costo 0 y una advertencia. Los tokens y las llamadas sí se miden bien;
lo que falta es la tabla de conversión a dólares.

### 3. Elección de modelos

**Embeddings.** El corpus es mayoritariamente español, y ya hay evidencia en
[EXPERIMENTS.md](../EXPERIMENTS.md) de que la calibración del modelo importa
más que su ranking general. `cohere.embed-multilingual-v3` (1024 dim) es la
opción por defecto: multilingüe real y acepta 96 textos por llamada.
`amazon.titan-embed-text-v2:0` es más barato pero acepta **un texto por
llamada**, lo que multiplica por 96 el número de invocaciones y el tiempo.

Si se cambia de modelo hay que ajustar `bedrock.embedding_dimensions` **y** la
dimensión del tipo `vector(1024)` en [`sql/schema.sql`](../sql/schema.sql).

**LLM de extracción.** Cualquier modelo Claude disponible en Bedrock sirve; el
id va en `bedrock.llm_model_id` con el prefijo de perfil de inferencia
(`anthropic.…`). Para elegir entre los disponibles en la cuenta:

```bash
aws bedrock list-foundation-models --region us-east-1 \
  --query 'modelSummaries[].modelId' --output table
```

La extracción corre con `temperature = 0`: la reproducibilidad de la corrida
depende de eso, no lo subas sin motivo.

### 4. RDS

```bash
# 1. Aplicar el esquema
psql "host=... dbname=... user=... sslmode=require" -f sql/schema.sql

# 2. Si se usa auth IAM (recomendado), en la base:
CREATE USER pulso_app WITH LOGIN;
GRANT rds_iam TO pulso_app;
GRANT USAGE ON SCHEMA libroblanco TO pulso_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA libroblanco TO pulso_app;
```

`sql/schema.sql` incluye `CREATE EXTENSION vector` (pgvector) para guardar los
embeddings en la base. Requiere un usuario con `rds_superuser` **una sola vez**
por base de datos. Si no se quiere pgvector, poner `rds.use_pgvector = false` y
los vectores irán a S3.

**Falta un driver de PostgreSQL en este servidor.** No hay pip. Opciones:

```bash
sudo apt install -y python3-psycopg2        # la más simple
# o, para aislar el entorno:
sudo apt install -y python3-venv && python3 -m venv .venv && \
  .venv/bin/pip install 'psycopg[binary]'
```

### 5. LibreChat (opcional)

Solo cubre el paso de LLM, nunca los embeddings. Tiene sentido si el equipo
quiere que las llamadas queden registradas en la misma instancia que ya usa.
Poner `librechat.enabled = true`, `base_url`, `model`, y la clave en la
variable de entorno `LB_LIBRECHAT__API_KEY` (no en el TOML).

Con LibreChat de por medio, el reporte de consumo depende de que la pasarela
devuelva `usage` en la respuesta. Si no lo hace, los tokens salen en 0 y el
costo del paso de LLM queda sin medir — razón para preferir Bedrock directo
mientras el consumo sea algo que haya que reportar.

## Qué funciona ya, sin nada de lo anterior

```bash
python scripts/pipeline_temas/00_check_infra.py                       # diagnóstico
python scripts/pipeline_temas/01_prep_units.py --domain projects      # unidades + reporte de insumos
python scripts/pipeline_temas/01_prep_units.py --domain publications
python scripts/pipeline_temas/seed_from_legacy.py --domain projects --run-id legacy-49
python scripts/pipeline_temas/04_quantify.py --domain projects --run-id legacy-49 --affinity extraction
python scripts/pipeline_temas/05_report.py --domain projects --run-id legacy-49
```

Las etapas 02 y 03 son las únicas que necesitan Bedrock.

## Problema de datos detectado (independiente de la infraestructura)

`salidas/01_projects_closed_con_cris.csv` en este servidor tiene **975 filas y
`cris_abstract` lleno en 9 (0.9%)**. `EXPERIMENTS.md` documenta que el export
bueno tiene **984 filas con `cris_abstract` al 66.6%** y corrige expresamente
las cifras bajas como pertenecientes a un export viejo y más delgado.

Es decir: **el CSV que hay aquí es el export antiguo**. Los CSV de `datos/` y
`salidas/` no están versionados (`.gitignore` excluye `*.csv`), y los exports
CRIS (`ProyectosPUCPCRIS-20260721.csv`, `-20260814.csv`) no llegaron a este
servidor.

Correr la extracción de temas así significaría pagar el LLM para leer
básicamente títulos: 142 caracteres de media por proyecto contra los ~1.100 de
publicaciones. **Hay que traer el export CRIS bueno antes de correr la etapa
02 para proyectos.** Publicaciones no tiene este problema (13.995 filas,
`abstract`/`keywords`/`journal` completos).

El reporte de insumos de la etapa 01 detecta esto automáticamente en cada
corrida; ver `salidas/topics/<dominio>/<run>/reporte_insumos.md`.

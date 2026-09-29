#!/usr/bin/env bash
# Secretos del pipeline. Copiar a config/env.sh, rellenar y cargar con:
#
#     source config/env.sh
#
# config/env.sh esta en .gitignore. NO lo versiones, no lo pegues en un chat,
# no lo adjuntes en un correo.
#
# Cualquier clave de config/pipeline.toml se puede sobrescribir aqui con el
# prefijo LB_ y la ruta en mayusculas separada por doble guion bajo:
#     [rds] host        ->  LB_RDS__HOST
#     [gateway] api_key ->  LB_GATEWAY__API_KEY

# ---------------------------------------------------------------------------
# 1. RDS — la clave de la base (usuario pulsovri)
# ---------------------------------------------------------------------------
export LB_RDS__PASSWORD='PEGAR_AQUI_LA_CLAVE_DE_LA_BD'

# ---------------------------------------------------------------------------
# 2. Pasarela de Bedrock — la "API Key" que acompana a OPENAI_BASE_URL
# ---------------------------------------------------------------------------
export LB_GATEWAY__API_KEY='PEGAR_AQUI_LA_API_KEY'
# Y el endpoint, si se prefiere no dejarlo en pipeline.toml:
# export LB_GATEWAY__BASE_URL='https://...'

# ---------------------------------------------------------------------------
# 3. AWS — los pares "Access key ID" / "Secret access key"
#
# NO van aqui. Van en ~/.aws/credentials como perfiles con nombre, que es el
# mecanismo estandar y el que boto3 espera. Con dos pares distintos (uno para
# S3, otro para Bedrock), crear dos perfiles:
#
#     aws configure --profile s3-pulso     # pide las claves de S3
#     aws configure --profile bedrock      # pide las claves de Bedrock
#
# y luego, en config/pipeline.toml:
#     [s3]      profile = "s3-pulso"
#     [bedrock] profile = "bedrock"
#
# Si ambos servicios usan el MISMO par, basta con dejar los dos perfiles
# vacios: se usa el [default] que ya esta en ~/.aws/credentials.
#
# Mejor aun: adjuntar un rol de instancia a este EC2 y borrar las claves del
# disco. boto3 lo toma solo, sin cambiar nada de la configuracion.
# ---------------------------------------------------------------------------

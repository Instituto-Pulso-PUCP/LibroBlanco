# Estado del pipeline de temas — 2026-09-23

## Para lanzar publicaciones

```bash
cd ~/LibroBlanco
setsid nohup ./lanzar_publicaciones.sh > /dev/null 2>&1 &
```

Sobrevive al cierre de la terminal. Ver progreso en cualquier momento, desde
cualquier sesion:

```bash
./estado.sh          # procesos, memoria, filas en RDS, avance de la extraccion
tail -f salidas/topics/publications/ultimo.log
```

El script hace, deteniendose al primer fallo:
0. comprobacion de infraestructura
1. piloto de 400 publicaciones (muestra aleatoria, ~USD 3)
2. **puerta de validacion**: PC en rango informativo, <2% de errores, 0 celdas
   huerfanas, RAM proyectada < 900 MB. Si no pasa, NO gasta en la completa.
3. corrida completa de 13.995 (~20 h, ~USD 97 estimados)

Interrumpible con Ctrl-C o `pkill -f pipeline_temas`: la etapa 02 cachea cada
unidad en `02_extraction_cache.jsonl`, asi que un rerun no vuelve a pagarlas.
Reanudar con:

```bash
source config/env.sh
python3 scripts/pipeline_temas/run_domain.py --domain publications \
    --run-id pubs-full-13995 --from 02
```

## Proyectos: TERMINADO

`full-proj-975`, 2026-09-23 04:48 UTC, estado `ok`.
975 proyectos · 1.928 temas extraidos · **49 temas normalizados** ·
7.801 celdas · PC normalizado 0,505 · 2,27 temas efectivos por proyecto ·
**USD 5,68** · ~25 min. Salidas en `salidas/topics/projects/full-proj-975/`
y en `s3://pulso-vri-pucp/libroblanco/runs/full-proj-975/`.

## El problema de memoria: RESUELTO

Los vectores se guardaban como listas de float de Python (~33 bytes por numero).
A escala de publicaciones eran ~1,6 GB en una maquina de 1,8 GB: moria en la
etapa 03 **despues** de pagar las 14.000 llamadas de extraccion.

Ahora son matrices `numpy` float32 de extremo a extremo (Bedrock -> agrupamiento
-> pgvector). No se pierde precision: pgvector almacena `vector` en float32, asi
que los embeddings ya venian redondeados a esa precision desde la base.

Medido a escala real (35.000 temas x 1024 dims, con la geometria de los
embeddings reales, bajo un limite duro de 440 MB):

| | Antes | Ahora |
|---|---:|---:|
| Memoria (49k vectores) | 1.638 MB | **201 MB** |
| RSS pico a escala completa | ~4.000 MB (proyectado) | **324 MB** (medido) |
| Agrupamiento etapa 03 | ~13 h (proyectado) | **8,7 s** (medido) |

Se verifico que el refactor es **identico en comportamiento**: mismas
asignaciones de grupo en 5 combinaciones de umbrales; diferencia maxima entre
centroides 6,7e-08.

## Avisos que deben acompañar cualquier informe

- **37% de los proyectos (356/975)** apoyan su texto en resultados declarados:
  para esos el tema describe lo que el proyecto **publico**, no lo que propuso.
- **42 proyectos (4,3%)** no produjeron ningun tema extraido (solo tenian
  titulo). Reciben tema por similitud, **sin evidencia textual detras**.
- El export CRIS en disco es el **delgado** (`dc.description.abstract` al 8,2%
  en origen, 0,9% tras el cruce; los que si tienen resumen son proyectos de
  2023-2025, fuera de este universo). Pedir `ProyectosPUCPCRIS-20260814.csv`.
- `[pricing]` lleva tarifas de **primera parte de Anthropic para Sonnet 5**
  (USD 2/10 por millon), no las de Bedrock. Confirmar en la consola de
  facturacion antes de publicar un costo.
- El coste de embeddings **no esta incluido**: Bedrock no devuelve tokens
  facturados para Cohere. Se reporta el numero de textos embebidos.
- El modelo de embeddings (`cohere.embed-multilingual-v3`) **no esta
  comparado** contra alternativas en este corpus. Los del registro antiguo
  (`EXPERIMENTS.md`: jina, minilm, bge-m3...) son locales y no caben aqui.
  Su distribucion de similitud si se midio y usa bien el rango (mediana 0,44,
  p95 0,59), a diferencia del defecto documentado de jina-v5-nano.

## LibreChat: descartado como via de ejecucion

No expone API compatible con OpenAI (`/v1/chat/completions` devuelve el HTML de
la web) y su `/api/balance` rechaza la API key con 401. El saldo de 20 M solo se
gasta desde el navegador. La clave `ABSK...` de la OTD es una **API key de
Bedrock** (cuenta 861677364255): factura igual que boto3, y el endpoint
compatible con OpenAI de Bedrock **no sirve modelos Claude** (solo de peso
abierto como `openai.gpt-oss-20b-1:0`). El codigo de pasarela esta construido y
probado por si la OTD habilita un endpoint real.

## Nada esta commiteado

Todo el trabajo esta en el working tree (`git status`). Secretos en
`config/env.sh` (chmod 600, gitignored, respaldo en `config/env.sh.bak`).

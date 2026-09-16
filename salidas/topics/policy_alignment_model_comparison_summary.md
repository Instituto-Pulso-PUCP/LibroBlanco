# Resumen: comparación minilm vs. jina-v5-nano para alineación tema-política

Generado automáticamente tras habilitar GPU (GTX 1650 Ti, 4GB) y correr
`jina-v5-nano` sobre el corpus completo de políticas (30,963 chunks, 946
documentos) para comparar contra `minilm-multilingual` sin el sesgo de
candidatos de la validación anterior (que solo probó contra los documentos
que `minilm` ya había puesto en su propio top-5).

## Qué se comparó

401 temas normalizados (49 proyectos + 352 publicaciones) × 946 documentos
de política, con ambos modelos, corpus completo, sin muestreo.

- `salidas/topics/topic_policy_alignment_minilm-multilingual.json` — **salida canónica**, usada por el explorador publicado.
- `salidas/topics/topic_policy_alignment_jina-v5-nano.json` — solo para esta comparación, no es la salida canónica.

## Resultados

| Métrica | minilm-multilingual | jina-v5-nano |
|---|---|---|
| Score del mejor match — media | 0.489 | 0.764 |
| Score del mejor match — mediana | 0.505 | 0.771 |
| Score del mejor match — desviación | 0.149 | 0.106 |
| Score del mejor match — mínimo (todo el corpus) | 0.130 | **0.430** |
| Score del mejor match — máximo | 0.786 | 0.969 |

- Solapamiento promedio del top-3 entre ambos modelos: **0.80 de 3 (~27%)**.
- 159/401 temas (40%) sin ningún documento en común en el top-3.
- Solo 11/401 temas (2.7%) con acuerdo total (3/3).
- El desacuerdo **no se concentra en temas de baja confianza**: incluso para
  los 153 temas donde `minilm` da su score más alto (≥0.55), `jina-v5-nano`
  no comparte ningún documento del top-3 el 39% de las veces.

## Conclusión

El hallazgo de la validación anterior (muestra de 14 temas / 64 documentos
candidatos) se confirma y refuerza a escala completa: `jina-v5-nano`
comprime todos los scores hacia arriba — ni el tema con menor score de los
401 baja de 0.43 — lo que le impide separar señal de ruido tan bien como
`minilm-multilingual`, que sí usa la parte baja de la escala (mínimo 0.13)
para temas genuinamente sin relación con ninguna política.

**Se mantiene `minilm-multilingual` como modelo para este paso.** La
disponibilidad de GPU cambió el cálculo de costo (jina ya no toma 14h, toma
~35-40 min) pero no cambió la conclusión de calidad — de hecho la reforzó,
porque ahora se comparó contra el corpus completo, no solo contra una
muestra sesgada hacia los propios candidatos de `minilm`.

## Detalle técnico de la corrida en GPU

- PyTorch reinstalado con soporte CUDA: `torch==2.6.0+cu124`.
- `scripts/lib/embeddings.py` ahora detecta CUDA automáticamente en vez de
  forzar `device='cpu'`.
- Los chunks más largos del corpus (hasta 26,630 caracteres) provocan OOM
  en los 4GB de VRAM sin límite de secuencia — mitigado capando
  `max_seq_length=2048` (cubre percentil 99.9 de chunks sin truncar nada)
  + `batch_size=16`. Verificado sin OOM contra los 16 chunks más largos
  reales del corpus antes de confiar en la corrida completa.
- Ver `docs/topic_normalization_pipeline.md` para el detalle completo
  (estructura del corpus, metodología, limitaciones conocidas).

## Qué no cambia

- El explorador publicado (`salidas/topics/explorador_alineacion_politicas.html`,
  https://claude.ai/artifact/2zyRJzQTheWBFMVfHAWhWv) sigue usando la salida
  de `minilm-multilingual` — no requiere ninguna actualización por esta
  comparación.
- No se ha corrido ningún otro modelo del registro (`bge-m3`,
  `snowflake-arctic-l-v2`, etc.) contra el corpus completo de políticas —
  la comparación fue específicamente `minilm` vs. el modelo que ganaba los
  benchmarks de clustering intra-dominio (`jina-v5-nano`), no un barrido
  exhaustivo de todo el registro.

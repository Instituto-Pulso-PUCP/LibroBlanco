# Adaptadores de dataset

Cada institución entrega sus datos en su propio formato. Un adaptador los
convierte a cuatro CSV estándar en `salidas/datasets/<dataset>/`; desde ahí el
pipeline es el mismo para todos. El adaptador no decide el universo: pasa lo
que se recibió (solo descarta filas vacías).

| Archivo | Columnas |
|---|---|
| `projects.csv` | `project_id, title, abstract, keywords, year, ...` |
| `publications.csv` | `publication_id, title, abstract, keywords, doi, year, journal, abstract_source, ...` |
| `links.csv` | `project_id, publication_id, link_type` |
| `policies.csv` | `policy_id, label, text, l1_id, l1_label, l2_id, l2_label, ...` (hojas del plan nacional; `text` es lo que se embebe) |

`keywords` es solo de autor. Las generadas por terceros (OpenAlex) van en otra
columna y no se embeben.

## Añadir un dataset

1. `scripts/datasets/<dataset>.py` que escriba los cuatro CSV (ver `ecotec.py`).
2. Si las publicaciones llegan sin abstract: `recover_abstracts_external.py
   --publications ...`, `build_external_candidates.py`, revisión a mano de las
   filas `revisar` y volver a correr el adaptador (pasos en el docstring de
   `ecotec.py`).
3. Un `Domain` por tipo de unidad en `scripts/lib/lb_domains.py` (con
   `dataset`, `kind` y `plan`).
4. El plan nacional en `scripts/lib/lb_plans.py`.
5. El valor del enum en RDS: un archivo en `sql/migrations/`.

## ECOTEC en el servidor

`datos/` y `salidas/` no se versionan: copiar `datos/ecotec/` y
`salidas/datasets/ecotec/` (en especial `abstracts_recuperados/candidatos.csv`,
que guarda las decisiones a mano).

```bash
cd ~/LibroBlanco && git pull && source config/env.sh
psql "$LB_DSN" -f sql/migrations/20261028_ecotec_domains.sql   # una sola vez
python3 scripts/datasets/ecotec.py                              # rehace los CSV estándar

python3 scripts/pipeline_temas/run_domain.py --domain ecotec_projects --limit 5   # prueba barata
python3 scripts/pipeline_temas/run_domain.py --domain ecotec_projects --run-id ecotec-proj-<fecha>
python3 scripts/pipeline_temas/run_domain.py --domain ecotec_publications --run-id ecotec-pubs-<fecha>

python3 scripts/analysis/ceplan_units.py --dry-run \
    --run ecotec_projects=ecotec-proj-<fecha> --run ecotec_publications=ecotec-pubs-<fecha>
python3 scripts/analysis/ceplan_units.py \
    --run ecotec_projects=ecotec-proj-<fecha> --run ecotec_publications=ecotec-pubs-<fecha>
```

El cruce con el PND escribe `07_pnd_units.json`, `pnd_por_unidad.csv`,
`pnd_por_politica.csv` y `reporte_pnd_unidades.md` en cada corrida, y la
cobertura conjunta en `salidas/topics/plans/pnd_ec_2025/reporte_cobertura.md`.

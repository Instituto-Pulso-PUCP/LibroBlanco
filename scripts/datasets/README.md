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
3. La institucion en `DATASETS` de `scripts/lib/lb_domains.py` (nombre, pais
   y gentilicio, que van en el prompt del verificador del cruce) y un `Domain`
   por tipo de unidad (con `dataset`, `kind` y `plan`, su plan por defecto).
4. Si trae un plan nacional nuevo, su entrada en `scripts/lib/lb_plans.py`.
5. El valor del enum en RDS: un archivo en `sql/migrations/`.
6. Para el atlas: una entrada en `DATASETS` (y en `PLANS` si el plan es nuevo)
   de `scripts/analysis/atlas_profiles.py`, y `build_atlas.py --run ...` con
   sus corridas. Aparece en el selector de universidad junto a los demás, con
   todos los planes con los que ya se cruzó en el selector «Retos».

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

## Cruzar un dataset con otro plan

Cualquier dataset se cruza con cualquier plan de `lb_plans.PLANS`; el plan del
`Domain` es solo el de por defecto. Una ejecucion = un dataset y un plan:

```bash
python3 scripts/analysis/ceplan_units.py --plan pedn2050 --dry-run     --run ecotec_projects=<run> --run ecotec_publications=<run>
python3 scripts/analysis/ceplan_units.py --plan pedn2050     --run ecotec_projects=<run> --run ecotec_publications=<run>
```

Los archivos llevan el prefijo del plan (`07_ceplan_units.json`,
`07_pnd_units.json`...), asi que una corrida guarda los cruces con varios planes
a la vez. Si el plan es de otro pais que el dataset, el prompt del verificador
agrega que se juzga por el tema y no por el pais (`lb_plans.Plan.judge_system`);
ese cruce no tiene todavia una validacion manual.

Un plan nuevo (p.ej. los retos de Prociencia) que no sale de un adaptador: su
`policies.csv` en `datos/plans/<clave>/` con
`policy_id, label, text, l1_id, l1_label[, l2_label]` (`l2_label` vacio o
ausente en un plan de dos niveles) y una entrada en `lb_plans.PLANS` con
`load=_policies_csv_loader(plan_csv("<clave>"))`.

Ejemplo: el plan `mit_airisk` (taxonomia de dominios del MIT AI Risk
Repository, 24 categorias de riesgo, sin pais). Su `policies.csv` lo escribe
`scripts/plans/mit_airisk.py` desde la hoja del MIT (en el docstring, de donde
bajarla); despues se cruza como cualquier otro plan:

```bash
python3 scripts/plans/mit_airisk.py
python3 scripts/analysis/ceplan_units.py --plan mit_airisk --dry-run \
    --run projects=<run> --run publications_linked=<run>
```

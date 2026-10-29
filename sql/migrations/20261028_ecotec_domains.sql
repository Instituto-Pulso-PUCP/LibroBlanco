-- Dominios del dataset ECOTEC (scripts/datasets/ecotec.py, lb_domains.DOMAINS).
--
-- Aplicar una vez sobre la base existente:
--     psql "$LB_DSN" -f sql/migrations/20261028_ecotec_domains.sql
--
-- Solo agrega valores al enum: no toca filas ni corridas existentes, y es
-- idempotente (IF NOT EXISTS). ADD VALUE no puede ir dentro de una
-- transaccion junto con un uso del valor nuevo; por eso va solo.

ALTER TYPE libroblanco.lb_domain ADD VALUE IF NOT EXISTS 'ecotec_projects';
ALTER TYPE libroblanco.lb_domain ADD VALUE IF NOT EXISTS 'ecotec_publications';

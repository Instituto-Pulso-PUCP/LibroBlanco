-- Esquema RDS (PostgreSQL) del pipeline de temas LibroBlanco / Pulso.
--
-- Aplicar con:  psql "$LB_DSN" -f sql/schema.sql
--
-- Principio de diseno: PROYECTOS Y PUBLICACIONES NO COMPARTEN ESPACIO DE TEMAS.
-- Todas las tablas llevan la columna `domain` ('projects' | 'publications') y
-- las claves e indices unicos la incluyen, de modo que es imposible por
-- construccion que un tema de proyectos aparezca ligado a una publicacion.

CREATE SCHEMA IF NOT EXISTS libroblanco;
SET search_path TO libroblanco, public;

-- pgvector: solo si rds.use_pgvector = true en config/pipeline.toml.
-- En RDS hay que habilitarla una vez por base de datos, con un usuario que
-- tenga rds_superuser.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TYPE lb_domain AS ENUM ('projects', 'publications', 'publications_linked');

-- ---------------------------------------------------------------------------
-- Trazabilidad de corridas
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id            TEXT PRIMARY KEY,
    domain            lb_domain    NOT NULL,
    started_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    ended_at          TIMESTAMPTZ,
    status            TEXT         NOT NULL DEFAULT 'running',
    git_commit        TEXT,
    -- copia de config/pipeline.toml sin secretos: sin esto un run no es replicable
    config_snapshot   JSONB        NOT NULL DEFAULT '{}'::jsonb,
    usage_report      JSONB,
    notes             TEXT
);

CREATE TABLE IF NOT EXISTS pipeline_stage_usage (
    id                BIGSERIAL PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    stage             TEXT NOT NULL,
    status            TEXT NOT NULL,
    wall_seconds      DOUBLE PRECISION NOT NULL DEFAULT 0,
    units_processed   INTEGER NOT NULL DEFAULT 0,
    llm_input_tokens  BIGINT NOT NULL DEFAULT 0,
    llm_output_tokens BIGINT NOT NULL DEFAULT 0,
    embedded_items    BIGINT NOT NULL DEFAULT 0,
    embedded_tokens   BIGINT NOT NULL DEFAULT 0,
    llm_calls         INTEGER NOT NULL DEFAULT 0,
    throttles         INTEGER NOT NULL DEFAULT 0,
    retries           INTEGER NOT NULL DEFAULT 0,
    s3_put_bytes      BIGINT NOT NULL DEFAULT 0,
    s3_get_bytes      BIGINT NOT NULL DEFAULT 0,
    db_rows_written   BIGINT NOT NULL DEFAULT 0,
    max_rss_mb        DOUBLE PRECISION,
    cost_usd          NUMERIC(12, 6) NOT NULL DEFAULT 0,
    detail            JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (run_id, stage)
);

-- ---------------------------------------------------------------------------
-- Unidades de texto (un proyecto o una publicacion)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS units (
    domain          lb_domain NOT NULL,
    unit_id         TEXT      NOT NULL,
    title           TEXT,
    year            INTEGER,
    -- agrupador institucional: executing_unit (proyectos) / journal (publicaciones)
    grouping        TEXT,
    knowledge_area  TEXT,
    text            TEXT      NOT NULL,
    -- que columnas de origen aportaron texto, para el reporte de cobertura
    text_sources    TEXT[]    NOT NULL DEFAULT '{}',
    text_chars      INTEGER   NOT NULL DEFAULT 0,
    source_row      JSONB     NOT NULL DEFAULT '{}'::jsonb,
    ingested_run_id TEXT REFERENCES pipeline_runs(run_id),  -- legacy: vease run_units
    PRIMARY KEY (domain, unit_id)
);

-- `units` es una fila por (domain, unit_id) COMPARTIDA entre corridas: el
-- contenido (texto, titulo...) no cambia entre corridas del mismo dominio, asi
-- que reescribirlo es barato e idempotente. Pero por eso NO puede llevar la
-- pertenencia a una corrida en una sola columna mutable como hacia
-- `ingested_run_id`: la corrida B que reingesta un subconjunto de unidades que
-- la corrida A ya tenia le "robaria" la propiedad, y read_units() de A
-- devolveria menos unidades de las que en realidad tiene. `run_units` fija eso:
-- cada corrida reclama sus unidades de forma aditiva, sin pisar a las demas.
CREATE TABLE IF NOT EXISTS run_units (
    domain  lb_domain NOT NULL,
    run_id  TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    unit_id TEXT NOT NULL,
    PRIMARY KEY (domain, run_id, unit_id),
    FOREIGN KEY (domain, unit_id) REFERENCES units(domain, unit_id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- Temas extraidos (crudos, uno o varios por unidad) y temas normalizados
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS extracted_topics (
    id           BIGSERIAL PRIMARY KEY,
    domain       lb_domain NOT NULL,
    run_id       TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    unit_id      TEXT NOT NULL,
    topic        TEXT NOT NULL,
    description  TEXT,
    evidence     TEXT,               -- cita literal del texto: sin esto no es auditable
    confidence   REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    FOREIGN KEY (domain, unit_id) REFERENCES units(domain, unit_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_extracted_unit ON extracted_topics (domain, run_id, unit_id);

CREATE TABLE IF NOT EXISTS topics (
    domain          lb_domain NOT NULL,
    run_id          TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    topic_id        TEXT NOT NULL,
    label           TEXT NOT NULL,
    description     TEXT,
    num_variants    INTEGER NOT NULL DEFAULT 0,
    centroid        vector(1024),   -- ajustar la dimension al modelo elegido
    PRIMARY KEY (domain, run_id, topic_id)
);

-- Que tema extraido cayo en que tema normalizado (trazabilidad completa).
CREATE TABLE IF NOT EXISTS topic_map (
    domain              lb_domain NOT NULL,
    run_id              TEXT NOT NULL,
    -- posicion del tema extraido dentro del run (no un id autogenerado: el
    -- pipeline los referencia por indice y asi el upsert es idempotente)
    extracted_index     INTEGER NOT NULL,
    unit_id             TEXT NOT NULL,
    topic_id            TEXT NOT NULL,
    similarity          REAL,
    PRIMARY KEY (domain, run_id, extracted_index),
    FOREIGN KEY (domain, run_id, topic_id) REFERENCES topics(domain, run_id, topic_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS unit_embeddings (
    domain      lb_domain NOT NULL,
    run_id      TEXT NOT NULL,
    unit_id     TEXT NOT NULL,
    model_id    TEXT NOT NULL,
    embedding   vector(1024),
    PRIMARY KEY (domain, run_id, unit_id, model_id)
);

-- ---------------------------------------------------------------------------
-- Cuantificacion bidireccional (el resultado que se muestra)
-- Ver docs/cuantificacion_temas.md
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS unit_topic_membership (
    domain        lb_domain NOT NULL,
    run_id        TEXT NOT NULL,
    unit_id       TEXT NOT NULL,
    topic_id      TEXT NOT NULL,
    affinity      DOUBLE PRECISION NOT NULL,
    -- "cuanto de la unidad es de este tema": suma 1 por unidad
    containment   DOUBLE PRECISION NOT NULL CHECK (containment >= 0 AND containment <= 1),
    -- "cuanto de este tema lo aporta la unidad": suma 1 por tema
    contribution  DOUBLE PRECISION NOT NULL CHECK (contribution >= 0 AND contribution <= 1),
    PRIMARY KEY (domain, run_id, unit_id, topic_id),
    FOREIGN KEY (domain, run_id, topic_id) REFERENCES topics(domain, run_id, topic_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_membership_topic
    ON unit_topic_membership (domain, run_id, topic_id, contribution DESC);
CREATE INDEX IF NOT EXISTS idx_membership_unit
    ON unit_topic_membership (domain, run_id, unit_id, containment DESC);

CREATE TABLE IF NOT EXISTS unit_topic_metrics (
    domain                  lb_domain NOT NULL,
    run_id                  TEXT NOT NULL,
    unit_id                 TEXT NOT NULL,
    num_topics              INTEGER NOT NULL DEFAULT 0,
    effective_topics        DOUBLE PRECISION,   -- 1 / sum(containment^2)
    herfindahl              DOUBLE PRECISION,
    entropy_normalized      DOUBLE PRECISION,
    top_topic_id            TEXT,
    top_topic_containment   DOUBLE PRECISION,
    assigned                BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (domain, run_id, unit_id)
);

CREATE TABLE IF NOT EXISTS topic_metrics (
    domain                  lb_domain NOT NULL,
    run_id                  TEXT NOT NULL,
    topic_id                TEXT NOT NULL,
    num_units               INTEGER NOT NULL DEFAULT 0,
    units_equivalent        DOUBLE PRECISION,   -- sum(containment) = tamano real
    share_of_corpus         DOUBLE PRECISION,
    effective_units         DOUBLE PRECISION,   -- 1 / sum(contribution^2)
    herfindahl              DOUBLE PRECISION,
    entropy_normalized      DOUBLE PRECISION,
    top_unit_id             TEXT,
    top_unit_contribution   DOUBLE PRECISION,
    PRIMARY KEY (domain, run_id, topic_id)
);

-- Indices de validez de la particion difusa (coeficiente de particion de
-- Bezdek y entropia), uno por run: dicen si la asignacion es nitida o difusa.
CREATE TABLE IF NOT EXISTS partition_metrics (
    domain                              lb_domain NOT NULL,
    run_id                              TEXT NOT NULL,
    side                                TEXT NOT NULL,  -- 'unit' | 'topic'
    partition_coefficient               DOUBLE PRECISION,
    partition_coefficient_normalized    DOUBLE PRECISION,
    partition_entropy                   DOUBLE PRECISION,
    partition_entropy_normalized        DOUBLE PRECISION,
    mean_effective_topics_per_unit      DOUBLE PRECISION,
    mean_effective_units_per_topic      DOUBLE PRECISION,
    num_units                           INTEGER,
    num_topics                          INTEGER,
    params                              JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (domain, run_id, side)
);

-- ---------------------------------------------------------------------------
-- Reporte auxiliar: filas usadas y tasa de llenado de las columnas embebidas
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS input_coverage (
    domain            lb_domain NOT NULL,
    run_id            TEXT NOT NULL,
    column_name       TEXT NOT NULL,
    used_in_embedding BOOLEAN NOT NULL,
    rows_total        INTEGER NOT NULL,
    rows_filled       INTEGER NOT NULL,
    fill_rate         DOUBLE PRECISION NOT NULL,
    mean_chars        DOUBLE PRECISION,
    p50_chars         INTEGER,
    p95_chars         INTEGER,
    max_chars         INTEGER,
    notes             TEXT,
    PRIMARY KEY (domain, run_id, column_name)
);

-- ---------------------------------------------------------------------------
-- Vistas de lectura para el explorador / LibreChat
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_unit_topics AS
SELECT m.domain, m.run_id, m.unit_id, u.title AS unit_title, u.grouping,
       m.topic_id, t.label AS topic_label,
       m.containment, m.contribution, m.affinity
FROM unit_topic_membership m
JOIN topics t ON (t.domain, t.run_id, t.topic_id) = (m.domain, m.run_id, m.topic_id)
JOIN units  u ON (u.domain, u.unit_id) = (m.domain, m.unit_id);

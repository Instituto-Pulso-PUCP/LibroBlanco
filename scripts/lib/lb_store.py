"""Persistencia del pipeline: RDS (PostgreSQL) o ficheros locales.

Dos implementaciones detras de la misma interfaz:

  - ``PostgresStore``: destino real (RDS). Requiere el paquete ``psycopg``
    (v3) o ``psycopg2``, que hoy NO esta instalado en este servidor.
  - ``LocalStore``: escribe JSON en ``salidas/topics/<domain>/<run_id>/``.
    Existe para poder correr y revisar el flujo completo antes de que RDS este
    levantado, y para desarrollo. No es el destino final.

La interfaz es deliberadamente chica (upsert por lotes + consultas puntuales)
porque el pipeline escribe mucho y lee poco; el consumo analitico se hace con
SQL directo sobre las vistas de sql/schema.sql.

Todas las operaciones llevan ``domain`` ('projects' | 'publications'): los dos
universos se guardan en las mismas tablas pero nunca comparten temas.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

import lb_domains  # noqa: E402  (unica fuente de verdad de los dominios)

DOMAINS = tuple(lb_domains.DOMAINS)


class StoreError(RuntimeError):
    pass


def check_domain(domain: str) -> str:
    if domain not in DOMAINS:
        raise StoreError(f"domain invalido: {domain!r}; esperado uno de {DOMAINS}")
    return domain


class BaseStore:
    def __init__(self, cfg, domain: str, run_id: str, meter_stage=None):
        self.cfg = cfg
        self.domain = check_domain(domain)
        self.run_id = run_id
        self.stage = meter_stage

    def _count(self, written=0, read=0, queries=1):
        if self.stage:
            self.stage.record_db(queries=queries, rows_read=read, rows_written=written)

    # Interfaz que implementan ambas
    def start_run(self, config_snapshot, git_commit=None): raise NotImplementedError
    def finish_run(self, status, usage_report): raise NotImplementedError
    def write_units(self, rows): raise NotImplementedError
    def read_units(self): raise NotImplementedError
    def claim_units(self, unit_ids): raise NotImplementedError
    def write_extracted_topics(self, rows): raise NotImplementedError
    def read_extracted_topics(self): raise NotImplementedError
    def write_topics(self, rows): raise NotImplementedError
    def read_topics(self): raise NotImplementedError
    def write_membership(self, rows): raise NotImplementedError
    def write_metrics(self, unit_metrics, topic_metrics, partition_metrics): raise NotImplementedError
    def write_input_coverage(self, rows): raise NotImplementedError


# ---------------------------------------------------------------------------
# Local (hoy)
# ---------------------------------------------------------------------------

class LocalStore(BaseStore):
    """Ficheros JSON bajo salidas/topics/<domain>/<run_id>/."""

    def __init__(self, cfg, domain, run_id, meter_stage=None):
        super().__init__(cfg, domain, run_id, meter_stage)
        self.root = REPO_ROOT / "salidas" / "topics" / self.domain / run_id
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.root / f"{name}.json"

    def _dump(self, name, data, rows=0):
        self._path(name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._count(written=rows or (len(data) if isinstance(data, list) else 1))
        return self._path(name)

    def _load(self, name, default=None):
        path = self._path(name)
        if not path.exists():
            if default is not None:
                return default
            raise StoreError(
                f"Falta {path.relative_to(REPO_ROOT)} — hay que correr la etapa previa "
                f"de este run ({self.run_id}), o pasar --run-id del run correcto.")
        data = json.loads(path.read_text(encoding="utf-8"))
        self._count(read=len(data) if isinstance(data, list) else 1)
        return data

    def start_run(self, config_snapshot, git_commit=None):
        return self._dump("00_run", {
            "run_id": self.run_id, "domain": self.domain,
            "git_commit": git_commit, "status": "running",
            "config_snapshot": config_snapshot})

    def finish_run(self, status, usage_report):
        run = self._load("00_run", default={})
        run.update({"status": status, "usage_report": usage_report})
        return self._dump("00_run", run)

    def write_units(self, rows):            return self._dump("01_units", rows)
    def read_units(self):                   return self._load("01_units")
    def write_extracted_topics(self, rows): return self._dump("02_extracted_topics", rows)
    def read_extracted_topics(self):        return self._load("02_extracted_topics")
    def write_topics(self, rows):           return self._dump("03_topics", rows)
    def read_topics(self):                  return self._load("03_topics")
    def write_topic_map(self, rows):        return self._dump("03_topic_map", rows)
    def read_topic_map(self):               return self._load("03_topic_map", default=[])
    def write_unit_embeddings(self, rows):  return self._dump("03_unit_embeddings", rows)
    def read_unit_embeddings(self):         return self._load("03_unit_embeddings", default=[])
    def write_membership(self, rows):       return self._dump("04_membership", rows)
    def read_membership(self):              return self._load("04_membership")

    def write_metrics(self, unit_metrics, topic_metrics, partition_metrics):
        self._dump("04_unit_metrics", unit_metrics)
        self._dump("04_topic_metrics", topic_metrics)
        return self._dump("04_partition_metrics", partition_metrics)

    def read_metrics(self):
        return (self._load("04_unit_metrics", default={}),
                self._load("04_topic_metrics", default={}),
                self._load("04_partition_metrics", default={}))

    def write_input_coverage(self, rows):   return self._dump("05_input_coverage", rows)


# ---------------------------------------------------------------------------
# RDS / PostgreSQL (produccion)
# ---------------------------------------------------------------------------

def _as_vector(values):
    """Serializa un vector (lista o array numpy) al literal de pgvector."""
    if values is None:
        return None
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


def _from_vector(raw):
    """Lee un valor pgvector (que psycopg2 devuelve como texto) a lista."""
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return [float(x) for x in str(raw).strip("[]").split(",") if x]


def _connect(cfg):
    """Abre la conexion a RDS. Soporta psycopg v3 o psycopg2, y auth IAM."""
    host = cfg.require("rds.host")
    database = cfg.require("rds.database")
    user = cfg.require("rds.user")
    port = int(cfg.get("rds.port", 5432))
    auth = cfg.get("rds.auth", "iam")

    if auth == "iam":
        # Token efimero (15 min). No hay contrasena que rotar ni guardar.
        # El rol necesita rds-db:connect sobre
        #   arn:aws:rds-db:<region>:<cuenta>:dbuser:<resource-id>/<user>
        from lb_aws import _session
        client = _session(cfg, "rds").client("rds")
        password = client.generate_db_auth_token(
            DBHostname=host, Port=port, DBUsername=user,
            Region=cfg.get("aws.region"))
    elif cfg.get("rds.password_secret_arn"):
        from lb_aws import _session
        client = _session(cfg, "rds").client("secretsmanager")
        secret = json.loads(client.get_secret_value(
            SecretId=cfg.get("rds.password_secret_arn"))["SecretString"])
        password = secret.get("password", secret.get("Password", ""))
    else:
        password = cfg.require("rds.password",
                               "O bien usar rds.auth = 'iam' / rds.password_secret_arn.")

    kwargs = dict(host=host, port=port, dbname=database, user=user,
                  password=password, sslmode=cfg.get("rds.sslmode", "require"))
    try:
        import psycopg
        return psycopg.connect(**kwargs), "psycopg3"
    except ImportError:
        pass
    try:
        import psycopg2
        return psycopg2.connect(**kwargs), "psycopg2"
    except ImportError as exc:
        raise StoreError(
            "Falta el driver de PostgreSQL. Instalar con:\n"
            "  sudo apt install -y python3-psycopg2   (o)\n"
            "  pip install 'psycopg[binary]'\n"
            "Este servidor no tiene pip ni entorno virtual todavia; ver "
            "docs/infraestructura_aws.md."
        ) from exc


class PostgresStore(BaseStore):
    """Destino real. Upserts por lotes contra el esquema de sql/schema.sql."""

    def __init__(self, cfg, domain, run_id, meter_stage=None):
        super().__init__(cfg, domain, run_id, meter_stage)
        self._conn = None
        self._driver = None
        self.schema = cfg.get("rds.schema", "libroblanco")

    @property
    def conn(self):
        if self._conn is None:
            self._conn, self._driver = _connect(self.cfg)
            with self._conn.cursor() as cur:
                cur.execute(f"SET search_path TO {self.schema}, public")
        return self._conn

    def _executemany(self, sql, params_list):
        if not params_list:
            return 0
        with self.conn.cursor() as cur:
            cur.executemany(sql, params_list)
        self.conn.commit()
        self._count(written=len(params_list))
        return len(params_list)

    def _fetchall(self, sql, params=()):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            columns = [d[0] for d in cur.description]
            rows = [dict(zip(columns, r)) for r in cur.fetchall()]
        self._count(read=len(rows))
        return rows

    def start_run(self, config_snapshot, git_commit=None):
        return self._executemany(
            """INSERT INTO pipeline_runs (run_id, domain, git_commit, config_snapshot)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (run_id) DO UPDATE
                 SET config_snapshot = EXCLUDED.config_snapshot,
                     git_commit = EXCLUDED.git_commit""",
            [(self.run_id, self.domain, git_commit, json.dumps(config_snapshot))])

    def finish_run(self, status, usage_report):
        self._executemany(
            """UPDATE pipeline_runs
                  SET status = %s, ended_at = now(), usage_report = %s
                WHERE run_id = %s""",
            [(status, json.dumps(usage_report), self.run_id)])
        return self._executemany(
            """INSERT INTO pipeline_stage_usage
                 (run_id, stage, status, wall_seconds, units_processed,
                  llm_input_tokens, llm_output_tokens, embedded_items, embedded_tokens,
                  llm_calls, throttles, retries, s3_put_bytes, s3_get_bytes,
                  db_rows_written, max_rss_mb, cost_usd, detail)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (run_id, stage) DO UPDATE SET
                 status=EXCLUDED.status, wall_seconds=EXCLUDED.wall_seconds,
                 cost_usd=EXCLUDED.cost_usd, detail=EXCLUDED.detail""",
            [(self.run_id, s["stage"], s["status"], s["wall_seconds"],
              s["units_processed"],
              sum(m["input_tokens"] for m in s["models"].values()),
              sum(m["output_tokens"] for m in s["models"].values()),
              sum(m["embedded_items"] for m in s["models"].values()),
              sum(m["embedded_tokens"] for m in s["models"].values()),
              sum(m["calls"] for m in s["models"].values()),
              sum(m["throttles"] for m in s["models"].values()),
              sum(m["retries"] for m in s["models"].values()),
              s["s3_put_bytes"], s["s3_get_bytes"], s["db_rows_written"],
              s["max_rss_mb"], s["cost"]["total_usd"], json.dumps(s))
             for s in usage_report.get("stages", [])])

    def write_units(self, rows):
        # `units` es contenido compartido entre corridas del mismo dominio (el
        # texto de un proyecto no cambia porque otra corrida lo reingeste), asi
        # que el upsert es seguro. La pertenencia a ESTA corrida se registra
        # aparte, en run_units, de forma ADITIVA -- nunca le quita unidades a
        # una corrida anterior que ya las tuviera (ver comentario en el schema).
        written = self._executemany(
            """INSERT INTO units (domain, unit_id, title, year, grouping,
                                  knowledge_area, text, text_sources, text_chars,
                                  source_row, ingested_run_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (domain, unit_id) DO UPDATE SET
                 title=EXCLUDED.title, text=EXCLUDED.text,
                 text_sources=EXCLUDED.text_sources, text_chars=EXCLUDED.text_chars,
                 source_row=EXCLUDED.source_row, ingested_run_id=EXCLUDED.ingested_run_id""",
            [(self.domain, r["unit_id"], r.get("title"), r.get("year"),
              r.get("grouping"), r.get("knowledge_area"), r.get("text", ""),
              r.get("text_sources", []), len(r.get("text", "")),
              json.dumps(r.get("source_row", {}))) + (self.run_id,) for r in rows])
        self.claim_units([r["unit_id"] for r in rows])
        return written

    def claim_units(self, unit_ids):
        """Registra que ESTA corrida incluye estos unit_id, sin reescribir su
        contenido. Pensado para reusar unidades (y, con seed_from_run.py, sus
        embeddings/temas extraidos) de una corrida anterior sobre un
        subconjunto, sin pagar de nuevo Bedrock por texto que no cambio.
        Falla si algun unit_id no existe ya en `units` para este dominio (FK):
        eso es intencional, evita reclamar unidades que nunca se ingestaron."""
        if not unit_ids:
            return 0
        return self._executemany(
            """INSERT INTO run_units (domain, run_id, unit_id) VALUES (%s,%s,%s)
               ON CONFLICT DO NOTHING""",
            [(self.domain, self.run_id, uid) for uid in unit_ids])

    def read_units(self):
        # Acotado al run via run_units (ver comentario en write_units): sin
        # esto, una corrida de 40 unidades leeria tambien las de todas las
        # anteriores del dominio, porque `units` es una tabla compartida.
        return self._fetchall(
            """SELECT u.* FROM units u
                 JOIN run_units ru ON ru.domain = u.domain AND ru.unit_id = u.unit_id
                WHERE u.domain = %s AND ru.run_id = %s
                ORDER BY u.unit_id""", (self.domain, self.run_id))

    def write_extracted_topics(self, rows):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM extracted_topics WHERE domain=%s AND run_id=%s",
                        (self.domain, self.run_id))
        self.conn.commit()
        return self._executemany(
            """INSERT INTO extracted_topics
                 (domain, run_id, unit_id, topic, description, evidence, confidence)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            [(self.domain, self.run_id, r["unit_id"], r["topic"], r.get("description"),
              r.get("evidence"), float(r.get("confidence", 0))) for r in rows])

    def read_extracted_topics(self):
        return self._fetchall(
            "SELECT * FROM extracted_topics WHERE domain=%s AND run_id=%s",
            (self.domain, self.run_id))

    def write_topics(self, rows):
        # Una reejecucion de la etapa 03 produce otros topic_id: sin borrar los
        # anteriores del mismo run, se acumulan temas fantasma (el upsert por
        # topic_id no los alcanza). El borrado arrastra topic_map y membership
        # por clave foranea.
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM topics WHERE domain=%s AND run_id=%s",
                        (self.domain, self.run_id))
        self.conn.commit()
        return self._executemany(
            """INSERT INTO topics (domain, run_id, topic_id, label, description,
                                   num_variants, centroid)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (domain, run_id, topic_id) DO UPDATE SET
                 label=EXCLUDED.label, description=EXCLUDED.description,
                 num_variants=EXCLUDED.num_variants, centroid=EXCLUDED.centroid""",
            [(self.domain, self.run_id, r["topic_id"], r["label"], r.get("description"),
              r.get("num_variants", 0), _as_vector(r.get("centroid"))) for r in rows])

    def read_topics(self):
        rows = self._fetchall(
            "SELECT * FROM topics WHERE domain=%s AND run_id=%s", (self.domain, self.run_id))
        for row in rows:
            row["centroid"] = _from_vector(row.get("centroid"))
        return rows

    def write_membership(self, rows):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM unit_topic_membership WHERE domain=%s AND run_id=%s",
                        (self.domain, self.run_id))
        self.conn.commit()
        return self._executemany(
            """INSERT INTO unit_topic_membership
                 (domain, run_id, unit_id, topic_id, affinity, containment, contribution)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (domain, run_id, unit_id, topic_id) DO UPDATE SET
                 affinity=EXCLUDED.affinity, containment=EXCLUDED.containment,
                 contribution=EXCLUDED.contribution""",
            [(self.domain, self.run_id, r["unit_id"], r["topic_id"], r["affinity"],
              r["containment"], r["contribution"]) for r in rows])

    def write_metrics(self, unit_metrics, topic_metrics, partition_metrics):
        # Estas tres tablas no cuelgan de `topics` por clave foranea, asi que
        # el borrado en cascada de write_topics no las limpia. Sin esto, una
        # reejecucion deja las metricas de los temas viejos mezcladas con las
        # nuevas (se detecto: 92 filas en topic_metrics para 49 temas).
        with self.conn.cursor() as cur:
            for table in ("unit_topic_metrics", "topic_metrics", "partition_metrics"):
                cur.execute(f"DELETE FROM {table} WHERE domain=%s AND run_id=%s",
                            (self.domain, self.run_id))
        self.conn.commit()
        self._executemany(
            """INSERT INTO unit_topic_metrics
                 (domain, run_id, unit_id, num_topics, effective_topics, herfindahl,
                  entropy_normalized, top_topic_id, top_topic_containment, assigned)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (domain, run_id, unit_id) DO UPDATE SET
                 num_topics=EXCLUDED.num_topics, effective_topics=EXCLUDED.effective_topics,
                 herfindahl=EXCLUDED.herfindahl, top_topic_id=EXCLUDED.top_topic_id,
                 top_topic_containment=EXCLUDED.top_topic_containment,
                 assigned=EXCLUDED.assigned""",
            [(self.domain, self.run_id, uid, m["num_topics"], m["effective_topics"],
              m["herfindahl"], m["entropy_normalized"], m["top_topic_id"],
              m["top_topic_containment"], m["assigned"]) for uid, m in unit_metrics.items()])
        self._executemany(
            """INSERT INTO topic_metrics
                 (domain, run_id, topic_id, num_units, units_equivalent, share_of_corpus,
                  effective_units, herfindahl, entropy_normalized, top_unit_id,
                  top_unit_contribution)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (domain, run_id, topic_id) DO UPDATE SET
                 num_units=EXCLUDED.num_units, units_equivalent=EXCLUDED.units_equivalent,
                 share_of_corpus=EXCLUDED.share_of_corpus,
                 effective_units=EXCLUDED.effective_units""",
            [(self.domain, self.run_id, tid, m["num_units"], m["units_equivalent"],
              m["share_of_corpus"], m["effective_units"], m["herfindahl"],
              m["entropy_normalized"], m["top_unit_id"], m["top_unit_contribution"])
             for tid, m in topic_metrics.items()])
        return self._executemany(
            """INSERT INTO partition_metrics
                 (domain, run_id, side, partition_coefficient,
                  partition_coefficient_normalized, partition_entropy,
                  partition_entropy_normalized, mean_effective_topics_per_unit,
                  mean_effective_units_per_topic, num_units, num_topics, params)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (domain, run_id, side) DO UPDATE SET
                 partition_coefficient=EXCLUDED.partition_coefficient,
                 partition_coefficient_normalized=EXCLUDED.partition_coefficient_normalized""",
            [(self.domain, self.run_id, side,
              partition_metrics[f"{side}_side"]["partition_coefficient"],
              partition_metrics[f"{side}_side"]["partition_coefficient_normalized"],
              partition_metrics[f"{side}_side"]["partition_entropy"],
              partition_metrics[f"{side}_side"]["partition_entropy_normalized"],
              partition_metrics["mean_effective_topics_per_unit"],
              partition_metrics["mean_effective_units_per_topic"],
              partition_metrics["num_units_in_partition"],
              partition_metrics["num_topics_in_partition"],
              json.dumps(partition_metrics.get("params", {})))
             for side in ("unit", "topic")])

    # -- mapa tema extraido -> tema normalizado -----------------------------
    def write_topic_map(self, rows):
        # El upsert va por extracted_index: si una corrida previa del mismo
        # run_id genero mas indices, los sobrantes quedarian apuntando a
        # unidades que ya no forman parte del run. Se borra primero.
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM topic_map WHERE domain=%s AND run_id=%s",
                        (self.domain, self.run_id))
        self.conn.commit()
        return self._executemany(
            """INSERT INTO topic_map
                 (domain, run_id, extracted_index, unit_id, topic_id, similarity)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON CONFLICT (domain, run_id, extracted_index) DO UPDATE SET
                 topic_id=EXCLUDED.topic_id, similarity=EXCLUDED.similarity""",
            [(self.domain, self.run_id, r["extracted_index"], r["unit_id"],
              r["topic_id"], r.get("similarity")) for r in rows])

    def read_topic_map(self):
        return self._fetchall(
            """SELECT extracted_index, unit_id, topic_id, similarity
                 FROM topic_map WHERE domain=%s AND run_id=%s
                ORDER BY extracted_index""", (self.domain, self.run_id))

    # -- embeddings de unidades (pgvector) ----------------------------------
    def write_unit_embeddings(self, rows):
        model_id = self.cfg.get("bedrock.embedding_model_id", "")
        return self._executemany(
            """INSERT INTO unit_embeddings (domain, run_id, unit_id, model_id, embedding)
               VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT (domain, run_id, unit_id, model_id) DO UPDATE SET
                 embedding=EXCLUDED.embedding""",
            [(self.domain, self.run_id, r["unit_id"], model_id,
              _as_vector(r["embedding"])) for r in rows])

    def read_unit_embeddings(self):
        rows = self._fetchall(
            "SELECT unit_id, embedding FROM unit_embeddings WHERE domain=%s AND run_id=%s",
            (self.domain, self.run_id))
        return [{"unit_id": r["unit_id"], "embedding": _from_vector(r["embedding"])}
                for r in rows]

    def read_membership(self):
        return self._fetchall(
            """SELECT unit_id, topic_id, affinity, containment, contribution
                 FROM unit_topic_membership WHERE domain=%s AND run_id=%s""",
            (self.domain, self.run_id))

    def read_metrics(self):
        units = {r.pop("unit_id"): r for r in self._fetchall(
            "SELECT * FROM unit_topic_metrics WHERE domain=%s AND run_id=%s",
            (self.domain, self.run_id))}
        topics = {r.pop("topic_id"): r for r in self._fetchall(
            "SELECT * FROM topic_metrics WHERE domain=%s AND run_id=%s",
            (self.domain, self.run_id))}
        sides = self._fetchall(
            "SELECT * FROM partition_metrics WHERE domain=%s AND run_id=%s",
            (self.domain, self.run_id))
        partition = {f"{r['side']}_side": r for r in sides}
        first = sides[0] if sides else {}
        partition.update({
            "mean_effective_topics_per_unit": first.get("mean_effective_topics_per_unit", 0),
            "mean_effective_units_per_topic": first.get("mean_effective_units_per_topic", 0),
            "num_units_in_partition": first.get("num_units", 0),
            "num_topics_in_partition": first.get("num_topics", 0),
            "params": first.get("params", {}),
        })
        return units, topics, partition

    def write_input_coverage(self, rows):
        return self._executemany(
            """INSERT INTO input_coverage
                 (domain, run_id, column_name, used_in_embedding, rows_total,
                  rows_filled, fill_rate, mean_chars, p50_chars, p95_chars, max_chars, notes)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (domain, run_id, column_name) DO UPDATE SET
                 fill_rate=EXCLUDED.fill_rate, rows_filled=EXCLUDED.rows_filled""",
            [(self.domain, self.run_id, r["column_name"], r["used_in_embedding"],
              r["rows_total"], r["rows_filled"], r["fill_rate"], r.get("mean_chars"),
              r.get("p50_chars"), r.get("p95_chars"), r.get("max_chars"), r.get("notes"))
             for r in rows])


def open_store(cfg, domain, run_id, meter_stage=None) -> BaseStore:
    backend = cfg.get("run.store", "local")
    if backend == "rds":
        return PostgresStore(cfg, domain, run_id, meter_stage)
    if backend == "local":
        return LocalStore(cfg, domain, run_id, meter_stage)
    raise StoreError(f"run.store invalido: {backend!r} (esperado 'rds' o 'local')")

"""Medicion de consumo de recursos por etapa del pipeline.

Requisito explicito del equipo: que cada corrida sea *reportable y replicable*
con otro dataset. Para eso no basta con guardar las salidas; hay que poder
decir cuanto costo producirlas y con que se produjeron. Este modulo registra,
por etapa:

  - tokens de LLM (entrada/salida) y de embeddings, por modelo;
  - llamadas a Bedrock, reintentos y throttles (el throttling es el que
    explica la mayor parte de la diferencia entre tiempo de reloj y tiempo util);
  - bytes y objetos leidos/escritos en S3;
  - filas leidas/escritas en RDS, y consultas;
  - tiempo de reloj y pico de memoria del proceso;
  - costo estimado, aplicando la tabla [pricing] de config/pipeline.toml.

El agregado se escribe como JSON junto al run y, si hay RDS, en la tabla
``pipeline_runs`` / ``pipeline_stage_usage``. Al portar el pipeline a otro
dataset, ese JSON es la linea base contra la que comparar.

Uso:
    meter = UsageMeter(run_id, domain, pricing)
    with meter.stage("02_extract_topics") as stage:
        stage.record_llm(model_id, input_tokens=..., output_tokens=...)
        stage.record_s3_put(nbytes)
    meter.write_report(path)
"""

from __future__ import annotations

import json
import os
import platform
import resource
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class ModelUsage:
    model_id: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    embedded_tokens: int = 0
    embedded_items: int = 0
    retries: int = 0
    throttles: int = 0
    errors: int = 0
    latency_seconds: float = 0.0


@dataclass
class StageUsage:
    stage: str
    started_at: str = ""
    ended_at: str = ""
    wall_seconds: float = 0.0
    status: str = "running"
    error: str = ""
    models: dict[str, ModelUsage] = field(default_factory=dict)
    s3_get_objects: int = 0
    s3_get_bytes: int = 0
    s3_put_objects: int = 0
    s3_put_bytes: int = 0
    db_queries: int = 0
    db_rows_read: int = 0
    db_rows_written: int = 0
    units_processed: int = 0
    max_rss_mb: float = 0.0
    notes: dict = field(default_factory=dict)

    # -- registro ----------------------------------------------------------
    def _model(self, model_id: str) -> ModelUsage:
        if model_id not in self.models:
            self.models[model_id] = ModelUsage(model_id=model_id)
        return self.models[model_id]

    def record_llm(self, model_id, input_tokens=0, output_tokens=0,
                   latency_seconds=0.0, retries=0, throttles=0, errors=0):
        usage = self._model(model_id)
        usage.calls += 1
        usage.input_tokens += int(input_tokens or 0)
        usage.output_tokens += int(output_tokens or 0)
        usage.latency_seconds += float(latency_seconds or 0.0)
        usage.retries += retries
        usage.throttles += throttles
        usage.errors += errors

    def record_embeddings(self, model_id, items=0, tokens=0,
                          latency_seconds=0.0, retries=0, throttles=0, errors=0):
        usage = self._model(model_id)
        usage.calls += 1
        usage.embedded_items += int(items or 0)
        usage.embedded_tokens += int(tokens or 0)
        usage.latency_seconds += float(latency_seconds or 0.0)
        usage.retries += retries
        usage.throttles += throttles
        usage.errors += errors

    def record_s3_get(self, nbytes, objects=1):
        self.s3_get_objects += objects
        self.s3_get_bytes += int(nbytes or 0)

    def record_s3_put(self, nbytes, objects=1):
        self.s3_put_objects += objects
        self.s3_put_bytes += int(nbytes or 0)

    def record_db(self, queries=1, rows_read=0, rows_written=0):
        self.db_queries += queries
        self.db_rows_read += int(rows_read or 0)
        self.db_rows_written += int(rows_written or 0)


class UsageMeter:
    def __init__(self, run_id: str, domain: str, pricing: dict | None = None,
                 config_snapshot: dict | None = None):
        self.run_id = run_id
        self.domain = domain
        self.pricing = dict(pricing or {})
        self.config_snapshot = config_snapshot or {}
        self.stages: list[StageUsage] = []
        self.started_at = datetime.now(timezone.utc)
        self._t0 = time.perf_counter()
        self.environment = {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
        }

    @contextmanager
    def stage(self, name: str, units_processed: int = 0):
        stage = StageUsage(
            stage=name,
            started_at=datetime.now(timezone.utc).isoformat(),
            units_processed=units_processed,
        )
        self.stages.append(stage)
        start = time.perf_counter()
        try:
            yield stage
            stage.status = "ok"
        except Exception as exc:
            stage.status = "error"
            stage.error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            stage.wall_seconds = time.perf_counter() - start
            stage.ended_at = datetime.now(timezone.utc).isoformat()
            # ru_maxrss: KB en Linux, bytes en macOS.
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            divisor = 1024 if platform.system() != "Darwin" else 1024 * 1024
            stage.max_rss_mb = round(rss / divisor, 1)

    # -- costo -------------------------------------------------------------
    def _stage_cost(self, stage: StageUsage) -> dict:
        p = self.pricing
        llm_in = sum(m.input_tokens for m in stage.models.values())
        llm_out = sum(m.output_tokens for m in stage.models.values())
        emb = sum(m.embedded_tokens for m in stage.models.values())
        cost = {
            "llm_input_usd": llm_in / 1e6 * p.get("llm_input_per_mtok", 0.0),
            "llm_output_usd": llm_out / 1e6 * p.get("llm_output_per_mtok", 0.0),
            "embeddings_usd": emb / 1e6 * p.get("embedding_per_mtok", 0.0),
            "s3_requests_usd": (stage.s3_put_objects / 1000 * p.get("s3_put_per_1k", 0.0)
                                + stage.s3_get_objects / 1000 * p.get("s3_get_per_1k", 0.0)),
            "compute_usd": stage.wall_seconds / 3600 * p.get("compute_per_hour", 0.0),
            "rds_usd": stage.wall_seconds / 3600 * p.get("rds_per_hour", 0.0),
        }
        cost["total_usd"] = round(sum(cost.values()), 6)
        return {k: round(v, 6) for k, v in cost.items()}

    def report(self) -> dict:
        stages = []
        totals = {
            "llm_calls": 0, "llm_input_tokens": 0, "llm_output_tokens": 0,
            "embedding_calls": 0, "embedded_items": 0, "embedded_tokens": 0,
            "retries": 0, "throttles": 0, "errors": 0,
            "s3_get_objects": 0, "s3_get_bytes": 0,
            "s3_put_objects": 0, "s3_put_bytes": 0,
            "db_queries": 0, "db_rows_read": 0, "db_rows_written": 0,
            "wall_seconds": 0.0, "cost_usd": 0.0,
        }
        for stage in self.stages:
            cost = self._stage_cost(stage)
            entry = asdict(stage)
            entry["models"] = {k: asdict(v) for k, v in stage.models.items()}
            entry["cost"] = cost
            stages.append(entry)
            for usage in stage.models.values():
                if usage.embedded_items:
                    totals["embedding_calls"] += usage.calls
                else:
                    totals["llm_calls"] += usage.calls
                totals["llm_input_tokens"] += usage.input_tokens
                totals["llm_output_tokens"] += usage.output_tokens
                totals["embedded_items"] += usage.embedded_items
                totals["embedded_tokens"] += usage.embedded_tokens
                totals["retries"] += usage.retries
                totals["throttles"] += usage.throttles
                totals["errors"] += usage.errors
            for key in ("s3_get_objects", "s3_get_bytes", "s3_put_objects",
                        "s3_put_bytes", "db_queries", "db_rows_read", "db_rows_written"):
                totals[key] += getattr(stage, key)
            totals["wall_seconds"] += stage.wall_seconds
            totals["cost_usd"] += cost["total_usd"]
        totals["wall_seconds"] = round(totals["wall_seconds"], 2)
        totals["cost_usd"] = round(totals["cost_usd"], 4)

        units = max((s.units_processed for s in self.stages), default=0)
        per_unit = {}
        if units:
            per_unit = {
                "units": units,
                "cost_usd_per_unit": round(totals["cost_usd"] / units, 6),
                "llm_tokens_per_unit": round(
                    (totals["llm_input_tokens"] + totals["llm_output_tokens"]) / units, 1),
                "seconds_per_unit": round(totals["wall_seconds"] / units, 3),
            }

        pricing_filled = any(
            self.pricing.get(k) for k in
            ("llm_input_per_mtok", "llm_output_per_mtok", "embedding_per_mtok"))
        return {
            "run_id": self.run_id,
            "domain": self.domain,
            "started_at": self.started_at.isoformat(),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "total_wall_seconds": round(time.perf_counter() - self._t0, 2),
            "environment": self.environment,
            "totals": totals,
            # Para extrapolar el costo a otro dataset sin rehacer la corrida.
            "per_unit": per_unit,
            "stages": stages,
            "pricing": self.pricing,
            "pricing_configured": pricing_filled,
            "cost_warning": (None if pricing_filled else
                             "Los precios en [pricing] estan en 0: el costo reportado "
                             "no es real. Rellenar config/pipeline.toml."),
            "config": self.config_snapshot,
        }

    def write_report(self, path):
        from pathlib import Path
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.report(), ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return path

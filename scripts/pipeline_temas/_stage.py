"""Andamiaje comun de las etapas del pipeline de temas.

Cada etapa es un script ejecutable con la misma forma:

    python scripts/pipeline_temas/01_prep_units.py --domain projects --run-id mi-run

Se encarga aqui de: cargar la configuracion, resolver el run_id, abrir el
store (RDS o local), montar el medidor de uso y escribir el reporte de uso al
terminar, incluso si la etapa falla.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))

# Sin esto, Python almacena stdout en bufer cuando va a un fichero y el log
# parece vacio durante horas aunque el proceso este avanzando.
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except AttributeError:
    pass

import lb_config      # noqa: E402
import lb_domains     # noqa: E402
import lb_store       # noqa: E402
import lb_usage       # noqa: E402
import lb_aws         # noqa: E402

RUN_ID_FILE = REPO_ROOT / "salidas" / "topics" / ".last_run_id.json"


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=REPO_ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return ""


def base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--domain", required=True, choices=sorted(lb_domains.DOMAINS),
                        help="Universo a procesar. Proyectos y publicaciones NO "
                             "comparten espacio de temas.")
    parser.add_argument("--run-id", default=None,
                        help="Identificador del run. Por defecto reusa el ultimo "
                             "de este dominio, o crea uno nuevo si no hay.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--store", choices=["rds", "local"], default=None,
                        help="Sobrescribe run.store de la configuracion.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Procesa solo las primeras N unidades. Rapido, pero "
                             "NO representativo: el orden del CSV esta correlacionado "
                             "con la cobertura de datos. Para un piloto usar --sample.")
    parser.add_argument("--sample", type=int, default=0,
                        help="Muestra aleatoria de N unidades (con --seed). Es lo "
                             "que hay que usar para estimar costo y calidad.")
    parser.add_argument("--seed", type=int, default=42,
                        help="Semilla de --sample, para que el piloto sea repetible.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Calcula y muestra, pero no llama a AWS ni escribe.")
    return parser


def _remember_run_id(domain: str, run_id: str):
    import json
    RUN_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if RUN_ID_FILE.exists():
        data = json.loads(RUN_ID_FILE.read_text(encoding="utf-8"))
    data[domain] = run_id
    RUN_ID_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _recall_run_id(domain: str) -> str | None:
    import json
    if not RUN_ID_FILE.exists():
        return None
    return json.loads(RUN_ID_FILE.read_text(encoding="utf-8")).get(domain)


def select_units(units, args):
    """Aplica --limit / --sample. --sample es el que hay que usar en pilotos:
    el CSV de proyectos viene ordenado de forma correlacionada con la cobertura
    de datos, asi que las primeras N filas no representan al universo."""
    import random
    if getattr(args, "sample", 0):
        rng = random.Random(getattr(args, "seed", 42))
        return rng.sample(units, min(args.sample, len(units)))
    if args.limit:
        return units[:args.limit]
    return units


class StageContext:
    """Todo lo que una etapa necesita, ya montado."""

    def __init__(self, args, stage_name: str, new_run: bool = False):
        self.args = args
        self.stage_name = stage_name
        self.cfg = lb_config.load(args.config)
        if args.store:
            self.cfg._data.setdefault("run", {})["store"] = args.store
        self.domain_key = args.domain
        self.domain = lb_domains.get(args.domain)

        run_id = args.run_id or (None if new_run else _recall_run_id(args.domain))
        self.run_id = run_id or self.cfg.resolve_run_id(args.domain)
        _remember_run_id(args.domain, self.run_id)

        self.meter = lb_usage.UsageMeter(
            self.run_id, self.domain_key,
            pricing=self.cfg.section("pricing"),
            config_snapshot=self.cfg.as_dict())
        self.stage = None
        self.store = None
        self.s3 = None

    def __enter__(self):
        self._cm = self.meter.stage(self.stage_name)
        self.stage = self._cm.__enter__()
        self.store = lb_store.open_store(self.cfg, self.domain_key, self.run_id, self.stage)
        self.s3 = lb_aws.S3Store(self.cfg, self.stage)
        print(f"[{self.stage_name}] dominio={self.domain_key} run={self.run_id} "
              f"store={self.cfg.get('run.store')} s3={'sí' if self.s3.enabled else 'no'}")
        self._balance_before = self._gateway_balance()
        if self._balance_before is not None:
            print(f"[{self.stage_name}] saldo de la pasarela al empezar: "
                  f"{self._balance_before:,.0f}")
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self._cm.__exit__(exc_type, exc, tb)
        finally:
            self.write_usage()
        return False

    def _gateway_balance(self):
        """Saldo de la pasarela, o None si no hay pasarela o no lo expone."""
        if not self.cfg.get("gateway.enabled"):
            return None
        try:
            return lb_aws.OpenAICompatClient(self.cfg).balance()
        except Exception:
            return None

    def usage_path(self) -> Path:
        return (REPO_ROOT / "salidas" / "topics" / self.domain_key / self.run_id
                / f"uso_{self.stage_name}.json")

    def write_usage(self):
        # Consumo de creditos de la pasarela: la diferencia de saldo es la
        # medida real, independiente de lo que la pasarela reporte como tokens.
        after = self._gateway_balance()
        before = getattr(self, "_balance_before", None)
        if before is not None and after is not None and self.stage is not None:
            spent = before - after
            self.stage.notes["gateway_balance"] = {
                "before": before, "after": after, "spent": spent}
            tokens = sum(m.input_tokens + m.output_tokens
                         for m in self.stage.models.values())
            rate = (spent / tokens) if tokens else None
            print(f"[{self.stage_name}] creditos consumidos: {spent:,.0f} "
                  f"(saldo {before:,.0f} -> {after:,.0f})"
                  + (f" · {rate:.3f} creditos por token" if rate else ""))
        path = self.meter.write_report(self.usage_path())
        report = self.meter.report()
        # Persistir el consumo tambien en el store, no solo en el JSON local:
        # es lo que hace que la corrida sea reportable desde la base.
        if self.store is not None:
            status = "error" if any(s["status"] == "error" for s in report["stages"]) else "ok"
            try:
                self.store.finish_run(status, report)
            except Exception as exc:   # no tumbar la etapa por el registro de uso
                print(f"[{self.stage_name}] aviso: no se pudo registrar el uso en "
                      f"el store: {type(exc).__name__}: {exc}")
        totals = report["totals"]
        print(f"[{self.stage_name}] {totals['wall_seconds']:.1f}s · "
              f"tokens LLM {totals['llm_input_tokens']:,}/{totals['llm_output_tokens']:,} · "
              f"items embebidos {totals['embedded_items']:,} · "
              f"costo estimado USD {totals['cost_usd']:.4f}"
              + ("" if report["pricing_configured"] else "  (precios sin configurar)"))
        print(f"[{self.stage_name}] uso -> {path.relative_to(REPO_ROOT)}")
        if self.s3 and self.s3.enabled:
            self.s3.put_json(self.s3.run_key(self.run_id, f"uso_{self.stage_name}.json"),
                             report)
        return path


def main_wrapper(fn):
    """Convierte una excepcion de configuracion en un mensaje util, no un traceback."""
    def wrapped():
        try:
            return fn()
        except (lb_config.ConfigError, lb_store.StoreError, lb_aws.AwsNotConfigured) as exc:
            print(f"\nERROR DE CONFIGURACION\n{exc}\n", file=sys.stderr)
            print("Ver config/pipeline.example.toml y docs/infraestructura_aws.md.",
                  file=sys.stderr)
            raise SystemExit(2)
    return wrapped

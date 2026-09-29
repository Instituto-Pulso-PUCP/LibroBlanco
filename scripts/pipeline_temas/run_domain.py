#!/usr/bin/env python3
"""Corre el pipeline de temas completo para UN dominio.

Un dominio = un universo con su propio espacio de temas. Proyectos y
publicaciones se corren por separado, a proposito: sus temas no se comparan ni
se mezclan. Para procesar los dos, se invoca dos veces.

    python scripts/pipeline_temas/run_domain.py --domain projects
    python scripts/pipeline_temas/run_domain.py --domain publications
    python scripts/pipeline_temas/run_domain.py --domain projects --from 04

Cada etapa es tambien un script independiente; esto solo las encadena con el
mismo run_id y corta al primer fallo.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))

import lb_domains  # noqa: E402  (unica fuente de verdad de los dominios)

STAGES = [
    ("01", "01_prep_units.py", "Construir unidades y auditar insumos"),
    ("02", "02_extract_topics.py", "Extraer temas con LLM"),
    ("03", "03_normalize_topics.py", "Normalizar temas (embeddings + agrupamiento)"),
    ("04", "04_quantify.py", "Cuantificación bidireccional"),
    ("05", "05_report.py", "Reportes de temas, cuantificación y consumo"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--domain", required=True,
                        choices=sorted(lb_domains.DOMAINS))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--from", dest="from_stage", default="01",
                        choices=[s[0] for s in STAGES],
                        help="Empieza en esta etapa (reusa el run_id anterior).")
    parser.add_argument("--to", dest="to_stage", default="05",
                        choices=[s[0] for s in STAGES])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--sample", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--store", choices=["rds", "local"], default=None)
    parser.add_argument("--dry-run", action="store_true")
    args, extra = parser.parse_known_args()

    selected = [s for s in STAGES if args.from_stage <= s[0] <= args.to_stage]
    run_id = args.run_id

    for number, script, label in selected:
        print(f"\n{'=' * 72}\n== Etapa {number} — {label}\n{'=' * 72}")
        command = [sys.executable, str(STAGE_DIR / script), "--domain", args.domain]
        if run_id:
            command += ["--run-id", run_id]
        if args.limit:
            command += ["--limit", str(args.limit)]
        if args.sample:
            command += ["--sample", str(args.sample), "--seed", str(args.seed)]
        if args.store:
            command += ["--store", args.store]
        if args.dry_run:
            command += ["--dry-run"]
        command += extra
        result = subprocess.run(command, cwd=REPO_ROOT)
        if result.returncode != 0:
            print(f"\nLa etapa {number} falló (código {result.returncode}). Se detiene.",
                  file=sys.stderr)
            print("Las etapas ya completadas quedan guardadas; al corregir, reanudar con "
                  f"--from {number}.", file=sys.stderr)
            return result.returncode
        if not run_id:
            # La etapa 01 fija el run_id; las siguientes lo reusan.
            import json
            state = REPO_ROOT / "salidas" / "topics" / ".last_run_id.json"
            if state.exists():
                run_id = json.loads(state.read_text(encoding="utf-8")).get(args.domain)

    print(f"\n{'=' * 72}")
    print(f"Listo. Dominio={args.domain} run={run_id}")
    print(f"Salidas en salidas/topics/{args.domain}/{run_id}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

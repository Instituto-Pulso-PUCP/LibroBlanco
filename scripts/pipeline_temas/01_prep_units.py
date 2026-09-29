#!/usr/bin/env python3
"""Etapa 01 — construye las unidades de texto del dominio y audita los insumos.

Lee el CSV de origen del dominio, arma una unidad por proyecto/publicacion con
el esquema fijo de lb_domains, y produce el reporte auxiliar de cobertura
(filas usadas, columnas embebidas y tasa de llenado de cada una).

No usa AWS: corre hoy tal cual. Si run.use_s3 = true, sube ademas una copia del
CSV de origen a S3 para que la corrida sea reproducible desde el bucket.

    python scripts/pipeline_temas/01_prep_units.py --domain projects
    python scripts/pipeline_temas/01_prep_units.py --domain publications --limit 500
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _stage import (REPO_ROOT, StageContext, base_parser, git_commit,  # noqa: E402
                    main_wrapper, select_units)

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
import lb_coverage  # noqa: E402
import lb_domains   # noqa: E402


@main_wrapper
def main():
    parser = base_parser(__doc__)
    parser.add_argument("--source", type=Path, default=None,
                        help="CSV de origen alternativo (por defecto el del dominio).")
    args = parser.parse_args()

    with StageContext(args, "01_prep_units", new_run=not args.run_id) as ctx:
        domain = ctx.domain
        if args.source:
            domain.source_csv = args.source

        rows = lb_domains.read_source(domain)
        rows, dropped_min_req = lb_domains.filter_min_requirements(domain, rows)
        if dropped_min_req:
            print(f"  universo minimo declarado: se descartan {dropped_min_req:,} filas "
                  "que no cumplen los requisitos minimos del dominio (ver lb_domains."
                  "filter_min_requirements).")
        max_chars = int(ctx.cfg.get("topics.max_text_chars", 6000))
        units, dropped = lb_domains.to_units(domain, rows, max_chars)
        units = select_units(units, args)
        ctx.stage.units_processed = len(units)

        report = lb_coverage.build(domain, rows, units, dropped)
        report["run_id"] = ctx.run_id
        report["git_commit"] = git_commit()

        print(f"  filas origen={report['rows_in_source']:,}  "
              f"unidades={report['units_built']:,}  descartadas={report['units_dropped']:,}")
        for warning in report["warnings"]:
            print(f"  AVISO: {warning}")

        if args.dry_run:
            print("  --dry-run: no se escribe nada.")
            return

        ctx.store.start_run(ctx.cfg.as_dict(), git_commit())
        ctx.store.write_units(units)
        ctx.store.write_input_coverage(report["columns"])

        out_dir = REPO_ROOT / "salidas" / "topics" / ctx.domain_key / ctx.run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        md_path = out_dir / "reporte_insumos.md"
        md_path.write_text(lb_coverage.to_markdown(report), encoding="utf-8")
        import json
        (out_dir / "reporte_insumos.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  reporte de insumos -> {md_path.relative_to(REPO_ROOT)}")

        if ctx.s3.enabled:
            ctx.s3.put_json(ctx.s3.run_key(ctx.run_id, "reporte_insumos.json"), report)
            raw_key = ctx.s3.key(ctx.cfg.get("s3.raw_prefix", "raw"),
                                 ctx.domain_key, domain.source_csv.name)
            ctx.s3.put_bytes(raw_key, domain.source_csv.read_bytes(), "text/csv")
            print(f"  origen respaldado en s3://{ctx.s3.bucket}/{raw_key}")


if __name__ == "__main__":
    main()

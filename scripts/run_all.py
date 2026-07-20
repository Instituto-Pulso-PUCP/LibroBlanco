"""Ejecuta el flujo completo del pipeline.

Uso:
    python scripts/run_all.py [opciones]

Opciones utiles:
    --no-openalex        Omite el enriquecimiento OpenAlex (construccion rapida).
    --limit N            Enriquece solo las primeras N filas tipo publicacion.
    --skip-xlsx          No genera los XLSX coloreados por fuente.
    --with-resumenes     Integra los resumenes/palabras clave de la carpeta
                         "Obtencion de resumenes" en las salidas 06 y 07.

El enriquecimiento OpenAlex es reanudable: puede detenerse con Ctrl-C y
continuar en la siguiente ejecucion (usa un cache persistente).
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'


def main(argv=None):
    parser = argparse.ArgumentParser(description='Ejecuta run_pipeline + matching + metricas.')
    parser.add_argument('--no-openalex', action='store_true')
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--no-cache', action='store_true')
    parser.add_argument('--skip-xlsx', action='store_true')
    parser.add_argument('--with-resumenes', action='store_true',
                        help='Integra los resumenes de "Obtencion de resumenes" al final.')
    args = parser.parse_args(argv)

    pipeline_cmd = [sys.executable, str(SCRIPTS / 'run_pipeline.py')]
    if args.no_openalex:
        pipeline_cmd.append('--no-openalex')
    if args.no_cache:
        pipeline_cmd.append('--no-cache')
    if args.skip_xlsx:
        pipeline_cmd.append('--skip-xlsx')
    if args.limit is not None:
        pipeline_cmd += ['--limit', str(args.limit)]

    subprocess.check_call(pipeline_cmd)
    subprocess.check_call([sys.executable, str(SCRIPTS / '02_match_candidates.py')])
    subprocess.check_call([sys.executable, str(SCRIPTS / '03_ground_truth_metrics.py')])

    if args.with_resumenes:
        subprocess.check_call([sys.executable, str(SCRIPTS / 'merge_resumenes.py')])


if __name__ == '__main__':
    main()

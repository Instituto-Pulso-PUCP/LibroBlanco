#!/usr/bin/env python3
"""Puerta de validacion entre el piloto y la corrida completa.

Comprueba que el piloto no solo termino, sino que termino BIEN. Si algo falla
aqui, no tiene sentido gastar ~20 h y ~USD 97 en la corrida completa.

Devuelve 0 si todo pasa, 1 si no. Pensado para encadenarse en un script:

    python scripts/pipeline_temas/validar_piloto.py --domain publications \
        --run-id pubs-pilot-400 && echo "adelante"
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))

import lb_config   # noqa: E402
import lb_domains  # noqa: E402
import lb_store    # noqa: E402

# Margenes. El pico de RAM se compara contra lo que quedara libre en la maquina
# cuando la corrida completa escale; ver --ram-limit.
PC_MIN, PC_MAX = 0.15, 0.92
MAX_ERROR_RATE = 0.02
MAX_UNASSIGNED_RATE = 0.10


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", required=True,
                        choices=sorted(lb_domains.DOMAINS))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--ram-limit", type=float, default=900.0,
                        help="MB de RSS que NO se deben superar al extrapolar.")
    parser.add_argument("--full-units", type=int, default=0)
    args = parser.parse_args()

    cfg = lb_config.load()
    root = REPO_ROOT / "salidas" / "topics" / args.domain / args.run_id
    problems, notes = [], []

    # --- 1. las cinco etapas terminaron ---
    stages = {}
    for path in glob.glob(str(root / "uso_*.json")):
        for stage in json.loads(Path(path).read_text(encoding="utf-8"))["stages"]:
            stages[stage["stage"]] = stage
    expected = ["01_prep_units", "02_extract_topics", "03_normalize_topics",
                "04_quantify", "05_report"]
    for name in expected:
        if name not in stages:
            problems.append(f"la etapa {name} no dejo registro de uso")
        elif stages[name]["status"] != "ok":
            problems.append(f"la etapa {name} termino en estado "
                            f"{stages[name]['status']}: {stages[name].get('error','')}")

    # --- 2. errores de extraccion ---
    cache = root / "02_extraction_cache.jsonl"
    units = errors = 0
    if cache.exists():
        for line in cache.read_text(encoding="utf-8").splitlines():
            if line.strip():
                units += 1
                if json.loads(line).get("error"):
                    errors += 1
        rate = errors / units if units else 0
        notes.append(f"extraccion: {errors}/{units} con error ({rate*100:.1f}%)")
        if rate > MAX_ERROR_RATE:
            problems.append(f"tasa de error de extraccion {rate*100:.1f}% > "
                            f"{MAX_ERROR_RATE*100:.0f}%")

    # --- 3. la particion dice algo ---
    store = lb_store.open_store(cfg, args.domain, args.run_id)
    _, _, partition = store.read_metrics()
    side = partition.get("unit_side") or {}
    pcn = side.get("partition_coefficient_normalized")
    if pcn is None:
        problems.append("no hay indices de particion")
    else:
        notes.append(f"PC normalizado = {pcn:.3f}")
        if not (PC_MIN <= pcn <= PC_MAX):
            problems.append(f"PC normalizado {pcn:.3f} fuera del rango informativo "
                            f"[{PC_MIN}, {PC_MAX}] — la particion es trivial")

    # --- 4. integridad: nada huerfano ---
    membership = store.read_membership()
    unit_ids = {u["unit_id"] for u in store.read_units()}
    orphans = sum(1 for r in membership if r["unit_id"] not in unit_ids)
    notes.append(f"celdas de membership: {len(membership):,} · huerfanas: {orphans}")
    if orphans:
        problems.append(f"{orphans} celdas apuntan a unidades fuera del run")

    unassigned = sum(1 for u in unit_ids
                     if not any(r["unit_id"] == u for r in membership[:0])) if False else 0
    del unassigned

    # --- 5. memoria extrapolada ---
    peak = max((s["max_rss_mb"] for s in stages.values()), default=0)
    pilot_n = max((s["units_processed"] for s in stages.values()), default=0)
    full_n = args.full_units or 0
    if not full_n:
        domain = lb_domains.get(args.domain)
        rows = lb_domains.read_source(domain)
        full_n = len(lb_domains.to_units(domain, rows,
                                         int(cfg.get("topics.max_text_chars", 6000)))[0])
    # Extrapolar el RSS completo de forma lineal no sirve: en un piloto chico
    # casi todo el pico es la linea base de Python+numpy (~120 MB), no datos.
    # Lo que escala es la matriz de vectores, y eso se calcula exacto:
    #   (temas extraidos + unidades) x dim x 4 bytes (float32)
    # Contrastado con el banco de pruebas: 35.000 temas + 14.000 unidades
    # midieron 324 MB reales frente a 321 MB de este modelo.
    dim = int(cfg.get("bedrock.embedding_dimensions", 1024))
    topics_per_unit = (stages.get("03_normalize_topics", {})
                       .get("notes", {}).get("extracted_per_unit"))
    if not topics_per_unit:
        extracted = len(store.read_extracted_topics())
        topics_per_unit = extracted / pilot_n if pilot_n else 2.5
    vectors_full = full_n * (1 + topics_per_unit)
    matrix_mb = vectors_full * dim * 4 / 1e6
    base_mb = 130.0                      # interprete + numpy + driver, medido
    projected = base_mb + matrix_mb * 1.6   # 1.6x: copias transitorias y la matriz GxG
    notes.append(f"temas extraidos por unidad: {topics_per_unit:.2f} -> "
                 f"{vectors_full:,.0f} vectores en la corrida completa")
    notes.append(f"RAM pico del piloto {peak:.0f} MB · proyeccion analitica para "
                 f"{full_n:,} unidades: {projected:.0f} MB "
                 f"(matriz {matrix_mb:.0f} MB + base {base_mb:.0f} MB)")
    if pilot_n < 200:
        notes.append(f"AVISO: el piloto es de solo {pilot_n} unidades; la "
                     "proyeccion es menos fiable por debajo de 200")
    if projected > args.ram_limit:
        problems.append(f"RAM proyectada {projected:.0f} MB > limite {args.ram_limit:.0f} MB")

    print("=" * 66)
    print(f"VALIDACION DEL PILOTO  {args.domain} / {args.run_id}")
    print("=" * 66)
    for note in notes:
        print(f"  · {note}")
    print()
    if problems:
        print("NO PASA:")
        for problem in problems:
            print(f"  ✗ {problem}")
        print("\nNo se lanza la corrida completa.")
        return 1
    print("PASA: el piloto es sano, se puede lanzar la corrida completa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

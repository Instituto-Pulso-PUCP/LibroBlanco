#!/usr/bin/env python3
"""Etapa 04 — cuantificacion bidireccional unidad <-> tema.

Produce, para cada par (proyecto/publicacion, tema), los dos numeros que pidio
el equipo, sobre la misma matriz de afinidad:

  CONTENCION   "cuanto del Proyecto 1 es del Tema 1"   -> suma 1 por proyecto
  CONTRIBUCION "cuanto del Tema 1 lo aporta el Proyecto 1" -> suma 1 por tema

y los indices de validez de la particion difusa (coeficiente de particion de
Bezdek y entropia), que dicen si la asignacion es nitida o esta repartida.
Ver docs/cuantificacion_temas.md para la definicion y como leerlos.

El peso de cada celda sale de quantification.affinity_source:
  extraction | embedding | hybrid (por defecto)

No llama a AWS: trabaja sobre lo que dejaron las etapas 02 y 03. Es barata y se
puede reejecutar con distintos parametros sin volver a pagar el LLM.

    python scripts/pipeline_temas/04_quantify.py --domain projects
    python scripts/pipeline_temas/04_quantify.py --domain projects --affinity extraction
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _stage import REPO_ROOT, StageContext, base_parser, main_wrapper  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
import lb_cluster     # noqa: E402
import lb_membership  # noqa: E402


def build_affinity(ctx, source, extracted, topic_map, topics, unit_embeddings):
    """Arma la matriz de afinidad segun la fuente pedida."""
    cfg = ctx.cfg
    extraction_rows = []
    for entry in topic_map:
        record = extracted[entry["extracted_index"]]
        extraction_rows.append({
            "unit_id": entry["unit_id"],
            "topic_id": entry["topic_id"],
            "confidence": record.get("confidence", 0.0),
        })
    extraction = lb_membership.affinity_from_extraction(extraction_rows)

    similarity = {}
    if source in ("embedding", "hybrid"):
        centroids = {t["topic_id"]: t["centroid"] for t in topics if t.get("centroid")}
        vectors = {e["unit_id"]: e["embedding"] for e in unit_embeddings}
        if not centroids or not vectors:
            raise SystemExit(
                "Faltan centroides o embeddings de unidades: la etapa 03 no llego a "
                "calcularlos (necesita Bedrock). Usar --affinity extraction mientras tanto.")
        top_k = int(cfg.get("quantification.similarity_top_k", 8))
        rows = lb_cluster.similarity_matrix(vectors, centroids, top_k=top_k)
        similarity = lb_membership.affinity_from_similarity(
            rows,
            top_k=top_k,
            floor=float(cfg.get("quantification.similarity_floor", 0.30)),
            power=float(cfg.get("quantification.similarity_power", 3.0)))

    if source == "extraction":
        return extraction
    if source == "embedding":
        return similarity
    return lb_membership.blend_affinities(
        extraction, similarity,
        alpha=float(cfg.get("quantification.hybrid_alpha", 0.7)))


@main_wrapper
def main():
    parser = base_parser(__doc__)
    parser.add_argument("--affinity", choices=["extraction", "embedding", "hybrid"],
                        default=None, help="Sobrescribe quantification.affinity_source.")
    parser.add_argument("--contribution-mode", choices=["share", "mass"], default=None)
    args = parser.parse_args()

    with StageContext(args, "04_quantify") as ctx:
        source = args.affinity or ctx.cfg.get("quantification.affinity_source", "hybrid")
        mode = args.contribution_mode or ctx.cfg.get(
            "quantification.contribution_mode", "share")

        units = ctx.store.read_units()
        extracted = ctx.store.read_extracted_topics()
        topics = ctx.store.read_topics()
        topic_map = ctx.store.read_topic_map()
        unit_embeddings = ctx.store.read_unit_embeddings()

        affinity = build_affinity(ctx, source, extracted, topic_map, topics, unit_embeddings)
        result = lb_membership.quantify(
            affinity,
            unit_ids=[u["unit_id"] for u in units],
            topic_ids=[t["topic_id"] for t in topics],
            contribution_mode=mode)

        stale = result.params.get("cells_outside_universe_dropped", 0)
        if stale:
            print(f"  AVISO: se descartaron {stale:,} celdas que apuntaban a unidades o "
                  "temas fuera de este run (residuo de una corrida previa del mismo "
                  "run_id). Revisar si el run se reejecuto parcialmente.")
        errors = lb_membership.validate(result)
        if errors:
            # Una identidad rota significa que las dos lecturas no son comparables.
            raise SystemExit("La cuantificacion no cumple sus identidades:\n  "
                             + "\n  ".join(errors[:10]))

        partition = result.partition_metrics
        unit_side = partition["unit_side"]
        print(f"  fuente de afinidad={source}  contribucion={mode}")
        print(f"  celdas no nulas={result.params['num_nonzero_cells']:,}  "
              f"densidad={result.params['density']*100:.2f}%  "
              f"unidades sin tema={result.params['num_unassigned']:,}")
        print(f"  coeficiente de particion PC={unit_side['partition_coefficient']:.4f}  "
              f"(normalizado {unit_side['partition_coefficient_normalized']:.4f})")
        print(f"  entropia normalizada={unit_side['partition_entropy_normalized']:.4f}")
        print(f"  temas efectivos por unidad (media)="
              f"{partition['mean_effective_topics_per_unit']:.2f}")
        print(f"  unidades efectivas por tema (media)="
              f"{partition['mean_effective_units_per_topic']:.1f}")
        if unit_side["partition_coefficient_normalized"] > 0.95:
            print("  AVISO: la particion es practicamente nitida (cada unidad cae en un "
                  "solo tema). La contencion no aporta informacion: revisar la fuente "
                  "de afinidad o usar un espacio de temas mas fino.")
        if unit_side["partition_coefficient_normalized"] < 0.05:
            print("  AVISO: la particion es practicamente uniforme (cada unidad se "
                  "reparte por igual entre todos los temas). Subir similarity_floor / "
                  "similarity_power o bajar similarity_top_k.")

        if args.dry_run:
            print("  --dry-run: no se escribe nada.")
            return

        partition["params"] = dict(result.params)
        rows = lb_membership.to_rows(
            result, min_containment=float(ctx.cfg.get("quantification.min_containment", 0.0)))
        ctx.stage.units_processed = len(units)
        ctx.store.write_membership(rows)
        ctx.store.write_metrics(result.unit_metrics, result.topic_metrics, partition)

        # Tabla larga lista para Excel / BI, con los nombres legibles.
        labels = {t["topic_id"]: t["label"] for t in topics}
        titles = {u["unit_id"]: u.get("title", "") for u in units}
        out_dir = REPO_ROOT / "salidas" / "topics" / ctx.domain_key / ctx.run_id
        csv_path = out_dir / "cuantificacion.csv"
        import csv as _csv
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = _csv.writer(handle)
            writer.writerow(["unit_id", "unit_title", "topic_id", "topic_label",
                             "afinidad", "contencion", "contribucion"])
            for row in rows:
                writer.writerow([
                    row["unit_id"], titles.get(row["unit_id"], ""),
                    row["topic_id"], labels.get(row["topic_id"], ""),
                    f"{row['affinity']:.6f}", f"{row['containment']:.6f}",
                    f"{row['contribution']:.6f}"])
        print(f"  {len(rows):,} celdas -> {csv_path.relative_to(REPO_ROOT)}")

        if ctx.s3.enabled:
            ctx.s3.put_json(ctx.s3.run_key(ctx.run_id, "04_partition_metrics.json"), partition)
            ctx.s3.put_bytes(ctx.s3.run_key(ctx.run_id, "cuantificacion.csv"),
                             csv_path.read_bytes(), "text/csv")


if __name__ == "__main__":
    main()

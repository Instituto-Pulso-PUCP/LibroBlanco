#!/usr/bin/env python3
"""Etapa 05 — reportes del run: temas, cuantificacion y consumo de recursos.

Produce tres markdown en salidas/topics/<dominio>/<run_id>/:
  - `reporte_temas.md`        temas normalizados con su tamano real y quienes lo sostienen
  - `reporte_cuantificacion.md` las dos lecturas (contencion / contribucion) con ejemplos
  - `reporte_uso.md`          tokens, llamadas, bytes y costo por etapa

El de uso agrega los `uso_*.json` que dejo cada etapa: es lo que hace la
corrida reportable y permite estimar el costo de repetirla con otro dataset.

    python scripts/pipeline_temas/05_report.py --domain projects
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _stage import REPO_ROOT, StageContext, base_parser, main_wrapper  # noqa: E402


def topics_markdown(ctx, topics, topic_metrics, partition, membership, units):
    labels = {t["topic_id"]: t for t in topics}
    titles = {u["unit_id"]: u.get("title", "") for u in units}
    by_topic = {}
    for row in membership:
        by_topic.setdefault(row["topic_id"], []).append(row)

    order = sorted(topic_metrics.items(), key=lambda kv: -kv[1]["units_equivalent"])
    lines = [
        f"# Temas normalizados — {ctx.domain.label}",
        "",
        f"Run `{ctx.run_id}` · {len(topics)} temas · "
        f"{partition['num_units_in_partition']:,} unidades en la particion",
        "",
        "`Equivalentes` es el tamaño real del tema descontando que cada unidad se "
        "reparte entre varios temas: suma de la contención sobre todas las unidades. "
        "La suma de los equivalentes de todos los temas es el número de unidades. "
        "`Efectivas` (1/HHI sobre la contribución) dice cuántas unidades lo sostienen "
        "de verdad: un tema con 40 unidades pero 3 efectivas está sostenido por tres.",
        "",
        "| Tema | Equivalentes | % corpus | Unidades | Efectivas | Mayor aporte |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for topic_id, metrics in order:
        label = labels.get(topic_id, {}).get("label", topic_id)
        top_unit = metrics["top_unit_id"]
        top_text = (f"{metrics['top_unit_contribution']*100:.1f}% · "
                    f"{titles.get(top_unit, top_unit or '')[:48]}" if top_unit else "—")
        lines.append(
            f"| {label} | {metrics['units_equivalent']:.1f} | "
            f"{metrics['share_of_corpus']*100:.1f}% | {metrics['num_units']} | "
            f"{metrics['effective_units']:.1f} | {top_text} |")

    lines += ["", "## Detalle por tema", ""]
    for topic_id, metrics in order:
        topic = labels.get(topic_id, {})
        lines += [f"### {topic.get('label', topic_id)}", ""]
        if topic.get("description"):
            lines += [topic["description"], ""]
        lines += [
            f"- **Equivalentes:** {metrics['units_equivalent']:.2f} "
            f"({metrics['share_of_corpus']*100:.1f}% del corpus)",
            f"- **Unidades que lo tocan:** {metrics['num_units']} · "
            f"**efectivas:** {metrics['effective_units']:.1f}",
            f"- **Temas extraídos que lo componen:** {topic.get('num_variants', 0)}",
            "",
            "Unidades que más lo aportan:",
            "",
        ]
        top_rows = sorted(by_topic.get(topic_id, []),
                          key=lambda r: -r["contribution"])[:8]
        for row in top_rows:
            lines.append(
                f"- **{row['contribution']*100:.1f}%** del tema · el tema es "
                f"**{row['containment']*100:.0f}%** de esta unidad · "
                f"`{row['unit_id']}` {titles.get(row['unit_id'], '')[:80]}")
        lines.append("")
    return "\n".join(lines)


def quantification_markdown(ctx, partition, unit_metrics, topic_metrics, membership,
                            units, topics):
    unit_side, topic_side = partition["unit_side"], partition["topic_side"]
    labels = {t["topic_id"]: t["label"] for t in topics}
    titles = {u["unit_id"]: u.get("title", "") for u in units}
    by_unit = {}
    for row in membership:
        by_unit.setdefault(row["unit_id"], []).append(row)

    def fmt(value, digits=4):
        return "—" if value is None else f"{value:.{digits}f}"

    lines = [
        f"# Cuantificación bidireccional — {ctx.domain.label}",
        "",
        f"Run `{ctx.run_id}`. Método y cómo leer estos números: "
        "[docs/cuantificacion_temas.md](../../../../docs/cuantificacion_temas.md).",
        "",
        "## Índices de validez de la partición",
        "",
        "| Índice | Lado unidad | Lado tema |",
        "|---|---:|---:|",
        f"| Coeficiente de partición (PC) | {fmt(unit_side['partition_coefficient'])} | "
        f"{fmt(topic_side['partition_coefficient'])} |",
        f"| PC normalizado (0–1) | {fmt(unit_side['partition_coefficient_normalized'])} | "
        f"{fmt(topic_side['partition_coefficient_normalized'])} |",
        f"| Entropía de partición | {fmt(unit_side['partition_entropy'])} | "
        f"{fmt(topic_side['partition_entropy'])} |",
        f"| Entropía normalizada (0–1) | {fmt(unit_side['partition_entropy_normalized'])} | "
        f"{fmt(topic_side['partition_entropy_normalized'])} |",
        "",
        f"- **Temas efectivos por unidad (media):** "
        f"{partition['mean_effective_topics_per_unit']:.2f} de "
        f"{partition['num_topics_in_partition']} posibles",
        f"- **Unidades efectivas por tema (media):** "
        f"{partition['mean_effective_units_per_topic']:.1f}",
        "",
        "PC cerca de 1 = cada unidad cae en un solo tema (partición nítida, la "
        "contención no aporta información nueva). PC cerca de 0 (normalizado) = cada "
        "unidad se reparte por igual entre todos los temas (partición sin señal). El "
        "rango informativo está en medio.",
        "",
        "## Unidades más repartidas entre temas",
        "",
        "Las que más temas efectivos tienen: son las que hacen que la pregunta "
        "\"cuánto del proyecto es de este tema\" tenga sentido.",
        "",
    ]
    spread = sorted((m for m in unit_metrics.items() if m[1]["assigned"]),
                    key=lambda kv: -kv[1]["effective_topics"])[:10]
    for unit_id, metrics in spread:
        lines.append(f"- `{unit_id}` ({metrics['effective_topics']:.2f} temas efectivos) "
                     f"— {titles.get(unit_id, '')[:70]}")
        for row in sorted(by_unit.get(unit_id, []), key=lambda r: -r["containment"])[:4]:
            lines.append(f"    - **{row['containment']*100:.0f}%** {labels.get(row['topic_id'], '')} "
                         f"(aporta el {row['contribution']*100:.1f}% de ese tema)")
    lines.append("")

    unassigned = [u for u, m in unit_metrics.items() if not m["assigned"]]
    if unassigned:
        lines += [
            f"## Unidades sin tema ({len(unassigned)})", "",
            "No entraron en la partición: ningún tema alcanzó afinidad positiva. No "
            "cuentan en el denominador de ningún índice.", "",
        ]
        for unit_id in unassigned[:20]:
            lines.append(f"- `{unit_id}` {titles.get(unit_id, '')[:80]}")
        if len(unassigned) > 20:
            lines.append(f"- … y {len(unassigned) - 20} más")
        lines.append("")
    return "\n".join(lines)


def usage_markdown(ctx, reports):
    lines = [
        f"# Consumo de recursos — {ctx.domain.label}",
        "",
        f"Run `{ctx.run_id}`",
        "",
        "| Etapa | Estado | Segundos | Unidades | Tokens in | Tokens out | "
        "Items embebidos | Throttles | RAM pico (MB) | Costo USD |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    totals = {"wall": 0.0, "tin": 0, "tout": 0, "emb": 0, "thr": 0, "cost": 0.0}
    warning = None
    for report in reports:
        warning = warning or report.get("cost_warning")
        for stage in report["stages"]:
            tin = sum(m["input_tokens"] for m in stage["models"].values())
            tout = sum(m["output_tokens"] for m in stage["models"].values())
            emb = sum(m["embedded_items"] for m in stage["models"].values())
            thr = sum(m["throttles"] for m in stage["models"].values())
            cost = stage["cost"]["total_usd"]
            lines.append(
                f"| `{stage['stage']}` | {stage['status']} | {stage['wall_seconds']:.1f} | "
                f"{stage['units_processed']:,} | {tin:,} | {tout:,} | {emb:,} | {thr} | "
                f"{stage['max_rss_mb']:.0f} | {cost:.4f} |")
            totals["wall"] += stage["wall_seconds"]; totals["tin"] += tin
            totals["tout"] += tout; totals["emb"] += emb; totals["thr"] += thr
            totals["cost"] += cost
    lines.append(
        f"| **Total** | | **{totals['wall']:.1f}** | | **{totals['tin']:,}** | "
        f"**{totals['tout']:,}** | **{totals['emb']:,}** | **{totals['thr']}** | | "
        f"**{totals['cost']:.4f}** |")
    lines.append("")
    if warning:
        lines += [f"> **{warning}**", ""]

    units = max((s["units_processed"] for r in reports for s in r["stages"]), default=0)
    if units:
        lines += [
            "## Por unidad — para estimar otro dataset", "",
            f"- **Unidades procesadas:** {units:,}",
            f"- **Tokens de LLM por unidad:** "
            f"{(totals['tin'] + totals['tout']) / units:,.0f}",
            f"- **Segundos por unidad:** {totals['wall'] / units:.3f}",
            f"- **Costo por unidad:** USD {totals['cost'] / units:.6f}",
            "",
            f"Un dataset de 10.000 unidades costaría del orden de "
            f"USD {totals['cost'] / units * 10000:,.2f} y "
            f"{totals['wall'] / units * 10000 / 3600:,.1f} horas con esta misma "
            "concurrencia.",
            "",
        ]
    env = reports[0]["environment"] if reports else {}
    lines += [
        "## Entorno", "",
        f"- {env.get('platform', '')}",
        f"- Python {env.get('python', '')} · {env.get('cpu_count', '?')} vCPU",
        "",
    ]
    return "\n".join(lines)


@main_wrapper
def main():
    parser = base_parser(__doc__)
    args = parser.parse_args()

    with StageContext(args, "05_report") as ctx:
        out_dir = REPO_ROOT / "salidas" / "topics" / ctx.domain_key / ctx.run_id
        units = ctx.store.read_units()
        topics = ctx.store.read_topics()
        membership = ctx.store.read_membership()
        unit_metrics, topic_metrics, partition = ctx.store.read_metrics()

        written = []
        path = out_dir / "reporte_temas.md"
        path.write_text(topics_markdown(ctx, topics, topic_metrics, partition,
                                        membership, units), encoding="utf-8")
        written.append(path)

        path = out_dir / "reporte_cuantificacion.md"
        path.write_text(quantification_markdown(ctx, partition, unit_metrics,
                                                topic_metrics, membership, units, topics),
                        encoding="utf-8")
        written.append(path)

        reports = []
        for usage_file in sorted(out_dir.glob("uso_*.json")):
            if usage_file.name == "uso_05_report.json":
                continue
            reports.append(json.loads(usage_file.read_text(encoding="utf-8")))
        if reports:
            path = out_dir / "reporte_uso.md"
            path.write_text(usage_markdown(ctx, reports), encoding="utf-8")
            written.append(path)

        for path in written:
            print(f"  -> {path.relative_to(REPO_ROOT)}")

        if ctx.s3.enabled:
            for path in written:
                ctx.s3.put_bytes(ctx.s3.run_key(ctx.run_id, path.name),
                                 path.read_bytes(), "text/markdown")


if __name__ == "__main__":
    main()

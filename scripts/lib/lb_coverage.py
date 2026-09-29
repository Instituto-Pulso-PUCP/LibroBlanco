"""Reporte auxiliar de insumos: filas usadas y tasa de llenado por columna.

Responde, para cada corrida y cada dominio:
  - cuantas filas trae el origen, cuantas se usan y por que se cae el resto;
  - que columnas se concatenan para el embedding / el LLM y cuales se excluyen
    a proposito (con el motivo);
  - que porcentaje de filas tiene cada columna llena, y cuanto texto aporta.

Sirve para dos cosas concretas:
  1. Detectar a tiempo que un export de origen llego vacio o incompleto. La
     diferencia entre "el modelo agrupa mal" y "la columna de la que dependia
     viene al 1%" no se ve en las metricas de clustering, se ve aqui.
  2. Poder decir en el informe con que material se produjo cada resultado, que
     es lo que hace la corrida replicable con otro dataset.
"""

from __future__ import annotations

import lb_domains

# Por debajo de esto, una columna declarada como insumo de embedding esta
# practicamente vacia y conviene avisar en vez de dejar que pase inadvertida.
LOW_FILL_WARNING = 0.10


def _percentile(sorted_values, fraction):
    if not sorted_values:
        return 0
    index = min(len(sorted_values) - 1, int(round(fraction * (len(sorted_values) - 1))))
    return sorted_values[index]


def column_stats(rows, column, used_in_embedding, notes=""):
    lengths = []
    for row in rows:
        value = lb_domains.clean_value(row.get(column))
        if value:
            lengths.append(len(value))
    total = len(rows)
    filled = len(lengths)
    lengths.sort()
    return {
        "column_name": column,
        "used_in_embedding": used_in_embedding,
        "rows_total": total,
        "rows_filled": filled,
        "fill_rate": (filled / total) if total else 0.0,
        "mean_chars": round(sum(lengths) / filled, 1) if filled else 0.0,
        "p50_chars": _percentile(lengths, 0.50),
        "p95_chars": _percentile(lengths, 0.95),
        "max_chars": lengths[-1] if lengths else 0,
        "notes": notes,
    }


def build(domain, rows, units, dropped):
    """Construye el reporte completo de cobertura de insumos."""
    columns = []
    for column in domain.text_columns:
        columns.append(column_stats(rows, column, True))
    for column in domain.metadata_columns:
        if column in domain.text_columns:
            continue
        columns.append(column_stats(rows, column, False, "metadato (no se embebe)"))
    for column, reason in domain.excluded_columns.items():
        if any(c["column_name"] == column for c in columns):
            continue
        columns.append(column_stats(rows, column, False, f"excluida: {reason}"))

    # Columnas de texto auxiliar (p.ej. los resultados declarados de un
    # proyecto): su cobertura se mide sobre UNIDADES, no sobre filas del CSV
    # de origen, porque una unidad puede tener varias filas auxiliares.
    if domain.aux_csv:
        for column in domain.aux_text_columns:
            key = f"aux:{column}"
            using = sum(1 for u in units if key in u["text_sources"])
            columns.append({
                "column_name": key,
                "used_in_embedding": True,
                "rows_total": len(units),
                "rows_filled": using,
                "fill_rate": (using / len(units)) if units else 0.0,
                "mean_chars": 0.0, "p50_chars": 0, "p95_chars": 0, "max_chars": 0,
                "notes": f"{domain.aux_label} ({domain.aux_csv.name}, "
                         f"max {domain.aux_max_rows} por unidad)",
            })

    # Cuantas unidades acabaron usando cada columna (no es lo mismo que la tasa
    # de llenado del origen: una fila puede caerse por otro motivo).
    used_counts = {}
    for unit in units:
        for source in unit["text_sources"]:
            used_counts[source] = used_counts.get(source, 0) + 1
    for entry in columns:
        entry["units_using_column"] = used_counts.get(entry["column_name"], 0)

    text_lengths = sorted(len(u["text"]) for u in units)
    drop_reasons = {}
    for item in dropped:
        drop_reasons[item["reason"]] = drop_reasons.get(item["reason"], 0) + 1

    embedding_columns = [c for c in columns if c["used_in_embedding"]]
    warnings = []
    for entry in embedding_columns:
        if entry["column_name"].startswith("aux:"):
            continue
        if entry["fill_rate"] < LOW_FILL_WARNING:
            warnings.append(
                f"'{entry['column_name']}' se usa para el embedding pero solo esta "
                f"llena en {entry['rows_filled']}/{entry['rows_total']} filas "
                f"({entry['fill_rate']*100:.1f}%). Revisar el export de origen antes "
                "de interpretar los temas.")
    with_aux = sum(1 for u in units
                   if any(x.startswith("aux:") for x in u["text_sources"]))
    if domain.aux_csv and units:
        warnings.append(
            f"{with_aux}/{len(units)} unidades ({with_aux/len(units)*100:.0f}%) apoyan su "
            f"texto en {domain.aux_label}. Para esas, el tema describe lo que el "
            "proyecto PUBLICO, no lo que se propuso: decirlo al reportar.")
    single_source = sum(1 for u in units if len(u["text_sources"]) == 1)
    if units and single_source / len(units) > 0.5:
        warnings.append(
            f"{single_source}/{len(units)} unidades ({single_source/len(units)*100:.0f}%) "
            "aportan texto de una sola columna. Los temas extraidos van a reflejar "
            "sobre todo esa columna.")

    return {
        "domain": domain.key,
        "domain_label": domain.label,
        "source_file": str(domain.source_csv),
        "rows_in_source": len(rows),
        "units_built": len(units),
        "units_dropped": len(dropped),
        "drop_reasons": drop_reasons,
        "required_any": domain.required_any,
        "embedding_columns": [c["column_name"] for c in embedding_columns],
        "text_chars": {
            "total": sum(text_lengths),
            "mean": round(sum(text_lengths) / len(text_lengths), 1) if text_lengths else 0,
            "p50": _percentile(text_lengths, 0.50),
            "p95": _percentile(text_lengths, 0.95),
            "max": text_lengths[-1] if text_lengths else 0,
        },
        "units_with_aux_text": with_aux if domain.aux_csv else 0,
        "sources_per_unit": {
            "mean": round(sum(len(u["text_sources"]) for u in units) / len(units), 2)
                    if units else 0,
            "units_with_one_source": single_source,
        },
        "columns": columns,
        "warnings": warnings,
    }


def to_markdown(report) -> str:
    lines = [
        f"# Cobertura de insumos — {report['domain_label']}",
        "",
        f"- **Origen:** `{report['source_file']}`",
        f"- **Filas en el origen:** {report['rows_in_source']:,}",
        f"- **Unidades construidas:** {report['units_built']:,}",
        f"- **Unidades descartadas:** {report['units_dropped']:,}",
    ]
    for reason, count in sorted(report["drop_reasons"].items(), key=lambda x: -x[1]):
        lines.append(f"  - {count:,} — {reason}")
    chars = report["text_chars"]
    lines += [
        f"- **Texto por unidad (caracteres):** media {chars['mean']:,.0f} · "
        f"mediana {chars['p50']:,} · p95 {chars['p95']:,} · max {chars['max']:,}",
        f"- **Columnas que aportan texto por unidad:** media "
        f"{report['sources_per_unit']['mean']}",
        "",
    ]
    if report["warnings"]:
        lines += ["## Avisos", ""]
        lines += [f"- {w}" for w in report["warnings"]] + [""]

    lines += [
        "## Columnas",
        "",
        "`Embebida` = su texto entra en lo que se manda al LLM y al modelo de "
        "embeddings. `Llenado` es sobre las filas del origen.",
        "",
        "| Columna | Embebida | Llenado | Filas llenas | Unidades que la usan | "
        "Chars (media) | p95 | Nota |",
        "|---|---|---|---|---|---|---|---|",
    ]
    order = sorted(report["columns"],
                   key=lambda c: (not c["used_in_embedding"], -c["fill_rate"]))
    for entry in order:
        mark = "sí" if entry["used_in_embedding"] else "no"
        lines.append(
            f"| `{entry['column_name']}` | {mark} | {entry['fill_rate']*100:.1f}% | "
            f"{entry['rows_filled']:,}/{entry['rows_total']:,} | "
            f"{entry['units_using_column']:,} | {entry['mean_chars']:,.0f} | "
            f"{entry['p95_chars']:,} | {entry['notes']} |")
    return "\n".join(lines) + "\n"

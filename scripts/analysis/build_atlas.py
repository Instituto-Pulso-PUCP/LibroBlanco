#!/usr/bin/env python3
"""Genera el Atlas Temático: explorador HTML de la cuantificacion bidireccional.

Lee los resultados de RDS (o del store local) y los incrusta en
`templates/atlas_template.html`. Para cambiar el diseño o los textos, editar
esa plantilla y volver a correr esto: el HTML publicado es una salida, no una
fuente que haya que editar a mano.

    python scripts/analysis/build_atlas.py \
        --run projects=full-proj-975 \
        --run publications_linked=publications_linked-20260924-002153

Salida: salidas/topics/atlas.html
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import lb_cluster    # noqa: E402
import lb_config     # noqa: E402
import lb_coverage   # noqa: E402
import lb_domains    # noqa: E402
import lb_membership # noqa: E402
import lb_store      # noqa: E402

TEMPLATE = Path(__file__).resolve().parent / "templates" / "atlas_template.html"
DEFAULT_OUT = ROOT / "salidas" / "topics" / "atlas.html"

# Etiqueta y sustantivo por dominio, para que los textos de la pagina concuerden.
NOUNS = {
    "projects": ("Proyectos de investigación PUCP cerrados (2010+)", "proyecto"),
    "publications": ("Publicaciones PUCP (catálogo completo)", "publicación"),
    "publications_linked": ("Publicaciones derivadas de proyectos del universo", "publicación"),
}


def decompose(cfg, store, unit_id, topics):
    """Rehace, solo para la unidad del ejemplo, las dos mitades de su fila.

    La pagina afirma que la fila de afinidades no la escribe el LLM sino una
    mezcla 70/30. Esto lo demuestra con los numeros de la propia corrida en vez
    de pedir que se crea: se recalcula la mitad de extraccion y la mitad de
    similitud por separado, con los mismos parametros de la etapa 04.
    """
    alpha = float(cfg.get("quantification.hybrid_alpha", 0.7))
    top_k = int(cfg.get("quantification.similarity_top_k", 8))
    floor = float(cfg.get("quantification.similarity_floor", 0.30))
    power = float(cfg.get("quantification.similarity_power", 3.0))

    extracted = store.read_extracted_topics()
    llm = []
    ext_rows = []
    for entry in store.read_topic_map():
        if str(entry["unit_id"]) != str(unit_id):
            continue
        record = extracted[entry["extracted_index"]]
        ext_rows.append({"unit_id": unit_id, "topic_id": entry["topic_id"],
                         "confidence": record.get("confidence", 0.0)})
        llm.append({"c": round(float(record.get("confidence") or 0), 2),
                    "t": record["topic"],
                    "tid": entry["topic_id"]})
    llm.sort(key=lambda x: -x["c"])
    extraction = lb_membership.row_normalize(
        lb_membership.affinity_from_extraction(ext_rows))

    centroids = {t: topics[t]["centroid"] for t in topics if topics[t].get("centroid")}
    vector = None
    for row in store.read_unit_embeddings():
        if str(row["unit_id"]) == str(unit_id):
            vector = row["embedding"]
            break
    if vector is None or not centroids:
        return {}
    cosines = lb_cluster.similarity_matrix({str(unit_id): vector}, centroids, top_k=top_k)
    raw = {r["topic_id"]: r["score"] for r in cosines}
    similarity = lb_membership.row_normalize(
        lb_membership.affinity_from_similarity(cosines, top_k=top_k, floor=floor, power=power))
    blend = lb_membership.blend_affinities(extraction, similarity, alpha=alpha)

    comp = []
    for (_u, tid), w in sorted(blend.items(), key=lambda kv: -kv[1]):
        comp.append({"t": topics.get(tid, {}).get("label", tid),
                     "cos": round(raw.get(tid, 0.0), 4),
                     "e": round(extraction.get((str(unit_id), tid), 0.0), 4),
                     "s": round(similarity.get((str(unit_id), tid), 0.0), 4),
                     "w": round(w, 4)})
    return {"alpha": alpha, "k": top_k, "floor": floor, "power": power,
            "llm": llm, "comp": comp,
            "nllm": len({r["topic_id"] for r in ext_rows})}


def examples(cfg, store, rows, topics, units, raw_topics):
    """Celdas reales de esta corrida para el ejemplo de la pestana de metodologia.

    Se eligen solas. Escritas a mano, cada renormalizacion las dejaria
    desfasadas sin que nadie lo note: la pagina seguiria mostrando numeros de
    una corrida que ya no existe.
    """
    if not rows:
        return {}
    by_unit, by_topic = {}, {}
    for r in rows:
        by_unit.setdefault(r["unit_id"], []).append(r)
        by_topic.setdefault(r["topic_id"], []).append(r)

    def size(topic_id):
        return topics.get(topic_id, {}).get("eq", 0) or 0

    def describe(r):
        siblings = sorted(by_unit[r["unit_id"]], key=lambda x: -x["affinity"])
        return {
            "uid": r["unit_id"],
            "u": units.get(r["unit_id"], {}).get("t") or r["unit_id"],
            "tid": r["topic_id"],
            "t": topics.get(r["topic_id"], {}).get("l", r["topic_id"]),
            "aff": round(r["affinity"], 4),
            "row": [round(x["affinity"], 4) for x in siblings[:8]],
            "nrow": len(siblings),
            "rowsum": round(sum(x["affinity"] for x in siblings), 4),
            "c": round(r["containment"], 4),
            "k": round(r["contribution"], 5),
            "eq": round(size(r["topic_id"]), 2),
            "nt": len(by_topic[r["topic_id"]]),
        }

    # Ejemplo principal: la celda mas concentrada de la corrida, pero de una
    # unidad con varios temas y de un tema que varias unidades tocan; si no,
    # el ejemplo saldria degenerado (una fila de un solo numero).
    def ok(r):
        return len(by_unit[r["unit_id"]]) >= 4 and len(by_topic[r["topic_id"]]) >= 8
    pool = [r for r in rows if ok(r)] or rows
    main = max(pool, key=lambda r: (r["containment"], -len(r["unit_id"])))

    # Par de contraste: misma pregunta, dos tamanos de tema.
    sizes = sorted((size(t) for t in by_topic), reverse=True)
    big_cut = sizes[max(len(sizes) // 20, 0)] if sizes else 0
    big_pool = [r for r in rows if size(r["topic_id"]) >= big_cut] or rows
    big = max(big_pool, key=lambda r: r["containment"])
    # El contraste solo dice algo si el tema chico lo tocan varias unidades: un
    # tema de una sola unidad da 100 % de aporte por definicion, no por medida.
    small_pool = [r for r in rows
                  if r["containment"] < 0.3 and len(by_topic[r["topic_id"]]) >= 5] or rows
    small = max(small_pool, key=lambda r: r["contribution"])
    main_cell = describe(main)
    main_cell["parts"] = decompose(cfg, store, main["unit_id"], raw_topics)
    return {"main": main_cell, "big": describe(big), "small": describe(small)}


def attach_ceplan(domain: str, run_id: str, topics: dict) -> None:
    """Cuelga, en cada tema, su mejor calce con el PEDN 2050 / Objetivos
    Nacionales (scripts/analysis/ceplan_alignment.py), si ya se corrió para
    este run. Sin ese archivo, la pestaña de Objetivos Nacionales sale vacia
    en vez de romperse -- el cruce es un cruce aparte, no una etapa obligatoria
    del pipeline."""
    path = ROOT / "salidas" / "topics" / domain / run_id / "06_ceplan_alignment.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    for row in data.get("rows", []):
        tid = row["topic_id"]
        if tid not in topics:
            continue
        entry = {"i": row["best_on_via_subtema"], "l": row["best_on_label"],
                 "t": row["best_tema"], "s": row["best_subtema"],
                 "sc": row["score_subtema"], "di": row["on_direct_id"],
                 "dl": row["on_direct_label"], "dsc": row["score_on_direct"],
                 "ok": row["agrees_direct_vs_subtema"]}
        if row.get("secondary_best_on"):
            entry.update({"si": row["secondary_best_on"], "ss": row["secondary_best_subtema"],
                         "ssc": row["secondary_score"]})
        topics[tid]["on"] = entry


def collect(cfg, domain: str, run_id: str) -> dict:
    store = lb_store.open_store(cfg, domain, run_id)
    raw_topics = {t["topic_id"]: t for t in store.read_topics()}
    topics = {t["topic_id"]: {"l": t["label"], "d": t.get("description") or "",
                              "v": t.get("num_variants") or 0}
              for t in raw_topics.values()}
    unit_metrics, topic_metrics, partition = store.read_metrics()
    for tid, m in topic_metrics.items():
        if tid in topics:
            topics[tid].update({
                "eq": round(m["units_equivalent"] or 0, 2),
                "n": m["num_units"],
                "sh": round(m["share_of_corpus"] or 0, 5),
                "eff": round(m["effective_units"] or 0, 1)})
    units = {}
    for u in store.read_units():
        units[u["unit_id"]] = {"t": (u.get("title") or "")[:170],
                               "g": (u.get("grouping") or "")[:60],
                               "y": u.get("year")}
    for uid, m in unit_metrics.items():
        if uid in units:
            units[uid].update({"eff": round(m.get("effective_topics") or 0, 2),
                               "top": m.get("top_topic_id")})
    rows = store.read_membership()
    cells = [[r["unit_id"], r["topic_id"], round(r["containment"], 4), round(r["contribution"], 5)]
             for r in rows]
    cells.sort(key=lambda c: (c[0], -c[2]))
    side = partition.get("unit_side") or {}
    label, noun = NOUNS.get(domain, (domain, "unidad"))
    attach_ceplan(domain, run_id, topics)
    return {"run": run_id, "label": label, "noun": noun,
            "topics": topics, "units": units, "cells": cells,
            "ex": examples(cfg, store, rows, topics, units, raw_topics),
            "pc": round(side.get("partition_coefficient") or 0, 4),
            "pcn": round(side.get("partition_coefficient_normalized") or 0, 4),
            "pen": round(side.get("partition_entropy_normalized") or 0, 4),
            "mt": round(partition.get("mean_effective_topics_per_unit") or 0, 2),
            "mu": round(partition.get("mean_effective_units_per_topic") or 0, 1),
            "nu": partition.get("num_units_in_partition") or len(units),
            "nt": partition.get("num_topics_in_partition") or len(topics)}


def coverage(domain: str) -> dict:
    """Tasas de llenado de las columnas embebidas, para la pestaña de metodología.

    Se calcula sobre la poblacion YA filtrada por el universo minimo
    declarado (lb_domains.filter_min_requirements): antes de que ese filtro
    existiera esto se calculaba sobre TODAS las filas del CSV de origen, asi
    que las tasas de llenado mostradas no correspondian a la corrida real.
    """
    spec = lb_domains.get(domain)
    raw_rows = lb_domains.read_source(spec)
    rows, dropped_min_req = lb_domains.filter_min_requirements(spec, raw_rows)
    units, dropped = lb_domains.to_units(spec, rows, 6000)
    report = lb_coverage.build(spec, rows, units, dropped)
    cols = [{"n": c["column_name"], "f": round(c["fill_rate"], 4),
             "r": c["rows_filled"], "aux": c["column_name"].startswith("aux:")}
            for c in report["columns"] if c["used_in_embedding"]]
    cols.sort(key=lambda c: -c["f"])
    return {"src": spec.source_csv.name, "rows": report["rows_in_source"],
            "units": report["units_built"], "dropped": report["units_dropped"],
            "chars": report["text_chars"], "cols": cols, "req": spec.required_any,
            "raw_rows": len(raw_rows), "dropped_min_req": dropped_min_req,
            "provenance": provenance_notes(domain)}


def provenance_notes(domain: str) -> dict:
    """El embudo completo hasta la poblacion final: de donde salen los datos
    y por que se quedo tan poca. Numeros escritos a mano porque cada paso
    viene de un archivo/decision distinta que no se puede derivar solo del
    CSV de origen del dominio (ver conversacion del equipo)."""
    if domain == "projects":
        return {
            "steps": [
                {"n": 1928, "label": "Proyectos registrados en PULSO/CRIS",
                 "note": "hoja PROYECTOS de datos/informacion_proyecto_pulso.xlsx"},
                {"n": 975, "label": "Cerrados (Estado = \"5. Cerrado\") y de 2010 en adelante",
                 "note": "filtro fijo del equipo: solo proyectos concluidos, en la ventana "
                         "temporal declarada"},
                {"n": 409, "label": "Cumplen el universo mínimo declarado",
                 "note": "title + área de conocimiento + al menos una línea de investigación, "
                         "las tres. Decisión del equipo: un proyecto con solo título no da "
                         "suficiente señal para un análisis semántico serio."},
            ],
            "why": "Se probaron dos versiones antes de fijar esta: exigir título + línea de "
                   "investigación (cualquiera de las dos, sin exigir área de conocimiento) "
                   "dejaba 493; exigir las tres a la vez, como se hace aquí, deja 409. La "
                   "diferencia es chica porque en este registro casi todo proyecto con área "
                   "de conocimiento también tiene línea de investigación (se solapan), así "
                   "que la exigencia extra no penaliza dos veces lo mismo.",
        }
    if domain == "publications_linked":
        return {
            "steps": [
                {"n": 1192, "label": "Publicaciones declaradas como resultado de un proyecto "
                                     "del universo",
                 "note": "salidas/07_publications_linked_full.csv"},
                {"n": 308, "label": "Cumplen título + resumen + palabras clave, y su proyecto "
                                    "padre también califica",
                 "note": "mismo criterio de calidad que projects, extendido: no tiene sentido "
                         "declarar \"nuestros proyectos calificados\" y contar publicaciones "
                         "de un proyecto que no calificaría."},
                {"n": 300, "label": "Publicaciones distintas tras deduplicar",
                 "note": "8 publicaciones son resultado declarado de DOS proyectos a la vez "
                         "(comparten publication_id con project_id distinto); cuentan una "
                         "sola vez."},
            ],
            "why": "De las 308 filas que pasan el filtro por su propio texto, 351 pasarían "
                   "sin exigir que el proyecto padre también califique -- la exigencia extra "
                   "cuesta poco (43 filas) porque las publicaciones tienden a venir "
                   "precisamente de los proyectos mejor documentados.",
        }
    return {"steps": [], "why": ""}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="append", required=True, metavar="DOMINIO=RUN_ID",
                        help="Se puede repetir: --run projects=full-proj-975")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    cfg = lb_config.load()
    data, method = {}, {}
    for pair in args.run:
        domain, _, run_id = pair.partition("=")
        if not run_id:
            raise SystemExit(f"--run mal formado: {pair!r}. Formato: dominio=run_id")
        data[domain] = collect(cfg, domain, run_id)
        method[domain] = coverage(domain)
        print(f"  {domain:22s} {len(data[domain]['topics'])} temas · "
              f"{len(data[domain]['units'])} unidades · {len(data[domain]['cells']):,} celdas")

    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if "</" in blob:
        # Rompería el <script> que la incrusta.
        blob = blob.replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__DATA__", blob)
    html = html.replace("__METHOD__", json.dumps(method, ensure_ascii=False,
                                                 separators=(",", ":")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"\n-> {args.out.relative_to(ROOT)}  ({len(html)/1e6:.2f} MB)")
    print("Publicar con la herramienta Artifact, o abrir el fichero en el navegador.")


if __name__ == "__main__":
    main()

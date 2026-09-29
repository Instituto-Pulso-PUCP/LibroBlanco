#!/usr/bin/env python3
"""Cruza los temas normalizados (proyectos / publicaciones_linked) con los
Objetivos Nacionales (ON) del PEDN 2050 / CEPLAN, por similitud de embeddings.

Encargo (correo del profesor, ver conversacion): "introducir CEPLAN en el
analisis tematico y sacar los temas normalizados que deben ir asociados a los
ON" + "alinear temas normalizados con embeddings y ver donde estan mejor
clasificados: 1. de proyectos con ON, 2. publicaciones con ON".

CEPLAN no pasa por el pipeline de extraccion LLM: su taxonomia (ON -> Tematica
-> Sub-tematica) ya es oficial y esta nombrada por CEPLAN mismo -- solo hace
falta embeberla con el MISMO modelo que embebio nuestros temas para poder
compararlos (ver lb_ceplan.py). No se compara con otros planes/politicas mas
alla del PEDN 2050 -- eso sigue fuera de alcance segun lo acordado.

Para cada tema normalizado de un dominio, se reporta su mejor Sub-tematica
(la lectura mas especifica e interpretable), con la Tematica y el ON que
implica, mas el top-3 y el score directo contra el centroide del ON. Tambien
se compara contra "Lineas Ceplan" (arbol mas chico, solo referencia).

IMPORTANTE -- validar antes de confiar en el ranking: si los scores salen
comprimidos (ver diagnóstico impreso), el ranking es poco mas que ruido; ya
paso con otro modelo en este mismo corpus (ver
salidas/topics/policy_alignment_model_comparison_summary.md, ahora retirado).

Uso:
    python scripts/analysis/ceplan_alignment.py \
        --run projects=full-proj-409 \
        --run publications_linked=publications_linked-308
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import lb_aws      # noqa: E402
import lb_ceplan   # noqa: E402
import lb_cluster  # noqa: E402
import lb_config   # noqa: E402
import lb_store    # noqa: E402

NAMES = {"projects": "Proyectos", "publications_linked": "Publicaciones de proyectos"}


def embed_taxonomy(embedder, tree: dict) -> dict:
    """Embebe cada sub-tematica del arbol; devuelve centroides de sub-tema,
    tema y ON (jerarquico: ON = media de sus temas, tema = media de sus
    sub-temas -- asi un tema con muchas sub-temas no domina el centroide del
    ON solo por tener mas entradas que otro)."""
    leaves = []  # (on_id, on_label, tema, sub_id, sub_label, text)
    for on_id, on_node in tree.items():
        for tema, tema_node in on_node["temas"].items():
            for sub_id, sub_node in tema_node["subtemas"].items():
                leaves.append((on_id, on_node["label"], tema, sub_id,
                               sub_node["label"], sub_node["text"]))
    if not leaves:
        return {"sub": {}, "tema": {}, "on": {}, "on_label": {}, "n_leaves": 0}

    texts = [leaf[5] for leaf in leaves]
    matrix = lb_cluster.normalize_rows(embedder.embed(texts))

    sub_centroids = {}
    tema_members: dict[tuple[str, str], list[int]] = {}
    on_label = {}
    for i, (on_id, on_lbl, tema, sub_id, sub_lbl, _text) in enumerate(leaves):
        sub_centroids[(on_id, tema, sub_id)] = {
            "vector": matrix[i], "label": sub_lbl, "tema": tema, "on": on_id}
        tema_members.setdefault((on_id, tema), []).append(i)
        on_label[on_id] = on_lbl

    tema_centroids = {}
    on_members: dict[str, list[np.ndarray]] = {}
    for (on_id, tema), idxs in tema_members.items():
        vec = lb_cluster.normalize(matrix[idxs].mean(axis=0))
        tema_centroids[(on_id, tema)] = vec
        on_members.setdefault(on_id, []).append(vec)

    on_centroids = {on_id: lb_cluster.normalize(np.stack(vecs).mean(axis=0))
                    for on_id, vecs in on_members.items()}

    return {"sub": sub_centroids, "tema": tema_centroids, "on": on_centroids,
            "on_label": on_label, "n_leaves": len(leaves)}


def score_diagnostics(scores: list[float]) -> dict:
    arr = np.array(scores, dtype=np.float64)
    return {"n": len(arr), "min": float(arr.min()), "p25": float(np.quantile(arr, .25)),
            "median": float(np.median(arr)), "p75": float(np.quantile(arr, .75)),
            "max": float(arr.max())}


def align_domain(cfg, embedder, domain_key: str, run_id: str, primary: dict, secondary: dict) -> dict:
    store = lb_store.open_store(cfg, domain_key, run_id)
    topics = store.read_topics()
    topics = [t for t in topics if t.get("centroid")]

    sub_ids = list(primary["sub"].keys())
    sub_matrix = lb_cluster.as_matrix([primary["sub"][k]["vector"] for k in sub_ids])
    on_ids = list(primary["on"].keys())
    on_matrix = lb_cluster.as_matrix([primary["on"][k] for k in on_ids])

    sec_sub_ids = list(secondary["sub"].keys())
    sec_matrix = (lb_cluster.as_matrix([secondary["sub"][k]["vector"] for k in sec_sub_ids])
                  if sec_sub_ids else None)

    rows = []
    best_scores, on_direct_scores = [], []
    for t in topics:
        vec = np.asarray(t["centroid"], dtype=lb_cluster.DTYPE)
        sub_sims = sub_matrix @ vec
        order = np.argsort(-sub_sims)
        best_i = int(order[0])
        best_key = sub_ids[best_i]
        best_leaf = primary["sub"][best_key]
        top3 = [{"on": primary["sub"][sub_ids[j]]["on"],
                 "tema": primary["sub"][sub_ids[j]]["tema"],
                 "subtema": primary["sub"][sub_ids[j]]["label"],
                 "score": round(float(sub_sims[j]), 4)} for j in order[:3]]

        on_sims = on_matrix @ vec
        on_best_i = int(np.argmax(on_sims))

        row = {
            "topic_id": t["topic_id"], "label": t["label"],
            "num_variants": t.get("num_variants"),
            "best_on_via_subtema": best_leaf["on"],
            "best_on_label": primary["on_label"][best_leaf["on"]],
            "best_tema": best_leaf["tema"],
            "best_subtema": best_leaf["label"],
            "score_subtema": round(float(sub_sims[best_i]), 4),
            "top3": top3,
            "on_direct_id": on_ids[on_best_i],
            "on_direct_label": primary["on_label"][on_ids[on_best_i]],
            "score_on_direct": round(float(on_sims[on_best_i]), 4),
            "agrees_direct_vs_subtema": on_ids[on_best_i] == best_leaf["on"],
        }
        if sec_matrix is not None:
            sec_sims = sec_matrix @ vec
            sec_i = int(np.argmax(sec_sims))
            sec_leaf = secondary["sub"][sec_sub_ids[sec_i]]
            row["secondary_best_on"] = sec_leaf["on"]
            row["secondary_best_subtema"] = sec_leaf["label"]
            row["secondary_score"] = round(float(sec_sims[sec_i]), 4)
        rows.append(row)
        best_scores.append(float(sub_sims[best_i]))
        on_direct_scores.append(float(on_sims[on_best_i]))

    agree = sum(1 for r in rows if r["agrees_direct_vs_subtema"])
    diag = {
        "score_subtema": score_diagnostics(best_scores),
        "score_on_direct": score_diagnostics(on_direct_scores),
        "on_agreement_subtema_vs_direct": f"{agree}/{len(rows)}",
    }
    return {"domain": domain_key, "run": run_id, "rows": rows, "diagnostics": diag}


def summarize_by_on(result: dict, topics_by_id: dict) -> dict:
    """Unidades-equivalentes del dominio agrupadas por ON (via mejor sub-tema)."""
    totals: dict[str, float] = {}
    for r in result["rows"]:
        eq = (topics_by_id.get(r["topic_id"]) or {}).get("units_equivalent", 0) or 0
        totals[r["best_on_label"]] = totals.get(r["best_on_label"], 0.0) + eq
    return dict(sorted(totals.items(), key=lambda kv: -kv[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="append", required=True, metavar="DOMINIO=RUN_ID")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    cfg = lb_config.load()
    embedder = lb_aws.embedding_client(cfg)

    print("Cargando taxonomia CEPLAN/PEDN 2050 (Lineas de Inv. + Lineas Ceplan)...")
    tax = lb_ceplan.build_taxonomy()
    print(f"  ON={len(tax['on'])}  categorias excluidas (no-ON, fuera del cruce)="
          f"{sorted({r['on'] for r in tax['excluded_categories']})}")

    print("Embebiendo la taxonomia (mismo modelo que los temas: "
          f"{cfg.get('bedrock.embedding_model_id')})...")
    primary = embed_taxonomy(embedder, tax["on"])
    secondary = embed_taxonomy(embedder, tax["secondary"])
    print(f"  primaria (Lineas de Inv.): {primary['n_leaves']} sub-temas embebidos")
    print(f"  secundaria (Lineas Ceplan): {secondary['n_leaves']} sub-temas embebidos")

    for pair in args.run:
        domain_key, _, run_id = pair.partition("=")
        store = lb_store.open_store(cfg, domain_key, run_id)
        topics_by_id = {t["topic_id"]: t for t in store.read_topics()}
        _, topic_metrics, _ = store.read_metrics()

        print(f"\n=== {NAMES.get(domain_key, domain_key)} ({run_id}) ===")
        result = align_domain(cfg, embedder, domain_key, run_id, primary, secondary)
        d = result["diagnostics"]["score_subtema"]
        print(f"  temas comparados: {d['n']}")
        print(f"  score (mejor sub-tema): min={d['min']:.3f} mediana={d['median']:.3f} "
              f"max={d['max']:.3f}")
        do = result["diagnostics"]["score_on_direct"]
        print(f"  score (ON directo): min={do['min']:.3f} mediana={do['median']:.3f} "
              f"max={do['max']:.3f}")
        print(f"  acuerdo ON-por-subtema vs ON-directo: "
              f"{result['diagnostics']['on_agreement_subtema_vs_direct']}")
        if d["median"] > 0.9 or (d["max"] - d["min"]) < 0.05:
            print("  AVISO: scores muy comprimidos -- el ranking podria ser poco "
                  "informativo. Revisar antes de reportar resultados.")

        out_dir = args.out_dir or (ROOT / "salidas" / "topics" / domain_key / run_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "06_ceplan_alignment.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        by_on = summarize_by_on(result, topic_metrics)
        total_eq = sum(by_on.values()) or 1.0
        lines = [f"# Alineación con Objetivos Nacionales (PEDN 2050) — "
                 f"{NAMES.get(domain_key, domain_key)}", "",
                 f"Corrida `{run_id}`. Taxonomía: hoja `Líneas de Inv.` del PEDN 2050 "
                 f"({primary['n_leaves']} sub-temáticas, {len(tax['on'])} ON). "
                 f"Modelo de embeddings: `{cfg.get('bedrock.embedding_model_id')}` "
                 "(el mismo que embebió los temas, para que las similitudes sean comparables).",
                 "",
                 "## Diagnóstico de la comparación",
                 f"- Score contra la mejor sub-temática: min {d['min']:.3f} · "
                 f"mediana {d['median']:.3f} · max {d['max']:.3f}",
                 f"- Score contra el centroide del ON directamente: min {do['min']:.3f} · "
                 f"mediana {do['median']:.3f} · max {do['max']:.3f}",
                 f"- El ON implicado por la mejor sub-temática coincide con el ON de mayor "
                 f"similitud directa en {result['diagnostics']['on_agreement_subtema_vs_direct']} "
                 "de los temas.",
                 "", "## Reparto por ON (unidades-equivalentes, vía mejor sub-temática)", "",
                 "| ON | Unidades-equivalentes | % del corpus |", "|---|---:|---:|"]
        for on_label, eq in by_on.items():
            lines.append(f"| {on_label} | {eq:.1f} | {eq/total_eq*100:.1f}% |")
        lines += ["", "## Detalle por tema (ordenado por tamaño)", "",
                  "| Tema | eq | ON | Sub-temática | score | ON directo | score dir. |",
                  "|---|---:|---|---|---:|---|---:|"]
        rows_sorted = sorted(result["rows"], key=lambda r: -(
            (topics_by_id.get(r["topic_id"]) or {}).get("num_variants") or 0))
        for r in rows_sorted:
            eq = (topic_metrics.get(r["topic_id"]) or {}).get("units_equivalent", 0) or 0
            flag = "" if r["agrees_direct_vs_subtema"] else " ⚠"
            lines.append(f"| {r['label']} | {eq:.1f} | {r['best_on_label'].split('.')[0]} | "
                         f"{r['best_subtema']} | {r['score_subtema']:.3f} | "
                         f"{r['on_direct_label'].split('.')[0]}{flag} | {r['score_on_direct']:.3f} |")
        (out_dir / "reporte_ceplan_alignment.md").write_text("\n".join(lines), encoding="utf-8")
        print(f"  -> {out_dir.relative_to(ROOT)}/06_ceplan_alignment.json")
        print(f"  -> {out_dir.relative_to(ROOT)}/reporte_ceplan_alignment.md")


if __name__ == "__main__":
    main()

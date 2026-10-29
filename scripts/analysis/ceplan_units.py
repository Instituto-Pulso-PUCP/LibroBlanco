#!/usr/bin/env python3
"""Cruce unidad (proyecto / publicacion) <-> hoja de un plan nacional.

Nacio para el PEDN 2050 / CEPLAN (sub-tematicas); ahora el plan sale del
dominio (lb_domains.Domain.plan -> lb_plans): PUCP contra el PEDN 2050,
ECOTEC contra las politicas del PND 2025-2029. Abajo "sub-tematica" se lee
como "hoja del plan".

Responde, por dominio, las dos preguntas del encargo:
  - "¿que sub-tematicas CEPLAN desarrolla este proyecto?"  (hasta 5, con piso)
  - "¿que proyectos desarrollan esta sub-tematica?"         (y cuales no tiene nadie)

Metodo (ver EXPERIMENTS.md §6 y docs/cuantificacion_temas.md §8):
  1. Candidatas por embeddings: similitud coseno entre el embedding de la
     unidad (el mismo de la etapa 03) y el de cada sub-tematica, tomando la
     mayor entre su texto en espanol y su traduccion al ingles (las
     publicaciones en ingles puntuan ~0.15 menos contra texto en espanol).
     Se quedan las `max_candidates` mejores con similitud >= `floor` y, en
     la otra direccion, cada sub-tematica suma sus `reverse_top_m` unidades
     mas similares (sobre el piso) a las candidatas de esas unidades. Sin la
     via inversa, las sub-tematicas de linea base baja (puntuan menos contra
     todo, p.ej. "Saneamiento") nunca entran al top de ninguna unidad aunque
     un proyecto de agua potable puntue 0.65 contra ellas: apareceria como
     "sin cobertura" un hueco que es solo de recuperacion.
  2. Verificacion por LLM: un modelo lee el texto de la unidad y califica
     cada candidata 0/1/2 (0 = sin relacion, 1 = tangencial, 2 = la
     desarrolla claramente). Mismo prompt que el benchmark que eligio el
     modelo (scripts/analysis/ceplan_judge_benchmark.py). Cache por
     unidad+texto+candidatas: re-ejecutar no vuelve a pagar.
  3. Cuantificacion: afinidad = peso(grado) * (similitud - piso) para todos
     los vinculos confirmados (grado >= 1); contencion y contribucion con
     lb_membership, igual que unidad <-> tema. `top_n` solo limita lo que se
     lista por unidad: la pregunta inversa ("¿quien desarrolla esta
     sub-tematica?") usa todos los vinculos confirmados, o un proyecto con
     seis sub-tematicas claras perderia la sexta en la cobertura.

Salidas en salidas/topics/<dominio>/<run>/, con el prefijo del plan
(PEDN: "ceplan", PND: "pnd"): 07_<prefijo>_units.json, <prefijo>_por_unidad.csv,
<prefijo>_por_<hoja>.csv, reporte_<prefijo>_unidades.md; y la cobertura
cruzada de los dominios en <plan.cache_dir>/reporte_cobertura.md
(PEDN: salidas/topics/ceplan/).

Parametros: seccion [ceplan] de config/pipeline.toml, sobrescribible por plan
en [plans.<clave>] (p.ej. plans.pnd_ec_2025.developed_min_grade2).

    source config/env.sh
    python scripts/analysis/ceplan_units.py \\
        --run projects=full-proj-646 --run publications_linked=publications_linked-529
    python scripts/analysis/ceplan_units.py --run projects=full-proj-646 --dry-run
    python scripts/analysis/ceplan_units.py \\
        --run ecotec_projects=<run> --run ecotec_publications=<run>
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

import lb_aws         # noqa: E402
import lb_ceplan      # noqa: E402
import lb_cluster     # noqa: E402
import lb_config      # noqa: E402
import lb_domains     # noqa: E402
import lb_membership  # noqa: E402
import lb_plans       # noqa: E402
import lb_store       # noqa: E402
from ceplan_judge_benchmark import MAX_TEXT_CHARS, PRICES, parse_grades  # noqa: E402


def domain_name(domain):
    return lb_domains.get(domain).short_label or domain


def domain_noun(domain):
    return lb_domains.get(domain).noun or domain

DEFAULTS = {
    "floor": 0.40,
    "max_candidates": 8,
    "reverse_top_m": 10,
    # Una unidad generica queda cerca de muchas sub-tematicas a la vez: sin
    # este tope recibia hasta ~100 candidatas por la via inversa. Al llenarse,
    # la sub-tematica pasa a su siguiente unidad mas cercana.
    "reverse_max_per_unit": 6,
    "top_n": 5,
    "judge_model_id": "us.meta.llama4-maverick-17b-instruct-v1:0",
    "judge_workers": 4,
    # Peso de cada grado en la afinidad: una relacion tangencial cuenta la
    # mitad que una clara.
    "weight_grade_1": 0.5,
    "weight_grade_2": 1.0,
    # Cobertura de una sub-tematica, contada solo con vinculos de grado 2 (los
    # de grado 1 del verificador son ruidosos en el margen, EXPERIMENTS.md §6):
    # >= este numero -> desarrollada; 1 a este numero - 1 -> debil; 0 -> sin
    # desarrollo (puede tener vinculos tangenciales).
    "developed_min_grade2": 3,
}

PRICE_KEY = {"us.meta.llama4-maverick-17b-instruct-v1:0": "llama4_maverick",
             "us.anthropic.claude-haiku-4-5-20251001-v1:0": "haiku45",
             "us.amazon.nova-pro-v1:0": "nova_pro",
             "qwen.qwen3-32b-v1:0": "qwen3_32b"}


def params_from(cfg, args, plan):
    p = {k: cfg.get(f"plans.{plan.key}.{k}", cfg.get(f"ceplan.{k}", v))
         for k, v in DEFAULTS.items()}
    if args.model:
        p["judge_model_id"] = args.model
    p["floor"] = float(p["floor"])
    for k in ("max_candidates", "reverse_top_m", "reverse_max_per_unit", "top_n", "judge_workers", "developed_min_grade2"):
        p[k] = int(p[k])
    return p


# --------------------------------------------------------------------------
# Taxonomia
# --------------------------------------------------------------------------

def load_taxonomy(cfg, plan):
    """Hojas del plan con sus embeddings en espanol e ingles (normalizados)."""
    subs = plan.load()
    texts_es = [s["text"] for s in subs]
    # La traduccion esta en cache desde la calibracion; solo llama al LLM si
    # el plan cambio alguna hoja.
    translations = lb_ceplan.translate_texts(
        lb_aws.llm_client(cfg), texts_es,
        cache_path=plan.cache_dir / f"{plan.leaf_slug}s_en.json",
        system=plan.translate_system)
    # Cache en disco: Cohere no devuelve exactamente el mismo vector en cada
    # llamada, y una diferencia minima cambia las candidatas que rozan el piso
    # o el tope (y con ellas el cache del LLM). Se invalida si cambia el
    # modelo o cualquier texto.
    model_id = cfg.get("bedrock.embedding_model_id")
    texts_en = [translations[t] for t in texts_es]
    digest = hashlib.sha256(json.dumps([model_id, texts_es, texts_en]).encode()).hexdigest()[:16]
    cache = plan.cache_dir / f"{plan.leaf_slug}s_emb.npz"
    if cache.exists():
        stored = np.load(cache)
        if str(stored["digest"]) == digest:
            return subs, stored["es"], stored["en"]
    embedder = lb_aws.embedding_client(cfg)
    es = lb_cluster.normalize_rows(embedder.embed(texts_es))
    en = lb_cluster.normalize_rows(embedder.embed(texts_en))
    plan.cache_dir.mkdir(parents=True, exist_ok=True)
    np.savez(cache, es=es, en=en, digest=np.array(digest))
    return subs, es, en


# --------------------------------------------------------------------------
# Verificacion por LLM (con cache)
# --------------------------------------------------------------------------

def build_user(text, cands, subs, plan):
    lines = [f"{n + 1}. {subs[j]['label']} ({plan.judge_level2_tag}: {subs[j]['tema']}; "
             f"{subs[j]['on_label'][:60]})" for n, (j, _sim) in enumerate(cands)]
    return (f"INVESTIGACION:\n{text[:MAX_TEXT_CHARS]}\n\n{plan.judge_header}:\n"
            + "\n".join(lines))


def cache_key(model_id, system, user):
    return hashlib.sha256(f"{model_id}\n{system}\n{user}".encode()).hexdigest()[:24]


def judge_units(cfg, params, plan, jobs, cache_path):
    """jobs: [(unit_id, user_prompt, sub_ids candidatas en orden)]. Devuelve {unit_id: grados|None}
    y el uso de tokens de las llamadas nuevas."""
    cache = {}
    if cache_path.exists():
        for line in cache_path.open(encoding="utf-8"):
            row = json.loads(line)
            cache[row["key"]] = row
    model_id = params["judge_model_id"]
    lock = threading.Lock()
    usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "failed": 0}
    results = {}

    def work(job):
        unit_id, user, sub_ids = job
        n = len(sub_ids)
        key = cache_key(model_id, plan.judge_system, user)
        if key in cache and cache[key]["grades"] is not None:
            return unit_id, cache[key]["grades"]
        client = lb_aws.BedrockClient(cfg)
        grades, raw, used = None, "", {"input_tokens": 0, "output_tokens": 0}
        for _attempt in range(2):  # un reintento si la respuesta no se pudo leer
            raw = client.converse(plan.judge_system, user, model_id=model_id, max_tokens=2048)
            used["input_tokens"] += client.last_usage["input_tokens"]
            used["output_tokens"] += client.last_usage["output_tokens"]
            grades = parse_grades(raw, n)
            if grades is not None:
                break
        with lock:
            usage["calls"] += 1
            usage["input_tokens"] += used["input_tokens"]
            usage["output_tokens"] += used["output_tokens"]
            usage["failed"] += grades is None
            with cache_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"key": key, "unit_id": unit_id, "model": model_id,
                                         "subs": sub_ids, "grades": grades, "raw": raw[-400:]},
                                        ensure_ascii=False) + "\n")
            if usage["calls"] % 100 == 0:
                print(f"    {usage['calls']} llamadas nuevas...")
        return unit_id, grades

    with ThreadPoolExecutor(max_workers=params["judge_workers"]) as pool:
        for unit_id, grades in pool.map(work, jobs):
            results[unit_id] = grades
    return results, usage


# --------------------------------------------------------------------------
# Un dominio
# --------------------------------------------------------------------------

def run_domain(cfg, params, plan, domain, run_id, subs, emb_es, emb_en, dry_run):
    store = lb_store.open_store(cfg, domain, run_id)
    units = {u["unit_id"]: u for u in store.read_units()}
    emb = store.read_unit_embeddings()
    ids = [e["unit_id"] for e in emb if e["unit_id"] in units]
    vectors = lb_cluster.normalize_rows(lb_cluster.as_matrix(
        [e["embedding"] for e in emb if e["unit_id"] in units]))
    sims = np.maximum(vectors @ emb_es.T, vectors @ emb_en.T)

    floor, k = params["floor"], params["max_candidates"]
    chosen = {i: {int(j) for j in np.argsort(-sims[i])[:k] if sims[i, j] >= floor}
              for i in range(len(ids))}
    # Via inversa, por rondas: en la ronda r cada sub-tematica ofrece su r-esima
    # unidad mas cercana; la unidad la acepta si aun tiene cupo. Asi ninguna
    # sub-tematica acapara cupos y las unidades genericas no se saturan.
    m, cap = params["reverse_top_m"], params["reverse_max_per_unit"]
    order_by_sub = np.argsort(-sims, axis=0)          # [rango, sub] -> unidad
    taken = {j: 0 for j in range(sims.shape[1])}       # unidades sumadas por sub-tematica
    added_to = {i: 0 for i in range(len(ids))}         # cupo usado por unidad
    reverse_added = 0
    for r in range(len(ids)):
        active = [j for j in range(sims.shape[1]) if taken[j] < m]
        if not active:
            break
        for j in active:
            i = int(order_by_sub[r, j])
            if sims[i, j] < floor:
                taken[j] = m  # el resto de su lista esta bajo el piso
                continue
            if j in chosen[i]:
                taken[j] += 1  # ya era candidata por la via directa
            elif added_to[i] < cap:
                chosen[i].add(j)
                added_to[i] += 1
                taken[j] += 1
                reverse_added += 1
    # Sin tope total: un tope por similitud cortaria justo lo que agrego la via
    # inversa (son las de rango bajo para esa unidad). Queda acotado igual:
    # cada sub-tematica suma a lo sumo reverse_top_m unidades.
    candidates = {}
    for i, unit_id in enumerate(ids):
        candidates[unit_id] = sorted(((j, float(sims[i, j])) for j in chosen[i]),
                                     key=lambda c: -c[1])
    print(f"  via inversa: +{reverse_added} candidatas (top {params['reverse_top_m']} unidades "
          f"por sub-tematica); maximo por unidad: {max(len(c) for c in chosen.values())}")
    no_cand = [u for u in ids if not candidates[u]]
    n_cand = sum(len(c) for c in candidates.values())
    print(f"  {len(ids)} unidades con embedding; {len(ids) - len(no_cand)} con candidatas "
          f"(media {n_cand / max(len(ids) - len(no_cand), 1):.1f}); "
          f"{len(no_cand)} sin ninguna sobre el piso {floor}")
    if dry_run:
        return None

    out_dir = ROOT / "salidas" / "topics" / domain / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = plan.file_prefix
    jobs = [(u, build_user(units[u]["text"], candidates[u], subs, plan),
             [subs[j]["id"] for j, _s in candidates[u]])
            for u in ids if candidates[u]]
    grades, usage = judge_units(cfg, params, plan, jobs,
                                out_dir / f"07_{prefix}_judge_cache.jsonl")
    failed = sorted(u for u, g in grades.items() if g is None)
    price = PRICES.get(PRICE_KEY.get(params["judge_model_id"], ""), (0.0, 0.0))
    usage["usd"] = (usage["input_tokens"] * price[0] + usage["output_tokens"] * price[1]) / 1e6
    print(f"  LLM: {usage['calls']} llamadas nuevas ({len(jobs) - usage['calls']} desde cache), "
          f"{usage['input_tokens']:,} / {usage['output_tokens']:,} tokens, "
          f"~USD {usage['usd']:.3f}; respuestas ilegibles: {len(failed)}")

    # Afinidad: todos los vinculos confirmados (grado >= 1).
    weight = {1: float(params["weight_grade_1"]), 2: float(params["weight_grade_2"])}
    affinity, links = {}, {}
    for unit_id, cands in candidates.items():
        g = grades.get(unit_id)
        if not g:
            continue
        kept = [(j, s, gr) for (j, s), gr in zip(cands, g) if gr >= 1]
        # 1e-3 evita peso cero para una candidata justo en el piso
        for j, s, gr in kept:
            affinity[(unit_id, subs[j]["id"])] = weight[gr] * (s - floor + 1e-3)
            links[(unit_id, subs[j]["id"])] = {"grade": gr, "sim": s}
    result = lb_membership.quantify(affinity, unit_ids=ids, topic_ids=[s["id"] for s in subs])
    errors = lb_membership.validate(result)
    if errors:
        raise SystemExit("La cuantificacion no cumple sus identidades:\n  " + "\n  ".join(errors[:10]))

    # --- por unidad -------------------------------------------------------
    sub_by_id = {s["id"]: s for s in subs}
    per_unit = {}
    for (unit_id, sub_id), c in result.containment.items():
        per_unit.setdefault(unit_id, []).append({
            "sub_id": sub_id, "grade": links[(unit_id, sub_id)]["grade"],
            "sim": round(links[(unit_id, sub_id)]["sim"], 4),
            "containment": round(c, 4),
            "contribution": round(result.contribution.get((unit_id, sub_id), 0.0), 5)})
    for rows in per_unit.values():
        rows.sort(key=lambda r: -r["containment"])
        for n, r in enumerate(rows):
            r["top"] = n < params["top_n"]
    status = {}
    for unit_id in ids:
        if unit_id in per_unit:
            status[unit_id] = "alineada"
        elif not candidates[unit_id]:
            status[unit_id] = "sin_candidatas"
        elif grades.get(unit_id) is None:
            status[unit_id] = "verificacion_fallida"
        else:
            status[unit_id] = "rechazadas_por_llm"

    # --- por sub-tematica -------------------------------------------------
    per_sub = {}
    for s in subs:
        rows = [(u, r) for u, rs in per_unit.items() for r in rs if r["sub_id"] == s["id"]]
        n2 = sum(1 for _u, r in rows if r["grade"] == 2)
        eq = result.topic_equivalents.get(s["id"], 0.0)
        if n2 >= params["developed_min_grade2"]:
            cov = "desarrollada"
        elif n2 > 0:
            cov = "debil"
        else:
            cov = "sin_desarrollo"
        per_sub[s["id"]] = {
            "label": s["label"], "tema": s["tema"], "on": s["on"],
            "num_units": len(rows), "num_grade2": n2, "units_equivalent": round(eq, 3),
            "coverage": cov,
            "units": sorted(({"unit_id": u, "grade": r["grade"], "sim": r["sim"],
                              "containment": r["containment"], "contribution": r["contribution"]}
                             for u, r in rows), key=lambda x: -x["contribution"])}

    def rollup(level):
        out = {}
        for sid, v in per_sub.items():
            key = v["on"] if level == "on" else f"{v['on']} · {v['tema']}"
            out[key] = out.get(key, 0.0) + v["units_equivalent"]
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    partition = result.partition_metrics
    payload = {
        "domain": domain, "run": run_id, "params": params, "usage": usage,
        # Las claves de abajo (on, tema, subtematicas...) conservan los nombres
        # de CEPLAN para cualquier plan; "plan" dice como se llaman de verdad.
        "plan": {"key": plan.key, "name": plan.name, "leaf": plan.leaf, "leaves": plan.leaves,
                 "level1": plan.level1, "level1_long": plan.level1_long, "level2": plan.level2},
        "num_units": len(ids),
        "status_counts": {s: sum(1 for v in status.values() if v == s)
                          for s in ("alineada", "rechazadas_por_llm", "sin_candidatas",
                                    "verificacion_fallida")},
        "candidates_total": n_cand,
        "links_total": len(affinity),
        "links_by_grade": {g: sum(1 for v in links.values() if v["grade"] == g) for g in (1, 2)},
        "mean_effective_subs_per_unit": partition.get("mean_effective_topics_per_unit"),
        "on_labels": {s["on"]: s["on_label"] for s in subs},
        "by_on": rollup("on"), "by_tema": rollup("tema"),
        "units": {u: {"title": units[u].get("title", ""), "status": status[u],
                      "subs": per_unit.get(u, []),
                      # todas las candidatas evaluadas, en orden de similitud,
                      # con el grado del verificador (null si no se pudo leer)
                      "judged": [{"sub_id": subs[j]["id"], "sim": round(sim, 4),
                                  "grade": (grades.get(u) or [None] * len(candidates[u]))[n]}
                                 for n, (j, sim) in enumerate(candidates[u])]}
                  for u in ids},
        "subtematicas": per_sub,
    }
    (out_dir / f"07_{prefix}_units.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    col_l1, col_l2, col_leaf = plan.csv_columns
    with (out_dir / f"{prefix}_por_unidad.csv").open("w", encoding="utf-8-sig", newline="") as h:
        w = csv.writer(h)
        w.writerow(["unit_id", "titulo", "estado", "rango", col_leaf, col_l2, col_l1,
                    "grado", "similitud", "contencion", "contribucion"])
        for u in ids:
            rows = [r for r in per_unit.get(u, []) if r["top"]] or [None]
            for n, r in enumerate(rows, 1):
                if r is None:
                    w.writerow([u, units[u].get("title", ""), status[u], "", "", "", "", "", "", "", ""])
                    continue
                s = sub_by_id[r["sub_id"]]
                w.writerow([u, units[u].get("title", ""), status[u], n, s["label"], s["tema"], s["on"],
                            r["grade"], f"{r['sim']:.4f}", f"{r['containment']:.4f}",
                            f"{r['contribution']:.5f}"])
    with (out_dir / f"{prefix}_por_{plan.leaf_slug}.csv").open("w", encoding="utf-8-sig",
                                                                newline="") as h:
        w = csv.writer(h)
        w.writerow([col_l1, col_l2, col_leaf, "cobertura", "num_unidades", "num_grado2",
                    "unidades_equivalentes", "unit_id", "titulo", "grado", "contribucion"])
        for sid, v in per_sub.items():
            rows = v["units"] or [None]
            for r in rows:
                base = [v["on"], v["tema"], v["label"], v["coverage"], v["num_units"],
                        v["num_grade2"], f"{v['units_equivalent']:.3f}"]
                if r is None:
                    w.writerow(base + ["", "", "", ""])
                else:
                    w.writerow(base + [r["unit_id"], units[r["unit_id"]].get("title", ""),
                                       r["grade"], f"{r['contribution']:.5f}"])
    write_domain_report(out_dir, payload, subs, plan)
    print(f"  -> {out_dir.relative_to(ROOT)}/07_{prefix}_units.json, {prefix}_por_unidad.csv, "
          f"{prefix}_por_{plan.leaf_slug}.csv, reporte_{prefix}_unidades.md")
    return payload


def write_domain_report(out_dir, p, subs, plan):
    domain, noun = p["domain"], domain_noun(p["domain"])
    leaf, leaves = plan.leaf, plan.leaves
    sc = p["status_counts"]
    n = p["num_units"]
    covs = {c: [v for v in p["subtematicas"].values() if v["coverage"] == c]
            for c in ("desarrollada", "debil", "sin_desarrollo")}
    total_eq = sum(p["by_on"].values()) or 1.0
    pr = p["params"]
    lines = [
        f"# {leaves.capitalize()} del {plan.name} por unidad — {domain_name(domain)}", "",
        f"Corrida `{p['run']}` · {n} {noun} · {len(subs)} {leaves} ({plan.source_note}). "
        f"Candidatas por embeddings (piso {pr['floor']}, hasta {pr['max_candidates']} por unidad "
        f"más las {pr['reverse_top_m']} unidades más cercanas a cada {leaf}, "
        f"máx(es, en)); verificadas por `{pr['judge_model_id']}` con grado 0/1/2; se conservan las "
        f"de grado ≥ 1 (en el listado por unidad, las {pr['top_n']} con mayor contención). Método y elección del modelo: "
        "EXPERIMENTS.md §6.", "",
        "## Unidades", "",
        f"- Con al menos una {leaf} confirmada: **{sc['alineada']}** ({sc['alineada'] / n:.0%})",
        f"- Con candidatas pero todas rechazadas por el LLM: {sc['rechazadas_por_llm']}",
        f"- Sin ninguna candidata sobre el piso: {sc['sin_candidatas']}",
        f"- Verificación fallida (respuesta ilegible): {sc['verificacion_fallida']}",
        f"- Vínculos: {p['links_total']} ({p['links_by_grade'][2]} de grado 2, "
        f"{p['links_by_grade'][1]} de grado 1) de {p['candidates_total']} candidatas; "
        f"{leaves} efectivas por unidad (media): {p['mean_effective_subs_per_unit']:.2f}",
        f"- Costo de la verificación en esta ejecución: ~USD {p['usage']['usd']:.3f} "
        f"({p['usage']['calls']} llamadas nuevas)", "",
        f"## Reparto por {plan.level1_long} (unidades-equivalentes)", "",
        f"| {plan.level1} | Unidades-equivalentes | % de lo alineado |", "|---|---:|---:|"]
    for on, eq in p["by_on"].items():
        lines.append(f"| {p['on_labels'][on][:90]} | {eq:.1f} | {eq / total_eq:.1%} |")
    k = pr["developed_min_grade2"]
    head = f"| {plan.level1} | {plan.level2} | {leaf.capitalize()} |"
    lines += ["", f"## Cobertura de las {leaves}", "",
              "Se cuenta solo con vínculos de grado 2 (relación clara); los tangenciales se "
              "listan pero no cierran un hueco.", "",
              f"- Desarrolladas (≥ {k} unidades de grado 2): **{len(covs['desarrollada'])}**",
              f"- Débiles (1 a {k - 1} de grado 2): {len(covs['debil'])}",
              f"- **Sin desarrollo (ninguna de grado 2): {len(covs['sin_desarrollo'])}**", "",
              "### Sin desarrollo", "",
              f"{head} vínculos tangenciales |", "|---|---|---|---:|"]
    for v in sorted(covs["sin_desarrollo"], key=lambda v: (v["on"], v["tema"])):
        lines.append(f"| {v['on']} | {v['tema']} | **{v['label']}** | {v['num_units']} |")
    lines += ["", "### Débiles", "", f"{head} unidades | de grado 2 |",
              "|---|---|---|---:|---:|"]
    for v in sorted(covs["debil"], key=lambda v: (v["on"], v["tema"])):
        lines.append(f"| {v['on']} | {v['tema']} | {v['label']} | {v['num_units']} | {v['num_grade2']} |")
    lines += ["", "### Las 15 más desarrolladas", "",
              f"| {leaf.capitalize()} | {plan.level1} | unidades | de grado 2 | unidades-equivalentes |",
              "|---|---|---:|---:|---:|"]
    for v in sorted(p["subtematicas"].values(), key=lambda v: -v["units_equivalent"])[:15]:
        lines.append(f"| {v['label']} | {v['on']} | {v['num_units']} | {v['num_grade2']} | "
                     f"{v['units_equivalent']:.1f} |")
    lines += ["", "Precisión de los vínculos: **pendiente** de la validación sobre una muestra "
              "de la salida real (EXPERIMENTS.md §6.4). No reportar como exacta antes de eso.", ""]
    (out_dir / f"reporte_{plan.file_prefix}_unidades.md").write_text("\n".join(lines),
                                                                      encoding="utf-8")


def write_cross_report(payloads, subs, plan):
    """Cobertura conjunta: que hojas del plan no desarrolla ningun dominio."""
    lines = [f"# Cobertura de las {plan.leaves} del {plan.name} — proyectos y publicaciones", "",
             f"| {plan.level1} | {plan.level2} | {plan.leaf.capitalize()} | " +
             " | ".join(f"{domain_noun(p['domain'])} (grado 2)" for p in payloads) + " |",
             "|---|---|---|" + "---:|" * len(payloads)]
    nobody = []
    for s in sorted(subs, key=lambda s: (s["on"], s["tema"], s["label"])):
        cells = []
        total = 0
        for p in payloads:
            v = p["subtematicas"][s["id"]]
            cells.append(f"{v['num_units']} ({v['num_grade2']})")
            total += v["num_grade2"]
        if total == 0:
            nobody.append(s)
        lines.append(f"| {s['on']} | {s['tema']} | {s['label']} | " + " | ".join(cells) + " |")
    head = ["", "Celdas: unidades vinculadas (de ellas, con relación clara, grado 2).", "",
            f"**{plan.leaves.capitalize()} sin ninguna unidad de grado 2 en ningún dominio: "
            f"{len(nobody)}**", ""]
    head += [f"- {s['on']} · {s['tema']} · {s['label']}" for s in nobody] + [""]
    lines[2:2] = head
    plan.cache_dir.mkdir(parents=True, exist_ok=True)
    (plan.cache_dir / "reporte_cobertura.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n-> {(plan.cache_dir / 'reporte_cobertura.md').relative_to(ROOT)} "
          f"({len(nobody)} {plan.leaves} sin ninguna unidad de grado 2)")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="append", required=True, metavar="DOMINIO=RUN_ID")
    parser.add_argument("--model", help="Sobrescribe ceplan.judge_model_id.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo cuenta candidatas; no llama al LLM ni escribe nada.")
    args = parser.parse_args()

    runs = [pair.partition("=")[::2] for pair in args.run]
    plan_keys = {lb_domains.get(domain).plan for domain, _run in runs}
    if len(plan_keys) != 1:
        raise SystemExit(f"Los dominios de --run se cruzan con planes distintos ({sorted(plan_keys)}); "
                         "correr una vez por plan.")
    plan = lb_plans.get(plan_keys.pop())

    cfg = lb_config.load()
    params = params_from(cfg, args, plan)
    print(f"Plan: {plan.name} · verificador: {params['judge_model_id']} · piso {params['floor']} · "
          f"hasta {params['max_candidates']} candidatas · top {params['top_n']}")
    subs, emb_es, emb_en = load_taxonomy(cfg, plan)
    print(f"Taxonomía: {len(subs)} {plan.leaves} embebidas (es + en)")
    payloads = []
    for domain, run_id in runs:
        print(f"\n=== {domain_name(domain)} ({run_id}) ===")
        p = run_domain(cfg, params, plan, domain, run_id, subs, emb_es, emb_en, args.dry_run)
        if p:
            payloads.append(p)
    if len(payloads) > 1:
        write_cross_report(payloads, subs, plan)


if __name__ == "__main__":
    main()

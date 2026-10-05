#!/usr/bin/env python3
"""Benchmark de modelos LLM como verificadores unidad <-> sub-tematica CEPLAN.

Contexto: el cruce proyectos/publicaciones <-> sub-tematicas del PEDN 2050 usa
embeddings para proponer candidatas y un LLM para confirmar cada una con un
grado 0/1/2 (ver docs/cuantificacion_temas.md §8). Antes de pagar la corrida
completa (~1 000 unidades) se mide que modelo de Bedrock hace ese juicio igual
de bien que Claude Sonnet 5 por menos dinero.

Datos: salidas/topics/ceplan/benchmark/unidades.jsonl -- 80 unidades (40
proyectos, 40 publicaciones) estratificadas por su mejor similitud, cada una
con sus 5 sub-tematicas mas cercanas por embedding y el grado que les dio
Sonnet 5 en la calibracion (400 pares). El mismo prompt se repite tal cual
para cada modelo.

Subcomandos:
    gold    escribe gold_humano.csv: 100 pares (20 unidades) para etiquetar a
            mano, sin mostrar grados de modelos ni similitudes.
    run     corre los modelos (cache por modelo: lo ya respondido no se repaga).
    report  metricas contra Sonnet 5 (400 pares) y contra el gold humano (si ya
            esta etiquetado) -> reporte.md

    python scripts/analysis/ceplan_judge_benchmark.py gold
    python scripts/analysis/ceplan_judge_benchmark.py run
    python scripts/analysis/ceplan_judge_benchmark.py report
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import lb_aws     # noqa: E402
import lb_config  # noqa: E402

BENCH_DIR = ROOT / "salidas" / "topics" / "ceplan" / "benchmark"
UNITS_PATH = BENCH_DIR / "unidades.jsonl"
GOLD_PATH = BENCH_DIR / "gold_humano.csv"
ANSWERS_DIR = BENCH_DIR / "respuestas"

# Sonnet 5 es la referencia: sus grados ya estan en unidades.jsonl (no se
# vuelve a correr). Los demas se corren por la API Converse.
REFERENCE = "sonnet5"
MODELS = {
    "haiku45": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "nova_pro": "us.amazon.nova-pro-v1:0",
    "gpt_oss_120b": "openai.gpt-oss-120b-1:0",
    "qwen3_32b": "qwen.qwen3-32b-v1:0",
    "llama4_maverick": "us.meta.llama4-maverick-17b-instruct-v1:0",
    "glm47": "zai.glm-4.7",
}

# USD por millon de tokens (entrada, salida), on-demand en us-east-1, para el
# ID que se usa arriba (los perfiles "us." de Claude cobran la tarifa regional,
# 10% sobre la "global."). Fuente: lista publica de precios de AWS
# (pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock[FoundationModels]),
# publicada 2026-09-30 / 2026-10-03.
PRICES = {
    "sonnet5": (2.20, 11.00),
    "haiku45": (1.10, 5.50),
    "nova_pro": (0.80, 3.20),
    "gpt_oss_120b": (0.15, 0.60),
    "qwen3_32b": (0.15, 0.60),
    "llama4_maverick": (0.24, 0.97),
    "glm47": (0.60, 2.20),
}

# Mismo prompt que la calibracion con Sonnet 5 (no cambiar: los grados de la
# referencia se obtuvieron con este texto exacto).
SYSTEM = (
    "Evaluas si una investigacion universitaria peruana desarrolla o aporta a una sub-tematica "
    "del Plan Estrategico de Desarrollo Nacional (PEDN 2050, CEPLAN). Para cada sub-tematica "
    "responde 2 = la investigacion la desarrolla claramente o aporta conocimiento directamente "
    "util para ella; 1 = relacion tangencial o indirecta; 0 = sin relacion real. Responde SOLO "
    "un arreglo JSON de enteros, uno por sub-tematica, en orden.")
MAX_TEXT_CHARS = 3000


def load_units():
    return [json.loads(line) for line in UNITS_PATH.open(encoding="utf-8")]


def build_user(unit):
    subs = [f"{n + 1}. {s['subtema']} (tematica: {s['tema']}; {s['on_label'][:60]})"
            for n, s in enumerate(unit["subs"])]
    return (f"INVESTIGACION:\n{unit['text'][:MAX_TEXT_CHARS]}\n\nSUB-TEMATICAS:\n"
            + "\n".join(subs))


def parse_grades(raw, expected):
    """Ultimo arreglo JSON de enteros 0-2 con el largo esperado, o None.

    Se toma el ultimo porque los modelos que razonan en texto (gpt-oss, Qwen3)
    a veces escriben arreglos de prueba antes de la respuesta final.
    """
    for match in reversed(re.findall(r"\[[\s\d,]*\]", raw or "")):
        try:
            values = json.loads(match)
        except json.JSONDecodeError:
            continue
        if len(values) == expected and all(v in (0, 1, 2) for v in values):
            return values
    return None


# --------------------------------------------------------------------------
# gold
# --------------------------------------------------------------------------

def cmd_gold(_args):
    units = load_units()
    rng = random.Random(11)
    picked = []
    for domain in ("projects", "publications_linked"):
        pool = sorted((u for u in units if u["domain"] == domain),
                      key=lambda u: max(s["sim"] for s in u["subs"]))
        # 10 unidades repartidas a lo largo del rango de similitud
        step = len(pool) / 10
        picked += [pool[int(i * step + rng.random() * step)] for i in range(10)]
    rng.shuffle(picked)
    if GOLD_PATH.exists():
        raise SystemExit(f"{GOLD_PATH.relative_to(ROOT)} ya existe: no se sobrescribe "
                         "(podria tener etiquetas). Borrarlo a mano si se quiere regenerar.")
    with GOLD_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["par_id", "tipo", "titulo", "texto", "sub_tematica", "tematica",
                         "objetivo_nacional", "grado_0_1_2", "comentario"])
        for unit in picked:
            subs = list(unit["subs"])
            rng.shuffle(subs)  # el orden original es el ranking por similitud: no filtrarlo
            for s in subs:
                writer.writerow([
                    f"{unit['domain']}|{unit['unit_id']}|{s['sub_id']}",
                    "proyecto" if unit["domain"] == "projects" else "publicacion",
                    unit["title"], unit["text"][:MAX_TEXT_CHARS], s["subtema"], s["tema"],
                    s["on_label"], "", ""])
    print(f"{len(picked) * 5} pares -> {GOLD_PATH.relative_to(ROOT)}")
    print("Criterio: 2 = la investigacion desarrolla claramente la sub-tematica o aporta "
          "conocimiento directamente util; 1 = relacion tangencial o indirecta; "
          "0 = sin relacion real.")


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------

def run_model(cfg, name, model_id, units):
    client = lb_aws.BedrockClient(cfg)
    path = ANSWERS_DIR / f"{name}.jsonl"
    done = set()
    if path.exists():
        done = {json.loads(line)["key"] for line in path.open(encoding="utf-8")}
    lock = threading.Lock()
    pending = [u for u in units if f"{u['domain']}|{u['unit_id']}" not in done]
    for unit in pending:
        key = f"{unit['domain']}|{unit['unit_id']}"
        error = None
        raw = ""
        try:
            raw = client.converse(SYSTEM, build_user(unit), model_id=model_id, max_tokens=4096)
            usage = dict(client.last_usage)
        except lb_aws.AwsNotConfigured:
            raise
        except Exception as exc:  # noqa: BLE001 -- se registra y se cuenta como fallo
            error = f"{type(exc).__name__}: {exc}"[:400]
            usage = {}
        grades = parse_grades(raw, len(unit["subs"]))
        with lock, path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"key": key, "grades": grades, "raw": raw[-600:],
                                     "error": error, **usage}, ensure_ascii=False) + "\n")
    print(f"  {name}: {len(pending)} llamadas nuevas, {len(done)} ya en cache")


def cmd_run(args):
    cfg = lb_config.load()
    units = load_units()
    ANSWERS_DIR.mkdir(parents=True, exist_ok=True)
    names = args.models or list(MODELS)
    # Verificacion de acceso con una llamada minima antes de lanzar todo.
    client = lb_aws.BedrockClient(cfg)
    for name in names:
        client.converse("Responde solo OK.", "OK", model_id=MODELS[name], max_tokens=200)
        print(f"  acceso ok: {name} ({MODELS[name]})")
    # Un hilo por modelo: cada uno tiene su propia cuota en Bedrock.
    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        futures = [pool.submit(run_model, cfg, n, MODELS[n], units) for n in names]
        for fut in futures:
            fut.result()


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def cohen_kappa(a, b, labels, weighted=False):
    """Kappa de Cohen; con ``weighted`` usa pesos lineales (0 vs 2 cuenta doble)."""
    n = len(a)
    if n == 0:
        return None
    k = len(labels)
    idx = {lab: i for i, lab in enumerate(labels)}

    def w(i, j):
        return abs(i - j) / (k - 1) if weighted else float(i != j)
    observed = sum(w(idx[x], idx[y]) for x, y in zip(a, b)) / n
    pa = [sum(1 for x in a if x == lab) / n for lab in labels]
    pb = [sum(1 for y in b if y == lab) / n for lab in labels]
    expected = sum(pa[i] * pb[j] * w(i, j) for i in range(k) for j in range(k))
    return 1 - observed / expected if expected > 0 else None


def compare(pred, truth):
    """pred/truth: listas paralelas de grados 0-2."""
    pb = [int(p >= 1) for p in pred]
    tb = [int(t >= 1) for t in truth]
    tp = sum(1 for p, t in zip(pb, tb) if p and t)
    prec = tp / max(sum(pb), 1)
    rec = tp / max(sum(tb), 1)
    return {
        "n": len(pred),
        "acc_bin": sum(1 for p, t in zip(pb, tb) if p == t) / max(len(pred), 1),
        "f1_rel": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
        "kappa_bin": cohen_kappa(pb, tb, [0, 1]),
        "kappa_w3": cohen_kappa(pred, truth, [0, 1, 2], weighted=True),
        "rate_rel": sum(pb) / max(len(pred), 1),
    }


def load_gold():
    if not GOLD_PATH.exists():
        return {}
    gold = {}
    with GOLD_PATH.open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            value = (row.get("grado_0_1_2") or "").strip()
            if value in ("0", "1", "2"):
                gold[row["par_id"]] = int(value)
    return gold


def fmt(x, pct=False):
    if x is None:
        return "—"
    return f"{x * 100:.1f}%" if pct else f"{x:.3f}"


def cost(name, tokens_in, tokens_out, units=1000):
    pin, pout = PRICES[name]
    return units * (tokens_in * pin + tokens_out * pout) / 1e6


def cmd_report(_args):
    units = load_units()
    gold = load_gold()
    # grados por par para cada modelo: {modelo: {par_id: grado}}
    preds = {REFERENCE: {}}
    for u in units:
        for s in u["subs"]:
            preds[REFERENCE][f"{u['domain']}|{u['unit_id']}|{s['sub_id']}"] = s["sonnet5"]
    ops = {}
    for name in MODELS:
        path = ANSWERS_DIR / f"{name}.jsonl"
        if not path.exists():
            continue
        by_key = {u["domain"] + "|" + u["unit_id"]: u for u in units}
        preds[name] = {}
        rows = [json.loads(line) for line in path.open(encoding="utf-8")]
        fails = 0
        tin, tout, lat = [], [], []
        for r in rows:
            unit = by_key[r["key"]]
            if r.get("input_tokens"):
                tin.append(r["input_tokens"])
                tout.append(r["output_tokens"])
                lat.append(r["latency"])
            if r["grades"] is None:
                fails += 1
                continue
            for s, g in zip(unit["subs"], r["grades"]):
                preds[name][f"{r['key']}|{s['sub_id']}"] = g
        lat.sort()
        ops[name] = {"units": len(rows), "fails": fails,
                     "in": sum(tin) / max(len(tin), 1), "out": sum(tout) / max(len(tout), 1),
                     "lat_p50": lat[len(lat) // 2] if lat else None}

    lines = ["# Benchmark: LLM como verificador unidad ↔ sub-temática CEPLAN", "",
             f"Datos: {len(units)} unidades × 5 sub-temáticas = "
             f"{sum(len(u['subs']) for u in units)} pares (`unidades.jsonl`). "
             f"Referencia: Sonnet 5 (`{REFERENCE}`). Gold humano: {len(gold)} pares etiquetados.",
             "", "Métricas binarias: 'relacionado' = grado ≥ 1. κ_w3 = kappa de Cohen con "
             "pesos lineales sobre 0/1/2.", ""]

    lines += ["## Operación", "",
              "| Modelo | Bedrock ID | unidades | respuestas inválidas | tokens in / out (media) | latencia p50 | USD por 1 000 unidades |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for name, o in ops.items():
        lines.append(f"| {name} | `{MODELS[name]}` | {o['units']} | {o['fails']} "
                     f"({o['fails'] / max(o['units'], 1) * 100:.1f}%) | "
                     f"{o['in']:.0f} / {o['out']:.0f} | "
                     f"{o['lat_p50']:.1f}s | {cost(name, o['in'], o['out']):.2f} |"
                     if o["lat_p50"] is not None else
                     f"| {name} | `{MODELS[name]}` | {o['units']} | {o['fails']} | — | — |")

    # Sonnet 5 no paso por este script (sus grados vienen de la calibracion), asi
    # que su costo se estima con los tokens de entrada medidos de Haiku 4.5 y
    # ~100 tokens de salida.
    if "haiku45" in ops:
        lines.append(f"| {REFERENCE} (estimado) | `us.anthropic.claude-sonnet-5` | — | — | "
                     f"~{ops['haiku45']['in']:.0f} / ~100 | — | "
                     f"~{cost(REFERENCE, ops['haiku45']['in'], 100):.2f} |")
    lines += ["", "Precios: lista pública de AWS (on-demand, us-east-1), ver `PRICES`.", ""]

    def table(title, truth, models):
        out = [f"## {title}", "",
               "| Modelo | n | acierto rel/no | F1 rel | κ binario | κ_w3 | % marcado rel |",
               "|---|---:|---:|---:|---:|---:|---:|"]
        for name in models:
            keys = [k for k in truth if k in preds.get(name, {})]
            m = compare([preds[name][k] for k in keys], [truth[k] for k in keys])
            out.append(f"| {name} | {m['n']} | {fmt(m['acc_bin'], True)} | {fmt(m['f1_rel'])} | "
                       f"{fmt(m['kappa_bin'])} | {fmt(m['kappa_w3'])} | {fmt(m['rate_rel'], True)} |")
        truth_rate = sum(1 for v in truth.values() if v >= 1) / max(len(truth), 1)
        out += ["", f"Tasa de 'relacionado' en la referencia: {truth_rate * 100:.1f}%.", ""]
        return out

    lines.append("")
    lines += table("Contra Sonnet 5 (400 pares)", preds[REFERENCE],
                   [n for n in MODELS if n in preds])
    if gold:
        lines += table(f"Contra el gold humano ({len(gold)} pares)", gold,
                       [REFERENCE] + [n for n in MODELS if n in preds])
        lines += ["Con ~100 pares, diferencias de κ menores a ~0.1 están dentro del ruido.", ""]
    else:
        lines += ["## Contra el gold humano", "",
                  f"Pendiente: `{GOLD_PATH.relative_to(ROOT)}` aún no tiene etiquetas.", ""]

    report = BENCH_DIR / "reporte.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n-> {report.relative_to(ROOT)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gold")
    run = sub.add_parser("run")
    run.add_argument("--models", nargs="*", choices=list(MODELS))
    sub.add_parser("report")
    args = parser.parse_args()
    {"gold": cmd_gold, "run": cmd_run, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Mapa fijo de la investigacion y posicion de los retos de cada plan.

Responde, en la pestaña «Mapa» del atlas, «¿que esta priorizando este conjunto
de retos?»: un mapa 2D de todos los proyectos y publicaciones (PUCP y ECOTEC),
dividido en sectores tematicos, sobre el que cae cada reto del plan elegido.

El mapa es FIJO: se ajusta una vez y se guarda; los retos se colocan encima
sin moverlo. Asi un plan nuevo (la enciclica) no cambia la posicion de nada y
los planes se pueden comparar en el mismo espacio. Por eso tres pasos, cada
uno donde puede correr:

  export  (servidor) embeddings y temas de las unidades de las corridas
          publicadas (salidas/topics/atlas/datasets.json)
          -> salidas/topics/mapa/unidades.npz + unidades.json
  fit     (una sola vez, donde haya scikit-learn: el servidor no lo tiene)
          t-SNE coseno con semilla fija -> coordenadas de cada unidad;
          k-means sobre el plano -> sectores contiguos; nombre de cada sector
          = sus temas normalizados (etapa 04) de mayor peso
          -> salidas/topics/mapa/mapa_base.json  (EL mapa; copiar al servidor)
  name    (servidor, una vez tras fit) el LLM da a cada sector un nombre amplio
          a partir de sus temas y titulos (una sola llamada con todos, para
          que no se repitan); el nombre por tema queda en name_topic
  place  (servidor, solo numpy; lo llama rebuild_atlas.sh) cada hoja de cada
          plan va al promedio, ponderado por similitud, de la posicion de sus
          K unidades mas parecidas (max es/en, como el cruce). Una hoja que no
          supera el piso con ninguna unidad queda marcada «lejos de toda la
          investigacion». -> salidas/topics/atlas/data/mapa.json

Por que vecinos y no proyectar el texto de la hoja: el mapa sale de resumenes
largos y las hojas son textos cortos; proyectarlas directo las deja donde el
modelo no aprendio nada (Matsui et al. 2022). Con vecinos, un reto queda donde
esta la investigacion que mas se le parece.

    python3 scripts/analysis/research_map.py export          # servidor
    scp servidor:LibroBlanco/salidas/topics/mapa/unidades.* salidas/topics/mapa/
    python scripts/analysis/research_map.py fit              # local, una vez
    scp salidas/topics/mapa/mapa_base.json servidor:LibroBlanco/salidas/topics/mapa/
    python3 scripts/analysis/research_map.py name            # servidor, una vez
    python3 scripts/analysis/research_map.py place           # servidor
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

MAP_DIR = ROOT / "salidas" / "topics" / "mapa"
UNITS_NPZ = MAP_DIR / "unidades.npz"
UNITS_JSON = MAP_DIR / "unidades.json"
BASE = MAP_DIR / "mapa_base.json"
MANIFEST = ROOT / "salidas" / "topics" / "atlas" / "datasets.json"
OUT = ROOT / "salidas" / "topics" / "atlas" / "data" / "mapa.json"

SEED = 2026
N_SECTORS = 12
PERPLEXITY = 30
K_NEIGHBOURS = 15
TOPICS_PER_UNIT = 5


def manifest_runs() -> list[tuple[str, str, str]]:
    """[(dataset, dominio, corrida)] de lo publicado ahora."""
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return [(d["id"], dom, run) for d in data["datasets"] for dom, run in d["runs"].items()]


def unit_key(domain: str, unit_id: str) -> str:
    return f"{domain}/{unit_id}"


# --------------------------------------------------------------------------
# export (servidor)
# --------------------------------------------------------------------------

def cmd_export(_args):
    import lb_config
    import lb_store
    cfg = lb_config.load()
    ids, vectors, meta = [], [], []
    for dataset, domain, run in manifest_runs():
        store = lb_store.open_store(cfg, domain, run)
        units = {u["unit_id"]: u for u in store.read_units()}
        labels = {t["topic_id"]: t["label"] for t in store.read_topics()}
        topics = defaultdict(list)
        for m in store.read_membership():
            topics[m["unit_id"]].append((labels.get(m["topic_id"], m["topic_id"]), float(m["containment"])))
        n = 0
        for e in store.read_unit_embeddings():
            uid = e["unit_id"]
            if uid not in units:
                continue
            ids.append(unit_key(domain, uid))
            vectors.append(np.asarray(e["embedding"], dtype=np.float32))
            top = sorted(topics.get(uid, []), key=lambda t: -t[1])[:TOPICS_PER_UNIT]
            meta.append({"id": unit_key(domain, uid), "dataset": dataset, "domain": domain, "run": run,
                         "title": units[uid].get("title", ""), "topics": [[l, round(c, 4)] for l, c in top]})
            n += 1
        print(f"  {dataset:7s} {domain:22s} {run:32s} {n:5d} unidades")
    emb = np.vstack(vectors)
    emb /= np.linalg.norm(emb, axis=1, keepdims=True)
    MAP_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(UNITS_NPZ, ids=np.array(ids), emb=emb)
    UNITS_JSON.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"-> {UNITS_NPZ.relative_to(ROOT)} ({emb.shape[0]} x {emb.shape[1]}) y {UNITS_JSON.name}")


# --------------------------------------------------------------------------
# fit (una vez, con scikit-learn)
# --------------------------------------------------------------------------

def convex_hull(points: np.ndarray) -> list[list[float]]:
    """Envolvente convexa (cadena monotona de Andrew), sin scipy."""
    pts = sorted(map(tuple, points.tolist()))
    if len(pts) <= 2:
        return [list(p) for p in pts]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return [[round(x, 4), round(y, 4)] for x, y in lower[:-1] + upper[:-1]]


def sector_topics(members: list[dict], n: int = 6) -> list[list]:
    """Temas de mas peso en un sector: suma de la contencion de sus unidades."""
    weight = defaultdict(float)
    for m in members:
        for label, c in m["topics"]:
            weight[label] += c
    total = sum(weight.values()) or 1.0
    return [[label, round(w / total, 3)] for label, w in
            sorted(weight.items(), key=lambda kv: -kv[1])[:n]]


def cmd_fit(args):
    from sklearn.cluster import KMeans
    from sklearn.manifold import TSNE
    import sklearn
    data = np.load(UNITS_NPZ)
    ids, emb = [str(x) for x in data["ids"]], data["emb"]
    meta = {m["id"]: m for m in json.loads(UNITS_JSON.read_text(encoding="utf-8"))}
    print(f"t-SNE de {len(ids)} unidades (perplejidad {args.perplexity}, semilla {SEED})...")
    xy = TSNE(n_components=2, metric="cosine", init="pca", perplexity=args.perplexity,
              random_state=SEED).fit_transform(emb.astype(np.float64))
    xy = (xy - xy.min(axis=0)) / (xy.max(axis=0) - xy.min(axis=0))   # 0..1
    km = KMeans(n_clusters=args.sectors, n_init=20, random_state=SEED).fit(xy)
    labels = km.labels_
    sectors = []
    for s in range(args.sectors):
        idx = np.where(labels == s)[0]
        members = [meta[ids[i]] for i in idx]
        topics = sector_topics(members)
        by_ds = defaultdict(int)
        for m in members:
            by_ds[m["dataset"]] += 1
        sectors.append({"id": int(s), "name": topics[0][0] if topics else f"Sector {s + 1}",
                        "topics": topics, "n": int(len(idx)), "by_dataset": dict(by_ds),
                        "cx": round(float(xy[idx, 0].mean()), 4), "cy": round(float(xy[idx, 1].mean()), 4),
                        "hull": convex_hull(xy[idx])})
    base = {"version": date.today().isoformat(),
            "params": {"method": "t-SNE (coseno) + k-means sobre el plano", "perplexity": args.perplexity,
                       "sectors": args.sectors, "seed": SEED, "sklearn": sklearn.__version__},
            "runs": sorted({(m["dataset"], m["domain"], m["run"]) for m in meta.values()}),
            "units": {ids[i]: [round(float(xy[i, 0]), 4), round(float(xy[i, 1]), 4), int(labels[i])]
                      for i in range(len(ids))},
            "sectors": sectors}
    BASE.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
    print(f"-> {BASE.relative_to(ROOT)}: {len(ids)} unidades, {args.sectors} sectores")
    for s in sorted(sectors, key=lambda s: -s["n"]):
        print(f"   {s['id']:2d} {s['n']:5d}  {s['name'][:50]:50s} | " +
              "; ".join(t[0][:28] for t in s["topics"][1:4]))


# --------------------------------------------------------------------------
# name (servidor, LLM): un nombre amplio por sector
# --------------------------------------------------------------------------

NAME_SYSTEM = """Nombras las areas de un mapa de la investigacion de dos universidades \
(PUCP, Peru; ECOTEC, Ecuador). Cada area agrupa proyectos y publicaciones cercanos; para cada \
una recibes sus temas de mas peso y algunos titulos. Da a cada area un nombre amplio de 2 a 5 \
palabras en espanol, al nivel de un area del conocimiento (p.ej. «Física y materiales», \
«Historia y sociedad andina»), no el de un tema puntual. Los nombres deben ser distintos entre \
si. Responde SOLO un arreglo JSON de strings, uno por area, en el orden recibido."""


def cmd_name(_args):
    import random
    import lb_aws
    import lb_config
    base = json.loads(BASE.read_text(encoding="utf-8"))
    meta = json.loads(UNITS_JSON.read_text(encoding="utf-8"))
    by_sector = defaultdict(list)
    for m in meta:
        if m["id"] in base["units"]:
            by_sector[base["units"][m["id"]][2]].append(m)
    rng = random.Random(SEED)
    blocks = []
    for s in base["sectors"]:
        members = by_sector[s["id"]]
        topics = sector_topics(members, n=10)
        titles = [m["title"][:110] for m in rng.sample(members, min(8, len(members)))]
        blocks.append(f"AREA {s['id'] + 1} ({len(members)} unidades)\nTemas: " +
                      "; ".join(t[0] for t in topics) + "\nTitulos: " + " | ".join(titles))
    raw = lb_aws.llm_client(lb_config.load()).complete(NAME_SYSTEM, "\n\n".join(blocks), max_tokens=2000)
    names = json.loads(raw[raw.find("["):raw.rfind("]") + 1])
    if len(names) != len(base["sectors"]):
        raise SystemExit(f"El LLM devolvio {len(names)} nombres para {len(base['sectors'])} sectores: {raw[:300]}")
    for s, name in zip(base["sectors"], names):
        s["name_topic"] = s.get("name_topic", s["name"])
        s["name"] = name.strip()
        print(f"   {s['id']:2d} {s['name']:40s} <- {s['name_topic'][:50]}")
    BASE.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
    print(f"-> {BASE.relative_to(ROOT)}: nombres de sector actualizados")


# --------------------------------------------------------------------------
# place (servidor, numpy)
# --------------------------------------------------------------------------

def place_leaves(sims: np.ndarray, xy: np.ndarray, sector: np.ndarray, floor: float,
                 k: int = K_NEIGHBOURS) -> list[dict]:
    """sims: [hojas x unidades]. Cada hoja al promedio de la posicion de sus k
    unidades mas parecidas, con peso (sim - piso); si ninguna llega al piso,
    peso uniforme y `far`."""
    out = []
    n_sectors = int(sector.max()) + 1
    for row in sims:
        top = np.argsort(-row)[:k]
        w = np.clip(row[top] - floor, 0, None)
        far = not w.any()
        if far:
            w = np.ones_like(w)
        w = w / w.sum()
        x, y = (xy[top] * w[:, None]).sum(axis=0)
        share = np.bincount(sector[top], weights=w, minlength=n_sectors)
        out.append({"x": round(float(x), 4), "y": round(float(y), 4), "s": int(share.argmax()),
                    "sim": round(float(row[top[0]]), 3), "far": bool(far), "top": top[:3].tolist()})
    return out


def cmd_place(_args):
    import lb_config
    import lb_plans
    import ceplan_units
    import atlas_profiles
    cfg = lb_config.load()
    base = json.loads(BASE.read_text(encoding="utf-8"))
    data = np.load(UNITS_NPZ)
    ids, emb = [str(x) for x in data["ids"]], data["emb"]
    keep = [i for i, u in enumerate(ids) if u in base["units"]]
    if len(keep) < len(ids):
        print(f"  aviso: {len(ids) - len(keep)} unidades exportadas no estan en el mapa base "
              "(corridas nuevas: volver a correr fit para incluirlas)")
    ids = [ids[i] for i in keep]
    emb = emb[keep]
    xy = np.array([base["units"][u][:2] for u in ids])
    sector = np.array([base["units"][u][2] for u in ids])
    meta = {m["id"]: m for m in json.loads(UNITS_JSON.read_text(encoding="utf-8"))}
    floor = float(cfg.get("ceplan.floor", 0.40))

    plans = {}
    for key, plan in lb_plans.PLANS.items():
        try:
            leaves, es, en = ceplan_units.load_taxonomy(cfg, plan)
        except FileNotFoundError as exc:
            print(f"  {key}: sin hojas ({exc}); se omite")
            continue
        sims = np.maximum(emb @ es.T, emb @ en.T).T          # [hojas x unidades]
        placed = place_leaves(sims, xy, sector, floor)
        prof = atlas_profiles.PLANS.get(key, {})
        plans[key] = {
            "name": prof.get("name", plan.name), "short": prof.get("short", plan.name),
            "leaf": plan.leaf, "leaves": plan.leaves, "level1": plan.level1_long,
            "l1": {l["on"]: l["on_label"] for l in leaves},
            "retos": [{"id": l["id"], "l": l["label"], "o": l["on"], "t": l["tema"], **p,
                       "near": [meta[ids[i]]["title"][:120] for i in p.pop("top")]}
                      for l, p in zip(leaves, placed)]}
        far = sum(r["far"] for r in plans[key]["retos"])
        print(f"  {key:12s} {len(leaves):4d} hojas colocadas ({far} lejos de toda la investigacion)")
    # Las unidades van compactas: x, y, sector, dataset (indice), dominio
    # (indice) e id de la unidad en su dominio. Con dominio e id, la pagina
    # resalta el universo elegido y las unidades vinculadas a un reto.
    datasets = sorted({meta[u]["dataset"] for u in ids})
    domains = sorted({meta[u]["domain"] for u in ids})
    payload = {"version": base["version"], "params": {**base["params"], "k": K_NEIGHBOURS, "floor": floor},
               "datasets": datasets, "domains": domains,
               "sectors": [{k: s[k] for k in ("id", "name", "topics", "n", "by_dataset", "cx", "cy", "hull")}
                           for s in base["sectors"]],
               "units": [[*base["units"][u][:3], datasets.index(meta[u]["dataset"]),
                          domains.index(meta[u]["domain"]), u.split("/", 1)[1]] for u in ids],
               "plans": plans}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"-> {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e6:.2f} MB)")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("export").set_defaults(fn=cmd_export)
    fit = sub.add_parser("fit")
    fit.add_argument("--sectors", type=int, default=N_SECTORS)
    fit.add_argument("--perplexity", type=float, default=PERPLEXITY)
    fit.set_defaults(fn=cmd_fit)
    sub.add_parser("name").set_defaults(fn=cmd_name)
    sub.add_parser("place").set_defaults(fn=cmd_place)
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

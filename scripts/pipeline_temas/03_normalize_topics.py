#!/usr/bin/env python3
"""Etapa 03 — agrupa los temas extraidos en temas normalizados del dominio.

Tres pasos:
  1. Embeber cada tema extraido ("tema. descripcion") con Bedrock.
  2. Agruparlos con lb_cluster (lider-seguidor + fusion de centroides).
  3. Pedirle al LLM un nombre y una descripcion para cada grupo, a partir de
     sus miembros. Ese es el "tema normalizado".

Tambien embebe el texto completo de cada unidad, porque la etapa 04 lo necesita
para la afinidad por similitud (modos "embedding" e "hybrid").

IMPORTANTE: el espacio de temas es por dominio. Este script nunca mezcla
proyectos con publicaciones; correrlo dos veces produce dos conjuntos de temas
independientes, que es lo que pidio el equipo.

    python scripts/pipeline_temas/03_normalize_topics.py --domain projects
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _stage import REPO_ROOT, StageContext, base_parser, main_wrapper  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
import lb_aws      # noqa: E402
import lb_cluster  # noqa: E402

NAMING_SYSTEM = """\
Eres un analista que pone nombre a agrupaciones de temas de investigación.

Recibes una lista de temas extraídos que un algoritmo agrupó por similitud
semántica. Tu tarea es darle al grupo un nombre y una descripción que cubran a
sus miembros, sin ser tan genéricos que sirvan para cualquier grupo.

Devuelve SOLO JSON válido: {"label": str, "description": str}
- "label": 4 a 12 palabras, en español, específico al contenido del grupo.
- "description": una o dos oraciones que delimiten qué entra y qué no.
- Si el grupo es heterogéneo, nombra el eje que de verdad comparten sus
  miembros en vez de inventar una categoría que los cubra a la fuerza.
"""


def slugify(text: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:60]
    return slug or fallback


def name_cluster(client, members) -> dict:
    listing = "\n".join(
        f"- {m['topic']}: {m.get('description', '')}" for m in members[:40])
    user = (f"Temas del grupo ({len(members)} en total, se muestran hasta 40):\n{listing}")
    raw = client.complete(NAMING_SYSTEM, user)
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json")
    start, end = text.find("{"), text.rfind("}")
    if start == -1:
        return {"label": members[0]["topic"], "description": ""}
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {"label": members[0]["topic"], "description": ""}
    return {"label": data.get("label") or members[0]["topic"],
            "description": data.get("description", "")}


@main_wrapper
def main():
    parser = base_parser(__doc__)
    parser.add_argument("--cluster-threshold", type=float, default=None,
                        help="Coseno minimo para entrar en un grupo existente. "
                             "Por defecto se calibra sobre la distribucion real "
                             "de similitudes (cada modelo usa un rango distinto).")
    parser.add_argument("--merge-threshold", type=float, default=None,
                        help="Coseno minimo para fusionar dos grupos. "
                             "Por defecto, calibrado sobre los datos.")
    parser.add_argument("--target-topics", type=int, default=None,
                        help="Numero objetivo de temas normalizados. Por defecto "
                             "topics.target_topics de la configuracion.")
    parser.add_argument("--no-naming", action="store_true",
                        help="No llama al LLM para nombrar; usa el tema mas frecuente.")
    args = parser.parse_args()

    with StageContext(args, "03_normalize_topics") as ctx:
        extracted = ctx.store.read_extracted_topics()
        units = ctx.store.read_units()
        target = (args.target_topics if args.target_topics is not None
                  else ctx.cfg.get("topics.target_topics"))
        # target <= 0 significa "sin objetivo": el numero de temas lo decide el
        # umbral calibrado y no se fuerza ninguna fusion por debajo de el.
        # Forzar un objetivo bajo (p.ej. 49 sobre 1.928 temas extraidos) obliga
        # a aceptar fusiones de similitud 0.525 contra un umbral de 0.636, y
        # produce grupos de 303 miembros que ya no son un tema.
        if target is not None and int(target) <= 0:
            target = None
        print(f"  temas extraidos={len(extracted):,}  unidades={len(units):,}  "
              f"objetivo de temas={target if target is not None else 'sin objetivo (solo umbral)'}")

        if args.dry_run:
            chars = (sum(len(e["topic"]) + len(e.get("description", "")) for e in extracted)
                     + sum(len(u["text"]) for u in units))
            print(f"  --dry-run: se embeberian {len(extracted) + len(units):,} textos "
                  f"({chars:,} caracteres).")
            return

        embedder = lb_aws.embedding_client(ctx.cfg, ctx.stage)

        # 1. Embeddings de los temas extraidos
        topic_texts = [f"{e['topic']}. {e.get('description', '')}".strip()
                       for e in extracted]
        print(f"  embebiendo {len(topic_texts):,} temas extraidos...")
        topic_matrix = lb_cluster.normalize_rows(embedder.embed(topic_texts))

        items = [{"id": index, "vector": topic_matrix[index],
                  "weight": float(extracted[index].get("confidence", 0))}
                 for index in range(topic_matrix.shape[0])]

        # 2. Agrupamiento
        clusters = lb_cluster.cluster_topics(
            items, threshold=args.cluster_threshold,
            merge_threshold=args.merge_threshold, target=target,
            matrix=topic_matrix)
        diag = clusters[0].pop("_diagnostics", {}) if clusters else {}
        if diag:
            print(f"  umbrales: lider={diag['leader_threshold']:.3f} "
                  f"fusion={diag['merge_threshold']:.3f}"
                  + (f"  (similitud del corpus: mediana={diag['p50']:.3f} "
                     f"p90={diag['p90']:.3f})" if "p50" in diag else ""))
            ctx.stage.notes["clustering"] = diag
        print(f"  grupos formados={len(clusters)}")

        # 3. Nombre por grupo
        client = lb_aws.llm_client(ctx.cfg, ctx.stage)
        topics, topic_map, used_slugs = [], [], set()
        for index, cluster in enumerate(clusters):
            members = [extracted[i] for i in cluster["member_indices"]]
            members.sort(key=lambda m: -float(m.get("confidence", 0)))
            if args.no_naming:
                named = {"label": members[0]["topic"], "description": members[0].get("description", "")}
            else:
                named = name_cluster(client, members)
            slug = slugify(named["label"], f"tema-{index:03d}")
            while slug in used_slugs:
                slug = f"{slug}-{index}"
            used_slugs.add(slug)
            topics.append({
                "topic_id": slug,
                "label": named["label"],
                "description": named["description"],
                "num_variants": len(members),
                "centroid": cluster["centroid"],
                # trazabilidad: los temas extraidos que cayeron aqui
                "variants": sorted({m["topic"] for m in members}),
            })
            for member_index in cluster["member_indices"]:
                topic_map.append({
                    "extracted_index": member_index,
                    "unit_id": extracted[member_index]["unit_id"],
                    "topic_id": slug,
                    "similarity": lb_cluster.cosine(topic_matrix[member_index],
                                                    cluster["centroid"]),
                })
            if (index + 1) % 10 == 0:
                print(f"  nombrados {index + 1}/{len(clusters)}")

        # 4. Embeddings de las unidades (los necesita la etapa 04).
        # Si ya hay embeddings para este run_id -- p.ej. seeded desde una
        # corrida anterior con seed_from_run.py, porque el texto de la unidad
        # no cambio, solo el universo -- se reusan sin volver a llamar a
        # Bedrock. Solo se embeben las unidades que de verdad falten.
        existing = {r["unit_id"]: r["embedding"] for r in ctx.store.read_unit_embeddings()}
        missing = [u for u in units if u["unit_id"] not in existing]
        if missing:
            reused = len(units) - len(missing)
            print(f"  embebiendo {len(missing):,} unidades"
                  + (f" ({reused:,} reusadas del store, sin llamar a Bedrock)" if reused else "")
                  + "...")
            missing_matrix = lb_cluster.normalize_rows(embedder.embed([u["text"] for u in missing]))
            for i, u in enumerate(missing):
                existing[u["unit_id"]] = missing_matrix[i]
        else:
            print(f"  {len(units):,} unidades ya tenian embedding en el store "
                  "(reusadas, 0 llamadas a Bedrock).")
        unit_embeddings = [{"unit_id": u["unit_id"], "embedding": existing[u["unit_id"]]}
                           for u in units]

        ctx.stage.units_processed = len(units)
        ctx.store.write_topics(topics)
        ctx.store.write_topic_map(topic_map)
        ctx.store.write_unit_embeddings(unit_embeddings)
        sizes = sorted((t["num_variants"] for t in topics), reverse=True)
        print(f"  temas normalizados={len(topics)}  "
              f"tamano: max={sizes[0]} mediana={sizes[len(sizes)//2]} min={sizes[-1]}")

        if ctx.s3.enabled:
            ctx.s3.put_json(ctx.s3.run_key(ctx.run_id, "03_topics.json"),
                            [{k: v for k, v in t.items() if k != "centroid"} for t in topics])


if __name__ == "__main__":
    main()

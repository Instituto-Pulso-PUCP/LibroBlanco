#!/usr/bin/env python3
"""Contrasts the normalized research topics (projects + publications) against
Peru's official national policy corpus, completing the pending step described
in docs/topic_normalization_pipeline.md ("Para agregar el contraste con un
objetivo (ODS / CEPLAN)"): once an "objetivo" text is available, embed it
alongside normalized_topics and produce a 0-1 compatibility index.

The objective text is now available at
``datos/corpus_politicas_chunks.jsonl``: 30,963 page-level chunks from Peru's
Politicas Nacionales (PN), Planes Estrategicos Sectoriales Multianuales
(PESEM), the Plan Estrategico de Desarrollo Nacional (PEDN), CEPLAN foresight
documents, CONCYTEC strategy documents, and Programas Presupuestales (PP) —
946 distinct documents in total.

Approach:
1. Embed every policy chunk once (cached to disk — this is the expensive
   step) and mean-pool chunk embeddings per ``doc_id`` to get one vector per
   policy document (946 vectors).
2. Embed every normalized topic (name + description) — projects' final
   consolidated set (49) and publications' current set (352).
3. Cosine similarity (embeddings are L2-normalized, so this is a dot
   product) between every topic and every policy document.
4. For each topic, keep the top-K policy documents by score, and for each of
   those, the single best-matching individual chunk as textual evidence.

Usage::

    python scripts/analysis/build_topic_policy_alignment.py
    python scripts/analysis/build_topic_policy_alignment.py --model minilm-multilingual --top-k 5
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))

from embeddings import EMBEDDING_MODELS, compute_embeddings  # noqa: E402

ROOT = SCRIPTS_DIR.parent
POLICY_CORPUS_PATH = ROOT / "datos" / "corpus_politicas_chunks.jsonl"
PROJECTS_TOPICS_PATH = ROOT / "salidas" / "topics" / "projects_topics_consolidated.json"
PUBLICATIONS_TOPICS_PATH = ROOT / "salidas" / "topics" / "publications_topics_current.json"
CACHE_DIR = ROOT / "salidas" / "topics" / "policy_alignment_cache"
OUT_DIR = ROOT / "salidas" / "topics"

FUENTE_LABELS = {
    "PN": "Politica Nacional",
    "PESEM": "Plan Estrategico Sectorial Multianual",
    "PEDN": "Plan Estrategico de Desarrollo Nacional",
    "CEPLAN": "Tendencia / megatendencia CEPLAN",
    "CONCYTEC": "Documento estrategico CONCYTEC",
    "PP": "Programa Presupuestal",
}


def load_policy_chunks():
    chunks = []
    with open(POLICY_CORPUS_PATH, encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))
    return chunks


def load_topics():
    """Returns a flat list of {topic_id, source, normalized_topic, description,
    count, project_ids, embed_text}."""
    topics = []

    with open(PROJECTS_TOPICS_PATH, encoding="utf-8") as f:
        proj = json.load(f)
    for i, t in enumerate(proj["normalized_topics"]):
        topics.append({
            "topic_id": f"proj_{i:03d}",
            "source": "proyectos",
            "normalized_topic": t["normalized_topic"],
            "description": t["description"],
            "count": t.get("count"),
            "project_ids": t.get("project_ids", []),
            "embed_text": f"{t['normalized_topic']}. {t['description']}",
        })

    with open(PUBLICATIONS_TOPICS_PATH, encoding="utf-8") as f:
        pub = json.load(f)
    for i, t in enumerate(pub["normalized_topics"]):
        topics.append({
            "topic_id": f"pub_{i:03d}",
            "source": "publicaciones",
            "normalized_topic": t["normalized_topic"],
            "description": t["description"],
            "count": t.get("count"),
            "project_ids": t.get("project_ids", []),
            "embed_text": f"{t['normalized_topic']}. {t['description']}",
        })

    return topics


def get_chunk_embeddings(chunks, model_key):
    """Embeds every policy chunk, cached to disk since this is the expensive step."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"chunk_embeddings_{model_key}.npy"
    if cache_path.exists():
        print(f"Usando cache de embeddings de chunks: {cache_path}")
        return np.load(cache_path)

    texts = [c["texto"] for c in chunks]
    config = EMBEDDING_MODELS[model_key]
    if config["method"] != "sentence-transformers":
        # tfidf and similar are cheap/instant; checkpointing isn't needed.
        print(f"Calculando embeddings para {len(texts)} chunks de politicas ({model_key})...")
        embeddings, metadata = compute_embeddings(texts, model_key)
        np.save(cache_path, embeddings)
        print(f"Embeddings guardados en cache: {cache_path} ({metadata})")
        return embeddings

    embeddings = _embed_with_checkpoints(texts, model_key, config, group_size=1000)
    np.save(cache_path, embeddings)
    print(f"Embeddings guardados en cache: {cache_path}")
    return embeddings


def _embed_with_checkpoints(texts, model_key, config, group_size=1000):
    """Encodes ``texts`` in groups, saving each group's embeddings to disk as
    soon as it finishes, so a killed/interrupted run resumes from the last
    completed group instead of starting over. Groups are ~5-15 min each for
    slow models on CPU, so at most one group's work is ever lost."""
    from sentence_transformers import SentenceTransformer

    parts_dir = CACHE_DIR / f"chunk_embeddings_{model_key}_parts"
    parts_dir.mkdir(parents=True, exist_ok=True)

    n_groups = (len(texts) + group_size - 1) // group_size
    done_parts = sorted(parts_dir.glob("part*.npy"))
    n_done = len(done_parts)
    if n_done:
        print(f"Reanudando: {n_done}/{n_groups} grupos ya calculados en {parts_dir}")

    if n_done < n_groups:
        model_kwargs = dict(config.get("model_kwargs") or {})
        if "device" not in model_kwargs:
            import torch
            model_kwargs["device"] = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Cargando {model_key} en device={model_kwargs['device']}...")
        model = SentenceTransformer(config["model_name"], **model_kwargs)
        if model_kwargs["device"] == "cuda":
            # Cap sequence length: covers 99.9% of policy chunks with zero
            # truncation (p99.9 = 7884 chars ~ under 2048 tokens) while
            # keeping the rare 26k-char outlier chunks from spiking VRAM
            # past this GPU's 4GB (confirmed via OOM before this cap).
            model.max_seq_length = min(model.max_seq_length or 2048, 2048)
        text_prefix = config.get("text_prefix", "")
        encode_kwargs = dict(config.get("encode_kwargs") or {})
        encode_kwargs.setdefault("normalize_embeddings", True)
        if model_kwargs["device"] == "cuda":
            encode_kwargs.setdefault("batch_size", 16)

        for g in range(n_done, n_groups):
            start, end = g * group_size, min((g + 1) * group_size, len(texts))
            group_texts = texts[start:end]
            if text_prefix:
                group_texts = [f"{text_prefix}{t}" for t in group_texts]
            print(f"Grupo {g + 1}/{n_groups} ({start}:{end})...")
            group_emb = model.encode(
                group_texts, show_progress_bar=True, convert_to_numpy=True, **encode_kwargs,
            )
            np.save(parts_dir / f"part{g:05d}.npy", group_emb)

    parts = [np.load(p) for p in sorted(parts_dir.glob("part*.npy"))]
    return np.concatenate(parts, axis=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="minilm-multilingual",
                         help="Embedding model key from scripts/lib/embeddings.py registry")
    parser.add_argument("--top-k", type=int, default=5,
                         help="Numero de politicas mejor alineadas a guardar por tema")
    args = parser.parse_args()

    chunks = load_policy_chunks()
    print(f"{len(chunks)} chunks de politicas cargados de {POLICY_CORPUS_PATH.name}")

    topics = load_topics()
    print(f"{len(topics)} temas normalizados cargados "
          f"({sum(1 for t in topics if t['source']=='proyectos')} proyectos, "
          f"{sum(1 for t in topics if t['source']=='publicaciones')} publicaciones)")

    chunk_embeddings = get_chunk_embeddings(chunks, args.model)

    topic_texts = [t["embed_text"] for t in topics]
    topic_embeddings, topic_meta = compute_embeddings(topic_texts, args.model)
    print(f"Embeddings de temas calculados: {topic_meta}")

    # Group chunk indices by doc_id, keep doc-level metadata, mean-pool embeddings.
    doc_chunk_idx = defaultdict(list)
    doc_info = {}
    for i, c in enumerate(chunks):
        doc_chunk_idx[c["doc_id"]].append(i)
        doc_info[c["doc_id"]] = {"fuente": c["fuente"], "titulo": c["titulo"]}

    doc_ids = sorted(doc_chunk_idx.keys())
    doc_embeddings = np.zeros((len(doc_ids), chunk_embeddings.shape[1]), dtype=np.float32)
    for d, doc_id in enumerate(doc_ids):
        idxs = doc_chunk_idx[doc_id]
        vec = chunk_embeddings[idxs].mean(axis=0)
        norm = np.linalg.norm(vec)
        doc_embeddings[d] = vec / norm if norm > 0 else vec
    print(f"{len(doc_ids)} documentos de politica (agregados desde {len(chunks)} chunks)")

    # topics (N) x policy docs (M) cosine similarity (embeddings already L2-normalized).
    sim_topic_doc = topic_embeddings @ doc_embeddings.T

    topic_results = []
    policy_topic_hits = defaultdict(list)  # doc_id -> [{topic_id, score}]

    for ti, topic in enumerate(topics):
        scores = sim_topic_doc[ti]
        top_idx = np.argsort(-scores)[: args.top_k]

        matches = []
        for di in top_idx:
            doc_id = doc_ids[di]
            score = float(scores[di])
            chunk_idxs = doc_chunk_idx[doc_id]
            chunk_scores = chunk_embeddings[chunk_idxs] @ topic_embeddings[ti]
            best_local = int(np.argmax(chunk_scores))
            best_chunk = chunks[chunk_idxs[best_local]]

            matches.append({
                "doc_id": doc_id,
                "fuente": doc_info[doc_id]["fuente"],
                "fuente_label": FUENTE_LABELS.get(doc_info[doc_id]["fuente"], doc_info[doc_id]["fuente"]),
                "titulo": doc_info[doc_id]["titulo"],
                "score": round(score, 4),
                "evidence_chunk_id": best_chunk["chunk_id"],
                "evidence_paginas": best_chunk.get("paginas"),
                "evidence_text": best_chunk["texto"][:600],
            })
            policy_topic_hits[doc_id].append({
                "topic_id": topic["topic_id"],
                "source": topic["source"],
                "normalized_topic": topic["normalized_topic"],
                "score": round(score, 4),
            })

        topic_results.append({
            "topic_id": topic["topic_id"],
            "source": topic["source"],
            "normalized_topic": topic["normalized_topic"],
            "description": topic["description"],
            "count": topic["count"],
            "top_policy_matches": matches,
        })

    policy_results = []
    for doc_id in doc_ids:
        hits = sorted(policy_topic_hits.get(doc_id, []), key=lambda h: -h["score"])
        policy_results.append({
            "doc_id": doc_id,
            "fuente": doc_info[doc_id]["fuente"],
            "fuente_label": FUENTE_LABELS.get(doc_info[doc_id]["fuente"], doc_info[doc_id]["fuente"]),
            "titulo": doc_info[doc_id]["titulo"],
            "n_chunks": len(doc_chunk_idx[doc_id]),
            "top_topic_matches": hits[: args.top_k],
        })

    data = {
        "metadata": {
            "title": "Alineacion entre temas de investigacion PUCP y politicas nacionales del Peru",
            "embedding_model": args.model,
            "num_topics": len(topics),
            "num_topics_proyectos": sum(1 for t in topics if t["source"] == "proyectos"),
            "num_topics_publicaciones": sum(1 for t in topics if t["source"] == "publicaciones"),
            "num_policy_docs": len(doc_ids),
            "num_policy_chunks": len(chunks),
            "source_files": {
                "proyectos": str(PROJECTS_TOPICS_PATH.relative_to(ROOT)),
                "publicaciones": str(PUBLICATIONS_TOPICS_PATH.relative_to(ROOT)),
                "politicas": str(POLICY_CORPUS_PATH.relative_to(ROOT)),
            },
            "note": (
                "Indice de compatibilidad 0-1 (similitud coseno de embeddings) entre "
                "cada tema normalizado y cada documento de politica publica peruana. "
                "Los documentos de politica se agregan por promedio de embeddings de "
                "sus paginas/chunks; la evidencia textual mostrada es el chunk "
                "individual con mayor similitud al tema dentro de ese documento."
            ),
        },
        "topics": topic_results,
        "policies": policy_results,
    }

    out_path = OUT_DIR / f"topic_policy_alignment_{args.model}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"OK: {len(topics)} temas x {len(doc_ids)} politicas -> {out_path}")


if __name__ == "__main__":
    main()

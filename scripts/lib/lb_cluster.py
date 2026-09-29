"""Agrupamiento de temas extraidos en temas normalizados.

Todo el trabajo vectorial va sobre una unica matriz ``numpy`` float32 de forma
(N, dim). La version anterior guardaba cada vector como lista de float de
Python: ~33 bytes por numero en vez de 4, lo que para las ~49.000 vectores de
publicaciones (35k temas extraidos + 14k unidades) suponia ~1,6 GB en una
maquina de 1,8 GB -- moria por falta de memoria a mitad de la etapa 03,
despues de haber pagado las 14.000 llamadas de extraccion.

float32 no pierde precision util aqui: pgvector almacena `vector` en float32,
asi que los embeddings ya vienen redondeados a esa precision desde la base.
El error del coseno entre vectores unitarios en float32 es del orden de 1e-7,
seis ordenes de magnitud por debajo de la separacion entre umbrales (~0,01).

Dos pasadas:

  1. **Lider-seguidor (canopy)**: recorre los temas ordenados por confianza y
     abre un grupo nuevo cuando ninguno de los lideres existentes lo alcanza.
     Coste O(N*G), una multiplicacion matriz-vector por elemento.
  2. **Enlace promedio (average linkage)**: fusiona los grupos cuya similitud
     media entre miembros supera el umbral. Para vectores unitarios esa
     similitud es exactamente el producto punto de las medias SIN normalizar
     (ver ``mean_vector``), asi que se calcula con una sola matriz G x G que se
     actualiza por filas en cada fusion.
"""

from __future__ import annotations

import math

import numpy as np

DTYPE = np.float32


# ---------------------------------------------------------------------------
# Utilidades de vector
# ---------------------------------------------------------------------------

def as_matrix(vectors) -> np.ndarray:
    """Lista de vectores -> matriz (N, dim) float32 contigua."""
    if isinstance(vectors, np.ndarray):
        return np.ascontiguousarray(vectors, dtype=DTYPE)
    return np.ascontiguousarray(np.asarray(vectors, dtype=DTYPE))


def normalize(vector):
    """Normaliza a norma 1. Acepta y devuelve lista o array segun lo que entre."""
    arr = np.asarray(vector, dtype=DTYPE)
    norm = float(np.linalg.norm(arr))
    if norm == 0:
        return vector if isinstance(vector, np.ndarray) else list(vector)
    out = arr / norm
    return out if isinstance(vector, np.ndarray) else out.tolist()


def normalize_rows(matrix: np.ndarray) -> np.ndarray:
    """Normaliza cada fila a norma 1, dejando en paz las filas nulas."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    np.maximum(norms, 1e-12, out=norms)
    return (matrix / norms).astype(DTYPE, copy=False)


def cosine(a, b) -> float:
    """Coseno de dos vectores YA normalizados (producto punto)."""
    return float(np.dot(np.asarray(a, dtype=DTYPE), np.asarray(b, dtype=DTYPE)))


def mean_vector(vectors):
    """Media aritmetica SIN normalizar.

    Es el criterio de enlace entre grupos: para vectores unitarios, el producto
    punto de dos medias sin normalizar es *exactamente* la similitud coseno
    media entre todos los pares de miembros de ambos grupos (average linkage):

        (1/|A||B|) * sum_a sum_b  a·b  =  (sum_a a / |A|) · (sum_b b / |B|)

    Normalizar la media rompe esa igualdad y produce un efecto de arrastre: la
    media normalizada de un grupo grande se parece cada vez mas a todo lo
    demas, cada fusion vuelve mas probable la siguiente y el agrupamiento
    colapsa en un grupo gigante (observado: 78 temas -> 4 grupos, el mayor 75).
    """
    matrix = as_matrix(vectors)
    if matrix.size == 0:
        return []
    out = matrix.mean(axis=0)
    return out if isinstance(vectors, np.ndarray) else out.tolist()


def centroid(vectors):
    """Media normalizada: para GUARDAR el tema y compararlo contra unidades."""
    return normalize(mean_vector(vectors))


# ---------------------------------------------------------------------------
# Paso 1: lider-seguidor
# ---------------------------------------------------------------------------

def leader_cluster(items, threshold=0.62, max_clusters=None, matrix=None):
    """``items``: [{'id', 'vector' (normalizado), 'weight'}] -> [[indices]].

    Se recorre de mayor a menor peso para que los lideres sean los temas con
    mas confianza, no los que llegaron primero.
    """
    if not items:
        return []
    if matrix is None:
        matrix = as_matrix([it["vector"] for it in items])
    order = sorted(range(len(items)), key=lambda i: -items[i].get("weight", 0.0))

    dim = matrix.shape[1]
    # Buffer de lideres preasignado; se amplia al doble cuando hace falta.
    leaders = np.empty((max(16, len(items) // 8), dim), dtype=DTYPE)
    count = 0
    groups: list[list[int]] = []

    for index in order:
        vector = matrix[index]
        if count:
            # una sola matriz-vector contra todos los lideres actuales
            sims = leaders[:count] @ vector
            best = int(np.argmax(sims))
            best_score = float(sims[best])
        else:
            best, best_score = -1, -1.0
        if best_score >= threshold or (max_clusters and count >= max_clusters):
            groups[best].append(index)
        else:
            if count == leaders.shape[0]:
                leaders = np.resize(leaders, (leaders.shape[0] * 2, dim))
            leaders[count] = vector
            count += 1
            groups.append([index])
    return groups


# ---------------------------------------------------------------------------
# Paso 2: fusion por enlace promedio
# ---------------------------------------------------------------------------

def merge_close(items, groups, threshold=0.70, target=None, max_passes=None,
                matrix=None):
    """Fusiona grupos por enlace promedio hasta el umbral (o hasta ``target``).

    Mantiene una matriz G x G de similitudes entre medias sin normalizar y solo
    recalcula la fila/columna del grupo fusionado, en vez de rehacerla entera
    en cada pasada: O(G^2) total en lugar de O(G^3).
    """
    if not groups:
        return [], []
    if matrix is None:
        matrix = as_matrix([it["vector"] for it in items])
    means = np.stack([matrix[g].mean(axis=0) for g in groups]).astype(DTYPE)
    sims = means @ means.T
    np.fill_diagonal(sims, -np.inf)          # nunca fusionar un grupo consigo mismo
    alive = np.ones(len(groups), dtype=bool)
    groups = [list(g) for g in groups]
    remaining = len(groups)
    if max_passes is None:
        max_passes = max(remaining - 1, 0)

    for _ in range(max_passes):
        if remaining <= 1 or (target is not None and remaining <= target):
            break
        flat = int(np.argmax(sims))
        a, b = divmod(flat, sims.shape[1])
        best_score = float(sims[a, b])
        forced = target is not None and remaining > target
        if not np.isfinite(best_score) or (best_score < threshold and not forced):
            break

        groups[a] = groups[a] + groups[b]
        groups[b] = []
        alive[b] = False
        remaining -= 1
        means[a] = matrix[groups[a]].mean(axis=0)
        # recalcular solo la fila/columna de 'a', y retirar 'b' del juego
        row = means[a] @ means.T
        row[~alive] = -np.inf
        row[a] = -np.inf
        sims[a, :] = row
        sims[:, a] = row
        sims[b, :] = -np.inf
        sims[:, b] = -np.inf

    survivors = [g for g in groups if g]
    centroids = [normalize(matrix[g].mean(axis=0)).tolist() for g in survivors]
    return survivors, centroids


# ---------------------------------------------------------------------------
# Calibracion
# ---------------------------------------------------------------------------

def calibrate_thresholds(items, sample=2000, seed=0, matrix=None):
    """Deriva los umbrales de la distribucion real de similitudes.

    Cada modelo de embeddings usa un rango distinto (ver EXPERIMENTS.md: unos
    comprimen todo hacia arriba y otros usan la escala baja), asi que un umbral
    fijo no es portable entre modelos ni entre datasets. "Parecido" se define
    como lo que destaca sobre el fondo de este corpus, no como un numero
    absoluto.

    Devuelve (umbral_lider, umbral_fusion, diagnostico).
    """
    n = len(items)
    if n < 3:
        return 0.62, 0.70, {}
    rng = np.random.default_rng(seed)
    if matrix is None:
        matrix = as_matrix([it["vector"] for it in items])
    pairs = min(sample * 10, n * (n - 1) // 2)
    left = rng.integers(0, n, size=pairs)
    right = rng.integers(0, n, size=pairs)
    keep = left != right
    if not keep.any():
        return 0.62, 0.70, {}
    left, right = left[keep], right[keep]
    # Por bloques: matrix[left] completo serian decenas de MB de copia solo
    # para estimar unos percentiles.
    chunks = []
    for start in range(0, left.size, 4096):
        sl = slice(start, start + 4096)
        chunks.append(np.einsum("ij,ij->i", matrix[left[sl]], matrix[right[sl]]))
    sims = np.concatenate(chunks) if chunks else np.zeros(0, dtype=DTYPE)
    leader, merge = (float(x) for x in np.quantile(sims, [0.95, 0.99]))
    return leader, merge, {
        "pairs_sampled": int(sims.size),
        "min": float(sims.min()), "max": float(sims.max()),
        "p50": float(np.quantile(sims, 0.50)),
        "p90": float(np.quantile(sims, 0.90)),
        "p95": leader, "p99": merge,
        "leader_threshold": leader, "merge_threshold": merge,
    }


def cluster_topics(items, threshold=None, merge_threshold=None, target=None,
                   matrix=None):
    """Pipeline completo. Devuelve [{'members', 'member_indices', 'centroid'}].

    Con los umbrales en None se calibran sobre los datos. ``matrix`` permite
    pasar los vectores ya apilados y evitar una copia completa (a escala de
    publicaciones, 143 MB).
    """
    # Una sola copia de los vectores para todo el pipeline: a escala de
    # publicaciones cada copia son ~143 MB y la maquina deja ~350 MB libres.
    if matrix is None:
        matrix = as_matrix([it["vector"] for it in items]) if items else None

    diagnostics = {}
    if threshold is None or merge_threshold is None:
        auto_leader, auto_merge, diagnostics = calibrate_thresholds(items, matrix=matrix)
        threshold = auto_leader if threshold is None else threshold
        merge_threshold = auto_merge if merge_threshold is None else merge_threshold

    groups = leader_cluster(items, threshold, matrix=matrix)
    groups, centroids = merge_close(items, groups, merge_threshold, target, matrix=matrix)
    order = sorted(range(len(groups)), key=lambda i: -len(groups[i]))
    result = [{"members": [items[j]["id"] for j in groups[i]],
               "member_indices": groups[i],
               "centroid": centroids[i]} for i in order]
    if result:
        result[0]["_diagnostics"] = dict(
            diagnostics, leader_threshold=threshold, merge_threshold=merge_threshold)
    return result


def similarity_matrix(unit_vectors, topic_centroids, top_k=None):
    """Similitud unidad <-> centroide de tema, en filas dispersas.

    ``unit_vectors``: {unit_id: vector normalizado}
    ``topic_centroids``: {topic_id: centroide normalizado}
    Devuelve [{'unit_id', 'topic_id', 'score'}], que es lo que consume
    ``lb_membership.affinity_from_similarity``.

    Se calcula por bloques de unidades: la matriz completa (14k x 49) cabe de
    sobra, pero el troceado mantiene el pico de memoria acotado si algun dia
    crece el numero de temas.
    """
    unit_ids = list(unit_vectors)
    topic_ids = list(topic_centroids)
    if not unit_ids or not topic_ids:
        return []
    centroids = as_matrix([topic_centroids[t] for t in topic_ids])
    rows = []
    block = 2048
    for start in range(0, len(unit_ids), block):
        chunk_ids = unit_ids[start:start + block]
        chunk = as_matrix([unit_vectors[u] for u in chunk_ids])
        scores = chunk @ centroids.T
        if top_k and top_k < len(topic_ids):
            idx = np.argpartition(-scores, top_k - 1, axis=1)[:, :top_k]
        else:
            idx = np.tile(np.arange(len(topic_ids)), (len(chunk_ids), 1))
        for i, unit_id in enumerate(chunk_ids):
            for j in idx[i]:
                rows.append({"unit_id": unit_id, "topic_id": topic_ids[j],
                             "score": float(scores[i, j])})
    return rows

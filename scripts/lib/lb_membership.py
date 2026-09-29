"""Cuantificacion bidireccional proyecto/publicacion <-> tema.

Responde las dos preguntas que pidio el equipo, sobre la MISMA matriz de
afinidad, cambiando solo la direccion de la normalizacion:

  1. "Cuanto del Proyecto 1 es del Tema 1"  -> CONTENCION  (filas suman 1)
  2. "Cuanto del Tema 1 lo aporta el Proyecto 1" -> CONTRIBUCION (columnas suman 1)

Nota sobre el "coeficiente de particion" que sugirio el profesor
-----------------------------------------------------------------
El *partition coefficient* de Bezdek NO es la cuantificacion por celda: es un
indice de validez del conjunto de la particion difusa,
``PC = (1/N) * sum_d sum_t u[d,t]^2``, que vale 1 si cada unidad pertenece a un
solo tema y 1/T si pertenece por igual a todos. Lo que responde las dos
preguntas es la propia matriz de pertenencia difusa ``u`` (aqui: CONTENCION).
Por eso este modulo calcula ambas cosas y las reporta por separado:

  - la matriz (contencion / contribucion)  -> el dato que se muestra;
  - PC, PE y sus versiones normalizadas    -> que tan nitida o difusa es la
    particion completa, para poder decir si la asignacion tema-proyecto es
    informativa o esta repartida entre todos los temas.

Identidades utiles (se verifican en ``validate``):
    sum_t C[d,t] = 1              cada unidad aporta 1 "unidad-equivalente"
    sum_d C[d,t] = E[t]           tamano del tema en unidades-equivalentes
    sum_t E[t]   = N              las unidades-equivalentes se conservan
    K[d,t]       = C[d,t] / E[t]  contribucion = contencion / tamano del tema

Implementacion en stdlib puro y dispersa (dict de (unit, topic) -> peso): el
servidor de produccion tiene 1 GB de RAM y no hay numpy/pandas instalados, y
la matriz densa de publicaciones (14k x ~350) no hace falta materializarla.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# Pesos por debajo de esto se tratan como cero (ruido numerico de los modelos).
EPSILON = 1e-12


@dataclass
class Quantification:
    """Resultado completo de la cuantificacion bidireccional."""

    unit_ids: list[str]
    topic_ids: list[str]
    # (unit_id, topic_id) -> valor
    affinity: dict[tuple[str, str], float]
    containment: dict[tuple[str, str], float]
    contribution: dict[tuple[str, str], float]
    # topic_id -> unidades-equivalentes (sum_d C[d,t])
    topic_equivalents: dict[str, float]
    unit_metrics: dict[str, dict] = field(default_factory=dict)
    topic_metrics: dict[str, dict] = field(default_factory=dict)
    partition_metrics: dict = field(default_factory=dict)
    # unidades sin ninguna afinidad > 0: no entran en la particion
    unassigned_units: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# Construccion de la matriz de afinidad (tres fuentes de peso)
# --------------------------------------------------------------------------

def affinity_from_extraction(extractions, confidence_key="confidence"):
    """Peso = masa de confianza de los temas extraidos por el LLM.

    ``extractions``: iterable de dicts con ``unit_id``, ``topic_id`` y la
    confianza del tema extraido. Si una unidad tuvo varios temas extraidos que
    cayeron en el mismo tema normalizado, sus confianzas se suman (una unidad
    que menciona un tema tres veces pesa mas en ese tema que la que lo menciona
    una vez).

    Matriz dispersa y explicable: cada celda > 0 tiene evidencia textual detras.
    Su limite es que una unidad toca tipicamente 2-4 temas, asi que la
    contencion es casi cruda (0.5 / 0.3 / 0.2) y no distingue afinidades debiles.
    """
    weights: dict[tuple[str, str], float] = {}
    for row in extractions:
        unit_id = str(row["unit_id"])
        topic_id = str(row["topic_id"])
        conf = float(row.get(confidence_key) or 0.0)
        if conf <= 0:
            continue
        key = (unit_id, topic_id)
        weights[key] = weights.get(key, 0.0) + conf
    return weights


def affinity_from_similarity(similarities, top_k=None, floor=0.0, power=1.0):
    """Peso = similitud coseno unidad <-> centroide del tema, recortada.

    ``similarities``: iterable de dicts con ``unit_id``, ``topic_id``, ``score``.

    Densa y con gradacion fina, pero sin evidencia textual, y sensible a la
    calibracion del modelo de embeddings (ver EXPERIMENTS.md: jina-v5-nano
    comprime todos los scores hacia arriba en comparaciones cross-dominio).
    Por eso se recorta antes de normalizar:

      - ``floor``: similitudes por debajo del piso se descartan (no hay
        "0.3 de pertenencia" solo porque el coseno nunca baja de 0.3);
      - ``top_k``: se conservan los k temas mas cercanos por unidad;
      - ``power``: exponente > 1 agudiza la distribucion (1.0 = sin cambio).

    Sin recorte, la contencion tenderia a 1/T para todas las unidades y el
    coeficiente de particion caeria a su minimo: informacion cero.
    """
    by_unit: dict[str, list[tuple[str, float]]] = {}
    for row in similarities:
        score = float(row.get("score") or 0.0)
        if score <= floor:
            continue
        by_unit.setdefault(str(row["unit_id"]), []).append((str(row["topic_id"]), score))

    weights: dict[tuple[str, str], float] = {}
    for unit_id, pairs in by_unit.items():
        pairs.sort(key=lambda p: p[1], reverse=True)
        if top_k:
            pairs = pairs[:top_k]
        for topic_id, score in pairs:
            weights[(unit_id, topic_id)] = (score - floor) ** power
    return weights


def blend_affinities(primary, secondary, alpha=0.7):
    """Mezcla dos matrices de afinidad normalizando cada una por fila primero.

    Sin la normalizacion previa la mezcla no significaria nada: la masa de
    confianza del LLM (0-1 por tema, 2-4 temas) y la similitud coseno recortada
    viven en escalas distintas. Se normaliza cada fuente a "perfil de la unidad"
    y recien ahi se promedia con peso ``alpha`` para la primaria.
    """
    prim = row_normalize(primary)
    sec = row_normalize(secondary)
    out: dict[tuple[str, str], float] = {}
    for key, value in prim.items():
        out[key] = alpha * value
    for key, value in sec.items():
        out[key] = out.get(key, 0.0) + (1.0 - alpha) * value
    return out


def row_normalize(weights):
    """Normaliza por unidad (fila) para que cada fila sume 1."""
    totals: dict[str, float] = {}
    for (unit_id, _topic_id), value in weights.items():
        totals[unit_id] = totals.get(unit_id, 0.0) + value
    out = {}
    for (unit_id, topic_id), value in weights.items():
        total = totals.get(unit_id, 0.0)
        if total > EPSILON:
            out[(unit_id, topic_id)] = value / total
    return out


# --------------------------------------------------------------------------
# Cuantificacion
# --------------------------------------------------------------------------

def quantify(affinity, unit_ids=None, topic_ids=None, contribution_mode="share"):
    """Calcula contencion, contribucion e indices de particion.

    ``contribution_mode``:
      - ``"share"`` (por defecto): la contribucion se calcula sobre la
        contencion, de modo que cada unidad aporta como mucho 1 unidad-
        equivalente repartida entre sus temas. "El tema 1 es 12% del proyecto A"
        significa entonces 12% de las unidades-equivalentes del tema. Es la
        opcion simetrica: ninguna unidad pesa mas por haber tenido mas texto o
        mas temas extraidos.
      - ``"mass"``: la contribucion se calcula sobre la afinidad cruda, asi que
        una unidad con mas masa de confianza (mas temas, mas evidencia) aporta
        proporcionalmente mas al total del tema. Util si se quiere que un
        proyecto grande *deba* pesar mas, pero mezcla "cuanto del tema aporta"
        con "cuanto texto tenia el proyecto".
    """
    if contribution_mode not in ("share", "mass"):
        raise ValueError(f"contribution_mode invalido: {contribution_mode!r}")

    affinity = {k: v for k, v in affinity.items() if v > EPSILON}

    # Descartar celdas fuera del universo declarado. Sin esto, una fila
    # residual en el store (p.ej. un topic_map de una corrida anterior del
    # mismo run) entraria en la particion y los porcentajes se calcularian
    # sobre unidades que no pertenecen a este experimento.
    dropped_cells = 0
    if unit_ids is not None or topic_ids is not None:
        allowed_units = set(unit_ids) if unit_ids is not None else None
        allowed_topics = set(topic_ids) if topic_ids is not None else None
        kept = {}
        for (unit_id, topic_id), value in affinity.items():
            if allowed_units is not None and unit_id not in allowed_units:
                dropped_cells += 1
                continue
            if allowed_topics is not None and topic_id not in allowed_topics:
                dropped_cells += 1
                continue
            kept[(unit_id, topic_id)] = value
        affinity = kept

    observed_units = sorted({u for u, _ in affinity})
    observed_topics = sorted({t for _, t in affinity})
    unit_ids = list(unit_ids) if unit_ids is not None else observed_units
    topic_ids = list(topic_ids) if topic_ids is not None else observed_topics

    unit_set = set(unit_ids)
    unassigned = sorted(unit_set - set(observed_units))

    containment = row_normalize(affinity)

    # Tamano del tema en unidades-equivalentes: sum_d C[d,t].
    topic_equivalents: dict[str, float] = {t: 0.0 for t in topic_ids}
    for (_unit_id, topic_id), value in containment.items():
        topic_equivalents[topic_id] = topic_equivalents.get(topic_id, 0.0) + value

    if contribution_mode == "share":
        source, denominators = containment, topic_equivalents
    else:
        source = affinity
        denominators = {t: 0.0 for t in topic_ids}
        for (_unit_id, topic_id), value in affinity.items():
            denominators[topic_id] = denominators.get(topic_id, 0.0) + value

    contribution = {}
    for (unit_id, topic_id), value in source.items():
        denom = denominators.get(topic_id, 0.0)
        if denom > EPSILON:
            contribution[(unit_id, topic_id)] = value / denom

    result = Quantification(
        unit_ids=unit_ids,
        topic_ids=topic_ids,
        affinity=affinity,
        containment=containment,
        contribution=contribution,
        topic_equivalents=topic_equivalents,
        unassigned_units=unassigned,
        params={
            "contribution_mode": contribution_mode,
            "num_units": len(unit_ids),
            "num_topics": len(topic_ids),
            "num_units_assigned": len(observed_units),
            "num_unassigned": len(unassigned),
            "num_nonzero_cells": len(affinity),
            "density": (len(affinity) / (len(unit_ids) * len(topic_ids))
                        if unit_ids and topic_ids else 0.0),
            "cells_outside_universe_dropped": dropped_cells,
        },
    )
    result.unit_metrics = _unit_metrics(result)
    result.topic_metrics = _topic_metrics(result)
    result.partition_metrics = _partition_metrics(result)
    return result


def _by_unit(cells):
    out: dict[str, list[tuple[str, float]]] = {}
    for (unit_id, topic_id), value in cells.items():
        out.setdefault(unit_id, []).append((topic_id, value))
    return out


def _by_topic(cells):
    out: dict[str, list[tuple[str, float]]] = {}
    for (unit_id, topic_id), value in cells.items():
        out.setdefault(topic_id, []).append((unit_id, value))
    return out


def _concentration(pairs):
    """HHI, numero efectivo, entropia normalizada y lider de una distribucion.

    ``pairs``: [(id, share)] con shares que suman ~1.
    El "numero efectivo" (1/HHI, inverso de Simpson) es la lectura intuitiva:
    un proyecto con contencion {0.5, 0.3, 0.2} tiene 2.6 temas efectivos.
    """
    hhi = sum(v * v for _k, v in pairs)
    entropy = -sum(v * math.log(v) for _k, v in pairs if v > EPSILON)
    top_id, top_share = max(pairs, key=lambda p: p[1]) if pairs else (None, 0.0)
    return {
        "count": len(pairs),
        "herfindahl": hhi,
        "effective_count": (1.0 / hhi) if hhi > EPSILON else 0.0,
        "entropy": entropy,
        "entropy_normalized": (entropy / math.log(len(pairs))) if len(pairs) > 1 else 0.0,
        "top_id": top_id,
        "top_share": top_share,
    }


def _unit_metrics(result):
    metrics = {}
    for unit_id, pairs in _by_unit(result.containment).items():
        stats = _concentration(pairs)
        metrics[unit_id] = {
            "num_topics": stats["count"],
            "effective_topics": stats["effective_count"],
            "herfindahl": stats["herfindahl"],
            "entropy_normalized": stats["entropy_normalized"],
            "top_topic_id": stats["top_id"],
            "top_topic_containment": stats["top_share"],
            "affinity_mass": sum(v for (u, _t), v in result.affinity.items() if u == unit_id),
            "assigned": True,
        }
    for unit_id in result.unassigned_units:
        metrics[unit_id] = {
            "num_topics": 0, "effective_topics": 0.0, "herfindahl": 0.0,
            "entropy_normalized": 0.0, "top_topic_id": None,
            "top_topic_containment": 0.0, "affinity_mass": 0.0, "assigned": False,
        }
    return metrics


def _topic_metrics(result):
    total_equiv = sum(result.topic_equivalents.values())
    by_topic_contribution = _by_topic(result.contribution)
    by_topic_containment = _by_topic(result.containment)
    metrics = {}
    for topic_id in result.topic_ids:
        contrib_pairs = by_topic_contribution.get(topic_id, [])
        stats = _concentration(contrib_pairs) if contrib_pairs else _concentration([])
        equiv = result.topic_equivalents.get(topic_id, 0.0)
        metrics[topic_id] = {
            # cuantas unidades lo tocan aunque sea un poco
            "num_units": len(by_topic_containment.get(topic_id, [])),
            # tamano real del tema descontando que las unidades se reparten
            "units_equivalent": equiv,
            "share_of_corpus": (equiv / total_equiv) if total_equiv > EPSILON else 0.0,
            # si el tema lo sostienen muchas unidades o dos o tres
            "effective_units": stats["effective_count"],
            "herfindahl": stats["herfindahl"],
            "entropy_normalized": stats["entropy_normalized"],
            "top_unit_id": stats["top_id"],
            "top_unit_contribution": stats["top_share"],
        }
    return metrics


def _partition_metrics(result):
    """Indices de Bezdek sobre la contencion, y su espejo sobre la contribucion.

    PC en [1/T, 1]; PC_normalized en [0, 1] (normalizacion de Dunn/Backer) para
    que sea comparable entre corridas con distinto numero de temas -- sin eso,
    un PC de 0.45 con 49 temas y otro de 0.45 con 350 no dicen lo mismo.
    """
    num_units = len({u for u, _ in result.containment})
    num_topics = len(result.topic_ids)

    def indices(cells, n, k):
        if n == 0 or k < 2:
            return {"partition_coefficient": None, "partition_coefficient_normalized": None,
                    "partition_entropy": None, "partition_entropy_normalized": None}
        pc = sum(v * v for v in cells.values()) / n
        pe = -sum(v * math.log(v) for v in cells.values() if v > EPSILON) / n
        return {
            "partition_coefficient": pc,
            "partition_coefficient_normalized": (pc - 1.0 / k) / (1.0 - 1.0 / k),
            "partition_entropy": pe,
            "partition_entropy_normalized": pe / math.log(k),
        }

    unit_side = indices(result.containment, num_units, num_topics)
    topic_side = indices(result.contribution, num_topics, max(num_units, 1))

    return {
        # "que tan nitidamente cada unidad pertenece a un solo tema"
        "unit_side": unit_side,
        # "que tan concentrado esta cada tema en unas pocas unidades"
        "topic_side": topic_side,
        "mean_effective_topics_per_unit": _mean(
            m["effective_topics"] for m in result.unit_metrics.values() if m["assigned"]),
        "mean_effective_units_per_topic": _mean(
            m["effective_units"] for m in result.topic_metrics.values()),
        "num_units_in_partition": num_units,
        "num_topics_in_partition": num_topics,
    }


def _mean(values):
    values = list(values)
    return (sum(values) / len(values)) if values else 0.0


def validate(result, tolerance=1e-6):
    """Verifica las identidades del modulo. Devuelve lista de errores (vacia = ok)."""
    errors = []
    for unit_id, pairs in _by_unit(result.containment).items():
        total = sum(v for _t, v in pairs)
        if abs(total - 1.0) > tolerance:
            errors.append(f"contencion de {unit_id} suma {total:.9f}, no 1")
    for topic_id, pairs in _by_topic(result.contribution).items():
        total = sum(v for _u, v in pairs)
        if abs(total - 1.0) > tolerance:
            errors.append(f"contribucion del tema {topic_id} suma {total:.9f}, no 1")
    num_assigned = len({u for u, _ in result.containment})
    total_equiv = sum(result.topic_equivalents.values())
    if abs(total_equiv - num_assigned) > tolerance * max(num_assigned, 1):
        errors.append(
            f"unidades-equivalentes suman {total_equiv:.6f}, no {num_assigned}")
    return errors


def to_rows(result, min_containment=0.0):
    """Aplana el resultado a filas listas para RDS/CSV: una por celda no nula."""
    rows = []
    for key, containment in result.containment.items():
        if containment < min_containment:
            continue
        unit_id, topic_id = key
        rows.append({
            "unit_id": unit_id,
            "topic_id": topic_id,
            "affinity": result.affinity.get(key, 0.0),
            "containment": containment,
            "contribution": result.contribution.get(key, 0.0),
        })
    rows.sort(key=lambda r: (r["unit_id"], -r["containment"]))
    return rows

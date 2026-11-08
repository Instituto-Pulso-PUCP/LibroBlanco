"""Idioma del texto de cada unidad, para reportarlo.

Las unidades en ingles se conectan menos con el plan nacional que las en
espanol (PUCP publications_linked-20261018: 66,5 % con al menos un vinculo
claro frente a 93,7 %). Parte es el idioma: Cohere multilingual v3 puntua mas
bajo un texto en ingles contra uno en espanol. Pero comparar las unidades por
su traduccion al espanol se probo y se descarto (EXPERIMENTS.md §6.6): sube la
similitud, y los vinculos que agrega resultaron mucho menos precisos que los
que reemplaza en una validacion a mano. La mayor parte de la diferencia es de
contenido (las publicaciones en ingles son mas a menudo ciencia basica).

Por eso no se traduce nada: el embedding es siempre el del texto original, y
este modulo solo cuenta idiomas para que los reportes y el atlas lo digan.
"""
from __future__ import annotations

import re
from collections import Counter

_ES = set("de la que el en los del las por con una para es al se su sus como más este esta "
          "entre sobre".split())
_EN = set("the of and to in is for on with that by this are from as an be which we our "
          "their".split())


def detect(text: str) -> str:
    """'es', 'en', 'mixto' o '?' (muy poco texto para decidir), por palabras
    funcionales. Suficiente para separar espanol de ingles en resumenes; no
    distingue otros idiomas (caen en '?' o 'mixto')."""
    words = re.findall(r"[a-záéíóúñ]+", (text or "").lower())
    es, en = sum(w in _ES for w in words), sum(w in _EN for w in words)
    if es + en < 5:
        return "?"
    if es > 1.5 * en:
        return "es"
    if en > 1.5 * es:
        return "en"
    return "mixto"


def language_counts(texts) -> dict:
    return dict(Counter(detect(t) for t in texts))

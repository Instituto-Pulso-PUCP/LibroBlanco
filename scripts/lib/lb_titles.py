"""¿Dos titulos son la misma obra? Control compartido para emparejamientos por titulo.

Se usa donde un texto (abstract) llego por una busqueda por titulo y hay que
decidir si de verdad es de la obra declarada: la cascada de
`publications_linked` (scripts/addons/rebuild_linked_publications.py), el
texto auxiliar de `projects` (lb_domains) y la recuperacion externa de
abstracts (scripts/addons/recover_abstracts_external.py).

Historia (2026-10-10/11): la primera version media el solapamiento de palabras
sobre el titulo MAS CORTO, con piso 0.85. Eso acepta cualquier titulo corto
contenido en el otro aunque sea otra obra: "EPICICLOS" se quedaba con el
abstract de un articulo sobre Copernico y Kepler, y "La construccion de la
masculinidad entre jovenes universitarios..." con "Dilemas de la
masculinidad". Ahora el solapamiento cuenta solo palabras de contenido y
exige que el titulo corto tenga al menos MIN_CONTENT_WORDS y sea al menos
MIN_LENGTH_RATIO del largo; la similitud de secuencia sigue valiendo sola.
"""
from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENALEX_RAW = REPO_ROOT / "salidas" / "06_project_results_ground_truth_openalex_raw_payload.jsonl"

MIN_SEQUENCE = 0.85
MIN_OVERLAP = 0.85
MIN_CONTENT_WORDS = 3
MIN_LENGTH_RATIO = 0.5

_STOP = set("""
a al ante bajo con contra de del desde durante e el en entre hacia hasta la las lo los mediante
o para por segun sin sobre su sus tras u un una unas unos y
an and as at by for from in into of on or the to with
""".split())


def norm_title(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def _content_words(norm: str) -> list[str]:
    return [w for w in norm.split() if w not in _STOP and len(w) > 1]


def title_match(a: str, b: str) -> float:
    """Puntaje 0-1 de "misma obra". >= MIN_SEQUENCE (0.85) se acepta.

    Mayor entre (1) la similitud de secuencia de los titulos normalizados y
    (2) el solapamiento de palabras de contenido sobre el titulo mas corto,
    este ultimo solo si el corto tiene al menos MIN_CONTENT_WORDS palabras de
    contenido y al menos MIN_LENGTH_RATIO de las del largo (tolera subtitulos
    agregados, no titulos de una o dos palabras contenidos en otro).
    """
    na, nb = norm_title(a), norm_title(b)
    if not na or not nb:
        return 0.0
    seq = SequenceMatcher(None, na, nb).ratio()
    wa, wb = set(_content_words(na)), set(_content_words(nb))
    short, long_ = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    overlap = 0.0
    if len(short) >= MIN_CONTENT_WORDS and len(short) >= MIN_LENGTH_RATIO * len(long_):
        overlap = len(short & long_) / len(short)
    return max(seq, overlap)


def same_work(a: str, b: str) -> bool:
    return title_match(a, b) >= MIN_SEQUENCE


_OPENALEX_TITLES: dict | None = None


def openalex_titles() -> dict[tuple[str, str], str]:
    """(project_id, cod_prod) -> titulo de la obra OpenAlex emparejada (cacheado)."""
    global _OPENALEX_TITLES
    if _OPENALEX_TITLES is not None:
        return _OPENALEX_TITLES
    out = {}
    if OPENALEX_RAW.exists():
        with OPENALEX_RAW.open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                payload = row.get("openalex_raw_payload")
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except ValueError:
                        continue
                if isinstance(payload, dict) and payload.get("id"):
                    out[(str(row["project_id"]).strip(), str(row["cod_prod"]).strip())] = (
                        payload.get("title") or "")
    _OPENALEX_TITLES = out
    return out


def openalex_abstract_is_valid(row: dict, declared_title: str) -> bool:
    """El openalex_abstract de una fila de resultados es de la obra declarada.

    Por DOI vale siempre (los emparejados por DOI con titulo distinto eran la
    misma obra con el titulo traducido). Por titulo, solo si `same_work`. Sin
    el archivo de payloads no se puede verificar: se descarta.
    """
    doi = (row.get("doi_norm") or "").strip()
    if doi and doi != "-":
        return True
    key = (str(row.get("project_id", "")).strip(), str(row.get("cod_prod", "")).strip())
    return same_work(declared_title, openalex_titles().get(key, ""))

"""Textos del Atlas Temático que cambian de un dataset a otro.

build_atlas.py manda los numeros; la pagina (templates/atlas/)
tiene el texto comun a todos los datasets. Lo que depende de la institucion o
de su plan nacional -- titulo, nombre de cada universo, embudo de «Datos de
origen», vocabulario del plan, validacion del cruce -- se escribe aqui y viaja
en el archivo de datos de cada dataset, para que el selector de la pagina
cambie todo a la vez.

Anadir un dataset al atlas = una entrada en DATASETS (y en PLANS si trae un
plan nacional nuevo). Los niveles del plan (hoja, nivel 1) salen de
lb_plans.Plan; aqui solo va lo que el atlas necesita ademas.

Los textos de PUCP son exactamente los que la plantilla tenia escritos antes
de existir este modulo: la pagina publicada no cambia.
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Misma ruta para los dos datasets: el agente de LibreChat PUCP (ver
# uso_02_extract_topics.json de cada corrida, `gateway:agent_...`).
EXTRACTION_HTML = ("La extracción y el nombrado corren sobre <code>Claude Sonnet 5</code> a través de "
                   "LibreChat PUCP, con un agente sin instrucciones propias para que no se mezclen con las "
                   "del análisis.")
EXTRACTION_FOOTER = "Claude Sonnet 5 (LibreChat PUCP)"

# Nombre legible del verificador del cruce con el plan, por model_id.
MODEL_NAMES = {"us.meta.llama4-maverick-17b-instruct-v1:0": "Llama 4 Maverick"}

# Lo que el atlas dice del plan, ademas de lo que ya trae lb_plans.Plan.
# `source` lleva su preposicion: «Qué políticas del Plan...» / «de la hoja...».
# `validation` es la frase sobre la revision manual del cruce; None si el plan
# todavia no tiene una (la pagina lo dice en vez de mostrar cifras ajenas).
PLANS = {
    "pedn2050": {
        "name": "PEDN 2050", "short": "CEPLAN", "tab": "Objetivos Nacionales",
        "cross": "los Objetivos Nacionales", "level1_plural": "Objetivos Nacionales",
        "source": "de la hoja «Líneas de Inv.» del PEDN 2050",
        "validation": ("En una revisión manual de 130 vínculos, el 84 % tenía una relación real; una "
                       "calificación 2 indica una relación real con alta confianza (91 %), no "
                       "necesariamente que la sub-temática sea el centro de la unidad (53 %)."),
    },
    "pnd_ec_2025": {
        "name": "PND 2025-2029", "short": "PND", "tab": "Plan Nacional (PND)",
        "cross": "las políticas del PND", "level1_plural": "ejes",
        "source": "del Plan Nacional de Desarrollo 2025-2029 del Ecuador",
        "validation": ("Para este plan todavía no hay una revisión manual de los vínculos: no hay una "
                       "tasa de acierto medida y las calificaciones son las del verificador tal cual."),
    },
}


def es_int(n: int) -> str:
    """Como Number.toLocaleString('es'): separa miles solo desde 10.000."""
    return f"{n:,}".replace(",", ".") if n >= 10000 else str(n)


# --- Embudos de «Datos de origen» -------------------------------------------
# Cada funcion recibe las filas del CSV de origen (todas), las de la corrida y
# el numero de unidades, y devuelve {steps: [{n, label, note}], why}. label y
# note se insertan como HTML.

def _pucp_projects(raw_rows, rows, n_units):
    # Desde 2026-10-13 el universo parte de las filas de Proyectos CRIS
    # (scripts/addons/build_projects_from_cris.py), no de la hoja de PULSO.
    cris_files = sorted((ROOT / "datos").glob("ProyectosPUCPCRIS*.csv"))
    n_cris = None
    if cris_files:
        with cris_files[-1].open(encoding="utf-8-sig", newline="") as fh:
            csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
            n_cris = sum(1 for _ in csv.DictReader(fh))
    return {
        "steps": [
            {"n": n_cris or 1891, "label": "Proyectos registrados en CRIS",
             "note": "export " + (cris_files[-1].stem if cris_files else "de Proyectos CRIS")},
            # el CSV de origen ya viene con ese filtro aplicado
            {"n": len(raw_rows), "label": "Concluidos y con inicio desde 2010",
             "note": "estado «concluido» en CRIS; año de inicio de CRIS o, si falta, el de PULSO"},
            {"n": n_units, "label": "Tienen título y resumen de CRIS",
             "note": "un proyecto con solo título no alcanza para un análisis de texto serio"},
        ],
        "why": ("El universo lo definen los registros de CRIS y no la hoja de proyectos de "
                "PULSO. De PULSO se toman solo el código AERI."),
    }


def _pucp_publications_linked(raw_rows, rows, n_units):
    dup = len(rows) - n_units
    return {
        "steps": [
            {"n": len(raw_rows),
             "label": "Publicaciones que un proyecto del universo declaró como su resultado",
             "note": "archivo publications_linked_full"},
            {"n": len(rows), "label": "Tienen título y resumen",
             "note": ("una publicación con solo título no alcanza para un análisis de texto serio; "
                      "los resúmenes buscados por título se verifican contra el título declarado")},
            {"n": n_units, "label": "Publicaciones distintas tras quitar duplicados",
             "note": (es_int(dup) + " publicaciones estaban declaradas por más de un proyecto y se "
                      "cuentan una sola vez") if dup else "no había duplicados"},
        ],
        "why": "Solo entran las publicaciones que el propio proyecto declaró como resultado.",
    }


def _ecotec_projects(raw_rows, rows, n_units):
    lost = len(raw_rows) - n_units
    return {
        "steps": [
            {"n": len(raw_rows), "label": "Proyectos en el registro entregado por ECOTEC",
             "note": "archivo «DATASET 1- Registro de Proyectos»"},
            {"n": n_units, "label": "Tienen título y descripción",
             "note": (es_int(lost) + " sin texto quedaron fuera") if lost
                     else "todos los proyectos del registro traen descripción; no se descartó ninguno"},
        ],
        "why": "El universo es el que entregó la universidad: el análisis no filtra proyectos.",
    }


_ABSTRACT_SOURCES = {"openalex": "OpenAlex", "semanticscholar": "Semantic Scholar",
                     "crossref": "Crossref"}


def _ecotec_publications(raw_rows, rows, n_units):
    # abstract_source = "<fuente>_<como>[+<fuente>_<como>]"; cuenta la primera.
    by_source = Counter(_ABSTRACT_SOURCES.get(r["abstract_source"].split("+")[0].split("_")[0],
                                              "la página del editor")
                        for r in rows if r.get("abstract_source"))
    sources = ", ".join(f"{name} ({es_int(n)})" for name, n in by_source.most_common())
    dup = len(rows) - n_units
    steps = [
        {"n": len(raw_rows), "label": "Artículos que un proyecto declaró como su resultado",
         "note": "archivo «DATASET 2- Proyectos - Artículos»; llegan solo con su título"},
        {"n": len(rows), "label": "Se encontró su resumen",
         "note": ("buscado por título en " + sources + "; cada resumen se verifica contra el "
                  "título declarado y los dudosos se revisaron a mano")},
    ]
    if dup:
        steps.append({"n": n_units, "label": "Artículos distintos tras quitar duplicados",
                      "note": es_int(dup) + " estaban declarados por más de un proyecto"})
    return {
        "steps": steps,
        "why": ("Solo entran los artículos que el propio proyecto declaró. Sin resumen no hay texto "
                "suficiente para extraer temas: los " + es_int(len(raw_rows) - len(rows)) +
                " sin resumen encontrado quedan fuera."),
    }


# --- Datasets ----------------------------------------------------------------
# domains: tab = nombre corto (botones, encabezados), label = nombre largo
# (pie de pagina), noun = como se llama una unidad, provenance = embudo.
DATASETS = {
    "pucp": {
        "label": "PUCP",
        "title": "Atlas Temático PUCP",
        "eyebrow": "Libro Blanco · Proyecto Pulso · PUCP",
        "provenance_intro": ("No todo lo que existe en los registros de la universidad entra al análisis. "
                             "Cada universo pasa primero por un filtro de calidad, porque hace falta texto "
                             "propio para poder extraer temas. Esta pestaña muestra ese filtro paso a paso, "
                             "por qué se puso ahí el corte, y cuánto texto queda al final en cada unidad."),
        "domains": {
            "projects": {"tab": "Proyectos", "noun": "proyecto",
                         "label": "Proyectos de investigación PUCP concluidos (2010+)",
                         "provenance": _pucp_projects},
            "publications": {"tab": "Publicaciones", "noun": "publicación",
                             "label": "Publicaciones PUCP (catálogo completo)"},
            "publications_linked": {"tab": "Publicaciones de proyectos", "noun": "publicación",
                                    "label": "Publicaciones derivadas de proyectos del universo",
                                    "provenance": _pucp_publications_linked},
        },
    },
    "ecotec": {
        "label": "ECOTEC",
        "title": "Atlas Temático ECOTEC",
        "eyebrow": "Libro Blanco · Proyecto Pulso · ECOTEC",
        "provenance_intro": ("El universo es el que entregó la universidad. Los proyectos entran todos; "
                             "los artículos llegan solo con su título, y entran los que tienen un resumen "
                             "encontrado, porque hace falta texto propio para poder extraer temas. Esta "
                             "pestaña muestra cada paso y cuánto texto queda al final en cada unidad."),
        "domains": {
            "ecotec_projects": {"tab": "Proyectos", "noun": "proyecto",
                                "label": "Proyectos de investigación ECOTEC (registro entregado por la universidad)",
                                "provenance": _ecotec_projects},
            "ecotec_publications": {"tab": "Publicaciones de proyectos", "noun": "publicación",
                                    "label": "Artículos de proyectos ECOTEC (declarados por la universidad)",
                                    "provenance": _ecotec_publications},
        },
    },
}


def provenance(dataset: str, domain: str, raw_rows, rows, n_units) -> dict | None:
    fn = DATASETS[dataset]["domains"].get(domain, {}).get("provenance")
    return fn(raw_rows, rows, n_units) if fn else None


def page_profile(dataset: str, domains: list[str], plan) -> dict:
    """Lo que la pagina necesita para presentarse como este dataset. `plan` es
    el lb_plans.Plan de sus dominios."""
    import lb_domains
    ds = DATASETS[dataset]
    extra = PLANS[plan.key]
    return {
        "id": dataset, "label": ds["label"], "title": ds["title"], "eyebrow": ds["eyebrow"],
        "provenance_intro": ds["provenance_intro"],
        "extraction_html": EXTRACTION_HTML, "extraction_footer": EXTRACTION_FOOTER,
        "order": domains,
        "domains": {d: {"tab": ds["domains"][d]["tab"], "label": ds["domains"][d]["label"],
                        "noun": ds["domains"][d]["noun"], "kind": lb_domains.get(d).kind}
                    for d in domains},
        "plan": {"key": plan.key, "leaf": plan.leaf, "leaves": plan.leaves,
                 "level1_long": plan.level1_long, **extra},
    }

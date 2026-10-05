"""Definicion de los dos dominios: proyectos y publicaciones.

Separados a proposito. Cada dominio tiene su propio corpus, sus propias
columnas de texto y —lo importante— SU PROPIO ESPACIO DE TEMAS: los temas de
proyectos y los de publicaciones no se mezclan ni se comparan entre si. Si en
algun momento hace falta cruzarlos, tiene que ser un paso explicito y aparte,
no un efecto lateral de compartir tabla.

Anadir un dataset nuevo = anadir una entrada aqui. El resto del pipeline
(extraccion, normalizacion, cuantificacion, reportes) no cambia: esa es la
parte "replicable con otros datasets".
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Marcadores de "vacio" que aparecen en los CSV de origen y que NO deben
# contar como texto (ver EXPERIMENTS.md: el "-" del ground truth, y la columna
# Abstract de Scopus que en realidad es un enlace a scopus.com).
EMPTY_MARKERS = {"", "-", "--", "n/a", "na", "null", "none", "sin informacion",
                 "sin información", "[no disponible]"}
JUNK_PREFIXES = ("http://", "https://", "www.scopus.com")


@dataclass
class Domain:
    key: str
    label: str
    source_csv: Path
    id_column: str
    title_column: str
    # Columnas cuyo texto se concatena y se manda al LLM y a los embeddings.
    # Este es EXACTAMENTE el conjunto que audita el reporte de cobertura.
    text_columns: list[str]
    # Columnas de metadatos que se guardan pero no se embeben.
    metadata_columns: list[str] = field(default_factory=list)
    year_column: str = "year"
    grouping_column: str = ""
    knowledge_area_column: str = ""
    # Columnas que existen en el origen pero se excluyen del texto a proposito,
    # con el motivo. Salen en el reporte de cobertura como excluidas.
    excluded_columns: dict[str, str] = field(default_factory=dict)
    # Una unidad sin ninguna de estas columnas llena no se procesa.
    required_any: list[str] = field(default_factory=list)

    # --- Texto auxiliar: filas de otro CSV unidas por clave ----------------
    # Para proyectos, el CSV de origen no trae resumen (el export CRIS solo lo
    # tiene para proyectos recientes, que estan fuera de este universo). El
    # unico contenido disponible es el de los RESULTADOS DECLARADOS del
    # proyecto: sus publicaciones. Ojo con lo que eso significa: el tema pasa a
    # describir lo que el proyecto publico, no lo que se propuso.
    aux_csv: Path | None = None
    aux_join_column: str = ""          # columna de union en el CSV auxiliar
    aux_text_columns: list[str] = field(default_factory=list)
    aux_max_rows: int = 5              # cuantos resultados por unidad, como maximo
    aux_label: str = "resultado declarado"
    # Si se declara, el auxiliar es un FALLBACK, no un agregado: solo se usa
    # cuando estas columnas, juntas, no llegan a aux_min_primary_chars. Sin
    # esto, el texto de "lo que el proyecto publico" (aux) se apila siempre
    # encima de "lo que el proyecto dice que es" (p.ej. cris_abstract), aun
    # cuando la segunda ya es una descripcion completa por si sola.
    aux_primary_columns: list[str] = field(default_factory=list)
    aux_min_primary_chars: int = 0


DOMAINS: dict[str, Domain] = {
    "projects": Domain(
        key="projects",
        label="Proyectos de investigacion PUCP cerrados (2010+)",
        source_csv=REPO_ROOT / "salidas" / "01_projects_closed_con_cris.csv",
        id_column="project_id",
        title_column="title",
        # 2026-09-30: reducido a estas tres tras el export CRIS del 29-set
        # (cris_abstract paso de 0.9% a 66.3% de los 975 proyectos). Se probo
        # con knowledge_area + research_line* sumados: la mediana de
        # caracteres casi no cambiaba (1547 -> 1569) porque son etiquetas
        # cortas, y quedaban implicitos en cris_keywords de todos modos.
        # cris_fos se dejo fuera a proposito: solo 6 valores posibles en toda
        # la universidad (a veces repetido, "Social sciences||Social
        # sciences"), aporta casi nada. cris_ocde_subject nunca aporto nada
        # (son URIs, ver excluded_columns).
        text_columns=["title", "cris_abstract", "cris_keywords"],
        metadata_columns=[
            "year", "project_type", "knowledge_area", "executing_unit",
            "executing_section", "funding_type", "coordinator_norm",
        ],
        grouping_column="executing_unit",
        knowledge_area_column="knowledge_area",
        excluded_columns={
            "funder": "Nombre del financiador: identifica la fuente de fondos, no el tema.",
            "funding_type": "Interno/externo: administrativo, no tematico.",
            "cris_coinvestigators": "Nombres de personas: introducen ruido de nombres propios.",
            "coordinator_norm": "Idem; se guarda como metadato pero no se embebe.",
            "status": "Constante en este universo (todos cerrados).",
            "cris_fos": "Solo 6 valores posibles en toda la universidad (a veces repetido "
                       "literalmente); casi no discrimina entre proyectos.",
            "cris_ocde_subject": "Son URIs (p.ej. .../ford#5.07.03), no texto: clean_value() las "
                                 "descarta. Nunca aporto un caracter al embedding, en ningun export.",
            "knowledge_area": "Etiqueta corta; con cris_abstract presente aporta poco texto nuevo. "
                              "Se sigue guardando como metadato (knowledge_area_column) para "
                              "mostrarla, solo no se embebe.",
            "research_line_1": "Idem knowledge_area.", "research_line_2": "Idem.",
            "research_line_3": "Idem.", "research_line_4": "Idem.", "research_line": "Idem.",
        },
        required_any=["title", "cris_abstract", "cris_keywords"],
        aux_csv=REPO_ROOT / "salidas" / "06_project_results_ground_truth.csv",
        aux_join_column="project_id",
        # Orden deliberado: primero el titulo del resultado, luego el mejor
        # resumen disponible. clean_value ya descarta el "-" y las celdas que
        # en realidad son un enlace (la columna Abstract de Scopus lo es).
        aux_text_columns=["result_title", "resumen", "openalex_abstract",
                          "source_abstract", "palabras_clave", "source_keywords"],
        aux_max_rows=5,
        aux_label="resultado declarado del proyecto",
        # Fallback, no agregado: el universo minimo ya exige cris_abstract, asi
        # que esto solo se activa para el puñado de proyectos cuyo abstract es
        # mas corto que un tuit.
        aux_primary_columns=["cris_abstract"],
        aux_min_primary_chars=200,
    ),
    "publications": Domain(
        key="publications",
        label="Publicaciones PUCP (catalogo Scopus+WoS+RI deduplicado)",
        source_csv=REPO_ROOT / "salidas" / "03_publications_master.csv",
        id_column="publication_id",
        title_column="title",
        text_columns=["title", "abstract", "keywords", "journal"],
        metadata_columns=["year", "doi", "journal", "source_count"],
        grouping_column="journal",
        excluded_columns={
            "doi": "Identificador, sin contenido semantico.",
            "master_key": "Clave de deduplicacion interna.",
            "RI": "Banderas de procedencia, no tematicas.",
            "SCOPUS": "Idem.",
            "WOS": "Idem.",
        },
        required_any=["title", "abstract", "keywords"],
    ),
    # Tercer experimento de EXPERIMENTS.md: solo las publicaciones que son
    # resultado declarado de un proyecto del universo. Es el contraparte
    # directo del dominio "projects" -- responde "que publicaron de verdad
    # nuestros proyectos", con la misma unidad de analisis que ellos.
    # Espacio de temas PROPIO: no se comparan con los de projects ni con los
    # del catalogo completo.
    "publications_linked": Domain(
        key="publications_linked",
        label="Publicaciones derivadas de proyectos del universo (resultados declarados)",
        source_csv=REPO_ROOT / "salidas" / "07_publications_linked_full.csv",
        id_column="publication_id",
        title_column="title",
        text_columns=["title", "abstract", "keywords", "journal"],
        metadata_columns=["journal", "project_id", "abstract_source"],
        grouping_column="journal",
        excluded_columns={
            "abstract_source": "Procedencia del abstract: metadato de auditoria.",
            "project_id": "Proyecto que declaro el resultado; se guarda para trazar.",
        },
        required_any=["title", "abstract", "keywords"],
    ),
}


def get(key: str) -> Domain:
    if key not in DOMAINS:
        raise KeyError(f"dominio desconocido: {key!r}; disponibles: {sorted(DOMAINS)}")
    return DOMAINS[key]


def clean_year(value):
    """"2010.0" -> 2010. El Excel exporta el anio como float y la columna de la
    base es INTEGER, asi que el texto crudo no se puede insertar tal cual."""
    text = clean_value(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def clean_value(value) -> str:
    """Normaliza un valor de celda a texto util, o cadena vacia.

    Filtra los marcadores de vacio y los valores que son en realidad un enlace
    (la columna Abstract de Scopus lo es en todas sus filas; ver EXPERIMENTS.md).
    """
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in EMPTY_MARKERS:
        return ""
    if text.lower().startswith(JUNK_PREFIXES):
        return ""
    return text


def read_source(domain: Domain) -> list[dict]:
    if not domain.source_csv.exists():
        raise FileNotFoundError(
            f"No existe {domain.source_csv}. Los CSV de salidas/ no estan versionados; "
            "hay que traerlos desde S3 (etapa 00) o regenerarlos con scripts/run_all.py.")
    # Los abstracts pueden ser largos; el limite por defecto de csv rompe.
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    with domain.source_csv.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def qualifying_project_ids(rows: list[dict] | None = None) -> set[str]:
    """Universo minimo declarado de PROYECTOS (decision del equipo, no del
    CSV): closed/2010+ ya viene aplicado en el CSV de origen; a eso se suma
    title + cris_abstract.

    Antes exigia ademas knowledge_area + linea de investigacion (dejaba 409).
    Se reemplazo por este criterio mas simple cuando un nuevo export de CRIS
    (2026-09-29) llevo cris_abstract de 0.9% a 66.3% de los 975 proyectos:
    medido por longitud de texto, los proyectos que calificaban SOLO por
    knowledge_area+linea (sin abstract) tenian una mediana de 801 caracteres,
    y los que calificarian solo por abstract (sin esos tags) tenian 1547 --
    casi el doble. knowledge_area/linea de investigacion eran la mejor senal
    disponible de "hay contenido real" cuando el abstract estaba casi vacio;
    ya no lo son. 646 de 975 proyectos cumplen este criterio hoy.
    """
    if rows is None:
        rows = read_source(get("projects"))
    return {clean_value(r.get("project_id")) for r in rows
            if clean_value(r.get("title")) and clean_value(r.get("cris_abstract"))}


def filter_min_requirements(domain: Domain, rows: list[dict]) -> tuple[list[dict], int]:
    """Aplica el universo minimo declarado del dominio, si tiene uno.

    Esto es una decision del equipo sobre CALIDAD de dato, separada de
    ``required_any`` (que solo evita unidades sin texto en absoluto). Un
    proyecto o publicacion puede tener texto suficiente para `to_units()` y
    aun asi no cumplir el universo minimo declarado.
    """
    if domain.key == "projects":
        keep = qualifying_project_ids(rows)
        kept = [r for r in rows if clean_value(r.get("project_id")) in keep]
    elif domain.key == "publications_linked":
        # Universo minimo: title + abstract, aplicado directo sobre las 1192
        # publicaciones declaradas como resultado de un proyecto del universo.
        # Antes exigia ademas keywords (dejaba 308/300) y que el proyecto
        # padre TAMBIEN calificara bajo el criterio de projects -- se saco esa
        # segunda exigencia: la pregunta aqui es "esta publicacion tiene
        # suficiente texto propio", no "el proyecto que la declaro tambien
        # califica" (eso acoplaba el universo de publicaciones a un criterio
        # de otro dominio, sin necesidad). keywords se saco por el mismo
        # razonamiento que en projects: de las 1192 filas candidatas, keywords
        # estaba lleno en solo 30.8% (title 71.3%, abstract 45.1%) -- era el
        # cuello de botella real, no una senal de calidad adicional.
        # 538 filas (529 tras deduplicar) cumplen title+abstract hoy.
        kept = [r for r in rows
                if clean_value(r.get("title")) and clean_value(r.get("abstract"))]
    else:
        return rows, 0
    return kept, len(rows) - len(kept)


def load_aux(domain: Domain) -> dict[str, list[dict]]:
    """Agrupa las filas del CSV auxiliar por su clave de union."""
    if not domain.aux_csv or not domain.aux_csv.exists():
        return {}
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    grouped: dict[str, list[dict]] = {}
    with domain.aux_csv.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = clean_value(row.get(domain.aux_join_column))
            if key:
                grouped.setdefault(key, []).append(row)
    return grouped


def aux_text(domain: Domain, aux_rows: list[dict]) -> tuple[list[str], list[str]]:
    """Texto aportado por las filas auxiliares de una unidad.

    Se ordenan poniendo delante las que traen resumen, para que el recorte por
    ``aux_max_rows`` conserve los resultados con contenido real en vez de los
    que solo tienen titulo.
    """
    def richness(row):
        return sum(len(clean_value(row.get(c))) for c in domain.aux_text_columns)

    parts, sources = [], []
    for index, row in enumerate(sorted(aux_rows, key=richness, reverse=True)[:domain.aux_max_rows]):
        for column in domain.aux_text_columns:
            value = clean_value(row.get(column))
            if not value:
                continue
            parts.append(value)
            sources.append(f"aux:{column}")
            # Un solo resumen por resultado: en cuanto hay uno bueno, no se
            # apilan las tres variantes de la misma publicacion.
            if column in ("resumen", "openalex_abstract", "source_abstract"):
                break
    return parts, sources


def build_text(domain: Domain, row: dict, max_chars: int = 0,
               extra: tuple[list[str], list[str]] | None = None) -> tuple[str, list[str]]:
    """Concatena las columnas de texto del dominio. Devuelve (texto, fuentes).

    Las columnas vacias se omiten en vez de rellenarse con un marcador: meter
    "Sin informacion" en el texto le da al modelo de embeddings una senal
    espuria compartida por todas las filas incompletas, y esas filas terminan
    agrupandose entre si por su falta de datos y no por su tema.
    """
    parts, sources = [], []
    for column in domain.text_columns:
        value = clean_value(row.get(column))
        if not value:
            continue
        parts.append(value)
        sources.append(column)
    if extra:
        parts.extend(extra[0])
        sources.extend(extra[1])
    text = ". ".join(parts)
    if max_chars and len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0]
    return text, sources


def to_units(domain: Domain, rows: list[dict], max_chars: int = 0,
             use_aux: bool = True) -> tuple[list[dict], list[dict]]:
    """Convierte filas crudas en unidades. Devuelve (unidades, descartadas)."""
    aux = load_aux(domain) if use_aux else {}
    units, dropped = [], []
    for row in rows:
        unit_id = clean_value(row.get(domain.id_column))
        if not unit_id:
            dropped.append({"unit_id": "", "reason": "sin id"})
            continue
        aux_rows = aux.get(unit_id, [])
        if domain.aux_primary_columns:
            primary_chars = sum(len(clean_value(row.get(c))) for c in domain.aux_primary_columns)
            if primary_chars >= domain.aux_min_primary_chars:
                aux_rows = []  # la fuente primaria ya alcanza: no apilar el fallback
        extra = aux_text(domain, aux_rows) if aux_rows else None
        if domain.required_any and not any(
                clean_value(row.get(c)) for c in domain.required_any) and not extra:
            dropped.append({"unit_id": unit_id,
                            "reason": f"ninguna de {domain.required_any} tiene valor"})
            continue
        text, sources = build_text(domain, row, max_chars, extra)
        if not text:
            dropped.append({"unit_id": unit_id, "reason": "texto vacio tras limpieza"})
            continue
        units.append({
            "unit_id": unit_id,
            "title": clean_value(row.get(domain.title_column)),
            "year": clean_year(row.get(domain.year_column)),
            "grouping": clean_value(row.get(domain.grouping_column)) if domain.grouping_column else "",
            "knowledge_area": (clean_value(row.get(domain.knowledge_area_column))
                               if domain.knowledge_area_column else ""),
            "text": text,
            "text_sources": sources,
            "aux_rows_used": min(len(aux_rows), domain.aux_max_rows),
            "source_row": {c: clean_value(row.get(c)) for c in domain.metadata_columns},
        })
    return units, dropped

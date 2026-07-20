#!/usr/bin/env python3
"""
Integra múltiples exportaciones CSV de la interfaz web de Scopus con el CSV
base producido por resumenes_por_doi.py.

El programa:
1. Lee todos los CSV de una carpeta.
2. Detecta automáticamente columnas frecuentes de Scopus.
3. Normaliza los DOI.
4. Une las exportaciones y elimina duplicados.
5. Cruza los datos con el CSV base.
6. Completa únicamente campos vacíos:
   - titulo
   - scopus_id
   - eid
   - resumen
   - palabras_clave
7. Conserva la trazabilidad mediante columnas de fuente.
8. Produce un CSV final y reportes de control.

No reemplaza valores ya existentes en el CSV base.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path
from typing import Iterable

import pandas as pd


DOI_PREFIX_RE = re.compile(
    r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)",
    re.IGNORECASE,
)
SCOPUS_ID_RE = re.compile(r"(?:SCOPUS_ID:)?(\d+)$", re.IGNORECASE)
MULTISPACE_RE = re.compile(r"\s+")
KEYWORD_SPLIT_RE = re.compile(r"\s*[;|]\s*")


# Posibles nombres de columnas en las exportaciones de Scopus.
COLUMN_ALIASES = {
    "doi": {
        "doi",
        "document doi",
        "digital object identifier",
    },
    "titulo": {
        "title",
        "document title",
        "titulo",
        "título",
    },
    "eid": {
        "eid",
    },
    "scopus_id": {
        "scopus id",
        "scopus_id",
        "scopus eid",
    },
    "resumen": {
        "abstract",
        "resumen",
        "description",
    },
    "author_keywords": {
        "author keywords",
        "author keyword",
        "palabras clave de autor",
    },
    "indexed_keywords": {
        "indexed keywords",
        "index keywords",
        "indexed keyword",
        "palabras clave indexadas",
    },
    "pubmed_id": {
        "pubmed id",
        "pmid",
    },
}


OUTPUT_COLUMNS = [
    "doi",
    "titulo",
    "fuente_titulo",
    "scopus_id",
    "eid",
    "resumen",
    "fuente_resumen",
    "palabras_clave",
    "fuente_palabras_clave",
    "pubmed_id",
    "openalex_id",
    "estado_scopus",
    "detalle_error_scopus",
]


def normalize_header(value: object) -> str:
    """Normaliza un encabezado para compararlo con los alias."""
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[_\-]+", " ", text)
    return MULTISPACE_RE.sub(" ", text).strip()


def normalize_doi(value: object) -> str:
    """Normaliza DOI escritos como DOI puro o URL."""
    if value is None or pd.isna(value):
        return ""

    doi = str(value).strip()
    doi = DOI_PREFIX_RE.sub("", doi).strip()
    doi = doi.rstrip(" .;,")
    return doi.lower()


def clean_text(value: object) -> str:
    """Devuelve texto limpio y evita representar NaN como cadena."""
    if value is None or pd.isna(value):
        return ""
    return MULTISPACE_RE.sub(" ", str(value).strip())


def is_blank(value: object) -> bool:
    return clean_text(value) == ""


def unique_keywords(*values: object) -> str:
    """
    Combina palabras clave de autor e indexadas sin duplicados.
    Admite separadores ; y |.
    """
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        text = clean_text(value)
        if not text:
            continue

        for keyword in KEYWORD_SPLIT_RE.split(text):
            keyword = clean_text(keyword)
            key = keyword.casefold()

            if keyword and key not in seen:
                seen.add(key)
                result.append(keyword)

    return " | ".join(result)


def detect_delimiter(path: Path, encoding: str) -> str:
    """Intenta identificar coma, punto y coma o tabulador."""
    sample = path.read_text(encoding=encoding, errors="replace")[:65536]

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        return dialect.delimiter
    except csv.Error:
        # Las exportaciones CSV de Scopus suelen usar coma.
        return ","


def read_csv_flexible(path: Path) -> pd.DataFrame:
    """
    Lee CSV con varias codificaciones y detección de delimitador.
    dtype=str evita que identificadores largos se conviertan en números.
    """
    errors: list[str] = []

    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            delimiter = detect_delimiter(path, encoding)
            return pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                encoding=encoding,
                sep=delimiter,
                engine="python",
            )
        except Exception as exc:
            errors.append(f"{encoding}: {exc}")

    raise ValueError(
        f"No se pudo leer {path.name}. Intentos: {'; '.join(errors)}"
    )


def find_column(df: pd.DataFrame, logical_name: str) -> str | None:
    """Busca una columna mediante alias normalizados."""
    aliases = {
        normalize_header(alias)
        for alias in COLUMN_ALIASES[logical_name]
    }

    for column in df.columns:
        if normalize_header(column) in aliases:
            return column

    return None


def extract_scopus_id(eid: object, explicit_id: object = "") -> str:
    """Obtiene el ID numérico desde Scopus ID o desde el EID."""
    explicit = clean_text(explicit_id)
    match = SCOPUS_ID_RE.search(explicit)

    if match:
        return match.group(1)

    eid_text = clean_text(eid)
    if eid_text:
        final_part = eid_text.rsplit("-", 1)[-1]
        if final_part.isdigit():
            return final_part

    return ""


def standardize_scopus_file(path: Path) -> pd.DataFrame:
    """
    Convierte una exportación de Scopus a un esquema común.
    Los archivos que no tengan DOI se omiten mediante una excepción clara.
    """
    df = read_csv_flexible(path)

    column_map = {
        name: find_column(df, name)
        for name in COLUMN_ALIASES
    }

    if not column_map["doi"]:
        raise ValueError(
            "No se encontró una columna DOI. "
            f"Encabezados detectados: {list(df.columns)}"
        )

    result = pd.DataFrame()
    result["doi"] = df[column_map["doi"]].map(normalize_doi)

    for logical_name in (
        "titulo",
        "eid",
        "scopus_id",
        "resumen",
        "author_keywords",
        "indexed_keywords",
        "pubmed_id",
    ):
        source_column = column_map[logical_name]

        if source_column:
            result[logical_name] = df[source_column].map(clean_text)
        else:
            result[logical_name] = ""

    result["palabras_clave"] = [
        unique_keywords(author, indexed)
        for author, indexed in zip(
            result["author_keywords"],
            result["indexed_keywords"],
        )
    ]

    result["scopus_id"] = [
        extract_scopus_id(eid, sid)
        for eid, sid in zip(result["eid"], result["scopus_id"])
    ]

    result["archivo_scopus"] = path.name
    result = result[result["doi"] != ""].copy()

    return result[
        [
            "doi",
            "titulo",
            "scopus_id",
            "eid",
            "resumen",
            "palabras_clave",
            "pubmed_id",
            "archivo_scopus",
        ]
    ]


def choose_first_nonblank(values: Iterable[object]) -> str:
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return ""


def consolidate_scopus(rows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Consolida duplicados por DOI escogiendo el primer valor no vacío por campo.
    Produce además un reporte con el número de apariciones de cada DOI.
    """
    duplicate_report = (
        rows.groupby("doi", as_index=False)
        .agg(
            apariciones=("doi", "size"),
            archivos=("archivo_scopus", lambda s: " | ".join(sorted(set(s)))),
        )
    )
    duplicate_report = duplicate_report[
        duplicate_report["apariciones"] > 1
    ].copy()

    consolidated = (
        rows.groupby("doi", as_index=False)
        .agg(
            titulo=("titulo", choose_first_nonblank),
            scopus_id=("scopus_id", choose_first_nonblank),
            eid=("eid", choose_first_nonblank),
            resumen=("resumen", choose_first_nonblank),
            palabras_clave=("palabras_clave", choose_first_nonblank),
            pubmed_id=("pubmed_id", choose_first_nonblank),
            archivos_scopus=(
                "archivo_scopus",
                lambda s: " | ".join(sorted(set(s))),
            ),
        )
    )

    return consolidated, duplicate_report


def ensure_base_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega al CSV base cualquier columna esperada que no exista."""
    result = df.copy()

    for column in OUTPUT_COLUMNS:
        if column not in result.columns:
            result[column] = ""

    return result


def fill_if_blank(
    merged: pd.DataFrame,
    target: str,
    source: str,
    provenance_column: str | None = None,
) -> int:
    """
    Completa target usando source solo cuando target está vacío.
    Retorna el número de filas completadas.
    """
    target_blank = merged[target].map(is_blank)
    source_available = ~merged[source].map(is_blank)
    mask = target_blank & source_available

    merged.loc[mask, target] = merged.loc[mask, source]

    if provenance_column:
        merged.loc[mask, provenance_column] = "Scopus Web"

    return int(mask.sum())


def merge_data(
    base_df: pd.DataFrame,
    scopus_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Cruza por DOI y completa exclusivamente valores vacíos."""
    base = ensure_base_columns(base_df)
    base["doi"] = base["doi"].map(normalize_doi)

    scopus = scopus_df.rename(
        columns={
            "titulo": "_web_titulo",
            "scopus_id": "_web_scopus_id",
            "eid": "_web_eid",
            "resumen": "_web_resumen",
            "palabras_clave": "_web_palabras_clave",
            "pubmed_id": "_web_pubmed_id",
        }
    )

    merged = base.merge(scopus, on="doi", how="left", validate="m:1")

    stats = {
        "filas_base": len(base),
        "doi_encontrados_scopus_web": int(
            merged["_web_titulo"].notna().sum()
        ),
    }

    stats["titulos_completados"] = fill_if_blank(
        merged,
        "titulo",
        "_web_titulo",
        "fuente_titulo",
    )
    stats["scopus_id_completados"] = fill_if_blank(
        merged,
        "scopus_id",
        "_web_scopus_id",
    )
    stats["eid_completados"] = fill_if_blank(
        merged,
        "eid",
        "_web_eid",
    )
    stats["resumenes_completados"] = fill_if_blank(
        merged,
        "resumen",
        "_web_resumen",
        "fuente_resumen",
    )
    stats["palabras_clave_completadas"] = fill_if_blank(
        merged,
        "palabras_clave",
        "_web_palabras_clave",
        "fuente_palabras_clave",
    )
    stats["pubmed_id_completados"] = fill_if_blank(
        merged,
        "pubmed_id",
        "_web_pubmed_id",
    )

    stats["sin_resumen_final"] = int(
        merged["resumen"].map(is_blank).sum()
    )
    stats["sin_palabras_clave_final"] = int(
        merged["palabras_clave"].map(is_blank).sum()
    )
    stats["sin_resumen_o_palabras_final"] = int(
        (
            merged["resumen"].map(is_blank)
            | merged["palabras_clave"].map(is_blank)
        ).sum()
    )

    helper_columns = [
        column
        for column in merged.columns
        if column.startswith("_web_")
    ]

    final = merged.drop(columns=helper_columns)

    # Conserva primero el esquema conocido y después cualquier columna adicional.
    ordered = [
        column
        for column in OUTPUT_COLUMNS
        if column in final.columns
    ]
    extras = [
        column
        for column in final.columns
        if column not in ordered
    ]

    final = final[ordered + extras]
    return final, stats


def write_stats(stats: dict[str, int], path: Path) -> None:
    pd.DataFrame(
        [{"indicador": key, "valor": value} for key, value in stats.items()]
    ).to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Integra exportaciones CSV de Scopus Web con el CSV base "
            "y completa únicamente los campos vacíos."
        )
    )

    parser.add_argument(
        "base",
        type=Path,
        help="CSV base, por ejemplo doi-resultados.csv.",
    )
    parser.add_argument(
        "carpeta_scopus",
        type=Path,
        help="Carpeta que contiene las exportaciones CSV de Scopus.",
    )
    parser.add_argument(
        "-o",
        "--salida",
        type=Path,
        default=Path("doi-resultados-final.csv"),
        help="Nombre del CSV final.",
    )
    parser.add_argument(
        "--patron",
        default="*.csv",
        help="Patrón de archivos Scopus. Por defecto: *.csv",
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    if not args.base.exists():
        print(f"ERROR: no existe el CSV base: {args.base}", file=sys.stderr)
        return 2

    if not args.carpeta_scopus.is_dir():
        print(
            f"ERROR: no existe la carpeta: {args.carpeta_scopus}",
            file=sys.stderr,
        )
        return 2

    try:
        base_df = read_csv_flexible(args.base)
    except Exception as exc:
        print(f"ERROR al leer el CSV base: {exc}", file=sys.stderr)
        return 2

    if "doi" not in [normalize_header(c) for c in base_df.columns]:
        print(
            "ERROR: el CSV base debe tener una columna llamada doi.",
            file=sys.stderr,
        )
        return 2

    # Renombra a doi aunque el encabezado tenga mayúsculas o espacios.
    doi_column = next(
        c for c in base_df.columns if normalize_header(c) == "doi"
    )
    if doi_column != "doi":
        base_df = base_df.rename(columns={doi_column: "doi"})

    files = sorted(args.carpeta_scopus.glob(args.patron))

    # Evita leer accidentalmente el CSV final si se ejecuta en la misma carpeta.
    output_resolved = args.salida.resolve()
    files = [path for path in files if path.resolve() != output_resolved]

    if not files:
        print(
            "ERROR: no se encontraron archivos CSV de Scopus.",
            file=sys.stderr,
        )
        return 2

    standardized_frames: list[pd.DataFrame] = []
    file_log: list[dict[str, object]] = []

    for position, path in enumerate(files, start=1):
        print(f"[{position}/{len(files)}] Leyendo {path.name}", flush=True)

        try:
            frame = standardize_scopus_file(path)
            standardized_frames.append(frame)
            file_log.append(
                {
                    "archivo": path.name,
                    "estado": "OK",
                    "filas_validas": len(frame),
                    "detalle": "",
                }
            )
        except Exception as exc:
            file_log.append(
                {
                    "archivo": path.name,
                    "estado": "ERROR",
                    "filas_validas": 0,
                    "detalle": str(exc),
                }
            )
            print(f"    ADVERTENCIA: {exc}", file=sys.stderr)

    if not standardized_frames:
        print(
            "ERROR: ninguno de los archivos pudo procesarse.",
            file=sys.stderr,
        )
        return 2

    all_scopus = pd.concat(standardized_frames, ignore_index=True)
    consolidated, duplicate_report = consolidate_scopus(all_scopus)

    final, stats = merge_data(base_df, consolidated)

    output = args.salida.with_suffix(".csv")
    output.parent.mkdir(parents=True, exist_ok=True)

    final.to_csv(
        output,
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_MINIMAL,
    )

    prefix = output.with_suffix("")
    consolidated.to_csv(
        prefix.parent / f"{prefix.name}_scopus_unificado.csv",
        index=False,
        encoding="utf-8-sig",
    )
    duplicate_report.to_csv(
        prefix.parent / f"{prefix.name}_duplicados_scopus.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(file_log).to_csv(
        prefix.parent / f"{prefix.name}_log_archivos.csv",
        index=False,
        encoding="utf-8-sig",
    )
    write_stats(
        stats,
        prefix.parent / f"{prefix.name}_estadisticas.csv",
    )

    not_found = final[
        final["resumen"].map(is_blank)
        | final["palabras_clave"].map(is_blank)
    ].copy()
    not_found.to_csv(
        prefix.parent / f"{prefix.name}_pendientes.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print("\nProceso finalizado.")
    for key, value in stats.items():
        print(f"- {key}: {value}")

    print(f"\nCSV final: {output.resolve()}")
    print(
        "Reportes adicionales guardados con el mismo prefijo.",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Enriquecimiento de metadatos por DOI.

Fuentes consultadas, en orden:
1. Scopus
2. PubMed
3. OpenAlex
4. Crossref

Scopus se utiliza como fuente principal. Las otras fuentes solo completan
título, resumen o palabras clave cuando esos campos siguen vacíos.

Entrada:
- CSV con una columna llamada doi, o
- TXT con un DOI por línea.

Salida:
- CSV UTF-8 con BOM, compatible con Excel.

Variables de entorno:
- ELSEVIER_API_KEY: obligatoria.
- API_CONTACT_EMAIL: recomendada para identificar las consultas a APIs abiertas.
"""

from __future__ import annotations

import argparse
import csv
import html
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests


SCOPUS = "https://api.elsevier.com/content/abstract/doi"
PUBMED = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
OPENALEX = "https://api.openalex.org/works"
CROSSREF = "https://api.crossref.org/works"

DOI_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.I)
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = TAG_RE.sub(" ", text)
    return SPACE_RE.sub(" ", text).strip()


def normalize_doi(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return DOI_RE.sub("", str(value).strip()).strip()


def load_dois(path: Path) -> list[str]:
    extension = path.suffix.lower()

    if extension == ".txt":
        values = path.read_text(encoding="utf-8-sig").splitlines()

    elif extension == ".csv":
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        if len(df.columns) == 0:
            return []
        column = next(
            (c for c in df.columns if c.lower().strip() == "doi"),
            df.columns[0],
        )
        values = df[column].tolist()

    else:
        raise ValueError("La entrada debe ser un archivo .csv o .txt.")

    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        doi = normalize_doi(value)
        key = doi.lower()

        if doi and key not in seen:
            seen.add(key)
            result.append(doi)

    return result


def unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        text = clean(value)
        key = text.casefold()

        if text and key not in seen:
            seen.add(key)
            result.append(text)

    return result


def json_texts(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        text = clean(value)
        return [text] if text else []

    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(json_texts(item))
        return result

    if isinstance(value, dict):
        for key in ("$", "abstract"):
            if key in value:
                return json_texts(value[key])

    return []


def base_record(doi: str) -> dict[str, str]:
    return {
        "doi": doi,
        "titulo": "",
        "fuente_titulo": "",
        "scopus_id": "",
        "eid": "",
        "resumen": "",
        "fuente_resumen": "",
        "palabras_clave": "",
        "fuente_palabras_clave": "",
        "pubmed_id": "",
        "openalex_id": "",
        "estado_scopus": "",
        "detalle_error_scopus": "",
    }


def query_scopus(
    session: requests.Session,
    doi: str,
    api_key: str,
    timeout: int,
    retries: int,
) -> dict[str, str]:
    record = base_record(doi)
    url = f"{SCOPUS}/{quote(doi, safe='')}"

    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json",
        "User-Agent": "doi-metadata-enrichment-course/1.0",
    }

    # No se envía el parámetro view. Algunas claves pueden recuperar el registro
    # básico sin view, aunque no tengan autorización para vistas restringidas.
    for attempt in range(retries + 1):
        try:
            response = session.get(url, headers=headers, timeout=timeout)

        except requests.RequestException as exc:
            if attempt < retries:
                time.sleep(2**attempt)
                continue

            record["estado_scopus"] = "ERROR_RED"
            record["detalle_error_scopus"] = str(exc)
            return record

        if response.status_code == 200:
            try:
                data = response.json().get("abstracts-retrieval-response", {})
                core = data.get("coredata", {}) or {}

                record["titulo"] = clean(core.get("dc:title"))
                if record["titulo"]:
                    record["fuente_titulo"] = "Scopus"

                record["eid"] = clean(core.get("eid"))

                identifier = clean(core.get("dc:identifier"))
                if identifier:
                    record["scopus_id"] = identifier.split(":")[-1]
                elif record["eid"]:
                    record["scopus_id"] = record["eid"].rsplit("-", 1)[-1]

                record["pubmed_id"] = clean(core.get("pubmed-id"))

                record["resumen"] = clean(core.get("dc:description"))
                if not record["resumen"]:
                    abstract_node = (
                        data.get("item", {})
                        .get("bibrecord", {})
                        .get("head", {})
                        .get("abstracts")
                    )
                    record["resumen"] = " ".join(json_texts(abstract_node))

                if record["resumen"]:
                    record["fuente_resumen"] = "Scopus"

                keywords = json_texts(
                    data.get("authkeywords", {}).get("author-keyword", [])
                )

                if not keywords:
                    keywords = json_texts(
                        data.get("idxterms", {}).get("mainterm", [])
                    )

                if keywords:
                    record["palabras_clave"] = " | ".join(unique(keywords))
                    record["fuente_palabras_clave"] = "Scopus"

                record["estado_scopus"] = "OK"
                return record

            except (ValueError, TypeError, AttributeError) as exc:
                record["estado_scopus"] = "ERROR_JSON"
                record["detalle_error_scopus"] = str(exc)
                return record

        if response.status_code in {429, 500, 502, 503, 504} and attempt < retries:
            retry_after = response.headers.get("Retry-After", "1")
            try:
                wait_seconds = max(1.0, float(retry_after))
            except ValueError:
                wait_seconds = 1.0

            time.sleep(wait_seconds)
            continue

        status_map = {
            401: "API_KEY_INVALIDA",
            403: "SIN_AUTORIZACION",
            404: "NO_ENCONTRADO",
            429: "CUOTA_EXCEDIDA",
        }

        record["estado_scopus"] = status_map.get(
            response.status_code,
            f"HTTP_{response.status_code}",
        )

        try:
            record["detalle_error_scopus"] = clean(str(response.json()))[:1000]
        except ValueError:
            record["detalle_error_scopus"] = clean(response.text)[:1000]

        return record

    return record


def xml_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return clean("".join(element.itertext()))


def query_pubmed(
    session: requests.Session,
    doi: str,
    pubmed_id: str,
    timeout: int,
    email: str,
) -> dict[str, Any]:
    result = {
        "titulo": "",
        "resumen": "",
        "palabras_clave": [],
        "pubmed_id": "",
    }

    common_params = {
        "tool": "doi_metadata_enrichment_course",
        "email": email,
    }

    pmid = pubmed_id

    if not pmid:
        try:
            response = session.get(
                f"{PUBMED}/esearch.fcgi",
                params={
                    **common_params,
                    "db": "pubmed",
                    "term": f'"{doi}"[AID]',
                    "retmode": "json",
                    "retmax": 1,
                },
                timeout=timeout,
            )

            ids = (
                response.json()
                .get("esearchresult", {})
                .get("idlist", [])
                if response.status_code == 200
                else []
            )
            pmid = ids[0] if ids else ""

        except (requests.RequestException, ValueError):
            return result

    if not pmid:
        return result

    try:
        response = session.get(
            f"{PUBMED}/efetch.fcgi",
            params={
                **common_params,
                "db": "pubmed",
                "id": pmid,
                "retmode": "xml",
            },
            timeout=timeout,
        )

        if response.status_code != 200:
            return result

        root = ET.fromstring(response.content)
        article = root.find(".//PubmedArticle")

        if article is None:
            return result

    except (requests.RequestException, ET.ParseError):
        return result

    result["pubmed_id"] = pmid
    result["titulo"] = xml_text(article.find(".//ArticleTitle"))

    abstract_parts: list[str] = []

    for element in article.findall(".//Abstract/AbstractText"):
        text = xml_text(element)
        label = element.attrib.get("Label", "").strip()

        if text:
            abstract_parts.append(f"{label}: {text}" if label else text)

    result["resumen"] = " ".join(abstract_parts)

    author_keywords = [
        xml_text(element)
        for element in article.findall(".//KeywordList/Keyword")
    ]
    mesh_terms = [
        xml_text(element)
        for element in article.findall(".//MeshHeading/DescriptorName")
    ]

    result["palabras_clave"] = unique(author_keywords or mesh_terms)
    return result


def reconstruct_openalex_abstract(index: Any) -> str:
    if not isinstance(index, dict):
        return ""

    pairs: list[tuple[int, str]] = []

    for word, positions in index.items():
        if isinstance(positions, list):
            pairs.extend(
                (position, word)
                for position in positions
                if isinstance(position, int)
            )

    pairs.sort(key=lambda pair: pair[0])
    return clean(" ".join(word for _, word in pairs))


def query_openalex(
    session: requests.Session,
    doi: str,
    timeout: int,
    email: str,
) -> dict[str, Any]:
    result = {
        "titulo": "",
        "resumen": "",
        "palabras_clave": [],
        "openalex_id": "",
    }

    url = f"{OPENALEX}/https://doi.org/{quote(doi, safe='')}"

    headers = {
        "User-Agent": f"doi-metadata-enrichment-course/1.0 (mailto:{email})"
    }

    try:
        response = session.get(url, headers=headers, timeout=timeout)

        if response.status_code != 200:
            return result

        data = response.json()

    except (requests.RequestException, ValueError):
        return result

    result["openalex_id"] = clean(data.get("id"))
    result["titulo"] = clean(data.get("title"))
    result["resumen"] = reconstruct_openalex_abstract(
        data.get("abstract_inverted_index")
    )

    keywords = [
        item.get("display_name", "")
        for item in (data.get("keywords") or [])
        if isinstance(item, dict)
    ]

    if not keywords:
        keywords = [
            item.get("display_name", "")
            for item in (data.get("topics") or [])
            if isinstance(item, dict)
        ]

    result["palabras_clave"] = unique(keywords)
    return result


def query_crossref(
    session: requests.Session,
    doi: str,
    timeout: int,
    email: str,
) -> dict[str, Any]:
    result = {
        "titulo": "",
        "resumen": "",
        "palabras_clave": [],
    }

    url = f"{CROSSREF}/{quote(doi, safe='')}"

    headers = {
        "User-Agent": f"doi-metadata-enrichment-course/1.0 (mailto:{email})"
    }

    try:
        response = session.get(url, headers=headers, timeout=timeout)

        if response.status_code != 200:
            return result

        data = response.json().get("message", {})

    except (requests.RequestException, ValueError):
        return result

    titles = data.get("title") or []

    result["titulo"] = clean(titles[0]) if titles else ""
    result["resumen"] = clean(data.get("abstract"))
    result["palabras_clave"] = unique(data.get("subject") or [])

    return result


def fill_empty_fields(
    record: dict[str, str],
    source: str,
    data: dict[str, Any],
) -> None:
    if not record["titulo"] and data.get("titulo"):
        record["titulo"] = clean(data["titulo"])
        record["fuente_titulo"] = source

    if not record["resumen"] and data.get("resumen"):
        record["resumen"] = clean(data["resumen"])
        record["fuente_resumen"] = source

    if not record["palabras_clave"] and data.get("palabras_clave"):
        keywords = unique(list(data["palabras_clave"]))

        if keywords:
            record["palabras_clave"] = " | ".join(keywords)
            record["fuente_palabras_clave"] = source


def process_doi(
    session: requests.Session,
    doi: str,
    api_key: str,
    timeout: int,
    retries: int,
    email: str,
) -> dict[str, str]:
    record = query_scopus(
        session,
        doi,
        api_key,
        timeout,
        retries,
    )

    pubmed_data = query_pubmed(
        session,
        doi,
        record["pubmed_id"],
        timeout,
        email,
    )

    if pubmed_data.get("pubmed_id"):
        record["pubmed_id"] = str(pubmed_data["pubmed_id"])

    fill_empty_fields(record, "PubMed", pubmed_data)

    if (
        not record["titulo"]
        or not record["resumen"]
        or not record["palabras_clave"]
    ):
        openalex_data = query_openalex(
            session,
            doi,
            timeout,
            email,
        )

        if openalex_data.get("openalex_id"):
            record["openalex_id"] = str(openalex_data["openalex_id"])

        fill_empty_fields(record, "OpenAlex", openalex_data)

    if (
        not record["titulo"]
        or not record["resumen"]
        or not record["palabras_clave"]
    ):
        crossref_data = query_crossref(
            session,
            doi,
            timeout,
            email,
        )
        fill_empty_fields(record, "Crossref", crossref_data)

    return record


def save_csv(rows: list[dict[str, str]], path: Path) -> None:
    columns = [
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

    output_path = path.with_suffix(".csv")

    df = pd.DataFrame(rows, columns=columns)

    df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_MINIMAL,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Consulta DOI en Scopus y completa campos vacíos "
            "con PubMed, OpenAlex y Crossref."
        )
    )

    parser.add_argument(
        "entrada",
        type=Path,
        help="Archivo de entrada .csv o .txt.",
    )

    parser.add_argument(
        "-o",
        "--salida",
        type=Path,
        default=Path("resultados_resumenes.csv"),
        help="Archivo CSV de salida.",
    )

    parser.add_argument(
        "--api-key",
        default=os.getenv("ELSEVIER_API_KEY"),
        help="API Key de Elsevier. Se recomienda usar ELSEVIER_API_KEY.",
    )

    parser.add_argument(
        "--email",
        default=os.getenv(
            "API_CONTACT_EMAIL",
            "biblioteca@institucion.edu",
        ),
        help="Correo de contacto para PubMed, OpenAlex y Crossref.",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Tiempo máximo por solicitud, en segundos.",
    )

    parser.add_argument(
        "--reintentos",
        type=int,
        default=2,
        help="Número de reintentos ante errores temporales.",
    )

    parser.add_argument(
        "--pausa",
        type=float,
        default=0.35,
        help="Pausa entre DOI, en segundos.",
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    if not args.api_key:
        print(
            "ERROR: defina ELSEVIER_API_KEY o use --api-key.",
            file=sys.stderr,
        )
        return 2

    if not args.entrada.exists():
        print(
            f"ERROR: no existe el archivo {args.entrada}",
            file=sys.stderr,
        )
        return 2

    try:
        dois = load_dois(args.entrada)
    except Exception as exc:
        print(
            f"ERROR al leer la entrada: {exc}",
            file=sys.stderr,
        )
        return 2

    if not dois:
        print(
            "ERROR: no se encontraron DOI válidos.",
            file=sys.stderr,
        )
        return 2

    rows: list[dict[str, str]] = []

    with requests.Session() as session:
        for position, doi in enumerate(dois, start=1):
            print(
                f"[{position}/{len(dois)}] {doi}",
                flush=True,
            )

            record = process_doi(
                session,
                doi,
                args.api_key,
                args.timeout,
                args.reintentos,
                args.email,
            )

            rows.append(record)
            save_csv(rows, args.salida)

            print(
                "    "
                f"Scopus={record['estado_scopus']} | "
                f"resumen={record['fuente_resumen'] or 'sin resumen'} | "
                f"palabras clave="
                f"{record['fuente_palabras_clave'] or 'sin palabras clave'}",
                flush=True,
            )

            if position < len(dois) and args.pausa > 0:
                time.sleep(args.pausa)

    output_path = args.salida.with_suffix(".csv")

    print(
        f"Finalizado: {len(rows)} DOI; "
        f"con resumen: {sum(bool(row['resumen']) for row in rows)}; "
        f"con palabras clave: "
        f"{sum(bool(row['palabras_clave']) for row in rows)}."
    )
    print(f"Salida: {output_path.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

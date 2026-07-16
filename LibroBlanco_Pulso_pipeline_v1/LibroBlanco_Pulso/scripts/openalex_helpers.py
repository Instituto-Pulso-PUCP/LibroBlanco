import os
import json
import time
import random
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

OPENALEX_API_KEY = os.getenv('OPENALEX_API_KEY', '').strip()
OPENALEX_MAILTO = os.getenv('OPENALEX_MAILTO', '').strip()
# Rate limiting and retry/backoff configuration for OpenAlex queries
OPENALEX_RATE_LIMIT_SECONDS = float(os.getenv('OPENALEX_RATE_LIMIT_SECONDS', '3.0'))
OPENALEX_MAX_RETRIES = int(os.getenv('OPENALEX_MAX_RETRIES', '4'))
OPENALEX_BACKOFF_FACTOR = float(os.getenv('OPENALEX_BACKOFF_FACTOR', '2.0'))
OPENALEX_JITTER_SECONDS = float(os.getenv('OPENALEX_JITTER_SECONDS', '0.5'))


def build_openalex_query(doi=None, title=None):
    doi_norm = doi.strip().lower() if doi is not None else ''
    if doi_norm in {'', '-', 'nan', 'none'}:
        doi_norm = ''
    params = []
    if OPENALEX_API_KEY:
        params.append(("api_key", OPENALEX_API_KEY))
    if OPENALEX_MAILTO:
        params.append(("mailto", OPENALEX_MAILTO))

    def build_query(base, query_params):
        if not query_params:
            return base
        qs = '&'.join(f"{quote(str(k))}={quote(str(v))}" for k, v in query_params)
        return f"{base}?{qs}"

    if doi_norm:
        return build_query(f"https://api.openalex.org/works/doi:{doi_norm}", params)
    title_norm = str(title or "").strip()
    if title_norm:
        query_params = [("search", title_norm), ("per-page", 1)] + params
        return build_query("https://api.openalex.org/works", query_params)
    return ""


def extract_openalex_enrichment(payload, doi=None, title=None):
    payload = payload or {}
    location = payload.get("primary_location") or {}
    oa_location = payload.get("best_oa_location") or location
    oa_meta = payload.get("open_access") or {}
    is_oa = bool(oa_meta.get("is_oa") if isinstance(oa_meta, dict) else False) or bool(location.get("is_oa") or False)
    oa_status = oa_meta.get("oa_status") or ("green" if is_oa else "closed")
    oa_url = (oa_location or {}).get("landing_page_url") or (location or {}).get("landing_page_url") or ""
    source_name = ((oa_location or {}).get("source") or {}).get("display_name") or ((location or {}).get("source") or {}).get("display_name") or ""
    authors = []
    for item in payload.get("authorships") or []:
        author = item.get("author") or {}
        name = author.get("display_name")
        if name:
            authors.append(name)

    suggested_fields = []
    if payload.get("doi"):
        suggested_fields.append("openalex_doi")
    if payload.get("publication_year") is not None:
        suggested_fields.append("openalex_publication_year")
    if payload.get("cited_by_count") is not None:
        suggested_fields.append("openalex_cited_by_count")
    if source_name:
        suggested_fields.append("openalex_source_display_name")
    if authors:
        suggested_fields.append("openalex_authors")
    if oa_status:
        suggested_fields.append("openalex_oa_status")
    if oa_url:
        suggested_fields.append("openalex_oa_url")

    return {
        'openalex_query': build_openalex_query(doi=doi, title=title),
        'openalex_work_id': payload.get('id', ''),
        'openalex_doi': payload.get('doi', ''),
        'openalex_is_oa': is_oa,
        'openalex_oa_status': oa_status,
        'openalex_oa_url': oa_url,
        'openalex_publication_year': payload.get('publication_year'),
        'openalex_cited_by_count': payload.get('cited_by_count'),
        'openalex_source_display_name': source_name,
        'openalex_authors': '; '.join(authors),
        'openalex_suggested_fields': suggested_fields,
        'openalex_enrichment_error': '',
        'openalex_enrichment_raw_json': json.dumps(payload, ensure_ascii=False)
    }


def fetch_openalex_enrichment(doi=None, title=None, timeout=10):
    query = build_openalex_query(doi=doi, title=title)
    headers = {'User-Agent': 'Mozilla/5.0'}
    if OPENALEX_API_KEY:
        headers['Authorization'] = f"Bearer {OPENALEX_API_KEY}"
    if OPENALEX_MAILTO:
        headers['mailto'] = OPENALEX_MAILTO
    if not query:
        return {
            'openalex_query': '',
            'openalex_work_id': '',
            'openalex_doi': '',
            'openalex_is_oa': False,
            'openalex_oa_status': 'unknown',
            'openalex_oa_url': '',
            'openalex_publication_year': None,
            'openalex_cited_by_count': None,
            'openalex_source_display_name': '',
            'openalex_authors': '',
            'openalex_suggested_fields': [],
            'openalex_enrichment_error': 'missing doi or title',
            'openalex_enrichment_raw_json': ''
        }

    attempt = 0
    payload = None
    last_error = None
    while attempt < OPENALEX_MAX_RETRIES:
        try:
            req = Request(query, headers=headers)
            with urlopen(req, timeout=timeout) as resp:
                payload = json.load(resp)
            time.sleep(OPENALEX_RATE_LIMIT_SECONDS + random.uniform(0, OPENALEX_JITTER_SECONDS))
            break
        except HTTPError as he:
            last_error = he
            if getattr(he, 'code', None) == 429:
                retry_after = None
                if hasattr(he, 'headers') and he.headers is not None:
                    ra = he.headers.get('Retry-After')
                    if ra:
                        try:
                            retry_after = float(ra)
                        except ValueError:
                            pass
                wait = retry_after if retry_after is not None else (OPENALEX_RATE_LIMIT_SECONDS * (OPENALEX_BACKOFF_FACTOR ** attempt))
                wait += random.uniform(0, OPENALEX_JITTER_SECONDS)
                time.sleep(wait)
                attempt += 1
                continue
            return {
                'openalex_query': query,
                'openalex_work_id': '',
                'openalex_doi': '',
                'openalex_is_oa': False,
                'openalex_oa_status': 'unknown',
                'openalex_oa_url': '',
                'openalex_publication_year': None,
                'openalex_cited_by_count': None,
                'openalex_source_display_name': '',
                'openalex_authors': '',
                'openalex_suggested_fields': [],
                'openalex_enrichment_error': f'HTTP Error {he.code}: {he.reason}',
                'openalex_enrichment_raw_json': ''
            }
        except URLError as ue:
            last_error = ue
            wait = (OPENALEX_RATE_LIMIT_SECONDS * (OPENALEX_BACKOFF_FACTOR ** attempt)) + random.uniform(0, OPENALEX_JITTER_SECONDS)
            time.sleep(wait)
            attempt += 1
            continue
        except Exception as exc:
            return {
                'openalex_query': query,
                'openalex_work_id': '',
                'openalex_doi': '',
                'openalex_is_oa': False,
                'openalex_oa_status': 'unknown',
                'openalex_oa_url': '',
                'openalex_publication_year': None,
                'openalex_cited_by_count': None,
                'openalex_source_display_name': '',
                'openalex_authors': '',
                'openalex_suggested_fields': [],
                'openalex_enrichment_error': str(exc),
                'openalex_enrichment_raw_json': ''
            }

    if payload is None:
        err_msg = str(last_error) if last_error is not None else 'no response'
        return {
            'openalex_query': query,
            'openalex_work_id': '',
            'openalex_doi': '',
            'openalex_is_oa': False,
            'openalex_oa_status': 'unknown',
            'openalex_oa_url': '',
            'openalex_publication_year': None,
            'openalex_cited_by_count': None,
            'openalex_source_display_name': '',
            'openalex_authors': '',
            'openalex_suggested_fields': [],
            'openalex_enrichment_error': f'request failed after retries: {err_msg}',
            'openalex_enrichment_raw_json': ''
        }

    if isinstance(payload, dict) and 'results' in payload and payload.get('results'):
        payload = payload['results'][0]
    if not isinstance(payload, dict):
        return {
            'openalex_query': query,
            'openalex_work_id': '',
            'openalex_doi': '',
            'openalex_is_oa': False,
            'openalex_oa_status': 'unknown',
            'openalex_oa_url': '',
            'openalex_publication_year': None,
            'openalex_cited_by_count': None,
            'openalex_source_display_name': '',
            'openalex_authors': '',
            'openalex_suggested_fields': [],
            'openalex_enrichment_error': 'empty response',
            'openalex_enrichment_raw_json': ''
        }

    return extract_openalex_enrichment(payload, doi=doi, title=title)

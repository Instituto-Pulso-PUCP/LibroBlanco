import os
import json
import time
import random
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def _load_dotenv():
    """Minimal .env loader (no external dependency).

    Populates ``os.environ`` from the repository-root ``.env`` file without
    overriding variables that are already set in the environment. Runs on
    import so any entry point picks up OPENALEX_* credentials automatically.
    """
    env_path = Path(__file__).resolve().parents[1] / '.env'
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)
    except Exception:
        # A malformed .env should never break the pipeline.
        pass


_load_dotenv()

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
        query_params = [("search.exact", title_norm), ("per-page", 1)] + params
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
    institution_names = []
    institution_country_codes = []
    for item in payload.get("authorships") or []:
        author = item.get("author") or {}
        name = author.get("display_name")
        if name:
            authors.append(name)
        for inst in item.get("institutions") or []:
            inst_name = inst.get("display_name")
            if inst_name:
                institution_names.append(inst_name)
            country_code = inst.get("country_code")
            if country_code:
                institution_country_codes.append(str(country_code).upper())

    unique_institution_names = []
    for name in institution_names:
        if name not in unique_institution_names:
            unique_institution_names.append(name)
    unique_country_codes = []
    for code in institution_country_codes:
        if code not in unique_country_codes:
            unique_country_codes.append(code)

    return {
        'openalex_work_id': payload.get('id', ''),
        'openalex_doi': payload.get('doi', ''),
        'openalex_is_oa': is_oa,
        'openalex_oa_status': oa_status,
        'openalex_oa_url': oa_url,
        'openalex_publication_year': payload.get('publication_year'),
        'openalex_cited_by_count': payload.get('cited_by_count'),
        'openalex_source_display_name': source_name,
        'openalex_authors': '; '.join(authors),
        'openalex_institution_names': '; '.join(unique_institution_names),
        'openalex_institution_country_codes': '; '.join(unique_country_codes),
        'openalex_enrichment_error': '',
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
            'openalex_work_id': '',
            'openalex_doi': '',
            'openalex_is_oa': False,
            'openalex_oa_status': 'unknown',
            'openalex_oa_url': '',
            'openalex_publication_year': None,
            'openalex_cited_by_count': None,
            'openalex_source_display_name': '',
            'openalex_authors': '',
            'openalex_institution_names': '',
            'openalex_institution_country_codes': '',
            'openalex_enrichment_error': 'missing doi or title',
            'openalex_raw_payload': None
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
                'openalex_work_id': '',
                'openalex_doi': '',
                'openalex_is_oa': False,
                'openalex_oa_status': 'unknown',
                'openalex_oa_url': '',
                'openalex_publication_year': None,
                'openalex_cited_by_count': None,
                'openalex_source_display_name': '',
                'openalex_authors': '',
                'openalex_institution_names': '',
                'openalex_institution_country_codes': '',
                'openalex_enrichment_error': f'HTTP Error {he.code}: {he.reason}',
                'openalex_raw_payload': None
            }
        except URLError as ue:
            last_error = ue
            wait = (OPENALEX_RATE_LIMIT_SECONDS * (OPENALEX_BACKOFF_FACTOR ** attempt)) + random.uniform(0, OPENALEX_JITTER_SECONDS)
            time.sleep(wait)
            attempt += 1
            continue
        except Exception as exc:
            return {
                'openalex_work_id': '',
                'openalex_doi': '',
                'openalex_is_oa': False,
                'openalex_oa_status': 'unknown',
                'openalex_oa_url': '',
                'openalex_publication_year': None,
                'openalex_cited_by_count': None,
                'openalex_source_display_name': '',
                'openalex_authors': '',
                'openalex_institution_names': '',
                'openalex_institution_country_codes': '',
                'openalex_enrichment_error': str(exc),
                'openalex_raw_payload': None
            }

    if payload is None:
        err_msg = str(last_error) if last_error is not None else 'no response'
        return {
            'openalex_work_id': '',
            'openalex_doi': '',
            'openalex_is_oa': False,
            'openalex_oa_status': 'unknown',
            'openalex_oa_url': '',
            'openalex_publication_year': None,
            'openalex_cited_by_count': None,
            'openalex_source_display_name': '',
            'openalex_authors': '',
            'openalex_institution_names': '',
            'openalex_institution_country_codes': '',
            'openalex_enrichment_error': f'request failed after retries: {err_msg}',
            'openalex_raw_payload': None
        }

    if isinstance(payload, dict) and 'results' in payload and payload.get('results'):
        payload = payload['results'][0]
    if not isinstance(payload, dict):
        return {
            'openalex_work_id': '',
            'openalex_doi': '',
            'openalex_is_oa': False,
            'openalex_oa_status': 'unknown',
            'openalex_oa_url': '',
            'openalex_publication_year': None,
            'openalex_cited_by_count': None,
            'openalex_source_display_name': '',
            'openalex_authors': '',
            'openalex_institution_names': '',
            'openalex_institution_country_codes': '',
            'openalex_enrichment_error': 'empty response',
            'openalex_raw_payload': None
        }

    result = extract_openalex_enrichment(payload, doi=doi, title=title)
    result['openalex_raw_payload'] = payload
    return result


# ---------------------------------------------------------------------------
# Persistent enrichment cache (enables stop/resume without re-querying OpenAlex)
# ---------------------------------------------------------------------------

# Errors that are transient and should NOT be cached, so a later resume retries
# them instead of serving a stale failure.
_TRANSIENT_ERROR_MARKERS = ('429', 'Too Many Requests', 'after retries', 'timed out', 'timeout')


def enrichment_cache_key(doi=None, title=None):
    """Stable cache key for an enrichment request.

    Independent of credentials so the cache stays valid across API-key changes.
    Prefers DOI (deduplicating works that share a DOI); falls back to a
    normalized title. Returns '' when neither is usable.
    """
    doi_norm = (doi or '').strip().lower()
    if doi_norm in {'', '-', 'nan', 'none'}:
        doi_norm = ''
    if doi_norm:
        return 'doi:' + doi_norm
    title_norm = ' '.join(str(title or '').strip().lower().split())
    return ('title:' + title_norm) if title_norm else ''


def _is_transient_error(result):
    err = str((result or {}).get('openalex_enrichment_error') or '')
    if not err:
        return False
    return any(marker in err for marker in _TRANSIENT_ERROR_MARKERS)


class OpenAlexCache:
    """Append-only JSONL cache of OpenAlex enrichment results.

    Each successful (or definitively-failed) lookup is written to disk
    immediately, so an interrupted run keeps every result already fetched and a
    re-run resumes from where it stopped. Transient failures (rate limits,
    network timeouts) are deliberately not persisted.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.data = {}
        if self.path.exists():
            with open(self.path, encoding='utf-8') as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except Exception:
                        continue
                    key = record.get('key')
                    if key:
                        self.data[key] = record.get('result')

    def __contains__(self, key):
        return key in self.data

    def __len__(self):
        return len(self.data)

    def get(self, key):
        return self.data.get(key)

    def put(self, key, result):
        self.data[key] = result
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps({'key': key, 'result': result}, ensure_ascii=False) + '\n')


def fetch_openalex_enrichment_cached(doi=None, title=None, cache=None, timeout=10):
    """Cache-aware wrapper around :func:`fetch_openalex_enrichment`.

    Returns ``(result, was_cached)``. Results are served from ``cache`` when
    present; new lookups are stored unless they failed transiently. When
    ``cache`` is None this behaves like the uncached fetch.
    """
    if cache is None:
        return fetch_openalex_enrichment(doi=doi, title=title, timeout=timeout), False

    key = enrichment_cache_key(doi=doi, title=title)
    if key and key in cache:
        return cache.get(key), True

    result = fetch_openalex_enrichment(doi=doi, title=title, timeout=timeout)
    if key and not _is_transient_error(result):
        cache.put(key, result)
    return result, False

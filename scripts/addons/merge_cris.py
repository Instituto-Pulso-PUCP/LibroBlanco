#!/usr/bin/env python3
"""Enrich the project master (``01_projects_closed.csv``) with the DSpace-CRIS
project export (``datos/ProyectosPUCPCRIS-*.csv``).

The CRIS export carries project-level fields the VRI Excel does not have:
abstract, free-text keywords, full co-investigator roster, OCDE/FOS
classification and real start/end dates. It also contains a handful of
projects that are absent from the VRI Excel entirely.

Matching strategy, in priority order:
    1. Internal code: CRIS ``oairecerif.internalid`` vs the project's
       ``codigo_actividad`` or ``codigo_campus``.
    2. Exact normalized title.
    3. Fuzzy normalized title (token Jaccard >= ``--fuzzy-threshold``,
       default 0.65) -- only accepted when unambiguous.

CRIS rows that cannot be matched at all become new rows appended to the
project master (continuing the ``project_id`` sequence) *only* when their
CRIS status is "concluido" and their start year is >= ``--year-start``
(2010 by default), mirroring the same closed/year filter
``01_build_pipeline.py`` applies to the VRI Excel. Everything else
(ambiguous title matches, and new-looking CRIS projects that don't meet the
closed/year filter) is written to a report CSV instead of being silently
merged or dropped.

New columns are namespaced ``cris_*`` so ``export_xlsx.py`` colors them as
their own source and they never collide with existing pipeline columns.

Usage::

    # default: reads salidas/01_projects_closed.csv + datos/ProyectosPUCPCRIS-*.csv
    python scripts/addons/merge_cris.py

    # explicit files
    python scripts/addons/merge_cris.py --main salidas/01_projects_closed.csv \
        --cris datos/ProyectosPUCPCRIS-20260814.csv \
        --output salidas/01_projects_closed_con_cris.csv
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))

from export_xlsx import write_colored_xlsx  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'salidas'
DATOS = ROOT / 'datos'
XLSX_INPUT = DATOS / 'informacion_proyecto_pulso.xlsx'
PROJECT_SHEET = 'PROYECTOS'

_EMPTY_CODES = {'', 'NO APLICA', '-', 'NAN', 'NONE'}
_URI_FRAGMENT_RE = re.compile(r'.*[#/]')


def norm_text(x) -> str:
    """Same normalization used by 01_build_pipeline.py, so title_norm joins match."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ''
    s = str(x).strip().upper()
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'[^A-Z0-9 ]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def norm_code(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ''
    s = str(x).strip().upper().replace('.', '-')
    return '' if s in _EMPTY_CODES else s


def clean_uri_fragment(x) -> str:
    """'https://purl.org/.../estadoProyecto#concluido' -> 'concluido'; '||'-joined values kept."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ''
    parts = [p.strip() for p in str(x).split('||') if p.strip()]
    return '||'.join(_URI_FRAGMENT_RE.sub('', p) for p in parts)


def title_tokens(t: str) -> set:
    return {w for w in t.split() if len(w) > 3}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_default_cris_csv() -> Path | None:
    candidates = sorted(DATOS.glob('ProyectosPUCPCRIS*.csv'))
    return candidates[-1] if candidates else None


def load_cris(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df = df.rename(columns={
        'id': 'cris_uuid',
        'oairecerif.internalid': 'internalid',
        'dc.title': 'cris_title',
        'dc.description.abstract': 'cris_abstract',
        'dc.subject': 'cris_keywords',
        'perucris.subject.ocde': 'cris_ocde_subject',
        'datacite.subject.fos': 'cris_fos',
        'perucris.project.typeOcde': 'cris_type_ocde_raw',
        'oairecerif.project.status': 'cris_status_raw',
        'oairecerif.project.startDate': 'cris_start_date',
        'oairecerif.project.endDate': 'cris_end_date',
        'crispj.coordinator': 'cris_coordinator',
        'crispj.coinvestigators': 'cris_coinvestigators',
        'crispj.coinvestigators.role': 'cris_coinvestigator_roles',
    })
    df['code'] = df['internalid'].map(norm_code)
    df['t'] = df['cris_title'].map(norm_text)
    df['cris_status'] = df['cris_status_raw'].map(clean_uri_fragment)
    df['cris_type_ocde'] = df['cris_type_ocde_raw'].map(clean_uri_fragment)
    df['cris_coinvestigator_roles'] = df['cris_coinvestigator_roles'].map(clean_uri_fragment)

    name_n = df['cris_coinvestigators'].apply(lambda s: len([p for p in s.split('||') if p.strip()]) if s else 0)
    role_n = df['cris_coinvestigator_roles'].apply(lambda s: len([p for p in s.split('||') if p.strip()]) if s else 0)
    df['cris_coinvestigator_count_mismatch'] = (name_n != role_n) & ((name_n > 0) | (role_n > 0))

    # A handful of CRIS rows are duplicate registrations of the same project
    # under two different internal codes (same normalized title + start date).
    # Keep the most complete row per (title, start date) pair.
    df['_completeness'] = df[['cris_abstract', 'cris_keywords', 'cris_coinvestigators']] \
        .apply(lambda r: sum(bool(str(v).strip()) for v in r), axis=1)
    before = len(df)
    df = (df.sort_values('_completeness', ascending=False)
            .drop_duplicates(subset=['t', 'cris_start_date'], keep='first')
            .drop(columns=['_completeness']))
    dropped = before - len(df)
    if dropped:
        print(f'  {dropped} filas CRIS descartadas por ser duplicados de titulo+fecha.', flush=True)
    return df.reset_index(drop=True)


def load_full_project_index(xlsx_path: Path) -> dict:
    """Codes/titles of *every* project in the VRI Excel (not just the closed
    subset in ``01_projects_closed.csv``), used only to tell "genuinely
    absent from the Excel" apart from "exists in the Excel but isn't part of
    the closed/2010+ master" -- so we don't mis-classify the latter as new.
    """
    proj = pd.read_excel(xlsx_path, sheet_name=PROJECT_SHEET)
    codes = set()
    for col in ('CÓDIGO DE PROYECTO', 'CÓDIGO CAMPUS'):
        codes.update(c for c in proj[col].map(norm_code) if c)
    titles = set()
    title_tokens_list = []
    for t in proj['Título'].map(norm_text):
        if t and t not in titles:
            titles.add(t)
            title_tokens_list.append(title_tokens(t))
    return {'codes': codes, 'titles': titles, 'title_tokens_list': title_tokens_list}


CRIS_ENRICH_COLS = [
    'internalid', 'cris_abstract', 'cris_keywords', 'cris_ocde_subject', 'cris_fos',
    'cris_type_ocde', 'cris_status', 'cris_start_date', 'cris_end_date',
    'cris_coordinator', 'cris_coinvestigators', 'cris_coinvestigator_roles',
    'cris_coinvestigator_count_mismatch',
]


def _exists_in_full_xlsx(cris_row, full_index: dict, fuzzy_threshold: float) -> bool:
    """True if this CRIS row matches some project anywhere in the full VRI
    Excel (closed or not) -- used to avoid treating an existing-but-not-closed
    project as a brand-new one."""
    if cris_row.code and cris_row.code in full_index['codes']:
        return True
    if cris_row.t and cris_row.t in full_index['titles']:
        return True
    if cris_row.t:
        toks = title_tokens(cris_row.t)
        best = max((jaccard(toks, mtoks) for mtoks in full_index['title_tokens_list']), default=0.0)
        if best >= fuzzy_threshold:
            return True
    return False


def match_and_merge(main: pd.DataFrame, cris: pd.DataFrame, full_index: dict, fuzzy_threshold: float,
                     new_row_min_score: float):
    main = main.copy()
    for c in ['codigo_actividad_norm', 'codigo_campus_norm']:
        if c in main.columns:
            main = main.drop(columns=[c])
    main['codigo_actividad_norm'] = main['codigo_actividad'].map(norm_code)
    main['codigo_campus_norm'] = main['codigo_campus'].map(norm_code)

    code_to_project_id = {}
    for r in main.itertuples():
        for code in (r.codigo_actividad_norm, r.codigo_campus_norm):
            if code:
                code_to_project_id.setdefault(code, []).append(r.project_id)
    title_to_project_id = {}
    for r in main.itertuples():
        if r.title_norm:
            title_to_project_id.setdefault(r.title_norm, []).append(r.project_id)

    main_titles = [(pid, title_tokens(t)) for pid, t in zip(main['project_id'], main['title_norm']) if t]

    match_of_project_id = {}   # project_id -> cris row (namedtuple)
    method_of_project_id = {}  # project_id -> 'code' | 'title_exact' | 'title_fuzzy'
    stats = {'ambiguous_code': 0, 'ambiguous_title': 0}
    new_candidates = []
    report_rows = []

    for cris_row in cris.itertuples():
        target_pid = None
        method = None

        if cris_row.code and cris_row.code in code_to_project_id:
            pids = code_to_project_id[cris_row.code]
            if len(pids) == 1:
                target_pid, method = pids[0], 'code'
            else:
                stats['ambiguous_code'] += 1
                report_rows.append(_report_row(cris_row, 'ambiguous_code_match', None, None,
                                                best_pid=','.join(map(str, pids))))
                continue
        elif cris_row.t and cris_row.t in title_to_project_id:
            pids = title_to_project_id[cris_row.t]
            if len(pids) == 1:
                target_pid, method = pids[0], 'title_exact'
            else:
                stats['ambiguous_title'] += 1
                report_rows.append(_report_row(cris_row, 'ambiguous_title_match', None, None,
                                                best_pid=','.join(map(str, pids))))
                continue
        elif cris_row.t:
            toks = title_tokens(cris_row.t)
            best_pid, best_score = None, 0.0
            for pid, mtoks in main_titles:
                score = jaccard(toks, mtoks)
                if score > best_score:
                    best_pid, best_score = pid, score
            if best_score >= fuzzy_threshold:
                target_pid, method = best_pid, 'title_fuzzy'
            elif best_score >= new_row_min_score:
                best_title = next((t for pid, t in zip(main['project_id'], main['title_norm']) if pid == best_pid), '')
                report_rows.append(_report_row(cris_row, 'ambiguous_title_fuzzy', best_title, best_score,
                                                best_pid=best_pid))
                continue
            elif _exists_in_full_xlsx(cris_row, full_index, fuzzy_threshold):
                report_rows.append(_report_row(cris_row, 'exists_in_xlsx_but_not_closed', None, None))
                continue
            else:
                new_candidates.append(cris_row)
                continue
        else:
            if _exists_in_full_xlsx(cris_row, full_index, fuzzy_threshold):
                report_rows.append(_report_row(cris_row, 'exists_in_xlsx_but_not_closed', None, None))
                continue
            new_candidates.append(cris_row)
            continue

        if target_pid in match_of_project_id:
            # Two CRIS rows mapping to the same project: keep the more complete one.
            prev = match_of_project_id[target_pid]
            prev_score = sum(bool(str(getattr(prev, c, ''))) for c in ('cris_abstract', 'cris_keywords'))
            new_score = sum(bool(getattr(cris_row, c, '')) for c in ('cris_abstract', 'cris_keywords'))
            if new_score <= prev_score:
                continue
        match_of_project_id[target_pid] = cris_row
        method_of_project_id[target_pid] = method

    # stats reflects only the final winner per project_id (a project_id can be
    # claimed by more than one CRIS row across different methods; counting
    # incrementally as each claim came in would double-count losers that get
    # displaced later), so tally it from method_of_project_id, not in-loop.
    for m in ('code', 'title_exact', 'title_fuzzy'):
        stats[m] = sum(1 for v in method_of_project_id.values() if v == m)

    # Merge matched CRIS data onto main
    for col in CRIS_ENRICH_COLS:
        main[col] = ''
    main['cris_coinvestigator_count_mismatch'] = False
    main['cris_match_method'] = ''
    for pid, cris_row in match_of_project_id.items():
        idx = main.index[main['project_id'] == pid]
        for col in CRIS_ENRICH_COLS:
            main.loc[idx, col] = getattr(cris_row, col)
        main.loc[idx, 'cris_match_method'] = method_of_project_id[pid]

    main = main.drop(columns=['codigo_actividad_norm', 'codigo_campus_norm'])
    return main, stats, new_candidates, report_rows


def _report_row(cris_row, reason, best_title, best_score, best_pid=None):
    return {
        'cris_uuid': getattr(cris_row, 'cris_uuid', ''),
        'cris_internalid': getattr(cris_row, 'internalid', ''),
        'cris_title': getattr(cris_row, 'cris_title', ''),
        'cris_start_date': getattr(cris_row, 'cris_start_date', ''),
        'cris_status': getattr(cris_row, 'cris_status', ''),
        'reason': reason,
        'best_match_project_id': best_pid if best_pid is not None else '',
        'best_match_title_norm': best_title or '',
        'best_match_score': round(best_score, 3) if best_score is not None else '',
        'action': '',
        'target_project_id': '',
        'notes': '',
    }


def _row_year(cris_row):
    m = re.match(r'^(\d{4})', getattr(cris_row, 'cris_start_date', '') or '')
    return int(m.group(1)) if m else None


def _build_project_row(cris_row, project_id: int, main_columns, year, match_method: str) -> dict:
    title = getattr(cris_row, 'cris_title', '')
    row = {c: '' for c in main_columns}
    row.update({
        'project_id': project_id,
        'codigo_actividad': '',
        'cod_aeri': '',
        'codigo_campus': '',
        'year': year if year is not None else '',
        'title': title,
        'title_norm': norm_text(title),
        'status': '5. Cerrado',
        'coordinator_original': getattr(cris_row, 'cris_coordinator', ''),
        'coordinator_norm': norm_text(getattr(cris_row, 'cris_coordinator', '')),
        'source': 'CRIS',
        'cris_match_method': match_method,
    })
    for col in CRIS_ENRICH_COLS:
        row[col] = getattr(cris_row, col, '')
    return row


def build_new_rows(new_candidates, main, next_id: int, year_start: int, report_rows: list):
    """CRIS-only projects become new project rows, but only when they look
    like a genuinely closed project in the same universe 01_build_pipeline.py
    keeps (status concluido, year >= year_start). Everything else is reported.
    Returns (rows, next_id) so a caller can keep appending (e.g. forced rows).
    """
    rows = []
    for cris_row in new_candidates:
        status = getattr(cris_row, 'cris_status', '')
        year = _row_year(cris_row)
        if status != 'concluido':
            report_rows.append(_report_row(cris_row, f'excluded_status_{status or "desconocido"}', None, None))
            continue
        if year is None or year < year_start:
            report_rows.append(_report_row(cris_row, 'excluded_no_year_or_before_year_start', None, None))
            continue
        rows.append(_build_project_row(cris_row, next_id, main.columns, year, 'new_row'))
        next_id += 1
    return rows, next_id


# --- Manual overrides -------------------------------------------------------
# A small human-in-the-loop escape hatch for the CRIS rows the automatic
# matcher can't confidently resolve (ambiguous titles, code collisions).
# Workflow:
#   1. Run the script once; it writes <output>_overrides_template.csv listing
#      every ambiguous/collision row with a suggested best match.
#   2. Copy that file somewhere you control (it gets regenerated -- and
#      overwritten -- on every run), fill in `action` per row:
#        match -> same project; also fill `target_project_id`
#        new   -> genuinely a different/new project; add it as a new row
#        skip  -> leave unresolved (default; same as doing nothing)
#   3. Re-run with --overrides pointing at your filled-in copy.

VALID_OVERRIDE_ACTIONS = {'match', 'new', 'skip'}


def load_overrides(path: Path) -> dict:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = {'cris_uuid', 'action'} - set(df.columns)
    if missing:
        raise ValueError(f'El archivo de overrides no tiene las columnas requeridas: {sorted(missing)}')
    overrides = {}
    for r in df.itertuples():
        uuid = r.cris_uuid.strip()
        action = r.action.strip().lower()
        if not uuid or not action:
            continue
        if action not in VALID_OVERRIDE_ACTIONS:
            raise ValueError(f"Accion invalida '{action}' para cris_uuid={uuid}; use match/new/skip.")
        target = getattr(r, 'target_project_id', '').strip()
        if action == 'match' and not target:
            raise ValueError(f'action=match requiere target_project_id (cris_uuid={uuid}).')
        overrides[uuid] = {'action': action, 'target_project_id': int(target) if target else None}
    return overrides


def apply_overrides(cris: pd.DataFrame, overrides: dict, valid_project_ids: set):
    """Split CRIS rows into (remaining_for_auto_matching, manual_matches,
    forced_new, extra_report_rows) based on a human-filled overrides dict."""
    if not overrides:
        return cris, [], [], []
    manual_matches, forced_new, extra_report_rows = [], [], []
    handled_uuids = set()
    for cris_row in cris.itertuples():
        ov = overrides.get(cris_row.cris_uuid)
        if ov is None:
            continue
        handled_uuids.add(cris_row.cris_uuid)
        if ov['action'] == 'skip':
            extra_report_rows.append(_report_row(cris_row, 'manual_skip', None, None))
        elif ov['action'] == 'new':
            forced_new.append(cris_row)
        elif ov['action'] == 'match':
            pid = ov['target_project_id']
            if pid not in valid_project_ids:
                extra_report_rows.append(_report_row(
                    cris_row, 'invalid_override_target_project_id', None, None, best_pid=pid))
                continue
            manual_matches.append((cris_row, pid))
    remaining = cris[~cris['cris_uuid'].isin(handled_uuids)].reset_index(drop=True)
    return remaining, manual_matches, forced_new, extra_report_rows


def write_overrides_template(report_rows: list, path: Path) -> int:
    ambiguous_reasons = {'ambiguous_title_fuzzy', 'ambiguous_title_match', 'ambiguous_code_match'}
    rows = [r for r in report_rows if r['reason'] in ambiguous_reasons]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=[
        'cris_uuid', 'cris_internalid', 'cris_title', 'cris_start_date', 'cris_status', 'reason',
        'best_match_project_id', 'best_match_title_norm', 'best_match_score',
        'action', 'target_project_id', 'notes',
    ]).to_csv(path, index=False, encoding='utf-8-sig')
    return len(rows)


def merge_cris_into(main_csv: Path, cris_csv: Path, xlsx_path: Path, output_csv: Path, report_csv: Path,
                    overrides_path: Path | None = None, template_path: Path | None = None,
                    fuzzy_threshold: float = 0.65, new_row_min_score: float = 0.35,
                    year_start: int = 2010, make_xlsx: bool = True) -> dict:
    main = pd.read_csv(main_csv, dtype=str, keep_default_na=False)
    main['project_id'] = main['project_id'].astype(int)
    if 'source' not in main.columns:
        main['source'] = 'VRI'

    cris = load_cris(cris_csv)
    full_index = load_full_project_index(xlsx_path)

    overrides = load_overrides(overrides_path) if overrides_path else {}
    cris, manual_matches, forced_new, override_report_rows = apply_overrides(
        cris, overrides, valid_project_ids=set(main['project_id']))
    if overrides:
        print(f'  Overrides: {len(manual_matches)} match, {len(forced_new)} new, '
              f'{len(override_report_rows)} skip/invalidos', flush=True)

    merged, stats, new_candidates, report_rows = match_and_merge(
        main, cris, full_index, fuzzy_threshold, new_row_min_score)
    report_rows += override_report_rows

    manual_applied = 0
    for cris_row, pid in manual_matches:
        idx = merged.index[merged['project_id'] == pid]
        if idx.empty:
            report_rows.append(_report_row(cris_row, 'invalid_override_target_project_id', None, None, best_pid=pid))
            continue
        existing_method = merged.loc[idx, 'cris_match_method'].iloc[0]
        if existing_method:
            # Some other CRIS row already auto-matched this project (e.g. by
            # exact title) -- never silently clobber a higher-confidence
            # automatic match. Report it instead of guessing.
            report_rows.append(_report_row(
                cris_row, f'override_conflicts_with_{existing_method}_match', None, None, best_pid=pid))
            continue
        for col in CRIS_ENRICH_COLS:
            merged.loc[idx, col] = getattr(cris_row, col)
        merged.loc[idx, 'cris_match_method'] = 'manual_match'
        manual_applied += 1

    next_id = (merged['project_id'].astype(int).max() if len(merged) else 0) + 1
    new_rows, next_id = build_new_rows(new_candidates, merged, next_id, year_start, report_rows)
    for cris_row in forced_new:
        new_rows.append(_build_project_row(cris_row, next_id, merged.columns, _row_year(cris_row), 'new_row_manual'))
        next_id += 1
    if new_rows:
        merged = pd.concat([merged, pd.DataFrame(new_rows)], ignore_index=True)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_csv, index=False, encoding='utf-8-sig')

    report_csv.parent.mkdir(parents=True, exist_ok=True)
    report_df = pd.DataFrame(report_rows)
    report_df.to_csv(report_csv, index=False, encoding='utf-8-sig')

    template_path = template_path or report_csv.with_name(report_csv.stem + '_template.csv')
    n_template = write_overrides_template(report_rows, template_path)

    xlsx_out_path = None
    if make_xlsx:
        xlsx_out_path = output_csv.with_suffix('.xlsx')
        write_colored_xlsx(merged, xlsx_out_path, title='Proyectos + enriquecimiento CRIS')

    return {
        'main_csv': str(main_csv),
        'output_csv': str(output_csv),
        'output_xlsx': str(xlsx_out_path) if xlsx_out_path else None,
        'report_csv': str(report_csv),
        'template_csv': str(template_path),
        'template_rows': n_template,
        'rows_total': int(len(merged)),
        'rows_matched_code': stats['code'],
        'rows_matched_title_exact': stats['title_exact'],
        'rows_matched_title_fuzzy': stats['title_fuzzy'],
        'rows_matched_manual': manual_applied,
        'rows_new_from_cris': len(new_rows),
        'rows_ambiguous_or_excluded': len(report_rows),
        'coinvestigator_count_mismatches': int(merged['cris_coinvestigator_count_mismatch'].sum()),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Enriquece el maestro de proyectos con el export CRIS (abstract, '
                    'palabras clave, coinvestigadores, fechas, OCDE) y agrega proyectos nuevos.')
    parser.add_argument('--main', type=Path, default=OUT / '01_projects_closed.csv',
                        help='CSV del maestro de proyectos a enriquecer.')
    parser.add_argument('--cris', type=Path, default=None,
                        help='CSV export de CRIS (por defecto, el mas reciente en datos/).')
    parser.add_argument('--xlsx', type=Path, default=XLSX_INPUT,
                        help='Excel VRI completo, usado solo para distinguir proyectos '
                            'realmente nuevos de proyectos existentes pero fuera del maestro cerrado '
                            '(por defecto, datos/informacion_proyecto_pulso.xlsx).')
    parser.add_argument('--output', type=Path, default=None,
                        help='CSV de salida (por defecto, <main>_con_cris.csv).')
    parser.add_argument('--report', type=Path, default=None,
                        help='CSV de filas CRIS ambiguas/excluidas para revision manual '
                            '(por defecto, <main>_cris_review.csv).')
    parser.add_argument('--overrides', type=Path, default=None,
                        help='CSV con decisiones manuales (columnas cris_uuid, action, '
                            'target_project_id) para resolver filas ambiguas. Ver el archivo '
                            '*_cris_review_template.csv generado por una corrida previa.')
    parser.add_argument('--fuzzy-threshold', type=float, default=0.65,
                        help='Umbral de Jaccard de titulo para aceptar un match difuso (default 0.65).')
    parser.add_argument('--new-row-min-score', type=float, default=0.35,
                        help='Por debajo de este Jaccard, una fila CRIS sin match se considera '
                            'proyecto nuevo; entre este valor y --fuzzy-threshold se reporta como ambigua.')
    parser.add_argument('--year-start', type=int, default=2010,
                        help='Año minimo para aceptar un proyecto CRIS nuevo (default 2010, igual que el pipeline).')
    parser.add_argument('--no-xlsx', action='store_true', help='No genera el XLSX coloreado.')
    args = parser.parse_args(argv)

    if not args.main.exists():
        parser.error(f'No existe {args.main}. Corre primero scripts/pipeline/01_build_pipeline.py.')
    cris_path = args.cris or find_default_cris_csv()
    if cris_path is None or not Path(cris_path).exists():
        parser.error('No se encontro un CSV de CRIS. Indique --cris con la ruta al archivo.')
    if not args.xlsx.exists():
        parser.error(f'No existe {args.xlsx}. Indique --xlsx con la ruta al Excel VRI.')
    if args.overrides and not args.overrides.exists():
        parser.error(f'No existe el archivo de overrides: {args.overrides}')

    output = args.output or args.main.with_name(args.main.stem + '_con_cris.csv')
    report = args.report or args.main.with_name(args.main.stem + '_cris_review.csv')

    print(f'Maestro: {args.main}', flush=True)
    print(f'CRIS: {cris_path}', flush=True)
    if args.overrides:
        print(f'Overrides: {args.overrides}', flush=True)
    stats = merge_cris_into(
        args.main, Path(cris_path), args.xlsx, output, report,
        overrides_path=args.overrides,
        fuzzy_threshold=args.fuzzy_threshold, new_row_min_score=args.new_row_min_score,
        year_start=args.year_start, make_xlsx=not args.no_xlsx)

    print(
        f"- {stats['rows_total']} filas totales "
        f"({stats['rows_matched_code']} por codigo, {stats['rows_matched_title_exact']} por titulo exacto, "
        f"{stats['rows_matched_title_fuzzy']} por titulo difuso, {stats['rows_matched_manual']} por override manual, "
        f"{stats['rows_new_from_cris']} filas nuevas de CRIS)",
        flush=True)
    print(
        f"- {stats['rows_ambiguous_or_excluded']} filas CRIS ambiguas/excluidas -> {Path(stats['report_csv']).name}",
        flush=True)
    print(
        f"- {stats['template_rows']} filas ambiguas listas para revisar -> {Path(stats['template_csv']).name} "
        f"(llenar action/target_project_id y volver a correr con --overrides)", flush=True)
    print(
        f"- {stats['coinvestigator_count_mismatches']} proyectos con conteo nombres/roles de "
        f"coinvestigadores desalineado (cris_coinvestigator_count_mismatch=True)", flush=True)
    print(f"-> {Path(stats['output_csv']).name}" + (f" (+ {Path(stats['output_xlsx']).name})" if stats['output_xlsx'] else ''), flush=True)


if __name__ == '__main__':
    main()

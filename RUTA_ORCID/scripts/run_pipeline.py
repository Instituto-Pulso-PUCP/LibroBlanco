
from pathlib import Path
import sqlite3, re, unicodedata, json
from difflib import SequenceMatcher
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "datos" / "informacion_proyecto_pulso.xlsx"
OUT = ROOT / "salidas"
DB = OUT / "libro_blanco.db"

PROJECT_SHEET = "PROYECTOS"
RESULTS_SHEET = "PROY_RESULTADOS"
SCOPUS_SHEET = "Pubs_SCOPUS"
WOS_SHEET = "Pubs_WoS"
RI_SHEET = "Pubs_RI"
ORCID_SHEET = "ORCID PUCP"

PUBLICATION_RESULT_TYPES = {
    'Artículo indizado',
    'Artículo arbitrado',
    'Capítulo de libro arbitrado',
    'Capítulo de libro indizado',
    'Libro arbitrado',
    'Libro indizado',
    'Editor de libro',
    'Memoria en anales de congreso arbitrado',
    'Memoria en anales de congreso indizado'
}

CONFIG = {
    "year_start": 2010,
    "closed_status": "5. Cerrado",
    "max_years_after_project": 5,
    "weights": {
        "responsible_is_author": 50,
        "published_same_year": 20,
        "published_1_2_years_after": 18,
        "published_3_5_years_after": 12,
        "source_ri": 15,
        "source_scopus": 10,
        "source_wos": 10,
        "title_similarity_max": 25
    }
}

STOPWORDS = set('''de del la el los las y e en para por con sin un una unos unas the and of in on for to a an from via as at into sobre entre hacia desde mediante frente al ante que se su sus or o'''.split())

def norm_text(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = str(x).strip().upper()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def norm_doi(x):
    s = str(x).strip().lower() if x is not None and not pd.isna(x) else ""
    if s in {"", "-", "nan", "none"}: return ""
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s)
    return s.strip().rstrip('.')

def name_aliases(name):
    raw = "" if name is None or pd.isna(name) else str(name).strip()
    aliases = {norm_text(raw)} if raw else set()
    if ',' in raw:
        parts = [p.strip() for p in raw.split(',', 1)]
        if len(parts) == 2:
            aliases.add(norm_text(parts[1] + ' ' + parts[0]))
    return {a for a in aliases if a}

def split_authors_scopus(authors):
    if authors is None or pd.isna(authors): return []
    return [a.strip() for a in str(authors).split('|') if a.strip()]

def split_ids(ids):
    if ids is None or pd.isna(ids): return []
    return [i.strip() for i in str(ids).split('|') if i.strip() and i.strip() != '-']

def pub_key(source, doi, title_norm, year):
    doi = norm_doi(doi)
    if doi: return "doi:" + doi
    return f"titleyear:{title_norm}|{int(year) if pd.notna(year) else ''}"

def token_jaccard(a,b):
    ta = {t for t in norm_text(a).split() if len(t)>2 and t not in STOPWORDS}
    tb = {t for t in norm_text(b).split() if len(t)>2 and t not in STOPWORDS}
    if not ta or not tb: return 0.0
    return len(ta & tb)/len(ta | tb)

def title_score(proj_title, pub_title):
    nt1, nt2 = norm_text(proj_title), norm_text(pub_title)
    seq = SequenceMatcher(None, nt1, nt2).ratio() if nt1 and nt2 else 0
    jac = token_jaccard(proj_title, pub_title)
    return round(max(seq*0.5, jac), 4)

def connect():
    if DB.exists(): DB.unlink()
    return sqlite3.connect(DB)

def build():
    OUT.mkdir(exist_ok=True)
    con = connect()
    print('01 projects...', flush=True)
    # Projects
    projects = pd.read_excel(INPUT, sheet_name=PROJECT_SHEET)
    projects['year'] = pd.to_numeric(projects['Año'], errors='coerce').astype('Int64')
    projects['status'] = projects['Estado'].astype(str).str.strip()
    closed = projects[(projects['year'] >= CONFIG['year_start']) & (projects['status'] == CONFIG['closed_status'])].copy()
    closed['project_id'] = range(1, len(closed)+1)
    closed['cod_aeri'] = closed['COD_AERI'].astype(str).str.strip()
    closed['coordinator_norm'] = closed['COORDINADOR DE LA INVESTIGACIÓN'].map(norm_text)
    closed['title_norm'] = closed['Título'].map(norm_text)
    project_cols = {
        'project_id':'project_id','CÓDIGO DE PROYECTO':'codigo_actividad','cod_aeri':'cod_aeri','CÓDIGO CAMPUS':'codigo_campus','year':'year','Título':'title','title_norm':'title_norm','Estado':'status','Tipo de Proyecto':'project_type','Área de Conocimiento':'knowledge_area','LÍNEA DE INVESTIGACIÓN HOMOLOGADA':'research_line','UNIDAD EJECUTORA':'executing_unit','SECCIÓN EJECUTORA':'executing_section','COORDINADOR DE LA INVESTIGACIÓN':'coordinator_original','coordinator_norm':'coordinator_norm','UNIDAD DE GESTIÓN':'management_unit','Tipo de Financiamiento':'funding_type','Entidad Financiadora':'funder'
    }
    closed_out = closed[list(project_cols.keys())].rename(columns=project_cols)
    closed_out.to_sql('projects', con, index=False)
    closed_out.to_csv(OUT/'01_projects_closed.csv', index=False, encoding='utf-8-sig')

    print('02 investigators...', flush=True)
    # ORCID
    orcid = pd.read_excel(INPUT, sheet_name=ORCID_SHEET)
    orcid['name_norm'] = orcid['Nombres'].map(norm_text)
    orcid_out = pd.DataFrame({
        'investigator_id': range(1, len(orcid)+1),
        'name_original': orcid['Nombres'],
        'name_norm': orcid['name_norm'],
        'orcid': orcid['Código ORCID'],
        'codigo_pucp': orcid['código PUCP'],
        'dni': orcid['dni'],
        'source_seed': 'ORCID PUCP'
    })
    # RI persons not in ORCID exact norm
    ri = pd.read_excel(INPUT, sheet_name=RI_SHEET)
    ri_people = ri[['idperson','nombre','doc']].drop_duplicates().copy()
    ri_people['name_norm'] = ri_people['nombre'].map(norm_text)
    existing = set(orcid_out['name_norm'])
    add = ri_people[~ri_people['name_norm'].isin(existing)].copy()
    start = len(orcid_out)+1
    ri_add = pd.DataFrame({
        'investigator_id': range(start, start+len(add)),
        'name_original': add['nombre'],
        'name_norm': add['name_norm'],
        'orcid': '',
        'codigo_pucp': '',
        'dni': add['doc'],
        'source_seed': 'RI'
    })
    inv = pd.concat([orcid_out, ri_add], ignore_index=True)
    inv.to_sql('investigators', con, index=False)
    inv.to_csv(OUT/'02_investigators_master.csv', index=False, encoding='utf-8-sig')
    orcid_lookup = {r.name_norm: str(r.orcid).strip() for r in inv.itertuples()
                    if r.name_norm and str(r.orcid).strip() not in ('', 'nan', '-', 'None')}
    name_to_investigator = {r.name_norm: int(r.investigator_id) for r in inv.itertuples() if r.name_norm}

    # aliases
    aliases=[]
    for r in inv.itertuples():
        for a in name_aliases(r.name_original):
            aliases.append([r.investigator_id, r.name_original, a, r.source_seed])
    alias_df = pd.DataFrame(aliases, columns=['investigator_id','alias_original','alias_norm','source'])
    alias_df.drop_duplicates().to_sql('investigator_aliases', con, index=False)

    print('03 publications/authorships...', flush=True)
    # Publications and sources
    source_rows=[]
    authorship_rows=[]
    def add_pub(source, row_idx, doi, title, year, journal='', abstract='', keywords='', raw=None):
        tn=norm_text(title); dk=norm_doi(doi); key=pub_key(source, dk, tn, year)
        source_rows.append({'source_record_id': f'{source}:{row_idx}', 'source':source, 'master_key':key, 'doi':dk, 'title':title, 'title_norm':tn, 'year': int(year) if pd.notna(year) else None, 'journal':journal, 'abstract':abstract, 'keywords':keywords, 'raw_json': ''})
        return key

    sc = pd.read_excel(INPUT, sheet_name=SCOPUS_SHEET)
    for i,r in sc.iterrows():
        key = add_pub('SCOPUS', i, r.get('DOI'), r.get('Title'), r.get('Year'), r.get('Scopus Source title'), r.get('Abstract'), r.get('Topic name'), r.to_dict())
        authors = split_authors_scopus(r.get('Authors'))
        ids = split_ids(r.get('Scopus Author Ids'))
        for pos,a in enumerate(authors, start=1):
            an = norm_text(a)
            authorship_rows.append({'master_key':key,'source':'SCOPUS','author_order':pos,'author_name_raw':a,'author_name_norm':an,'external_author_id':ids[pos-1] if pos-1 < len(ids) else '', 'investigator_id': name_to_investigator.get(an)})
    wos = pd.read_excel(INPUT, sheet_name=WOS_SHEET)
    for i,r in wos.iterrows():
        kw = ' | '.join([str(r.get('keywords') or ''), str(r.get('keywords_plus') or '')]).strip(' |')
        add_pub('WOS', i, r.get('doi'), r.get('title'), r.get('pub_year'), r.get('source'), r.get('abstract'), kw, r.to_dict())
    for i,r in ri.iterrows():
        key = add_pub('RI', i, r.get('doi'), r.get('titulo'), r.get('año'), r.get('medio_div'), '', r.get('key_words'), r.to_dict())
        an = norm_text(r.get('nombre'))
        authorship_rows.append({'master_key':key,'source':'RI','author_order':1,'author_name_raw':r.get('nombre'),'author_name_norm':an,'external_author_id':str(r.get('idperson') or ''), 'investigator_id': name_to_investigator.get(an)})

    print('04 source_rows built', len(source_rows), len(authorship_rows), flush=True)
    src = pd.DataFrame(source_rows)
    # aggregate master publications
    def first_nonempty(s):
        for v in s:
            if v is not None and not pd.isna(v) and str(v).strip() not in {'','-','nan'}: return v
        return ''
    pubs = src.groupby('master_key', as_index=False).agg({
        'doi': first_nonempty, 'title': first_nonempty, 'title_norm': first_nonempty, 'year': 'min', 'journal': first_nonempty, 'abstract': first_nonempty, 'keywords': first_nonempty, 'source':'nunique'
    }).rename(columns={'source':'source_count'})
    flags = src.pivot_table(index='master_key', columns='source', values='source_record_id', aggfunc='count', fill_value=0).reset_index()
    pubs = pubs.merge(flags, on='master_key', how='left')
    for c in ['RI','SCOPUS','WOS']:
        if c not in pubs: pubs[c]=0
        pubs[c] = pubs[c].fillna(0).astype(int)
    pubs['publication_id'] = range(1, len(pubs)+1)
    pubs = pubs[['publication_id','master_key','doi','title','title_norm','year','journal','abstract','keywords','source_count','RI','SCOPUS','WOS']]
    print('05 pubs master', len(pubs), flush=True)
    pubs.to_sql('publications', con, index=False)
    pubs.to_csv(OUT/'03_publications_master.csv', index=False, encoding='utf-8-sig')
    src = src.merge(pubs[['publication_id','master_key']], on='master_key', how='left')
    src.to_sql('publication_sources', con, index=False)

    auth = pd.DataFrame(authorship_rows).merge(pubs[['publication_id','master_key']], on='master_key', how='left')
    auth = auth[['publication_id','master_key','source','author_order','author_name_raw','author_name_norm','external_author_id','investigator_id']]
    print('06 auth rows', len(auth), flush=True)
    auth.to_sql('authorships', con, index=False)
    auth.to_csv(OUT/'04_authorships.csv', index=False, encoding='utf-8-sig')

    print('07 project-results ground truth...', flush=True)
    results = pd.read_excel(INPUT, sheet_name=RESULTS_SHEET)
    results['cod_aeri'] = results['COD_AERI'].astype(str).str.strip()
    results['doi_norm'] = results['DOI'].map(norm_doi)
    gt = closed_out[['project_id','cod_aeri','codigo_campus','year','title','coordinator_original','coordinator_norm']].merge(
        results,
        on='cod_aeri',
        how='inner'
    )
    doi_lookup = pubs[['publication_id','doi']].assign(doi_norm=pubs['doi'].map(norm_doi))
    doi_lookup = doi_lookup[doi_lookup['doi_norm'] != ''][['publication_id','doi_norm']].drop_duplicates(['doi_norm'])
    gt = gt.merge(
        doi_lookup,
        on='doi_norm',
        how='left'
    )
    gt['publication_id'] = gt['publication_id'].astype('Int64')
    gt['match_method'] = gt['publication_id'].notna().map({True: 'doi', False: ''})
    gt = gt.rename(columns={
        'year': 'project_year',
        'title': 'project_title',
        'tipo': 'result_type',
        'cat_e': 'result_category',
        'producto_e': 'result_title',
        'otros_e': 'result_other',
        'año_pub': 'result_year',
        'DOI': 'doi_raw',
        'issn': 'issn_raw',
        'isbn': 'isbn_raw',
        'estado': 'result_status',
        'evidencia': 'result_evidence',
        'eid': 'scopus_eid',
        'journal': 'journal_raw',
        'quartil': 'quartile_raw',
        'citation': 'citation_raw',
        'citation_fw': 'citation_fw_raw',
        'citation_fa': 'citation_fa_raw',
        'cit_policy': 'citation_policy_raw',
        'conv': 'call_name',
        'idperson': 'result_idperson',
        'coordinador': 'result_coordinator'
    })
    gt['coordinator_orcid'] = gt['coordinator_norm'].map(orcid_lookup).fillna('')
    gt_cols = [
        'project_id','cod_aeri','codigo_campus','project_year','project_title','coordinator_original','coordinator_orcid',
        'cod_prod','result_type','result_category','result_title','result_other','result_year',
        'equivalencia','doi_raw','doi_norm','issn_raw','isbn_raw','result_status','result_evidence',
        'scopus_eid','journal_raw','quartile_raw','citation_raw','citation_fw_raw','citation_fa_raw',
        'citation_policy_raw','call_name','result_idperson','result_coordinator','publication_id','match_method'
    ]
    gt = gt[gt_cols].sort_values(['project_id','cod_prod']).reset_index(drop=True)
    gt.to_sql('project_results_ground_truth', con, index=False, if_exists='replace')
    gt.to_csv(OUT/'06_project_results_ground_truth.csv', index=False, encoding='utf-8-sig')

    gt_publications = gt[gt['result_type'].isin(PUBLICATION_RESULT_TYPES)].copy()
    gt_publications.to_sql('project_publication_ground_truth', con, index=False, if_exists='replace')
    gt_publications.to_csv(OUT/'07_project_publication_ground_truth.csv', index=False, encoding='utf-8-sig')

    print('08 base built; matching candidates will be generated by 02_match_candidates.py', flush=True)
    # Basic empty candidates placeholder; run 02_match_candidates.py for the full matching stage.
    candidates = pd.DataFrame()

    summary = {
        'projects_total': int(len(projects)),
        'projects_closed_since_2010': int(len(closed_out)),
        'investigators_master': int(len(inv)),
        'publication_source_records': int(len(src)),
        'publications_master': int(len(pubs)),
        'authorship_rows': int(len(auth)),
        'ground_truth_rows': int(len(gt)),
        'ground_truth_projects': int(gt['project_id'].nunique()),
        'ground_truth_rows_with_doi': int((gt['doi_norm'] != '').sum()),
        'ground_truth_rows_matched_by_doi': int(gt['publication_id'].notna().sum()),
        'ground_truth_publication_rows': int(len(gt_publications)),
        'ground_truth_publication_projects': int(gt_publications['project_id'].nunique()),
        'ground_truth_publication_rows_matched_by_doi': int(gt_publications['publication_id'].notna().sum()),
        'candidate_links_v1': int(len(candidates)),
        'candidate_links_high_confidence': int((candidates['confidence']=='Alta').sum()) if not candidates.empty else 0,
        'candidate_links_medium_confidence': int((candidates['confidence']=='Media').sum()) if not candidates.empty else 0,
        'candidate_links_low_confidence': int((candidates['confidence']=='Baja').sum()) if not candidates.empty else 0,
        'important_note': 'Pubs_WoS does not contain author names in the provided dataset; WoS only contributes as a publication source unless matched by DOI/title to RI or Scopus.'
    }
    with open(OUT/'00_summary.json','w',encoding='utf-8') as f: json.dump(summary,f,ensure_ascii=False,indent=2)
    con.close()
    return summary

if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False, indent=2))

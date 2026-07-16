from pathlib import Path
import sqlite3, pandas as pd, re, unicodedata, json
from difflib import SequenceMatcher
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'salidas'; DB=OUT/'libro_blanco.db'
STOP=set('de del la el los las y e en para por con sin un una unos unas the and of in on for to a an from via as at into sobre entre hacia desde mediante frente al ante que se su sus or o'.upper().split())
def norm_text(x):
    if x is None or pd.isna(x): return ''
    s=str(x).strip().upper(); s=unicodedata.normalize('NFKD',s); s=''.join(c for c in s if not unicodedata.combining(c)); s=re.sub(r'[^A-Z0-9 ]+',' ',s); return re.sub(r'\s+',' ',s).strip()
def token_jaccard(a,b):
    ta={t for t in norm_text(a).split() if len(t)>2 and t not in STOP}; tb={t for t in norm_text(b).split() if len(t)>2 and t not in STOP}
    return len(ta&tb)/len(ta|tb) if ta and tb else 0.0
def title_score(a,b):
    nt1,nt2=norm_text(a),norm_text(b); seq=SequenceMatcher(None,nt1,nt2).ratio() if nt1 and nt2 else 0; jac=token_jaccard(a,b); return round(max(seq*0.5,jac),4)
def run():
    con=sqlite3.connect(DB)
    auth=pd.read_sql('select * from authorships',con)
    pubs=pd.read_sql('select * from publications',con)
    proj=pd.read_sql('select * from projects',con)
    inv=pd.read_sql('select * from investigators',con)
    gt_publications=pd.read_sql('select project_id, publication_id from project_publication_ground_truth where publication_id is not null', con)
    name_to_inv=dict(zip(inv.name_norm, inv.investigator_id))
    author_pub=auth.dropna(subset=['publication_id']).copy(); author_pub['publication_id']=author_pub.publication_id.astype(int)
    by_author={k:v for k,v in author_pub.groupby('author_name_norm')}
    # Avoid very broad fuzzy matching in v1; exact normalized author/coordinator only.
    pub_map=pubs.set_index('publication_id').to_dict('index')
    cand=[]; seen=set()
    for p in proj.itertuples():
        if not p.coordinator_norm: continue
        rows=by_author.get(p.coordinator_norm)
        if rows is None: continue
        pyear=int(p.year) if pd.notna(p.year) else None
        for a in rows.itertuples():
            pair=(int(p.project_id), int(a.publication_id))
            if pair in seen: continue
            pub=pub_map.get(int(a.publication_id));
            if not pub: continue
            y=pub.get('year')
            if pyear and y and (y < pyear or y > pyear+5): continue
            seen.add(pair)
            delta=(int(y)-pyear) if pyear and y else None
            score=50; ev=['responsable_autor']
            if delta is not None:
                if delta==0: score+=20; ev.append('publicado_mismo_anio')
                elif 1<=delta<=2: score+=18; ev.append('publicado_1_2_anios_despues')
                elif 3<=delta<=5: score+=12; ev.append('publicado_3_5_anios_despues')
            if pub.get('RI',0)>0: score+=15; ev.append('fuente_RI')
            if pub.get('SCOPUS',0)>0: score+=10; ev.append('fuente_SCOPUS')
            if pub.get('WOS',0)>0: score+=10; ev.append('fuente_WOS')
            sim=title_score(p.title,pub.get('title','')); score+=round(sim*25,2)
            if sim>=.20: ev.append(f'similitud_tematica_{sim:.2f}')
            cand.append({'project_id':p.project_id,'codigo_campus':p.codigo_campus,'project_year':p.year,'project_title':p.title,'coordinator_original':p.coordinator_original,'publication_id':int(a.publication_id),'publication_year':y,'publication_title':pub.get('title',''),'doi':pub.get('doi',''),'source_RI':pub.get('RI',0),'source_SCOPUS':pub.get('SCOPUS',0),'source_WOS':pub.get('WOS',0),'matched_author':a.author_name_raw,'year_delta':delta,'title_similarity':sim,'score':round(score,2),'confidence':'Alta' if score>=85 else ('Media' if score>=65 else 'Baja'),'evidence':' | '.join(ev)})
    c=pd.DataFrame(cand).drop_duplicates(['project_id','publication_id']) if cand else pd.DataFrame()
    if not c.empty: c=c.sort_values(['score','project_id'],ascending=[False,True])
    c.to_sql('project_publication_candidates',con,index=False,if_exists='replace')
    c.to_csv(OUT/'05_project_publication_candidates_v1.csv',index=False,encoding='utf-8-sig')
    gt_pairs = set((int(r.project_id), int(r.publication_id)) for r in gt_publications.drop_duplicates().itertuples())
    cand_pairs = set((int(r.project_id), int(r.publication_id)) for r in c[['project_id','publication_id']].drop_duplicates().itertuples(index=False)) if not c.empty else set()
    matched_pairs = cand_pairs & gt_pairs
    precision_pct = round(100 * len(matched_pairs) / len(cand_pairs), 2) if cand_pairs else 0.0
    recall_pct = round(100 * len(matched_pairs) / len(gt_pairs), 2) if gt_pairs else 0.0
    summary=json.loads((OUT/'00_summary.json').read_text(encoding='utf-8')) if (OUT/'00_summary.json').exists() else {}
    summary.update({'candidate_links_v1':int(len(c)),'candidate_links_high_confidence':int((c.confidence=='Alta').sum()) if not c.empty else 0,'candidate_links_medium_confidence':int((c.confidence=='Media').sum()) if not c.empty else 0,'candidate_links_low_confidence':int((c.confidence=='Baja').sum()) if not c.empty else 0,'ground_truth_publication_pairs':int(len(gt_pairs)),'candidate_pairs_confirmed_by_ground_truth':int(len(matched_pairs)),'candidate_precision_vs_ground_truth_pct':precision_pct,'ground_truth_recall_by_candidates_pct':recall_pct,'important_note':'Pubs_WoS no contiene nombres de autores en el dataset entregado; WoS enriquece fuentes cuando el registro se consolida por DOI o título/año.'})
    (OUT/'00_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    con.close(); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': run()

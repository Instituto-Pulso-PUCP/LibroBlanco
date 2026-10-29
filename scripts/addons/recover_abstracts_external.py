"""Busca abstracts para publicaciones ligadas que la cascada dejo sin abstract.

Fuentes externas gratuitas (Semantic Scholar, Crossref, OpenAlex, Google
Books). No modifica los datos del proyecto: lee la salida de
rebuild_linked_publications.py y escribe un JSONL de resultados para revisar.
Corrida del 2026-10-11 (369 candidatas, ~5 h por los limites de Semantic
Scholar sin clave): salidas/abstracts_recuperados/.

    python scripts/addons/recover_abstracts_external.py \
        --linked salidas/07_publications_linked_full.csv \
        --out salidas/abstracts_recuperados/busqueda.jsonl
 Toda coincidencia por titulo se verifica con
rebuild_linked_publications.title_similarity >= 0.85 (el mismo control que
descarto los 98 abstracts de otra obra).
"""
import argparse, csv, html, json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "addons"))
from rebuild_linked_publications import title_similarity, load_openalex_titles  # noqa

OUT = ROOT / "salidas" / "abstracts_recuperados" / "busqueda.jsonl"
LINKED = ROOT / "salidas" / "07_publications_linked_full.csv"
MIN_SIM, MIN_CHARS = 0.85, 80
UA = {"User-Agent": "LibroBlanco-PUCP-abstract-probe/0.1"}
NOPUB = {"No publicado / presentado", "En proceso de elaboración / publicación", "Exonerado",
         "No hay evidencia"}
clean = lambda v: "" if (v or "").strip() in ("", "-", "nan", "None") else v.strip()
EVENT = re.compile(r"^(?:[IVXLC]+\s+|\d+\S*\s+)?(?:CONGRES|SIMPOSI|ENCUENTRO|JORNADA|COLOQUIO|CONFERENC|SEMINARIO|"
                   r"WORKSHOP|SYMPOSIUM|CONFERENCE|ESCUELA|FORO|TALLER)", re.I)


ORG = re.compile(r"^(SOCIEDAD|ASOCIACI|INSTITUT|UNIVERSI|COLEGIO|RED |FEDERACI)", re.I)


def paper_title(t):
    """'IX CONGRESO INTERNACIONAL DE X - TITULO REAL' -> 'TITULO REAL'."""
    parts = [p.strip() for p in re.split(r"\s[-–—:]\s", t) if p.strip()]
    if len(parts) > 1 and EVENT.match(parts[0]):
        parts = parts[1:]
        # el nombre del organizador a veces va como segundo segmento
        while len(parts) > 1 and ORG.match(parts[0]):
            parts = parts[1:]
        return " - ".join(parts)
    return t


def get(url, data=None, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={**UA, **(
                {"Content-Type": "application/json"} if data else {})})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(2 * 2 ** i)
                continue
            return None
        except Exception:
            time.sleep(2 * 2 ** i)
    return None


def strip_jats(t):
    t = re.sub(r"<[^>]+>", " ", t or "")
    t = html.unescape(re.sub(r"\s+", " ", t)).strip()
    return re.sub(r"^(abstract|resumen)[:.\s]*", "", t, flags=re.I)


def oa_abstract(inv):
    if not inv:
        return ""
    pos = sorted((p, w) for w, ps in inv.items() for p in ps)
    return " ".join(w for _p, w in pos)


# --- fuentes ----------------------------------------------------------------
def s2_doi(doi):
    r = get("https://api.semanticscholar.org/graph/v1/paper/DOI:" + urllib.parse.quote(doi)
            + "?fields=title,abstract,year")
    time.sleep(1.1)
    return r and {"title": r.get("title") or "", "abstract": r.get("abstract") or ""}


def s2_title(t):
    r = get("https://api.semanticscholar.org/graph/v1/paper/search/match?query="
            + urllib.parse.quote(t[:300]) + "&fields=title,abstract,year,externalIds")
    time.sleep(1.1)
    d = (r or {}).get("data") or []
    return [{"title": x.get("title") or "", "abstract": x.get("abstract") or "",
             "doi": (x.get("externalIds") or {}).get("DOI", "")} for x in d]


def cr_doi(doi):
    r = get("https://api.crossref.org/works/" + urllib.parse.quote(doi))
    m = (r or {}).get("message") or {}
    return m and {"title": (m.get("title") or [""])[0], "abstract": strip_jats(m.get("abstract"))}


def cr_title(t):
    r = get("https://api.crossref.org/works?rows=3&select=DOI,title,abstract&query.bibliographic="
            + urllib.parse.quote(t[:300]))
    return [{"title": (x.get("title") or [""])[0], "abstract": strip_jats(x.get("abstract")),
             "doi": x.get("DOI", "")} for x in ((r or {}).get("message") or {}).get("items", [])]


def oa_title(t):
    r = get("https://api.openalex.org/works?per-page=5&select=id,doi,title,abstract_inverted_index"
            "&search=" + urllib.parse.quote(t[:300]))
    return [{"title": x.get("title") or "", "abstract": oa_abstract(x.get("abstract_inverted_index")),
             "doi": (x.get("doi") or "").replace("https://doi.org/", "")}
            for x in (r or {}).get("results", [])]


def gbooks(isbn):
    r = get("https://www.googleapis.com/books/v1/volumes?q=isbn:" + urllib.parse.quote(isbn))
    out = []
    for it in (r or {}).get("items", [])[:3]:
        v = it.get("volumeInfo", {})
        out.append({"title": v.get("title", "") + (" " + v["subtitle"] if v.get("subtitle") else ""),
                    "abstract": strip_jats(v.get("description"))})
    return out


def first_hit(query, results, src, full=None):
    """Primer resultado con titulo verificado (contra el titulo limpio o el
    completo, el mayor); devuelve (hit, sim)."""
    for x in results or []:
        sim = max(title_similarity(query, x["title"]),
                  title_similarity(full, x["title"]) if full else 0.0)
        if sim >= MIN_SIM:
            return dict(x, source=src), sim
    return None, 0.0


# --- candidatas ---------------------------------------------------------------
def candidates():
    gt = list(csv.DictReader(open(ROOT / "salidas/07_project_publication_ground_truth.csv",
                                  encoding="utf-8-sig")))
    new = list(csv.DictReader(open(LINKED, encoding="utf-8-sig")))
    oat = load_openalex_titles()
    seen = {}
    for g, n in zip(gt, new):
        seen.setdefault(n["publication_id"], (g, n))
    out = []
    for pid, (g, n) in seen.items():
        if len(n["abstract"].strip()) >= MIN_CHARS or g["result_status"] in NOPUB or not n["title"].strip():
            continue
        title = n["title"].strip()
        doi = clean(g["doi_norm"])
        if not doi and clean(g["openalex_doi"]):
            key = (g["project_id"].strip(), g["cod_prod"].strip())
            if title_similarity(clean(g["result_title"]) or title, oat.get(key, "")) >= MIN_SIM:
                doi = clean(g["openalex_doi"]).replace("https://doi.org/", "")
        isbn = re.sub(r"[^0-9Xx]", "", clean(g["isbn_raw"]).split(";")[0].split(",")[0])
        group = "doi" if doi else ("isbn" if len(isbn) in (10, 13) else "titulo")
        out.append({"publication_id": pid, "group": group, "title": title,
                    "query": paper_title(title), "doi": doi, "isbn": isbn,
                    "type": g["result_type"], "has_kw": bool(n["keywords"].strip())})
    return out


def candidates_from_publications(path):
    """Candidatas desde un publications.csv estandar (salida de un adaptador
    de scripts/datasets/): toda fila con titulo y sin abstract util."""
    out = []
    for n in csv.DictReader(open(path, encoding="utf-8-sig")):
        title = (n.get("title") or "").strip()
        if not title or len((n.get("abstract") or "").strip()) >= MIN_CHARS:
            continue
        doi = clean(n.get("doi"))
        out.append({"publication_id": n["publication_id"], "group": "doi" if doi else "titulo",
                    "title": title, "query": paper_title(title), "doi": doi, "isbn": "",
                    "type": "", "has_kw": bool(clean(n.get("keywords")))})
    return out


def main():
    global OUT, LINKED
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--linked", type=Path, default=LINKED,
                        help="Salida de rebuild_linked_publications.py (mismo orden que el ground truth).")
    parser.add_argument("--publications", type=Path,
                        help="publications.csv estandar de otro dataset (scripts/datasets/); "
                             "reemplaza a --linked y al ground truth de PUCP.")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    OUT, LINKED = args.out, args.linked
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if OUT.exists():
        done = {json.loads(l)["publication_id"] for l in OUT.open(encoding="utf-8")}
    pool = candidates_from_publications(args.publications) if args.publications else candidates()
    cands = [c for c in pool if c["publication_id"] not in done]
    print(f"{len(cands)} por buscar ({len(done)} ya hechas)", flush=True)
    for n, c in enumerate(cands, 1):
        hit, sim, tried = None, 0.0, []
        if c["doi"]:
            for src, fn in (("semanticscholar_doi", s2_doi), ("crossref_doi", cr_doi)):
                tried.append(src)
                r = fn(c["doi"])
                if r and len(r["abstract"]) >= MIN_CHARS:
                    hit, sim = dict(r, source=src), max(title_similarity(c["query"], r["title"]),
                                                        title_similarity(c["title"], r["title"]))
                    break
        if not hit:
            for src, fn in (("openalex_titulo", oa_title), ("semanticscholar_titulo", s2_title),
                            ("crossref_titulo", cr_title)):
                tried.append(src)
                h, s = first_hit(c["query"], fn(c["query"]), src, c["title"])
                if h and len(h["abstract"]) >= MIN_CHARS:
                    hit, sim = h, s
                    break
                if h and h.get("doi") and not c["doi"]:
                    # obra verificada sin abstract en esa fuente: probar por su DOI
                    for src2, fn2 in (("semanticscholar_doi", s2_doi), ("crossref_doi", cr_doi)):
                        r = fn2(h["doi"])
                        if r and len(r["abstract"]) >= MIN_CHARS:
                            hit, sim = dict(r, source=src + "+" + src2), s
                            break
                    if hit:
                        break
        if not hit and c["isbn"]:
            tried.append("googlebooks")
            h, s = first_hit(c["query"], gbooks(c["isbn"]), "googlebooks_descripcion", c["title"])
            if h and len(h["abstract"]) >= MIN_CHARS:
                hit, sim = h, s
        rec = dict(c, found=bool(hit), source=hit["source"] if hit else "", sim=round(sim, 3),
                   matched_title=hit["title"] if hit else "", abstract=hit["abstract"] if hit else "",
                   tried=tried)
        with OUT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if n % 25 == 0:
            print(f"  {n}/{len(cands)}", flush=True)
    print("listo", flush=True)


if __name__ == "__main__":
    main()

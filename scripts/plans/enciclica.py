#!/usr/bin/env python3
"""Plan «Encíclica Magnifica Humanitas»: borrador de retos desde el texto libre.

A diferencia de CEPLAN, el PND o el MIT, la enciclica no trae una lista de
retos: la armamos leyendo el documento. Por eso el resultado de este script es
un BORRADOR para revisar a mano, no el policies.csv del plan.

Fuente: Leon XIV, Carta Enciclica «Magnifica Humanitas» sobre la custodia de
la persona humana en el tiempo de la inteligencia artificial (15-05-2026).

    curl -L -o datos/plans/enciclica_mh/magnifica_humanitas.html \\
      https://www.vatican.va/content/leo-xiv/es/encyclicals/documents/20260515-magnifica-humanitas.html
    python scripts/plans/enciclica.py parse       # sin LLM
    python scripts/plans/enciclica.py extract     # LLM por seccion (cache)
    python scripts/plans/enciclica.py normalize   # LLM, una llamada (cache)

Pasos (todo en datos/plans/enciclica_mh/):
  1. parse: el HTML en sus 245 parrafos numerados, cada uno con su ruta
     capitulo -> seccion -> subseccion -> parrafos.jsonl. Sin notas al pie.
  2. extract: por cada seccion (titulo en negrita; la introduccion y la
     conclusion, que solo tienen subtitulos, van enteras) el LLM lista los
     retos o propuestas que el texto plantea, con sus parrafos de respaldo y
     una cita literal -> extraccion.json. Se procesa todo el documento: si una
     seccion no propone nada (historia, principios), devuelve [].
  3. normalize: en dos pasos de respuestas cortas (la pasarela corta las
     largas): asigna cada candidata a la seccion de los capitulos III-V donde
     su tema mas se desarrolla, o la descarta si no es un reto (por lotes); y
     por seccion junta las que dicen lo mismo (la educacion aparece en ¶14,
     ¶106, ¶139-147, ¶238) -> retos_borrador.json y retos_borrador.xlsx (para
     la revision).

Estructura del plan (tres niveles, como el PEDN): capitulo -> seccion de la
enciclica -> reto. Los niveles los pone el documento; los retos, la
normalizacion.

Modelo: el de lb_aws.llm_client (en el servidor, Claude Sonnet 5 por la
pasarela LibreChat PUCP), el mismo de la extraccion de temas. Cache por
prompt: re-ejecutar no vuelve a llamar.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))

PLAN_DIR = REPO_ROOT / "datos" / "plans" / "enciclica_mh"
HTML_PATH = PLAN_DIR / "magnifica_humanitas.html"
PARAGRAPHS = PLAN_DIR / "parrafos.jsonl"
EXTRACTION = PLAN_DIR / "extraccion.json"
DRAFT_JSON = PLAN_DIR / "retos_borrador.json"
DRAFT_XLSX = PLAN_DIR / "retos_borrador.xlsx"
CACHE = PLAN_DIR / "llm_cache.json"

CHAPTERS = {"INTRODUCCION": "Introducción", "CAPITULO_PRIMERO": "Capítulo I",
            "CAPITULO_SEGUNDO": "Capítulo II", "CAPITULO_TERCERO": "Capítulo III",
            "CAPITULO_CUARTO": "Capítulo IV", "CAPITULO_QUINTO": "Capítulo V",
            "CONCLUSION": "Conclusión"}
# Capitulos cuyos titulos de seccion son las categorias del plan (nivel 2).
TARGET_CHAPTERS = ("Capítulo III", "Capítulo IV", "Capítulo V")
N_PARAGRAPHS = 245


# --------------------------------------------------------------------------
# 1. parse
# --------------------------------------------------------------------------

def _text(raw: str) -> str:
    raw = re.sub(r"<sup>.*?</sup>", "", raw, flags=re.S)
    raw = re.sub(r"<br\s*/?>", " ", raw)
    text = html.unescape(re.sub(r"<[^>]+>", "", raw))
    text = re.sub(r"\[\d+\]", "", text)          # llamadas a notas al pie
    return re.sub(r"\s+", " ", text).strip()


def parse(html_text: str) -> list[dict]:
    start = html_text.find('name="INTRODUCCION"></a>')
    start = html_text.rfind("<p", 0, start)
    end = html_text.find("Dado en Roma", start)
    body = html_text[start:end]
    blocks = re.findall(r"<(p|li|blockquote)\b([^>]*)>(.*?)</\1>", body, flags=re.S)
    paragraphs, chapter, chapter_title, section, subsection = [], None, "", "", ""
    expect_title = False
    for tag, attrs, raw in blocks:
        text = _text(raw)
        if not text:
            continue
        anchor = re.match(r'\s*(?:<[bi]>)?\s*<a name="([^"]+)"></a>', raw)
        name = anchor.group(1) if anchor else None
        centered = "center" in attrs
        if name in CHAPTERS:
            chapter, chapter_title, section, subsection = CHAPTERS[name], "", "", ""
            expect_title = chapter not in ("Introducción", "Conclusión")
            continue
        if centered and expect_title:
            chapter_title, expect_title = text, False
            continue
        if name and name.isdigit():
            number = int(name)
            text = re.sub(rf"^{number}\.\s*", "", text)
            paragraphs.append({"n": number, "chapter": chapter, "chapter_title": chapter_title,
                               "section": section, "subsection": subsection, "text": text})
            continue
        if name and raw.lstrip().startswith("<b>"):
            section, subsection = text, ""
            continue
        if name and raw.lstrip().startswith("<i>"):
            subsection = text
            continue
        if paragraphs and tag in ("p", "li", "blockquote"):
            paragraphs[-1]["text"] += " " + text      # listas y citas del mismo parrafo
    numbers = [p["n"] for p in paragraphs]
    if numbers != list(range(1, N_PARAGRAPHS + 1)):
        missing = sorted(set(range(1, N_PARAGRAPHS + 1)) - set(numbers))
        raise SystemExit(f"Se esperaban los parrafos 1-{N_PARAGRAPHS} en orden; faltan {missing[:20]}"
                         f" (leidos {len(numbers)}). Revisar el HTML.")
    return paragraphs


def cmd_parse(_args):
    paragraphs = parse(HTML_PATH.read_text(encoding="utf-8"))
    with PARAGRAPHS.open("w", encoding="utf-8") as handle:
        for p in paragraphs:
            handle.write(json.dumps(p, ensure_ascii=False) + "\n")
    words = sum(len(p["text"].split()) for p in paragraphs)
    print(f"-> {PARAGRAPHS.relative_to(REPO_ROOT)}: {len(paragraphs)} parrafos, ~{words:,} palabras")
    for unit in extraction_units(paragraphs):
        print(f"   {unit['chapter']:13s} {unit['section'][:60]:60s} ¶{unit['first']}-{unit['last']}")


def read_paragraphs() -> list[dict]:
    return [json.loads(line) for line in PARAGRAPHS.open(encoding="utf-8")]


def extraction_units(paragraphs: list[dict]) -> list[dict]:
    """Una unidad por seccion en negrita; introduccion y conclusion, enteras."""
    units = []
    for p in paragraphs:
        whole = p["chapter"] in ("Introducción", "Conclusión")
        key = (p["chapter"], "" if whole else p["section"])
        if not units or units[-1]["key"] != key:
            units.append({"key": key, "chapter": p["chapter"], "chapter_title": p["chapter_title"],
                          "section": "" if whole else p["section"], "paragraphs": []})
        units[-1]["paragraphs"].append(p)
    for u in units:
        u["first"], u["last"] = u["paragraphs"][0]["n"], u["paragraphs"][-1]["n"]
        if not u["section"]:
            u["section"] = u["chapter"] if u["chapter"] in ("Introducción", "Conclusión") \
                else "(apertura del capítulo)"
    return units


# --------------------------------------------------------------------------
# LLM con cache
# --------------------------------------------------------------------------

def _llm():
    import lb_aws
    import lb_config
    return lb_aws.llm_client(lb_config.load())


def ask_json(client, system: str, user: str, max_tokens: int):
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    key = hashlib.sha256(f"{system}\n{user}".encode()).hexdigest()[:24]
    if key not in cache:
        raw = client.complete(system, user, max_tokens=max_tokens)
        cache[key] = raw
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    raw = cache[key]
    match = re.search(r"[\[{].*[\]}]", raw, flags=re.S)
    if not match:
        raise ValueError(f"Respuesta sin JSON: {raw[:300]!r}")
    return json.loads(match.group(0))


# --------------------------------------------------------------------------
# 2. extract
# --------------------------------------------------------------------------

EXTRACT_SYSTEM = """Analizas una enciclica papal para armar una lista de RETOS contra la que se \
compararan proyectos de investigacion universitaria (como se hace con un plan nacional de \
desarrollo).

Un reto es un desafio, propuesta, exigencia o llamado a la accion que el texto plantea de forma \
explicita: algo que hay que lograr, cambiar, proteger, evitar o construir. NO son retos: la \
historia de la doctrina, la exegesis biblica, las descripciones de la situacion sin una \
exigencia, ni los principios doctrinales enunciados en abstracto. Si la seccion no plantea \
ningun reto, responde [].

Para cada reto:
- "reto": formulado como desafio concreto, en infinitivo, de 6 a 14 palabras (p.ej. "Garantizar \
que la automatizacion vaya acompanada de medidas de proteccion del empleo"). Debe ser lo bastante \
concreto para que una investigacion pueda aportar a el; evita formulaciones vagas como \
"custodiar la dignidad".
- "descripcion": 1 o 2 frases con lo que pide el texto, sin agregar nada que no diga.
- "destinatarios": a quien se dirige si el texto lo dice (gobiernos, universidades, empresas, \
desarrolladores de IA, escuelas, familias, Iglesia, todos...); [] si no lo dice.
- "parrafos": numeros de los parrafos que lo respaldan.
- "cita": una cita literal breve (maximo 30 palabras) de esos parrafos.

No inventes ni infieras retos que el texto no plantea. No repitas el mismo reto dos veces.
Responde SOLO un arreglo JSON de objetos con esas claves."""


def unit_prompt(unit: dict) -> str:
    lines = [f"{unit['chapter']}" + (f": {unit['chapter_title']}" if unit["chapter_title"] else ""),
             f"Seccion: {unit['section']}", ""]
    current = None
    for p in unit["paragraphs"]:
        if p["subsection"] and p["subsection"] != current:
            current = p["subsection"]
            lines += ["", f"[{current}]"]
        lines.append(f"¶{p['n']}. {p['text']}")
    return "\n".join(lines)


def cmd_extract(_args):
    client = _llm()
    units = extraction_units(read_paragraphs())
    out, n = [], 0
    for unit in units:
        allowed = {p["n"] for p in unit["paragraphs"]}
        items = ask_json(client, EXTRACT_SYSTEM, unit_prompt(unit), max_tokens=6000)
        kept = []
        for item in items:
            paras = sorted({int(x) for x in item.get("parrafos", []) if int(x) in allowed})
            if not item.get("reto") or not paras:
                continue
            n += 1
            kept.append({"id": f"C{n:03d}", "reto": item["reto"].strip(),
                         "descripcion": (item.get("descripcion") or "").strip(),
                         "destinatarios": item.get("destinatarios") or [],
                         "parrafos": paras, "cita": (item.get("cita") or "").strip(),
                         "chapter": unit["chapter"], "section": unit["section"]})
        out.extend(kept)
        print(f"   {unit['chapter']:13s} {unit['section'][:55]:55s} {len(kept):3d} retos")
    EXTRACTION.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {EXTRACTION.relative_to(REPO_ROOT)}: {len(out)} retos candidatos")


# --------------------------------------------------------------------------
# 3. normalize
# --------------------------------------------------------------------------

# Normalizar es dos pasos de respuestas cortas: la pasarela LibreChat corta
# (HTTP 504) una respuesta larga, y una sola llamada con los ~200 candidatos y
# ~50 retos descritos no pasaba. 1) asignar: cada candidato a una seccion de
# los capitulos III-V, o descartarlo (por lotes); 2) fusionar: por seccion, los
# candidatos que dicen lo mismo en un reto con su descripcion. Como cada tema va
# a la seccion donde mas se desarrolla, los duplicados entre capitulos caen
# juntos en el paso 2; lo que quede, se ve en la revision a mano.
ASSIGN_BATCH = 40

ASSIGN_SYSTEM = """Clasificas retos candidatos extraidos de una enciclica papal. La lista final \
sera un plan de retos contra el que se compararan proyectos de investigacion universitaria.

Para cada candidato decide UNA de dos cosas:
- la SECCION (por su numero, p.ej. "S4") de la lista dada donde ese tema se desarrolla mas. Los \
candidatos de la introduccion, los capitulos I y II y la conclusion se asignan a la seccion que \
corresponda por tema;
- o "descartar", si no es un reto abordable por la investigacion: demasiado generico, puramente \
espiritual, doctrinal o interno de la Iglesia, o una propuesta historica de otro Papa que el texto \
solo recuerda. Indica el motivo en pocas palabras.

Responde SOLO un objeto JSON: {"<id>": "S4", "<id>": "descartar: <motivo>", ...} con TODOS los \
ids recibidos."""

MERGE_SYSTEM = """Normalizas los retos candidatos que una enciclica papal plantea en una de sus \
secciones. La lista final es un plan de retos contra el que se compararan proyectos de \
investigacion universitaria: cada reto debe ser concreto, distinto de los demas y abordable por \
la investigacion.

Junta en un solo reto los candidatos que expresan el mismo desafio; deja separados los que piden \
cosas distintas. No descartes ninguno: ya se filtraron. En todo el documento habra entre 30 y 50 \
retos, asi que una seccion suele dar entre 2 y 8.

Para cada reto: "reto" (infinitivo, 6 a 14 palabras), "descripcion" (1 o 2 frases fieles al \
texto, sin agregar nada), "candidatos" (ids). Cada candidato debe aparecer en exactamente un reto.
Responde SOLO un arreglo JSON de objetos con esas claves."""


def cand_line(c: dict) -> str:
    return (f"{c['id']} [{c['chapter']} / {c['section']}; ¶{','.join(map(str, c['parrafos']))}] "
            f"{c['reto']} — {c['descripcion']}")


def two_step_normalize(client, cands: list[dict], sections: list[tuple[str, str]]) -> dict:
    """{"retos": [{reto, descripcion, seccion, candidatos}], "descartados": [...]}."""
    numbered = {f"S{n}": s for n, (_c, s) in enumerate(sections, 1)}
    header = "SECCIONES:\n" + "\n".join(f"S{n}. {s} ({c})" for n, (c, s) in enumerate(sections, 1))
    assign = {}
    for start in range(0, len(cands), ASSIGN_BATCH):
        batch = cands[start:start + ASSIGN_BATCH]
        out = ask_json(client, ASSIGN_SYSTEM, header + "\n\nCANDIDATOS:\n" +
                       "\n".join(cand_line(c) for c in batch), max_tokens=4000)
        assign.update({k: str(v) for k, v in out.items()})
        print(f"   asignados {min(start + ASSIGN_BATCH, len(cands))}/{len(cands)}")
    by_section, discarded = defaultdict(list), []
    for c in cands:
        verdict = assign.get(c["id"], "").strip()
        code = verdict.split()[0].rstrip(".:") if verdict else ""
        if verdict.lower().startswith("descartar"):
            discarded.append({"candidato": c["id"], "motivo": verdict.split(":", 1)[-1].strip()})
        elif code in numbered:
            by_section[numbered[code]].append(c)
        # sin veredicto legible: queda sin destino y cmd_normalize lo avisa
    retos = []
    for _chapter, section in sections:
        group = by_section.get(section)
        if not group:
            continue
        items = ask_json(client, MERGE_SYSTEM, f"SECCION: {section}\n\nCANDIDATOS:\n" +
                         "\n".join(cand_line(c) for c in group), max_tokens=4000)
        for r in items:
            retos.append({**r, "seccion": section})
        print(f"   {section[:55]:55s} {len(group):3d} candidatos -> {len(items):2d} retos")
    return {"retos": retos, "descartados": discarded}


def cmd_normalize(_args):
    client = _llm()
    cands = json.loads(EXTRACTION.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in cands}
    paragraphs = read_paragraphs()
    sections = []
    for p in paragraphs:
        if p["chapter"] in TARGET_CHAPTERS and p["section"] and \
                (p["chapter"], p["section"]) not in sections:
            sections.append((p["chapter"], p["section"]))
    allowed = {s for _c, s in sections}
    chapter_of = {s: c for c, s in sections}
    result = two_step_normalize(client, cands, sections)

    seen, retos, problems = set(), [], []
    for n, r in enumerate(result.get("retos", []), 1):
        ids = [i for i in r.get("candidatos", []) if i in by_id]
        if r.get("seccion") not in allowed:
            problems.append(f"reto {n}: seccion no permitida {r.get('seccion')!r}")
        seen.update(ids)
        paras = sorted({x for i in ids for x in by_id[i]["parrafos"]})
        retos.append({
            "id": f"R{n:02d}", "reto": r.get("reto", "").strip(),
            "descripcion": r.get("descripcion", "").strip(),
            "capitulo": chapter_of.get(r.get("seccion"), "?"), "seccion": r.get("seccion"),
            "parrafos": paras, "candidatos": ids,
            "citas": [by_id[i]["cita"] for i in ids if by_id[i]["cita"]],
            "destinatarios": sorted({d for i in ids for d in by_id[i]["destinatarios"]})})
    discarded = [d for d in result.get("descartados", []) if d.get("candidato") in by_id]
    seen.update(d["candidato"] for d in discarded)
    missing = sorted(set(by_id) - seen)
    if missing:
        problems.append(f"candidatos sin destino: {missing}")
    order = {s: i for i, (_c, s) in enumerate(sections)}
    retos.sort(key=lambda r: (order.get(r["seccion"], 99), r["parrafos"][:1]))
    for n, r in enumerate(retos, 1):
        r["id"] = f"R{n:02d}"
    DRAFT_JSON.write_text(json.dumps({"retos": retos, "descartados": discarded, "problemas": problems},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
    write_review_xlsx(retos, discarded, by_id)
    print(f"-> {DRAFT_JSON.relative_to(REPO_ROOT)} y {DRAFT_XLSX.name}: {len(retos)} retos, "
          f"{len(discarded)} candidatos descartados, de {len(cands)}")
    for p in problems:
        print(f"   AVISO: {p}")


def write_review_xlsx(retos, discarded, by_id):
    import openpyxl
    from openpyxl.styles import Alignment, Font
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "retos"
    ws.append(["id", "Capítulo", "Sección", "Reto", "Descripción", "Párrafos", "Citas",
               "Destinatarios", "Decisión (aprobar / editar / eliminar)", "Reto corregido / comentario"])
    for r in retos:
        ws.append([r["id"], r["capitulo"], r["seccion"], r["reto"], r["descripcion"],
                   ", ".join(map(str, r["parrafos"])), "\n".join(f"«{c}»" for c in r["citas"]),
                   ", ".join(r["destinatarios"]), "", ""])
    dv = DataValidation(type="list", formula1='"aprobar,editar,eliminar"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"I2:I{len(retos) + 1}")
    for col, width in zip("ABCDEFGHIJ", (6, 12, 34, 45, 60, 14, 60, 24, 18, 40)):
        ws.column_dimensions[col].width = width
    ws2 = wb.create_sheet("descartados")
    ws2.append(["Candidato", "Sección de origen", "Reto candidato", "Párrafos", "Motivo del descarte"])
    for d in discarded:
        c = by_id[d["candidato"]]
        ws2.append([c["id"], f"{c['chapter']} / {c['section']}", c["reto"],
                    ", ".join(map(str, c["parrafos"])), d.get("motivo", "")])
    for col, width in zip("ABCDE", (10, 40, 50, 12, 40)):
        ws2.column_dimensions[col].width = width
    for sheet in (ws, ws2):
        for row in sheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        sheet.freeze_panes = "A2"
    wb.save(DRAFT_XLSX)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, fn in (("parse", cmd_parse), ("extract", cmd_extract), ("normalize", cmd_normalize)):
        sub.add_parser(name).set_defaults(fn=fn)
    args = parser.parse_args()
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    args.fn(args)


if __name__ == "__main__":
    main()

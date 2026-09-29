#!/usr/bin/env python3
"""Etapa 02 — extrae temas por unidad con un LLM (Bedrock o pasarela OpenAI).

Sustituye el paso que hasta ahora se hacia leyendo cada proyecto a mano (ver
docs/topic_normalization_pipeline.md): por cada unidad pide al modelo entre 1 y
N temas con descripcion, EVIDENCIA LITERAL y confianza.

La evidencia es obligatoria y se verifica contra el texto de origen: un tema
cuya cita no aparece en el texto se marca y no se cuenta como evidencia
valida. Sin eso no hay forma de auditar despues si un tema salio del material
o lo invento el modelo.

Reanudable: cada unidad resuelta se anexa a
``salidas/topics/<dominio>/<run>/02_extraction_cache.jsonl`` apenas se obtiene.
Un rerun salta lo que ya esta en cache, asi que se puede cortar con Ctrl-C.

    python scripts/pipeline_temas/02_extract_topics.py --domain projects
    python scripts/pipeline_temas/02_extract_topics.py --domain projects --limit 20
"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _stage import REPO_ROOT, StageContext, base_parser, main_wrapper  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
import lb_aws  # noqa: E402

SYSTEM_PROMPT = """\
Eres un analista de investigación académica. Extraes los temas de investigación
de una unidad (un proyecto o una publicación) a partir de su texto.

Reglas:
- Devuelve SOLO un objeto JSON válido, sin texto antes ni después, sin ```.
- Esquema: {"topics": [{"topic": str, "description": str, "evidence": str,
  "confidence": float}]}
- "topic": frase nominal de 3 a 10 palabras que nombre el tema de investigación,
  en español, específica y no genérica ("Documentación del idioma kakataibo",
  no "Lingüística" ni "Investigación").
- "description": una oración explicando de qué trata el tema en esta unidad.
- "evidence": una CITA LITERAL y contigua del texto proporcionado que sustente
  el tema. Cópiala exactamente, sin parafrasear. Si no puedes citar el texto,
  no incluyas el tema.
- "confidence": 0 a 1. Cuán claramente sustenta el texto ese tema. Usa valores
  bajos cuando el texto sea escaso (por ejemplo, solo el título).
- Extrae entre 1 y {max_topics} temas. Si el texto es muy corto o vacío de
  contenido temático, devuelve menos temas, o {"topics": []}.
- No inventes temas que el texto no sustente. Es preferible un solo tema bien
  sustentado que cinco especulativos.
"""

USER_TEMPLATE = """\
Unidad: {unit_id}
Título: {title}
{metadata}
Texto:
\"\"\"
{text}
\"\"\"
"""


def parse_response(raw: str) -> list[dict]:
    """Extrae el JSON de la respuesta, tolerando que venga envuelto en ```."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"respuesta sin JSON: {raw[:200]!r}")
    return json.loads(text[start:end + 1]).get("topics", [])


def normalize_evidence(text: str) -> str:
    return " ".join(text.lower().split())


def extract_one(client, cfg, unit) -> dict:
    max_topics = int(cfg.get("topics.max_topics_per_unit", 5))
    min_confidence = float(cfg.get("topics.min_confidence", 0.5))
    metadata = " · ".join(
        f"{k}: {v}" for k, v in (unit.get("source_row") or {}).items() if v)
    user = USER_TEMPLATE.format(
        unit_id=unit["unit_id"], title=unit.get("title", ""),
        metadata=f"Metadatos: {metadata}" if metadata else "",
        text=unit["text"])

    system = SYSTEM_PROMPT.replace("{max_topics}", str(max_topics))
    raw = client.complete(system, user)
    try:
        topics = parse_response(raw)
    except (ValueError, json.JSONDecodeError) as first_error:
        # Un reintento con la regla de escapado explicita. La causa habitual es
        # una comilla sin escapar dentro de "evidence", que es una cita literal
        # del texto del proyecto. Perder la unidad por eso seria absurdo: son
        # ~0.4% de las llamadas y el reintento cuesta una fraccion de centimo.
        retry_system = system + (
            "\n\nIMPORTANTE: el JSON anterior no se pudo parsear. Escapa como \\\" "
            "toda comilla doble que aparezca dentro de un valor de cadena, y no "
            "uses saltos de linea literales dentro de las cadenas.")
        try:
            raw = client.complete(retry_system, user)
            topics = parse_response(raw)
        except (ValueError, json.JSONDecodeError) as second_error:
            return {"unit_id": unit["unit_id"], "topics": [],
                    "error": f"respuesta no parseable tras reintento: "
                             f"{first_error} | {second_error}"}

    haystack = normalize_evidence(unit["text"])
    clean = []
    for item in topics[:max_topics]:
        topic = str(item.get("topic", "")).strip()
        if not topic:
            continue
        confidence = float(item.get("confidence") or 0.0)
        if confidence < min_confidence:
            continue
        evidence = str(item.get("evidence", "")).strip()
        clean.append({
            "unit_id": unit["unit_id"],
            "topic": topic,
            "description": str(item.get("description", "")).strip(),
            "evidence": evidence,
            "confidence": min(max(confidence, 0.0), 1.0),
            # Bandera de auditoria: la cita no esta en el texto de origen.
            "evidence_verbatim": bool(evidence) and normalize_evidence(evidence) in haystack,
        })
    return {"unit_id": unit["unit_id"], "topics": clean}


@main_wrapper
def main():
    parser = base_parser(__doc__)
    parser.add_argument("--no-resume", action="store_true",
                        help="Ignora el cache y vuelve a consultar todo.")
    args = parser.parse_args()

    with StageContext(args, "02_extract_topics") as ctx:
        units = ctx.store.read_units()

        cache_path = (REPO_ROOT / "salidas" / "topics" / ctx.domain_key / ctx.run_id
                      / "02_extraction_cache.jsonl")
        done: dict[str, dict] = {}
        if cache_path.exists() and not args.no_resume:
            for line in cache_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    record = json.loads(line)
                    done[record["unit_id"]] = record
        pending = [u for u in units if u["unit_id"] not in done]
        print(f"  unidades={len(units):,}  en cache={len(done):,}  por consultar={len(pending):,}")

        if args.dry_run:
            if pending:
                print(f"  --dry-run: se consultarian {len(pending):,} unidades con "
                      f"{ctx.cfg.get('bedrock.llm_model_id')}.")
                chars = sum(len(u["text"]) for u in pending)
                print(f"  texto total a enviar: {chars:,} caracteres "
                      f"(~{chars // 4:,} tokens estimados, sin contar el prompt de sistema)")
            return

        client = lb_aws.llm_client(ctx.cfg, ctx.stage)
        workers = int(ctx.cfg.get("bedrock.max_concurrency", 4))
        started = time.time()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        errors = 0
        with cache_path.open("a", encoding="utf-8") as cache_file:
            def run(unit):
                return extract_one(client, ctx.cfg, unit)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for index, record in enumerate(pool.map(run, pending), 1):
                    done[record["unit_id"]] = record
                    cache_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                    cache_file.flush()
                    if record.get("error"):
                        errors += 1
                    step = 25 if len(pending) < 2000 else 200
                    if index % step == 0 or index == len(pending):
                        done_frac = index / len(pending)
                        elapsed = time.time() - started
                        eta = elapsed / done_frac - elapsed if done_frac else 0
                        print(f"  {index:,}/{len(pending):,} ({done_frac*100:5.1f}%)  "
                              f"{elapsed/60:5.1f} min transcurridos  "
                              f"ETA {eta/60:5.1f} min  "
                              f"{errors} con error", flush=True)

        rows = [topic for record in done.values() for topic in record.get("topics", [])]
        unverified = sum(1 for r in rows if not r["evidence_verbatim"])
        ctx.stage.units_processed = len(done)
        ctx.stage.notes = {
            "units_with_topics": sum(1 for r in done.values() if r.get("topics")),
            "units_without_topics": sum(1 for r in done.values() if not r.get("topics")),
            "extracted_topics": len(rows),
            "topics_with_unverified_evidence": unverified,
            "parse_errors": errors,
        }
        print(f"  temas extraidos={len(rows):,}  "
              f"sin evidencia literal verificable={unverified:,}")
        if unverified:
            print("  AVISO: esos temas citan texto que no aparece en la unidad. "
                  "Revisar antes de usarlos como evidencia.")

        ctx.store.write_extracted_topics(rows)
        if ctx.s3.enabled:
            ctx.s3.put_json(ctx.s3.run_key(ctx.run_id, "02_extracted_topics.json"), rows)


if __name__ == "__main__":
    main()

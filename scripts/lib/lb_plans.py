"""Planes (listas de objetivos o "retos") contra los que se cruzan las unidades.

Un plan es una taxonomia oficial de dos o tres niveles (nivel 1 -> [nivel 2 ->]
hoja) que ya viene nombrada: no pasa por la extraccion por LLM. El cruce
(scripts/analysis/ceplan_units.py) trabaja sobre las hojas. Cualquier dominio
se puede cruzar con cualquier plan (`ceplan_units.py --plan <clave>`);
lb_domains.Domain.plan es solo el plan por defecto del dominio.

  pedn2050     PEDN 2050 / CEPLAN (Peru): ON -> Tematica -> Sub-tematica (126).
               Desde datos/PEDN2050.xlsx via lb_ceplan.
  pnd_ec_2025  PND 2025-2029 "Ecuador no se detiene": Eje -> Objetivo ->
               Politica (45). Desde el policies.csv estandar que escribe
               scripts/datasets/ecotec.py.
  mit_airisk   Repositorio de Riesgos de IA del MIT (v4): Dominio -> categoria de
               riesgo (24 sub-dominios). Sin pais. Desde datos/plans/mit_airisk/
               policies.csv, que escribe scripts/plans/mit_airisk.py.

Anadir un plan = su policies.csv en datos/plans/<clave>/ (columnas abajo) y
una entrada en PLANS con `load=_policies_csv_loader(plan_csv("<clave>"))`;
para el atlas, ademas una entrada en atlas_profiles.PLANS. Columnas del CSV:

  policy_id, label, text, l1_id, l1_label[, l2_label]

`text` es lo que se embebe (la hoja enriquecida con su contexto); `l2_label`
puede faltar o quedar vacio en un plan de dos niveles. Las hojas salen como
{id, label, tema, on, on_label, text}: `on` y `tema` son los niveles 1 y 2 (los
nombres vienen del primer plan, CEPLAN, y se conservan para que las salidas ya
publicadas sigan leyendose igual; `tema` es "" en un plan de dos niveles).

El prompt del verificador sale de una sola plantilla (JUDGE_TEMPLATE) con el
plan y el dataset. Para un dataset del mismo pais que el plan reproduce letra
por letra el prompt que tenia cada plan antes de existir la plantilla: el cache
del verificador se indexa por el prompt, y cambiar una letra obligaria a
pagarlo de nuevo (tests/test_plans.py lo fija con un hash). Para un dataset de
otro pais agrega una frase: se juzga por el tema, no por el pais estudiado.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import lb_ceplan
import lb_domains

REPO_ROOT = Path(__file__).resolve().parents[2]

JUDGE_TEMPLATE = (
    "Evaluas si una investigacion universitaria {demonym} desarrolla o aporta a {a} {leaf} "
    "{scope}.{foreign} Para cada {leaf} responde 2 = la investigacion {pron} desarrolla claramente o "
    "aporta conocimiento directamente util para {ella}; 1 = relacion tangencial o indirecta; 0 = sin "
    "relacion real. Responde SOLO un arreglo JSON de enteros, uno por {leaf}, en orden.")

FOREIGN_CLAUSE = (
    " El plan es de {country} y la investigacion de una universidad de {other}: juzga por el tema y "
    "el conocimiento que aporta, no por el pais donde se hizo ni por el pais que estudia.")


@dataclass
class Plan:
    key: str
    name: str                   # "PEDN 2050"
    load: Callable[[], list[dict]]
    leaf: str                   # "sub-temática"
    leaves: str                 # "sub-temáticas"
    level1: str                 # "ON"
    level1_long: str            # "Objetivo Nacional"
    level2: str                 # "Temática" ("" en un plan de dos niveles)
    # --- Prompt del verificador (0/1/2 por hoja): ver JUDGE_TEMPLATE ------
    # Sin tildes, como el resto del prompt.
    judge_leaf: str             # "sub-tematica"
    judge_scope: str            # "del Plan Estrategico de Desarrollo Nacional (PEDN 2050, CEPLAN)"
    judge_header: str           # "SUB-TEMATICAS": encabezado de la lista de candidatas
    judge_level2_tag: str       # "tematica": como se rotula el nivel 2 de cada candidata
    translate_system: str
    # --- Archivos: salidas/topics/<dominio>/<run>/07_<prefix>_units.json --
    file_prefix: str
    leaf_slug: str              # "subtematica" -> <prefix>_por_subtematica.csv
    csv_columns: tuple[str, str, str]   # nivel 1, nivel 2, hoja
    cache_dir: Path             # traduccion, embeddings y cobertura conjunta
    source_note: str            # de donde salen las hojas, para los reportes
    # Pais del plan (sin tildes); None si no es de un pais (p.ej. los ODS).
    country: str | None = None
    # Dataset para el que se armo el plan: su cobertura conjunta se escribe en
    # cache_dir/reporte_cobertura.md (la de siempre); la de cualquier otro, en
    # reporte_cobertura_<dataset>.md.
    home_dataset: str | None = None
    judge_feminine: bool = True  # "una politica ... la desarrolla" / "un reto ... lo desarrolla"

    def judge_system(self, dataset: str) -> str:
        """Prompt del verificador para cruzar las unidades de `dataset` con este plan."""
        ds = lb_domains.dataset(dataset)
        foreign = ""
        if self.country and ds.country != self.country:
            foreign = FOREIGN_CLAUSE.format(country=self.country, other=ds.country)
        fem = self.judge_feminine
        return JUDGE_TEMPLATE.format(
            demonym=ds.demonym, a="una" if fem else "un", leaf=self.judge_leaf,
            scope=self.judge_scope, foreign=foreign,
            pron="la" if fem else "lo", ella="ella" if fem else "el")

    def coverage_report_path(self, dataset: str) -> Path:
        name = ("reporte_cobertura.md" if dataset == self.home_dataset
                else f"reporte_cobertura_{dataset}.md")
        return self.cache_dir / name


def plan_csv(key: str) -> Path:
    """Donde va el policies.csv de un plan que no sale de un adaptador de dataset."""
    return REPO_ROOT / "datos" / "plans" / key / "policies.csv"


def _pedn_leaves() -> list[dict]:
    tax = lb_ceplan.build_taxonomy()
    out = []
    for on_id, on in tax["on"].items():
        for tema, tnode in on["temas"].items():
            for sub_id, sub in tnode["subtemas"].items():
                out.append({"id": sub_id, "label": sub["label"], "tema": tema,
                            "on": on_id, "on_label": on["label"], "text": sub["text"]})
    return out


def read_policies_csv(path: Path) -> list[dict]:
    """Hojas de un policies.csv estandar (ver el docstring del modulo)."""
    if not path.exists():
        raise FileNotFoundError(
            f"No existe {path}. Lo escribe el adaptador del dataset (scripts/datasets/) "
            "o se arma a mano desde el documento del plan (ver lb_plans).")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    missing = {"policy_id", "label", "text", "l1_id", "l1_label"} - set(rows[0] if rows else {})
    if missing:
        raise ValueError(f"{path}: faltan columnas {sorted(missing)}")
    leaves, seen = [], set()
    for n, r in enumerate(rows, 2):
        pid = (r["policy_id"] or "").strip()
        if not pid or not (r["text"] or "").strip() or not (r["l1_id"] or "").strip():
            raise ValueError(f"{path}, fila {n}: policy_id, text y l1_id no pueden quedar vacios")
        if pid in seen:
            raise ValueError(f"{path}, fila {n}: policy_id repetido {pid!r}")
        seen.add(pid)
        leaves.append({"id": pid, "label": r["label"].strip(),
                       "tema": (r.get("l2_label") or "").strip(),
                       "on": r["l1_id"].strip(), "on_label": r["l1_label"].strip(),
                       "text": r["text"].strip()})
    return leaves


def _policies_csv_loader(path: Path) -> Callable[[], list[dict]]:
    return lambda: read_policies_csv(path)


PLANS: dict[str, Plan] = {
    "pedn2050": Plan(
        key="pedn2050", name="PEDN 2050", load=_pedn_leaves,
        leaf="sub-temática", leaves="sub-temáticas",
        level1="ON", level1_long="Objetivo Nacional", level2="Temática",
        judge_leaf="sub-tematica",
        judge_scope="del Plan Estrategico de Desarrollo Nacional (PEDN 2050, CEPLAN)",
        judge_header="SUB-TEMATICAS", judge_level2_tag="tematica",
        translate_system=lb_ceplan._TRANSLATE_SYSTEM,
        file_prefix="ceplan", leaf_slug="subtematica",
        csv_columns=("on", "tematica", "sub_tematica"),
        cache_dir=REPO_ROOT / "salidas" / "topics" / "ceplan",
        source_note="`Líneas de Inv.` de datos/PEDN2050.xlsx",
        country="Peru", home_dataset="pucp",
    ),
    "pnd_ec_2025": Plan(
        key="pnd_ec_2025", name="PND 2025-2029 (Ecuador)",
        load=_policies_csv_loader(REPO_ROOT / "salidas" / "datasets" / "ecotec" / "policies.csv"),
        leaf="política", leaves="políticas",
        level1="Eje", level1_long="Eje", level2="Objetivo",
        judge_leaf="politica",
        judge_scope=("del Plan Nacional de Desarrollo 2025-2029 del Ecuador "
                     "(\"Ecuador no se detiene\")"),
        judge_header="POLITICAS", judge_level2_tag="objetivo",
        translate_system=(
            "Traduces al ingles textos de planificacion publica ecuatoriana (Plan Nacional de "
            "Desarrollo 2025-2029). Traduccion fiel y natural, sin resumir ni agregar nada. Responde "
            "SOLO con un arreglo JSON de strings, uno por texto de entrada, en el mismo orden."),
        file_prefix="pnd", leaf_slug="politica",
        csv_columns=("eje", "objetivo", "politica"),
        cache_dir=REPO_ROOT / "salidas" / "topics" / "plans" / "pnd_ec_2025",
        source_note="columna `Política` de datos/ecotec/anexoPND25-29.xlsx "
                    "(enriquecida con su objetivo, indicadores y lineamientos ETN)",
        country="Ecuador", home_dataset="ecotec",
    ),
    # Taxonomia de dominios del MIT AI Risk Repository (v4, dic. 2025): no es
    # de un pais ni de una universidad. policies.csv: scripts/plans/mit_airisk.py.
    # Usa la plantilla del verificador tal cual: la hoja se nombra como «linea
    # de investigacion sobre riesgos de la IA» para que «desarrolla o aporta a»
    # signifique estudiarlo o mitigarlo, no causarlo, y judge_scope exige que
    # la investigacion trate de IA (los labels tambien lo dicen: el verificador
    # solo ve label y dominio). Su `text` esta en ingles, como la fuente:
    # translate_system lo pasa al espanol, y la cache "<slug>s_en.json" guarda
    # aqui la version en espanol (el cruce toma la mejor de las dos).
    "mit_airisk": Plan(
        key="mit_airisk", name="Repositorio de Riesgos de IA (MIT)",
        load=_policies_csv_loader(plan_csv("mit_airisk")),
        leaf="categoría de riesgo", leaves="categorías de riesgo",
        level1="Dominio", level1_long="Dominio", level2="",
        judge_leaf="linea de investigacion",
        judge_scope=("sobre riesgos de la inteligencia artificial (taxonomia de dominios del MIT "
                     "AI Risk Repository); solo cuenta si la investigacion trata sobre sistemas de "
                     "IA, algoritmicos o automatizados"),
        judge_header="LINEAS DE INVESTIGACION SOBRE RIESGOS DE LA IA", judge_level2_tag="dominio",
        translate_system=(
            "Traduces al espanol textos de la taxonomia de riesgos de la inteligencia artificial "
            "del MIT AI Risk Repository. Traduccion fiel y natural, sin resumir ni agregar nada. "
            "Responde SOLO con un arreglo JSON de strings, uno por texto de entrada, en el mismo "
            "orden."),
        file_prefix="mitai", leaf_slug="categoria",
        csv_columns=("dominio", "nivel2", "categoria_riesgo"),
        cache_dir=REPO_ROOT / "salidas" / "topics" / "plans" / "mit_airisk",
        source_note="Domain Taxonomy del MIT AI Risk Repository v4 (24 sub-dominios, "
                    "enriquecidos con su descripcion y riesgos de ejemplo de la base)",
        country=None, home_dataset=None,
    ),
}


def get(key: str) -> Plan:
    if key not in PLANS:
        raise KeyError(f"plan desconocido: {key!r}; disponibles: {sorted(PLANS)}")
    return PLANS[key]

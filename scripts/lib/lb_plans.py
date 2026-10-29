"""Planes nacionales contra los que se cruzan las unidades de un dominio.

Un plan es una taxonomia oficial de tres niveles (nivel 1 -> nivel 2 -> hoja)
que ya viene nombrada por el Estado: no pasa por la extraccion por LLM. El
cruce (scripts/analysis/ceplan_units.py) trabaja sobre las hojas; cada dominio
dice contra que plan se cruza (lb_domains.Domain.plan).

  pedn2050     PEDN 2050 / CEPLAN (Peru): ON -> Tematica -> Sub-tematica (126).
               Desde datos/PEDN2050.xlsx via lb_ceplan.
  pnd_ec_2025  PND 2025-2029 "Ecuador no se detiene": Eje -> Objetivo ->
               Politica (45). Desde el policies.csv estandar que escribe
               scripts/datasets/ecotec.py.

Anadir un plan = una entrada en PLANS con su cargador. Las hojas salen como
{id, label, tema, on, on_label, text}: `on` y `tema` son los niveles 1 y 2
(los nombres vienen del primer plan, CEPLAN, y se conservan para que las
salidas ya publicadas sigan leyendose igual).

Los textos de PEDN (prompt del verificador, encabezados, nombres de archivo)
son exactamente los de antes de existir este modulo: el cache del verificador
se indexa por el prompt, y cambiar una letra obligaria a pagarlo de nuevo.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import lb_ceplan

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Plan:
    key: str
    name: str                   # "PEDN 2050"
    load: Callable[[], list[dict]]
    leaf: str                   # "sub-temática"
    leaves: str                 # "sub-temáticas"
    level1: str                 # "ON"
    level1_long: str            # "Objetivo Nacional"
    level2: str                 # "Temática"
    # Prompt del verificador (0/1/2 por hoja) y como se lista cada candidata.
    judge_system: str
    judge_header: str           # "SUB-TEMATICAS"
    judge_level2_tag: str       # "tematica"
    translate_system: str
    # Archivos: salidas/topics/<dominio>/<run>/07_<prefix>_units.json, etc.
    file_prefix: str
    leaf_slug: str              # "subtematica" -> <prefix>_por_subtematica.csv
    csv_columns: tuple[str, str, str]   # nivel 1, nivel 2, hoja
    cache_dir: Path             # traduccion, embeddings y cobertura conjunta
    source_note: str            # de donde salen las hojas, para los reportes


def _pedn_leaves() -> list[dict]:
    tax = lb_ceplan.build_taxonomy()
    out = []
    for on_id, on in tax["on"].items():
        for tema, tnode in on["temas"].items():
            for sub_id, sub in tnode["subtemas"].items():
                out.append({"id": sub_id, "label": sub["label"], "tema": tema,
                            "on": on_id, "on_label": on["label"], "text": sub["text"]})
    return out


def _policies_csv_loader(path: Path) -> Callable[[], list[dict]]:
    """Cargador para el policies.csv estandar de un adaptador de dataset."""
    def load() -> list[dict]:
        if not path.exists():
            raise FileNotFoundError(
                f"No existe {path}. Lo escribe el adaptador del dataset (scripts/datasets/).")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return [{"id": r["policy_id"], "label": r["label"], "tema": r["l2_label"],
                     "on": r["l1_id"], "on_label": r["l1_label"], "text": r["text"]}
                    for r in csv.DictReader(handle)]
    return load


PLANS: dict[str, Plan] = {
    "pedn2050": Plan(
        key="pedn2050", name="PEDN 2050", load=_pedn_leaves,
        leaf="sub-temática", leaves="sub-temáticas",
        level1="ON", level1_long="Objetivo Nacional", level2="Temática",
        judge_system=(
            "Evaluas si una investigacion universitaria peruana desarrolla o aporta a una sub-tematica "
            "del Plan Estrategico de Desarrollo Nacional (PEDN 2050, CEPLAN). Para cada sub-tematica "
            "responde 2 = la investigacion la desarrolla claramente o aporta conocimiento directamente "
            "util para ella; 1 = relacion tangencial o indirecta; 0 = sin relacion real. Responde SOLO "
            "un arreglo JSON de enteros, uno por sub-tematica, en orden."),
        judge_header="SUB-TEMATICAS", judge_level2_tag="tematica",
        translate_system=lb_ceplan._TRANSLATE_SYSTEM,
        file_prefix="ceplan", leaf_slug="subtematica",
        csv_columns=("on", "tematica", "sub_tematica"),
        cache_dir=REPO_ROOT / "salidas" / "topics" / "ceplan",
        source_note="`Líneas de Inv.` de datos/PEDN2050.xlsx",
    ),
    "pnd_ec_2025": Plan(
        key="pnd_ec_2025", name="PND 2025-2029 (Ecuador)",
        load=_policies_csv_loader(REPO_ROOT / "salidas" / "datasets" / "ecotec" / "policies.csv"),
        leaf="política", leaves="políticas",
        level1="Eje", level1_long="Eje", level2="Objetivo",
        judge_system=(
            "Evaluas si una investigacion universitaria ecuatoriana desarrolla o aporta a una politica "
            "del Plan Nacional de Desarrollo 2025-2029 del Ecuador (\"Ecuador no se detiene\"). Para "
            "cada politica responde 2 = la investigacion la desarrolla claramente o aporta conocimiento "
            "directamente util para ella; 1 = relacion tangencial o indirecta; 0 = sin relacion real. "
            "Responde SOLO un arreglo JSON de enteros, uno por politica, en orden."),
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
    ),
}


def get(key: str) -> Plan:
    if key not in PLANS:
        raise KeyError(f"plan desconocido: {key!r}; disponibles: {sorted(PLANS)}")
    return PLANS[key]

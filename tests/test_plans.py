"""Planes: cualquier dataset contra cualquier plan (lb_plans, ceplan_units)."""

import hashlib
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS / "lib"))
sys.path.insert(0, str(SCRIPTS / "analysis"))

import lb_plans  # noqa: E402


def _h(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


# El cache del verificador se indexa por el prompt: estos hashes son los de los
# prompts escritos a mano antes de la plantilla. Si cambian, todas las
# corridas ya cruzadas se vuelven a pagar.
@pytest.mark.parametrize("plan,dataset,digest", [
    ("pedn2050", "pucp", "2c9f514bd4a720e4"),
    ("pnd_ec_2025", "ecotec", "66557ba88fc855d3"),
])
def test_same_country_prompt_is_unchanged(plan, dataset, digest):
    assert _h(lb_plans.get(plan).judge_system(dataset)) == digest


def test_foreign_prompt_names_both_countries():
    text = lb_plans.get("pedn2050").judge_system("ecotec")
    assert "universitaria ecuatoriana" in text
    assert "El plan es de Peru y la investigacion de una universidad de Ecuador" in text
    assert text.endswith("uno por sub-tematica, en orden.")
    assert "Ecuador no se detiene" in lb_plans.get("pnd_ec_2025").judge_system("pucp")


@pytest.mark.parametrize("dataset", ["pucp", "ecotec"])
def test_mit_airisk_prompt_judges_by_topic(dataset):
    # Plan sin pais: nunca la frase de otro pais. Cruce por tema: no exige que
    # la investigacion trate de IA.
    text = lb_plans.get("mit_airisk").judge_system(dataset)
    assert "aporta a una linea tematica de la taxonomia de riesgos del MIT" in text
    assert "aunque la investigacion no trate de inteligencia artificial" in text
    assert "El plan es de" not in text
    assert text.endswith("uno por linea tematica, en orden.")


def test_mit_airisk_builder_cleans_example_names():
    sys.path.insert(0, str(SCRIPTS / "plans"))
    mit = pytest.importorskip("mit_airisk")
    assert mit._ENUM.sub("", "Type 1: Diffusion of responsibility") == "Diffusion of responsibility"
    assert mit._ENUM.sub("", "Risk area 5: Human-Computer Interaction Harms").startswith("Human")
    assert mit._words("Hallucinations") == mit._words("Hallucination")
    assert len(mit.LABELS_ES) == 24 and mit.LABELS_ES["6.6"] == "Daño ambiental"
    assert mit.leaf_text("D", "S", "Desc.", ["a", "b"]) == \
        "Domain: D. Subdomain: S. Desc. Examples of risks: a; b."


def test_min_grade_comes_from_plan_and_config():
    cu = pytest.importorskip("ceplan_units")

    class Cfg:
        def __init__(self, values):
            self.values = values

        def get(self, key, default=None):
            return self.values.get(key, default)

    args = type("A", (), {"model": None})()
    assert cu.params_from(Cfg({}), args, lb_plans.get("pedn2050"))["min_grade"] == 1
    assert cu.params_from(Cfg({}), args, lb_plans.get("mit_airisk"))["min_grade"] == 2
    cfg = Cfg({"plans.mit_airisk.min_grade": "1"})
    assert cu.params_from(cfg, args, lb_plans.get("mit_airisk"))["min_grade"] == 1


def test_masculine_leaf_agrees():
    plan = lb_plans.Plan(**{**lb_plans.get("pnd_ec_2025").__dict__,
                            "judge_leaf": "reto", "judge_feminine": False})
    text = plan.judge_system("ecotec")
    assert "aporta a un reto " in text and "lo desarrolla" in text and "util para el;" in text


def test_coverage_report_path_keeps_home_name():
    plan = lb_plans.get("pedn2050")
    assert plan.coverage_report_path("pucp").name == "reporte_cobertura.md"
    assert plan.coverage_report_path("ecotec").name == "reporte_cobertura_ecotec.md"


def test_policies_csv_two_levels(tmp_path):
    path = tmp_path / "policies.csv"
    path.write_text("policy_id,label,text,l1_id,l1_label\n"
                    "R1,Agua,Agua segura para todos,A,Ambiente\n"
                    "R2,Salud,Salud materna,B,Salud\n", encoding="utf-8")
    leaves = lb_plans.read_policies_csv(path)
    assert leaves[0] == {"id": "R1", "label": "Agua", "tema": "", "on": "A",
                         "on_label": "Ambiente", "text": "Agua segura para todos"}


@pytest.mark.parametrize("body,error", [
    ("policy_id,label,text,l1_id\nR1,a,b,A\n", "faltan columnas"),
    ("policy_id,label,text,l1_id,l1_label\nR1,a,,A,x\n", "no pueden quedar vacios"),
    ("policy_id,label,text,l1_id,l1_label\nR1,a,b,A,x\nR1,c,d,A,x\n", "repetido"),
])
def test_policies_csv_rejects_bad_rows(tmp_path, body, error):
    path = tmp_path / "policies.csv"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        lb_plans.read_policies_csv(path)


def test_build_user_without_level2():
    cu = pytest.importorskip("ceplan_units")
    plan = lb_plans.get("pnd_ec_2025")
    subs = [{"id": "R1", "label": "Agua", "tema": "", "on": "A", "on_label": "Ambiente", "text": ""},
            {"id": "R2", "label": "Salud", "tema": "Materna", "on": "B", "on_label": "Salud", "text": ""}]
    user = cu.build_user("texto", [(0, 0.5), (1, 0.4)], subs, plan)
    assert "1. Agua (Ambiente)" in user
    assert "2. Salud (objetivo: Materna; Salud)" in user


def test_resolve_plan():
    cu = pytest.importorskip("ceplan_units")
    plan, ds = cu.resolve_plan([("ecotec_projects", "r1"), ("ecotec_publications", "r2")])
    assert (plan.key, ds) == ("pnd_ec_2025", "ecotec")
    plan, ds = cu.resolve_plan([("ecotec_projects", "r1")], "pedn2050")
    assert (plan.key, ds) == ("pedn2050", "ecotec")
    with pytest.raises(SystemExit, match="datasets distintos"):
        cu.resolve_plan([("projects", "r1"), ("ecotec_projects", "r2")], "pedn2050")


def test_atlas_plan_profile_notes():
    ap = pytest.importorskip("atlas_profiles")
    home = ap.plan_profile("pucp", lb_plans.get("pedn2050"))
    assert home["validated"] and "130 vínculos" in home["validation"] and home["foreign"] is None
    away = ap.plan_profile("ecotec", lb_plans.get("pedn2050"))
    assert not away["validated"] and away["validation"] == ap.NOT_VALIDATED
    assert "plan de Perú" in away["foreign"] and "universidad de Ecuador" in away["foreign"]
    pnd = ap.plan_profile("ecotec", lb_plans.get("pnd_ec_2025"))
    assert pnd["foreign"] is None and not pnd["validated"]


def test_atlas_page_profile_lists_plans():
    ap = pytest.importorskip("atlas_profiles")
    prof = ap.page_profile("ecotec", ["ecotec_projects"],
                           [lb_plans.get("pedn2050"), lb_plans.get("pnd_ec_2025")], "pnd_ec_2025")
    assert prof["plan_order"] == ["pedn2050", "pnd_ec_2025"]
    assert prof["plan_default"] == "pnd_ec_2025" and "plan" not in prof
    assert prof["plans"]["pedn2050"]["short"] == "CEPLAN"


def _units_json(path, sub="S1"):
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "subtematicas": {sub: {"label": "x", "tema": "", "on": "A", "coverage": "debil",
                               "num_units": 1, "num_grade2": 1, "units_equivalent": 1.0}},
        "units": {"u1": {"status": "alineada", "subs": [
            {"sub_id": sub, "grade": 2, "containment": 1.0, "contribution": 1.0}]}},
        "on_labels": {"A": "Eje A"}, "by_on": {"A": 1.0}, "status_counts": {}, "links_by_grade": {},
        "params": {"top_n": 5, "judge_model_id": "m", "floor": 0.4, "developed_min_grade2": 3}}),
        encoding="utf-8")


def test_plan_blocks_finds_every_crossed_plan(tmp_path, monkeypatch):
    ba = pytest.importorskip("build_atlas")
    monkeypatch.setattr(ba, "ROOT", tmp_path)
    runs = {"ecotec_projects": "r1", "ecotec_publications": "r2"}
    # Solo el plan por defecto, sin cruce: entra igual (la pestaña lo avisa).
    plans, default = ba.plan_blocks(runs)
    assert default == "pnd_ec_2025" and list(plans) == ["pnd_ec_2025"]
    assert plans["pnd_ec_2025"] == {"ecotec_projects": None, "ecotec_publications": None}
    # Cruce con el PEDN de una sola corrida: entra, en el orden de atlas_profiles.PLANS.
    _units_json(tmp_path / "salidas" / "topics" / "ecotec_projects" / "r1" / "07_ceplan_units.json")
    plans, default = ba.plan_blocks(runs)
    assert list(plans) == ["pedn2050", "pnd_ec_2025"] and default == "pnd_ec_2025"
    assert plans["pedn2050"]["ecotec_publications"] is None
    assert plans["pedn2050"]["ecotec_projects"]["units"] == {"u1": [["S1", 2, 1.0, 1.0]]}


def test_atlas_page_inlines_every_script():
    ap = pytest.importorskip("atlas_page")
    html = ap.render({"profile": {}, "data": {}})
    assert "window.AtlasCharts" in html and "function mount(B, planKey)" in html
    assert '<script src="' not in html and '<link rel="stylesheet" href="atlas.css">' not in html
    # los graficos se cargan antes que la pagina que los usa
    assert html.index("window.AtlasCharts") < html.index("function mount(B, planKey)")

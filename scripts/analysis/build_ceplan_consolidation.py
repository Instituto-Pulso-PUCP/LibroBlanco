#!/usr/bin/env python3
"""Consolidates CEPLAN's 762 atomic megatendencias (from
cluster_ceplan_policies.py's embedding-based clustering, reviewed manually in
salidas/topics/consolidation/ceplan_cluster_review.md) into 60 named,
broader policy "documents".

Unlike build_topic_consolidation.py (which rewrites the projects topics file
directly), this writes a doc_id -> {cluster_doc_id, cluster_titulo} remap
that build_topic_policy_alignment.py applies to the raw policy corpus before
its existing per-doc_id mean-pooling step. That keeps the alignment script's
logic untouched: once CEPLAN chunks are relabeled with a shared synthetic
doc_id, they get pooled into one vector per cluster automatically, exactly
like any other multi-chunk policy document (PN, PESEM, etc.) already is.

PN/PESEM/PEDN/CONCYTEC/PP (184 documents) are intentionally left untouched:
see the conversation that motivated this script for why lumping them in
with CEPLAN's one-sentence trends would risk collapsing very different kinds
of documents together.

Usage::

    python scripts/analysis/build_ceplan_consolidation.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REVIEW_CSV = ROOT / "salidas" / "topics" / "consolidation" / "ceplan_cluster_review.csv"
OUT_REMAP = ROOT / "salidas" / "topics" / "consolidation" / "ceplan_doc_remap.json"
OUT_SUMMARY = ROOT / "salidas" / "topics" / "consolidation" / "ceplan_consolidation_summary.md"

# cluster_id -> (nombre, descripcion), escritos a partir de la lectura de
# ceplan_cluster_review.md (ver cluster_ceplan_policies.py --k 60).
CLUSTER_NAMES = {
    7: ("Democracia y confianza institucional",
        "Insatisfacción con el funcionamiento de la democracia, menor participación electoral y "
        "desconfianza en los poderes del Estado, replicada en casi todas las regiones del Perú."),
    0: ("Carga sanitaria por enfermedades transmisibles",
        "Persistencia, con alguna reducción puntual, de la carga de enfermedades transmisibles y "
        "no transmisibles por región, incluyendo la mortalidad asociada."),
    51: ("Conectividad digital regional",
         "Mayor conectividad digital, uso de internet, dispositivos móviles y redes 5G, con "
         "expansión pareja en casi todas las regiones del país."),
    34: ("Logros y acceso educativo regional",
         "Evolución dispar —avances y estancamientos— de los logros educativos y el acceso a la "
         "educación inicial en las distintas regiones del Perú."),
    5: ("Salud infantil y enfermedades no transmisibles",
        "Reducción gradual del rezago en salud infantil (anemia, desnutrición) y evolución de las "
        "enfermedades no transmisibles, replicada por región."),
    32: ("Digitalización de la educación",
         "Mayor incorporación de tecnología en el sistema educativo y digitalización de la "
         "enseñanza, con avances o estancamientos según la región."),
    17: ("Percepción de corrupción",
         "Aumento de la percepción de corrupción y desconfianza en partidos políticos, junto con "
         "esfuerzos por restaurar la integridad pública, en casi todas las regiones."),
    9: ("Transformación territorial y urbanización de la población",
        "Cambios en la estructura y distribución territorial de la población, con mayor "
        "concentración en zonas urbanas, replicados por región."),
    20: ("Inseguridad ciudadana",
         "Persistencia de la inseguridad ciudadana en prácticamente todas las regiones del Perú."),
    28: ("Acceso a agua y saneamiento",
         "Aumento, con algún estancamiento puntual, del acceso seguro a agua y saneamiento por región."),
    23: ("Pérdida y degradación de bosques",
         "Degradación de ecosistemas y pérdida de bosques y biodiversidad, con avances puntuales "
         "de reforestación en algunas regiones."),
    45: ("Comercio internacional y economía global",
         "Integración comercial, diversificación exportadora, flujos de capital y cambios en el "
         "centro de gravedad económico mundial, con foco en América Latina."),
    52: ("Transformación digital de la economía",
         "Avance de la industria 4.0, la inteligencia artificial, blockchain, pagos digitales y "
         "comercio electrónico como impulsores de la economía."),
    30: ("Cobertura de electrificación",
         "Incremento, con algunos estancamientos regionales, de la cobertura de electrificación "
         "y la demanda de energía."),
    39: ("Pobreza, informalidad y desempleo",
         "Persistencia de la pobreza, la informalidad laboral y el desempleo, con crecimiento "
         "desigual del PBI per cápita por región."),
    4: ("Afiliación a sistemas de salud",
        "Mayor población afiliada a un sistema de salud, tendencia consistente en casi todas las "
        "regiones."),
    25: ("Emisiones y contaminación ambiental",
         "Incremento de emisiones de gases de efecto invernadero y contaminación, con "
         "preocupación creciente por la descarbonización industrial."),
    31: ("Transición energética",
         "Crecimiento de energías renovables, biocombustibles e hidrógeno limpio frente a la "
         "desaceleración de los combustibles fósiles."),
    38: ("Informalidad laboral y futuro del trabajo",
         "Persistencia de la informalidad y precariedad laboral, junto con nuevas dinámicas de "
         "teletrabajo, movilidad laboral y demanda de talento."),
    24: ("Eventos climáticos extremos",
         "Aumento de la frecuencia de eventos climáticos extremos y la vulnerabilidad ante "
         "peligros naturales por región."),
    35: ("Calidad y acceso educativo",
         "Estancamiento de los logros de aprendizaje y la provisión de servicios básicos "
         "escolares, junto con mayor demanda de educación técnica y privada."),
    37: ("Agricultura y consumo alimentario sostenible",
         "Mayor demanda de alimentos saludables, agricultura 4.0 y comercio justo agrícola, "
         "junto al uso persistente de agroquímicos."),
    1: ("Cambios demográficos y envejecimiento",
        "Envejecimiento poblacional, mayor esperanza de vida y dependencia demográfica, con "
        "creciente demanda de atención médica geriátrica."),
    6: ("Fragilidad institucional y polarización política",
        "Desconfianza en los poderes del Estado, menor institucionalidad y mayor polarización "
        "y populismo."),
    42: ("Crecimiento del tejido empresarial",
         "Incremento sostenido en la cantidad de empresas en las distintas regiones del país."),
    36: ("Producción agropecuaria y pesquera",
         "Evolución de la producción y exportación agropecuaria, y la sostenibilidad de los "
         "recursos pesqueros y acuícolas."),
    41: ("Movilidad social y previsión",
         "Recuperación de la clase media y ampliación de la cobertura previsional, en tensión "
         "con la persistencia de la pobreza y la desigualdad de ingresos."),
    22: ("Biodiversidad y gestión forestal",
         "Pérdida de biodiversidad y bosques, junto con avances en protección de áreas naturales "
         "y gestión forestal sostenible."),
    27: ("Cambio climático y degradación del suelo",
         "Variabilidad de temperaturas y precipitaciones, retroceso glaciar, desertificación y "
         "cambios en el uso del suelo."),
    3: ("Salud materno-infantil",
        "Descenso de la fecundidad y el embarazo adolescente, con avances en salud materna y "
        "lactancia, aunque persisten los nacimientos prematuros."),
    50: ("Innovación, ciencia y emprendimiento",
         "Financiamiento de startups, patentes y capital humano en ciencia y tecnología, con "
         "estancamiento en infraestructura de I+D."),
    43: ("Recuperación del turismo",
         "Recuperación, con algunos estancamientos regionales, del sector turismo y creciente "
         "interés en turismo sostenible."),
    10: ("Igualdad de género",
         "Mayor presencia y liderazgo político y económico de la mujer, en tensión con la "
         "persistencia de desigualdades y estereotipos de género."),
    54: ("Industrias culturales digitales",
         "Expansión de industrias culturales y creativas digitales —videojuegos, arte, "
         "contenidos— junto a la propagación de noticias falsas."),
    33: ("Identidad cultural y gobernanza institucional",
         "Descenso del analfabetismo e interés por preservar lenguas nativas e identidad "
         "cultural, junto con avances hacia una gobernanza regulatoria efectiva."),
    21: ("Crimen organizado y seguridad",
         "Aumento del crimen organizado, la trata de personas y las extorsiones, con creciente "
         "población penitenciaria."),
    18: ("Conflictos sociales",
         "Persistencia de conflictos sociales en distintas regiones del país."),
    19: ("Violencia de género e infantil",
         "Persistencia de la violencia contra la mujer y contra niños, niñas y adolescentes."),
    55: ("Ciberseguridad y delitos digitales",
         "Incremento del ciberdelito y los riesgos en el ciberespacio, junto con mayor "
         "protección contra el cibercrimen."),
    2: ("Nutrición infantil",
        "Incremento del sobrepeso y la obesidad infantil, en contraste con la persistencia de "
        "la desnutrición y la inseguridad alimentaria."),
    40: ("Consumo y endeudamiento de los hogares",
         "Incremento del consumismo y el endeudamiento de los hogares, junto con avances en "
         "inclusión y finanzas sostenibles."),
    29: ("Estrés hídrico y acceso al agua",
         "Mayor escasez y estrés hídrico pese al incremento del acceso a agua y servicios básicos."),
    11: ("Transformación de la familia y protección infantil",
         "Cambios en las estructuras familiares y mayor protección infantil, en un contexto de "
         "vulnerabilidad por conflictos armados."),
    12: ("Discriminación y derechos humanos",
         "Persistencia de la discriminación y retroceso en la protección de los derechos "
         "humanos y el Estado de derecho."),
    46: ("Movilidad urbana",
         "Mayor congestión, micromovilidad y demanda de transporte público urbano."),
    58: ("Salud digital y biomedicina",
         "Medicina preventiva, personalizada y nanomedicina impulsadas por tecnología, "
         "bioimpresión 3D e IoT médico."),
    59: ("Consumo de sustancias ilícitas y tráfico de drogas",
         "Incremento del consumo y producción de drogas, con descenso del consumo de tabaco "
         "entre jóvenes."),
    57: ("Geopolítica y seguridad internacional",
         "Conflictos armados, proliferación de armas nucleares y disminución de la paz mundial, "
         "junto a la diplomacia digital."),
    13: ("Migración internacional",
         "Aumento de la migración internacional y la población refugiada, incluyendo la "
         "migración venezolana y la emigración peruana."),
    26: ("Contaminación oceánica",
         "Aumento de plásticos, acidificación y contaminación de los océanos, junto con el "
         "incremento del nivel del mar."),
    48: ("Mercado inmobiliario",
         "Mayor demanda de vivienda, alquileres y edificios inteligentes, con crecimiento del "
         "mercado inmobiliario."),
    49: ("Bioeconomía e industria sostenible",
         "Transformación tecnológica de procesos productivos hacia biomateriales y "
         "sostenibilidad empresarial."),
    44: ("Exportación de recursos minerales",
         "Mayor participación y recuperación de la exportación de recursos minerales y el "
         "empleo en el sector minero."),
    16: ("Bienestar emocional",
         "Estancamiento de la felicidad y aumento de trastornos afectivos e individualismo."),
    14: ("Solidaridad y voluntariado",
         "Recuperación de la solidaridad y el voluntariado, pese a la desaceleración de "
         "actitudes filantrópicas."),
    8: ("Urbanización y vivienda precaria",
        "Mayor concentración urbana y población en barrios marginales, con avances en planes "
        "de desarrollo urbano."),
    53: ("Gobierno digital y participación ciudadana",
         "Mayor participación ciudadana por medios digitales y expansión de servicios de "
         "gobierno digital."),
    47: ("Movilidad sostenible",
         "Creciente interés en vehículos eléctricos y autónomos, y preocupación por "
         "descarbonizar el transporte."),
    56: ("Defensa y seguridad nacional",
         "Mayor demanda de tecnología militar y actividad espacial como parte de la seguridad "
         "nacional."),
    15: ("Transformación de creencias religiosas",
         "Cambios en las creencias y restricciones religiosas."),
}


def main() -> None:
    df = pd.read_csv(REVIEW_CSV, encoding="utf-8-sig")
    present_clusters = set(df["cluster"].unique().tolist())
    missing_names = present_clusters - set(CLUSTER_NAMES)
    assert not missing_names, f"clusters with no assigned name: {missing_names}"

    remap: dict[str, dict] = {}
    summary_lines = [f"# CEPLAN consolidation — {len(df)} tendencias -> {len(CLUSTER_NAMES)} clusters", ""]
    for cluster_id, group in df.groupby("cluster"):
        name, description = CLUSTER_NAMES[cluster_id]
        cluster_doc_id = f"CEPLAN_CLUSTER_{cluster_id:02d}"
        for _, row in group.iterrows():
            remap[row["doc_id"]] = {
                "cluster_doc_id": cluster_doc_id,
                "cluster_titulo": name,
            }
        summary_lines.append(f"## {name} ({cluster_doc_id}, {len(group)} tendencias)")
        summary_lines.append(description)
        summary_lines.append("")
        for _, row in group.iterrows():
            summary_lines.append(f"- {row['titulo']} ({row['doc_id']})")
        summary_lines.append("")

    OUT_REMAP.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_REMAP, "w", encoding="utf-8") as f:
        json.dump(remap, f, ensure_ascii=False, indent=2)
    print(f"OK: {len(df)} tendencias CEPLAN -> {len(CLUSTER_NAMES)} clusters -> {OUT_REMAP}")

    OUT_SUMMARY.write_text("\n".join(summary_lines), encoding="utf-8")
    print(f"Wrote summary: {OUT_SUMMARY}")


if __name__ == "__main__":
    main()

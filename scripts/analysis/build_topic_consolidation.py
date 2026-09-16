#!/usr/bin/env python3
"""Consolidates the 432 normalized topics (from cluster_normalized_topics.py's
embedding-based clustering, reviewed manually in salidas/topics/consolidation/
cluster_review.md) into ~49 broader normalized topics.

Reads cluster_review.csv for the cluster assignment, applies a few manual
reassignments where the embedding clustering grouped things awkwardly, gives
each surviving cluster a human-written name + description, and merges the
432 original normalized-topic entries (variants, project_ids, executing_units,
evidences, weighted avg_confidence) into the new coarser buckets.

Writes salidas/topics/projects_topics_consolidated.json (same shape as
projects_topics_current.json, but with the coarser normalized_topics list;
projects/project_topics passed through unchanged).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / 'salidas' / 'topics' / 'projects_topics_current.json'
REVIEW_CSV = ROOT / 'salidas' / 'topics' / 'consolidation' / 'cluster_review.csv'
OUT_PATH = ROOT / 'salidas' / 'topics' / 'projects_topics_consolidated.json'

# Manual fixes to the embedding-based clustering: fold cluster 4 (Peru/Latam
# history & gender politics) entirely into cluster 5 (Peru political/economic
# history) since they're the same theme split by an arbitrary cut, and move a
# couple of individually mis-clustered topics to a better-fitting cluster.
CLUSTER_MOVE = {
    # topic_name: new_cluster_id
    'Memoria histórica, género e identidad nacional': 5,
    'Arqueometalurgia prehispánica peruana': 49,
    'Arqueometría numismática de aleaciones metálicas peruanas': 49,
}
FOLD_CLUSTER = {4: 5}  # cluster_id -> target cluster_id (whole cluster merges in)

CLUSTER_NAMES = {
    5: ("Historia política y económica del Perú republicano",
        "Formación del Estado, élites, mercados laborales, partidos y política exterior "
        "peruana desde la República hasta la actualidad, en diálogo con procesos políticos "
        "y de género latinoamericanos."),
    49: ("Conservación del patrimonio arqueológico y arquitectónico",
         "Documentación, conservación y difusión —incluyendo química de materiales, "
         "arqueometalurgia, realidad virtual y turismo— del patrimonio arqueológico, "
         "arquitectónico y pictórico peruano."),
    21: ("Geometría algebraica, sistemas dinámicos y álgebra no conmutativa",
         "Investigación en matemática pura: foliaciones holomorfas, álgebras de Hopf, "
         "geometría algebraica y de contacto, y estabilidad de sistemas dinámicos y "
         "ecuaciones diferenciales."),
    44: ("Gobernanza de recursos naturales, agua y desarrollo sostenible",
         "Gobernanza del agua, la minería y los recursos naturales frente al cambio "
         "climático, con sus impactos socioeconómicos, de género y conflictos "
         "socioambientales en comunidades andinas y rurales."),
    17: ("Tecnología biomédica, asistiva y digital para el desarrollo",
         "Tecnologías de bajo costo —biomédicas, asistivas, TIC y de conectividad— "
         "desarrolladas para necesidades locales de salud, discapacidad y desarrollo rural."),
    3: ("Lenguas, letras y patrimonio cultural peruano",
        "Documentación lingüística, producción literaria y audiovisual, e investigación "
        "sobre el patrimonio cultural, histórico y artístico del Perú, desde lenguas "
        "amazónicas y de señas hasta cine, teatro y archivos coloniales."),
    9: ("Nanomateriales y biomateriales funcionales",
        "Diseño de polímeros, nanopartículas y biomateriales funcionales para "
        "aplicaciones biomédicas, sensores, energía y ambiente."),
    11: ("Materiales sostenibles para construcción y tratamiento ambiental",
         "Materiales reciclados, adsorbentes y procesos metalúrgicos o de reciclaje "
         "químico orientados a la construcción sostenible y al tratamiento de agua y residuos."),
    43: ("Energías renovables y sostenibilidad energética",
         "Desempeño, acceso y sostenibilidad de tecnologías energéticas renovables "
         "—fotovoltaica, solar térmica y eficiencia industrial— en el Perú."),
    38: ("Bienestar psicológico, identidad y salud mental",
         "Bienestar psicológico, regulación emocional y construcción de identidad en "
         "universitarios y adolescentes peruanos, incluyendo apego, género y neurocognición."),
    39: ("Interculturalidad, equidad y políticas educativas",
         "Políticas de inclusión educativa, interculturalidad y derechos ciudadanos para "
         "poblaciones indígenas, con énfasis en actitudes intergrupales e identidad nacional."),
    1: ("Minería, riesgo geológico y gestión ambiental costera",
        "Conflictos socioambientales y gestión del agua asociados a la minería andina, "
        "junto con estudios de riesgo geológico, climático y de salinización en la costa peruana."),
    14: ("Diagnóstico clínico no invasivo e imagenología médica",
         "Tecnologías de diagnóstico no invasivo —ultrasonido, termografía, pruebas "
         "moleculares— para enfermedades endémicas, COVID-19 y otras condiciones, "
         "incluyendo aplicaciones en zonas rurales."),
    37: ("Innovación docente y tecnologías educativas",
         "Estrategias pedagógicas, formación docente y herramientas digitales "
         "(videojuegos, asistentes virtuales) para mejorar la enseñanza en distintos "
         "niveles educativos."),
    47: ("Lenguas, etnohistoria y saberes ancestrales andinos",
         "Documentación lingüística e histórica de lenguas y saberes andinos —quechua, "
         "aimara, mochica—, fuentes coloniales sobre el Tahuantinsuyo, y diálogo entre "
         "conocimientos académicos e indígenas."),
    35: ("Modelización matemática y formación en matemáticas",
         "Modelos matemáticos y estadísticos aplicados a problemas educativos y "
         "económicos, junto con iniciativas de formación doctoral y didáctica matemática."),
    0: ("Química de productos naturales y bioactivos peruanos",
        "Extracción, caracterización y aplicación de compuestos bioactivos, colorantes, "
        "bioplásticos y cosméticos a partir de recursos vegetales y biodiversidad peruana."),
    48: ("Pueblos indígenas amazónicos: derechos, saberes y conservación",
         "Derechos, epistemologías y prácticas de comunidades indígenas amazónicas en su "
         "relación con el Estado, la biodiversidad y la conservación del bosque."),
    46: ("Desigualdad urbana y desarrollo territorial",
         "Gobernanza, segregación y transformación territorial en Lima y ciudades "
         "intermedias, incluyendo integración regional y fronteriza."),
    7: ("Religión, sociedad civil y bienestar en el Perú contemporáneo",
        "Religión, ética, salud pública histórica y organizaciones de la sociedad civil "
        "peruana, incluyendo bienestar subjetivo, desigualdad en salud y cultura política católica."),
    24: ("Física de altas energías y óptica cuántica",
         "Física de partículas y astropartículas, y óptica cuántica —coherencia, fases "
         "geométricas, efectos relativistas— con aplicaciones en computación cuántica."),
    25: ("Óptica de precisión y materiales semiconductores",
         "Manufactura e instrumentación óptica de precisión, materiales semiconductores y "
         "técnicas espectroscópicas/interferométricas para caracterización de superficies."),
    31: ("Motivación, resiliencia y bienestar psicosocial juvenil",
         "Motivación educativa, resiliencia psicológica y bienestar en adolescentes y "
         "jóvenes peruanos, incluyendo trabajo infantil, empleo juvenil y educación a distancia."),
    10: ("Bioquímica agrícola, ambiental y bioprocesos",
         "Química y bioquímica aplicada a la agricultura, la seguridad alimentaria y el "
         "ambiente: interacciones planta-insecto, biotoxinas, bioindicadores, "
         "biocombustibles y bioacumulación de contaminantes."),
    34: ("Memoria, derechos humanos y ciudadanía en el posconflicto",
         "Ciudadanía, reparaciones y derechos humanos en contextos de posconflicto y "
         "vulnerabilidad, incluyendo discapacidad, sistema penitenciario y acceso a la justicia."),
    20: ("Visión computacional y procesamiento de señales aplicado",
         "Algoritmos de visión computacional y procesamiento de señales aplicados a "
         "agricultura, ganadería y modelos matemáticos de biología poblacional."),
    42: ("Monitoreo ambiental con sensores y vehículos autónomos",
         "Redes de sensores, vehículos autónomos y teledetección para el monitoreo "
         "ambiental de bosques, lagunas, cuerpos de agua y gases de efecto invernadero."),
    33: ("Derecho constitucional, penal y derechos humanos",
         "Marcos normativos de protección de derechos, prueba judicial, proporcionalidad "
         "penal y filosofía del derecho, incluyendo aplicaciones de inteligencia "
         "artificial al razonamiento jurídico."),
    36: ("Comunicación digital y participación ciudadana",
         "Medios digitales, comunicación política y plataformas de participación "
         "ciudadana e innovación comunitaria."),
    6: ("Calidad, género y mercantilización en la educación superior peruana",
        "Calidad educativa, brechas de género en la carrera académica, y dinámicas de "
        "mercado en universidades peruanas, incluyendo formación policial y producción "
        "científica de posgrado."),
    2: ("Innovación empresarial y competitividad de sectores productivos peruanos",
        "Competencia, innovación y productividad en sectores como microfinanzas, "
        "gastronomía, software y manufactura peruana, incluyendo bioinsumos y "
        "bioprospección aplicados a negocios."),
    19: ("Diagnóstico, optimización y gestión de sistemas industriales",
         "Diagnóstico de fallas, optimización de procesos y gestión del conocimiento en "
         "sistemas industriales y de infraestructura energética."),
    29: ("Apego, crianza y desarrollo infantil temprano",
         "Apego materno y paterno, crianza y calidad de servicios de atención a la "
         "primera infancia en contextos de vulnerabilidad."),
    32: ("Filosofía contemporánea: lenguaje, fenomenología y poder",
         "Filosofía del lenguaje, fenomenología, filosofía política y de la mente, desde "
         "clásicos como Platón hasta debates contemporáneos sobre constructivismo y "
         "crítica social."),
    8: ("Química de coordinación y materiales inorgánicos funcionales",
        "Síntesis de pigmentos, biopolímeros y complejos metálicos con actividad "
        "antitumoral o insulino-mimética."),
    22: ("Instrumentación nuclear y de resonancia magnética",
         "Detección de radiación natural y contaminantes radiactivos, e infraestructura "
         "de resonancia magnética nuclear para biología estructural y ciencia de alimentos."),
    23: ("Procesos estocásticos y dinámica no lineal",
         "Modelamiento de frentes de reacción-difusión, condensación y grandes "
         "desviaciones en sistemas de partículas interactuantes, y dinámica molecular de "
         "líquidos iónicos."),
    27: ("Consumo de sustancias y conductas de riesgo juvenil",
         "Consumo de drogas, políticas antidrogas y conductas de riesgo en adolescentes y "
         "jóvenes, incluyendo su relación con la justicia juvenil y el narcotráfico."),
    40: ("Adaptación transcultural, migración y desarrollo cognitivo indígena",
         "Validación transcultural de instrumentos psicométricos y estudios de desarrollo "
         "cognitivo y migración en poblaciones indígenas y latinoamericanas."),
    26: ("Violencia de género y respuesta institucional",
         "Violencia de género, acoso sexual y violencia hacia la niñez y la diversidad "
         "sexual, y las respuestas institucionales y de política pública frente a ellas."),
    18: ("Diseño mecánico, estructuras y biomecánica aplicada",
         "Diseño y caracterización de conexiones estructurales de acero, equipos "
         "electromecánicos y dispositivos de evaluación biomecánica."),
    15: ("Paisaje sonoro y movilidad urbana",
         "Memoria auditiva urbana, contaminación sonora y sistemas de información para "
         "la movilidad y el tráfico en la ciudad."),
    41: ("Ingeniería sísmica y geotecnia",
         "Modelamiento de vibraciones ambientales, riesgo sísmico y comportamiento de "
         "suelos y sistemas constructivos ante sismos."),
    30: ("Género, participación y desarrollo económico local",
         "Emprendimiento femenino, liderazgo político y transversalización de género en "
         "la gobernanza municipal y el desarrollo rural."),
    28: ("Psicodiagnóstico, salud ocupacional y envejecimiento",
         "Adaptación de pruebas psicométricas proyectivas, salud ocupacional "
         "penitenciaria y evaluación funcional del envejecimiento."),
    45: ("Contaminación atmosférica y metabolismo urbano en Lima",
         "Monitoreo de contaminación industrial, metabolismo de recursos y variabilidad "
         "climática en Lima Metropolitana."),
    13: ("Combustión y materiales para energía térmica",
         "Materiales cerámicos para pilas de combustible, cocinas eficientes de altura y "
         "combustión dual diésel-gas natural."),
    12: ("Valorización energética de biomasa y residuos",
         "Pirólisis, producción de grafeno y plataformas nacionales de bioenergía a "
         "partir de biomasa y residuos agrícolas o forestales."),
    16: ("Robótica móvil y drones",
         "Drones para teledetección y navegación autónoma, y robots móviles para "
         "telepresencia, logística y competencias RoboCup."),
}


def main():
    with open(DATA_PATH, encoding='utf-8') as f:
        data = json.load(f)
    norms_by_name = {n['normalized_topic']: n for n in data['normalized_topics']}
    assert len(norms_by_name) == len(data['normalized_topics']), 'duplicate normalized_topic names!'

    df = pd.read_csv(REVIEW_CSV, encoding='utf-8-sig')
    assert set(df['normalized_topic']) == set(norms_by_name), 'cluster_review.csv out of sync with current data'

    for topic_name, new_cluster in CLUSTER_MOVE.items():
        df.loc[df['normalized_topic'] == topic_name, 'cluster'] = new_cluster
    for old_cluster, new_cluster in FOLD_CLUSTER.items():
        df.loc[df['cluster'] == old_cluster, 'cluster'] = new_cluster

    present_clusters = set(df['cluster'].unique().tolist())
    missing_names = present_clusters - set(CLUSTER_NAMES)
    assert not missing_names, f'clusters with no assigned name: {missing_names}'

    consolidated = []
    for cluster_id, group in df.groupby('cluster'):
        name, description = CLUSTER_NAMES[cluster_id]
        members = [norms_by_name[t] for t in group['normalized_topic']]

        variants, project_ids, executing_units, evidences = [], [], [], []
        weighted_conf_sum, weight_total = 0.0, 0
        for m in members:
            variants.extend(m['variants'])
            for pid in m['project_ids']:
                if pid not in project_ids:
                    project_ids.append(pid)
            for eu in m['executing_units']:
                if eu not in executing_units:
                    executing_units.append(eu)
            evidences.extend(m['evidences'])
            weighted_conf_sum += m['avg_confidence'] * m['count']
            weight_total += m['count']

        consolidated.append({
            'normalized_topic': name,
            'description': description,
            'variants': variants,
            'project_ids': project_ids,
            'executing_units': executing_units,
            'count': len(variants),
            'avg_confidence': round(weighted_conf_sum / weight_total, 2),
            'evidences': evidences,
            'component_topics': sorted({m['normalized_topic'] for m in members}),
        })

    consolidated.sort(key=lambda n: len(n['project_ids']), reverse=True)

    total_variants = sum(n['count'] for n in consolidated)
    assert total_variants == sum(n['count'] for n in data['normalized_topics']), (
        f'variant count mismatch: {total_variants} vs '
        f"{sum(n['count'] for n in data['normalized_topics'])}"
    )

    out_data = dict(data)
    out_data['normalized_topics'] = consolidated
    out_data['metadata'] = dict(data['metadata'])
    out_data['metadata']['num_normalized_topics'] = len(consolidated)
    out_data['metadata']['dataset_title'] = (
        'Proyectos de investigación PUCP cerrados (2010-2020) — temas consolidados'
    )
    out_data['metadata']['note'] = (
        data['metadata']['note'] + ' Consolidación: los 432 temas normalizados originales se '
        f'agruparon en {len(consolidated)} temas mediante clustering jerárquico sobre embeddings '
        '(paraphrase-multilingual-MiniLM-L12-v2) de nombre+descripción, seguido de revisión manual '
        'de cada grupo (ver scripts/analysis/build_topic_consolidation.py). Cada tema consolidado '
        'conserva sus temas normalizados originales en "component_topics".'
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)

    print(f'OK: {len(data["normalized_topics"])} normalized topics -> {len(consolidated)} consolidated '
          f'topics -> {OUT_PATH}')


if __name__ == '__main__':
    main()

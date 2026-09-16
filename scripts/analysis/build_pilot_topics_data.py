# -*- coding: utf-8 -*-
"""Builds the pilot extracted+normalized topics JSON from a hand-authored
extraction (done by Claude reading each project's cris_abstract/keywords,
following the methodology of the exemplar explorador_temas.html).

This is the source-of-truth for the 36-project pilot referenced in
docs/topic_normalization_pipeline.md: it records, as code, exactly which
topics were read out of which project and how they were grouped, so the
pilot JSON (gitignored, like the rest of salidas/) can be regenerated and
audited. Run `topic_extraction_prep.py` first to (re)produce the units file
this script reads.
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UNITS_PATH = REPO_ROOT / "salidas" / "topics" / "projects_units_pilot.json"
OUT_PATH = REPO_ROOT / "salidas" / "topics" / "projects_topics_pilot.json"

with open(UNITS_PATH, encoding="utf-8") as f:
    units = json.load(f)
for u in units:
    u["project_id"] = u.pop("unit_id")
units_by_id = {u["project_id"]: u for u in units}

# project_id -> list of (topic, description, evidence, confidence)
EXTRACTED = {
"872": [
    ("Modelización matemática y tecnología digital en la enseñanza",
     "Integra modelización matemática y tecnología digital para articular geometría y análisis en la formación continua de profesores.",
     "integre la modelización matemática y la tecnología digital en una propuesta para favorecer la articulación de los dominios de la geometría y del análisis en la formación continua del profesor de matemática", 0.95),
    ("Formación continua de docentes de matemática",
     "Marco teórico (Espacio de Trabajo Matemático, Ingeniería Didáctica) orientado a fortalecer la formación de profesores de matemática con mirada internacional.",
     "contribuir con la formación continua de profesores de matemática mediante un trabajo que tiene una mirada internacional", 0.9),
],
"139": [
    ("Modelos estadísticos de regresión para datos limitados",
     "Desarrollo de modelos de regresión en el intervalo unitario para datos con exceso de ceros y censura.",
     "desarrollar modelos de regresión para variables en el intervalo unitario que contemple la regresión binaria y la regresión de proporciones con respuesta limitada y con exceso de ceros", 0.95),
    ("Análisis estadístico de resultados electorales",
     "Aplicación de los modelos de regresión al análisis de proporciones de votación por partido a nivel subnacional.",
     "modelar la proporción obtenida por un determinado partido o movimiento político en una determinada elección a nivel de departamentos, provincias y distritos", 0.9),
],
"547": [
    ("Materiales semiconductores de amplio ancho de banda",
     "Estudio de nitruros (Si3N4, AlN) por sus propiedades ópticas y térmicas frente a semiconductores convencionales.",
     "materiales con un amplio ancho de banda como nitruro de silicio (Si3N4) o nitruro de aluminio (AlN) son de creciente interés en investigación y desarrollo para aplicaciones ópticas", 0.93),
    ("Dopaje con tierras raras para emisión óptica",
     "Dopaje de semiconductores amorfos con iones de tierras raras para lograr emisión de luz en colores básicos.",
     "al dopar estos semiconductores con iones de tierras raras también permiten la emisión de luz a temperatura de ambiente, cubriendo por ejemplo los colores básicos azul (Tm3+), verde (Tb3+) y rojo (Eu3+)", 0.92),
],
"805": [
    ("Hidrogeles inteligentes sensibles a estímulos",
     "Síntesis de hidrogeles responsivos a temperatura y pH con estabilidad mecánica.",
     "estos materiales mostraron sensibilidad a cambios de temperatura y cambios de pH del medio", 0.95),
    ("Remediación de contaminantes textiles mediante absorción",
     "Capacidad de los hidrogeles para absorber pigmentos como el azul de metileno, contaminante de aguas residuales textiles.",
     "capacidad de absorber pigmentos por ejemplo el azul de metileno, pigmento usado en la industria textil y que aparece como impureza en las aguas residuales de este tipo de industria", 0.85),
],
"818": [
    ("Ingeniería de banda prohibida en semiconductores amorfos",
     "Manipulación de la estequiometría de SiNx para ajustar el bandgap óptico del material.",
     "tailor the optical bandgap of this material by manipulating its stoichiometry", 0.93),
    ("Materiales para dispositivos optoelectrónicos y fotovoltaicos",
     "Aplicación en pasivación y dispositivos fotoelectroquímicos para producción de hidrógeno.",
     "a-SiC:H is currently a candidate to serve as photo-electrode in photo-electrochemical devices for hydrogen production", 0.85),
],
"295": [
    ("Bioadhesión y biomateriales de origen natural",
     "Estudio de mecanismos de adhesión biológica (seda de araña, colágeno) para desarrollar bioadhesivos.",
     "estudió los mecanismos de adhesión que ocurren en sistemas biológicos, como la adhesión de la seda de araña y la adhesión de proteínas animales como el colágeno", 0.95),
    ("Aplicaciones biomédicas de nuevos adhesivos",
     "Desarrollo de adhesivos no tóxicos para uso en biomedicina: tejidos, sensores y transporte de fármacos.",
     "desarrollo de nuevos adhesivos de origen natural, no tóxicos, para aplicaciones en biomedicina como adhesivo de tejidos, sensores para el reconocimiento molecular, transporte de fármacos", 0.9),
],
"403": [
    ("Reciclaje de materiales compuestos plástico-madera",
     "Desarrollo de procesos de sinterizado de plástico reciclado (PP, HDPE) y madera recuperada para piezas industriales.",
     "procesos de sinterizado en materiales compuestos de polipropileno (PP) y polietileno de alta densidad (HDPE) reciclados y madera capirona (MC) recuperada", 0.95),
    ("Gestión de residuos sólidos y economía circular industrial",
     "Motivado por la contaminación de residuos sólidos, busca soluciones económicamente viables para la industria.",
     "la contaminación ambiental producida por los residuos sólidos... son los problemas más relevantes que impulsaron el desarrollo del presente proyecto", 0.88),
],
"212": [
    ("Imagenología cuantitativa por ultrasonido",
     "Uso de promediado angular completo para mejorar la precisión de la estimación de atenuación ultrasónica.",
     "aplicación de promediado angular completo para extender el compromiso entre resolución espacial y precisión en la formación de imágenes cuantitativas de atenuación ultrasónica", 0.94),
    ("Diagnóstico temprano del cáncer de mama",
     "Mejora de herramientas complementarias a la mamografía para el diagnóstico de lesiones mamarias.",
     "el cáncer de mama es la mayor causa de mortandad por cáncer en mujeres a nivel mundial... este estudio tiene implicancias directas en el diagnóstico de cáncer de mama", 0.9),
],
"451": [
    ("Ultrasonido cuantitativo para diagnóstico clínico",
     "Uso de QUS (ultrasonido cuantitativo) para estimar parámetros de tejidos y mejorar el diagnóstico no invasivo.",
     "una herramienta con potencial para el diagnóstico de NAFLD es el ultrasonido cuantitativo (QUS)", 0.93),
    ("Diagnóstico de hígado graso no alcohólico (NAFLD)",
     "Corrección de aberración para mejorar la aplicabilidad clínica de QUS en pacientes obesos con NAFLD.",
     "extender la aplicabilidad de QUS al manejo clínico de NAFLD", 0.92),
],
"889": [
    ("Vivienda sismorresistente de bajo costo",
     "Bloques de tierra comprimida ensamblables para regiones de alta sismicidad.",
     "desarrollar una solución para la vivienda ecoamigable localizada en regiones de alta sismicidad... uso de bloques de tierra comprimida", 0.95),
    ("Materiales de construcción sostenibles",
     "Sistema constructivo con materiales tradicionales y confort térmico, orientado a formalización normativa.",
     "un estudio termo-higrométrico a nivel del material e indicadores que cuantifiquen las propiedades térmicas de la solución constructiva que se propone", 0.88),
],
"881": [
    ("Conservación del patrimonio arqueológico costero",
     "Identificación de factores climáticos, geológicos y culturales que amenazan sitios arqueológicos de la costa.",
     "el patrimonio arqueológico de la costa... se encuentra bajo constante peligro de destrucción por efecto de tres factores... climático (El Niño), geológico (movimientos tectónicos) y culturales", 0.96),
    ("Gestión de riesgos ante cambio climático en sitios patrimoniales",
     "Propuesta metodológica replicable para identificar riesgos climáticos en el patrimonio costero.",
     "elaborar una propuesta metodológica que permita identificar los factores de riesgo, su impacto y proyección a futuro", 0.85),
],
"27": [
    ("Arqueología mochica en el valle de Jequetepeque",
     "Excavaciones en San José de Moro enfocadas en el periodo Mochica Medio.",
     "excavación de los estratos más profundos, los mismos que pertenecen al periodo de tiempo... periodo denominado Mochica Medio", 0.94),
    ("Prácticas funerarias y rituales prehispánicos",
     "Estudio de tumbas y contextos funerarios/ceremoniales asociados a la élite mochica.",
     "brindará importantes datos para el entendimiento de las prácticas funerarias y costumbres culturales durante este periodo", 0.88),
],
"870": [
    ("Memoria histórica y género en la independencia",
     "Revisión de la ausencia de mujeres en los relatos históricos sobre la independencia peruana.",
     "generando un relato histórico incierto acerca de la ausencia de las mujeres en los procesos de independencia y de emancipación", 0.95),
    ("Historia de género desde perspectivas feministas",
     "Uso de categorías feministas para reinterpretar figuras históricas femeninas.",
     "hace uso de categorías propuestas desde los feminismos acerca de lo político", 0.85),
],
"337": [
    ("Literatura histórica para público escolar",
     "Novela histórica ambientada en la Lima colonial dirigida a escolares.",
     "novela histórica sobre Lima en el siglo XVII, y la historia de Juan Tasayco, un muchacho de Lurín... para escolares", 0.9),
],
"412": [
    ("Enseñanza crítica de la historia reciente",
     "Busca superar métodos memorísticos para desarrollar razonamiento histórico crítico en estudiantes.",
     "los planteamientos psicopedagógicos más recientes para enseñar historia plantean que esta debe desarrollar el razonamiento histórico en los estudiantes desde una perspectiva crítica", 0.93),
    ("Formación docente en temas sensibles y dilemas morales",
     "Concepciones y dilemas morales de los docentes al enseñar historia reciente y conflicto armado.",
     "investigar las concepciones pedagógicas que los docentes de secundaria tienen sobre la enseñanza de la historia... y los dilemas morales por los que atraviesan", 0.9),
],
"500": [
    ("Crianza positiva en contextos de vulnerabilidad",
     "Validación de un programa de videofeedback para mejorar la sensibilidad materna en madres privadas de libertad.",
     "evaluar la eficacia de este programa en un grupo de madres privadas de su libertad y a partir de ello, incrementar el comportamiento sensitivo de las madres", 0.95),
    ("Apego y desarrollo emocional infantil en prisión",
     "El encarcelamiento materno como riesgo para el desarrollo emocional del niño.",
     "la situación en la que las madres privadas de su libertad hacen frente a la maternidad constituye un riesgo para el desarrollo emocional del niño", 0.88),
],
"616": [
    ("Consumo de alcohol y drogas en universitarios",
     "Prevalencia y predicción del binge drinking y consumo de marihuana en estudiantes universitarios.",
     "existe una prevalencia anual de consumo de alcohol de 71.7%... la marihuana tiene una prevalencia por año en universitarios de 4.3%", 0.95),
    ("Teoría de la acción planificada aplicada a conductas de riesgo",
     "Uso del modelo TPB (actitud, norma subjetiva, control conductual) para predecir conductas de consumo.",
     "la Teoría de la Acción Planeada... ha demostrado explicar y predecir satisfactoriamente la conducta y la intención de realizar binge drinking", 0.9),
],
"600": [
    ("Educación intercultural bilingüe en la Amazonía",
     "Fortalecimiento de acompañantes pedagógicos indígenas en comunidades Asháninka y Shipibo-Konibo.",
     "docentes indígenas de la región Ucayali, que vienen trabajando acompañando a profesores de aula en comunidades Asháninka y Shipibo-Konibo", 0.95),
    ("Investigación-acción para fortalecimiento docente",
     "Diagnóstico y programa ad hoc para reforzar capacidades de acompañamiento psicopedagógico.",
     "se implementará un programa ad hoc para reforzar las capacidades de este grupo de acompañantes", 0.85),
],
"813": [
    ("Inclusión de becarios indígenas en la educación superior",
     "Modos de organización de universidades peruanas para atender a becarios de comunidades nativas amazónicas y EIB.",
     "cómo responde la universidad a la presencia de los becarios de poblaciones amazónicas e indígenas", 0.95),
    ("Gestión universitaria y equidad educativa",
     "Análisis de los arreglos institucionales que incluyen o excluyen a estudiantes becados.",
     "qué arreglos organizativos surgen para atender a esta población... y cómo estos arreglos incluyen o excluyen a los estudiantes", 0.88),
],
"108": [
    ("Descentralización de la gestión educativa",
     "Rol de los gobiernos municipales en la educación, estudiado en cuatro municipios de Piura.",
     "estudia la descentralización educativa en Piura, así como el rol de la gestión municipal en la educación", 0.92),
],
"533": [
    ("Diálogo intercultural de saberes andinos",
     "Articulación de conocimientos y prácticas andinas con la formación universitaria en justicia y bienestar.",
     "articular conocimientos y prácticas de la cultura andina a la formación universitaria, en el campo del establecimiento de la justicia y el bienestar", 0.94),
    ("Justicia comunitaria y bienestar emocional",
     "Noción integral de justicia vinculada al bienestar (allin kawsay) desde una perspectiva intercultural.",
     "una noción integral de justicia está fuertemente relacionada con el bienestar y la salud emocional, noción que en la cultura andina corresponde al allin kawsay", 0.9),
],
"598": [
    ("Gobernanza e instituciones deportivas",
     "Análisis de las lógicas institucionales detrás de la crisis del fútbol peruano.",
     "identificar las lógicas y los marcos institucionales que intervienen en el gobierno del fútbol peruano", 0.93),
    ("Informalidad y crisis organizacional en el deporte",
     "Tensión entre lógicas patrimonialistas y de negocio moderno en la gestión futbolística.",
     "subsisten lógicas patrimonialistas enraizadas históricamente junto con lógicas modernas y de negocio", 0.85),
],
"913": [
    ("Liderazgo y participación de mujeres indígenas",
     "Barreras culturales y sociales que excluyen a mujeres indígenas de la toma de decisiones comunitarias.",
     "por qué las mujeres aún están excluidas de la toma de decisiones comunitarias, revelando los determinantes culturales y sociales que las bloquean", 0.96),
    ("Gestión comunitaria de recursos naturales amazónicos",
     "Rol de las mujeres en la seguridad alimentaria y en la gestión de tierras y aguas amazónicas.",
     "las mujeres juegan un papel fundamental en la seguridad alimentaria, la preservación de la biodiversidad... y la gestión y defensa de las tierras y aguas amazónicas", 0.88),
],
"906": [
    ("Respuesta indígena a políticas sanitarias estatales",
     "Traducción cultural del \"aislamiento social\" decretado por el Estado en comunidades Kukama y Urarinas.",
     "comprender las formas y la organización del cuidado en las comunidades Kukama y Urarinas del Bajo Marañón... cómo las disposiciones estatales se han llevado a cabo durante la pandemia", 0.95),
    ("Cuidado comunitario y prácticas de género en la Amazonía",
     "Roles diferenciados de cuidado entre mujeres y varones frente a la pandemia.",
     "las relaciones de cuidado permiten también identificar los roles diferenciados de las mujeres y los varones", 0.87),
],
"874": [
    ("Memoria del conflicto armado interno en comunidades indígenas",
     "Normalización de la violencia en el contexto del estado de emergencia en Satipo.",
     "el proceso de normalización de la violencia en el contexto del estado de emergencia... entendiendo como una prolongación del conflicto armado interno", 0.93),
    ("Experiencia educativa de jóvenes indígenas",
     "Negociaciones identitarias de estudiantes indígenas dentro del sistema educativo.",
     "las negociaciones que se ponen en marcha entre los estudiantes indígenas para dar sentido a su experiencia educativa desde sus identidades locales", 0.88),
],
"101": [
    ("Innovación en telecomunicaciones móviles",
     "Apertura de redes móviles para habilitar innovación en aplicaciones y desarrollo de software.",
     "las redes móviles siguen manteniendo características de redes cerradas... bloqueando la posibilidad de la innovación", 0.92),
    ("TIC para el desarrollo socioeconómico rural",
     "Uso de tecnología móvil para llevar información y desarrollo a zonas rurales remotas.",
     "poder llevar información y desarrollo a través de estas redes, sobre todo a la población que reside en áreas rurales remotas", 0.88),
],
"479": [
    ("Impacto social de becas de educación superior",
     "Efectos de Beca 18 en la ampliación de escolaridad de jóvenes en situación de pobreza.",
     "identificar efectos del proceso de inserción en la educación superior de jóvenes beneficiarios/as del Programa Nacional BECA18", 0.94),
    ("Movilidad social y equidad educativa",
     "Enfoque familiar/económico, más allá de los retornos laborales, para entender el acceso a educación superior.",
     "explorar otras valoraciones sobre educación... diferentes a las que usualmente son medidas en términos de los retornos económicos", 0.85),
],
"927": [
    ("Ciudadanía digital y derechos de la niñez",
     "Agendas y políticas orientadas a proteger los derechos digitales de niñas, niños y adolescentes.",
     "generar conocimiento sobre la ciudadanía digital de los NNA para influir en agendas y políticas que protejan los derechos de los NNA", 0.95),
],
"6": [
    ("Reforma del derecho penal y política criminal",
     "Sistematización de criterios de imputación de responsabilidad penal conforme a principios constitucionales.",
     "desarrollar y sistematizar dichos criterios de imputación de responsabilidad penal... interpretar la legislación con arreglo a los principios constitucionales", 0.93),
    ("Seguridad jurídica y acceso a la justicia",
     "La eficacia del sistema de resolución de conflictos como condición para el desarrollo social.",
     "la existencia de un sistema de resolución de conflictos eficaz, objetivo, previsible y oportuno, es una condición imprescindible para el desarrollo de la sociedad", 0.85),
],
"732": [
    ("Sistemas internacionales de protección de derechos humanos",
     "Análisis del Sistema Interamericano y su relación con el ordenamiento jurídico peruano.",
     "un análisis más detallado en lo que respecta al Sistema Interamericano debido a la pertenencia del Perú al mismo", 0.93),
    ("Acceso a la justicia interamericana",
     "El Perú como el país con mayor número de casos ante la Corte Interamericana de Derechos Humanos.",
     "el hecho que el Perú es el país con mayor número de casos ante la Corte Interamericana de Derechos Humanos", 0.87),
],
"441": [
    ("Laicidad y libertad religiosa en el Estado",
     "Tratamiento estatal del principio de laicidad frente a la relación Estado-Iglesia Católica.",
     "cuestionar el tratamiento conferido por algunos órganos estatales... a ciertas manifestaciones en las que se pone en entredicho el principio de laicidad del Estado", 0.94),
],
"759": [
    ("Impacto del cambio climático en cadenas agroexportadoras",
     "Efectos del cambio climático sobre la exportación de quinua peruana.",
     "identificar los efectos del cambio climático sobre estas exportaciones, particularmente el caso de la quinua", 0.95),
    ("Crecimiento verde inclusivo y pequeños productores",
     "La quinua como eje de crecimiento verde inclusivo, pese a la paradoja pobreza-biodiversidad.",
     "es un eje central de crecimiento verde inclusivo para un país como el nuestro. Paradójicamente, las zonas... de mayor diversidad, son también las de mayor pobreza", 0.87),
],
"460": [
    ("Gobernanza institucional de la Amazonía",
     "Emergencia de áreas naturales protegidas, territorio indígena comunal y consulta previa como instituciones.",
     "estudiaremos la emergencia de tres instituciones: las áreas naturales protegidas, el territorio indígena comunal y la consulta previa", 0.93),
    ("Economía extractiva y bienes comunes ambientales",
     "La Amazonía como fuente de bienes comunes y servicios ambientales críticos para el bienestar del planeta.",
     "una fuente de bienes comunes y servicios ambientales de importancia crítica para el bienestar del planeta", 0.87),
],
"148": [
    ("Desigualdad económica y herencia colonial",
     "Factores históricos, económicos y políticos que explican la persistencia de la desigualdad en el Perú.",
     "el nivel y la persistencia de la desigualdad en el largo periodo... se debe a factores históricos... económicos... y políticos", 0.95),
    ("Distribución del ingreso y política fiscal",
     "El coeficiente de Gini y el carácter regresivo de la política fiscal como determinantes de la desigualdad.",
     "el valor de largo plazo de la desigualdad se ha mantenido en torno a 0.60, medido por el coeficiente de Gini", 0.88),
],
"215": [
    ("Infraestructura subterránea y patrimonio cultural",
     "Trazado de una vía subterránea que protege el patrimonio del centro histórico de Lima.",
     "conjuga teorías matemáticas como la topología, teoría de grafos y geometría computacional junto con variables de arquitectura y valora el cuidado del patrimonio cultural", 0.92),
],
"370": [
    ("Conservación de patrimonio religioso colonial",
     "Estudio histórico-arquitectónico de dos monasterios limeños en riesgo de deterioro.",
     "dos conjuntos monumentales... se ha elegido trabajar son recintos de vida contemplativa... insertas en un contexto actualmente degradado", 0.93),
    ("Metodología de análisis comparado de patrimonio arquitectónico",
     "Modelo replicable para analizar por contraste otros conjuntos monásticos del casco histórico.",
     "desarrollar un modelo que nos permita analizar por contraste otros conjuntos monásticos del casco histórico", 0.85),
],
}

# normalized_topic -> (description, [(project_id, topic_text), ...])
NORMALIZED = {
"Materiales semiconductores avanzados y optoelectrónica": (
    "Diseño y caracterización de semiconductores de banda ancha y su dopaje para aplicaciones ópticas y optoelectrónicas.",
    [("547", "Materiales semiconductores de amplio ancho de banda"),
     ("547", "Dopaje con tierras raras para emisión óptica"),
     ("818", "Ingeniería de banda prohibida en semiconductores amorfos"),
     ("818", "Materiales para dispositivos optoelectrónicos y fotovoltaicos")],
),
"Materiales poliméricos funcionales y biomateriales": (
    "Polímeros y adhesivos de origen natural o sintético diseñados para responder a estímulos o cumplir funciones biomédicas/ambientales.",
    [("805", "Hidrogeles inteligentes sensibles a estímulos"),
     ("805", "Remediación de contaminantes textiles mediante absorción"),
     ("295", "Bioadhesión y biomateriales de origen natural"),
     ("295", "Aplicaciones biomédicas de nuevos adhesivos")],
),
"Materiales y sistemas constructivos sostenibles": (
    "Materiales reciclados o tradicionales aplicados a soluciones constructivas económicas, sismorresistentes y de menor impacto ambiental.",
    [("403", "Reciclaje de materiales compuestos plástico-madera"),
     ("403", "Gestión de residuos sólidos y economía circular industrial"),
     ("889", "Vivienda sismorresistente de bajo costo"),
     ("889", "Materiales de construcción sostenibles"),
     ("215", "Infraestructura subterránea y patrimonio cultural")],
),
"Ultrasonido cuantitativo para diagnóstico clínico": (
    "Técnicas de imagenología y caracterización cuantitativa por ultrasonido aplicadas al diagnóstico de cáncer de mama e hígado graso.",
    [("212", "Imagenología cuantitativa por ultrasonido"),
     ("212", "Diagnóstico temprano del cáncer de mama"),
     ("451", "Ultrasonido cuantitativo para diagnóstico clínico"),
     ("451", "Diagnóstico de hígado graso no alcohólico (NAFLD)")],
),
"Modelización matemática y métodos estadísticos aplicados": (
    "Modelos matemáticos y estadísticos (regresión, modelización didáctica) aplicados a problemas educativos y sociopolíticos.",
    [("872", "Modelización matemática y tecnología digital en la enseñanza"),
     ("139", "Modelos estadísticos de regresión para datos limitados"),
     ("139", "Análisis estadístico de resultados electorales")],
),
"Formación e innovación docente": (
    "Estrategias e investigación-acción orientadas a fortalecer las capacidades pedagógicas y el pensamiento crítico de los docentes.",
    [("872", "Formación continua de docentes de matemática"),
     ("412", "Enseñanza crítica de la historia reciente"),
     ("412", "Formación docente en temas sensibles y dilemas morales"),
     ("600", "Investigación-acción para fortalecimiento docente")],
),
"Investigación y conservación del patrimonio arqueológico y arquitectónico": (
    "Documentación, riesgos y conservación de sitios arqueológicos y arquitectónicos, desde metodologías de excavación hasta análisis de riesgo climático.",
    [("881", "Conservación del patrimonio arqueológico costero"),
     ("881", "Gestión de riesgos ante cambio climático en sitios patrimoniales"),
     ("27", "Arqueología mochica en el valle de Jequetepeque"),
     ("27", "Prácticas funerarias y rituales prehispánicos"),
     ("370", "Conservación de patrimonio religioso colonial"),
     ("370", "Metodología de análisis comparado de patrimonio arquitectónico")],
),
"Memoria histórica, género e identidad nacional": (
    "Revisión crítica de relatos históricos nacionales desde una perspectiva de género, incluyendo su divulgación a públicos escolares.",
    [("870", "Memoria histórica y género en la independencia"),
     ("870", "Historia de género desde perspectivas feministas"),
     ("337", "Literatura histórica para público escolar")],
),
"Crianza, apego y desarrollo infantil en contextos de vulnerabilidad": (
    "Intervenciones sobre crianza y apego dirigidas a fortalecer el vínculo materno-infantil en poblaciones en riesgo.",
    [("500", "Crianza positiva en contextos de vulnerabilidad"),
     ("500", "Apego y desarrollo emocional infantil en prisión")],
),
"Conductas de riesgo y salud en jóvenes universitarios": (
    "Prevalencia y modelos psicológicos predictivos de conductas de consumo de sustancias en población universitaria.",
    [("616", "Consumo de alcohol y drogas en universitarios"),
     ("616", "Teoría de la acción planificada aplicada a conductas de riesgo")],
),
"Equidad, inclusión y gestión de políticas educativas": (
    "Políticas y arreglos institucionales orientados a la inclusión educativa de poblaciones indígenas y en pobreza, y a la gestión descentralizada de la educación.",
    [("600", "Educación intercultural bilingüe en la Amazonía"),
     ("813", "Inclusión de becarios indígenas en la educación superior"),
     ("813", "Gestión universitaria y equidad educativa"),
     ("479", "Impacto social de becas de educación superior"),
     ("479", "Movilidad social y equidad educativa"),
     ("108", "Descentralización de la gestión educativa")],
),
"Diálogo intercultural y saberes ancestrales": (
    "Articulación de conocimientos y prácticas ancestrales andinas con marcos institucionales de justicia y bienestar.",
    [("533", "Diálogo intercultural de saberes andinos"),
     ("533", "Justicia comunitaria y bienestar emocional")],
),
"Pueblos indígenas amazónicos: derechos, género y Estado": (
    "Liderazgo, cuidado y memoria de comunidades indígenas amazónicas en su relación con políticas y presencia del Estado.",
    [("913", "Liderazgo y participación de mujeres indígenas"),
     ("913", "Gestión comunitaria de recursos naturales amazónicos"),
     ("906", "Respuesta indígena a políticas sanitarias estatales"),
     ("906", "Cuidado comunitario y prácticas de género en la Amazonía"),
     ("874", "Memoria del conflicto armado interno en comunidades indígenas"),
     ("874", "Experiencia educativa de jóvenes indígenas")],
),
"Gobernanza y crisis institucional en el deporte": (
    "Lógicas institucionales y organizacionales detrás de crisis de gobernanza en el fútbol profesional peruano.",
    [("598", "Gobernanza e instituciones deportivas"),
     ("598", "Informalidad y crisis organizacional en el deporte")],
),
"Sistema jurídico, derechos humanos y Estado de derecho": (
    "Marcos normativos e institucionales de protección de derechos y acceso a la justicia, en el plano penal, constitucional e interamericano.",
    [("6", "Reforma del derecho penal y política criminal"),
     ("6", "Seguridad jurídica y acceso a la justicia"),
     ("732", "Sistemas internacionales de protección de derechos humanos"),
     ("732", "Acceso a la justicia interamericana"),
     ("441", "Laicidad y libertad religiosa en el Estado")],
),
"Cambio climático, recursos naturales y desarrollo sostenible": (
    "Efectos del cambio climático y gobernanza institucional sobre economías basadas en recursos naturales.",
    [("759", "Impacto del cambio climático en cadenas agroexportadoras"),
     ("759", "Crecimiento verde inclusivo y pequeños productores"),
     ("460", "Gobernanza institucional de la Amazonía"),
     ("460", "Economía extractiva y bienes comunes ambientales")],
),
"Desigualdad económica y estructura social en el Perú": (
    "Determinantes históricos, económicos y políticos de la desigualdad de ingresos de largo plazo en el país.",
    [("148", "Desigualdad económica y herencia colonial"),
     ("148", "Distribución del ingreso y política fiscal")],
),
"Tecnologías digitales, TIC y desarrollo": (
    "Uso de tecnologías digitales y móviles para el desarrollo socioeconómico y la protección de derechos.",
    [("101", "Innovación en telecomunicaciones móviles"),
     ("101", "TIC para el desarrollo socioeconómico rural"),
     ("927", "Ciudadanía digital y derechos de la niñez")],
),
}

def main():
    # sanity: every project referenced in EXTRACTED must exist in units
    missing = [pid for pid in EXTRACTED if pid not in units_by_id]
    assert not missing, f"unit ids missing from units file: {missing}"
    assert set(EXTRACTED) == set(units_by_id), (
        f"mismatch between extracted project ids and units file: "
        f"extra_in_units={set(units_by_id)-set(EXTRACTED)} extra_in_extracted={set(EXTRACTED)-set(units_by_id)}"
    )

    project_topics = []
    total_extracted = 0
    for pid, topics in EXTRACTED.items():
        u = units_by_id[pid]
        entry = {
            "project_id": pid,
            "title": u["title"],
            "executing_unit": u["executing_unit"],
            "knowledge_area": u["knowledge_area"],
            "year": u["year"],
            "topics": [
                {"topic": t, "description": d, "evidence": e, "confidence": c}
                for (t, d, e, c) in topics
            ],
        }
        project_topics.append(entry)
        total_extracted += len(topics)

    # index topic_text -> (project_id, confidence) for lookups while building normalized topics
    topic_lookup = {}
    for pid, topics in EXTRACTED.items():
        for (t, d, e, c) in topics:
            topic_lookup[(pid, t)] = (d, e, c)

    normalized_topics = []
    variant_to_norm_count = {}
    for name, (description, variants) in NORMALIZED.items():
        confidences = []
        project_ids = []
        executing_units = []
        evidences = []
        variant_texts = []
        for pid, topic_text in variants:
            d, e, c = topic_lookup[(pid, topic_text)]
            confidences.append(c)
            if pid not in project_ids:
                project_ids.append(pid)
            eu = units_by_id[pid]["executing_unit"]
            if eu not in executing_units:
                executing_units.append(eu)
            variant_texts.append(topic_text)
            evidences.append({
                "project_id": pid,
                "title": units_by_id[pid]["title"],
                "topic": topic_text,
            })
            variant_to_norm_count[topic_text] = variant_to_norm_count.get(topic_text, 0) + 1

        normalized_topics.append({
            "normalized_topic": name,
            "description": description,
            "variants": variant_texts,
            "project_ids": project_ids,
            "executing_units": executing_units,
            "count": len(variants),
            "avg_confidence": round(sum(confidences) / len(confidences), 2),
            "evidences": evidences,
        })

    # sanity: every extracted topic should map to exactly one normalized topic
    all_topic_texts = [t for topics in EXTRACTED.values() for (t, d, e, c) in topics]
    dupes = [t for t in set(all_topic_texts) if all_topic_texts.count(t) > 1]
    assert not dupes, f"duplicate topic text across projects (ambiguous): {dupes}"
    unmapped = [t for t in all_topic_texts if variant_to_norm_count.get(t, 0) == 0]
    assert not unmapped, f"extracted topics not mapped to any normalized topic: {unmapped}"
    multi_mapped = [t for t, n in variant_to_norm_count.items() if n > 1]
    assert not multi_mapped, f"topics mapped to more than one normalized topic: {multi_mapped}"

    data = {
        "metadata": {
            "dataset_title": "Proyectos de investigación PUCP cerrados (2010-2020) — muestra piloto",
            "source_file": "salidas/01_projects_closed_con_cris.csv",
            "num_projects": len(project_topics),
            "num_extracted_topics": total_extracted,
            "num_normalized_topics": len(normalized_topics),
            "note": (
                "Muestra piloto estratificada por unidad ejecutora (36 de 983 proyectos "
                "cerrados 2010+ con cris_abstract disponible). Extraccion y normalizacion "
                "de temas realizadas siguiendo la metodologia del explorador de referencia "
                "(topic -> descripcion -> evidencia -> confianza; agrupacion en temas "
                "normalizados con trazabilidad completa). Pendiente: escalar al universo "
                "completo (983 proyectos) mediante llamadas a un LLM por script, y aplicar "
                "el contraste con un objetivo (ODS / plan CEPLAN) una vez definido — ver "
                "docs/topic_normalization_pipeline.md."
            ),
        },
        "projects": units,
        "project_topics": project_topics,
        "normalized_topics": normalized_topics,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"OK: {len(project_topics)} projects, {total_extracted} extracted topics, "
          f"{len(normalized_topics)} normalized topics -> {OUT_PATH}")

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Batch 1 of publication topic extraction (70 of the 562 usable declared
results, see publication_extraction_prep.py). Separate pool from the
projects pipeline (462/49 normalized topics) per team decision: publication
topics are normalized independently for now and will be reconciled with the
projects taxonomy as a later step.

First batch: nothing exists yet to REUSE, so every topic lands in
NEW_NORMALIZED_PUBBATCH01. Closely related papers (same experiment
collaboration, same device, same sub-field) are grouped under one normalized
topic with multiple variants, same convention as the projects pipeline.
"""

EXTRACTED_PUBBATCH01 = {
    "862_1": [(
        "Política migratoria y de asilo hacia la migración venezolana en el Perú",
        "Análisis de cómo la política migratoria y de asilo peruana hacia la población venezolana se inscribe en una lógica de control migratorio.",
        "el objetivo de este artículo es describir cómo la política migratoria peruana hacia la población venezolana se inscribe en una lógica de control migratorio.",
        0.92,
    )],
    "590_20": [(
        "Efectos nucleares en interacciones neutrino-carbono (MINERvA)",
        "Aislamiento de efectos nucleares en datos de dispersión neutrino-carbono de baja transferencia de momento del experimento MINERvA.",
        "Two different nuclear-medium effects are isolated using a low three-momentum transfer subsample of neutrino-carbon scattering data from the MINERvA neutrino experiment.",
        0.9,
    )],
    "826_8": [(
        "Foliaciones Levi-flat singulares en variedades complejas",
        "Clasificación de gérmenes de foliaciones Levi-flat singulares en variedades complejas bajo la hipótesis de que la foliación tangente es holomorfa.",
        "In this article, we classify germs of Levi-flat foliations at $(\\mathbb{C}^{n},0)$ under the hypothesis that $\\mathcal{L}$ is a germ holomorphic foliation.",
        0.92,
    )],
    "876_2": [(
        "Instrumentación óptica de bajo costo para medición de haces láser",
        "Diseño y prueba de un montaje automatizado simple para medir el perfil y tamaño de punto de un haz láser gaussiano con sensores de luz económicos.",
        "We have designed and tested an automated simple setup for measuring the profile and spot size of a Gaussian laser beam, which exhibits a similar performance to ready-made optical devices, using three light sensors.",
        0.88,
    )],
    "915_2": [(
        "Derechos de la naturaleza y crítica al antropocentrismo jurídico",
        "Problematización hermenéutica de la relación entre la naturaleza y la posibilidad de su acceso a derechos, frente al antropocentrismo del derecho moderno.",
        "el presente artículo se propone problematizar desde la perspectiva de algunas voces de la hermenéutica contemporánea la relación entre la naturaleza y la posibilidad de su acceso a derechos.",
        0.88,
    )],
    "897_1": [(
        "Lingüística computacional para la revitalización de lenguas indígenas",
        "Hoja de ruta para el desarrollo de lingüística computacional de idiomas infrasoportados (quechua, aimara y otros) hablados por millones de personas.",
        "En este documento se describe una hoja de ruta para el desarrollo de la lingüística computacional de idiomas infrasoportados que todavía son hablados por millones de hablantes.",
        0.9,
    )],
    "487_1": [(
        "Enfoque de martingalas para la metaestabilidad de cadenas de Markov",
        "Extensión de un enfoque de martingalas para derivar el comportamiento metaestable de cadenas de Markov de tiempo continuo, reemplazando condiciones sobre tiempos de visita por condiciones sobre tiempos de mezcla y relajación.",
        "We replace this condition here by assumptions on the mixing times and on the relaxation times of the chains reflected at the boundary of the metastable sets.",
        0.88,
    )],
    "685_1": [(
        "Producción alfarera colonial temprana en los Andes centrales",
        "Propuesta metodológica, basada en modelos analíticos explícitos, para comprender cómo el régimen colonial temprano afectó el oficio alfarero en los Andes.",
        "Cmo el rgimen colonial temprano afect el oficio de alfarero en los Andes? Cmo la evidencia documental y material sobre alfarera nos permite comprender mejor ese periodo?",
        0.7,
    )],
    "590_19": [(
        "Calibración del detector MINERvA con datos de haz de prueba",
        "Medición de la respuesta calorimétrica del detector MINERvA a protones, piones y electrones usando una réplica a escala reducida en un haz de prueba.",
        "This paper reports measurements with samples of protons, pions, and electrons from 0.35 to 2.0 GeV/c momentum.",
        0.9,
    )],
    "562_1": [(
        "Manipulativos virtuales para la argumentación matemática sobre números enteros",
        "Estudio de caso sobre cómo un entorno de manipulativos virtuales en tableta apoya la argumentación de estudiantes de primaria sobre suma y resta de enteros negativos.",
        "We examine the properties of integers they conjectured, and the kinds of evidence and arguments they used to support their conjectures.",
        0.88,
    )],
    "769_1": [(
        "Articulación teórica entre competencia algebraica y modelización",
        "Ensayo teórico que articula tres enfoques sobre álgebra escolar: el desarrollo de la competencia algebraica, el proceso de algebrización y la modelización.",
        "Verificamos a possibilidade dessa articulação e ainda que ela nos permite analisar com mais clareza o ensino da álgebra escolar e verificar os pontos de escassez ou de excesso de tarefas que conduzam ao desenvolvimento da competência algébrica no aluno.",
        0.82,
    )],
    "838_2": [(
        "Efectos psicológicos de la música y danza en la construcción de cultura de paz",
        "Estudio experimental del efecto de estímulos musicales y de danza andina sobre la empatía intergrupal, dominancia social y estereotipos hacia el grupo andino.",
        "this research seeks to analyze the effect of music and dance stimuli related to the Andean social group on intergroup empathy, social dominance, stereotypes, emotions, and attitudes toward Andean music.",
        0.9,
    )],
    "836_7": [(
        "Tipificación estructural de edificaciones patrimoniales mediante HBIM",
        "Metodología de tipificación estructural de edificaciones patrimoniales usando modelado digital (HBIM) y realidad aumentada, aplicada a 22 iglesias andinas del sur del Perú.",
        "This article provides a methodology of structural typification using modern technologies for digitalization and visualization of information based on the study of a representative sample of 22 churches located in the South Andean zone of Peru and considered as part of Peru's Cultural Heritage.",
        0.9,
    )],
    "870_3": [(
        "Escritura epistolar y agencia política de Manuela Sáenz",
        "Análisis de las cartas y diarios de Manuela Sáenz Aizpuru como fuente para que ella misma explique su propia política durante las independencias americanas.",
        "Este artículo se centra en sus escritos para que sea ella quien explique su propia política y los sentidos que puso al período de las independencias en el Ecuador, en Colombia y en el Perú.",
        0.85,
    )],
    "703_29": [(
        "Integración comercial del Perú en la cooperación Asia-Pacífico",
        "Análisis del rol del Perú y la Alianza del Pacífico en la integración comercial con la región Asia-Pacífico.",
        "el escrito aborde por un lado, el estudio de Asia-Pacífico como región, los acuerdos que están negociando los países que la configuran y el relacionamiento de estos con los países latinoamericanos.",
        0.8,
    )],
    "838_1": [(
        "Adherencia a intervenciones de salud mental digital en jóvenes",
        "Revisión de la literatura sobre adherencia a programas de salud mental digital (e-mental health) en jóvenes y recomendaciones de diseño de intervención.",
        "This paper presents a broad review of the adherence literature, focusing on factors associated with improving adherence to e-mental health among youth.",
        0.88,
    )],
    "658_1": [(
        "Convergencia de caminatas aleatorias coalescentes al coalescente de Kingman",
        "Demostración de que una secuencia de cadenas de Markov de caminatas aleatorias coalescentes en un toro discreto converge al coalescente de Kingman.",
        "We prove that the sequence of Markov chains (Z(t theta N)(N))(t >= 0) converges to the total number of partitions in Kingman's coalescent.",
        0.9,
    )],
    "769_2": [(
        "Validación de escala de involucramiento parental en padres peruanos",
        "Evidencias de validez y confiabilidad de la Escala de Involucramiento Parental (actividades de cuidado y socialización) en una muestra de 420 padres y 420 madres peruanos.",
        "El presente estudio busca obtener evidencias de validez y confiabilidad de la Escala de Involucramiento Parental: Actividades de cuidado y socialización en una muestra de padres peruanos de niños y niñas preescolares.",
        0.9,
    )],
    "789_13": [(
        "Restricciones a sleptones en escenarios supersimétricos de seesaw de baja escala",
        "Evaluación sistemática de las cotas del LHC sobre masas de sleptones en un escenario de supersimetría natural con seesaw de baja escala y neutralinos higgsino-like.",
        "We consider a scenario inspired by natural supersymmetry, where neutrino data is explained within a low-scale seesaw scenario.",
        0.88,
    )],
    "738_4": [(
        "Simulación numérica del comportamiento fluido-dinámico de un agitador a escala reducida",
        "Estudio mediante CFD del comportamiento de un agitador con impulsor hidroala para mezclar agua con partículas polimetálicas en la industria minera.",
        "Se presenta el estudio del comportamiento de un agitador con impulsor hidroala (hydrofoil), usado para mezclar agua con partículas polimetálicas en la industria minera, mediante simulación numérica con software de dinámica de fluidos computacional (CFD).",
        0.85,
    )],
    "572_1": [(
        "Revisión narrativa de estudios de apego en América Latina",
        "Revisión sistemática narrativa de 82 publicaciones latinoamericanas sobre teoría del apego y sensitividad materna, evaluando la aplicabilidad de sus hipótesis centrales fuera de países occidentales.",
        "a search was conducted in four electronic databases (Web of Science, PsycInfo, SciELO, and Redalyc) and 82 publications on attachment and/or sensitivity met inclusion criteria.",
        0.9,
    )],
    "731_3": [(
        "Polarización política y representatividad democrática del voto",
        "Análisis del rol mediador de los contextos políticos y la consolidación democrática sobre el efecto de la polarización del sistema de partidos en el voto ideológico.",
        "This contribution evaluates the mediating role of different political contexts and levels of democratic consolidation on the effect of party system polarization on ideological vote and discusses how this relationship enhances democratic representativeness.",
        0.88,
    )],
    "672_6": [(
        "Optimización ambiental de dietas alimentarias peruanas mediante programación lineal",
        "Modelo de programación lineal que combina evaluación de ciclo de vida con datos nutricionales y económicos para optimizar 25 patrones dietéticos peruanos y reducir emisiones de GEI.",
        "a linear programming model was built in which the environmental, nutritional and economic information on a set of 25 dietary patterns in Peru were optimized in order to achieve the environmentally best-performing diet that complies with economic and nutritional standards.",
        0.92,
    )],
    "520_12": [(
        "Síndrome de agotamiento profesional en trabajadores penitenciarios peruanos",
        "Investigación cualitativa nacional sobre los factores institucionales y sociales asociados al síndrome de agotamiento profesional en trabajadores penitenciarios del Perú.",
        "El artículo presenta los resultados de una investigación cualitativa a nivel nacional acerca de los factores institucionales y sociales asociados al Síndrome de Agotamiento Profesional (SAP) y al estrés laboral en trabajadores penitenciarios peruanos.",
        0.92,
    )],
    "901_3": [(
        "Evolución de la terminología de partes del cuerpo en lenguas Pano",
        "Demostración estadística de que las raíces de partes del cuerpo en lenguas Pano son conservadoras mientras que los formativos derivativos muestran innovaciones recientes y paralelas.",
        "We use various statistical methods to demonstrate that whereas body-part roots are generally conservative, body-part formatives exhibit diverse chronologies and are often the result of recent and parallel innovations.",
        0.9,
    )],
    "743_5": [(
        "Goniómetro electrónico portátil impreso en 3D para medición articular",
        "Desarrollo de un goniómetro de rodilla portátil impreso en 3D con sensor de efecto Hall y aplicación móvil para medir el ángulo de flexión en tiempo real.",
        "This paper proposes the development of a 3D printed knee wearable goniometer that uses a Hall-effect sensor to measure the knee flexion angle, which works with a mobile app that shows the angle in real-time as well as the activity the user is performing.",
        0.92,
    )],
    "901_14": [(
        "Base de datos Grambank sobre diversidad gramatical y pérdida lingüística",
        "Presentación de Grambank, la mayor base de datos comparativa de gramática disponible (2400 lenguas), usada para cuantificar el efecto de la herencia genealógica y la proximidad geográfica sobre la diversidad lingüística.",
        "Here, we outline the Grambank database. With over 400,000 data points and 2400 languages, Grambank is the largest comparative grammatical database available.",
        0.88,
    )],
    "788_7": [(
        "Teología de la liberación de Gustavo Gutiérrez y ética teológica contemporánea",
        "Análisis de la articulación entre la salvación cristiana y la liberación de la opresión, y del aporte de Gustavo Gutiérrez a la comprensión teológica del sufrimiento humano.",
        "este ensayo analiza dos temas centrales en el pensamiento de este profeta latinoamericano que contribuyeron a la renovación de la teología moral contemporánea tras el concilio Vaticano II.",
        0.9,
    )],
    "502_21": [(
        "Juegos tradicionales shipibo-konibo como herramienta pedagógica intercultural",
        "Recopilación de juegos tradicionales del pueblo shipibo-konibo y propuesta de su aprovechamiento como herramienta educativa para sociedades interculturales.",
        "presentamos una recopilación de juegos del pueblo shipibo-konibo, pueblo indígena de la Amazonía del Perú, y algunas ideas para su aprovechamiento como herramienta educativa.",
        0.88,
    )],
    "709_9": [(
        "Representación de la mujer andina en el cine peruano del conflicto armado interno",
        "Análisis de la representación desigual de personajes femeninos andinos en el cine peruano ambientado en el conflicto armado interno (1980-1999), en la película La boca del lobo.",
        "This paper focuses on the representation of Andean female characters (indigenous) in Peruvian films set in the Internal Armed Conflict (IAC 1980-1999) and their relationship with male characters from the coast and from the Peruvian Andes.",
        0.9,
    )],
    "659_1": [(
        "Grandes desviaciones estáticas en modelos de reacción-difusión",
        "Principio de grandes desviaciones para la medida empírica bajo el estado estacionario de un modelo de reacción-difusión con dinámica de exclusión simple y spin-flip.",
        "We prove the large deviations principle for the empirical measure under the stationary state.",
        0.88,
    )],
    "806_1": [(
        "Compromiso agentivo estudiantil y enseñanza de apoyo a la autonomía",
        "Estudio longitudinal que muestra que el compromiso agentivo temprano de estudiantes universitarios predice incrementos posteriores en la enseñanza docente percibida de apoyo a la autonomía.",
        "students' early-semester agentic engagement predicted longitudinal increases in perceived autonomy-supportive teaching, which suggests that students' classroom engagement may recruit greater perceived autonomy support.",
        0.9,
    )],
    "762_7": [(
        "Envejecimiento y degradación mecánica de espinas de erizo de mar",
        "Evaluación del efecto del envejecimiento y la irradiación UV sobre las propiedades mecánicas y los modos de falla de espinas de erizo de mar, como modelo de compuesto natural duro.",
        "Uniaxial compression tests carried out on aged and UV irradiated samples showed that both treatments affected the mechanical properties of the spines.",
        0.9,
    )],
    "706_2": [(
        "Beneficios causales del compromiso agentivo estudiantil manipulado experimentalmente",
        "Dos experimentos con pares profesor-estudiante que prueban la capacidad causal del compromiso agentivo manipulado para generar un entorno de aprendizaje más favorable y mayor satisfacción motivacional.",
        "two experiments tested the causal capacity of manipulated agentic engagement to create three categories of benefits: a supportive learning environment; motivational satisfactions; and effective functioning.",
        0.9,
    )],
    "718_1": [(
        "Convección inducida por gradientes térmicos en frentes de reacción química",
        "Modelo de frente delgado para la propagación de frentes de reacción química en líquidos dentro de una celda Hele-Shaw, incorporando gradientes de densidad térmicos y composicionales.",
        "We present a thin front model for the propagation of chemical reaction fronts in liquids inside a Hele-Shaw cell or porous media.",
        0.88,
    )],
    "657_1": [(
        "Control óptimo lineal-cuadrático de sistemas singulares con saltos markovianos",
        "Solución del problema de control óptimo lineal-cuadrático para sistemas lineales singulares de tiempo discreto con saltos markovianos, mediante transformaciones de base.",
        "we address the linear quadratic optimal control problem for discrete-time Markov jump linear singular systems.",
        0.9,
    )],
    "855_1": [(
        "Prácticas de ética empresarial en grandes empresas peruanas",
        "Caracterización de las prácticas de ética y gestión empresarial reportadas por empresas del top 10000 en el Perú.",
        "Palabras clave: Ethical Practices, Ethical Management, Business Ethics",
        0.55,
    )],
    "690_1": [(
        "Modelo de regresión beta-inflada con efectos mixtos para variables fraccionarias",
        "Nuevo modelo de regresión de efectos mixtos para variables de respuesta fraccionarias acotadas, estimado bayesianamente y aplicado a datos de utilización de líneas de crédito en el Perú.",
        "we propose a new mixed-effects regression model for fractional bounded response variables.",
        0.9,
    )],
    "578_6": [(
        "Modelamiento de la corrosión de materiales ferrosos mediante diseño D-óptimo",
        "Modelamiento de la tasa de corrosión de acero al carbono y acero inoxidable inmersos en sulfato y cloruro férrico, usando diseño experimental D-óptimo y metodología de superficie de respuesta.",
        "the purpose of this paper is to model the corrosion rate behavior for two ferrous materials, carbon steel AISI 1020 and stainless steel AISI 304, immersed in ferric sulfate and ferric chloride solutions using D-optimal design with response surface methodology.",
        0.9,
    )],
    "904_1": [(
        "Efectos espectrales en el rendimiento de tecnologías fotovoltaicas en Lima",
        "Primer estudio del impacto espectral sobre el desempeño de distintas tecnologías fotovoltaicas en Lima, monitoreando la distribución espectral durante un año.",
        "This study presents for the first time the spectral impact on the performance of different photovoltaic (PV) technologies in Lima, Peru.",
        0.92,
    )],
    "850_1": [(
        "Caracterización de cámaras de radón con detectores CR-39",
        "Estudio de la permeabilidad y el factor de transmisión de radón usando detectores CR-39 dentro de cámaras de difusión no comerciales, en una cámara de radón de nueva construcción.",
        "Many CR-39 (poly allyl glycol carbonate) detectors inside two different non-commercial diffusion chambers were used to study the radon permeability and the radon transmission factor.",
        0.9,
    )],
    "901_2": [(
        "Conjunto de datos Grammars Across Time Analyzed (GATA) para lingüística histórica",
        "Presentación del recurso GATA, con información gramatical de 52 lenguas en dos momentos temporales distintos, para el estudio del cambio lingüístico y cultural.",
        "GATA comprises grammatical information on 52 diverse languages across all continents, featuring morphological, syntactic, and phonological information based on published grammars of the same language at two different time points.",
        0.85,
    )],
    "722_4": [(
        "Reconstrucción paleogenómica de la historia poblacional andina",
        "Datos genómicos de 89 individuos de entre 9,000 y 500 años de antigüedad que reconstruyen la historia poblacional profunda de los Andes centrales y surcentrales, incluyendo Moche, Wari, Tiwanaku e Inca.",
        "We assembled genome-wide data on 89 individuals dating from ~9,000-500 years ago (BP), with a particular focus on the period of the rise and fall of state societies.",
        0.92,
    )],
    "876_9": [(
        "Pruebas de decoherencia cuántica en el experimento DUNE",
        "Expresión invariante general para una matriz de decoherencia bajo rotación de base cuántica, y evaluación de su impacto en la sensibilidad a parámetros de oscilación de neutrinos en DUNE.",
        "we provide a general expression for an invariant decoherence matrix under a quantum basis rotation.",
        0.9,
    )],
    "634_1": [(
        "Detección de cianuro en agua mediante nanopartículas de oro y dispersión Rayleigh de resonancia",
        "Sensor ratiométrico altamente sensible para cuantificar cianuro en muestras acuosas usando nanopartículas de oro estabilizadas, con límites de detección por debajo del máximo aceptable de la OMS.",
        "A highly sensitive and selective ratiometric sensor for the quantification of cyanide (CN-) in aqueous samples has been developed using spherical gold nanoparticles (AuNPs) stabilized by polysorbate 40 (PS-40).",
        0.92,
    )],
    "901_15": [(
        "Evidencia lexico-gramatical a favor de la hipótesis Pano-Takana",
        "Comparación de reconstrucciones proto-Pano y proto-Takana que muestra cognados en vocabulario básico y partes del cuerpo, en apoyo de la hipótesis de parentesco genético entre ambas familias.",
        "The present paper offers lexical and grammatical evidence in support of the hypothesis that Pano and Takana are genetically connected.",
        0.9,
    )],
    "690_8": [(
        "Modelo bayesiano de respuesta al ítem para medir fluidez verbal con speededness",
        "Modelo bayesiano simple para estimar parámetros personales y de ítem a partir de datos de fluidez de palabras sin sentido en estudiantes peruanos, en presencia de speededness.",
        "This work proposes a simple Bayesian model to estimate both, personal and item parameters, from a test data with evidence of Speededness.",
        0.88,
    )],
    "510_1": [(
        "Detección de trigonelina como marcador de calidad de café mediante espectrometría Raman portátil",
        "Título declarado sobre detección selectiva de trigonelina (marcador de calidad del café) con un espectrómetro Raman portátil; el resumen disponible no corresponde al tema del título (revisión genérica de RMN en alimentos).",
        "FAST AND SELECTIVE DETECTION OF TRIGONELLINE, A COFFEE QUALITY MARKER, USING A PORTABLE RAMAN SPECTROMETER",
        0.5,
    )],
    "529_8": [(
        "Sistema RIMAC: plataforma abierta de información vial con fuentes en tiempo real",
        "Propuesta de un sistema de información abierto sobre una plataforma geográfica open source, que incorpora sensores fijos y móviles, cámaras y datos de teléfonos para reportar tráfico en Lima.",
        "this project proposes the development of information systems built with open source software over an open source geographical platform that allows the introduction of new and reliable sources of information like data from fixed and mobile sensor, camcorders, traffic lights or mobile phones.",
        0.88,
    )],
    "743_4": [(
        "Diseño e implementación de un sistema electrogoniométrico para tobillo y rodilla",
        "Diseño del sistema electrogoniométrico WHITE, basado en entrevistas a profesionales de salud, para la evaluación del movimiento de tobillo y rodilla en centros de salud.",
        "the design and implementation of a novel electrogoniometer system called WHITE is presented. First, the specifications of the system were gathered based on interviewing health professionals in public and private health centers.",
        0.9,
    )],
    "529_9": [(
        "Red de cámaras de bajo costo para alimentar el sistema RIMAC de información vial",
        "Segunda etapa del proyecto RIMAC: interconexión del núcleo del sistema con una red de cámaras de bajo costo que calcula velocidades de tráfico localmente para evitar congestión de datos.",
        "this paper describes the development of the second part of the project: the interconnection of the core with a source of information: a camera network.",
        0.88,
    )],
    "590_14": [(
        "Modelo neutrino 3+2 mínimo y decaimientos del Higgs",
        "Estudio del modelo neutrino 3+2 mínimo de tipo seesaw con singletes a escala del GeV, que podría producir decaimientos del Higgs en neutrinos pesados observables como vértices desplazados en el LHC.",
        "In this work, we study the minimal 3+2 neutrino model in scenarios where the singlets have masses at the GeV scale.",
        0.88,
    )],
    "557_11": [(
        "Modelado incremental del fondo de video robusto a vibración de cámara (PCP)",
        "Algoritmo incremental de Principal Component Pursuit para modelado de fondo de video que es robusto a la vibración traslacional y rotacional de la cámara, procesando un cuadro a la vez.",
        "we propose a novel fully incremental PCP algorithm for video background modeling that is robust to translational and rotational jitter.",
        0.9,
    )],
    "808_5": [(
        "Modelo de diseño de videojuegos educativos sobre historia",
        "Aplicación y validación de un modelo de diseño de videojuegos educativos al desarrollo de un videojuego sobre la independencia del Perú, evaluado con estudiantes universitarios.",
        "a model, previously used in the educational context, was applied to design and develop an educational video game about the independence of Peru.",
        0.88,
    )],
    "539_6": [(
        "Fotografía aérea con UAV de ala fija para reconstrucción 3D en zonas altoandinas",
        "Sistema UAV de ala fija capaz de 30 minutos de vuelo en alta altitud (5000-6200 m.s.n.m.) para fotografía aérea orientada a la reconstrucción 3D georreferenciada de paisajes altoandinos.",
        "an UAV system capable of carrying an image acquisition system and capable of 30 minutes of flight time in high-altitude (between 5000 and 6200 m.a.s.l.), windy environments is proposed.",
        0.9,
    )],
    "839_6": [(
        "Codificación dispersa convolucional sin parámetro de regularización vía proyección en bola L1",
        "Método libre de parámetro de regularización para resolver el problema de codificación dispersa convolucional, mediante proyección sobre la bola L1 guiada por el principio de discrepancia de Morozov.",
        "we propose a regularization parameter-free method to solve the CSC problem via its projection onto the ℓ1-Ball formulation coupled with a warm-start like strategy.",
        0.88,
    )],
    "901_13": [(
        "Capítulo sobre la familia lingüística Pano en el Handbook of Amazonian Languages",
        "Capítulo de manual de referencia sobre la familia lingüística Pano; el resumen disponible no corresponde al tema del título (describe en cambio el contacto quechua-aimara en los Andes centrales).",
        "THE PANO LANGUAGE FAMILY. IN PATIENCE EPPS AND LEV MICHAEL (EDS.), HANDBOOK OF AMAZONIAN LANGUAGES. BERLIN: MOUTON DE GRUYTER.",
        0.45,
    )],
    "623_4": [(
        "Movilización feminista intergeneracional en las marchas Ni Una Menos",
        "Estudio de cómo activistas jóvenes se incorporan al movimiento Ni Una Menos gracias a la mediación productiva y el aprendizaje feminista entre generaciones de activistas.",
        "We show that these \"daughters\" have been welcomed by previous generations of feminist changemakers.",
        0.88,
    )],
    "797_4": [(
        "El \"Sur Distorsionado\" como marco de la música metal peruana",
        "Propuesta del concepto del Sur Distorsionado como espacio geográfico y simbólico desde el cual personas oprimidas usan la música metal para reflexionar críticamente sobre su experiencia.",
        "propongo la idea del Sur Distorsionado como un espacio, tanto geográfico como simbólico, donde las personas oprimidas del mundo e impactadas por el proyecto moderno/colonial, utilizan la música metal para reflexionar críticamente sobre sus experiencias.",
        0.85,
    )],
    "507_10": [(
        "Contaminación por metales pesados en sedimentos viales de corredores urbanos (Bogotá-Soacha)",
        "Evaluación de la contaminación por metales pesados (Pb, Zn, entre otros) en sedimentos viales de dos zonas del corredor Bogotá-Soacha, atribuida principalmente a fuentes móviles.",
        "Este artículo presenta los resultados de la evaluación de la contaminación por metales pesados asociados con el sedimento vial de dos zonas (i.e., Zonas 1 y 2) del corredor Bogotá - Soacha en Colombia.",
        0.85,
    )],
    "734_6": [(
        "Estatuto jurídico del consejo de usuarios en los servicios públicos de energía en el Perú",
        "Título declarado sobre el estatuto jurídico del consejo de usuarios de servicios de energía en el Perú; el texto disponible no corresponde al tema del título (describe proyectos legislativos argentinos).",
        "EL ESTATUTO JURIDICO DEL CONSEJO DE USUARIOS EN LOS SERVICIOS PUBLICOS DE ENERGIA EN PERU",
        0.4,
    )],
    "901_11": [(
        "Prefijación, incorporación y composición de partes del cuerpo en Pano y Takana",
        "Evidencia de que, aunque solo las lenguas Pano muestran prefijación de partes del cuerpo, las lenguas Takana muestran incorporación y composición nominal equivalentes, a favor de la hipótesis Pano-Takana.",
        "Although it is true that only Pano languages exhibit body-part prefixation, Takana languages feature body-part noun incorporation and compounding.",
        0.88,
    )],
    "854_3": [(
        "Articulación de los dominios de geometría y análisis mediante modelización y tecnología digital",
        "Tarea de modelización sobre función cuadrática, parte de una secuencia didáctica internacional orientada a articular los dominios de geometría y análisis mediante tecnología digital.",
        "se presenta una tarea de modelizacion sobre funcion cuadratica que forma parte de la secuencia didactica de un proyecto de investigacion internacional en ejecucion, cuya finalidad es promover la articulacion de los dominios de la Geometria y el analisis por medio de la modelizacion y la tecnologia digital.",
        0.8,
    )],
    "908_9": [(
        "Robot humanoide asistivo social para intervenciones de salud mental a distancia",
        "Diseño de un robot humanoide asistivo social con brazos articulados y expresión gestual, evaluado para ofrecer intervenciones telepsicológicas a pacientes aislados en hospitales.",
        "we present the design of a social assistive humanoid robot with articulated robotic arms intended to deliver telepsychological interventions.",
        0.9,
    )],
    "801_7": [(
        "Transferencia tecnológica y territorialidad de la vivienda altoandina",
        "Lectura arquitectónica de territorios rurales alpaqueros sobre 4000 m.s.n.m., analizando la vivienda rural y sus relaciones con los espacios productivos de las comunidades altoandinas.",
        "La interpretación se realiza desde la disciplina de la arquitectura a partir del análisis de la vivienda rural y sus relaciones con los espacios de comunidades alto andinas originarias donde se desarrolla la actividad productiva de crianza de camélidos sudamericanos.",
        0.85,
    )],
    "562_2": [(
        "Enseñanza basada en pruebas en estudiantes de tercer grado construyendo conocimiento mediante demostraciones",
        "Caso de enseñanza basada en pruebas con estudiantes de tercer grado construyendo conocimiento matemático mediante demostraciones; solo se dispone del título, sin resumen.",
        "AN EXAMPLE OF PROOF-BASED TEACHING : 3RD GRADERS CONSTRUCTING KNOWLEDGE BY PROVING",
        0.5,
    )],
    "842_1": [(
        "Historia fiscal del Perú e impacto asimétrico de la política fiscal (1980-2020)",
        "Análisis del impacto asimétrico del gasto público y la recaudación tributaria sobre el PBI peruano entre 2000 y 2022, usando un modelo de regresión de umbral (Threshold Autoregressive).",
        "Esta investigación presenta como eje principal analizar el impacto asimétrico de los instrumentos de política fiscal (gasto del gobierno y recaudación tributaria) en la evolución del Producto Bruto Interno durante periodo 2000-2022.",
        0.88,
    )],
    "811_6": [(
        "Derechos indígenas, extractivismo y respuesta estatal a la pandemia en la Amazonía",
        "Discusión sobre el centralismo institucional y la autodeterminación de los pueblos indígenas amazónicos frente a la pandemia, y su demanda de protección de derechos, territorio y salud culturalmente apropiada frente al extractivismo.",
        "the Amazonian peoples demand in times of pandemic guarantee to their specific rights, respect for their traditional ways of life, culturally appropriate health care, defense of the territory against extractivism and dispossession.",
        0.8,
    )],
    "586_2": [(
        "Libre mercado y educación superior: universidades de bajo costo en el Perú",
        "Título declarado sobre el caso de universidades privadas de bajo costo en el Perú bajo una lógica de libre mercado; solo se dispone de palabras clave genéricas no relacionadas, sin resumen real.",
        "FREE MARKET AND HIGHER EDUCATION: THE CASE OF LOW-FEE UNIVERSITIES IN PERU",
        0.45,
    )],
    "536_4": [(
        "Documentación gramatical del idioma kakataibo (familia Pano)",
        "Gramática de referencia del kakataibo, lengua de la familia Pano hablada en el Perú, como documentación y descripción lingüística.",
        "Palabras clave: kakataibo, panoan, amazonia, language description, language documentation",
        0.75,
    )],
}

REUSE_PUBBATCH01 = []

NEW_NORMALIZED_PUBBATCH01 = {
    "Física experimental y teórica de neutrinos y partículas (MINERvA/DUNE)": (
        "Estudios teóricos y experimentales sobre física de neutrinos y partículas elementales en los experimentos MINERvA y DUNE, incluyendo efectos nucleares, calibración de detectores, decoherencia cuántica y escenarios de supersimetría.",
        [
            ("590_20", "Efectos nucleares en interacciones neutrino-carbono (MINERvA)"),
            ("590_19", "Calibración del detector MINERvA con datos de haz de prueba"),
            ("789_13", "Restricciones a sleptones en escenarios supersimétricos de seesaw de baja escala"),
            ("876_9", "Pruebas de decoherencia cuántica en el experimento DUNE"),
            ("590_14", "Modelo neutrino 3+2 mínimo y decaimientos del Higgs"),
        ],
    ),
    "Sistema RIMAC de información vial urbana en tiempo real": (
        "Desarrollo de un sistema abierto de información de tráfico urbano en Lima alimentado por fuentes de datos en tiempo real, incluyendo una red de cámaras de bajo costo.",
        [
            ("529_8", "Sistema RIMAC: plataforma abierta de información vial con fuentes en tiempo real"),
            ("529_9", "Red de cámaras de bajo costo para alimentar el sistema RIMAC de información vial"),
        ],
    ),
    "Clasificación genética y rasgos gramaticales de las lenguas Pano-Takana": (
        "Evidencia léxica y gramatical (terminología de partes del cuerpo, prefijación, incorporación) a favor de la hipótesis de parentesco genético entre las familias lingüísticas Pano y Takana de la Amazonía occidental.",
        [
            ("901_3", "Evolución de la terminología de partes del cuerpo en lenguas Pano"),
            ("901_15", "Evidencia lexico-gramatical a favor de la hipótesis Pano-Takana"),
            ("901_13", "Capítulo sobre la familia lingüística Pano en el Handbook of Amazonian Languages"),
            ("901_11", "Prefijación, incorporación y composición de partes del cuerpo en Pano y Takana"),
        ],
    ),
    "Compromiso agentivo estudiantil y enseñanza de apoyo a la autonomía": (
        "Estudios longitudinales y experimentales sobre cómo el compromiso agentivo de los estudiantes predice y se ve predicho por la enseñanza docente de apoyo a la autonomía.",
        [
            ("806_1", "Compromiso agentivo estudiantil y enseñanza de apoyo a la autonomía"),
            ("706_2", "Beneficios causales del compromiso agentivo estudiantil manipulado experimentalmente"),
        ],
    ),
    "Desarrollo de electrogoniómetros portátiles para evaluación articular": (
        "Diseño e implementación de sistemas electrogoniométricos portátiles (impresión 3D, sensores Hall) para la medición no invasiva de grados articulares de tobillo y rodilla.",
        [
            ("743_5", "Goniómetro electrónico portátil impreso en 3D para medición articular"),
            ("743_4", "Diseño e implementación de un sistema electrogoniométrico para tobillo y rodilla"),
        ],
    ),
    "Enseñanza basada en pruebas y manipulativos virtuales en matemática escolar": (
        "Estudios de caso sobre el uso de manipulativos virtuales y la enseñanza basada en pruebas para el desarrollo del razonamiento matemático (enteros, construcción de conocimiento) en estudiantes de educación básica.",
        [
            ("562_1", "Manipulativos virtuales para la argumentación matemática sobre números enteros"),
            ("562_2", "Enseñanza basada en pruebas en estudiantes de tercer grado construyendo conocimiento mediante demostraciones"),
        ],
    ),
    "Política migratoria y de asilo hacia la migración venezolana en el Perú": (
        "Análisis de cómo la política migratoria y de asilo peruana hacia la población venezolana se inscribe en una lógica de control migratorio.",
        [("862_1", "Política migratoria y de asilo hacia la migración venezolana en el Perú")],
    ),
    "Foliaciones Levi-flat singulares en variedades complejas": (
        "Clasificación de gérmenes de foliaciones Levi-flat singulares en variedades complejas bajo la hipótesis de que la foliación tangente es holomorfa.",
        [("826_8", "Foliaciones Levi-flat singulares en variedades complejas")],
    ),
    "Instrumentación óptica de bajo costo para medición de haces láser": (
        "Diseño y prueba de un montaje automatizado simple para medir el perfil y tamaño de punto de un haz láser gaussiano con sensores de luz económicos.",
        [("876_2", "Instrumentación óptica de bajo costo para medición de haces láser")],
    ),
    "Derechos de la naturaleza y crítica al antropocentrismo jurídico": (
        "Problematización hermenéutica de la relación entre la naturaleza y la posibilidad de su acceso a derechos, frente al antropocentrismo del derecho moderno.",
        [("915_2", "Derechos de la naturaleza y crítica al antropocentrismo jurídico")],
    ),
    "Lingüística computacional para la revitalización de lenguas indígenas": (
        "Hoja de ruta para el desarrollo de lingüística computacional de idiomas infrasoportados (quechua, aimara y otros) hablados por millones de personas.",
        [("897_1", "Lingüística computacional para la revitalización de lenguas indígenas")],
    ),
    "Enfoque de martingalas para la metaestabilidad de cadenas de Markov": (
        "Extensión de un enfoque de martingalas para derivar el comportamiento metaestable de cadenas de Markov de tiempo continuo, reemplazando condiciones sobre tiempos de visita por condiciones sobre tiempos de mezcla y relajación.",
        [("487_1", "Enfoque de martingalas para la metaestabilidad de cadenas de Markov")],
    ),
    "Producción alfarera colonial temprana en los Andes centrales": (
        "Propuesta metodológica, basada en modelos analíticos explícitos, para comprender cómo el régimen colonial temprano afectó el oficio alfarero en los Andes.",
        [("685_1", "Producción alfarera colonial temprana en los Andes centrales")],
    ),
    "Articulación teórica entre competencia algebraica y modelización": (
        "Ensayo teórico que articula tres enfoques sobre álgebra escolar: el desarrollo de la competencia algebraica, el proceso de algebrización y la modelización.",
        [("769_1", "Articulación teórica entre competencia algebraica y modelización")],
    ),
    "Efectos psicológicos de la música y danza en la construcción de cultura de paz": (
        "Estudio experimental del efecto de estímulos musicales y de danza andina sobre la empatía intergrupal, dominancia social y estereotipos hacia el grupo andino.",
        [("838_2", "Efectos psicológicos de la música y danza en la construcción de cultura de paz")],
    ),
    "Tipificación estructural de edificaciones patrimoniales mediante HBIM": (
        "Metodología de tipificación estructural de edificaciones patrimoniales usando modelado digital (HBIM) y realidad aumentada, aplicada a 22 iglesias andinas del sur del Perú.",
        [("836_7", "Tipificación estructural de edificaciones patrimoniales mediante HBIM")],
    ),
    "Escritura epistolar y agencia política de Manuela Sáenz": (
        "Análisis de las cartas y diarios de Manuela Sáenz Aizpuru como fuente para que ella misma explique su propia política durante las independencias americanas.",
        [("870_3", "Escritura epistolar y agencia política de Manuela Sáenz")],
    ),
    "Integración comercial del Perú en la cooperación Asia-Pacífico": (
        "Análisis del rol del Perú y la Alianza del Pacífico en la integración comercial con la región Asia-Pacífico.",
        [("703_29", "Integración comercial del Perú en la cooperación Asia-Pacífico")],
    ),
    "Adherencia a intervenciones de salud mental digital en jóvenes": (
        "Revisión de la literatura sobre adherencia a programas de salud mental digital (e-mental health) en jóvenes y recomendaciones de diseño de intervención.",
        [("838_1", "Adherencia a intervenciones de salud mental digital en jóvenes")],
    ),
    "Convergencia de caminatas aleatorias coalescentes al coalescente de Kingman": (
        "Demostración de que una secuencia de cadenas de Markov de caminatas aleatorias coalescentes en un toro discreto converge al coalescente de Kingman.",
        [("658_1", "Convergencia de caminatas aleatorias coalescentes al coalescente de Kingman")],
    ),
    "Validación de escala de involucramiento parental en padres peruanos": (
        "Evidencias de validez y confiabilidad de la Escala de Involucramiento Parental (actividades de cuidado y socialización) en una muestra de 420 padres y 420 madres peruanos.",
        [("769_2", "Validación de escala de involucramiento parental en padres peruanos")],
    ),
    "Simulación numérica del comportamiento fluido-dinámico de un agitador a escala reducida": (
        "Estudio mediante CFD del comportamiento de un agitador con impulsor hidroala para mezclar agua con partículas polimetálicas en la industria minera.",
        [("738_4", "Simulación numérica del comportamiento fluido-dinámico de un agitador a escala reducida")],
    ),
    "Revisión narrativa de estudios de apego en América Latina": (
        "Revisión sistemática narrativa de 82 publicaciones latinoamericanas sobre teoría del apego y sensitividad materna, evaluando la aplicabilidad de sus hipótesis centrales fuera de países occidentales.",
        [("572_1", "Revisión narrativa de estudios de apego en América Latina")],
    ),
    "Polarización política y representatividad democrática del voto": (
        "Análisis del rol mediador de los contextos políticos y la consolidación democrática sobre el efecto de la polarización del sistema de partidos en el voto ideológico.",
        [("731_3", "Polarización política y representatividad democrática del voto")],
    ),
    "Optimización ambiental de dietas alimentarias peruanas mediante programación lineal": (
        "Modelo de programación lineal que combina evaluación de ciclo de vida con datos nutricionales y económicos para optimizar 25 patrones dietéticos peruanos y reducir emisiones de GEI.",
        [("672_6", "Optimización ambiental de dietas alimentarias peruanas mediante programación lineal")],
    ),
    "Síndrome de agotamiento profesional en trabajadores penitenciarios peruanos": (
        "Investigación cualitativa nacional sobre los factores institucionales y sociales asociados al síndrome de agotamiento profesional en trabajadores penitenciarios del Perú.",
        [("520_12", "Síndrome de agotamiento profesional en trabajadores penitenciarios peruanos")],
    ),
    "Base de datos Grambank sobre diversidad gramatical y pérdida lingüística": (
        "Presentación de Grambank, la mayor base de datos comparativa de gramática disponible (2400 lenguas), usada para cuantificar el efecto de la herencia genealógica y la proximidad geográfica sobre la diversidad lingüística.",
        [("901_14", "Base de datos Grambank sobre diversidad gramatical y pérdida lingüística")],
    ),
    "Teología de la liberación de Gustavo Gutiérrez y ética teológica contemporánea": (
        "Análisis de la articulación entre la salvación cristiana y la liberación de la opresión, y del aporte de Gustavo Gutiérrez a la comprensión teológica del sufrimiento humano.",
        [("788_7", "Teología de la liberación de Gustavo Gutiérrez y ética teológica contemporánea")],
    ),
    "Juegos tradicionales shipibo-konibo como herramienta pedagógica intercultural": (
        "Recopilación de juegos tradicionales del pueblo shipibo-konibo y propuesta de su aprovechamiento como herramienta educativa para sociedades interculturales.",
        [("502_21", "Juegos tradicionales shipibo-konibo como herramienta pedagógica intercultural")],
    ),
    "Representación de la mujer andina en el cine peruano del conflicto armado interno": (
        "Análisis de la representación desigual de personajes femeninos andinos en el cine peruano ambientado en el conflicto armado interno (1980-1999), en la película La boca del lobo.",
        [("709_9", "Representación de la mujer andina en el cine peruano del conflicto armado interno")],
    ),
    "Grandes desviaciones estáticas en modelos de reacción-difusión": (
        "Principio de grandes desviaciones para la medida empírica bajo el estado estacionario de un modelo de reacción-difusión con dinámica de exclusión simple y spin-flip.",
        [("659_1", "Grandes desviaciones estáticas en modelos de reacción-difusión")],
    ),
    "Envejecimiento y degradación mecánica de espinas de erizo de mar": (
        "Evaluación del efecto del envejecimiento y la irradiación UV sobre las propiedades mecánicas y los modos de falla de espinas de erizo de mar, como modelo de compuesto natural duro.",
        [("762_7", "Envejecimiento y degradación mecánica de espinas de erizo de mar")],
    ),
    "Convección inducida por gradientes térmicos en frentes de reacción química": (
        "Modelo de frente delgado para la propagación de frentes de reacción química en líquidos dentro de una celda Hele-Shaw, incorporando gradientes de densidad térmicos y composicionales.",
        [("718_1", "Convección inducida por gradientes térmicos en frentes de reacción química")],
    ),
    "Control óptimo lineal-cuadrático de sistemas singulares con saltos markovianos": (
        "Solución del problema de control óptimo lineal-cuadrático para sistemas lineales singulares de tiempo discreto con saltos markovianos, mediante transformaciones de base.",
        [("657_1", "Control óptimo lineal-cuadrático de sistemas singulares con saltos markovianos")],
    ),
    "Prácticas de ética empresarial en grandes empresas peruanas": (
        "Caracterización de las prácticas de ética y gestión empresarial reportadas por empresas del top 10000 en el Perú.",
        [("855_1", "Prácticas de ética empresarial en grandes empresas peruanas")],
    ),
    "Modelo de regresión beta-inflada con efectos mixtos para variables fraccionarias": (
        "Nuevo modelo de regresión de efectos mixtos para variables de respuesta fraccionarias acotadas, estimado bayesianamente y aplicado a datos de utilización de líneas de crédito en el Perú.",
        [("690_1", "Modelo de regresión beta-inflada con efectos mixtos para variables fraccionarias")],
    ),
    "Modelamiento de la corrosión de materiales ferrosos mediante diseño D-óptimo": (
        "Modelamiento de la tasa de corrosión de acero al carbono y acero inoxidable inmersos en sulfato y cloruro férrico, usando diseño experimental D-óptimo y metodología de superficie de respuesta.",
        [("578_6", "Modelamiento de la corrosión de materiales ferrosos mediante diseño D-óptimo")],
    ),
    "Efectos espectrales en el rendimiento de tecnologías fotovoltaicas en Lima": (
        "Primer estudio del impacto espectral sobre el desempeño de distintas tecnologías fotovoltaicas en Lima, monitoreando la distribución espectral durante un año.",
        [("904_1", "Efectos espectrales en el rendimiento de tecnologías fotovoltaicas en Lima")],
    ),
    "Caracterización de cámaras de radón con detectores CR-39": (
        "Estudio de la permeabilidad y el factor de transmisión de radón usando detectores CR-39 dentro de cámaras de difusión no comerciales, en una cámara de radón de nueva construcción.",
        [("850_1", "Caracterización de cámaras de radón con detectores CR-39")],
    ),
    "Conjunto de datos Grammars Across Time Analyzed (GATA) para lingüística histórica": (
        "Presentación del recurso GATA, con información gramatical de 52 lenguas en dos momentos temporales distintos, para el estudio del cambio lingüístico y cultural.",
        [("901_2", "Conjunto de datos Grammars Across Time Analyzed (GATA) para lingüística histórica")],
    ),
    "Reconstrucción paleogenómica de la historia poblacional andina": (
        "Datos genómicos de 89 individuos de entre 9,000 y 500 años de antigüedad que reconstruyen la historia poblacional profunda de los Andes centrales y surcentrales, incluyendo Moche, Wari, Tiwanaku e Inca.",
        [("722_4", "Reconstrucción paleogenómica de la historia poblacional andina")],
    ),
    "Detección de cianuro en agua mediante nanopartículas de oro y dispersión Rayleigh de resonancia": (
        "Sensor ratiométrico altamente sensible para cuantificar cianuro en muestras acuosas usando nanopartículas de oro estabilizadas, con límites de detección por debajo del máximo aceptable de la OMS.",
        [("634_1", "Detección de cianuro en agua mediante nanopartículas de oro y dispersión Rayleigh de resonancia")],
    ),
    "Modelo bayesiano de respuesta al ítem para medir fluidez verbal con speededness": (
        "Modelo bayesiano simple para estimar parámetros personales y de ítem a partir de datos de fluidez de palabras sin sentido en estudiantes peruanos, en presencia de speededness.",
        [("690_8", "Modelo bayesiano de respuesta al ítem para medir fluidez verbal con speededness")],
    ),
    "Detección de trigonelina como marcador de calidad de café mediante espectrometría Raman portátil": (
        "Título declarado sobre detección selectiva de trigonelina (marcador de calidad del café) con un espectrómetro Raman portátil; el resumen disponible no corresponde al tema del título (revisión genérica de RMN en alimentos).",
        [("510_1", "Detección de trigonelina como marcador de calidad de café mediante espectrometría Raman portátil")],
    ),
    "Modelado incremental del fondo de video robusto a vibración de cámara (PCP)": (
        "Algoritmo incremental de Principal Component Pursuit para modelado de fondo de video que es robusto a la vibración traslacional y rotacional de la cámara, procesando un cuadro a la vez.",
        [("557_11", "Modelado incremental del fondo de video robusto a vibración de cámara (PCP)")],
    ),
    "Modelo de diseño de videojuegos educativos sobre historia": (
        "Aplicación y validación de un modelo de diseño de videojuegos educativos al desarrollo de un videojuego sobre la independencia del Perú, evaluado con estudiantes universitarios.",
        [("808_5", "Modelo de diseño de videojuegos educativos sobre historia")],
    ),
    "Fotografía aérea con UAV de ala fija para reconstrucción 3D en zonas altoandinas": (
        "Sistema UAV de ala fija capaz de 30 minutos de vuelo en alta altitud (5000-6200 m.s.n.m.) para fotografía aérea orientada a la reconstrucción 3D georreferenciada de paisajes altoandinos.",
        [("539_6", "Fotografía aérea con UAV de ala fija para reconstrucción 3D en zonas altoandinas")],
    ),
    "Codificación dispersa convolucional sin parámetro de regularización vía proyección en bola L1": (
        "Método libre de parámetro de regularización para resolver el problema de codificación dispersa convolucional, mediante proyección sobre la bola L1 guiada por el principio de discrepancia de Morozov.",
        [("839_6", "Codificación dispersa convolucional sin parámetro de regularización vía proyección en bola L1")],
    ),
    "Movilización feminista intergeneracional en las marchas Ni Una Menos": (
        "Estudio de cómo activistas jóvenes se incorporan al movimiento Ni Una Menos gracias a la mediación productiva y el aprendizaje feminista entre generaciones de activistas.",
        [("623_4", "Movilización feminista intergeneracional en las marchas Ni Una Menos")],
    ),
    "El \"Sur Distorsionado\" como marco de la música metal peruana": (
        "Propuesta del concepto del Sur Distorsionado como espacio geográfico y simbólico desde el cual personas oprimidas usan la música metal para reflexionar críticamente sobre su experiencia.",
        [("797_4", "El \"Sur Distorsionado\" como marco de la música metal peruana")],
    ),
    "Contaminación por metales pesados en sedimentos viales de corredores urbanos (Bogotá-Soacha)": (
        "Evaluación de la contaminación por metales pesados (Pb, Zn, entre otros) en sedimentos viales de dos zonas del corredor Bogotá-Soacha, atribuida principalmente a fuentes móviles.",
        [("507_10", "Contaminación por metales pesados en sedimentos viales de corredores urbanos (Bogotá-Soacha)")],
    ),
    "Estatuto jurídico del consejo de usuarios en los servicios públicos de energía en el Perú": (
        "Título declarado sobre el estatuto jurídico del consejo de usuarios de servicios de energía en el Perú; el texto disponible no corresponde al tema del título (describe proyectos legislativos argentinos).",
        [("734_6", "Estatuto jurídico del consejo de usuarios en los servicios públicos de energía en el Perú")],
    ),
    "Articulación de los dominios de geometría y análisis mediante modelización y tecnología digital": (
        "Tarea de modelización sobre función cuadrática, parte de una secuencia didáctica internacional orientada a articular los dominios de geometría y análisis mediante tecnología digital.",
        [("854_3", "Articulación de los dominios de geometría y análisis mediante modelización y tecnología digital")],
    ),
    "Robot humanoide asistivo social para intervenciones de salud mental a distancia": (
        "Diseño de un robot humanoide asistivo social con brazos articulados y expresión gestual, evaluado para ofrecer intervenciones telepsicológicas a pacientes aislados en hospitales.",
        [("908_9", "Robot humanoide asistivo social para intervenciones de salud mental a distancia")],
    ),
    "Transferencia tecnológica y territorialidad de la vivienda altoandina": (
        "Lectura arquitectónica de territorios rurales alpaqueros sobre 4000 m.s.n.m., analizando la vivienda rural y sus relaciones con los espacios productivos de las comunidades altoandinas.",
        [("801_7", "Transferencia tecnológica y territorialidad de la vivienda altoandina")],
    ),
    "Historia fiscal del Perú e impacto asimétrico de la política fiscal (1980-2020)": (
        "Análisis del impacto asimétrico del gasto público y la recaudación tributaria sobre el PBI peruano entre 2000 y 2022, usando un modelo de regresión de umbral (Threshold Autoregressive).",
        [("842_1", "Historia fiscal del Perú e impacto asimétrico de la política fiscal (1980-2020)")],
    ),
    "Derechos indígenas, extractivismo y respuesta estatal a la pandemia en la Amazonía": (
        "Discusión sobre el centralismo institucional y la autodeterminación de los pueblos indígenas amazónicos frente a la pandemia, y su demanda de protección de derechos, territorio y salud culturalmente apropiada frente al extractivismo.",
        [("811_6", "Derechos indígenas, extractivismo y respuesta estatal a la pandemia en la Amazonía")],
    ),
    "Libre mercado y educación superior: universidades de bajo costo en el Perú": (
        "Título declarado sobre el caso de universidades privadas de bajo costo en el Perú bajo una lógica de libre mercado; solo se dispone de palabras clave genéricas no relacionadas, sin resumen real.",
        [("586_2", "Libre mercado y educación superior: universidades de bajo costo en el Perú")],
    ),
    "Documentación gramatical del idioma kakataibo (familia Pano)": (
        "Gramática de referencia del kakataibo, lengua de la familia Pano hablada en el Perú, como documentación y descripción lingüística.",
        [("536_4", "Documentación gramatical del idioma kakataibo (familia Pano)")],
    ),
}

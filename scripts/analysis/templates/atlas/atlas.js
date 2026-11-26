(function(){
  "use strict";
  // Un dataset (universidad) a la vez. build_atlas.py escribe por dataset un
  // archivo con sus numeros y sus textos propios (atlas_profiles.py); esta
  // pagina solo tiene el texto comun. Publicada, carga datasets.json y luego
  // data/<id>.json; como archivo unico (atlas_<id>.html) trae su dataset
  // incrustado y no muestra el selector.
  // Cada dataset se puede ver contra varios planes (retos): el cruce con cada
  // uno viaja aparte, en data/<id>/<plan>.json, y se carga al elegirlo. En el
  // archivo unico vienen todos incrustados (bundle.plans).
  var INLINE = JSON.parse(document.getElementById('bundle').textContent);
  var loaded = {}, ctrl = null, current = null, planHook = null;
  // Mapa de la investigacion (pestaña «Mapa»): uno para todos los datasets, en
  // data/mapa.json (research_map.py place). Se carga la primera vez que se abre.
  var MAPA = null, MAPA_ERR = null, mapaReq = null;
  function loadMap(){
    if (!mapaReq) mapaReq = fetchJSON('data/mapa.json')
      .then(function(M){ MAPA = M; })
      .catch(function(err){ MAPA_ERR = err.message; });
    return mapaReq;
  }
  var msg = document.getElementById('loadmsg');

  function status(text){ msg.textContent = text || ''; msg.hidden = !text; }
  function fetchJSON(url){
    return fetch(url).then(function(r){
      if (!r.ok) throw new Error(url + ': HTTP ' + r.status);
      return r.json();
    });
  }
  function initialId(list){
    var want = null;
    try { want = new URLSearchParams(location.search).get('ds'); } catch (e) {}
    if (!want) try { want = localStorage.getItem('atlas-ds'); } catch (e) {}
    var ids = list.map(function(x){ return x.id; });
    return ids.indexOf(want) >= 0 ? want : ids[0];
  }
  function remember(id){
    try { localStorage.setItem('atlas-ds', id); } catch (e) {}
    try {
      var u = new URL(location.href); u.searchParams.set('ds', id);
      history.replaceState(null, '', u.toString());
    } catch (e) {}
  }
  function paintSelector(list){
    var box = document.getElementById('ds');
    box.textContent = '';
    document.getElementById('datasets').hidden = list.length < 2;
    list.forEach(function(x){
      var b = document.createElement('button');
      b.type = 'button'; b.textContent = x.label; b.title = x.title;
      b.setAttribute('aria-pressed', String(x.id === current));
      b.addEventListener('click', function(){ if (x.id !== current) open(list, x.id); });
      box.appendChild(b);
    });
  }
  // --- planes ---------------------------------------------------------------
  // Un archivo de datos de antes de los planes multiples trae un solo plan
  // (profile.plan) y su cruce dentro de cada dominio (data[d].ceplan).
  function normalize(B){
    var PF = B.profile;
    if (PF.plans) return B;
    var k = PF.plan.key;
    PF.plans = {}; PF.plans[k] = PF.plan; PF.plan_order = [k]; PF.plan_default = k;
    B.plans = {}; B.plans[k] = {};
    Object.keys(B.data).forEach(function(d){ B.plans[k][d] = B.data[d].ceplan || null; });
    return B;
  }
  function initialPlan(B){
    var PF = B.profile, want = null;
    try { want = new URLSearchParams(location.search).get('plan'); } catch (e) {}
    if (!want) try { want = localStorage.getItem('atlas-plan'); } catch (e) {}
    return PF.plan_order.indexOf(want) >= 0 ? want : PF.plan_default;
  }
  function rememberPlan(key){
    try { localStorage.setItem('atlas-plan', key); } catch (e) {}
    try {
      var u = new URL(location.href); u.searchParams.set('plan', key);
      history.replaceState(null, '', u.toString());
    } catch (e) {}
  }
  function loadPlan(B, key){
    B.plans = B.plans || {};
    if (B.plans[key]) return Promise.resolve(B.plans[key]);
    return fetchJSON('data/' + encodeURIComponent(B.profile.id) + '/' + encodeURIComponent(key) + '.json')
      .then(function(P){ B.plans[key] = P; return P; });
  }
  function paintPlans(B, key){
    var PF = B.profile, box = document.getElementById('plans');
    box.textContent = '';
    document.getElementById('plansel').hidden = PF.plan_order.length < 2;
    PF.plan_order.forEach(function(k){
      var p = PF.plans[k], b = document.createElement('button');
      b.type = 'button'; b.textContent = p.short; b.title = p.name;
      b.setAttribute('aria-pressed', String(k === key));
      b.addEventListener('click', function(){ if (k !== B.planKey) choosePlan(B, k); });
      box.appendChild(b);
    });
  }
  function choosePlan(B, key){
    var id = B.profile.id;
    B.planKey = key; paintPlans(B, key);
    if (!B.plans || !B.plans[key]) status('Cargando ' + B.profile.plans[key].name + '…');
    loadPlan(B, key).then(function(){
      if (current !== id || B.planKey !== key) return;   // se eligio otra cosa mientras cargaba
      status(''); rememberPlan(key);
      if (planHook) planHook(key);
    }).catch(function(err){
      if (B.planKey === key) status('No se pudo cargar el cruce con ' + B.profile.plans[key].name +
        ' (' + err.message + ').');
    });
  }
  // Pinta el dataset ya con su plan cargado: la pagina nunca se muestra con un
  // plan a medio llegar.
  function start(B){
    normalize(B);
    var key = initialPlan(B);
    return loadPlan(B, key).catch(function(){
      key = B.profile.plan_default;
      return loadPlan(B, key);
    }).then(function(){
      if (current !== B.profile.id) return;   // se eligio otro dataset mientras cargaba
      B.planKey = key; rememberPlan(key); paintPlans(B, key); mount(B, key);
    });
  }

  function open(list, id){
    current = id; paintSelector(list);
    if (!loaded[id]) status('Cargando ' + (list.filter(function(x){ return x.id === id; })[0] || {}).label + '…');
    (loaded[id] ? Promise.resolve(loaded[id]) : fetchJSON('data/' + encodeURIComponent(id) + '.json'))
      .then(function(B){
        loaded[id] = B;
        if (current !== id) return;   // se eligio otro mientras cargaba
        return start(B).then(function(){ if (current === id){ status(''); remember(id); } });
      })
      .catch(function(err){
        if (current === id) status('No se pudieron cargar los datos de este dataset (' + err.message + ').');
      });
  }

  if (INLINE){ current = INLINE.profile.id; start(INLINE); }
  else fetchJSON('datasets.json').then(function(M){ open(M.datasets, initialId(M.datasets)); })
    .catch(function(){
      status(location.protocol === 'file:' ?
        'Abierta desde el disco, el navegador no deja que la página lea sus datos. Abre el archivo ' +
        'único atlas_<dataset>.html, o sirve esta carpeta (python -m http.server).' :
        'No se pudo cargar la lista de datasets (datasets.json).');
    });

  // Pinta un dataset completo. Cada llamada empieza de cero: los escuchadores
  // de la llamada anterior se quitan con su AbortController y las secciones se
  // vacian, para que nada de un dataset se cuele en el otro.
  function mount(B, planKey){
  if (ctrl) ctrl.abort();
  ctrl = new AbortController();
  var SIG = {signal: ctrl.signal};
  var DATA = B.data, META = B.method, PF = B.profile;
  // Lo que cambia con el plan elegido; lo asigna applyPlan().
  var PL, LEAF, LEAVES, PLAN_TITLE, STATUS_TXT;

  document.title = PF.title;
  document.getElementById('title').textContent = PF.title;
  document.getElementById('eyebrow').textContent = PF.eyebrow;
  ['method', 'provenance', 'ceplan', 'summary', 'map'].forEach(function(id){
    var s = document.getElementById(id); s.textContent = ''; delete s.dataset.done;
  });
  var CH = window.AtlasCharts;
  document.getElementById('atlas').hidden = false;
  document.getElementById('menu').hidden = false;

  Object.keys(DATA).forEach(function(d){
    var t = PF.domains[d] || {label: d, noun: 'unidad'};
    DATA[d].label = t.label; DATA[d].noun = t.noun; DATA[d].kind = t.kind;
  });
  var NAMES = {};
  PF.order.forEach(function(d){ NAMES[d] = PF.domains[d].tab; });

  // Cambia el plan sin rehacer la pagina: el cruce de cada dominio pasa a
  // DATA[d].ceplan y el vocabulario (hoja, nombre, avisos) al del plan nuevo.
  function applyPlan(key){
    planKey = key;
    PL = PF.plans[key];
    var P = B.plans[key] || {};
    Object.keys(DATA).forEach(function(d){ DATA[d].ceplan = P[d] || null; });
    // Las hojas de los planes cargados hoy son femeninas («sub-temática»,
    // «política»): «Ninguna», «desarrollada».
    LEAF = PL.leaf; LEAVES = PL.leaves; PLAN_TITLE = cap(LEAVES) + ' del ' + PL.name;
    STATUS_TXT = {
      sin_candidatas: 'Ninguna ' + LEAF + ' del ' + PL.name + ' se parece lo suficiente a esta unidad ' +
        '(similitud bajo el piso). Es lo esperable en investigación básica sin relación con política pública.',
      rechazadas_por_llm: 'Hubo ' + LEAVES + ' candidatas, pero el verificador no confirmó relación con ninguna.',
      verificacion_fallida: 'La verificación de esta unidad no produjo una respuesta legible.'
    };
    document.getElementById('dom-ceplan').title = PL.tab + ' · ' + PL.name;
    document.getElementById('omniq').placeholder =
      'Busca un proyecto, una publicación, un tema o una ' + PL.leaf + ' ' + PL.short + '…';
  }
  applyPlan(planKey);

  var dom = PF.order[0], mode = 'topic', sel = null, query = '';
  var idx = {};

  function build(d){
    if (idx[d]) return idx[d];
    var D = DATA[d], byTopic = {}, byUnit = {};
    D.cells.forEach(function(c){
      (byTopic[c[1]] = byTopic[c[1]] || []).push({u:c[0], c:c[2], k:c[3]});
      (byUnit[c[0]] = byUnit[c[0]] || []).push({t:c[1], c:c[2], k:c[3]});
    });
    Object.keys(byTopic).forEach(function(t){ byTopic[t].sort(function(a,b){return b.k-a.k;}); });
    Object.keys(byUnit).forEach(function(u){ byUnit[u].sort(function(a,b){return b.c-a.c;}); });
    idx[d] = {byTopic:byTopic, byUnit:byUnit};
    return idx[d];
  }
  function pct(x, dp){ return (x*100).toFixed(dp===undefined?1:dp) + ' %'; }
  function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g, function(m){
    return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[m]; }); }
  function el(tag, cls, txt){ var e=document.createElement(tag); if(cls)e.className=cls;
    if(txt!=null)e.textContent=txt; return e; }
  function cap(s){ return s.charAt(0).toUpperCase() + s.slice(1); }
  function plural(noun){ return noun.replace(/ción$/, 'cione') + 's'; }
  function fem(noun){ return /ción$/.test(noun); }
  function ningun(noun){ return (fem(noun) ? 'Ninguna ' : 'Ningún ') + noun; }

  // --- filtro de años -------------------------------------------------------
  // Recalcula, para el rango elegido, lo mismo que la corrida calcula para todo
  // el corpus: tamaño de tema = Σ contención de las unidades del rango, y el
  // aporte se renormaliza para que vuelva a sumar 100 % dentro del rango.
  var YR = (function(){
    var lo = Infinity, hi = -Infinity;
    Object.keys(DATA).forEach(function(d){
      Object.keys(DATA[d].units).forEach(function(u){
        var y = DATA[d].units[u].y;
        if (y){ lo = Math.min(lo, y); hi = Math.max(hi, y); }
      });
    });
    if (lo === Infinity){ lo = hi = new Date().getFullYear(); }
    return {min: lo, max: hi, lo: lo, hi: hi, nodate: true};
  })();
  function yrActive(){ return YR.lo > YR.min || YR.hi < YR.max || !YR.nodate; }
  function yrKey(d){ return d + '|' + YR.lo + '|' + YR.hi + '|' + YR.nodate; }
  function inYears(d, uid){
    var u = DATA[d].units[uid], y = u && u.y;
    if (!y) return YR.nodate;
    return y >= YR.lo && y <= YR.hi;
  }
  function yrText(){ return YR.lo === YR.hi ? String(YR.lo) : YR.lo + '–' + YR.hi; }

  var vcache = {};
  function view(d){
    var key = yrKey(d);
    if (vcache[key]) return vcache[key];
    var D = DATA[d], I = build(d), act = yrActive();
    var V = {eq: {}, n: {}, byTopic: {}, nu: 0, nt: 0};
    Object.keys(D.units).forEach(function(u){ if (inYears(d, u)) V.nu++; });
    Object.keys(D.topics).forEach(function(t){
      var rows = (I.byTopic[t] || []).filter(function(r){ return inYears(d, r.u); });
      var s = rows.reduce(function(a, r){ return a + r.c; }, 0);
      V.eq[t] = act ? s : D.topics[t].eq;
      V.n[t] = act ? rows.length : D.topics[t].n;
      V.byTopic[t] = !act ? rows : rows.map(function(r){ return {u: r.u, c: r.c, k: s ? r.c / s : 0}; })
        .sort(function(a, b){ return b.k - a.k; });
      if (V.n[t]) V.nt++;
    });
    if (!act){ V.nu = D.nu; V.nt = D.nt; }
    return (vcache[key] = V);
  }

  // Cruce del dominio con el plan, recalculado para el rango de años. Por
  // defecto el plan elegido; con C y pk, otro plan ya cargado (Resumen).
  function cview(d, C, pk){
    pk = pk || planKey; C = C || DATA[d].ceplan;
    var key = 'c:' + pk + '|' + yrKey(d);
    if (vcache[key]) return vcache[key];
    var act = yrActive(), V = {subs: {}, byOn: {}, aligned: 0, nu: 0};
    Object.keys(C.subs).forEach(function(k){
      var s = C.subs[k];
      V.subs[k] = act ? {n: 0, n2: 0, eq: 0, cov: 'sin_desarrollo'} : {n: s.n, n2: s.n2, eq: s.eq, cov: s.cov};
    });
    Object.keys(C.status).forEach(function(u){ if (inYears(d, u)) V.nu++; });
    Object.keys(C.units).forEach(function(u){
      if (!inYears(d, u)) return;
      V.aligned++;
      if (!act) return;
      C.units[u].forEach(function(r){
        var s = V.subs[r[0]]; if (!s) return;
        s.n++; if (r[1] === 2) s.n2++; s.eq += r[2];
      });
    });
    Object.keys(V.subs).forEach(function(k){
      var s = V.subs[k];
      if (act) s.cov = s.n2 >= C.minG2 ? 'desarrollada' : (s.n2 > 0 ? 'debil' : 'sin_desarrollo');
      var on = C.subs[k].o;
      V.byOn[on] = (V.byOn[on] || 0) + s.eq;
    });
    if (!act) V.byOn = C.byOn;
    return (vcache[key] = V);
  }
  function yrBanner(box, d, nIn, nAll){
    if (!yrActive()) return;
    var D = DATA[d];
    box.appendChild(el('p', 'yr-banner', 'Años ' + yrText() + (YR.nodate ? ' (y sin año)' : '') + ': ' +
      nIn.toLocaleString('es') + ' de ' + nAll.toLocaleString('es') + ' ' + plural(D.noun) +
      '. Tamaños y aportes recalculados dentro del rango.'));
  }


  function renderMethod(){
    var A = 'Cuánto de la unidad es este tema';
    var B = 'Cuánto del tema aporta la unidad';
    var box = document.getElementById('method');
    if (box.dataset.done) return;
    box.dataset.done = '1';
    // Todo numero concreto de esta pestana sale de la corrida cargada, no
    // escrito a mano: si se renormaliza, el ejemplo se actualiza solo.
    var dom0 = PF.order.filter(function(d){ return DATA[d].kind === 'projects'; })[0] || PF.order[0];
    var D0 = DATA[dom0], EX = D0.ex || {}, E = EX.main, BIG = EX.big, SM = EX.small;
    var NTEMAS = Object.keys(D0.topics).length, NUNI = Object.keys(D0.units).length;
    function n(x, dp){ return Number(x).toLocaleString('es-ES',
        {minimumFractionDigits: dp, maximumFractionDigits: dp}); }
    var h = [];
    h.push('<h2>Cómo se produjeron estos porcentajes</h2>');
    h.push('<p>Cada universo se procesa por separado, con su propio espacio de temas. El mismo ' +
           'código corre para los dos; sólo cambia el CSV de origen y las columnas que aportan texto.</p>');

    h.push('<h3>Flujo de datos</h3><div class="flow">');
    [['01','Unidades de texto','Se concatenan las columnas con contenido temático de cada fila. Las columnas vacías se omiten'],
     ['02','Extracción de temas','Un LLM lee cada unidad y devuelve de 1 a 5 temas con descripción, <b>cita literal</b> y confianza (0–1). La cita se verifica contra el texto de origen.'],
     ['03','Normalización','Se convierte a embedding cada tema extraído y se agrupan por similitud coseno, sin intervención del LLM. Sólo después un LLM pone nombre y descripción a cada grupo ya formado. Resultado: '+NTEMAS+' temas normalizados.'],
     ['04','Cuantificación','Se construye la matriz de afinidad y se normaliza en las dos direcciones. Es la etapa que produce los porcentajes.']
    //  ['05','Reportes','Tablas, métricas de la partición y consumo de recursos por etapa.']
    ].forEach(function(s){
      h.push('<div class="step"><span class="n">'+s[0]+'</span><span class="t">'+s[1]+
             '</span><span class="d">'+s[2]+'</span></div>');
    });
    h.push('</div>');

    h.push('<h3>Un ejemplo, paso a paso</h3>');
    h.push('<p>' + cap(D0.noun) + ' <b>' + E.uid +
           ' — «' + E.u + '»</b>, de la corrida real. Así se llega a sus dos porcentajes.</p>');
    var P = E.parts || {}, CO = P.comp || [], LL = P.llm || [];
    function fila(c){
      return '<tr><td class="nm">' + c.t + '</td>' +
             '<td class="mixnum">' + (c.cos ? n(c.cos, 4) : '—') + '</td>' +
             '<td class="mixnum' + (c.e ? '' : ' zero') + '">' + n(c.e, 4) + '</td>' +
             '<td class="mixnum' + (c.s ? '' : ' zero') + '">' + n(c.s, 4) + '</td>' +
             '<td class="mixnum"><b>' + n(c.w, 4) + '</b></td></tr>';
    }
    h.push('<div class="calc">' +
      '<div class="calc-step"><span class="s">1</span><div class="b">' +
        '<p>El LLM lee el texto de la unidad y extrae sus temas, cada uno con una cita literal ' +
        'verificada contra el texto y una confianza de 0 a 1. Para esta unidad devolvió ' +
        LL.length + ':</p>' +
        '<span class="eq">' + LL.map(function(x){
            return n(x.c, 2) + '&nbsp; «' + x.t + '»'; }).join('<br>') + '</span></div></div>' +

      '<div class="calc-step"><span class="s">2</span><div class="b">' +
        '<p><b>Primera parte: temas normalizados</b> Esos temas extraídos se agrupan por ' +
        '<b>geometría, no por criterio del LLM</b>: cada uno se convierte en embedding y entra ' +
        'en un grupo si supera un umbral de similitud coseno calibrado sobre el propio corpus. ' +
        'Recién con los grupos ya cerrados un LLM mira cada uno y le pone nombre y descripción; ' +
        '</p>' +
        '<p>Aquí los ' + LL.length + ' temas extraídos cayeron ' +
        (P.nllm === 1 ? 'todos en el mismo grupo, <b>«' + E.t + '»</b>: un único 1,0000 y cero ' +
                        'en los otros ' + (NTEMAS - 1) + ' temas.' :
                        'en ' + P.nllm + ' grupos distintos.') +
        '</p></div></div>' +

      '<div class="calc-step"><span class="s">3</span><div class="b">' +
        '<p><b>Segunda mitad: lo que dice el texto completo.</b> El LLM no dice nada sobre los ' +
        'demás temas, así que con eso solo la unidad sería 100 % un tema y 0 % todo lo demás. ' +
        'Aparte se mide entonces la similitud coseno entre el embedding de la unidad entera y el ' +
        'centroide de cada uno de los ' + NTEMAS + ' temas (el centroide es la media de los ' +
        'embeddings de los temas extraídos que cayeron en él).</p>' +
        '<p>Esa similitud se recorta antes de usarla: se descarta lo que no pasa de ' +
        n(P.floor, 2) + ', se conservan los ' + P.k + ' temas más cercanos y se elevan a ' +
        n(P.power, 0) + '.</p></div></div>' +

      '<div class="calc-step"><span class="s">4</span><div class="b">' +
        '<p><b>Las dos mitades se mezclan:</b> ' + n(P.alpha*100, 0) + ' % la extracción del LLM y ' +
        n((1-P.alpha)*100, 0) + ' % la similitud.</p>' +
        '<div class="tablewrap"><table><thead><tr><th>Tema</th>' +
        '<th class="mixnum">Coseno<span class="hint">crudo</span></th>' +
        '<th class="mixnum">LLM<span class="hint">fila normalizada</span></th>' +
        '<th class="mixnum">Embedding<span class="hint">fila normalizada</span></th>' +
        '<th class="mixnum">Afinidad<span class="hint">' + n(P.alpha, 1) + '·LLM + ' +
        n(1-P.alpha, 1) + '·emb.</span></th></tr></thead><tbody>' +
        CO.map(fila).join('') + '</tbody></table></div>' +
        (CO.length ? '<span class="eq">' + n(P.alpha, 1) + ' × ' + n(CO[0].e, 4) +
          '&nbsp; + &nbsp;' + n(1-P.alpha, 1) + ' × ' + n(CO[0].s, 4) + ' = <b>' +
          n(CO[0].w, 4) + '</b></span>' : '') +
        '<p class="warnline">Sólo la primera celda tiene evidencia textual detrás. Las otras ' +
        (CO.length - 1) + ' son ' + n(1-P.alpha, 1) + ' × similitud y nada más: proximidad ' +
        'semántica del texto, no algo que el LLM haya afirmado de esta unidad.</p></div></div>' +

      '<div class="calc-step"><span class="s">5</span><div class="b">' +
        '<p><b class="cc">' + A + '</b> — se divide cada afinidad entre la suma de su fila:</p>' +
        '<span class="eq">' + n(E.aff, 4) + ' ÷ ' + n(E.rowsum, 4) + ' = <b class="cc">' +
        n(E.c, 3) + ' → ' + n(E.c*100, 1) + ' %</b></span>' +
        '<p style="margin-top:7px">Es decir: el ' + n(E.c*100, 1) + ' % de lo que esta unidad trata ' +
        'es ese tema. Las ' + E.nrow + ' cifras de la fila suman 100 %.</p></div></div>' +
      '<div class="calc-step"><span class="s">6</span><div class="b">' +
        '<p>Se suma esa misma columna sobre las ' + n(NUNI, 0) + ' unidades. El tema recibe ' +
        'fracciones de muchas de ellas y acumula <b>' + n(E.eq, 2) + ' unidades-equivalentes</b>: ' +
        'vale ' + n(E.eq, 2) + ' unidades enteras, aunque lo rocen ' + E.nt + '.</p></div></div>' +
      '<div class="calc-step"><span class="s">7</span><div class="b">' +
        '<p><b class="kk">' + B + '</b> — se divide la cifra del paso 5 entre el tamaño del tema:</p>' +
        '<span class="eq">' + n(E.c, 3) + ' ÷ ' + n(E.eq, 2) + ' = <b class="kk">' +
        n(E.k, 3) + ' → ' + n(E.k*100, 1) + ' %</b></span>' +
        '<p style="margin-top:7px">Esta unidad es, ella sola, el ' + n(E.k*100, 1) + ' % de todo el ' +
        'tema. Las cifras de la columna suman 100 % entre las ' + E.nt + ' unidades que lo tocan.' +
        '</p></div></div>' +
    '</div>');



    h.push('<h3>Las dos fórmulas</h3>');
    h.push('<p>Todo parte de una matriz de afinidad <code>w[u,t]</code>: cuánta evidencia hay de que ' +
           'la unidad <i>u</i> trata del tema <i>t</i>. Se construye mezclando la masa de confianza ' +
           'de los temas que el LLM extrajo (70 %) con la similitud coseno entre la unidad y el ' +
           'centroide del tema (30 %).</p>');
    h.push('<div class="formula-box c"><p class="q">Cuánto de la unidad es este tema &nbsp;=&nbsp</p>' +
           '<code>C[u,t] = w[u,t] ÷ Σ<sub>temas</sub> w[u,·]</code>' +
           '<p class="x">«Sé que estoy mirando este proyecto: ¿qué probabilidad hay de que hable de ' +
           'este tema?» Suma 100 % en cada unidad.</p>' +
           '<ul class="terms">' +
             '<li><code>u, t</code> — una unidad fija (este proyecto) y un tema fijo.</li>' +
             '<li><code>w[u,t]</code> — la afinidad cruda de esa celda: ' + n(E.aff, 4) + ' en el ejemplo.</li>' +
             '<li><code>Σ<sub>temas</sub> w[u,·]</code> — se deja <code>u</code> fijo y se suma ' +
               '<code>w</code> sobre <b>todos los temas</b>: el total de la fila del proyecto, ' + n(E.rowsum, 4) + '.</li>' +
             '<li><code>C[u,t]</code> — el cociente: ' + n(E.aff, 4) + ' ÷ ' + n(E.rowsum, 4) + ' = ' +
               n(E.c, 4) + '. Al sumar sobre temas en el denominador, todas las <code>C</code> de un ' +
               'mismo proyecto suman 100 %.</li>' +
           '</ul></div>');
    h.push('<div class="formula-box k"><p class="q">Cuánto del tema aporta la unidad &nbsp;=&nbsp</p>' +
           '<code>K[u,t] = C[u,t] ÷ E[t]</code>' +
           '<p class="x">«Sé que estoy mirando este tema: ¿qué probabilidad hay de que venga de este ' +
           'proyecto?» Suma 100 % en cada tema.</p>' +
           '<ul class="terms">' +
             '<li><code>C[u,t]</code> — la misma cifra de la fórmula anterior: ' + n(E.c, 4) + '.</li>' +
             '<li><code>E[t]</code> — se deja <code>t</code> fijo y se suma <code>C</code> sobre ' +
               '<b>todas las unidades</b>: el total de la columna del tema, ' + n(E.eq, 2) +
               ' unidades-equivalentes.</li>' +
             '<li><code>K[u,t]</code> — el cociente: ' + n(E.c, 4) + ' ÷ ' + n(E.eq, 2) + ' = ' +
               n(E.k, 4) + '. Al sumar sobre unidades en el denominador, todas las <code>K</code> de ' +
               'un mismo tema suman 100 %.</li>' +
           '</ul></div>');
   h.push('<p><b>Unidades efectivas</b> de un tema = 1 ÷ Σ K², y <b>temas efectivos</b> de una unidad ' +
           '= 1 ÷ Σ C². Si diez proyectos aportan un 10 % cada uno, salen 10 efectivos; si uno aporta ' +
           'el 90 % y nueve el 1,1 %, sale 1,2.</p>');

 

    h.push('<h3>De dónde salen los nombres y descripciones de los temas</h3>');
    h.push('<p>Los escribe el LLM en la etapa 03, a partir de los temas extraídos que el ' +
           'agrupamiento ya reunió en cada grupo, y no provienen de ningún documento de origen, ' +
           'sino que son una síntesis de los temas miembros, no una cita. El LLM se limita a ' +
           'nombrar el grupo, no decide quién entra en él, eso ya lo resolvió la similitud ' +
           'coseno. Cómo sale cada dato de origen, cuántas filas se descartaron y con qué texto ' +
           'quedó cada unidad se explica en la pestaña <b>Datos de origen</b>.</p>');

    h.push('<h3>Modelos</h3>');
    var judge = PF.order.map(function(d){ return DATA[d].ceplan && DATA[d].ceplan.judge; })
      .filter(Boolean)[0];
    h.push('<p>' + PF.extraction_html + ' Los embeddings salen de <code>cohere.embed-multilingual-v3</code> en ' +
           'Amazon Bedrock, con 1024 dimensiones, troceando y promediando los textos de más de ' +
           '2048 caracteres, y los vectores quedan guardados en PostgreSQL con pgvector.' +
           (judge ? ' El cruce con ' + PL.cross + ' usa <code>' + esc(judge) + '</code>, también en Bedrock.' : '') +
           '</p>');

    // Idioma (lb_lang): cuantas unidades en ingles hay en cada universo cargado.
    var nen = Object.keys(META).map(function(d){
      var m = META[d];
      return m.langs && m.langs.en ? m.langs.en.toLocaleString('es') + ' de ' +
        m.units.toLocaleString('es') + ' ' + plural(DATA[d].noun) : null;
    }).filter(Boolean);
    h.push('<h3>Idioma</h3>');
    h.push('<p>Cada unidad se analiza en el idioma en que fue escrita' +
           (nen.length ? ' (en este atlas están en inglés ' + nen.join(' y ') + ')' : '') + '. Un texto ' +
           'en inglés puntúa algo más bajo contra uno en español que otro en español con el mismo ' +
           'contenido, y ' + PL.cross + ' están en español; para compensarlo, cada una se compara también ' +
           'con su traducción al inglés. Aun así, las unidades en inglés se conectan menos con el plan. ' +
           'Se probó comparar además cada unidad por su traducción al español: la similitud sube, pero en ' +
           'una revisión a mano los vínculos que agregaba eran claramente menos precisos que los que ' +
           'reemplazaba, así que se descartó. La diferencia que queda es sobre todo de contenido: las ' +
           'publicaciones en inglés son más a menudo de ciencia básica.</p>');
    box.innerHTML = h.join('');
  }

  function renderProvenance(){
    var box = document.getElementById('provenance');
    if (box.dataset.done) return;
    box.dataset.done = '1';
    var h = [];
    h.push('<h2>De dónde vienen los datos</h2>');
    h.push('<p>' + PF.provenance_intro + '</p>');

    Object.keys(META).forEach(function(d){
      var m = META[d];
      var prov = m.prov || {steps: [], why: ''};
      h.push('<h3>' + NAMES[d] + '</h3>');

      h.push('<div class="flow">');
      prov.steps.forEach(function(s, i){
        h.push('<div class="step"><span class="n">' + (i + 1) + ' de ' + prov.steps.length +
               '</span><span class="t">' + s.n.toLocaleString('es') + '</span>' +
               '<span class="d"><b>' + s.label + '</b><br>' + s.note + '</span></div>');
      });
      h.push('</div>');
      if (prov.why) h.push('<p class="note" style="margin:9px 2px 16px">' + prov.why + '</p>');

      h.push('<div class="chips">' + [
        ['Caracteres por unidad, mediana', m.chars.p50],
        ['media', Math.round(m.chars.mean)],
        ['p95', m.chars.p95],
        ['máximo', m.chars.max],
      ].map(function(c){
        return '<span class="chip">' + c[0] + ' <b>' + c[1].toLocaleString('es') + '</b></span>';
      }).join('') + '</div>');
      if (m.langs){
        var LN = {es: 'en español', en: 'en inglés', mixto: 'mezclan español e inglés', '?': 'sin idioma claro'};
        h.push('<p class="note" style="margin:9px 2px 0">Idioma: ' + Object.keys(m.langs)
          .sort(function(a, b){ return m.langs[b] - m.langs[a]; })
          .map(function(k){ return m.langs[k].toLocaleString('es') + ' ' + (LN[k] || k); }).join(', ') +
          '. Cada una se analiza en su idioma original (ver Metodología).</p>');
      }

      // Tabla de llenado por columna: todas las que entran al texto embebido.
      // Las que no estan en todas las unidades (p.ej. keywords de las
      // publicaciones) tambien aportan cuando existen, y se marcan como tales.
      // Las de respaldo (aux) solo completan otra columna y no se muestran;
      // journal tampoco se muestra.
      var cols = m.cols.filter(function(c){ return !c.aux && c.n !== 'journal'; });
      h.push('<div class="exp" style="margin-top:14px"><div class="exp-head">' +
             '<span class="nm">Qué columnas dan ese texto</span>' +
             '<span class="fl">' + m.src + ', ' + m.rows.toLocaleString('es') +
             ' filas de origen pasan el filtro, ' + m.units.toLocaleString('es') + ' unidades' +
             (m.dropped ? ', ' + m.dropped.toLocaleString('es') +
               ' descartadas por no tener ' + m.req.join(' ni ') : '') +
             '</span></div><table class="fills"><tbody>');
      cols.forEach(function(c){
        h.push('<tr><td class="cn">' + c.n +
               (c.f < 1 ? '<span class="opt">si existe</span>' : '') + '</td>' +
               '<td class="bar-td"><div class="track"><i style="width:' +
               Math.max(1.5, c.f * 100).toFixed(1) + '%;background:var(--contain)"></i></div></td>' +
               '<td class="pc">' + (c.f * 100).toFixed(1) + ' %  ·  ' +
               c.r.toLocaleString('es') + '</td></tr>');
      });
      h.push('</tbody></table></div>');
    });
    box.innerHTML = h.join('');
  }

  function renderMetrics(){
    var D = DATA[dom], V = view(dom), act = yrActive();
    var items = [
      ['Unidades', V.nu.toLocaleString('es'),
       act ? 'de ' + D.nu.toLocaleString('es') + ' · años ' + yrText() :
             plural(D.noun) + (fem(D.noun) ? ' analizadas' : ' analizados')],
      ['Temas', V.nt, act ? 'con presencia en el rango' : 'espacio propio de este universo'],
    ];
    var dl = document.getElementById('metrics'); dl.textContent='';
    items.forEach(function(it){
      var w = el('div','metric');
      w.appendChild(el('dt',null,it[0]));
      var dd = el('dd',null,it[1]);
      dd.appendChild(el('span','note',it[2]));
      w.appendChild(dd); dl.appendChild(w);
    });
    document.getElementById('prov').textContent =
      'Corrida ' + D.run + ' · ' + D.label + ' · extracción con ' + PF.extraction_footer + ' ' +
      'y embeddings cohere.embed-multilingual-v3 (Amazon Bedrock).';
  }

  function renderList(){
    var D = DATA[dom], V = view(dom), list = document.getElementById('list');
    list.textContent='';
    function byEq(a, b){ return V.eq[b] - V.eq[a]; }
    function present(id){ return V.n[id] > 0; }
    var q = fold(query.trim());   // sin tildes, igual que el buscador global
    var rows;
    if (mode === 'unit' || (q && q.length >= 2)) {
      // con busqueda se mezclan temas y unidades, priorizando temas
      var t = Object.keys(D.topics).filter(function(id){
        return present(id) && (!q || fold(D.topics[id].l).indexOf(q) >= 0); })
        .sort(byEq)
        .map(function(id){ return {kind:'t', id:id}; });
      var u = !q ? [] : Object.keys(D.units).filter(function(id){
        return inYears(dom, id) && fold(D.units[id].t).indexOf(q) >= 0; })
        .slice(0,120).map(function(id){ return {kind:'u', id:id}; });
      rows = t.concat(u);
    } else {
      rows = Object.keys(D.topics).filter(present).sort(byEq)
        .map(function(id){ return {kind:'t', id:id}; });
    }
    var maxEq = 1;
    Object.keys(D.topics).forEach(function(id){ maxEq = Math.max(maxEq, V.eq[id]); });

    document.getElementById('listCount').textContent =
      rows.length + (q ? ' resultados' : ' temas');

    rows.forEach(function(r){
      var b = el('button','row'); b.type='button';
      b.setAttribute('aria-current', (sel && sel.kind===r.kind && sel.id===r.id) ? 'true':'false');
      if (r.kind === 't'){
        var t = D.topics[r.id];
        b.appendChild(el('span','name', t.l));
        var m = el('div','meta');
        var tr = el('div','track'); tr.style.setProperty('--bar','var(--contain)');
        var i = el('i'); i.style.width = Math.max(2,(V.eq[r.id]/maxEq*100)) + '%'; tr.appendChild(i);
        m.appendChild(tr);
        m.appendChild(el('span','val', V.eq[r.id].toFixed(1) + ' eq · ' + V.n[r.id] + ' ' + D.noun.slice(0,3) + '.'));
        b.appendChild(m);
      } else {
        var u = D.units[r.id];
        b.appendChild(el('span','name', u.t));
        var m2 = el('div','meta');
        m2.appendChild(el('span','val', (u.eff!=null? u.eff.toFixed(2)+' temas efectivos' : '') +
          (u.g ? ' · ' + u.g : '')));
        b.appendChild(m2);
      }
      b.addEventListener('click', function(){ sel = r; renderList(); renderDetail();
        document.getElementById('detail').scrollIntoView({block:'nearest'}); });
      list.appendChild(b);
    });
  }

  function barCell(cls, value, scale){
    var td = el('td', cls);
    var w = el('div','bar');
    var tr = el('div','track'); var i = el('i');
    i.style.width = Math.max(1.5, Math.min(100, value/scale*100)) + '%';
    tr.appendChild(i); w.appendChild(tr);
    w.appendChild(el('span','val', pct(value, value < 0.01 ? 2 : 1)));
    td.appendChild(w); return td;
  }

  function renderDetail(){
    var D = DATA[dom], I = build(dom), V = view(dom), box = document.getElementById('detail');
    box.textContent = '';
    if (!sel){
      box.appendChild(el('h3',null,'Elige un tema'));
      box.appendChild(el('p','desc','La lista de la izquierda ordena los ' + V.nt +
        ' temas por tamaño real (unidades-equivalentes). También puedes buscar ' +
        (fem(D.noun) ? 'una ' : 'un ') + D.noun + (fem(D.noun) ? ' concreta' : ' concreto') +
        ' por su título para ver cómo se reparte entre temas.'));
      return;
    }
    if (sel.kind === 't'){
      var t = D.topics[sel.id], all = V.byTopic[sel.id] || [], rows = all.slice(0, 40);
      yrBanner(box, dom, V.nu, D.nu);
      box.appendChild(el('h3', null, t.l));
      if (t.d) box.appendChild(el('p','desc', t.d));
      var chips = el('div','chips');
      [['Del corpus', pct(yrActive() ? (V.nu ? V.eq[sel.id] / V.nu : 0) : t.sh)],
       [cap(plural(D.noun)) + ' que lo tocan', V.n[sel.id]],
       ['Temas extraídos que lo componen', t.v]
      ].forEach(function(c){
        var s = el('span','chip'); s.appendChild(document.createTextNode(c[0]+' '));
        var bEl = el('b',null,String(c[1])); s.appendChild(bEl); chips.appendChild(s);
      });
      box.appendChild(chips);

      var maxK = rows.length ? rows[0].k : 1;
      var wrap = el('div','tablewrap'), tbl = el('table');
      tbl.innerHTML = '<thead><tr>' +
        '<th>' + esc(D.noun.charAt(0).toUpperCase()+D.noun.slice(1)) + '</th>' +
        '<th class="k">Cuánto del tema aporta la unidad<span class="hint">barra a escala del mayor valor de la tabla</span></th>' +
        '<th class="c">Cuánto de la unidad es este tema<span class="hint">barra sobre 100 %</span></th>' +
        '</tr></thead>';
      var tb = el('tbody');
      rows.forEach(function(r){
        var u = D.units[r.u] || {t:r.u};
        var tr = el('tr');
        var td = el('td');
        var link = el('button','linkish', u.t || r.u); link.type='button';
        link.addEventListener('click', function(){ sel={kind:'u',id:r.u}; renderList(); renderDetail(); });
        td.appendChild(link);
        var meta = [u.y||'', u.g||''].filter(Boolean).join(' · ');
        if (meta) td.appendChild(el('span','unit-meta', meta));
        tr.appendChild(td);
        tr.appendChild(barCell('k', r.k, maxK));
        tr.appendChild(barCell('c', r.c, 1));
        tb.appendChild(tr);
      });
      tbl.appendChild(tb); wrap.appendChild(tbl); box.appendChild(wrap);
      if (!all.length)
        box.appendChild(el('p','note',ningun(D.noun) + ' de este tema cae en los años elegidos.'));
      if (all.length > 40)
        box.appendChild(el('p','note','Se muestran las 40 unidades que más aportan, de ' +
          all.length + '.'));
      box.appendChild(el('p','note','Las dos columnas responden preguntas distintas y rara vez coinciden: ' +
        'la unidad que más aporta al tema no es siempre la que más se dedica a él.'));
    } else {
      var u2 = D.units[sel.id], rws = (I.byUnit[sel.id]||[]);
      // Con un rango activo, el aporte se mide contra el tamaño del tema dentro
      // del rango, igual que en la tabla de cada tema; si no, ambas vistas
      // darían cifras distintas para la misma celda.
      var inRange = inYears(dom, sel.id);
      if (yrActive() && inRange){
        rws = rws.map(function(r){ return {t: r.t, c: r.c, k: V.eq[r.t] ? r.c / V.eq[r.t] : 0}; });
      }
      var back = el('div','back');
      var bb = el('button','linkish','← volver a los temas'); bb.type='button';
      bb.addEventListener('click', function(){ sel=null; query=''; document.getElementById('q').value='';
        renderList(); renderDetail(); });
      back.appendChild(bb); box.appendChild(back);
      if (yrActive()){
        if (inRange) yrBanner(box, dom, V.nu, D.nu);
        else box.appendChild(el('p', 'yr-banner', cap(D.noun) + ' fuera de los años elegidos (' + yrText() +
          '): el aporte se muestra sobre todo el corpus.'));
      }
      box.appendChild(el('h3', null, u2 ? u2.t : sel.id));
      var meta2 = [u2 && u2.y, u2 && u2.g].filter(Boolean).join(' · ');
      if (meta2) box.appendChild(el('p','desc', meta2));
      var ch = el('div','chips');
      [['Temas con presencia', rws.length],
       ['Temas efectivos', (u2 && u2.eff!=null) ? u2.eff.toFixed(2) : '—'],
       ['Identificador', sel.id]
      ].forEach(function(c){ var s=el('span','chip'); s.appendChild(document.createTextNode(c[0]+' '));
        s.appendChild(el('b',null,String(c[1]))); ch.appendChild(s); });
      box.appendChild(ch);

      var maxK2 = rws.reduce(function(m,r){ return Math.max(m, r.k); }, 0.0001);
      var wr = el('div','tablewrap'), tb2 = el('table');
      tb2.innerHTML = '<thead><tr><th>Tema</th>' +
        '<th class="c">Cuánto de la unidad es este tema<span class="hint">barra sobre 100 %</span></th>' +
        '<th class="k">Cuánto del tema aporta la unidad<span class="hint">barra a escala del mayor valor de la tabla</span></th>' +
        '</tr></thead>';
      var body2 = el('tbody');
      rws.forEach(function(r){
        var tp = D.topics[r.t] || {l:r.t};
        var tr = el('tr'), td = el('td');
        var lk = el('button','linkish', tp.l); lk.type='button';
        lk.addEventListener('click', function(){ sel={kind:'t',id:r.t}; renderList(); renderDetail(); });
        td.appendChild(lk); tr.appendChild(td);
        tr.appendChild(barCell('c', r.c, 1));
        tr.appendChild(barCell('k', r.k, maxK2));
        body2.appendChild(tr);
      });
      tb2.appendChild(body2); wr.appendChild(tb2); box.appendChild(wr);
      box.appendChild(el('p','note','La columna verde suma 100 % en esta unidad: es cómo se reparte su ' +
        'contenido. La naranja no suma nada en particular aquí, porque compara esta unidad con ' +
        'todas las demás dentro de cada tema.'));
      renderUnitCeplan(box, dom, sel.id);
    }
  }

  // Vocabulario del plan elegido (atlas_profiles.PLANS + lb_plans.Plan): ver
  // applyPlan().
  function renderUnitCeplan(box, d, uid){
    var C = DATA[d].ceplan;
    if (!C) return;
    var h = el('h3', null, PLAN_TITLE);
    h.style.cssText = 'font-size:18px;margin:26px 0 6px';
    box.appendChild(h);
    var links = C.units[uid];
    if (!links){
      box.appendChild(el('p', 'desc', STATUS_TXT[C.status[uid]] || 'Sin cruce con ' + PL.short + ' para esta unidad.'));
      return;
    }
    if (yrActive() && inYears(d, uid)){
      // mismo criterio que la tabla de temas: aporte dentro del rango
      var CVs = cview(d).subs;
      links = links.map(function(r){
        var s = CVs[r[0]]; return [r[0], r[1], r[2], s && s.eq ? r[2] / s.eq : 0]; });
    }
    var shown = links.slice(0, C.top);
    var maxK = shown.reduce(function(m, r){ return Math.max(m, r[3]); }, 0.0001);
    var wr = el('div', 'tablewrap'), tb = el('table');
    tb.innerHTML = '<thead><tr><th>' + cap(LEAF) + '</th><th>Relación</th>' +
      '<th class="c">Cuánto de la unidad es esta ' + LEAF + '<span class="hint">barra sobre 100 %</span></th>' +
      '<th class="k">Cuánto de la ' + LEAF + ' aporta<span class="hint">barra a escala del mayor valor de la tabla</span></th>' +
      '</tr></thead>';
    var body = el('tbody');
    shown.forEach(function(r){
      var s = C.subs[r[0]], tr = el('tr'), td = el('td');
      var lk = el('button', 'linkish', s.l); lk.type = 'button';
      lk.addEventListener('click', function(){ gotoSub(d, r[0]); });
      td.appendChild(lk);
      td.appendChild(el('span', 'unit-meta', [s.o, s.t].filter(Boolean).join(' · ')));
      tr.appendChild(td);
      var tdg = el('td'); tdg.appendChild(el('span', 'pill g' + r[1], r[1] === 2 ? 'clara' : 'tangencial'));
      tr.appendChild(tdg);
      tr.appendChild(barCell('c', r[2], 1));
      tr.appendChild(barCell('k', r[3], maxK));
      body.appendChild(tr);
    });
    tb.appendChild(body); wr.appendChild(tb); box.appendChild(wr);
    var extra = links.length > C.top ? ' Esta unidad tiene ' + links.length + ' vínculos confirmados; ' +
      'se listan los ' + C.top + ' con mayor peso, pero la barra verde reparte el 100 % entre todos.' : '';
    box.appendChild(el('p', 'note', 'Relación «clara» o «tangencial» según el verificador (' + C.model +
      '), sobre candidatas propuestas por similitud de embeddings.' + extra));
  }

  var ceplanDom = PF.order[0], ceplanOpen = null, ceplanOnlyGaps = false;
  var COV = {desarrollada: ['dev', 'Desarrollada'], debil: ['weak', 'Débil'], sin_desarrollo: ['none', 'Sin desarrollo']};

  // Pestañas: summary (Resumen), ceplan (Retos), topics (Temas), about. Un
  // dominio en lugar de una pestaña abre Temas en ese universo.
  var section = 'summary';
  function showSection(which){
    if (DATA[which]) which = 'topics';
    section = which;
    document.querySelectorAll('#domains button').forEach(function(o){
      o.setAttribute('aria-pressed', String(o.dataset.sec === which));
    });
    ['summary', 'topics', 'ceplan', 'map', 'about'].forEach(function(id){
      document.getElementById(id).hidden = id !== which;
    });
    if (which === 'topics') paintTopicDom();
    CH.hideTip();
  }
  function openSection(which){
    showSection(which);
    if (which === 'summary') renderSummary();
    else if (which === 'ceplan') renderCeplan();
    else if (which === 'map') renderMap();
    else if (which === 'about'){ renderMethod(); renderProvenance(); }
    else { renderMetrics(); renderList(); renderDetail(); }
  }
  // Universo dentro de Temas.
  function paintTopicDom(){
    var box = document.getElementById('topic-dom');
    box.textContent = '';
    box.hidden = PF.order.length < 2;
    PF.order.forEach(function(d){
      var b = el('button', null, NAMES[d] || d); b.type = 'button';
      b.setAttribute('aria-pressed', String(d === dom));
      b.addEventListener('click', function(){
        if (d === dom) return;
        dom = d; sel = null; query = ''; document.getElementById('q').value = '';
        paintTopicDom(); renderMetrics(); renderList(); renderDetail();
      });
      box.appendChild(b);
    });
  }

  function gotoUnit(d, uid){
    dom = d; sel = {kind: 'u', id: uid}; query = '';
    document.getElementById('q').value = '';
    showSection(d);
    renderMetrics(); renderList(); renderDetail();
    document.getElementById('detail').scrollIntoView({block: 'start'});
  }

  function gotoSub(d, sid){
    ceplanDom = d; ceplanOpen = sid; ceplanOnlyGaps = false;
    showSection('ceplan');
    renderCeplan();
    var target = document.getElementById('sub-' + sid);
    if (target) target.scrollIntoView({block: 'center'});
  }

  // --- Resumen ------------------------------------------------------------------
  // La portada: cuatro graficos que responden, para el universo y el plan
  // elegidos, «¿que retos cubre la universidad y cuales no?», «¿desde que
  // temas?», «¿desde cuando?» y «¿como se ve contra los otros planes?».
  var sumDom = PF.order[0], sumToken = 0;

  // Rotulo corto de un nivel 1: «ON1 · Alcanzar el pleno desarrollo…», o el
  // nombre tal cual si ya es corto («Eje Social»).
  function l1Short(C, key){
    var lab = C.on[key] || key;
    if (lab === key) return lab;
    return key + ' · ' + CH.clip(lab.replace(/^\s*[A-Za-z]+\s*\d+\s*[.:-]?\s*/, ''), 46);
  }
  function eqText(d, v){
    return v.toLocaleString('es', {maximumFractionDigits: 1}) + ' ' + plural(DATA[d].noun) + '-equivalentes';
  }
  function slug(s){ return String(s).replace(/[^\w-]+/g, '-'); }
  // Reparto de una unidad entre los niveles 1 del plan (suma 1 si esta alineada).
  function l1Shares(C, uid){
    var sh = {};
    (C.units[uid] || []).forEach(function(r){
      var s = C.subs[r[0]]; if (s) sh[s.o] = (sh[s.o] || 0) + r[2];
    });
    return sh;
  }
  function card(box, title, desc){
    var c = el('section', 'card');
    c.appendChild(el('h3', null, title));
    if (desc) c.appendChild(el('p', 'desc', desc));
    box.appendChild(c);
    return c;
  }
  function gotoOn(d, on){
    ceplanDom = d; ceplanOpen = null; ceplanOnlyGaps = false;
    showSection('ceplan'); renderCeplan();
    var t = document.getElementById('on-' + slug(on));
    if (t) t.scrollIntoView({block: 'start'});
  }

  function renderSummary(){
    var box = document.getElementById('summary');
    box.textContent = ''; CH.hideTip();
    var token = ++sumToken;
    var d = sumDom, D = DATA[d], C = D.ceplan, V = view(d), act = yrActive();

    if (PF.order.length > 1){
      var seg = el('div', 'seg'); seg.setAttribute('role', 'group'); seg.setAttribute('aria-label', 'Universo');
      PF.order.forEach(function(x){
        var b = el('button', null, NAMES[x] || x); b.type = 'button';
        b.setAttribute('aria-pressed', String(x === d));
        b.addEventListener('click', function(){ if (x !== sumDom){ sumDom = x; renderSummary(); } });
        seg.appendChild(b);
      });
      box.appendChild(seg);
    }
    yrBanner(box, d, V.nu, D.nu);

    // cifras de cabecera
    var CV = C ? cview(d) : null, ids = C ? Object.keys(C.subs) : [];
    var cnt = {desarrollada: 0, debil: 0, sin_desarrollo: 0};
    ids.forEach(function(k){ cnt[CV.subs[k].cov]++; });
    var tiles = [[cap(plural(D.noun)), V.nu.toLocaleString('es'),
                  act ? 'de ' + D.nu.toLocaleString('es') + ' · años ' + yrText() : 'en el análisis'],
                 ['Temas', V.nt.toLocaleString('es'), 'propios de este universo']];
    if (C){
      tiles.push(['Alineados con ' + PL.short, pct(CV.nu ? CV.aligned / CV.nu : 0, 0),
                  CV.aligned.toLocaleString('es') + ' de ' + CV.nu.toLocaleString('es') +
                  ' con al menos una ' + LEAF + ' confirmada']);
      tiles.push([cap(LEAVES) + ' desarrolladas', cnt.desarrollada + ' de ' + ids.length,
                  cnt.debil + ' débiles · ' + cnt.sin_desarrollo + ' sin desarrollo']);
    }
    var dl = el('dl', 'metrics kpis');
    tiles.forEach(function(t){
      var w = el('div', 'metric');
      w.appendChild(el('dt', null, t[0]));
      var dd = el('dd', null, t[1]); dd.appendChild(el('span', 'note', t[2]));
      w.appendChild(dd); dl.appendChild(w);
    });
    box.appendChild(dl);

    if (!C){
      box.appendChild(el('p', 'note', 'Todavía no hay un cruce de ' + plural(D.noun) + ' con ' + PL.short +
        ' (scripts/analysis/ceplan_units.py --plan ' + PL.key + '). Elige otro plan en «Retos», arriba.'));
      renderCompare(box, d, token);
      return;
    }
    var onKeys = Object.keys(C.on).sort();

    // 1. mapa de cobertura
    var c1 = card(box, 'Qué ' + LEAVES + ' del ' + PL.name + ' cubren los ' + plural(D.noun),
      'Cada cuadro es una ' + LEAF + '. Oscuro: la desarrollan con claridad al menos ' + C.minG2 + ' ' +
      plural(D.noun) + '; claro: menos; hueco: ninguna relación clara. Pasa el puntero para ver el detalle ' +
      'y haz clic para abrir la ' + LEAF + ' en «Retos».');
    var groups = onKeys.map(function(on){
      return {key: on, label: C.on[on], cells: ids.filter(function(k){ return C.subs[k].o === on; })
        .map(function(k){
          var s = C.subs[k], sv = CV.subs[k];
          return {id: k, label: s.l, cov: sv.cov, eq: sv.eq,
                  lines: [sv.n2 + ' con relación clara · ' + (sv.n - sv.n2) + ' tangenciales', eqText(d, sv.eq)]};
        })};
    });
    CH.coverageGrid(c1, groups, {covText: {desarrollada: 'Desarrollada', debil: 'Débil',
                                           sin_desarrollo: 'Sin desarrollo'},
                                 onClick: function(k){ gotoSub(d, k); }});
    CH.tableView(c1, [PL.level1_long, cap(LEAF), 'Estado', 'Relación clara', 'Tangencial', 'Equivalentes'],
      groups.reduce(function(acc, g){
        return acc.concat(g.cells.map(function(c){
          var sv = CV.subs[c.id];
          return [l1Short(C, g.key), c.label, COV[c.cov][1], sv.n2, sv.n - sv.n2, sv.eq.toFixed(1)];
        }));
      }, []), [0, 0, 0, 1, 1, 1]);

    // 2. de los temas a los objetivos
    var I = build(d), flow = {}, units = 0;
    Object.keys(C.units).forEach(function(u){
      if (!inYears(d, u)) return;
      var sh = l1Shares(C, u), byT = I.byUnit[u] || [];
      if (byT.length) units++;
      byT.forEach(function(c){
        Object.keys(sh).forEach(function(o){
          (flow[c.t] = flow[c.t] || {})[o] = (flow[c.t][o] || 0) + c.c * sh[o];
        });
      });
    });
    var tTot = Object.keys(flow).map(function(t){
      return [t, Object.keys(flow[t]).reduce(function(a, o){ return a + flow[t][o]; }, 0)]; })
      .sort(function(a, b){ return b[1] - a[1]; });
    // Solo los temas que mas aportan: un nodo «otros» con el resto se comia
    // casi todo el alto y dejaba a los temas mostrados en hilos.
    var TOP = 12, top = tTot.slice(0, TOP), rest = tTot.slice(TOP);
    var flows = [], OTHER = '__otros__';
    top.forEach(function(x){
      Object.keys(flow[x[0]]).forEach(function(o){ flows.push({s: x[0], t: o, v: flow[x[0]][o]}); }); });
    var all = tTot.reduce(function(a, x){ return a + x[1]; }, 0) || 1;
    var shownShare = top.reduce(function(a, x){ return a + x[1]; }, 0) / all;
    if (flows.length){
      var c2 = card(box, 'De los temas a los ' + PL.level1_plural,
        'Los ' + top.length + ' temas que más aportan a ' + PL.cross + ' (juntos, el ' + pct(shownShare, 0) +
        ' del aporte de los ' + tTot.length + ' temas), y hacia dónde va ese aporte. El grosor es ' +
        'cuánto de los ' + plural(D.noun) + ' es ese tema y, a la vez, ese ' + PL.level1_long.toLowerCase() +
        ' (la proporción del tema en cada unidad por la de su alineación con el plan). Clic en un tema ' +
        'para abrirlo; en un ' + PL.level1_long.toLowerCase() + ', para verlo en «Retos».');
      var left = top.map(function(x){ return {id: x[0], label: (D.topics[x[0]] || {}).l || x[0], value: x[1]}; });
      var right = onKeys.map(function(o){
        return {id: o, label: l1Short(C, o), note: C.on[o],
                value: flows.reduce(function(a, f){ return a + (f.t === o ? f.v : 0); }, 0)}; })
        .filter(function(r){ return r.value > 0; });
      CH.sankey(c2, {left: left, right: right, flows: flows,
        fmt: function(v){ return eqText(d, v); },
        aria: 'Flujo de los temas a los ' + PL.level1_plural + ' del ' + PL.name,
        onLeft: function(id){ if (id !== OTHER) gotoTopic(d, id); },
        onRight: function(id){ gotoOn(d, id); }});
      // La tabla trae todos los temas, no solo los del grafico.
      var allFlows = [];
      tTot.forEach(function(x){
        Object.keys(flow[x[0]]).forEach(function(o){ allFlows.push({s: x[0], t: o, v: flow[x[0]][o]}); }); });
      CH.tableView(c2, ['Tema', PL.level1_long, 'Equivalentes'],
        allFlows.sort(function(a, b){ return b.v - a.v; }).map(function(f){
          return [(D.topics[f.s] || {}).l || f.s, l1Short(C, f.t), f.v.toFixed(2)];
        }), [0, 0, 1]);
    }

    // 3. evolucion por año
    var per = {}, years = [], noYear = 0;
    Object.keys(C.units).forEach(function(u){
      if (!inYears(d, u)) return;
      var y = (D.units[u] || {}).y;
      if (!y){ noYear++; return; }
      years.push(y);
      var sh = l1Shares(C, u);
      Object.keys(sh).forEach(function(o){ (per[o] = per[o] || {})[y] = (per[o][y] || 0) + sh[o]; });
    });
    if (years.length){
      var lo = Math.min.apply(null, years), hi = Math.max.apply(null, years);
      if (hi > lo){
        var c3 = card(box, 'Por año, en cada ' + PL.level1_long.toLowerCase(),
          'Cuántos ' + plural(D.noun) + '-equivalentes aporta cada año a cada ' + PL.level1_long.toLowerCase() +
          ': cada unidad reparte 1 entre sus ' + LEAVES + '. Misma escala en todos los paneles.' +
          (noYear ? ' ' + noYear + ' ' + plural(D.noun) + ' sin año no entran.' : ''));
        CH.smallMultiples(c3, {years: [lo, hi], fmt: function(v){ return eqText(d, v); },
          panels: onKeys.map(function(o){ return {id: o, label: l1Short(C, o), values: per[o] || {}}; }),
          onPanel: function(o){ gotoOn(d, o); }});
        var yrs = []; for (var y = lo; y <= hi; y++) yrs.push(y);
        CH.tableView(c3, ['Año'].concat(onKeys.map(function(o){ return l1Short(C, o); })),
          yrs.map(function(y){
            return [String(y)].concat(onKeys.map(function(o){ return ((per[o] || {})[y] || 0).toFixed(1); }));
          }), [0].concat(onKeys.map(function(){ return 1; })));
      }
    }

    // 4. comparar planes
    renderCompare(box, d, token);
  }

  // Todos los planes de este dataset contra el mismo universo y años. Carga
  // los planes que falten; si mientras tanto se volvio a pintar, no hace nada.
  function renderCompare(box, d, token){
    if (PF.plan_order.length < 2) return;
    var D = DATA[d];
    var c = card(box, 'Comparar retos',
      'El mismo universo contra cada plan: qué parte de los ' + plural(D.noun) + ' tiene al menos una ' +
      'relación confirmada con el plan. Clic en un plan para elegirlo.');
    var wait = el('p', 'note', 'Cargando los otros planes…'); c.appendChild(wait);
    Promise.all(PF.plan_order.map(function(k){
      return loadPlan(B, k).then(function(){ return true; }, function(){ return false; });
    })).then(function(){
      if (token !== sumToken) return;
      wait.remove();
      var rows = [], tableRows = [], alignedAny = {}, nu = 0, crossed = 0;
      PF.plan_order.forEach(function(k){
        var Ck = (B.plans[k] || {})[d], P = PF.plans[k];
        if (!Ck){
          rows.push({id: k, label: P.name, sub: 'sin cruce para este universo todavía', value: 0, text: '—',
                     current: k === planKey});
          tableRows.push([P.name, '—', '—']);
          return;
        }
        crossed++;
        var CVk = cview(d, Ck, k), ids = Object.keys(Ck.subs);
        var dev = ids.filter(function(s){ return CVk.subs[s].cov === 'desarrollada'; }).length;
        nu = CVk.nu;
        Object.keys(Ck.units).forEach(function(u){ if (inYears(d, u)) alignedAny[u] = 1; });
        var share = CVk.nu ? CVk.aligned / CVk.nu : 0;
        rows.push({id: k, label: P.name, value: share, text: pct(share, 0), current: k === planKey,
                   sub: dev + ' de ' + ids.length + ' ' + P.leaves + ' desarrolladas' +
                        (P.validated ? '' : ' · sin revisión manual'),
                   onClick: k === planKey ? null : function(){ choosePlan(B, k); }});
        tableRows.push([P.name, pct(share, 1), dev + ' de ' + ids.length]);
      });
      CH.meterList(c, rows);
      if (crossed > 1){
        var none = nu - Object.keys(alignedAny).length;
        c.appendChild(el('p', 'note', none.toLocaleString('es') + ' ' + plural(D.noun) +
          ' no tienen relación confirmada con ninguno de estos planes.'));
      }
      CH.tableView(c, ['Plan', '% alineado', cap('hojas desarrolladas')], tableRows, [0, 1, 1]);
    });
  }

  // Perfil de cada agrupacion (departamento, linea de investigacion) entre los
  // niveles 1 del plan: cada fila suma 100 %. Solo proyectos: en publicaciones
  // la agrupacion es la revista, que no dice nada de quien investiga.
  function renderGroupHeat(box, d){
    var D = DATA[d], C = D.ceplan;
    if (D.kind !== 'projects') return;
    var groupName = (PF.domains[d] || {}).group || 'Agrupación';
    var acc = {}, n = {};
    Object.keys(C.units).forEach(function(u){
      if (!inYears(d, u)) return;
      var g = (D.units[u] || {}).g;
      if (!g) return;
      var sh = l1Shares(C, u);
      acc[g] = acc[g] || {}; n[g] = (n[g] || 0) + 1;
      Object.keys(sh).forEach(function(o){ acc[g][o] = (acc[g][o] || 0) + sh[o]; });
    });
    var gs = Object.keys(n).sort(function(a, b){ return n[b] - n[a]; });
    if (gs.length < 2) return;
    var MAXR = 15, shown = gs.slice(0, MAXR);
    var onKeys = Object.keys(C.on).sort();
    var sec = el('div', 'heat-block');
    sec.appendChild(el('h3', 'sub-h', 'Perfil por ' + groupName.toLowerCase()));
    sec.appendChild(el('p', 'desc', 'Cómo reparte cada ' + groupName.toLowerCase() + ' su alineación entre ' +
      'los ' + PL.level1_plural + ' (cada fila suma 100 %). Más oscuro, más peso.' +
      (gs.length > MAXR ? ' Se muestran las ' + MAXR + ' con más ' + plural(D.noun) + ' alineados, de ' + gs.length + '.' : '')));
    function tot(g){ return onKeys.reduce(function(a, o){ return a + (acc[g][o] || 0); }, 0) || 1; }
    CH.heatmap(sec, {rowName: groupName,
      rows: shown.map(function(g){ return {id: g, label: g, note: n[g] + ' ' + plural(D.noun)}; }),
      cols: onKeys.map(function(o){ return {id: o, label: o === C.on[o] ? CH.clip(o, 22) : o, full: C.on[o]}; }),
      val: function(r, c){ return (acc[r.id][c.id] || 0) / tot(r.id); },
      fmt: function(v){ return pct(v, 0) + ' de su alineación'; }});
    CH.tableView(sec, [groupName, cap(plural(D.noun))].concat(onKeys.map(function(o){ return l1Short(C, o); })),
      gs.map(function(g){
        return [g, String(n[g])].concat(onKeys.map(function(o){ return pct((acc[g][o] || 0) / tot(g), 0); }));
      }), [0, 1].concat(onKeys.map(function(){ return 1; })));
    box.appendChild(sec);
  }

  function renderCeplan(){
    var box = document.getElementById('ceplan');
    box.textContent = '';
    box.appendChild(el('h2', null, PLAN_TITLE));
    var avail = PF.order.filter(function(d){ return DATA[d].ceplan; });
    if (!avail.length){
      box.appendChild(el('p', 'note', 'Todavía no hay un cruce con ' + PL.short + ' para ninguna de las ' +
        'corridas cargadas (scripts/analysis/ceplan_units.py).'));
      return;
    }
    if (avail.indexOf(ceplanDom) < 0) ceplanDom = avail[0];
    var D = DATA[ceplanDom], C = D.ceplan, CV = cview(ceplanDom);
    var subsArr = Object.keys(C.subs);
    yrBanner(box, ceplanDom, CV.nu, Object.keys(C.status).length);
    box.appendChild(el('p', 'desc', 'Qué ' + LEAVES + ' ' + PL.source + ' (' +
      Object.keys(C.on).length + ' ' + PL.level1_plural + ', ' + subsArr.length + ' ' + LEAVES +
      ') desarrolla cada ' + D.noun + ', y quién desarrolla cada ' + LEAF + '.'));
    // Cuanto se puede confiar en este cruce: la revision manual vale solo para
    // el dataset con el que se hizo, y un plan de otro pais se juzga por tema.
    if (PL.foreign) box.appendChild(el('p', 'note', PL.foreign));
    if (PL.validation) box.appendChild(el('p', 'note', PL.validation));

    var seg = el('div', 'seg'); seg.setAttribute('role', 'group'); seg.setAttribute('aria-label', 'Universo');
    avail.forEach(function(d){
      var b = el('button', null, NAMES[d] || d); b.type = 'button';
      b.setAttribute('aria-pressed', String(d === ceplanDom));
      b.addEventListener('click', function(){ ceplanDom = d; ceplanOpen = null; renderCeplan(); });
      seg.appendChild(b);
    });
    box.appendChild(seg);

    renderRetoDots(box, ceplanDom);

    // reparto por ON
    var onKeys = Object.keys(CV.byOn).sort(function(a, b){ return CV.byOn[b] - CV.byOn[a]; });
    var total = onKeys.reduce(function(s, k){ return s + CV.byOn[k]; }, 0) || 1;
    var wrap = el('div', 'tablewrap'), tbl = el('table');
    tbl.innerHTML = '<thead><tr><th>' + PL.level1_long + '</th>' +
      '<th class="c">' + cap(plural(D.noun)) + '-equivalentes' +
      '<span class="hint">cada unidad reparte 1 entre sus ' + LEAVES + '</span></th>' +
      '<th class="c">% de lo alineado</th></tr></thead>';
    var tb = el('tbody');
    onKeys.forEach(function(k){
      var tr = el('tr');
      tr.appendChild(el('td', null, C.on[k]));
      var t1 = el('td', 'num'); t1.textContent = CV.byOn[k].toFixed(1); tr.appendChild(t1);
      tr.appendChild(barCell('c', CV.byOn[k] / total, 1));
      tb.appendChild(tr);
    });
    tbl.appendChild(tb); wrap.appendChild(tbl); box.appendChild(wrap);

    renderGroupHeat(box, ceplanDom);

    // ON -> Tematica -> Sub-tematica
    Object.keys(C.on).sort().forEach(function(on){
      var ids = subsArr.filter(function(k){
        return C.subs[k].o === on && (!ceplanOnlyGaps || CV.subs[k].cov !== 'desarrollada');
      });
      if (!ids.length) return;
      var blk = el('div', 'on-block'); blk.id = 'on-' + slug(on);
      blk.appendChild(el('h4', null, C.on[on]));
      var dev = ids.filter(function(k){ return CV.subs[k].cov === 'desarrollada'; }).length;
      blk.appendChild(el('p', 'on-sum', ids.length + ' ' + LEAVES +
        (ceplanOnlyGaps ? ' con poco o ningún desarrollo' : ' · ' + dev + ' desarrolladas')));
      var temas = {};
      ids.forEach(function(k){ (temas[C.subs[k].t] = temas[C.subs[k].t] || []).push(k); });
      Object.keys(temas).sort().forEach(function(t){
        if (t) blk.appendChild(el('div', 'tema-h', t));   // un plan de dos niveles no tiene nivel 2
        temas[t].sort(function(a, b){ return CV.subs[b].eq - CV.subs[a].eq; }).forEach(function(k){
          blk.appendChild(subRow(ceplanDom, k));
        });
      });
      box.appendChild(blk);
    });
  }

  // Grafico 1: «¿cuanto trabajo cientifico responde a cada reto?». Las areas
  // son las del propio plan (nivel 1 -> hoja) y cada punto es una unidad
  // vinculada en los años elegidos.
  function renderRetoDots(box, d){
    var D = DATA[d], C = D.ceplan;
    var c = card(box, 'Cuánto trabajo responde a cada ' + LEAF,
      'Cada cuadro es una ' + LEAF + ' del ' + PL.name + ', todas del mismo tamaño y en el orden del plan; ' +
      'cada punto es un' + (fem(D.noun) ? 'a ' : ' ') + D.noun + ' vinculad' + (fem(D.noun) ? 'a' : 'o') +
      '. Un cuadro con pocos puntos es una ' + LEAF + ' que casi nadie trabaja. Haz clic en el nombre para ' +
      'ver el detalle, o en un punto para abrir ' + (fem(D.noun) ? 'esa ' : 'ese ') + D.noun + '.');
    var dotsBySub = {};
    Object.keys(C.units).forEach(function(u){
      if (!inYears(d, u)) return;
      C.units[u].forEach(function(r){
        (dotsBySub[r[0]] = dotsBySub[r[0]] || []).push({id: u, g: r[1], t: (D.units[u] || {}).t || u});
      });
    });
    var groups = Object.keys(C.on).sort().map(function(on){
      return {key: on, label: C.on[on], cells: Object.keys(C.subs)
        .filter(function(k){ return C.subs[k].o === on; })
        .sort(function(a, b){ return a.localeCompare(b, 'es', {numeric: true}); })
        .map(function(k){
          var dots = (dotsBySub[k] || []).sort(function(a, b){ return b.g - a.g; });
          var n2 = dots.filter(function(x){ return x.g === 2; }).length;
          return {id: k, label: C.subs[k].l, n2: n2, n1: dots.length - n2, dots: dots};
        })};
    });
    CH.dotGrid(c, groups, {leaves: LEAVES, nouns: plural(D.noun),
                           onCell: function(k){ gotoSub(d, k); }, onDot: function(u){ gotoUnit(d, u); }});
    CH.tableView(c, [PL.level1_long, cap(LEAF), 'Relación clara', 'Tangencial'],
      groups.reduce(function(acc, g){
        return acc.concat(g.cells.map(function(x){ return [l1Short(C, g.key), x.label, x.n2, x.n1]; }));
      }, []), [0, 0, 1, 1]);
  }

  // --- Mapa ---------------------------------------------------------------------
  // Grafico 2: «¿que esta priorizando este conjunto de retos?». El mapa de la
  // investigacion es fijo y comun a todos los datasets (research_map.py); cada
  // reto cae donde esta la investigacion que mas se le parece.
  var mapPlans = null;
  function renderMap(){
    var box = document.getElementById('map');
    box.textContent = ''; CH.hideTip();
    box.appendChild(el('h2', null, 'Qué prioriza cada conjunto de retos'));
    if (!MAPA){
      box.appendChild(el('p', 'note', MAPA_ERR ? 'No se pudo cargar el mapa (' + MAPA_ERR + ').' : 'Cargando el mapa…'));
      if (!MAPA_ERR) loadMap().then(function(){ if (section === 'map') renderMap(); });
      return;
    }
    var M = MAPA, keys = Object.keys(M.plans);
    if (!mapPlans) mapPlans = keys.indexOf(planKey) >= 0 ? [planKey] : keys.slice(0, 1);
    mapPlans = mapPlans.filter(function(k){ return keys.indexOf(k) >= 0; });
    box.appendChild(el('p', 'desc', 'El fondo es fijo y el mismo para todos los planes: cada punto gris es un ' +
      'proyecto o una publicación (PUCP y ECOTEC), junto a los más parecidos por su contenido, y las zonas son ' +
      'áreas temáticas. Cada reto cae donde está la investigación que más se le parece. Así se ve en qué áreas ' +
      'se concentra un plan y cuáles deja de lado. Puedes superponer varios planes.'));
    var seg = el('div', 'seg'); seg.setAttribute('role', 'group'); seg.setAttribute('aria-label', 'Planes en el mapa');
    keys.forEach(function(k){
      var b = el('button', null, M.plans[k].short); b.type = 'button'; b.title = M.plans[k].name;
      b.setAttribute('aria-pressed', String(mapPlans.indexOf(k) >= 0));
      b.addEventListener('click', function(){
        var i = mapPlans.indexOf(k);
        if (i >= 0 && mapPlans.length > 1) mapPlans.splice(i, 1);
        else if (i < 0) mapPlans.push(k);
        renderMap();
      });
      seg.appendChild(b);
    });
    box.appendChild(seg);

    var secName = {};
    M.sectors.forEach(function(s){ secName[s.id] = s.name; });
    var hiDs = M.datasets.indexOf(PF.id);
    var c = card(box, 'Dónde caen los retos en el mapa de la investigación',
      'Más oscuros, los puntos de ' + PF.label + '. Pasa el puntero por un reto para ver su área y la ' +
      'investigación más cercana; en uno del plan elegido arriba, haz clic para abrirlo en «Retos».');
    var layers = mapPlans.map(function(k){
      var P = M.plans[k];
      var dom = k === planKey ? PF.order.filter(function(d){ return DATA[d].ceplan; })[0] : null;
      return {key: k, label: P.short, marks: P.retos.map(function(r){
        return {x: r.x, y: r.y, far: r.far,
                lines: [r.l, P.short + ' · ' + (P.l1[r.o] || r.o), 'Área: ' + secName[r.s],
                        'Similitud con la investigación más cercana: ' + r.sim.toFixed(2),
                        r.near.length ? 'Más cercana: ' + CH.clip(r.near[0], 90) : ''],
                onClick: dom ? function(){ gotoSub(dom, r.id); } : null};
      })};
    });
    CH.scatterMap(c, {sectors: M.sectors, units: M.units, hiDs: hiDs, layers: layers,
                      aria: 'Mapa de la investigación con los retos de ' +
                            layers.map(function(l){ return l.label; }).join(', ')});

    // Reparto por area: retos de cada plan frente a la investigacion.
    var c2 = card(box, 'Qué áreas prioriza cada plan',
      'Porcentaje de los retos de cada plan que cae en cada área, junto al porcentaje de la investigación ' +
      '(proyectos y publicaciones de PUCP y ECOTEC) que hay en ella. Un área con muchos retos y poca ' +
      'investigación es una prioridad del plan que la investigación apenas cubre.');
    var nUnits = M.units.length, unitsBy = {};
    M.units.forEach(function(u){ unitsBy[u[2]] = (unitsBy[u[2]] || 0) + 1; });
    var share = {};
    mapPlans.forEach(function(k){
      var P = M.plans[k], by = {};
      P.retos.forEach(function(r){ by[r.s] = (by[r.s] || 0) + 1; });
      share[k] = {by: by, n: P.retos.length};
    });
    var order = M.sectors.slice().sort(function(a, b){
      var k = mapPlans[0];
      return ((share[k].by[b.id] || 0) - (share[k].by[a.id] || 0)) || (unitsBy[b.id] - unitsBy[a.id]);
    });
    var wrap = el('div', 'tablewrap'), tbl = el('table');
    tbl.innerHTML = '<thead><tr><th>Área</th>' + mapPlans.map(function(k){
      return '<th class="c">' + esc(M.plans[k].short) + '<span class="hint">% de sus retos</span></th>';
    }).join('') + '<th class="c">Investigación<span class="hint">% de las unidades</span></th></tr></thead>';
    var tb = el('tbody');
    order.forEach(function(sct){
      var tr = el('tr'), td = el('td');
      td.appendChild(el('b', null, sct.name));
      td.appendChild(el('span', 'unit-meta', sct.topics.slice(0, 3).map(function(t){ return t[0]; }).join(' · ')));
      tr.appendChild(td);
      mapPlans.forEach(function(k){
        var n = share[k].by[sct.id] || 0, cell = barCell('c', n / share[k].n, 1);
        cell.title = n + ' de ' + share[k].n + ' ' + M.plans[k].leaves;
        tr.appendChild(cell);
      });
      tr.appendChild(barCell('k', (unitsBy[sct.id] || 0) / nUnits, 1));
      tb.appendChild(tr);
    });
    tbl.appendChild(tb); wrap.appendChild(tbl); c2.appendChild(wrap);
    CH.tableView(c2, ['Plan', 'Reto', 'Área', 'Similitud con la más cercana'],
      mapPlans.reduce(function(acc, k){
        return acc.concat(M.plans[k].retos.map(function(r){
          return [M.plans[k].short, r.l, secName[r.s], r.sim.toFixed(2)];
        }));
      }, []), [0, 0, 0, 1]);
    box.appendChild(el('p', 'note', 'Mapa: ' + M.params.method + ' sobre los embeddings de ' +
      nUnits.toLocaleString('es') + ' unidades (semilla fija, versión ' + M.version + '). Cada reto va al ' +
      'promedio, ponderado por similitud, de la posición de sus ' + M.params.k + ' unidades más parecidas.'));
  }

  function subRow(d, sid){
    var D = DATA[d], C = D.ceplan, s = C.subs[sid], sv = cview(d).subs[sid];
    var det = el('details', 'subrow'); det.id = 'sub-' + sid;
    if (ceplanOpen === sid) det.open = true;
    var sm = el('summary');
    sm.appendChild(el('span', 'nm', s.l));
    var cov = COV[sv.cov];
    sm.appendChild(el('span', 'pill ' + cov[0], cov[1]));
    sm.appendChild(el('span', 'ct', sv.n2 + ' claras · ' + (sv.n - sv.n2) + ' tang. · ' + sv.eq.toFixed(1) + ' eq'));
    det.appendChild(sm);
    var filled = false;
    det.addEventListener('toggle', function(){
      if (det.open) ceplanOpen = sid;
      if (!det.open || filled) return;
      filled = true;
      var inner = el('div', 'inner');
      var rows = [];
      Object.keys(C.units).forEach(function(u){
        if (!inYears(d, u)) return;
        C.units[u].forEach(function(r){ if (r[0] === sid) rows.push({u: u, g: r[1], c: r[2], k: r[3]}); });
      });
      if (yrActive()){
        var tot = rows.reduce(function(a, r){ return a + r.c; }, 0);
        rows.forEach(function(r){ r.k = tot ? r.c / tot : 0; });
      }
      rows.sort(function(a, b){ return (b.g - a.g) || (b.k - a.k); });
      if (!rows.length){
        inner.appendChild(el('p', 'note', ningun(D.noun) + ' tiene una relación confirmada con esta ' + LEAF +
          (yrActive() ? ' en los años elegidos.' : '.')));
        det.appendChild(inner); return;
      }
      var maxK = rows.reduce(function(m, r){ return Math.max(m, r.k); }, 0.0001);
      var wr = el('div', 'tablewrap'), tb = el('table');
      tb.innerHTML = '<thead><tr><th>' + esc(D.noun.charAt(0).toUpperCase() + D.noun.slice(1)) + '</th>' +
        '<th>Relación</th>' +
        '<th class="k">Cuánto de la ' + LEAF + ' aporta<span class="hint">barra a escala del mayor valor de la tabla</span></th>' +
        '<th class="c">Cuánto de la unidad es esta ' + LEAF + '<span class="hint">barra sobre 100 %</span></th>' +
        '</tr></thead>';
      var body = el('tbody');
      rows.forEach(function(r){
        var u = D.units[r.u] || {t: r.u}, tr = el('tr'), td = el('td');
        var lk = el('button', 'linkish', u.t || r.u); lk.type = 'button';
        lk.addEventListener('click', function(){ gotoUnit(d, r.u); });
        td.appendChild(lk);
        var meta = [u.y || '', u.g || ''].filter(Boolean).join(' · ');
        if (meta) td.appendChild(el('span', 'unit-meta', meta));
        tr.appendChild(td);
        var tdg = el('td'); tdg.appendChild(el('span', 'pill g' + r.g, r.g === 2 ? 'clara' : 'tangencial'));
        tr.appendChild(tdg);
        tr.appendChild(barCell('k', r.k, maxK));
        tr.appendChild(barCell('c', r.c, 1));
        body.appendChild(tr);
      });
      tb.appendChild(body); wr.appendChild(tb); inner.appendChild(wr);
      det.appendChild(inner);
    });
    return det;
  }

  document.querySelectorAll('#domains button').forEach(function(b){
    b.addEventListener('click', function(){ openSection(b.dataset.sec); }, SIG);
  });
  // «Acerca de los datos»: Metodología y Datos de origen, uno a la vez.
  document.querySelectorAll('#about-nav button').forEach(function(b){
    b.addEventListener('click', function(){
      document.querySelectorAll('#about-nav button').forEach(function(o){
        o.setAttribute('aria-pressed', String(o === b)); });
      document.getElementById('method').hidden = b.dataset.about !== 'method';
      document.getElementById('provenance').hidden = b.dataset.about !== 'provenance';
    }, SIG);
  });
  document.getElementById('q').addEventListener('input', function(e){
    query = e.target.value; renderList();
  }, SIG);

  function gotoTopic(d, tid){
    dom = d; sel = {kind: 't', id: tid}; query = '';
    document.getElementById('q').value = '';
    showSection(d);
    renderMetrics(); renderList(); renderDetail();
    document.getElementById('detail').scrollIntoView({block: 'start'});
  }
  function gotoListSearch(d, text){
    dom = d; sel = null; query = text;
    document.getElementById('q').value = text;
    showSection(d);
    renderMetrics(); renderList(); renderDetail();
    document.getElementById('explorer').scrollIntoView({block: 'start'});
  }

  // Vuelve a pintar lo que este a la vista cuando cambia el rango de años.
  function rerender(){
    if (section === 'topics'){ renderMetrics(); renderList(); renderDetail(); }
    if (section === 'ceplan') renderCeplan();
    if (section === 'summary') renderSummary();
    if (!omniRes.hidden) omniRender();
    var parts = [];
    if (yrActive()) Object.keys(DATA).forEach(function(d){
      parts.push(view(d).nu.toLocaleString('es') + ' de ' + DATA[d].nu.toLocaleString('es') + ' ' +
        plural(DATA[d].noun));
    });
    document.getElementById('yr-note').textContent = parts.join(' · ');
    document.getElementById('yr-reset').hidden = !yrActive();
  }

  // --- deslizador de años ---------------------------------------------------
  var yrLo = document.getElementById('yr-lo'), yrHi = document.getElementById('yr-hi');
  var yrNo = document.getElementById('yr-nodate');
  [yrLo, yrHi].forEach(function(r){ r.min = YR.min; r.max = YR.max; r.step = 1; });
  function yrPaint(){
    yrLo.value = YR.lo; yrHi.value = YR.hi; yrNo.checked = YR.nodate;
    var span = (YR.max - YR.min) || 1;
    var f = document.getElementById('yr-fill');
    f.style.left = ((YR.lo - YR.min) / span * 100) + '%';
    f.style.width = ((YR.hi - YR.lo) / span * 100) + '%';
    // Con los dos pulgares juntos al extremo derecho, el de "desde" debe quedar
    // encima o no se podria volver a mover.
    yrLo.style.zIndex = YR.lo >= YR.max - (span * 0.1) ? 3 : 1;
    document.getElementById('yr-out').textContent = yrText();
    yrLo.setAttribute('aria-valuetext', 'desde ' + YR.lo);
    yrHi.setAttribute('aria-valuetext', 'hasta ' + YR.hi);
  }
  function yrSet(lo, hi, nodate){
    lo = Math.max(YR.min, Math.min(YR.max, lo)); hi = Math.max(YR.min, Math.min(YR.max, hi));
    if (lo > hi){ var x = lo; lo = hi; hi = x; }
    var changed = lo !== YR.lo || hi !== YR.hi || nodate !== YR.nodate;
    YR.lo = lo; YR.hi = hi; YR.nodate = nodate;
    yrPaint();
    if (changed) rerender();
  }
  yrLo.addEventListener('input', function(){ yrSet(Math.min(+yrLo.value, YR.hi), YR.hi, YR.nodate); }, SIG);
  yrHi.addEventListener('input', function(){ yrSet(YR.lo, Math.max(+yrHi.value, YR.lo), YR.nodate); }, SIG);
  yrNo.addEventListener('change', function(){ yrSet(YR.lo, YR.hi, yrNo.checked); }, SIG);
  document.getElementById('yr-reset').addEventListener('click', function(){
    omniYrSaved = null; yrSet(YR.min, YR.max, true); }, SIG);
  yrPaint();

  // --- buscador global ------------------------------------------------------
  // Un solo indice con todo lo que se puede abrir: unidades de cada universo,
  // temas de cada universo y hojas del plan nacional. Sin acentos ni
  // mayusculas, y todas las palabras deben aparecer (en cualquier orden).
  function fold(s){ return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  // Pliega caracter a caracter para que las posiciones coincidan con el texto
  // original y se pueda resaltar sobre el.
  function foldAligned(s){
    var out = '';
    for (var i = 0; i < s.length; i++){ var f = fold(s[i]); out += f.length === 1 ? f : s[i]; }
    return out;
  }
  var OMNI = [], GROUPS = [];
  (function(){
    Object.keys(DATA).forEach(function(d){
      var D = DATA[d], g = 'u:' + d;
      GROUPS.push({key: g, label: cap(plural(D.noun)) + (D.kind === 'projects' ? '' : ' de proyectos'), d: d, kind: 'u'});
      Object.keys(D.units).forEach(function(id){
        var u = D.units[id];
        OMNI.push({g: g, kind: 'u', d: d, id: id, title: u.t || id, ft: foldAligned(u.t || id),
                   meta: [u.y, u.g].filter(Boolean).join(' · '), extra: fold(u.g + ' ' + id)});
      });
    });
    GROUPS.push({key: 't', label: 'Temas', kind: 't'});
    Object.keys(DATA).forEach(function(d){
      var D = DATA[d];
      Object.keys(D.topics).forEach(function(id){
        var t = D.topics[id];
        OMNI.push({g: 't', kind: 't', d: d, id: id, title: t.l, ft: foldAligned(t.l),
                   meta: (NAMES[d] || d), extra: fold(t.d)});
      });
    });
    GROUPS.push({key: 's', label: '', kind: 's'});
    omniPlan();
  })();
  // Las hojas del plan elegido; se rehace al cambiar de plan.
  function omniPlan(){
    OMNI = OMNI.filter(function(e){ return e.g !== 's'; });
    GROUPS.forEach(function(G){ if (G.key === 's') G.label = cap(LEAVES) + ' ' + PL.short; });
    var seen = {};
    Object.keys(DATA).forEach(function(d){
      var C = DATA[d].ceplan; if (!C) return;
      Object.keys(C.subs).forEach(function(id){
        if (seen[id]) return; seen[id] = 1;
        var s = C.subs[id], ctx = [C.on[s.o] || s.o, s.t].filter(Boolean).join(' · ');
        OMNI.push({g: 's', kind: 's', d: d, id: id, title: s.l, ft: foldAligned(s.l),
                   meta: ctx, extra: fold(s.t + ' ' + (C.on[s.o] || '') + ' ' + s.o)});
      });
    });
  }

  // Prefijos para acotar: "p:" proyectos, "pub:" publicaciones, "t:" temas,
  // "s:" (o el nombre del plan) hojas del plan. Un año (2015) o rango
  // (2012-2016) en la consulta mueve el deslizador mientras siga escrito.
  var PREFIX = {'t': 't', 'tema': 't', 'temas': 't',
    's': 's', 'sub': 's', 'ceplan': 's', 'pedn': 's', 'on': 's', 'pnd': 's', 'plan': 's',
    'politica': 's', 'politicas': 's', 'eje': 's'};
  PF.order.forEach(function(d){
    (DATA[d].kind === 'projects' ? ['p', 'proy', 'proyecto', 'proyectos']
                                 : ['pub', 'publicacion', 'publicaciones'])
      .forEach(function(k){ if (!PREFIX[k]) PREFIX[k] = 'u:' + d; });
  });
  function parseQuery(raw){
    var q = {only: null, years: null, tokens: []};
    fold(raw).split(/\s+/).filter(Boolean).forEach(function(tok){
      var m = /^([a-z]+):(.*)$/.exec(tok);
      if (m && PREFIX[m[1]]){ q.only = PREFIX[m[1]]; tok = m[2]; if (!tok) return; }
      var y = /^((?:19|20)\d\d)(?:(?:-|–|\.\.)((?:19|20)\d\d))?$/.exec(tok);
      if (y){ q.years = [+y[1], y[2] ? +y[2] : +y[1]]; return; }
      q.tokens.push(tok);
    });
    return q;
  }
  function scoreEntry(e, toks, phrase){
    var s = 0;
    for (var i = 0; i < toks.length; i++){
      var t = toks[i], at = e.ft.toLowerCase().indexOf(t);
      if (at >= 0){
        var wordStart = at === 0 || /[^a-z0-9]/.test(e.ft.toLowerCase().charAt(at - 1));
        s += wordStart ? 3 : 2;
      } else if (e.extra.indexOf(t) >= 0 || (e.kind === 'u' && e.id === t)) s += 1;
      else return 0;
    }
    var ft = e.ft.toLowerCase();
    if (ft.indexOf(phrase) === 0) s += 5; else if (ft.indexOf(phrase) >= 0) s += 2;
    if (e.kind === 'u' && e.id.toLowerCase() === phrase) s += 10;
    return s;
  }
  function highlight(e, toks){
    var ft = e.ft.toLowerCase(), marks = new Array(e.title.length + 1).join('0').split('');
    toks.forEach(function(t){
      var from = 0, at;
      while (t && (at = ft.indexOf(t, from)) >= 0){
        for (var i = at; i < at + t.length; i++) marks[i] = '1';
        from = at + t.length;
      }
    });
    var h = '', open = false;
    for (var i = 0; i < e.title.length; i++){
      if (marks[i] === '1' && !open){ h += '<mark>'; open = true; }
      if (marks[i] !== '1' && open){ h += '</mark>'; open = false; }
      h += esc(e.title[i]);
    }
    return h + (open ? '</mark>' : '');
  }

  var omniq = document.getElementById('omniq'), omniRes = document.getElementById('omni-res');
  var omniItems = [], omniActive = -1, omniYrSaved = null;
  var PER_GROUP = 6;

  function omniApplyYears(q){
    if (q.years){
      if (!omniYrSaved) omniYrSaved = {lo: YR.lo, hi: YR.hi, nodate: YR.nodate};
      yrSet(q.years[0], q.years[1], false);
    } else if (omniYrSaved){
      var s = omniYrSaved; omniYrSaved = null;
      yrSet(s.lo, s.hi, s.nodate);
    }
  }

  function omniRender(){
    var raw = omniq.value, q = parseQuery(raw);
    omniRes.textContent = ''; omniItems = []; omniActive = -1;
    if (!q.tokens.length){
      var help = el('div', 'omni-help');
      help.innerHTML = 'Escribe palabras del título, el departamento, la revista o el tema; sin importar tildes ni orden. ' +
        'Acota con <code>p:</code> proyectos, <code>pub:</code> publicaciones, <code>t:</code> temas o ' +
        '<code>s:</code> ' + LEAVES + ' ' + PL.short + '. Un año (<code>2015</code>) o rango (<code>2012-2016</code>) ' +
        'mueve el filtro de años.';
      omniRes.appendChild(help);
      omniOpen(true);
      return;
    }
    var phrase = q.tokens.join(' '), hits = {};
    OMNI.forEach(function(e){
      if (q.only && e.g !== q.only) return;
      if (e.kind === 'u' && !inYears(e.d, e.id)) return;
      if (e.kind === 't' && !view(e.d).n[e.id]) return;
      var sc = scoreEntry(e, q.tokens, phrase);
      if (sc) (hits[e.g] = hits[e.g] || []).push({e: e, s: sc});
    });
    var any = false;
    GROUPS.forEach(function(G){
      var list = hits[G.key]; if (!list) return;
      any = true;
      list.sort(function(a, b){ return b.s - a.s || a.e.title.length - b.e.title.length; });
      var limit = q.only ? 40 : PER_GROUP;
      var head = el('div', 'omni-grp');
      head.appendChild(el('span', null, G.label));
      head.appendChild(el('span', 'num', list.length > limit ? limit + ' de ' + list.length : String(list.length)));
      omniRes.appendChild(head);
      list.slice(0, limit).forEach(function(h){ omniAdd(h.e, q.tokens); });
      if (list.length > limit && G.kind === 'u'){
        omniAddMore('Ver los ' + list.length + ' en el explorador →', function(){ gotoListSearch(G.d, phrase); });
      } else if (list.length > limit){
        omniAddMore('Ver todos (' + list.length + ') →', function(){
          var pre = G.kind === 't' ? 't:' : 's:';
          omniq.value = pre + raw.replace(/^\s*[a-z]+:/i, ''); omniRender(); omniq.focus();
        });
      }
    });
    if (!any){
      omniRes.appendChild(el('div', 'omni-empty', 'Nada coincide con «' + raw.trim() + '»' +
        (yrActive() ? ' en los años ' + yrText() + '.' : '.')));
    }
    omniOpen(true);
    if (omniItems.length) omniMove(0);
  }
  function omniAdd(e, toks){
    var it = el('div', 'omni-item'); it.setAttribute('role', 'option');
    it.id = 'omni-' + omniItems.length;
    var t = el('span', 'ot'); t.innerHTML = highlight(e, toks); it.appendChild(t);
    if (e.meta) it.appendChild(el('span', 'om', e.meta));
    var go = function(){
      omniClose();
      if (e.kind === 'u') gotoUnit(e.d, e.id);
      else if (e.kind === 't') gotoTopic(e.d, e.id);
      else gotoSub(DATA[dom] && DATA[dom].ceplan ? dom : e.d, e.id);
    };
    omniBind(it, go);
  }
  function omniAddMore(label, go){
    var it = el('div', 'omni-item'); it.setAttribute('role', 'option');
    it.id = 'omni-' + omniItems.length;
    it.appendChild(el('span', 'om', label));
    omniBind(it, function(){ omniClose(); go(); });
  }
  function omniBind(it, go){
    var i = omniItems.length;
    it.addEventListener('mousedown', function(ev){ ev.preventDefault(); });
    it.addEventListener('click', go);
    it.addEventListener('mousemove', function(){ if (omniActive !== i) omniMove(i); });
    omniItems.push({node: it, go: go});
    omniRes.appendChild(it);
  }
  function omniMove(i){
    if (!omniItems.length) return;
    i = (i + omniItems.length) % omniItems.length;
    if (omniActive >= 0 && omniItems[omniActive]) omniItems[omniActive].node.setAttribute('aria-selected', 'false');
    omniActive = i;
    var n = omniItems[i].node;
    n.setAttribute('aria-selected', 'true');
    omniq.setAttribute('aria-activedescendant', n.id);
    n.scrollIntoView({block: 'nearest'});
  }
  function omniOpen(v){ omniRes.hidden = !v; omniq.setAttribute('aria-expanded', String(v)); }
  function omniClose(){ omniOpen(false); omniq.removeAttribute('aria-activedescendant'); }

  omniq.value = ''; omniClose();
  document.getElementById('q').value = '';
  document.getElementById('yr-note').textContent = '';
  document.getElementById('yr-reset').hidden = true;
  omniq.addEventListener('input', function(){ omniApplyYears(parseQuery(omniq.value)); omniRender(); }, SIG);
  omniq.addEventListener('focus', function(){ omniRender(); }, SIG);
  omniq.addEventListener('blur', function(){ omniClose(); }, SIG);
  omniq.addEventListener('keydown', function(ev){
    if (ev.key === 'ArrowDown'){ ev.preventDefault(); if (omniRes.hidden) omniRender(); else omniMove(omniActive + 1); }
    else if (ev.key === 'ArrowUp'){ ev.preventDefault(); omniMove(omniActive - 1); }
    else if (ev.key === 'Enter'){ if (omniActive >= 0 && omniItems[omniActive]){ ev.preventDefault(); omniItems[omniActive].go(); } }
    else if (ev.key === 'Escape'){
      // Sin preventDefault, Chrome/Edge vacian el type=search por su cuenta y el
      // evento input resultante volvia a abrir la lista: el primer Esc no cerraba.
      ev.preventDefault();
      if (!omniRes.hidden) omniClose();
      else { omniq.value = ''; omniApplyYears(parseQuery('')); }
    }
  }, SIG);
  document.addEventListener('keydown', function(ev){
    var tag = (ev.target.tagName || '').toLowerCase();
    if (ev.key === '/' && tag !== 'input' && tag !== 'textarea' && !ev.target.isContentEditable){
      ev.preventDefault(); omniq.focus(); omniq.select();
    }
  }, SIG);

  // Estado inicial: el Resumen. Temas queda listo con el primer universo y su
  // tema mas grande abierto, para que se lea de entrada al cambiar de pestaña.
  (function(){
    var D = DATA[dom];
    var top = Object.keys(D.topics).sort(function(a,b){ return D.topics[b].eq - D.topics[a].eq; })[0];
    sel = {kind:'t', id:top};
  })();
  document.querySelectorAll('#about-nav button').forEach(function(o){
    o.setAttribute('aria-pressed', String(o.dataset.about === 'method')); });
  document.getElementById('method').hidden = false;
  document.getElementById('provenance').hidden = true;
  renderMetrics(); renderList(); renderDetail();
  openSection('summary');

  // Cambio de plan desde el selector de la cabecera: se queda en la misma
  // pestaña, con la misma seleccion y el mismo rango de años.
  planHook = function(key){
    applyPlan(key);
    omniPlan();
    ceplanOpen = null;
    var m = document.getElementById('method');
    m.textContent = ''; delete m.dataset.done;   // nombra el plan y su verificador
    if (section === 'topics') renderDetail();
    if (section === 'ceplan') renderCeplan();
    if (section === 'summary') renderSummary();
    if (section === 'about') renderMethod();
    mapPlans = null;   // el mapa pasa a mostrar el plan recien elegido
    if (section === 'map') renderMap();
    if (!omniRes.hidden) omniRender();
  };
  }
})();

(function(){
  "use strict";
  // Un dataset (universidad) a la vez. build_atlas.py escribe por dataset un
  // archivo con sus numeros y sus textos propios (atlas_profiles.py); esta
  // pagina solo tiene el texto comun. Publicada, carga datasets.json y luego
  // data/<id>.json; como archivo unico (atlas_<id>.html) trae su dataset
  // incrustado y no muestra el selector.
  var INLINE = JSON.parse(document.getElementById('bundle').textContent);
  var loaded = {}, ctrl = null, current = null;
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
  function open(list, id){
    current = id; paintSelector(list);
    if (!loaded[id]) status('Cargando ' + (list.filter(function(x){ return x.id === id; })[0] || {}).label + '…');
    (loaded[id] ? Promise.resolve(loaded[id]) : fetchJSON('data/' + encodeURIComponent(id) + '.json'))
      .then(function(B){
        loaded[id] = B;
        if (current !== id) return;   // se eligio otro mientras cargaba
        status(''); remember(id); mount(B);
      })
      .catch(function(err){
        if (current === id) status('No se pudieron cargar los datos de este dataset (' + err.message + ').');
      });
  }

  if (INLINE) mount(INLINE);
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
  function mount(B){
  if (ctrl) ctrl.abort();
  ctrl = new AbortController();
  var SIG = {signal: ctrl.signal};
  var DATA = B.data, META = B.method, PF = B.profile, PL = PF.plan;

  document.title = PF.title;
  document.getElementById('title').textContent = PF.title;
  document.getElementById('eyebrow').textContent = PF.eyebrow;
  ['method', 'provenance', 'ceplan'].forEach(function(id){
    var s = document.getElementById(id); s.textContent = ''; delete s.dataset.done;
  });
  var bar = document.getElementById('domains'), anchor = document.getElementById('dom-method');
  bar.querySelectorAll('[data-unit-dom]').forEach(function(b){ b.remove(); });
  PF.order.forEach(function(d){
    var b = document.createElement('button');
    b.type = 'button'; b.dataset.dom = d; b.dataset.unitDom = '1'; b.textContent = PF.domains[d].tab;
    bar.insertBefore(b, anchor);
  });
  document.getElementById('dom-ceplan').textContent = PL.tab;
  document.getElementById('omniq').placeholder =
    'Busca un proyecto, una publicación, un tema o una ' + PL.leaf + ' ' + PL.short + '…';
  document.getElementById('atlas').hidden = false;
  document.getElementById('menu').hidden = false;

  Object.keys(DATA).forEach(function(d){
    var t = PF.domains[d] || {label: d, noun: 'unidad'};
    DATA[d].label = t.label; DATA[d].noun = t.noun; DATA[d].kind = t.kind;
  });
  var NAMES = {};
  PF.order.forEach(function(d){ NAMES[d] = PF.domains[d].tab; });

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

  function cview(d){
    var key = 'c' + yrKey(d);
    if (vcache[key]) return vcache[key];
    var C = DATA[d].ceplan, act = yrActive(), V = {subs: {}, byOn: {}, aligned: 0, nu: 0};
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

  // Vocabulario del plan nacional del dataset (atlas_profiles.PLANS +
  // lb_plans.Plan). Las hojas de los planes cargados hoy son femeninas
  // («sub-temática», «política»): «Ninguna», «desarrollada».
  var LEAF = PL.leaf, LEAVES = PL.leaves, PLAN_TITLE = cap(LEAVES) + ' del ' + PL.name;
  var STATUS_TXT = {
    sin_candidatas: 'Ninguna ' + LEAF + ' del ' + PL.name + ' se parece lo suficiente a esta unidad ' +
      '(similitud bajo el piso). Es lo esperable en investigación básica sin relación con política pública.',
    rechazadas_por_llm: 'Hubo ' + LEAVES + ' candidatas, pero el verificador no confirmó relación con ninguna.',
    verificacion_fallida: 'La verificación de esta unidad no produjo una respuesta legible.'
  };

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
      td.appendChild(el('span', 'unit-meta', s.o + ' · ' + s.t));
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

  function showSection(which){
    document.querySelectorAll('.domains button').forEach(function(o){
      var want = which === 'ceplan' ? '__ceplan__' : which;
      o.setAttribute('aria-pressed', String(o.dataset.dom === want));
    });
    var isCeplan = which === 'ceplan';
    document.getElementById('explorer').hidden = isCeplan;
    document.getElementById('method').hidden = true;
    document.getElementById('provenance').hidden = true;
    document.getElementById('ceplan').hidden = !isCeplan;
    document.querySelector('.metrics').hidden = isCeplan;
    document.querySelector('.legend').hidden = isCeplan;
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
    

    var seg = el('div', 'seg'); seg.setAttribute('role', 'group'); seg.setAttribute('aria-label', 'Universo');
    avail.forEach(function(d){
      var b = el('button', null, NAMES[d] || d); b.type = 'button';
      b.setAttribute('aria-pressed', String(d === ceplanDom));
      b.addEventListener('click', function(){ ceplanDom = d; ceplanOpen = null; renderCeplan(); });
      seg.appendChild(b);
    });
    box.appendChild(seg);

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

    // ON -> Tematica -> Sub-tematica
    Object.keys(C.on).sort().forEach(function(on){
      var ids = subsArr.filter(function(k){
        return C.subs[k].o === on && (!ceplanOnlyGaps || CV.subs[k].cov !== 'desarrollada');
      });
      if (!ids.length) return;
      var blk = el('div', 'on-block');
      blk.appendChild(el('h4', null, C.on[on]));
      var dev = ids.filter(function(k){ return CV.subs[k].cov === 'desarrollada'; }).length;
      blk.appendChild(el('p', 'on-sum', ids.length + ' ' + LEAVES +
        (ceplanOnlyGaps ? ' con poco o ningún desarrollo' : ' · ' + dev + ' desarrolladas')));
      var temas = {};
      ids.forEach(function(k){ (temas[C.subs[k].t] = temas[C.subs[k].t] || []).push(k); });
      Object.keys(temas).sort().forEach(function(t){
        blk.appendChild(el('div', 'tema-h', t));
        temas[t].sort(function(a, b){ return CV.subs[b].eq - CV.subs[a].eq; }).forEach(function(k){
          blk.appendChild(subRow(ceplanDom, k));
        });
      });
      box.appendChild(blk);
    });
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

  document.querySelectorAll('.domains button').forEach(function(b){
    b.addEventListener('click', function(){
      document.querySelectorAll('.domains button').forEach(function(o){
        o.setAttribute('aria-pressed', String(o === b)); });
      var isMethod = b.dataset.dom === '__method__';
      var isProvenance = b.dataset.dom === '__provenance__';
      var isCeplan = b.dataset.dom === '__ceplan__';
      var isSpecial = isMethod || isProvenance || isCeplan;
      document.getElementById('explorer').hidden = isSpecial;
      document.getElementById('method').hidden = !isMethod;
      document.getElementById('provenance').hidden = !isProvenance;
      document.getElementById('ceplan').hidden = !isCeplan;
      document.querySelector('.metrics').hidden = isSpecial;
      document.querySelector('.legend').hidden = isSpecial;
      if (isMethod){ renderMethod(); return; }
      if (isProvenance){ renderProvenance(); return; }
      if (isCeplan){ renderCeplan(); return; }
      dom = b.dataset.dom; sel = null; query=''; document.getElementById('q').value='';
      renderMetrics(); renderList(); renderDetail();
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
    if (!document.getElementById('explorer').hidden){ renderMetrics(); renderList(); renderDetail(); }
    if (!document.getElementById('ceplan').hidden) renderCeplan();
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
    GROUPS.push({key: 's', label: cap(LEAVES) + ' ' + PL.short, kind: 's'});
    var seen = {};
    Object.keys(DATA).forEach(function(d){
      var C = DATA[d].ceplan; if (!C) return;
      Object.keys(C.subs).forEach(function(id){
        if (seen[id]) return; seen[id] = 1;
        var s = C.subs[id];
        OMNI.push({g: 's', kind: 's', d: d, id: id, title: s.l, ft: foldAligned(s.l),
                   meta: (C.on[s.o] || s.o) + ' · ' + s.t, extra: fold(s.t + ' ' + (C.on[s.o] || '') + ' ' + s.o)});
      });
    });
  })();

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

  // Estado inicial: el primer universo, con su tema mas grande ya abierto,
  // para que la pagina se lea de entrada.
  showSection(dom);
  renderMetrics();
  (function(){
    var D = DATA[dom];
    var top = Object.keys(D.topics).sort(function(a,b){ return D.topics[b].eq - D.topics[a].eq; })[0];
    sel = {kind:'t', id:top};
  })();
  renderList(); renderDetail();
  }
})();

(function(){
  "use strict";
  // Una sola vista: arriba se elige la investigacion (universidad y tipo de
  // unidad) y el conjunto de retos; debajo, tres respuestas:
  //   1. cifras clave;
  //   2. ¿que prioriza el plan y donde esta la investigacion? (mapa fijo,
  //      research_map.py, y reparto por area);
  //   3. ¿cuanto trabajo responde a cada reto? (un cuadro por reto, un punto
  //      por unidad), con el detalle del reto o la unidad elegidos.
  // Datos, como los escribe build_atlas.py: datasets.json (que hay), data/<id>.json
  // (unidades de un dataset), data/<id>/<plan>.json (su cruce con un plan) y
  // data/mapa.json (el mapa, comun a todos). Como archivo unico
  // (atlas_<id>.html) trae su dataset incrustado y el mapa no esta.
  var INLINE = JSON.parse(document.getElementById('bundle').textContent);
  var CH = window.AtlasCharts;
  var view = document.getElementById('view'), msg = document.getElementById('loadmsg');
  var MANIFEST = null, loaded = {}, MAPA = null, MAPA_ERR = null, mapaReq = null;
  var sel = {ds: null, dom: null, plan: null, reto: null, unit: null};
  var token = 0;

  // --- utilidades -------------------------------------------------------------
  function el(tag, cls, txt, parent){
    var e = document.createElement(tag); if (cls) e.className = cls;
    if (txt != null) e.textContent = txt; if (parent) parent.appendChild(e); return e;
  }
  function status(text){ msg.textContent = text || ''; msg.hidden = !text; }
  function fetchJSON(url){
    return fetch(url).then(function(r){
      if (!r.ok) throw new Error(url + ': HTTP ' + r.status);
      return r.json();
    });
  }
  function fmt(n){ return Number(n).toLocaleString('es'); }
  function pct(x, dp){ return (x * 100).toFixed(dp === undefined ? 0 : dp) + ' %'; }
  function cap(s){ return s.charAt(0).toUpperCase() + s.slice(1); }
  function plural(noun){ return noun.replace(/ción$/, 'cione') + 's'; }
  function fem(noun){ return /ción$/.test(noun); }
  function card(title, desc){
    var c = el('section', 'card', null, view);
    el('h3', null, title, c);
    if (desc) el('p', 'desc', desc, c);
    return c;
  }
  function barCell(value, text){
    var td = el('td', 'c'), w = el('div', 'bar', null, td), tr = el('div', 'track', null, w), i = el('i', null, null, tr);
    i.style.width = Math.max(value > 0 ? 1.5 : 0, Math.min(100, value * 100)) + '%';
    el('span', 'val', text, w);
    return td;
  }

  // --- seleccion: URL y memoria del navegador ---------------------------------
  function readSel(){
    var q = {};
    try { new URLSearchParams(location.search).forEach(function(v, k){ q[k] = v; }); } catch (e) {}
    if (!q.ds) try { q = JSON.parse(localStorage.getItem('atlas-sel') || '{}'); } catch (e) {}
    return q;
  }
  function remember(){
    var q = {ds: sel.ds, dom: sel.dom, plan: sel.plan};
    try { localStorage.setItem('atlas-sel', JSON.stringify(q)); } catch (e) {}
    try {
      var u = new URL(location.href);
      Object.keys(q).forEach(function(k){ u.searchParams.set(k, q[k]); });
      history.replaceState(null, '', u.toString());
    } catch (e) {}
  }
  function entry(id){ return MANIFEST.filter(function(x){ return x.id === id; })[0]; }
  function domName(E, d){ return (E.domains && E.domains[d]) || (/pub/.test(d) ? 'Publicaciones' : 'Proyectos'); }
  function planName(E, k){ return (E.plan_names && E.plan_names[k]) || k; }
  function fixSel(){
    var E = entry(sel.ds) || MANIFEST[0];
    sel.ds = E.id;
    var doms = Object.keys(E.runs || E.domains);
    if (doms.indexOf(sel.dom) < 0) sel.dom = doms[0];
    if (E.plans.indexOf(sel.plan) < 0) sel.plan = E.plan || E.plans[0];
  }

  // --- selectores -------------------------------------------------------------
  function paintQuery(){
    var rs = document.getElementById('q-research'), ps = document.getElementById('q-plan');
    rs.textContent = ''; ps.textContent = '';
    MANIFEST.forEach(function(E){
      Object.keys(E.runs || E.domains).forEach(function(d){
        var o = el('option', null, E.label + ' · ' + domName(E, d), rs);
        o.value = E.id + '|' + d;
        o.selected = E.id === sel.ds && d === sel.dom;
      });
    });
    var E = entry(sel.ds);
    E.plans.forEach(function(k){
      var o = el('option', null, planName(E, k), ps);
      o.value = k; o.selected = k === sel.plan;
    });
    document.getElementById('query').hidden = false;
  }
  document.getElementById('q-research').addEventListener('change', function(ev){
    var v = ev.target.value.split('|');
    sel.ds = v[0]; sel.dom = v[1]; sel.reto = null; sel.unit = null;
    fixSel(); paintQuery(); go();
  });
  document.getElementById('q-plan').addEventListener('change', function(ev){
    sel.plan = ev.target.value; sel.reto = null; sel.unit = null; go();
  });

  // --- carga ------------------------------------------------------------------
  function loadDataset(id){
    if (loaded[id]) return Promise.resolve(loaded[id]);
    return fetchJSON('data/' + encodeURIComponent(id) + '.json').then(function(B){ loaded[id] = B; return B; });
  }
  function loadPlan(B, key){
    B.plans = B.plans || {};
    if (B.plans[key]) return Promise.resolve(B.plans[key]);
    return fetchJSON('data/' + encodeURIComponent(B.profile.id) + '/' + encodeURIComponent(key) + '.json')
      .then(function(P){ B.plans[key] = P; return P; });
  }
  function loadMap(){
    if (!mapaReq) mapaReq = fetchJSON('data/mapa.json')
      .then(function(M){ MAPA = M; })
      .catch(function(err){ MAPA_ERR = err.message; });
    return mapaReq;
  }
  function go(){
    var t = ++token, E = entry(sel.ds);
    remember();
    if (!loaded[sel.ds]) status('Cargando ' + E.label + '…');
    loadDataset(sel.ds).then(function(B){
      if (t !== token) return;
      status('Cargando ' + planName(E, sel.plan) + '…');
      return loadPlan(B, sel.plan).then(function(){ if (t === token){ status(''); render(); } });
    }).catch(function(err){
      if (t === token) status('No se pudieron cargar los datos (' + err.message + ').');
    });
    if (!INLINE) loadMap().then(function(){ if (t === token && loaded[sel.ds]) render(); });
  }

  // --- vista --------------------------------------------------------------------
  function ctx(){
    var B = loaded[sel.ds], PF = B.profile;
    var C = (B.plans[sel.plan] || {})[sel.dom] || null;
    return {B: B, PF: PF, D: B.data[sel.dom], DP: PF.domains[sel.dom], PL: PF.plans[sel.plan], C: C};
  }
  // Cobertura de cada reto en este universo: puntos (unidades vinculadas) y
  // cuantas son relacion clara.
  function retoStats(X){
    var C = X.C, by = {};
    Object.keys(C.subs).forEach(function(k){ by[k] = {n2: 0, n1: 0, dots: []}; });
    Object.keys(C.units).forEach(function(u){
      C.units[u].forEach(function(r){
        var st = by[r[0]]; if (!st) return;
        st.dots.push({id: u, g: r[1], t: (X.D.units[u] || {}).t || u});
        if (r[1] === 2) st.n2++; else st.n1++;
      });
    });
    Object.keys(by).forEach(function(k){ by[k].dots.sort(function(a, b){ return b.g - a.g; }); });
    return by;
  }
  function selectReto(id){
    sel.reto = sel.reto === id ? null : id; sel.unit = null; render();
    var d = document.getElementById('detail'); if (d && sel.reto) d.scrollIntoView({block: 'nearest'});
  }
  function selectUnit(uid){
    sel.unit = uid; render();
    var d = document.getElementById('detail'); if (d) d.scrollIntoView({block: 'nearest'});
  }

  function render(){
    CH.hideTip();
    var X = ctx(), PF = X.PF, PL = X.PL, noun = X.DP.noun;
    view.textContent = '';
    document.title = 'Atlas · ' + PF.label + ' · ' + PL.short;
    document.getElementById('q-research-note').textContent = X.DP.label;
    document.getElementById('q-plan-note').textContent = PL.name + (PL.validated ? '' : ' · cruce sin revisión manual');
    document.getElementById('prov').textContent = PF.extraction_footer ? 'Temas: ' + PF.extraction_footer : '';
    var stats = X.C ? retoStats(X) : null;
    renderKpis(X, stats, noun);
    renderMap(X, stats, noun);
    if (!X.C){
      el('p', 'note', 'Todavía no hay un cruce de ' + plural(noun) + ' de ' + PF.label + ' con ' + PL.name +
        ' (scripts/analysis/ceplan_units.py --plan ' + PL.key + '). El mapa de arriba sí muestra dónde caen sus ' +
        PL.leaves + '.', view);
      return;
    }
    renderGrid(X, stats, noun);
    renderDetail(X, stats, noun);
  }

  function renderKpis(X, stats, noun){
    var D = X.D, PL = X.PL, tiles = [[cap(plural(noun)), fmt(D.nu), X.DP.label]];
    if (stats){
      var aligned = Object.keys(X.C.units).filter(function(u){
        return X.C.units[u].some(function(r){ return r[1] === 2; });
      }).length;
      var ids = Object.keys(stats), worked = ids.filter(function(k){ return stats[k].n2 > 0; }).length;
      tiles.push(['Responden a algún reto', pct(D.nu ? aligned / D.nu : 0),
                  fmt(aligned) + ' de ' + fmt(D.nu) + ' con al menos una relación clara']);
      tiles.push([cap(PL.leaves) + ' con trabajo', worked + ' de ' + ids.length,
                  (ids.length - worked) + ' sin ' + (fem(noun) ? 'ninguna ' : 'ningún ') + noun + ' con relación clara']);
    }
    var dl = el('dl', 'metrics kpis', null, view);
    tiles.forEach(function(t){
      var w = el('div', 'metric', null, dl);
      el('dt', null, t[0], w);
      var dd = el('dd', null, t[1], w); el('span', 'note', t[2], dd);
    });
  }

  // 2. ¿Que prioriza el plan y donde esta la investigacion?
  function renderMap(X, stats, noun){
    var PF = X.PF, PL = X.PL;
    var c = card('¿Qué prioriza ' + (PL.short || PL.name) + ' y dónde está la investigación?',
      'El fondo es un mapa fijo de toda la investigación de PUCP y ECOTEC: cada punto es un proyecto o una ' +
      'publicación, junto a los más parecidos por su contenido, y las zonas son áreas temáticas. Cada ' + PL.leaf +
      ' cae donde está la investigación que más se le parece. Haz clic en una ' + PL.leaf + ' para ver qué ' +
      plural(noun) + ' la responden.');
    if (!MAPA){
      el('p', 'note', INLINE ? 'El mapa no viene en el archivo único; está en el atlas publicado.' :
        MAPA_ERR ? 'No se pudo cargar el mapa (' + MAPA_ERR + ').' : 'Cargando el mapa…', c);
      return;
    }
    var P = MAPA.plans[sel.plan];
    if (!P){ el('p', 'note', 'Este plan todavía no está en el mapa (research_map.py place).', c); return; }
    var dsI = MAPA.datasets.indexOf(sel.ds), domI = (MAPA.domains || []).indexOf(sel.dom);
    var linked = {};
    if (sel.reto && X.C) Object.keys(X.C.units).forEach(function(u){
      if (X.C.units[u].some(function(r){ return r[0] === sel.reto; })) linked[u] = true;
    });
    var secName = {};
    MAPA.sectors.forEach(function(s){ secName[s.id] = s.name; });
    var mine = function(u){ return u[3] === dsI && (domI < 0 || u[4] === domI); };
    var units = MAPA.units.map(function(u){
      return {x: u[0], y: u[1], cls: mine(u) ? (linked[u[5]] ? 'lk' : 'hi') : ''};
    });
    var marks = P.retos.map(function(r){
      var st = stats && stats[r.id];
      return {x: r.x, y: r.y, far: r.far, sel: r.id === sel.reto,
              lines: [r.l, P.l1[r.o] || r.o, 'Área: ' + secName[r.s],
                      st ? st.n2 + ' ' + plural(noun) + ' con relación clara' : '',
                      r.near.length ? 'Investigación más parecida: ' + CH.clip(r.near[0], 90) : ''],
              onClick: X.C ? function(){ selectReto(r.id); } : null};
    });
    CH.scatterMap(c, {sectors: MAPA.sectors, units: units, layers: [{label: cap(PL.leaves) + ' de ' + PL.short, marks: marks}],
                      hiLabel: X.PF.label + ' · ' + plural(noun),
                      lkLabel: plural(noun) + ' que responden a la ' + PL.leaf + ' elegida',
                      aria: 'Mapa de la investigación con las ' + PL.leaves + ' de ' + PL.name});

    // Reparto por area: retos del plan frente a la investigacion elegida.
    el('h4', 'sub-h', 'Retos e investigación por área', c);
    el('p', 'desc', 'Qué parte de las ' + PL.leaves + ' cae en cada área, frente a qué parte de los ' +
      plural(noun) + ' de ' + PF.label + ' hay en ella. Un área con muchas ' + PL.leaves + ' y poca investigación ' +
      'es una prioridad del plan que la investigación apenas cubre.', c);
    var nMine = 0, mineBy = {}, retoBy = {};
    MAPA.units.forEach(function(u){ if (mine(u)){ nMine++; mineBy[u[2]] = (mineBy[u[2]] || 0) + 1; } });
    P.retos.forEach(function(r){ retoBy[r.s] = (retoBy[r.s] || 0) + 1; });
    var order = MAPA.sectors.slice().sort(function(a, b){
      return ((retoBy[b.id] || 0) - (retoBy[a.id] || 0)) || ((mineBy[b.id] || 0) - (mineBy[a.id] || 0));
    });
    var wrap = el('div', 'tablewrap', null, c), tbl = el('table', 'areas', null, wrap);
    var hr = el('tr', null, null, el('thead', null, null, tbl));
    el('th', null, 'Área', hr);
    el('th', 'c', '% de las ' + PL.leaves, hr);
    el('th', 'c', '% de los ' + plural(noun) + ' de ' + PF.label, hr);
    var tb = el('tbody', null, null, tbl);
    order.forEach(function(s){
      var tr = el('tr', null, null, tb), td = el('td', null, null, tr);
      el('b', null, s.name, td);
      el('span', 'unit-meta', s.topics.slice(0, 3).map(function(t){ return t[0]; }).join(' · '), td);
      var nr = retoBy[s.id] || 0, nu = mineBy[s.id] || 0;
      tr.appendChild(barCell(nr / P.retos.length, pct(nr / P.retos.length) + ' · ' + nr));
      tr.appendChild(barCell(nMine ? nu / nMine : 0, pct(nMine ? nu / nMine : 0) + ' · ' + fmt(nu)));
    });
  }

  // 3. ¿Cuanto trabajo responde a cada reto?
  function renderGrid(X, stats, noun){
    var C = X.C, PL = X.PL;
    var c = card('¿Cuánto trabajo responde a cada ' + PL.leaf + '?',
      'Cada cuadro es una ' + PL.leaf + ' del ' + PL.name + ', todas del mismo tamaño y en el orden del plan; cada ' +
      'punto es un' + (fem(noun) ? 'a ' : ' ') + noun + ' vinculad' + (fem(noun) ? 'a' : 'o') + '. Un cuadro con ' +
      'pocos puntos es una ' + PL.leaf + ' que casi nadie trabaja. Haz clic en un cuadro para ver la lista, o en ' +
      'un punto para ver ' + (fem(noun) ? 'esa ' : 'ese ') + noun + '.');
    var groups = Object.keys(C.on).sort().map(function(on){
      return {key: on, label: C.on[on], cells: Object.keys(C.subs)
        .filter(function(k){ return C.subs[k].o === on; })
        .sort(function(a, b){ return a.localeCompare(b, 'es', {numeric: true}); })
        .map(function(k){
          var st = stats[k];
          return {id: k, label: C.subs[k].l, n2: st.n2, n1: st.n1, dots: st.dots};
        })};
    });
    CH.dotGrid(c, groups, {leaves: PL.leaves, nouns: plural(noun), selected: sel.reto,
                           onCell: selectReto, onDot: function(u){ selectUnit(u); }});
    CH.tableView(c, [PL.level1_long, cap(PL.leaf), 'Relación clara', 'Tangencial'],
      groups.reduce(function(acc, g){
        return acc.concat(g.cells.map(function(x){ return [g.label, x.label, x.n2, x.n1]; }));
      }, []), [0, 0, 1, 1]);
  }

  // Detalle: el reto elegido (sus unidades) o la unidad elegida (sus retos).
  function renderDetail(X, stats, noun){
    var C = X.C, D = X.D, PL = X.PL;
    var box = el('section', 'card detail', null, view); box.id = 'detail';
    function pill(g){ return el('span', 'pill g' + g, g === 2 ? 'clara' : 'tangencial'); }
    function meta(u){ return [u.y || '', u.g || ''].filter(Boolean).join(' · '); }
    if (sel.unit){
      var u = D.units[sel.unit] || {t: sel.unit};
      el('p', 'eyebrow', cap(noun), box);
      el('h3', null, u.t || sel.unit, box);
      if (meta(u)) el('p', 'unit-meta', meta(u), box);
      var rows = (C.units[sel.unit] || []).slice().sort(function(a, b){ return (b[1] - a[1]) || (b[2] - a[2]); });
      el('p', 'desc', rows.length ? 'Responde a ' + rows.length + ' ' + (rows.length === 1 ? PL.leaf : PL.leaves) + ':' :
        'No tiene relación con ninguna ' + PL.leaf + ' del ' + PL.name + '.', box);
      var ul = el('ul', 'links', null, box);
      rows.forEach(function(r){
        var s = C.subs[r[0]]; if (!s) return;
        var li = el('li', null, null, ul);
        li.appendChild(pill(r[1]));
        var b = el('button', 'linkish', s.l, li); b.type = 'button';
        b.addEventListener('click', function(){ selectReto(r[0]); });
        el('span', 'unit-meta', C.on[s.o] || s.o, li);
      });
      return;
    }
    if (!sel.reto){
      el('p', 'note', 'Elige una ' + PL.leaf + ' en el mapa o en los cuadros para ver qué ' + plural(noun) +
        ' la responden.', box);
      return;
    }
    var s = C.subs[sel.reto], st = stats[sel.reto];
    el('p', 'eyebrow', cap(PL.leaf) + ' · ' + (C.on[s.o] || s.o), box);
    el('h3', null, s.l, box);
    el('p', 'desc', st.n2 + ' ' + plural(noun) + ' con relación clara' + (st.n1 ? ' y ' + st.n1 + ' tangenciales' : '') + '.', box);
    if (!st.dots.length){
      el('p', 'note', (fem(noun) ? 'Ninguna ' : 'Ningún ') + noun + ' de ' + X.PF.label + ' responde a esta ' + PL.leaf + '.', box);
      return;
    }
    var wrap = el('div', 'tablewrap', null, box), tbl = el('table', null, null, wrap);
    var hr = el('tr', null, null, el('thead', null, null, tbl));
    el('th', null, cap(noun), hr); el('th', null, 'Relación', hr);
    var tb = el('tbody', null, null, tbl);
    st.dots.forEach(function(d){
      var tr = el('tr', null, null, tb), td = el('td', null, null, tr), u = D.units[d.id] || {};
      var b = el('button', 'linkish', d.t, td); b.type = 'button';
      b.addEventListener('click', function(){ selectUnit(d.id); });
      if (meta(u)) el('span', 'unit-meta', meta(u), td);
      el('td', null, null, tr).appendChild(pill(d.g));
    });
  }

  // --- ayuda («?») ------------------------------------------------------------
  var help = document.getElementById('help');
  document.getElementById('help-open').addEventListener('click', function(){
    renderHelp();
    if (help.showModal) help.showModal(); else help.setAttribute('open', '');
  });
  document.getElementById('help-close').addEventListener('click', function(){
    if (help.close) help.close(); else help.removeAttribute('open');
  });
  function renderHelp(){
    var body = document.getElementById('help-body');
    body.textContent = '';
    if (!loaded[sel.ds]) return;
    var X = ctx(), PL = X.PL, C = X.C, noun = X.DP.noun;
    function sec(title){ var s = el('section', null, null, body); el('h3', null, title, s); return s; }
    var a = sec('Qué se compara');
    el('p', null, 'A la izquierda, ' + X.DP.label.charAt(0).toLowerCase() + X.DP.label.slice(1) + ' (' + fmt(X.D.nu) +
      ' ' + plural(noun) + '). A la derecha, las ' + PL.leaves + ' ' + PL.source + '.', a);
    if (X.PF.extraction_html){
      var p = el('p', null, null, a); p.innerHTML = X.PF.extraction_html;   // texto propio de atlas_profiles.py
    }
    var b = sec('Cómo se vincula cada ' + noun + ' con las ' + PL.leaves);
    el('p', null, 'Primero se buscan las ' + PL.leaves + ' más parecidas a cada ' + noun + ' por su contenido ' +
      '(similitud de embeddings' + (C ? ', desde ' + C.floor : '') + '). Después un modelo de lenguaje' +
      (C && C.judge ? ' (' + C.judge + ')' : '') + ' lee ' + (fem(noun) ? 'la ' : 'el ') + noun + ' y califica cada ' +
      'candidata: 2 = relación clara, 1 = tangencial, 0 = ninguna. Las cifras cuentan las relaciones claras.', b);
    if (PL.validation) el('p', 'note', PL.validation, b);
    if (PL.foreign) el('p', 'note', PL.foreign, b);
    var m = sec('Cómo se arma el mapa');
    el('p', null, MAPA ? 'Un mapa 2D de ' + fmt(MAPA.units.length) + ' proyectos y publicaciones (' +
      MAPA.params.method + ', semilla fija, versión ' + MAPA.version + '). Es el mismo para todos los planes y no ' +
      'cambia al agregar uno. Cada ' + PL.leaf + ' va al promedio, ponderado por similitud, de la posición de sus ' +
      MAPA.params.k + ' unidades (proyectos o publicaciones) más parecidas; las áreas se nombran por sus temas.' :
      'El mapa no está disponible en esta versión.', m);
  }

  // --- arranque ---------------------------------------------------------------
  function start(list){
    MANIFEST = list;
    var q = readSel();
    sel.ds = q.ds; sel.dom = q.dom; sel.plan = q.plan;
    fixSel(); paintQuery(); go();
  }
  if (INLINE){
    var PF = INLINE.profile;
    loaded[PF.id] = INLINE;
    var dom = {}; PF.order.forEach(function(d){ dom[d] = PF.domains[d].tab; });
    var names = {}; PF.plan_order.forEach(function(k){ names[k] = PF.plans[k].short; });
    start([{id: PF.id, label: PF.label, domains: dom, plans: PF.plan_order, plan: PF.plan_default, plan_names: names}]);
  } else {
    fetchJSON('datasets.json').then(function(M){ start(M.datasets); }).catch(function(){
      status(location.protocol === 'file:' ?
        'Abierta desde el disco, el navegador no deja que la página lea sus datos. Abre el archivo ' +
        'único atlas_<dataset>.html, o sirve esta carpeta (python -m http.server).' :
        'No se pudo cargar la lista de datasets (datasets.json).');
    });
  }
})();

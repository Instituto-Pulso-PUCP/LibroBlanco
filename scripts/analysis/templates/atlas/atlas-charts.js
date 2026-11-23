/* Graficos del Atlas Temático: SVG/HTML a mano, sin dependencias.
 *
 * Cada funcion recibe un contenedor y datos ya calculados (atlas.js decide QUE
 * se muestra; aqui solo COMO). Reglas comunes (skill dataviz):
 *   - una sola tinta: el azul PUCP en una rampa ordinal validada
 *     (#93b5e2 -> #4f86cc -> #0f4c97, y #7ea7dc / #0f4c97 para débil /
 *     desarrollada); ningun grafico depende de distinguir colores categoricos;
 *   - marcas finas, ejes y grilla en hairline solida;
 *   - tooltip al pasar el puntero y al enfocar con teclado, valor primero;
 *   - todo texto de los datos entra con textContent;
 *   - cada grafico trae su tabla («Ver los datos como tabla»): el tooltip
 *     nunca es la unica forma de leer un valor.
 */
(function(){
  "use strict";
  var NS = 'http://www.w3.org/2000/svg';

  function h(tag, cls, text, parent){
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  function s(tag, attrs, parent){
    var e = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function(k){ e.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(e);
    return e;
  }
  function clip(text, n){
    text = String(text == null ? '' : text);
    return text.length > n ? text.slice(0, n - 1).replace(/[\s,.;:]+$/, '') + '…' : text;
  }
  function niceMax(v){
    if (!(v > 0)) return 1;
    var p = Math.pow(10, Math.floor(Math.log10(v))), m = v / p;
    return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
  }

  // --- tooltip unico --------------------------------------------------------
  var tipEl = null;
  function tip(){
    if (!tipEl){
      tipEl = h('div', 'viz-tip');
      tipEl.setAttribute('role', 'tooltip');
      tipEl.hidden = true;
      document.body.appendChild(tipEl);
    }
    return tipEl;
  }
  // lines: [valor, etiqueta, detalle...]; el primero va destacado.
  function showTip(lines, x, y){
    var t = tip();
    t.textContent = '';
    lines.filter(function(l){ return l != null && l !== ''; }).forEach(function(l, i){
      h('div', i === 0 ? 'v' : (i === 1 ? 'k' : 'd'), l, t);
    });
    t.hidden = false;
    var w = t.offsetWidth, ht = t.offsetHeight;
    var left = Math.min(x + 14, window.innerWidth - w - 8), top = y + 16;
    if (top + ht > window.innerHeight - 8) top = Math.max(8, y - ht - 12);
    t.style.left = Math.max(8, left) + 'px';
    t.style.top = top + 'px';
  }
  function hideTip(){ if (tipEl) tipEl.hidden = true; }
  // Tooltip en un elemento: puntero y teclado muestran lo mismo.
  function bindTip(el, lines, onActive){
    el.addEventListener('pointermove', function(ev){
      showTip(lines(), ev.clientX, ev.clientY); if (onActive) onActive(true);
    });
    el.addEventListener('pointerleave', function(){ hideTip(); if (onActive) onActive(false); });
    el.addEventListener('focus', function(){
      var r = el.getBoundingClientRect();
      showTip(lines(), r.left + r.width / 2, r.bottom); if (onActive) onActive(true);
    });
    el.addEventListener('blur', function(){ hideTip(); if (onActive) onActive(false); });
  }
  function activate(el, fn){
    if (!fn) return;
    el.addEventListener('click', fn);
    el.addEventListener('keydown', function(ev){
      if (ev.key === 'Enter' || ev.key === ' '){ ev.preventDefault(); fn(); }
    });
  }

  // --- tabla gemela -----------------------------------------------------------
  function tableView(box, headers, rows, numeric){
    var det = h('details', 'viz-table', null, box);
    h('summary', null, 'Ver los datos como tabla', det);
    var wrap = h('div', 'tablewrap', null, det), tbl = h('table', null, null, wrap);
    var tr = h('tr', null, null, h('thead', null, null, tbl));
    headers.forEach(function(x, i){ h('th', numeric && numeric[i] ? 'c' : null, x, tr); });
    var tb = h('tbody', null, null, tbl);
    rows.forEach(function(r){
      var row = h('tr', null, null, tb);
      r.forEach(function(v, i){ h('td', numeric && numeric[i] ? 'num' : null, v, row); });
    });
    return det;
  }

  // --- mapa de cobertura ------------------------------------------------------
  // Una celda por hoja del plan, agrupadas por nivel 1. Hueca = sin desarrollo,
  // clara = débil, oscura = desarrollada. Ver a la vez lo cubierto y los huecos.
  //   groups: [{key, label, cells: [{id, label, sub, cov, lines: [...]}]}]
  //   o: {covText: {desarrollada, debil, sin_desarrollo}, onClick(id), noun}
  var COV_ORDER = {desarrollada: 0, debil: 1, sin_desarrollo: 2};
  function coverageGrid(box, groups, o){
    var legend = h('div', 'viz-legend', null, box);
    ['desarrollada', 'debil', 'sin_desarrollo'].forEach(function(c){
      var it = h('span', 'it', null, legend);
      h('i', 'sw cov-' + c, null, it);
      h('span', null, o.covText[c], it);
    });
    var grid = h('div', 'cgrid', null, box);
    groups.forEach(function(g){
      var blk = h('div', 'cgroup', null, grid);
      h('h4', null, g.label, blk);
      var n = {desarrollada: 0, debil: 0, sin_desarrollo: 0};
      g.cells.forEach(function(c){ n[c.cov]++; });
      h('p', 'cg-sum', n.desarrollada + ' desarrolladas · ' + n.debil + ' débiles · ' +
        n.sin_desarrollo + ' sin desarrollo', blk);
      var cells = h('div', 'cells', null, blk);
      g.cells.slice().sort(function(a, b){
        return (COV_ORDER[a.cov] - COV_ORDER[b.cov]) || (b.eq - a.eq);
      }).forEach(function(c){
        var b = h('button', 'cell cov-' + c.cov, null, cells);
        b.type = 'button';
        b.setAttribute('aria-label', c.label + ': ' + o.covText[c.cov] + '. ' + c.lines.join('. '));
        bindTip(b, function(){ return [o.covText[c.cov]].concat([c.label], c.lines); });
        if (o.onClick) b.addEventListener('click', function(){ hideTip(); o.onClick(c.id); });
      });
    });
  }

  // --- flujo de temas a objetivos (sankey de dos columnas) ------------------
  //   o: {left: [{id, label, value}], right: [{id, label, value}],
  //       flows: [{s, t, v}], fmt(v), onLeft(id), onRight(id), leftName, rightName, aria}
  function sankey(box, o){
    var wrap = h('div', 'viz-scroll', null, box);
    var W = 900, labL = 300, labR = 250, nodeW = 10, gap = 8;
    var n = Math.max(o.left.length, o.right.length);
    var H = Math.max(300, n * 30 + 20);
    var total = o.flows.reduce(function(a, f){ return a + f.v; }, 0) || 1;
    var x0 = labL, x1 = W - labR - nodeW;
    var svg = s('svg', {viewBox: '0 0 ' + W + ' ' + H, width: '100%', role: 'img',
                        'aria-label': o.aria, class: 'sankey'}, wrap);
    function place(nodes){
      var k = (H - 20 - gap * (nodes.length - 1)) / total, y = 10, pos = {};
      nodes.forEach(function(nd){
        var hgt = Math.max(2, nd.value * k);
        pos[nd.id] = {y: y, h: hgt, k: k, off: 0};
        y += hgt + gap;
      });
      return pos;
    }
    var L = place(o.left), R = place(o.right);
    var orderL = {}, orderR = {};
    o.left.forEach(function(nd, i){ orderL[nd.id] = i; });
    o.right.forEach(function(nd, i){ orderR[nd.id] = i; });
    var flows = o.flows.slice().sort(function(a, b){
      return (orderL[a.s] - orderL[b.s]) || (orderR[a.t] - orderR[b.t]); });
    var ribbons = s('g', {class: 'ribbons'}, svg), paths = [];
    flows.forEach(function(f){
      var a = L[f.s], b = R[f.t];
      if (!a || !b) return;
      var hgt = f.v * a.k, sy = a.y + a.off, ty;
      a.off += hgt;
      paths.push({f: f, sy: sy, hgt: hgt});
    });
    // en el destino, apiladas en el orden de la columna izquierda
    paths.slice().sort(function(p, q){
      return (orderR[p.f.t] - orderR[q.f.t]) || (orderL[p.f.s] - orderL[q.f.s]);
    }).forEach(function(p){
      var b = R[p.f.t]; p.ty = b.y + b.off; b.off += p.hgt;
    });
    var xa = x0 + nodeW, xb = x1, mx = (xa + xb) / 2;
    paths.forEach(function(p){
      var d = 'M' + xa + ',' + p.sy + 'C' + mx + ',' + p.sy + ' ' + mx + ',' + p.ty + ' ' + xb + ',' + p.ty +
              'L' + xb + ',' + (p.ty + p.hgt) + 'C' + mx + ',' + (p.ty + p.hgt) + ' ' + mx + ',' +
              (p.sy + p.hgt) + ' ' + xa + ',' + (p.sy + p.hgt) + 'Z';
      var el = s('path', {d: d, class: 'rib'}, ribbons);
      p.el = el;
      var ln = o.left[orderL[p.f.s]], rn = o.right[orderR[p.f.t]];
      bindTip(el, function(){ return [o.fmt(p.f.v), ln.label + ' → ' + rn.label]; },
              function(on){ svg.classList.toggle('hl', on); el.classList.toggle('on', on); });
    });
    function highlight(side, id, on){
      svg.classList.toggle('hl', on);
      paths.forEach(function(p){
        p.el.classList.toggle('on', on && (side === 'L' ? p.f.s : p.f.t) === id);
      });
    }
    function node(side, nd, pos){
      var g = s('g', {class: 'node', tabindex: 0, role: 'button',
                      'aria-label': nd.label + ': ' + o.fmt(nd.value)}, svg);
      var x = side === 'L' ? x0 : x1;
      s('rect', {x: x, y: pos.y, width: nodeW, height: pos.h, rx: 2}, g);
      // area de acierto mas grande que la barra: incluye la etiqueta
      var hitX = side === 'L' ? 0 : x1, hitW = side === 'L' ? x0 + nodeW : W - x1;
      s('rect', {x: hitX, y: pos.y - gap / 2, width: hitW, height: pos.h + gap, class: 'hit'}, g);
      var t = s('text', {x: side === 'L' ? x - 8 : x + nodeW + 8, y: pos.y + pos.h / 2,
                         'text-anchor': side === 'L' ? 'end' : 'start', 'dominant-baseline': 'middle'}, g);
      t.textContent = clip(nd.label, side === 'L' ? 44 : 34);
      bindTip(g, function(){ return [o.fmt(nd.value), nd.label, nd.note]; },
              function(on){ highlight(side, nd.id, on); });
      activate(g, side === 'L' ? (o.onLeft && function(){ hideTip(); o.onLeft(nd.id); })
                               : (o.onRight && function(){ hideTip(); o.onRight(nd.id); }));
    }
    o.left.forEach(function(nd){ node('L', nd, L[nd.id]); });
    o.right.forEach(function(nd){ node('R', nd, R[nd.id]); });
  }

  // --- evolucion por año: multiplos pequeños, misma escala -----------------
  //   o: {panels: [{id, label, values: {año: v}}], years: [lo, hi], fmt(v), onPanel(id)}
  function smallMultiples(box, o){
    var grid = h('div', 'smgrid', null, box);
    var lo = o.years[0], hi = o.years[1];
    var max = 0;
    o.panels.forEach(function(p){
      for (var y = lo; y <= hi; y++) max = Math.max(max, p.values[y] || 0);
    });
    var ymax = niceMax(max);
    var W = 320, H = 150, pl = 34, pr = 12, pt = 12, pb = 22;
    var iw = W - pl - pr, ih = H - pt - pb;
    function X(y){ return pl + (hi === lo ? iw / 2 : (y - lo) / (hi - lo) * iw); }
    function Y(v){ return pt + ih - v / ymax * ih; }
    o.panels.forEach(function(p){
      var card = h('div', 'sm', null, grid);
      h('h5', null, p.label, card);
      var tot = 0, peak = lo;
      for (var y = lo; y <= hi; y++){
        tot += p.values[y] || 0;
        if ((p.values[y] || 0) > (p.values[peak] || 0)) peak = y;
      }
      h('p', 'sm-sum', o.fmt(tot) + ' en total', card);
      var svg = s('svg', {viewBox: '0 0 ' + W + ' ' + H, width: '100%', role: 'img',
                          'aria-label': p.label + ': ' + o.fmt(tot) + ' entre ' + lo + ' y ' + hi}, card);
      [0, ymax / 2, ymax].forEach(function(v){
        s('line', {x1: pl, x2: W - pr, y1: Y(v), y2: Y(v), class: v ? 'grid' : 'axis'}, svg);
        var t = s('text', {x: pl - 6, y: Y(v), 'text-anchor': 'end', 'dominant-baseline': 'middle', class: 'tick'}, svg);
        t.textContent = +v.toFixed(1);
      });
      var xt = hi - lo > 6 ? [lo, Math.round((lo + hi) / 2), hi] : (hi === lo ? [lo] : [lo, hi]);
      xt.forEach(function(y){
        var t = s('text', {x: X(y), y: H - 6, 'text-anchor': 'middle', class: 'tick'}, svg);
        t.textContent = y;
      });
      var pts = [];
      for (y = lo; y <= hi; y++) pts.push([X(y), Y(p.values[y] || 0)]);
      var line = pts.map(function(q, i){ return (i ? 'L' : 'M') + q[0].toFixed(1) + ',' + q[1].toFixed(1); }).join('');
      s('path', {d: line + 'L' + X(hi) + ',' + Y(0) + 'L' + X(lo) + ',' + Y(0) + 'Z', class: 'area'}, svg);
      s('path', {d: line, class: 'line'}, svg);
      // etiqueta selectiva: solo el pico
      if (p.values[peak]){
        s('circle', {cx: X(peak), cy: Y(p.values[peak]), r: 4, class: 'dot'}, svg);
        var pk = s('text', {x: Math.min(Math.max(X(peak), pl + 16), W - pr - 16), y: Y(p.values[peak]) - 9,
                            'text-anchor': 'middle', class: 'peak'}, svg);
        pk.textContent = (+p.values[peak].toFixed(1)) + ' (' + peak + ')';
      }
      // cruz que sigue al puntero y se engancha al año mas cercano
      var cross = s('line', {y1: pt, y2: pt + ih, class: 'cross', visibility: 'hidden'}, svg);
      var cdot = s('circle', {r: 4, class: 'dot', visibility: 'hidden'}, svg);
      var hit = s('rect', {x: pl, y: pt, width: iw, height: ih, class: 'hit', tabindex: 0}, svg);
      var cur = hi;
      function at(year){
        cur = year;
        var v = p.values[year] || 0;
        cross.setAttribute('x1', X(year)); cross.setAttribute('x2', X(year));
        cross.setAttribute('visibility', 'visible');
        cdot.setAttribute('cx', X(year)); cdot.setAttribute('cy', Y(v));
        cdot.setAttribute('visibility', 'visible');
        return [o.fmt(v), p.label, String(year)];
      }
      function off(){ cross.setAttribute('visibility', 'hidden'); cdot.setAttribute('visibility', 'hidden'); hideTip(); }
      hit.addEventListener('pointermove', function(ev){
        var r = svg.getBoundingClientRect(), sx = (ev.clientX - r.left) / r.width * W;
        var year = Math.round(lo + (sx - pl) / iw * (hi - lo));
        year = Math.min(hi, Math.max(lo, year));
        showTip(at(year), ev.clientX, ev.clientY);
      });
      hit.addEventListener('pointerleave', off);
      hit.addEventListener('blur', off);
      hit.addEventListener('keydown', function(ev){
        if (ev.key !== 'ArrowLeft' && ev.key !== 'ArrowRight') return;
        ev.preventDefault();
        var year = Math.min(hi, Math.max(lo, cur + (ev.key === 'ArrowRight' ? 1 : -1)));
        var r = svg.getBoundingClientRect();
        showTip(at(year), r.left + X(year) / W * r.width, r.top + Y(p.values[year] || 0) / H * r.height);
      });
      hit.addEventListener('focus', function(){
        var r = svg.getBoundingClientRect();
        showTip(at(cur), r.left + X(cur) / W * r.width, r.top + Y(p.values[cur] || 0) / H * r.height);
      });
      if (o.onPanel){
        var more = h('button', 'linkish sm-go', 'Ver en el plan', card);
        more.type = 'button';
        more.addEventListener('click', function(){ o.onPanel(p.id); });
      }
    });
  }

  // --- mapa de calor (filas x columnas, cada fila suma 100 %) ---------------
  //   o: {rows: [{id, label, note}], cols: [{id, label, full}], val(r, c) -> 0..1,
  //       fmt(v), rowName}
  var RAMP = [[0x93, 0xb5, 0xe2], [0x4f, 0x86, 0xcc], [0x0f, 0x4c, 0x97]];
  function rampColor(t){
    t = Math.max(0, Math.min(1, t));
    var seg = t <= 0.5 ? 0 : 1, u = seg ? (t - 0.5) * 2 : t * 2;
    var a = RAMP[seg], b = RAMP[seg + 1];
    return 'rgb(' + a.map(function(x, i){ return Math.round(x + (b[i] - x) * u); }).join(',') + ')';
  }
  function heatmap(box, o){
    var max = 0;
    o.rows.forEach(function(r){ o.cols.forEach(function(c){ max = Math.max(max, o.val(r, c)); }); });
    // tope de la escala: el maximo redondeado a la decena de % siguiente
    var top = Math.min(1, Math.ceil(max * 10 + 1e-9) / 10) || 1;
    var legend = h('div', 'viz-legend', null, box);
    var it = h('span', 'it', null, legend);
    h('span', 'tick', '0 %', it);
    h('i', 'grad', null, it);
    h('span', 'tick', Math.round(top * 100) + ' %', it);
    var it2 = h('span', 'it', null, legend);
    h('i', 'sw heat-zero', null, it2);
    h('span', null, 'nada', it2);
    var wrap = h('div', 'tablewrap', null, box), tbl = h('table', 'heat', null, wrap);
    var tr = h('tr', null, null, h('thead', null, null, tbl));
    h('th', null, o.rowName, tr);
    o.cols.forEach(function(c){ var th = h('th', 'hc', c.label, tr); th.title = c.full || c.label; });
    var tb = h('tbody', null, null, tbl);
    o.rows.forEach(function(r){
      var row = h('tr', null, null, tb);
      var th = h('th', null, null, row);
      h('span', 'rl', r.label, th);
      if (r.note) h('span', 'unit-meta', r.note, th);
      o.cols.forEach(function(c){
        var v = o.val(r, c), td = h('td', 'hcell', null, row);
        var sw = h('span', v > 0 ? 'hsw' : 'hsw heat-zero', null, td);
        if (v > 0) sw.style.background = rampColor(v / top);
        td.tabIndex = 0;
        td.setAttribute('aria-label', r.label + ', ' + (c.full || c.label) + ': ' + o.fmt(v));
        bindTip(td, function(){ return [o.fmt(v), r.label, c.full || c.label]; });
      });
    });
  }

  // --- lista de medidores -----------------------------------------------------
  //   rows: [{id, label, value (0..1), text, current, onClick}]
  function meterList(box, rows){
    var list = h('div', 'meters', null, box);
    rows.forEach(function(r){
      var row = h(r.onClick ? 'button' : 'div', 'meter' + (r.current ? ' cur' : ''), null, list);
      if (r.onClick){ row.type = 'button'; row.addEventListener('click', r.onClick); }
      var nm = h('span', 'm-nm', null, row);
      h('b', null, r.label, nm);
      if (r.sub) h('span', 'unit-meta', r.sub, nm);
      var tr = h('span', 'm-track', null, row);
      var fill = h('i', null, null, tr);
      fill.style.width = (Math.max(0, Math.min(1, r.value)) * 100).toFixed(1) + '%';
      h('span', 'm-val', r.text, row);
    });
  }

  window.AtlasCharts = {coverageGrid: coverageGrid, sankey: sankey, smallMultiples: smallMultiples,
                        heatmap: heatmap, meterList: meterList, tableView: tableView,
                        hideTip: hideTip, clip: clip};
})();

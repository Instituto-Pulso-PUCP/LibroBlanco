/* Graficos del Atlas: SVG/HTML a mano, sin dependencias.
 *
 * Cada funcion recibe un contenedor y datos ya calculados (atlas.js decide QUE
 * se muestra; aqui solo COMO). Reglas comunes (skill dataviz):
 *   - una sola tinta: el azul PUCP en una rampa ordinal; donde hay capas (varios
 *     planes en el mapa), la forma del marcador las distingue, no solo el color;
 *   - marcas finas, contornos en hairline;
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
  function bindTip(el, lines){
    el.addEventListener('pointermove', function(ev){ showTip(lines(), ev.clientX, ev.clientY); });
    el.addEventListener('pointerleave', hideTip);
    el.addEventListener('focus', function(){
      var r = el.getBoundingClientRect();
      showTip(lines(), r.left + r.width / 2, r.bottom);
    });
    el.addEventListener('blur', hideTip);
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

  // --- cuanto trabajo responde a cada reto ------------------------------------
  // Una celda del mismo tamaño por hoja del plan, agrupadas por nivel 1 y en el
  // orden del plan (cada reto siempre en el mismo lugar), con un punto por
  // unidad vinculada: lleno = relacion clara, hueco = tangencial. Una celda
  // punteada es un reto sin ninguna relacion clara.
  //   groups: [{key, label, cells: [{id, label, n2, n1, dots: [{id, g, t}]}]}]
  //   o: {selected, onCell(id), onDot(id), maxDots, nouns, leaves}
  function dotGrid(box, groups, o){
    var max = o.maxDots || 120;
    var legend = h('div', 'viz-legend', null, box);
    [['dot g2', 'relación clara'], ['dot g1', 'tangencial'], ['dcell-empty-sw', 'ninguna relación clara']]
      .forEach(function(x){
        var it = h('span', 'it', null, legend);
        h('i', x[0], null, it); h('span', null, x[1], it);
      });
    var grid = h('div', 'dgrid', null, box);
    groups.forEach(function(g){
      var blk = h('div', 'dgroup', null, grid);
      h('h4', null, g.label, blk);
      var empty = g.cells.filter(function(c){ return !c.n2; }).length;
      h('p', 'cg-sum', g.cells.length + ' ' + o.leaves + ' · ' + empty + ' sin ' + o.nouns +
        ' con relación clara', blk);
      var cells = h('div', 'dcells', null, blk);
      g.cells.forEach(function(c){
        var cell = h('div', 'dcell' + (c.n2 ? '' : ' empty') + (c.id === o.selected ? ' sel' : ''), null, cells);
        var head = h('button', 'dc-h', null, cell);
        head.type = 'button';
        head.setAttribute('aria-pressed', String(c.id === o.selected));
        h('span', 'dc-l', c.label, head);
        var ct = h('span', 'dc-n', null, head);
        h('b', 'num', String(c.n2), ct);
        h('span', null, ' clara' + (c.n2 === 1 ? '' : 's') + (c.n1 ? ' · ' + c.n1 + ' tang.' : ''), ct);
        head.setAttribute('aria-label', c.label + ': ' + c.n2 + ' ' + o.nouns + ' con relación clara, ' +
          c.n1 + ' tangenciales');
        if (o.onCell) head.addEventListener('click', function(){ hideTip(); o.onCell(c.id); });
        var dots = h('div', 'dc-dots', null, cell);
        dots.setAttribute('aria-hidden', 'true');
        c.dots.slice(0, max).forEach(function(d){
          var i = h('i', 'dot g' + d.g, null, dots);
          i.dataset.u = d.id;
        });
        if (c.dots.length > max) h('span', 'dc-more', '+' + (c.dots.length - max), dots);
        var byId = {};
        c.dots.forEach(function(d){ byId[d.id] = d; });
        dots.addEventListener('pointermove', function(ev){
          var d = ev.target.dataset && byId[ev.target.dataset.u];
          if (d) showTip([d.g === 2 ? 'Relación clara' : 'Tangencial', d.t, c.label], ev.clientX, ev.clientY);
          else hideTip();
        });
        dots.addEventListener('pointerleave', hideTip);
        if (o.onDot) dots.addEventListener('click', function(ev){
          var d = ev.target.dataset && byId[ev.target.dataset.u];
          if (d){ hideTip(); o.onDot(d.id, c.id); }
        });
      });
    });
  }

  // --- mapa de la investigacion con retos encima ----------------------------------
  // Fondo fijo: sectores (envolventes) y un punto por unidad; encima, un
  // marcador por reto de cada capa (plan).
  //   o: {sectors: [{id, name, hull, cx, cy}],
  //       units: [{x, y, cls}]   cls: '' (fondo) | 'hi' (universo elegido) | 'lk' (vinculada al reto elegido)
  //       layers: [{label, marks: [{x, y, far, sel, lines, onClick}]}], aria}
  var SHAPES = ['circle', 'square', 'diamond', 'triangle'];
  function mark(shape, x, y, r, parent){
    if (shape === 'square') return s('rect', {x: x - r * .9, y: y - r * .9, width: r * 1.8, height: r * 1.8}, parent);
    if (shape === 'diamond') return s('path', {d: 'M' + x + ',' + (y - r * 1.25) + 'L' + (x + r * 1.25) + ',' + y +
      'L' + x + ',' + (y + r * 1.25) + 'L' + (x - r * 1.25) + ',' + y + 'Z'}, parent);
    if (shape === 'triangle') return s('path', {d: 'M' + x + ',' + (y - r * 1.3) + 'L' + (x + r * 1.2) + ',' +
      (y + r * .9) + 'L' + (x - r * 1.2) + ',' + (y + r * .9) + 'Z'}, parent);
    return s('circle', {cx: x, cy: y, r: r}, parent);
  }
  function scatterMap(box, o){
    var W = 1000, PAD = 40, SC = W - 2 * PAD;
    function X(v){ return +(PAD + v * SC).toFixed(1); }
    var legend = h('div', 'viz-legend', null, box);
    function unitSw(cls, text){
      var it = h('span', 'it', null, legend);
      var sw = s('svg', {width: 12, height: 12, viewBox: '0 0 12 12', 'class': 'mk-sw rmap'}, it);
      s('circle', {cx: 6, cy: 6, r: 3.5, 'class': 'u ' + cls}, sw);
      h('span', null, text, it);
    }
    if (o.hiLabel) unitSw('hi', o.hiLabel);
    unitSw('', 'el resto de la investigación');
    if (o.units.some(function(u){ return u.cls === 'lk'; })) unitSw('lk', o.lkLabel || 'vinculadas al reto elegido');
    o.layers.forEach(function(l, k){
      var it = h('span', 'it', null, legend);
      var sw = s('svg', {width: 14, height: 14, viewBox: '0 0 14 14', 'class': 'mk-sw'}, it);
      mark(SHAPES[k % 4], 7, 7, 4.5, sw).setAttribute('class', 'mk l' + k);
      h('span', null, l.label, it);
    });
    if (o.layers.some(function(l){ return l.marks.some(function(m){ return m.far; }); })){
      var it2 = h('span', 'it', null, legend);
      var sw2 = s('svg', {width: 14, height: 14, viewBox: '0 0 14 14', 'class': 'mk-sw'}, it2);
      s('circle', {cx: 7, cy: 7, r: 4.5, 'class': 'mk far'}, sw2);
      h('span', null, 'lejos de toda la investigación', it2);
    }
    var wrap = h('div', 'rmap-wrap', null, box);
    var svg = s('svg', {viewBox: '0 0 ' + W + ' ' + W, 'class': 'rmap', role: 'img', 'aria-label': o.aria}, wrap);
    var gs = s('g', {'class': 'secs'}, svg);
    o.sectors.forEach(function(sec){
      s('polygon', {points: sec.hull.map(function(p){ return X(p[0]) + ',' + X(p[1]); }).join(' '),
                    'class': 'sec'}, gs);
    });
    // Fondo primero, el universo elegido encima y las vinculadas al final.
    var gu = s('g', {'class': 'units'}, svg);
    ['', 'hi', 'lk'].forEach(function(cls){
      o.units.forEach(function(u){
        if (u.cls !== cls) return;
        s('circle', {cx: X(u.x), cy: X(u.y), r: cls === 'lk' ? 4.2 : 2.6, 'class': 'u' + (cls ? ' ' + cls : '')}, gu);
      });
    });
    var gl = s('g', {'class': 'sec-labels'}, svg);
    o.sectors.forEach(function(sec){
      var t = s('text', {x: X(sec.cx), y: X(sec.cy), 'class': 'sec-l', 'text-anchor': 'middle'}, gl);
      t.textContent = clip(sec.name, 34);
    });
    o.layers.forEach(function(l, k){
      var g = s('g', {'class': 'marks'}, svg);
      l.marks.slice().sort(function(a, b){ return (a.sel ? 1 : 0) - (b.sel ? 1 : 0); }).forEach(function(m){
        var el = mark(SHAPES[k % 4], X(m.x), X(m.y), m.sel ? 10 : 7, g);
        el.setAttribute('class', 'mk l' + k + (m.far ? ' far' : '') + (m.sel ? ' sel' : ''));
        el.setAttribute('tabindex', '0');
        el.setAttribute('role', 'button');
        el.setAttribute('aria-label', m.lines.filter(Boolean).join('. '));
        bindTip(el, function(){ return m.lines; });
        activate(el, m.onClick ? function(){ hideTip(); m.onClick(); } : null);
      });
    });
  }

  window.AtlasCharts = {dotGrid: dotGrid, scatterMap: scatterMap, tableView: tableView,
                        hideTip: hideTip, clip: clip};
})();

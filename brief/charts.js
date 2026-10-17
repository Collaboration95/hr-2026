/* #paths, #phases, #benchmarks: inline SVG charts. No chart library. Every figure comes from data.js (sources named in the page). */
(() => {
  const { $, $$, h, fmt, esc, seg, tip, bindTip } = UI;
  const REDUCE = Brief.REDUCE;
  const C = { base: '#8A90A3', pen: '#2F45FF', penDeep: '#1E2FD0', ink: '#0F1222', ink2: '#2B3046', muted: '#555B70', rule: '#D6DCC8', rule2: '#C0C8AD', track: '#E3E8D8', sheet: '#F9FAF3', proof: '#4D7C0F' };
  const GRP = { base: ['Original layers', C.base], new: ['New boundaries · any plot', C.pen], reg: ['Registered plots only', C.penDeep] };

  function responsive(el, render) {
    let last = 0;
    const run = () => { const w = Math.floor(el.clientWidth); if (w < 160 || w === last) return; last = w; render(w); };
    new ResizeObserver(run).observe(el); run();
    return () => { last = 0; run(); };
  }
  const svg = (w, hgt, label) => h('svg', { width: w, height: hgt, viewBox: `0 0 ${w} ${hgt}`, role: 'img', 'aria-label': label });
  const txt = (x, y, s, o = {}) => h('text', { x, y, 'font-size': o.size || 12, fill: o.fill || C.ink2, 'text-anchor': o.anchor || 'start', 'font-weight': o.weight || 500, 'dominant-baseline': o.base || 'middle', style: 'font-family:var(--f-mono)' }, s);
  const tween = (ms, fn) => { if (REDUCE) { fn(1); return; } const t0 = performance.now(); const tick = now => { const t = Math.max(0, Math.min(1, (now - t0) / ms)); fn(1 - Math.pow(1 - t, 3)); if (t < 1) requestAnimationFrame(tick); }; requestAnimationFrame(tick); };
  const tableOf = (head, rows) => `<div class="tbl"><table class="dt"><thead><tr>${head.map((x, i) => `<th class="${i ? 'r' : ''}">${x}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map((x, i) => `<td class="${i ? 'r' : ''}">${x}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  const onView = (el, fn) => { if (REDUCE || !('IntersectionObserver' in window)) { fn(); return; } const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { io.disconnect(); fn(); } }, { threshold: 0.3 }); io.observe(el); };

  /* ================================================================ #paths: log-scale ladder */
  (() => {
    const root = $('#br-paths'); if (!root) return;
    const host = $('#br-ladder');
    const defs = {
      hot: { unit: 'µs per plot', get: p => p.perPlot, lo: 0.1, hi: 300, ticks: [0.1, 1, 10, 100], fmtV: v => v + ' µs', mult: p => p.x, def: '<b>Hot.</b> The layer is loaded and the code is warm. One pass over the 17 supplied plots is timed and divided by 17: the per-plot cost once the layer is local.' },
      cold: { unit: 'ms, load + 17 plots', get: p => p.cold, lo: 0.1, hi: 40, ticks: [0.1, 1, 10], fmtV: v => (v >= 10 ? v.toFixed(1) : v.toFixed(v >= 1 ? 2 : 3)) + ' ms', mult: p => p.xc || '', def: '<b>Fresh process.</b> A new Python process loads the layer and answers the 17 plots. Imports are done first; interpreter start-up is not counted.' },
      e2e: { unit: 'ms, process start to answer', get: p => p.e2e, lo: 10, hi: 200, ticks: [10, 100], fmtV: v => v.toFixed(1) + ' ms', mult: p => p.xe || '', def: '<b>End-to-end.</b> Python is launched from scratch and prints the answer. Includes interpreter start-up (about 14.6 ms) and importing NumPy (about 25 ms); an empty harness child already costs 20.1 ms.' },
    };
    let clock = 'hot', state = null;
    const P = BR.paths;
    const order = ['base', 'new', 'reg'];
    function build(W) {
      const compact = W < 620, labelW = compact ? 0 : Math.min(330, Math.round(W * .36)), rightW = compact ? 118 : 250;
      const x0 = compact ? 6 : labelW + 12, x1 = W - rightW;
      const rowH = compact ? 50 : 36, ghead = 30;
      let y = 8; const rows = [];
      order.forEach(g => { rows.push({ type: 'g', g, y }); y += ghead; P.filter(p => p.grp === g).forEach(p => { rows.push({ type: 'p', p, y: y + rowH / 2 }); y += rowH; }); y += 4; });
      const H = y + 36;
      const s = svg(W, H, 'Log-scale ladder of query paths for the 17 plots on the selected clock');
      const refs = [];
      /* axis group is rebuilt per clock */
      const axis = h('g', {}), refLine = h('g', {});
      s.append(axis, refLine);
      rows.forEach(r => {
        if (r.type === 'g') {
          s.append(h('rect', { x: 0, y: r.y + 5, width: 10, height: 10, rx: 2, fill: GRP[r.g][1] }), txt(18, r.y + 10, GRP[r.g][0].toUpperCase(), { size: 11, weight: 600, fill: C.muted }));
          if (r.g !== 'base') s.append(h('line', { x1: 0, x2: W, y1: r.y - 2, y2: r.y - 2, stroke: C.rule }));
          return;
        }
        const p = r.p, col = GRP[p.grp][1], lab = h('g', {});
        const ly = compact ? r.y - 14 : r.y;
        lab.append(txt(compact ? 6 : 4, ly, p.id, { weight: 700, size: 13, fill: C.ink }), txt((compact ? 6 : 4) + 40, ly, compact ? p.short : p.name, { size: compact ? 11 : 11.5, fill: C.muted }));
        const stem = h('line', { x1: x0, x2: x0, y1: compact ? r.y + 6 : r.y, y2: compact ? r.y + 6 : r.y, stroke: col, 'stroke-width': 2, 'stroke-linecap': 'round' });
        const cy = compact ? r.y + 6 : r.y;
        const dot = h('circle', { cx: x0, cy, r: 6, fill: col, stroke: C.sheet, 'stroke-width': 2 });
        const val = txt(x0, cy, '', { size: 12.5, weight: 600, fill: C.ink });
        const mult = txt(x0, compact ? ly : cy, '', { size: 12.5, weight: 700, fill: col, anchor: compact ? 'end' : 'start' });
        const hit = h('rect', { x: 0, y: r.y - rowH / 2, width: W, height: rowH, fill: 'transparent', tabindex: 0, 'aria-label': `${p.id} ${p.name}` });
        const g = h('g', {}, hit, lab, stem, dot, val, mult);
        s.append(g); refs.push({ p, stem, dot, val, mult, cy, hit });
        bindTip(hit, () => `<b>${p.id}</b> ${esc(p.name)}<br>hot ${p.perPlot} µs per plot (17-plot batch ${p.hot} ms)<br>fresh process ${p.cold} ms · end-to-end ${p.e2e} ms<br>peak memory ${p.rss} MB${p.note ? '<br><i>' + p.note + '</i>' : ''}`);
      });
      const axisY = H - 24;
      return { W, H, s, x0, x1, refs, axis, refLine, axisY, compact };
    }
    const xOf = (st, d, v) => st.x0 + (Math.log10(v) - Math.log10(d.lo)) / (Math.log10(d.hi) - Math.log10(d.lo)) * (st.x1 - st.x0);
    function apply(st, d, t, prev) {
      st.axis.replaceChildren(); st.refLine.replaceChildren();
      st.axis.append(h('line', { x1: st.x0, x2: st.x1, y1: st.axisY, y2: st.axisY, stroke: C.rule2 }));
      d.ticks.forEach(v => {
        const x = xOf(st, d, v);
        st.axis.append(h('line', { x1: x, x2: x, y1: 8, y2: st.axisY, stroke: C.rule }), txt(x, st.axisY + 14, v < 1 ? String(v) : fmt(v), { size: 11, anchor: 'middle', fill: C.muted }));
      });
      st.axis.append(txt(st.x1, st.axisY + 14 + 14, d.unit + ' · log scale', { size: 11, anchor: 'end', fill: C.muted }));
      const p0 = P[0], px = xOf(st, d, d.get(p0));
      st.refLine.append(h('line', { x1: px, x2: px, y1: 8, y2: st.axisY, stroke: C.ink, 'stroke-width': 1, opacity: .45 }), txt(px, 2, 'P0', { size: 10.5, anchor: 'middle', weight: 700, fill: C.ink }));
      st.refs.forEach(r => {
        const to = xOf(st, d, d.get(r.p)), from = prev ? prev.get(r.p.id) : st.x0, x = from + (to - from) * t;
        r.stem.setAttribute('x2', x); r.dot.setAttribute('cx', x);
        r.val.setAttribute('x', x + 12); r.val.textContent = d.fmtV(d.get(r.p));
        const m = d.mult(r.p);
        r.mult.setAttribute('x', st.compact ? st.W - 4 : x + 12 + 74); r.mult.textContent = m && r.p.id !== 'P0' ? `${m} vs P0${r.p.note && clock === 'hot' && !st.compact ? ' · ' + r.p.note : ''}` : (r.p.id === 'P0' ? 'baseline' : '');
        if (r.p.id === 'P0') r.mult.setAttribute('fill', C.muted); else r.mult.setAttribute('fill', GRP[r.p.grp][1]);
      });
    }
    const posOf = (st, d) => new Map(st.refs.map(r => [r.p.id, xOf(st, d, d.get(r.p))]));
    function render(W) {
      state = build(W); host.replaceChildren(state.s);
      const d = defs[clock]; apply(state, d, 1);
    }
    const redo = responsive(host, render);
    seg($('.br-seg', root), 'clock', v => {
      const prev = state ? posOf(state, defs[clock]) : null; clock = v; const d = defs[v];
      $('#br-clock-def').innerHTML = d.def;
      tween(650, t => apply(state, d, t, prev ? { get: id => prev.get(id) } : null));
    });
    $('#br-clock-def').innerHTML = defs.hot.def;
    /* table of all clocks */
    $('#br-ladder-table').innerHTML = tableOf(['Path', 'Hot, µs per plot', 'Multiple vs P0', 'Fresh process, ms', 'End-to-end, ms', 'Peak memory, MB'],
      P.map(p => [`<b>${p.id}</b> ${esc(p.name)}`, p.perPlot, p.x || '', p.cold + (p.xc ? ` (${p.xc})` : ''), p.e2e + (p.xe ? ` (${p.xe})` : ''), p.rss]));
    /* entrance */
    onView(host, () => { if (!state) return; const d = defs[clock]; tween(900, t => apply(state, d, t)); });
  })();

  /* ================================================================ #phases: line charts */
  (() => {
    const root = $('#br-phases'); if (!root) return;
    const phases = BR.phases;
    const charts = [];
    function lineChart(host, series, ymax, ticks, colors) {
      const draw = W => {
        const H = W < 480 ? 250 : 270, m = { l: 40, r: W < 480 ? 96 : 150, t: 16, b: 34 }, pw = W - m.l - m.r, ph = H - m.t - m.b;
        const s = svg(W, H, 'Line chart of the hot multiple against P0 across the five phases');
        const X = i => m.l + pw * i / (phases.length - 1), Y = v => m.t + ph * (1 - v / ymax);
        ticks.forEach(v => { s.append(h('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: C.rule }), txt(m.l - 8, Y(v), v + '×', { size: 11, anchor: 'end', fill: C.muted })); });
        phases.forEach((p, i) => s.append(txt(X(i), H - 12, W < 480 ? p.replace('Decision layers', 'Start').replace('Phase ', 'P') : p.replace('Decision layers', 'Start'), { size: 11, anchor: 'middle', fill: C.muted })));
        const paths = [];
        series.forEach((se, k) => {
          const col = colors[k], pts = se.v.map((v, i) => v == null ? null : [X(i), Y(v), v, i]).filter(Boolean);
          const path = h('path', { d: pts.map((p, i) => (i ? 'L' : 'M') + p[0] + ' ' + p[1]).join(' '), fill: 'none', stroke: col, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' });
          s.append(path); paths.push(path);
          const last = pts[pts.length - 1];
          s.append(txt(last[0] + 12, last[1] - (k ? 0 : 0), `${se.id} ${last[2]}×`, { size: 12.5, weight: 700, fill: C.ink }));
          pts.forEach(p => {
            const m2 = k ? h('rect', { x: p[0] - 5, y: p[1] - 5, width: 10, height: 10, transform: `rotate(45 ${p[0]} ${p[1]})`, fill: col, stroke: C.sheet, 'stroke-width': 2 }) : h('circle', { cx: p[0], cy: p[1], r: 5.5, fill: col, stroke: C.sheet, 'stroke-width': 2 });
            s.append(m2);
            const hit = h('circle', { cx: p[0], cy: p[1], r: 15, fill: 'transparent', tabindex: 0, 'aria-label': `${se.label}, ${phases[p[3]]}: ${p[2]}×` });
            s.append(hit); bindTip(hit, () => `<b>${esc(se.label)}</b><br>${phases[p[3]]}: ${p[2]}× against P0`);
            if (p[3] === 0 || p === last) s.append(txt(p[0], p[1] - 14, p[2] + '×', { size: 11.5, weight: 600, anchor: 'middle', fill: C.ink2 }));
          });
        });
        host.replaceChildren(s);
        paths.forEach(p => { const L = p.getTotalLength(); p.style.strokeDasharray = L; p.style.strokeDashoffset = 0; p._len = L; });
        host._paths = paths;
      };
      const redo = responsive(host, draw);
      return { host, replay() { (host._paths || []).forEach(p => { p.style.strokeDashoffset = p._len; }); tween(1100, t => (host._paths || []).forEach(p => { p.style.strokeDashoffset = p._len * (1 - t); })); } };
    }
    charts.push(lineChart($('#br-ph-new'), BR.phaseSeries.newb, 18, [0, 5, 10, 15], [C.pen, C.ink2]));
    charts.push(lineChart($('#br-ph-reg'), BR.phaseSeries.reg, 90, [0, 20, 40, 60, 80], [C.pen, C.ink2]));
    $('.replay', root).addEventListener('click', () => charts.forEach(c => c.replay()));
    onView(root, () => charts.forEach(c => c.replay()));
    $('#br-phase-notes').replaceChildren(...BR.phaseNotes.map(([a, b], i) => h('div', { class: 'pn' }, h('small', {}, String(i)), h('b', {}, a), h('span', {}, b))));
    const rows = [['Decision layers', 'Phase 1', 'Phase 2', 'Phase 3', 'Phase 4']];
    const all = [...BR.phaseSeries.newb, ...BR.phaseSeries.reg];
    $('#br-ph-table').innerHTML = tableOf(['Path', ...phases], all.map(se => [esc(se.label), ...se.v.map(v => v == null ? '—' : v + '×')]));
  })();

  /* ================================================================ #benchmarks */
  /* horizontal bars, linear, direct labels */
  function barChart(host, rowsFn, opts = {}) {
    const draw = W => {
      const rows = rowsFn(), compact = W < (opts.compactBelow || 440), labW = compact ? 0 : Math.min(opts.labW || 210, W * .38), rightW = compact ? 120 : 150;
      const rh = compact ? 44 : 32, H = rows.length * rh + 24;
      const s = svg(W, H, opts.label || 'Bar chart');
      const x0 = labW + (compact ? 4 : 10), x1 = W - rightW, max = opts.max || Math.max(...rows.map(r => r.v));
      s.append(h('line', { x1: x0, x2: x0, y1: 4, y2: H - 20, stroke: C.rule2 }));
      rows.forEach((r, i) => {
        const y = 10 + i * rh + rh / 2, bw = Math.max(r.v ? 3 : 0, Math.max(0, x1 - x0) * r.v / max), by = compact ? y + 8 : y;
        const g = h('g', {});
        g.append(txt(compact ? 4 : 2, compact ? y - 10 : y, r.label, { size: 11.5, fill: r.dim ? C.muted : C.ink2, weight: r.bold ? 700 : 500 }));
        g.append(h('rect', { x: x0, y: by - 8, width: 0, height: 16, rx: 0, fill: r.color || C.pen, 'data-w': bw, class: 'bar', opacity: r.dim ? .55 : 1 }));
        g.append(txt(x0 + bw + 8, by, r.text, { size: 12, weight: 600, fill: C.ink }));
        if (r.sub) g.append(txt(x0 + bw + 8, by + 13, r.sub, { size: 10.5, fill: C.muted }));
        const hit = h('rect', { x: 0, y: y - rh / 2, width: W, height: rh, fill: 'transparent' }); g.append(hit);
        if (r.tip) bindTip(hit, () => r.tip);
        s.append(g);
      });
      host.replaceChildren(s);
      const bars = $$('.bar', s); bars.forEach(b => b.setAttribute('width', 0));
      host._bars = bars; (opts.noAnim ? (() => bars.forEach(b => b.setAttribute('width', b.dataset.w))) : () => tween(800, t => bars.forEach(b => b.setAttribute('width', b.dataset.w * t))))();
    };
    return responsive(host, draw);
  }

  /* storage */
  (() => {
    const root = $('#br-store-chart'); if (!root) return;
    const host = $('#br-storage'), ctl = $('#br-storage-ctl');
    const B = BR.bytes; let scope = 'region', showGt = true, showZ = false;
    const pc = (x, base) => (100 * (1 - x / base)).toFixed(1) + '% smaller';
    const regionRows = () => {
      const r = [
        { label: 'Original (4 GeoTIFFs)', v: B.total, text: fmt(B.total) + ' B', color: C.base, tip: 'Hansen treecover2000, lossyear, datamask + JRC 2020 forest chip' },
        { label: 'Lossless v1 (L0)', v: B.retainedL0, text: fmt(B.retainedL0) + ' B', sub: pc(B.retainedL0, B.total), color: C.base, dim: true },
        { label: 'Screening store (L1)', v: B.screenStore, text: fmt(B.screenStore) + ' B', sub: pc(B.screenStore, B.total), color: C.pen },
      ];
      if (showGt) r.push({ label: 'L2 as best GeoTIFF', v: B.bestGeotiffDecision, text: fmt(B.bestGeotiffDecision) + ' B', sub: pc(B.bestGeotiffDecision, B.total), color: C.base, dim: true, tip: 'GTiff ZSTD22 one-strip, standard-format control' });
      if (showZ) r.push({ label: 'L2 as zstd-19 plane', v: B.zstd19Decision, text: fmt(B.zstd19Decision) + ' B', sub: pc(B.zstd19Decision, B.total), color: C.base, dim: true, tip: 'Yardstick: zstd level 19 of the raw uint8 plane, no header' });
      r.push({ label: 'Decision store (L2)', v: B.decisionStore, text: fmt(B.decisionStore) + ' B', sub: pc(B.decisionStore, B.total), color: C.penDeep, bold: true });
      return r;
    };
    const tileRows = () => {
      const [o, z, l1, l2] = BR.tile, mb = b => (b / 1e6).toFixed(1) + ' MB';
      return [
        { label: o.label, v: o.b, text: mb(o.b), color: C.base },
        { label: z.label, v: z.b, text: mb(z.b), sub: '64.7% smaller than original', color: C.base, dim: true },
        { label: l1.label, v: l1.b, text: mb(l1.b), sub: '96.8% smaller · 90.8% vs zstd-19', color: C.pen },
        { label: l2.label, v: l2.b, text: mb(l2.b), sub: '98.0% smaller · 94.5% vs zstd-19', color: C.penDeep, bold: true },
      ];
    };
    const redo = barChart(host, () => scope === 'region' ? regionRows() : tileRows(), { label: 'Storage bars', labW: 160, compactBelow: 400 });
    const mk = (label, get, set) => { const l = h('label', { class: 'br-chk' }, h('input', { type: 'checkbox', checked: get() }), label); l.firstChild.addEventListener('change', e => { set(e.target.checked); redo(); }); return l; };
    function ctls() { ctl.replaceChildren(); if (scope === 'region') ctl.append(mk('Standard GeoTIFF control', () => showGt, v => showGt = v), mk('zstd-19 yardstick', () => showZ, v => showZ = v)); else ctl.append(h('span', { class: 'muted' }, '1.6 billion cells · storage only · zstd-19 yardstick per strip')); }
    ctls();
    seg($('.br-seg', root), 'scope', v => { scope = v; ctls(); redo(); });
  })();

  /* where the original bytes sit */
  (() => {
    const host = $('#br-orig'); if (!host) return;
    const col = { treecover2000: '#2F6B47', lossyear: '#C9A08A', datamask: '#8FA37E', jrc: '#12A362' };
    const bar = h('div', { class: 'bar' }), leg = h('div', { class: 'leg' });
    BR.bytes.originals.forEach(o => {
      const pc = 100 * o.b / BR.bytes.total, seg = h('i', { style: `flex:${o.b} 1 0;background:${col[o.id]};min-width:3px` });
      bar.append(seg); bindTip(seg, () => `<b>${esc(o.label)}</b><br>${fmt(o.b)} B · ${pc.toFixed(1)}%<br>${esc(o.file)}`);
      leg.append(h('span', {}, h('i', { style: `background:${col[o.id]}` }), `${o.label} `, h('b', {}, fmt(o.b) + ' B'), ` · ${pc.toFixed(1)}%`));
    });
    host.append(bar, leg);
  })();

  /* memory and throughput */
  (() => {
    const mem = $('#br-mem'), thr = $('#br-thr'); if (!mem) return;
    barChart(mem, () => BR.paths.map(p => ({ label: `${p.id} ${p.short}`, v: p.rss, text: p.rss + ' MB', color: GRP[p.grp][1], bold: p.id === 'P0', tip: `<b>${p.id}</b> ${esc(p.name)}<br>peak RSS ${p.rss} MB` })), { label: 'Peak memory per path', labW: 170, max: 100 });
    barChart(thr, () => [
      { label: 'P0 v1 query', v: 9300, text: '≈ 9,300 / s', color: C.base },
      { label: 'P4 fast selection', v: 46000, text: '≈ 46,000 / s', sub: '5.0× P0', color: C.pen },
      { label: 'P4B batch evaluator', v: 146000, text: '≈ 146,000 / s', sub: '15.8× · one pass over 500', color: C.penDeep, bold: true },
    ], { label: 'New polygons per second', labW: 150, max: 150000 });
  })();

  /* fidelity counters */
  (() => {
    const root = $('#br-fid'); if (!root) return;
    const grid = $('#br-fid-grid');
    const items = [
      { n: 744732, of: 744732, cap: 'cells decode identically to the original GeoTIFFs, at both levels (independent float-affine path)' },
      { n: 17, of: 17, cap: 'supplied plots match on every output field, across the store, registry and table paths' },
      { n: 9829, of: 9829, cap: 'fuzzed polygons match: holes, multipolygons, edges through centres, chip edges, water. 171 invalid shapes rejected identically' },
      { n: 0, of: 4920, cap: 'mismatches between fast and reference selection on 4,920 validator-generated geometries', zero: true },
      { n: 3, of: 3, cap: 'negative controls detected: one flipped cell, a moved vertex, a flipped JRC bit' },
    ];
    const els = items.map(it => {
      const num = h('span', { class: 'n' }, '0'), bar = h('i', {}), of = h('span', { class: 'of' }, it.zero ? ` mismatches of ${fmt(it.of)}` : ` / ${fmt(it.of)}`);
      const el = h('div', { class: 'fid' }, h('div', { class: 'big' }, num, of), h('div', { class: 'track' }, bar), h('p', {}, it.cap));
      grid.append(el); return { it, num, bar };
    });
    const play = () => tween(1400, t => els.forEach(({ it, num, bar }) => { num.textContent = it.zero ? '0' : fmt(Math.round(it.n * t)); bar.style.width = (it.zero ? 100 : 100 * t) + '%'; }));
    els.forEach(({ num, it, bar }) => { num.textContent = REDUCE ? (it.zero ? '0' : fmt(it.n)) : '0'; if (REDUCE) bar.style.width = '100%'; });
    $('.replay', root).addEventListener('click', play);
    onView(grid, play);
  })();
})();

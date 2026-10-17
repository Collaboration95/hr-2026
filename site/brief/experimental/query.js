/* #query: browser re-creation of the map overlay with a synthetic, editable polygon.
   Cell codes are re-derived in core.js with the rule in engine/decision.py; selection is an even-odd test on cell centres. */
(() => {
  const { $, $$, h, fmt, esc, seg, tip } = UI;
  const root = $('#br-q'); if (!root) return;
  const mapCv = $('#q-map'), insetCv = $('#q-inset'), read = $('#q-read');
  const yearIn = $('#q-year'), yearOut = $('#q-year-out'), playBtn = $('#q-play'), jrcBtn = $('#q-jrc');
  const REDUCE = Brief.REDUCE;
  const ctlSeg = {};
  let R, hansenCv, jrcCv;
  let level = 'decision', year = 2025, jrcOn = true, zoom = 4, shape = 'penta';
  const DEFAULT_C = [440, 23];                       /* cell column, row of the default centre */
  const SHAPES = {
    penta: [[-5, -2], [-1, -6], [5, -3], [5, 4], [-3, 5]],
    square: [[-5, -5], [5, -5], [5, 5], [-5, 5]],
    ell: [[-6, -5], [0, -5], [0, 0], [6, 0], [6, 6], [-6, 6]],
    strip: [[-9, -1.5], [9, -1.5], [9, 1.5], [-9, 1.5]],
  };
  let poly = SHAPES.penta.map(([x, y]) => [x + DEFAULT_C[0], y + DEFAULT_C[1]]);
  const view = { x0: 0, y0: 0, s: 4 };
  let frozen = null;                                 /* inset window while a drag is in progress */
  let sel = null;                                    /* current selection result */
  let raf = 0;

  const dpr = () => Math.min(2, window.devicePixelRatio || 1);
  function fit(cv) {
    const w = cv.clientWidth, h2 = cv.clientHeight, d = dpr();
    if (cv.width !== Math.round(w * d) || cv.height !== Math.round(h2 * d)) { cv.width = Math.round(w * d); cv.height = Math.round(h2 * d); }
    const ctx = cv.getContext('2d'); ctx.setTransform(d, 0, 0, d, 0, 0);
    return { ctx, w, h: h2 };
  }
  const centroid = () => { let x = 0, y = 0; poly.forEach(p => { x += p[0]; y += p[1]; }); return [x / poly.length, y / poly.length]; };
  const bbox = () => { const xs = poly.map(p => p[0]), ys = poly.map(p => p[1]); return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]; };

  /* draw an image whose pixel (u, v) covers cells [ox + u k, ox + (u + 1) k] */
  function blit(ctx, img, k, ox, oy, x0, y0, s, w, h2) {
    const u0 = Math.max(0, Math.floor((x0 - ox) / k)), v0 = Math.max(0, Math.floor((y0 - oy) / k));
    const u1 = Math.min(img.width, Math.ceil((x0 + w / s - ox) / k)), v1 = Math.min(img.height, Math.ceil((y0 + h2 / s - oy) / k));
    if (u1 <= u0 || v1 <= v0) return;
    ctx.drawImage(img, u0, v0, u1 - u0, v1 - v0, (ox + u0 * k - x0) * s, (oy + v0 * k - y0) * s, (u1 - u0) * k * s, (v1 - v0) * k * s);
  }
  const layers = (ctx, x0, y0, s, w, h2) => {
    ctx.fillStyle = '#10141D'; ctx.fillRect(0, 0, w, h2);
    ctx.imageSmoothingEnabled = s < 1.5;
    blit(ctx, hansenCv, 1, 0, 0, x0, y0, s, w, h2);
    if (jrcOn) { ctx.imageSmoothingEnabled = s < 3; blit(ctx, jrcCv, 1 / 3, 2 / 3, 1 / 3, x0, y0, s, w, h2); }
  };

  /* ---------- selection ---------- */
  function select() {
    const [bx0, by0, bx1, by1] = bbox();
    const counts = new Array(Brief.CODE_COUNT).fill(0), cells = [];
    let selected = 0, outside = 0;
    const lv = R[level], W = R.W, H = R.H;
    for (let r = Math.floor(by0); r <= Math.ceil(by1); r++) for (let c = Math.floor(bx0); c <= Math.ceil(bx1); c++) {
      if (!Brief.inside(poly, c + 0.5, r + 0.5)) continue;
      selected++;
      if (r < 0 || r >= H || c < 0 || c >= W) { outside++; continue; }
      const code = lv[r * W + c]; counts[code]++; cells.push(r, c, code);
    }
    sel = { counts, cells, selected, outside, res: Brief.summarize(counts, selected, outside, level) };
  }

  /* ---------- readout ---------- */
  const flag = v => v === true ? '<b class="t">true</b>' : v === false ? '<b class="f">false</b>' : '<b class="u">unknown (null)</b>';
  const CODE_CLR = c => c === 0 ? '#6B7387' : c === 1 ? '#4C9BE8' : c < 8 ? '#7C8F72' : c < 14 ? (c === 8 ? '#2BD47D' : '#FF7A2E') : (c === 14 ? '#6B7387' : '#E0A33A');
  function readout() {
    const r = sel.res, y = year;
    const maxY = Math.max(1, ...r.yearly, ...(r.hansenYearly || [0]));
    const bars = (arr, cls) => arr.map((v, i) => `<div class="yb ${cls} ${y === 2021 + i ? 'now' : ''}" title="${2021 + i}: ${v}"><div class="bw"><i style="height:${Math.max(v ? 4 : 0, 100 * v / maxY)}%"></i></div><span class="v">${v}</span><span class="x">${2021 + i}</span></div>`).join('');
    const hmax = Math.max(1, ...sel.counts);
    const strip = sel.counts.map((v, c) => `<div class="hb" title="code ${c}: ${v}"><span class="v">${v || ''}</span><div class="bw"><i style="height:${Math.max(v ? 3 : 0, 100 * v / hmax)}%;background:${CODE_CLR(c)}"></i></div><span class="x">${c}</span></div>`).join('');
    read.innerHTML = `
      <div class="br-read-col">
        <div class="br-lab">Answer fields · ${level === 'decision' ? 'eudr-decision.v1' : 'eudr-screen.v1'}</div>
        <dl class="br-ans">
          <dt><code>selected_cell_count</code></dt><dd><b>${fmt(r.selected)}</b>${r.outside ? ` <small>(${r.outside} outside the chip)</small>` : ''}</dd>
          <dt><code>valid_land_cell_count</code></dt><dd>${fmt(r.land)}</dd>
          <dt><code>water_cell_count</code></dt><dd>${fmt(r.water)}</dd>
          <dt><code>unknown_cell_count</code></dt><dd>${fmt(r.unknown)}</dd>
          <dt><code>forest_2020.cell_counts</code></dt><dd><span class="pill f">forest ${fmt(r.forest)}</span> <span class="pill n">non-forest ${fmt(r.nonforest)}</span> <span class="pill u">unknown ${fmt(r.funk)}</span></dd>
          <dt><code>deforestation_after_2020.cell_count</code><small>mapped loss on mapped 2020 forest</small></dt><dd><b class="loss">${fmt(r.total)}</b></dd>
          <dt><code>forest_2020.present</code></dt><dd>${flag(r.forestPresent)}</dd>
          <dt><code>deforestation_after_2020.present</code></dt><dd>${flag(r.deforestPresent)}</dd>
          <dt><code>support</code></dt><dd><b>${r.support}</b></dd>
        </dl>
        <div class="br-lab">Mapped loss on mapped 2020 forest, by year</div>
        <div class="ybars">${bars(r.yearly, 'f')}</div>
        ${r.hansenYearly ? `<div class="br-lab">Hansen loss after 2020 on all land (screening level)</div><div class="ybars">${bars(r.hansenYearly, 'h')}</div>` : ''}
      </div>
      <div class="br-read-col">
        <div class="br-lab">20-bin histogram of selected cells · the reducer's only input</div>
        <div class="hist">${strip}</div>
        <p class="br-hist-note">${level === 'decision' ? 'Codes 3–7 are always 0 at the decision level.' : 'Codes 3–7 hold loss on 2020 non-forest land, which the supplier\'s Hansen-only check counts.'} Colour: <span class="sw" style="background:#6B7387"></span>unknown <span class="sw" style="background:#4C9BE8"></span>water <span class="sw" style="background:#7C8F72"></span>non-forest <span class="sw" style="background:#2BD47D"></span>forest <span class="sw" style="background:#FF7A2E"></span>forest + loss <span class="sw" style="background:#E0A33A"></span>forest unknown.</p>
      </div>`;
  }

  /* ---------- map ---------- */
  function drawPoly(ctx, f, vr, fillA) {
    ctx.beginPath(); poly.forEach((p, i) => { const [x, y] = f(p); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.closePath();
    ctx.fillStyle = `rgba(110,123,255,${fillA})`; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = '#6E7BFF'; ctx.lineJoin = 'round'; ctx.stroke();
    if (vr) poly.forEach(p => { const [x, y] = f(p); ctx.beginPath(); ctx.arc(x, y, vr, 0, 7); ctx.fillStyle = '#E6E9EF'; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = '#6E7BFF'; ctx.stroke(); });
  }
  function drawMap() {
    const { ctx, w, h: h2 } = fit(mapCv), { x0, y0, s } = view;
    layers(ctx, x0, y0, s, w, h2);
    drawPoly(ctx, p => [(p[0] - x0) * s, (p[1] - y0) * s], s >= 3 ? 4 : 0, 0.12);
    if (s < 3) { const [cx, cy] = centroid(); ctx.beginPath(); ctx.arc((cx - x0) * s, (cy - y0) * s, 11, 0, 7); ctx.lineWidth = 2; ctx.strokeStyle = '#6E7BFF'; ctx.stroke(); }
  }

  /* ---------- inset ---------- */
  function insetWin(w, h2) {
    if (frozen) return frozen;
    const [bx0, by0, bx1, by1] = bbox(), pad = 1.5;
    let ww = Math.max(bx1 - bx0 + 2 * pad, 12), hh = Math.max(by1 - by0 + 2 * pad, 9);
    const s = Math.min(w / ww, h2 / hh, 44);
    const cx = (bx0 + bx1) / 2, cy = (by0 + by1) / 2;
    return { s, x0: cx - w / s / 2, y0: cy - h2 / s / 2 };
  }
  function drawInset() {
    const { ctx, w, h: h2 } = fit(insetCv), win = insetWin(w, h2), { x0, y0, s } = win;
    layers(ctx, x0, y0, s, w, h2);
    /* unselected cells are veiled; selected cells keep their colour */
    const inSel = new Set(); for (let i = 0; i < sel.cells.length; i += 3) inSel.add(sel.cells[i] * 100000 + sel.cells[i + 1]);
    const c0 = Math.floor(x0), c1 = Math.ceil(x0 + w / s), r0 = Math.floor(y0), r1 = Math.ceil(y0 + h2 / s);
    ctx.fillStyle = 'rgba(7,9,13,.66)';
    for (let r = r0; r < r1; r++) for (let c = c0; c < c1; c++) if (!inSel.has(r * 100000 + c)) ctx.fillRect((c - x0) * s, (r - y0) * s, s + 0.6, s + 0.6);
    if (s >= 9) {
      ctx.strokeStyle = 'rgba(230,233,239,.13)'; ctx.lineWidth = 1; ctx.beginPath();
      for (let c = c0; c <= c1; c++) { const x = Math.round((c - x0) * s) + .5; ctx.moveTo(x, 0); ctx.lineTo(x, h2); }
      for (let r = r0; r <= r1; r++) { const y = Math.round((r - y0) * s) + .5; ctx.moveTo(0, y); ctx.lineTo(w, y); }
      ctx.stroke();
    }
    /* mapped loss on mapped 2020 forest (codes 9-13): orange frame */
    const lv = R[level];
    for (let r = Math.max(0, r0); r < Math.min(R.H, r1); r++) for (let c = Math.max(0, c0); c < Math.min(R.W, c1); c++) {
      const code = lv[r * R.W + c];
      if (code >= 9 && code <= 13 && inSel.has(r * 100000 + c) && 2020 + code - 8 <= year) {
        ctx.lineWidth = 2.5; ctx.strokeStyle = '#FF7A2E'; ctx.strokeRect((c - x0) * s + 1.5, (r - y0) * s + 1.5, s - 3, s - 3);
      }
    }
    /* centre sub-cell (the JRC cell the rule reads) and the centre dot */
    for (let r = r0; r < r1; r++) for (let c = c0; c < c1; c++) {
      const cx = (c + .5 - x0) * s, cy = (r + .5 - y0) * s, on = inSel.has(r * 100000 + c);
      if (s >= 14 && jrcOn) { ctx.lineWidth = 1; ctx.strokeStyle = on ? 'rgba(230,233,239,.75)' : 'rgba(230,233,239,.25)'; ctx.strokeRect(cx - s / 6 + .5, cy - s / 6 + .5, s / 3 - 1, s / 3 - 1); }
      const rad = Math.max(2, Math.min(5, s * .12));
      ctx.beginPath(); ctx.arc(cx, cy, rad, 0, 7);
      if (on) { ctx.fillStyle = '#E6E9EF'; ctx.fill(); } else { ctx.lineWidth = 1.4; ctx.strokeStyle = 'rgba(230,233,239,.55)'; ctx.fillStyle = 'rgba(7,9,13,.6)'; ctx.fill(); ctx.stroke(); }
    }
    drawPoly(ctx, p => [(p[0] - x0) * s, (p[1] - y0) * s], 6, 0.0);
    insetCv._win = win;
  }

  function draw() { raf = 0; if (!R) return; select(); drawMap(); drawInset(); readout(); }
  const schedule = () => { if (!raf) raf = requestAnimationFrame(draw); };

  /* ---------- view helpers ---------- */
  function setZoom(z, keep) {
    zoom = z;
    const w = mapCv.clientWidth, h2 = mapCv.clientHeight;
    const [cx, cy] = keep || centroid();
    view.s = z === 0 ? Math.min(w / R.W, h2 / R.H) : z;
    view.x0 = z === 0 ? (R.W - w / view.s) / 2 : cx - w / view.s / 2;
    view.y0 = z === 0 ? (R.H - h2 / view.s) / 2 : cy - h2 / view.s / 2;
    clampView();
  }
  function clampView() {
    const w = mapCv.clientWidth, h2 = mapCv.clientHeight, vw = w / view.s, vh = h2 / view.s;
    view.x0 = vw >= R.W ? (R.W - vw) / 2 : Math.max(0, Math.min(R.W - vw, view.x0));
    view.y0 = vh >= R.H ? (R.H - vh) / 2 : Math.max(0, Math.min(R.H - vh, view.y0));
  }
  function setShape(name) {
    shape = name; const [cx, cy] = centroid();
    poly = SHAPES[name].map(([x, y]) => [x + cx, y + cy]);
    schedule();
  }

  /* ---------- pointer interaction (shared by map and inset) ---------- */
  function wire(cv, getXf, opts) {
    let drag = null;
    const pos = e => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    const toCell = (px, py) => { const { x0, y0, s } = getXf(); return [x0 + px / s, y0 + py / s]; };
    const hitVertex = (px, py, rad) => { const { x0, y0, s } = getXf(); let best = -1, bd = rad * rad; poly.forEach((p, i) => { const dx = (p[0] - x0) * s - px, dy = (p[1] - y0) * s - py; const d = dx * dx + dy * dy; if (d <= bd) { bd = d; best = i; } }); return best; };
    cv.addEventListener('pointerdown', e => {
      if (!R || e.button === 2) return;
      const [px, py] = pos(e), v = hitVertex(px, py, 11);
      if (v >= 0 && (e.shiftKey || e.altKey || e.ctrlKey || e.metaKey)) { if (poly.length > 3) { poly.splice(v, 1); schedule(); } return; }
      const [cx, cy] = toCell(px, py);
      if (v >= 0 && (opts.vertex || getXf().s >= 3)) drag = { kind: 'v', i: v };
      else if (Brief.inside(poly, cx, cy) || (getXf().s < 3 && Math.hypot(cx - centroid()[0], cy - centroid()[1]) < 11 / getXf().s)) drag = { kind: 'm', cx, cy };
      else if (opts.pan) drag = { kind: 'p', px, py, x0: view.x0, y0: view.y0 };
      else return;
      if (opts.freeze) frozen = { ...getXf() };
      cv.setPointerCapture(e.pointerId); cv.classList.add('grab'); e.preventDefault();
    });
    cv.addEventListener('pointermove', e => {
      const [px, py] = pos(e);
      if (!drag) {
        cv.style.cursor = !R ? '' : hitVertex(px, py, 11) >= 0 ? 'pointer' : Brief.inside(poly, ...toCell(px, py)) ? 'move' : opts.pan ? 'grab' : 'default';
        hover(e, cv, getXf);
        return;
      }
      tip.hide();
      const [cx, cy] = toCell(px, py);
      if (drag.kind === 'v') { poly[drag.i] = [Math.round(cx * 8) / 8, Math.round(cy * 8) / 8]; }
      else if (drag.kind === 'm') { const dx = cx - drag.cx, dy = cy - drag.cy; poly = poly.map(p => [p[0] + dx, p[1] + dy]); drag.cx = cx; drag.cy = cy; }
      else { view.x0 = drag.x0 - (px - drag.px) / view.s; view.y0 = drag.y0 - (py - drag.py) / view.s; clampView(); }
      schedule();
    });
    const end = e => { if (!drag) return; drag = null; frozen = null; cv.classList.remove('grab'); schedule(); };
    cv.addEventListener('pointerup', end); cv.addEventListener('pointercancel', end);
    cv.addEventListener('pointerleave', tip.hide);
    cv.addEventListener('contextmenu', e => { if (!opts.vertex) return; const [px, py] = pos(e), v = hitVertex(px, py, 11); if (v >= 0 && poly.length > 3) { e.preventDefault(); poly.splice(v, 1); schedule(); } });
    if (opts.addVertex) cv.addEventListener('dblclick', e => {
      const [px, py] = pos(e), [cx, cy] = toCell(px, py);
      let bi = 0, bd = 1e9, bp = null;
      poly.forEach((a, i) => { const b = poly[(i + 1) % poly.length]; const vx = b[0] - a[0], vy = b[1] - a[1], L = vx * vx + vy * vy || 1; const t = Math.max(0, Math.min(1, ((cx - a[0]) * vx + (cy - a[1]) * vy) / L)); const qx = a[0] + t * vx, qy = a[1] + t * vy; const d = (qx - cx) ** 2 + (qy - cy) ** 2; if (d < bd) { bd = d; bi = i; bp = [qx, qy]; } });
      poly.splice(bi + 1, 0, [Math.round(cx * 8) / 8, Math.round(cy * 8) / 8]); schedule();
    });
  }
  function hover(e, cv, getXf) {
    const r = cv.getBoundingClientRect(), { x0, y0, s } = getXf();
    const c = Math.floor(x0 + (e.clientX - r.left) / s), rr = Math.floor(y0 + (e.clientY - r.top) / s);
    if (s < 2.5 || c < 0 || rr < 0 || c >= R.W || rr >= R.H) { tip.hide(); return; }
    const i = rr * R.W + c, code = R[level][i], ly = R.loss[i], f = R.forest[i];
    tip.show(`<b>row ${rr}, col ${c}</b><br>code ${code} · ${esc(Brief.codeInfo(code).label)}<br>Hansen loss year ${ly ? 2000 + ly : 'none'} · treecover2000 ${R.tree[i]}%<br>JRC 2020 at centre: ${f === 2 ? 'no value' : f ? 'forest' : 'non-forest'}`, e.clientX, e.clientY);
  }
  wire(mapCv, () => view, { pan: true, vertex: true });
  wire(insetCv, () => insetCv._win || { x0: 0, y0: 0, s: 1 }, { vertex: true, addVertex: true, freeze: true });
  mapCv.addEventListener('keydown', e => {
    const d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
    if (!d) return; e.preventDefault(); poly = poly.map(p => [p[0] + d[0], p[1] + d[1]]); schedule();
  });

  /* ---------- controls ---------- */
  seg($('.br-seg[aria-label="Level"]', root), 'level', v => { level = v; schedule(); });
  seg($('.br-seg[aria-label="Map zoom"]', root), 'zoom', v => { if (R) { setZoom(+v); schedule(); } else zoom = +v; });
  seg($('.br-seg[aria-label="Polygon shape"]', root), 'shape', v => setShape(v));
  yearIn.addEventListener('input', () => setYear(+yearIn.value));
  function setYear(y) { year = y; yearIn.value = y; yearOut.textContent = y; if (R) { Brief.paintHansen(hansenCv, R, year); schedule(); } }
  let timer = 0;
  playBtn.textContent = REDUCE ? 'Next year' : 'Play years';
  playBtn.addEventListener('click', () => {
    if (REDUCE) { setYear(year >= 2025 ? 2001 : year + 1); return; }
    if (timer) { clearInterval(timer); timer = 0; playBtn.textContent = 'Play years'; return; }
    if (year >= 2025) setYear(2000 + 1);
    playBtn.textContent = 'Pause';
    timer = setInterval(() => { if (year >= 2025) { clearInterval(timer); timer = 0; playBtn.textContent = 'Play years'; return; } setYear(year + 1); }, 380);
  });
  jrcBtn.addEventListener('click', () => { jrcOn = !jrcOn; jrcBtn.setAttribute('aria-pressed', String(jrcOn)); jrcBtn.classList.toggle('on', jrcOn); schedule(); });
  new ResizeObserver(() => { if (R) { setZoom(zoom, centroid()); schedule(); } }).observe(mapCv);

  read.innerHTML = '<div class="muted">Loading region rasters…</div>';
  Brief.ready.then(r => {
    R = r;
    hansenCv = document.createElement('canvas'); jrcCv = document.createElement('canvas');
    Brief.paintHansen(hansenCv, R, year); Brief.paintJrc(jrcCv, R);
    setZoom(zoom); draw();
  }).catch(err => { read.innerHTML = `<div class="note unknown"><b>Unavailable</b><span>The region rasters could not be loaded (${esc(err.message || err)}).</span></div>`; });
})();

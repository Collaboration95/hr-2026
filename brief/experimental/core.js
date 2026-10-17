/* Shared region loader for the technical brief.
   Decodes the committed display rasters exactly as app/src/map/region-raster.ts does, then re-derives the 20-code
   raster in the browser with the rule in engine/decision.py. Illustration only: the evidence is the Python engine's proof. */
window.Brief = (() => {
  const BASE = new URL('../data/', document.currentScript.src).href;
  const REDUCE = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* code space: engine/decision_summary.py */
  const UNKNOWN = 0, WATER = 1, LAND = 2, CODE_COUNT = 20;
  const FOREST_STATES = ['non-forest', 'forest', 'forest state unknown'];
  const YEARS = [2021, 2022, 2023, 2024, 2025];
  const landCode = (state, post) => LAND + 6 * state + post;
  const codeInfo = code => {
    if (code === UNKNOWN) return { kind: 'unknown', label: 'unknown' };
    if (code === WATER) return { kind: 'water', label: 'water' };
    const k = code - LAND, state = Math.floor(k / 6), post = k % 6;
    return { kind: 'land', state, post, label: `land · ${FOREST_STATES[state]} · ${post ? 'loss ' + (2020 + post) : 'no loss after 2020'}` };
  };

  /* palette: dark-edition tokens as RGB (brief.css, body.x-dark) */
  const P = {
    canopy0: [19, 25, 24], canopy100: [52, 160, 102], loss: [255, 122, 46], lossPast: [138, 100, 82],
    water: [58, 124, 196], nodata: [33, 39, 52], land: [30, 38, 36], forest: [43, 212, 125],
  };
  const LE = new Uint8Array(new Uint32Array([0x01020304]).buffer)[0] === 4;
  const pack = (c, a = 255) => (LE ? ((a << 24) | (c[2] << 16) | (c[1] << 8) | c[0]) : ((c[0] << 24) | (c[1] << 16) | (c[2] << 8) | a)) >>> 0;
  const mix = (a, b, t) => [Math.round(a[0] + (b[0] - a[0]) * t), Math.round(a[1] + (b[1] - a[1]) * t), Math.round(a[2] + (b[2] - a[2]) * t)];
  const canopy = (pct, dim) => { const ramp = mix(P.canopy0, P.canopy100, pct / 100); return dim ? mix(P.canopy0, ramp, 1 - dim) : ramp; };

  async function sha256Hex(buf) {
    if (!crypto.subtle) return null;
    const d = await crypto.subtle.digest('SHA-256', buf);
    return Array.from(new Uint8Array(d), b => b.toString(16).padStart(2, '0')).join('');
  }
  async function decode(blob, w, h) {
    let src, sw, sh;
    try { src = await createImageBitmap(blob, { colorSpaceConversion: 'none', premultiplyAlpha: 'none' }); sw = src.width; sh = src.height; }
    catch (_) { const url = URL.createObjectURL(blob); const img = new Image(); img.src = url; await img.decode(); URL.revokeObjectURL(url); src = img; sw = img.naturalWidth; sh = img.naturalHeight; }
    if (sw !== w || sh !== h) throw new Error(`decoded ${sw}x${sh}, expected ${w}x${h}`);
    const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
    const ctx = cv.getContext('2d', { willReadFrequently: true });
    ctx.imageSmoothingEnabled = false; ctx.globalCompositeOperation = 'copy'; ctx.drawImage(src, 0, 0);
    return ctx.getImageData(0, 0, w, h).data;
  }
  async function fetchPng(g) {
    const res = await fetch(BASE + g.png);
    if (!res.ok) throw new Error(`${g.png}: HTTP ${res.status}`);
    const buf = await res.arrayBuffer();
    const sha = await sha256Hex(buf);
    if (sha !== null && sha !== g.png_sha256) throw new Error(`${g.png}: SHA-256 differs from the manifest`);
    const [rows, cols] = g.shape_rows_columns;
    return { rgba: await decode(new Blob([buf], { type: 'image/png' }), cols, rows), verified: sha !== null };
  }

  /* Hansen centre (r, c) is the middle of JRC cell (3r + rowOff, 3c + colOff): engine.decision.nested_offsets */
  function nestedOffsets(hg, jg) {
    const [a, , c, , e, f] = hg.transform, [ja, , jc, , je, jf] = jg.transform;
    const k = Math.round(a / ja);
    const col0 = Math.round((c - jc) / ja), row0 = Math.round((f - jf) / je);
    const half = k >> 1;
    return { k, rowOff: row0 + half, colOff: col0 + half };
  }

  function build(manifest, h, j) {
    const [H, W] = manifest.hansen.shape_rows_columns, [JH, JW] = manifest.jrc.shape_rows_columns, n = H * W;
    const loss = new Uint8Array(n), mask = new Uint8Array(n), tree = new Uint8Array(n);
    for (let i = 0, p = 0; i < n; i++, p += 4) { loss[i] = h[p]; mask[i] = h[p + 1]; tree[i] = h[p + 2]; }
    const klass = new Uint8Array(JH * JW);
    for (let i = 0, p = 0; i < klass.length; i++, p += 4) klass[i] = j[p];
    const { k, rowOff, colOff } = nestedOffsets(manifest.hansen, manifest.jrc);
    const forest = new Uint8Array(n);                      /* JRC 2020 state at the Hansen centre: 0 non-forest, 1 forest, 2 unknown */
    for (let r = 0; r < H; r++) {
      const jr = k * r + rowOff;
      for (let c = 0; c < W; c++) {
        const jc = k * c + colOff;
        forest[r * W + c] = (jr >= 0 && jr < JH && jc >= 0 && jc < JW) ? klass[jr * JW + jc] : 2;
      }
    }
    const screen = new Uint8Array(n);
    for (let i = 0; i < n; i++) {
      const m = mask[i];
      if (m === 2) screen[i] = WATER;
      else if (m === 1) { const l = loss[i]; screen[i] = landCode(forest[i], l > 20 ? l - 20 : 0); }
      else screen[i] = UNKNOWN;
    }
    const decision = screen.slice();
    for (let i = 0; i < n; i++) if (decision[i] > LAND && decision[i] < LAND + 6) decision[i] = LAND;
    const count = a => { const o = new Array(CODE_COUNT).fill(0); for (let i = 0; i < a.length; i++) o[a[i]]++; return o; };
    return { H, W, JH, JW, loss, mask, tree, klass, forest, screen, decision, off: { k, rowOff, colOff }, hist: { screen: count(screen), decision: count(decision) } };
  }

  /* painting ------------------------------------------------------------------------------------------ */
  const imgCache = new WeakMap();
  function target(cv, w, h) {
    if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
    const ctx = cv.getContext('2d');
    let img = imgCache.get(cv);
    if (!img || img.width !== w || img.height !== h) { img = ctx.createImageData(w, h); imgCache.set(cv, img); }
    return { ctx, img, out: new Uint32Array(img.data.buffer) };
  }
  const lutCache = {};
  const lut = dim => lutCache[dim] || (lutCache[dim] = Uint32Array.from({ length: 101 }, (_, t) => pack(canopy(t, dim))));

  /* Hansen loss recoloured by year: loss before `year` rust, loss in `year` orange, later loss not drawn yet. */
  function paintHansen(cv, R, year) {
    const { ctx, img, out } = target(cv, R.W, R.H);
    const L = lut(0.35), water = pack(P.water), nodata = pack(P.nodata), lossC = pack(P.loss), past = pack(P.lossPast), sel = year - 2000;
    const { loss, mask, tree } = R;
    for (let i = 0; i < out.length; i++) {
      const m = mask[i];
      if (m === 1) { const l = loss[i]; out[i] = l === 0 || l > sel ? L[tree[i]] : l === sel ? lossC : past; }
      else out[i] = m === 2 ? water : nodata;
    }
    ctx.putImageData(img, 0, 0);
  }
  /* JRC 2020 forest, class 1 as translucent green, class 0 transparent. */
  function paintJrc(cv, R) {
    const { ctx, img, out } = target(cv, R.JW, R.JH);
    const f = pack(P.forest, 150), k = R.klass;
    for (let i = 0; i < out.length; i++) out[i] = k[i] === 1 ? f : 0;
    ctx.putImageData(img, 0, 0);
  }
  const rgb = (c, a = 1) => `rgb(${c[0]} ${c[1]} ${c[2]} / ${a})`;

  /* geometry ---------------------------------------------------------------------------------------- */
  /* even-odd point-in-polygon; the engine uses exact GEOS covers (boundary inclusive), which this illustration does not reproduce */
  function inside(poly, x, y) {
    let c = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const [xi, yi] = poly[i], [xj, yj] = poly[j];
      if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c;
    }
    return c;
  }

  /* JS port of engine/decision_summary.py summarize_ints */
  function summarize(counts, selected, outside, level) {
    const [, water, n0, n1, n2, n3, n4, n5, f0, f1, f2, f3, f4, f5, u0, u1, u2, u3, u4, u5] = counts;
    const total = f1 + f2 + f3 + f4 + f5, funkPost = u1 + u2 + u3 + u4 + u5;
    const nonforest = n0 + n1 + n2 + n3 + n4 + n5, forest = f0 + total, funk = u0 + funkPost;
    const land = nonforest + forest + funk, unknown = outside + counts[0];
    const out = { level, selected, outside, land, water, unknown, nonforest, forest, funk, total, yearly: [f1, f2, f3, f4, f5] };
    out.forestPresent = land === 0 ? null : forest > 0 ? true : (unknown + funk === 0 ? false : null);
    out.deforestPresent = land === 0 ? null : total > 0 ? true : (unknown + funkPost === 0 ? false : null);
    if (level === 'screen') out.hansenYearly = [n1 + f1 + u1, n2 + f2 + u2, n3 + f3 + u3, n4 + f4 + u4, n5 + f5 + u5];
    out.support = (selected === 0 || land === 0) ? 'none' : (unknown || funk) ? 'partial' : 'complete';
    return out;
  }

  const ready = (async () => {
    const manifest = await (await fetch(BASE + 'manifest.json')).json();
    const [h, j] = await Promise.all([fetchPng(manifest.hansen), fetchPng(manifest.jrc)]);
    const R = build(manifest, h.rgba, j.rgba);
    R.manifest = manifest; R.verified = h.verified && j.verified;
    const want = window.BR.hist;
    R.histMatches = ['screen', 'decision'].every(l => R.hist[l].every((v, i) => v === want[l][i]));
    api.region = R;
    return R;
  })();
  ready.catch(err => { api.error = err; console.warn('Region rasters unavailable:', err); });

  const api = { ready, REDUCE, P, pack, mix, canopy, rgb, UNKNOWN, WATER, LAND, CODE_COUNT, FOREST_STATES, YEARS, landCode, codeInfo,
    paintHansen, paintJrc, inside, summarize, BASE, region: null, error: null,
    fmt: n => n.toLocaleString('en-GB'), sha256Hex };
  return api;
})();

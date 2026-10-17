/* Swarm: one THREE.Points cloud of real map cells that regroups into a new formation for each section.
   Positions and colours of every formation are precomputed once; the GPU interpolates between the two active ones.
   Illustration only: the point cloud is a sample of the region rasters, not the evidence. */

const REDUCE = matchMedia('(prefers-reduced-motion: reduce)').matches;
const MOBILE = () => innerWidth < 820;
const MW = 100;                                  /* world width of the region map */

/* ---------- small helpers ---------- */
const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16) / 255);
const DARK = document.body.classList.contains('x-dark');      /* dark edition: additive glow; light edition: normal blending, solid cores */
const OP = 1.25;                                                /* base opacity lift applied to every point */
const C = DARK ? {
  forest: hex('#2BD47D'), loss: hex('#FF7A2E'), lossHot: hex('#FFA45C'), past: hex('#B98A73'), water: hex('#4C9BE8'),
  unk: hex('#6B7280'), pen: hex('#6E7BFF'), bytes: hex('#C9CED8'), land: hex('#8A93A3'), purple: hex('#8E86B0'),
  amber: hex('#F2B34A'), dust: hex('#8EA0C8'), ver: hex('#D8F6E4'), mk: [1, 1, 1], fLo: [0.1, 0.5, 0.3], fHi: [0.4, 1, 0.66], oLo: [0.2, 0.22, 0.14], oHi: [0.62, 0.6, 0.4],
  cLo: [0.05, 0.17, 0.12], cHi: [0.24, 0.93, 0.54], label: '#8B93A5', trail: null,
} : {
  forest: hex('#15803D'), loss: hex('#E8590C'), lossHot: hex('#D9480F'), past: hex('#C9A08A'), water: hex('#2B6CB0'),
  unk: hex('#8A90A3'), pen: hex('#2F45FF'), bytes: hex('#6B7389'), land: hex('#8A90A3'), purple: hex('#7A5AF8'),
  amber: hex('#B7791F'), dust: hex('#8A90A3'), ver: hex('#12B76A'), mk: [0.06, 0.07, 0.13], fLo: hex('#A9C9A8'), fHi: hex('#15803D'), oLo: hex('#CFCBA6'), oHi: hex('#7A7440'),
  cLo: hex('#C3D4BE'), cHi: hex('#2F6B47'), label: '#555B70', trail: hex('#2F45FF'),
};
const mix3 = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const sstep = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const rn = (i, k) => { const s = Math.sin(i * 12.9898 + k * 78.233) * 43758.5453; return s - Math.floor(s); };
const gauss = (i, k) => (rn(i, k) + rn(i, k + 1) + rn(i, k + 2) - 1.5) * 1.15;
function mulberry32(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; };
const canopy = t => mix3(C.cLo, C.cHi, Math.pow(clamp(t, 0, 1), 0.85));
function inside(poly, x, y) {                     /* even-odd, same rule as Brief.inside */
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c;
  }
  return c;
}

/* ---------- region (real, or a procedural stand-in so the page never breaks) ---------- */
function fakeRegion() {
  const H = 604, W = 1233, n = H * W;
  const loss = new Uint8Array(n), mask = new Uint8Array(n), tree = new Uint8Array(n), forest = new Uint8Array(n), screen = new Uint8Array(n);
  for (let r = 0; r < H; r++) for (let c = 0; c < W; c++) {
    const i = r * W + c, u = c / W, v = r / H;
    const f = Math.sin(u * 9 + 1.3) * Math.cos(v * 7) + 0.5 * Math.sin(u * 23 + v * 17) + 0.25 * Math.sin(u * 61 - v * 43);
    const lake = (u - 0.3) ** 2 * 3 + (v - 0.62) ** 2 * 9 < 0.018;
    mask[i] = lake ? 2 : 1;
    tree[i] = lake ? 0 : clamp(Math.round(55 + f * 45), 0, 100);
    forest[i] = tree[i] > 62 ? 1 : 0;
    loss[i] = !lake && Math.sin(u * 40) * Math.sin(v * 33) > 0.93 ? 21 + ((c >> 5) % 5) : 0;
    screen[i] = lake ? 1 : (2 + 6 * forest[i] + (loss[i] > 20 ? loss[i] - 20 : 0));
  }
  return { H, W, loss, mask, tree, forest, screen, decision: screen, hist: window.BR ? BR.hist : null, fake: true };
}
async function getRegion() {
  try { return await Brief.ready; } catch (e) { console.warn('Swarm: using a procedural stand-in map', e); return fakeRegion(); }
}

/* ---------- sample: stratified grid, one real cell per block ---------- */
function buildPoints(R, n0) {
  const { H, W } = R, rng = mulberry32(20261017);
  const nx = Math.round(Math.sqrt(n0 * W / H)), ny = Math.round(n0 / nx), N = nx * ny;
  const hist = (window.BR && BR.hist.screen) || R.hist.screen;
  const P = { N, nx, ny, x: new Float32Array(N), y: new Float32Array(N), tree: new Uint8Array(N), loss: new Uint8Array(N), mask: new Uint8Array(N),
    forest: new Uint8Array(N), code: new Uint8Array(N), bx: new Uint16Array(N), by: new Uint16Array(N), rank: new Uint32Array(N), MH: MW * H / W, hist };
  const perm = Array.from({ length: N }, (_, i) => i);
  for (let i = N - 1; i > 0; i--) { const j = Math.floor(rng() * (i + 1)); [perm[i], perm[j]] = [perm[j], perm[i]]; }
  perm.forEach((p, r) => { P.rank[p] = r; });
  const setPt = (i, idx) => { const r = (idx / W) | 0, c = idx % W;
    P.x[i] = (c / W - 0.5) * MW; P.y[i] = (0.5 - r / H) * P.MH;
    P.tree[i] = R.tree[idx]; P.loss[i] = R.loss[idx]; P.mask[i] = R.mask[idx]; P.forest[i] = R.forest[idx]; P.code[i] = R.screen[idx]; };
  let i = 0;
  for (let by = 0; by < ny; by++) for (let bx = 0; bx < nx; bx++, i++) {
    let best = -1;
    for (let k = 0; k < 4; k++) {                 /* four candidates per block; a rare code (<5,000 cells) wins over a common one */
      const r = Math.min(H - 1, Math.floor((by + rng()) * H / ny)), c = Math.min(W - 1, Math.floor((bx + rng()) * W / nx)), idx = r * W + c;
      if (best < 0 || (hist[R.screen[idx]] < 5000 && hist[R.screen[best]] >= 5000)) best = idx;
    }
    setPt(i, best); P.bx[i] = bx; P.by[i] = by;
  }
  /* quota: every rare non-empty code gets at least ~28 points (water 90), taken from random cells of that code and swapped in for random plain-land points */
  const cnt = new Array(20).fill(0); for (let k = 0; k < N; k++) cnt[P.code[k]]++;
  const quota = c => (c === 1 ? 90 : hist[c] > 0 && hist[c] < 5000 ? 28 : 0), need = [];
  for (let c = 1; c < 20; c++) if (quota(c) > cnt[c]) need.push(c);
  if (need.length) {
    const lists = {}; need.forEach(c => { lists[c] = []; });
    for (let k = 0; k < R.screen.length; k++) { const l = lists[R.screen[k]]; if (l) l.push(k); }
    const vic = []; for (let k = 0; k < N; k++) if (P.code[k] === 2) vic.push(k);
    for (let k = vic.length - 1; k > 0; k--) { const j = Math.floor(rng() * (k + 1)); [vic[k], vic[j]] = [vic[j], vic[k]]; }
    let vi = 0;
    need.forEach(c => { for (let n = cnt[c]; n < quota(c) && lists[c].length && vi < vic.length; n++) {
      const idx = lists[c][Math.floor(rng() * lists[c].length)], k = vic[vi++]; setPt(k, idx);
      P.bx[k] = Math.min(nx - 1, Math.floor((idx % W) / W * nx)); P.by[k] = Math.min(ny - 1, Math.floor(((idx / W) | 0) / H * ny));
    } });
  }
  /* density honesty: each code's weight = true share / sampled share (<= 1); map formations multiply alpha by it. A few loss points stay bright. */
  const cnt2 = new Array(20).fill(0); for (let k = 0; k < N; k++) cnt2[P.code[k]]++;
  const total = hist.reduce((a, b) => a + b, 0) || 1, wc = cnt2.map((n, c) => (n ? clamp((hist[c] / total) / (n / N), 0.12, 1) : 1));
  P.bw = new Float32Array(N);
  for (let k = 0; k < N; k++) { const w = wc[P.code[k]]; P.bw[k] = (w < 1 && P.loss[k] > 20 && P.rank[k] % 8 === 0) ? 1 : w; }
  const land = []; for (let k = 0; k < N; k++) if (P.mask[k] === 1) land.push(P.tree[k]);
  land.sort((a, b) => a - b); P.t0 = land[Math.floor(land.length * 0.05)] || 0; P.t1 = Math.max(P.t0 + 8, land[Math.floor(land.length * 0.97)] || 100);
  return P;
}

/* ---------- formations: (P) -> { pos, col, fx, rot, accent } ---------- */
const newForm = (N, rot, accent) => ({ pos: new Float32Array(3 * N), col: new Float32Array(4 * N), fx: new Float32Array(3 * N), rot, accent, labels: [] });
function put(F, i, x, y, z, c, a, s = 1, flow = 0, spin = 0) {
  let j = 3 * i; F.pos[j] = x; F.pos[j + 1] = y; F.pos[j + 2] = z;
  F.fx[j] = flow; F.fx[j + 1] = s; F.fx[j + 2] = spin;
  j = 4 * i; F.col[j] = c[0]; F.col[j + 1] = c[1]; F.col[j + 2] = c[2]; F.col[j + 3] = Math.min(1, a * OP);
}
const dust = (F, i) => put(F, i, (rn(i, 1) - 0.5) * 170, (rn(i, 2) - 0.5) * 90, (rn(i, 3) - 0.5) * 70, C.dust, 0.05, 0.7);
/* colour of a decision code (screen level) */
function codeStyle(code) {
  if (code === 0) return [C.unk, 0.4];
  if (code === 1) return [C.water, 0.95];
  if (code >= 14) return [C.purple, code === 14 ? 0.55 : 0.8];
  if (code >= 8) return code === 8 ? [C.forest, 0.85] : [C.lossHot, 1];
  return code === 2 ? [C.land, 0.4] : [C.loss, 0.85];
}
const ISO = [-0.62, 0.6, 0];

const FORMS = {
  nebula(P) {
    const F = newForm(P.N, [0.2, 0.3, 0], '#6E7BFF');
    for (let i = 0; i < P.N; i++) {
      const th = rn(i, 5) * 6.2832, ph = Math.acos(2 * rn(i, 6) - 1), r = 38 + gauss(i, 7) * 24;
      const c = mix3(C.pen, C.water, rn(i, 8));
      put(F, i, r * Math.sin(ph) * Math.cos(th) * 1.3, r * Math.cos(ph) * 0.9, r * Math.sin(ph) * Math.sin(th), c, 0.45 + 0.35 * rn(i, 9), 0.85, 0, 0.04);
    }
    return F;
  },
  hero(P) {
    const F = newForm(P.N, [-0.62, 0.1, 0.02], '#6E7BFF'), S = 0.96, ox = 4;
    for (let i = 0; i < P.N; i++) {
      const t = clamp((P.tree[i] - P.t0) / (P.t1 - P.t0), 0, 1), lum = Math.pow(t, 1.7), x = P.x[i] * S + ox, y = P.y[i] * S, z = P.tree[i] * 0.05;
      const w = P.bw[i];
      if (P.mask[i] === 2) put(F, i, x, y, 0, C.water, w, 1.4);
      else if (P.loss[i] > 20) put(F, i, x, y, z, C.loss, 0.95 * w, 1.2);
      else if (P.forest[i] === 1) put(F, i, x, y, z, mix3(C.fLo, C.fHi, lum), (0.4 + 0.6 * lum) * w);
      else put(F, i, x, y, z, mix3(C.oLo, C.oHi, lum), (0.22 + 0.45 * lum) * w);
    }
    F.bbox = [ox - 50 * S, ox + 50 * S, -P.MH / 2 * S, P.MH / 2 * S, 0, 5];
    F.labels.push({ p: [ox, -P.MH / 2 * S - 4, 0], text: '1,233 \u00d7 604 cells \u00b7 34 \u00d7 17 km', align: 'c' });
    return F;
  },
  framing(P) {
    const F = newForm(P.N, [-0.2, 0.05, 0], '#2BD47D');
    for (let i = 0; i < P.N; i++) {
      const w = P.bw[i];
      if (P.mask[i] === 2) put(F, i, P.x[i], P.y[i], 0, C.water, w, 1.4);
      else if (P.loss[i] > 20) put(F, i, P.x[i], P.y[i], 0, C.loss, 0.95 * w, 1.2);
      else if (P.forest[i] === 1) put(F, i, P.x[i], P.y[i], 0, C.forest, 0.85 * w);
      else put(F, i, P.x[i], P.y[i], 0, C.unk, 0.36 * w);
    }
    F.labels.push({ p: [0, -P.MH / 2 - 4, 0], text: '1,233 \u00d7 604 cells \u00b7 34 \u00d7 17 km', align: 'c' });
    return F;
  },
  layers(P) {
    const F = newForm(P.N, [-1.05, 0.45, 0], '#4C9BE8'), S = 0.6;
    for (let i = 0; i < P.N; i++) {
      const k = (P.bx[i] & 1) + 2 * (P.by[i] & 1), x = P.x[i] * S, y = P.y[i] * S - 5, z = (k - 1.5) * 17, L = P.loss[i];
      if (k === 0) put(F, i, x, y, z, mix3(canopy(P.tree[i] / 100), C.unk, 0.45), 0.4, 1.1);
      else if (k === 1) L > 20 ? put(F, i, x, y, z, C.loss, 1, 1.25) : L > 0 ? put(F, i, x, y, z, C.past, 0.7, 1.1) : put(F, i, x, y, z, C.past, 0.1, 1.1);
      else if (k === 2) P.mask[i] === 2 ? put(F, i, x, y, z, C.water, 0.95, 1.1) : put(F, i, x, y, z, C.land, 0.3, 1.1);
      else P.forest[i] === 1 ? put(F, i, x, y, z, C.forest, 0.85, 1.1) : put(F, i, x, y, z, C.unk, 0.12, 1.1);
    }
    ['TREECOVER2000 \u00b7 DROPPED', 'LOSSYEAR', 'DATAMASK', 'JRC 2020'].forEach((t, k) => F.labels.push({ p: [S * MW / 2 + 1.5, -P.MH * S / 2 * 0.2 - 5, (k - 1.5) * 17], text: t, align: 'l' }));
    return F;
  },
  schema(P) {
    const F = newForm(P.N, [-0.12, 0.3, 0], '#6E7BFF'), cnt = P.hist, W = 2.2, PITCH = 3.2, CAP = 900, Y0 = -17;
    const groups = [[0], [1], [2, 3, 4, 5, 6, 7], [8, 9, 10, 11, 12, 13], [14, 15, 16, 17, 18, 19]], names = ['UNKNOWN', 'WATER', 'NON-FOREST', 'FOREST', 'FOREST UNKNOWN'];
    const cx = new Array(20), colH = new Array(20);
    let x = 0;
    groups.forEach((g, gi) => { if (gi) x += 3.4; g.forEach(c => { cx[c] = x + W / 2; x += PITCH; colH[c] = 5.6 * Math.log10(1 + cnt[c]); }); });
    const x0 = (x - (PITCH - W)) / 2, seen = new Array(20).fill(0), tot = new Array(20).fill(0);
    for (let i = 0; i < P.N; i++) tot[P.code[i]]++;
    for (let i = 0; i < P.N; i++) {
      const c = P.code[i], j = ++seen[c], n = Math.min(tot[c], CAP);
      if (j > CAP) { dust(F, i); continue; }
      put(F, i, cx[c] - x0 + (rn(i, 11) - 0.5) * W * 0.85, Y0 + (j / n) * colH[c], (rn(i, 12) - 0.5) * 2.4, codeStyle(c)[0], clamp(260 / n, 0.3, 0.95), n < 60 ? 1.6 : 1.05);
    }
    for (let c = 0; c < 20; c++) F.labels.push({ p: [cx[c] - x0, Y0 - 1.8, 0], text: String(c), align: 'c' });
    groups.forEach((g, gi) => F.labels.push({ p: [(cx[g[0]] + cx[g[g.length - 1]]) / 2 - x0, Y0 - 1.8, 0], text: names[gi], align: gi === 0 ? 'r' : gi === 1 ? 'l' : 'c', dx: gi === 0 ? 7 : gi === 1 ? -7 : 0, dy: 18 }));
    return F;
  },
  store(P) {
    const F = newForm(P.N, [-0.42, 0.6, 0], '#C9CED8'), L = 48, N = P.N, bx = -23, cs = 20, sw = 16;
    const sec = BR.bytes.sections, raw = [sec.flags + sec.unknown, sec.water, sec.forest, sec.unknown_forest];
    const thick = raw.map(b => 0.5 + 3.5 * Math.sqrt(b / sec.forest)), slabY = raw.map((_, k) => 17 - k * 6.4), tsum = thick.reduce((a, b) => a + b);
    const slabCol = [C.unk, C.water, C.forest, C.purple], evY = -10.5, yrY = -15.5;
    const nOut = Math.round(N * 0.06), nEv = 70, nYr = 30, nSlab = Math.round(N * 0.55);
    const corner = k => [(k & 1) ? 1 : -1, (k & 2) ? 1 : -1, (k & 4) ? 1 : -1];
    const edges = []; for (let a = 0; a < 8; a++) for (let b = a + 1; b < 8; b++) { const d = a ^ b; if ((d & (d - 1)) === 0) edges.push([a, b]); }
    for (let i = 0; i < N; i++) {
      const r = P.rank[i];
      if (r < nOut) {
        const [a, b] = edges[r % 12], A = corner(a), B = corner(b), u = rn(i, 21);
        put(F, i, bx + L / 2 * (A[0] + (B[0] - A[0]) * u), L / 2 * (A[1] + (B[1] - A[1]) * u), L / 2 * (A[2] + (B[2] - A[2]) * u), C.bytes, 0.55, 0.95);
      } else if (r < nOut + nEv) {
        put(F, i, cs - sw / 2 + (r - nOut) / (nEv - 1) * sw, evY + (rn(i, 22) - 0.5) * 0.15, 0, C.loss, 1, 1.35);
      } else if (r < nOut + nEv + nYr) {
        const q = r - nOut - nEv;
        put(F, i, cs - 3 + (q % 15) / 14 * 6, yrY + ((q / 15) | 0) * 0.45, 0, C.past, 0.95, 1.1);
      } else if (r < nOut + nEv + nYr + nSlab) {
        let u = rn(i, 24) * tsum, k = 0; while (k < 3 && u > thick[k]) { u -= thick[k]; k++; }
        put(F, i, cs + (rn(i, 25) - 0.5) * sw, slabY[k] + (rn(i, 26) - 0.5) * thick[k], (rn(i, 27) - 0.5) * sw, slabCol[k], k === 2 ? 0.3 : 0.55, 0.9);
      } else dust(F, i);
    }
    const lx = cs + sw / 2 + 4;
    F.labels.push({ p: [bx, -L / 2 - 3.5, 0], text: '623,237 B original', align: 'c' }, { p: [cs, slabY[0] + 7, 0], text: '6,146 B .plds', align: 'c' });
    ['flags + unknown \u00b7 2 B', 'water \u00b7 449 B', 'forest \u00b7 4,453 B', 'forest unknown \u00b7 36 B'].forEach((t, k) => F.labels.push({ p: [lx, slabY[k], 0], text: t, align: 'l' }));
    F.labels.push({ p: [lx, evY, 0], text: 'loss events \u00b7 366 B', align: 'l' }, { p: [lx, yrY, 0], text: 'years \u00b7 145 B', align: 'l' });
    return F;
  },
  query(P) {
    const F = newForm(P.N, [0, 0, 0], '#6E7BFF'), poly = P.poly;
    const nOut = 400;
    for (let i = 0; i < P.N; i++) {
      const r = P.rank[i];
      if (r < nOut) {
        const u = r / nOut * poly.length, k = Math.floor(u), f = u - k, A = poly[k], B = poly[(k + 1) % poly.length];
        put(F, i, A[0] + (B[0] - A[0]) * f, A[1] + (B[1] - A[1]) * f, 0.5, C.pen, 1, 1.35);
        continue;
      }
      const [c, a] = codeStyle(P.code[i]);
      if (inside(poly, P.x[i], P.y[i])) put(F, i, P.x[i], P.y[i], 0, c, Math.max(a, 0.8) * P.bw[i], 1.2);
      else put(F, i, P.x[i], P.y[i], 0, c, 0.18 * P.bw[i], 0.95);
    }
    return F;
  },
  paths(P) {
    const F = newForm(P.N, [0, 0, 0], '#6E7BFF'), mult = [1, 5.2, 44, 83, 410], L = 84, S = 44, used = P.N * 0.7, ids = ['P0 \u00b7 1\u00d7', 'P4 \u00b7 5.2\u00d7', 'P5d \u00b7 44\u00d7', 'P5Ld \u00b7 83\u00d7', 'P6d \u00b7 410\u00d7'];
    const col = [C.bytes, C.pen, C.pen, mix3(C.pen, C.forest, 0.5), C.forest];
    for (let i = 0; i < P.N; i++) {
      const r = P.rank[i];
      if (r >= used) { dust(F, i); continue; }
      const lane = r % 5, sidx = (Math.floor(r / 5) * 7919 + lane) % S, len = (1.8 + 1.1 * Math.log(mult[lane])) * (0.55 + rn(sidx + lane * 97, 41));
      const head = ((sidx + rn(sidx + lane * 97, 40)) / S) * L - L / 2, u = rn(i, 31);
      put(F, i, head - len * Math.pow(u, 1.5), (2 - lane) * 9 + (rn(i, 33) - 0.5) * 0.18, 0, col[lane], 0.95 * Math.pow(1 - u, 0.9), 0.85, 4 + 9 * Math.log(mult[lane]));
    }
    ids.forEach((t, k) => F.labels.push({ p: [-L / 2 - 1.5, (2 - k) * 9, 0], text: t, align: 'r', raw: true }));
    return F;
  },
  phases(P) {
    const F = newForm(P.N, [0, 0, 0], '#2BD47D'), X = [-36, -18, 0, 18, 36], ys = v => -18 + Math.log10(v) / Math.log10(60) * 38;
    const reg = BR.phaseSeries.reg[0].v, nb = BR.phaseSeries.newb[0].v;
    const series = [[reg, C.pen], [nb, C.forest]], nGrid = Math.round(P.N * 0.18), nLine = Math.round(P.N * 0.2), nMark = 70;
    for (let i = 0; i < P.N; i++) {
      const r = P.rank[i];
      if (r < nGrid) {
        const k = r % 11;
        if (k < 6) put(F, i, -42 + rn(i, 41) * 84, ys([1, 2, 5, 10, 20, 50][k]), -1, C.bytes, 0.2, 0.8);
        else put(F, i, X[k - 6 < 5 ? k - 6 : 4], -20 + rn(i, 42) * 40, -1, C.bytes, 0.14, 0.8);
      } else if (r < nGrid + 2 * nLine) {
        const s = (r - nGrid) % 2, [v, c] = series[s], u = rn(i, 43) * 4, k = Math.min(3, Math.floor(u)), f = u - k;
        put(F, i, X[k] + (X[k + 1] - X[k]) * f, ys(v[k] + (v[k + 1] - v[k]) * f) + (rn(i, 44) - 0.5) * 0.5, 0, c, 0.85, 1.05);
      } else if (r < nGrid + 2 * nLine + 10 * nMark) {
        const m = r - nGrid - 2 * nLine, s = m % 2, k = ((m / 2) | 0) % 5, [v, c] = series[s];
        put(F, i, X[k] + gauss(i, 45) * 0.8, ys(v[k]) + gauss(i, 48) * 0.8, 0.5, mix3(c, C.mk, 0.35), 1, 1.35);
      } else dust(F, i);
    }
    F.labels.push({ p: [X[4] + 2.5, ys(reg[4]), 0], text: reg[4] + '\u00d7', align: 'l' }, { p: [X[4] + 2.5, ys(nb[4]), 0], text: nb[4] + '\u00d7', align: 'l' },
      { p: [X[0] - 2.5, ys(reg[0]), 0], text: reg[0] + '\u00d7', align: 'r' }, { p: [X[0] - 2.5, ys(nb[0]), 0], text: nb[0] + '\u00d7', align: 'r' });
    return F;
  },
  benchmarks(P) {
    const F = newForm(P.N, [-0.35, 0, 0], '#2BD47D'), n1 = Math.round(P.N * 0.46), n2 = Math.max(24, Math.round(n1 * 6146 / 623237)), nRing = Math.round(P.N * 0.07);
    for (let i = 0; i < P.N; i++) {
      const r = P.rank[i];
      if (r < n1) put(F, i, -14 + (rn(i, 51) - 0.5) * 5, -24 + (r / n1) * 46, (rn(i, 52) - 0.5) * 5, C.bytes, 0.3, 0.95);
      else if (r < n1 + n2) put(F, i, 14 + (rn(i, 53) - 0.5) * 5, -24 + ((r - n1) / n2) * 0.46 + 0.1, (rn(i, 54) - 0.5) * 5, C.forest, 1, 1.5);
      else if (r < n1 + n2 + nRing) {
        const a = (r - n1 - n2) / nRing * 6.2832;
        put(F, i, 36 * Math.cos(a), -2 + 1.2 * Math.sin(a * 3), 36 * Math.sin(a), mix3(C.forest, C.ver, 0.4), 0.9, 1.2, 0, 0.25);
      } else dust(F, i);
    }
    F.labels.push({ p: [-14, -27, 0], text: '623,237 B', align: 'c' }, { p: [14, -27, 0], text: '6,146 B', align: 'c' });
    return F;
  },
  decisions(P) {
    const F = newForm(P.N, [-0.12, 0, 0], '#6E7BFF'), K = 19, per = Math.floor(P.N * 0.8 / K);
    for (let i = 0; i < P.N; i++) {
      const r = P.rank[i], k = Math.floor(r / per);
      if (k >= K) { dust(F, i); continue; }
      const phi = (165 - k / (K - 1) * 150) * Math.PI / 180, cx = 40 * Math.cos(phi), cy = -8 + 29 * Math.sin(phi), kind = k < 8 ? 0 : k < 14 ? 1 : 2;
      const c = [C.pen, C.land, C.amber][kind], rad = 2.3;
      put(F, i, cx + gauss(i, 61) * rad, cy + gauss(i, 62) * rad, gauss(i, 63) * rad, c, [0.85, 0.5, 0.85][kind], 1);
    }
    return F;
  },
  limits(P) {
    const F = newForm(P.N, [-0.25, 0, 0], '#FF7A2E'), m = Math.max(5, Math.floor(Math.sqrt(P.N * 0.7 / 81))), pitch = 8, side = 6.2;
    const poly = [[-40, -28], [4, 6], [40, 12], [60, 12], [60, -60], [-40, -60]], nEdge = 240;
    for (let i = 0; i < P.N; i++) {
      const r = P.rank[i];
      if (r < 81 * m * m) {
        const cell = (r / (m * m)) | 0, q = r % (m * m), gx = cell % 9, gy = (cell / 9) | 0, cx = (gx - 4) * pitch, cy = (gy - 4) * pitch;
        const lit = inside(poly, cx, cy), px = (q % m + 0.5) / m, py = (((q / m) | 0) + 0.5) / m;
        put(F, i, cx + (px - 0.5) * side, cy + (py - 0.5) * side, 0, lit ? C.forest : C.unk, lit ? 0.9 : 0.07, lit ? 1.2 : 1);
      } else if (r < 81 * m * m + nEdge) {
        const u = (r - 81 * m * m) / nEdge * 2, k = Math.min(1, Math.floor(u)), f = u - k, A = poly[k], B = poly[k + 1];
        put(F, i, A[0] + (B[0] - A[0]) * f, A[1] + (B[1] - A[1]) * f, 0.6, C.pen, 1, 1.4);
      } else dust(F, i);
    }
    F.labels.push({ p: [0, -39, 0], text: 'centre in \u2192 counted', align: 'c' });
    return F;
  },
  reproduce(P) {
    const F = newForm(P.N, [-0.35, 0, 0], '#2BD47D');
    for (let i = 0; i < P.N; i++) { const [c, a] = codeStyle(P.code[i]); put(F, i, P.x[i], P.y[i], 0, c, a * 0.5 * P.bw[i]); }
    return F;
  },
  contact(P) {
    const F = newForm(P.N, [0.25, 0, 0.35], '#4C9BE8'), R0 = MW / 2.5, ga = Math.PI * (3 - Math.sqrt(5)), nClu = Math.round(P.N * 0.016);
    for (let i = 0; i < P.N; i++) {
      const r = P.rank[i];
      let lat, lon;
      if (r < nClu) { lat = (8.5 + gauss(i, 71) * 2.6) * Math.PI / 180; lon = (gauss(i, 72) * 3.2) * Math.PI / 180; }
      else { lat = Math.asin(1 - 2 * (r + 0.5) / P.N); lon = r * ga; }
      const x = R0 * Math.cos(lat) * Math.sin(lon), y = R0 * Math.sin(lat), z = R0 * Math.cos(lat) * Math.cos(lon);
      if (r < nClu) { put(F, i, x, y, z, C.forest, 1, 1.5, 0, 0.17); continue; }
      const land = Math.sin(lon * 2.1 + 0.4) * Math.cos(lat * 2.4) + 0.6 * Math.sin(lat * 5 + lon) > 0.35;
      put(F, i, x, y, z, land ? mix3(C.water, C.forest, 0.55) : C.water, land ? 0.55 : 0.32, 0.95, 0, 0.17);
    }
    F.labels.push({ p: [0, R0 * Math.sin(8.5 * Math.PI / 180), R0 * Math.cos(8.5 * Math.PI / 180)], text: 'Surat Thani \u00b7 8.5\u00b0N 99\u00b0E', align: 'l', dx: 34, spin: 0.17, back: R0 });
    return F;
  },
};
const ID_FORM = { top: 'hero', framing: 'framing', layers: 'layers', schema: 'schema', store: 'store', query: 'query', paths: 'paths', phases: 'phases', benchmarks: 'benchmarks', decisions: 'decisions', limits: 'limits', reproduce: 'reproduce', contact: 'contact' };

/* synthetic query polygon: irregular 9-gon, ~8% of the map, centre-right */
function makePolygon(P) {
  const pts = [], rad = [1, 0.8, 1.15, 0.9, 1.2, 0.78, 1.05, 0.85, 1.1], cx = 14, cy = -3;
  rad.forEach((r, k) => { const a = k / 9 * 6.2832 + 0.3; pts.push([Math.cos(a) * r, Math.sin(a) * r]); });
  let A = 0; pts.forEach((p, k) => { const q = pts[(k + 1) % 9]; A += p[0] * q[1] - q[0] * p[1]; });
  const s = Math.sqrt(0.08 * MW * P.MH / Math.abs(A / 2));
  return pts.map(p => [cx + p[0] * s, cy + p[1] * s]);
}

/* ---------- shaders ---------- */
const VERT = `
attribute vec3 posB; attribute vec4 colA; attribute vec4 colB; attribute vec4 aRand; attribute vec3 aFA; attribute vec3 aFB;
uniform float uT, uTime, uPx, uDist, uBase, uFlowL, uScanY, uScanK, uBreath, uShiftA, uShiftB, uLight; uniform vec2 uScan; uniform vec4 uVer;
varying vec4 vCol;
vec3 rotY(vec3 p, float a) { float c = cos(a), s = sin(a); return vec3(c * p.x + s * p.z, p.y, -s * p.x + c * p.z); }
vec3 place(vec3 p, vec3 f) {
  if (f.z != 0.0) p = rotY(p, f.z * uTime);
  if (f.x != 0.0) p.x = mod(p.x + uFlowL * 0.5 + f.x * uTime, uFlowL) - uFlowL * 0.5;
  return p;
}
vec4 shade(vec4 c, vec3 f, vec3 p, float on) {
  if (f.x != 0.0) c.a *= 1.0 - smoothstep(0.38, 0.5, abs(p.x) / uFlowL);
  if (on > 0.5) {
    float d = p.y - uScanY;
    float v = smoothstep(-0.3, 0.9, d) * uScanK;
    float band = exp(-d * d / 0.5) * uScanK;
    c.rgb = mix(c.rgb, uVer.rgb, v);
    c.a = mix(c.a, uVer.a, v) + band * 0.6;
  }
  return c;
}
void main() {
  float s = aRand.x;
  float t = smoothstep(s * 0.35, s * 0.35 + 0.65, uT);
  float te = mix(t, 1.0 - pow(1.0 - t, 3.0), 0.6);
  vec3 a = place(position, aFA), b = place(posB, aFB);
  vec3 p = mix(a, b, te);
  float arc = sin(3.14159 * t);
  vec3 d = b - a;
  vec3 perp = normalize(cross(d, vec3(0.0, 0.0, 1.0)) + vec3(0.0001));
  p += perp * (aRand.y - 0.5) * 2.0 * (length(d) * 0.1 + 2.0) * arc;
  p += (aRand.yzw - 0.5) * 5.0 * arc;
  p += vec3(sin(uTime * 1.7 + s * 40.0), cos(uTime * 1.3 + s * 55.0), sin(uTime * 1.1 + s * 30.0)) * 0.6 * arc;
  p += vec3(sin(uTime * 0.8 + s * 31.0), cos(uTime * 0.7 + s * 47.0), sin(uTime * 0.9 + s * 19.0)) * 0.28 * uBreath;
  vec4 ca = shade(colA, aFA, a, uScan.x), cb = shade(colB, aFB, b, uScan.y);
  vCol = mix(ca, cb, te);
  vCol.rgb *= mix(1.0 + 0.35 * arc, 1.0 - 0.18 * arc, uLight);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  float sz = mix(aFA.y, aFB.y, te) * (1.0 + 0.18 * arc);
  gl_PointSize = clamp(uBase * sz * uPx * uDist / -mv.z, 1.0, 18.0);
  vec4 clip = projectionMatrix * mv;
  clip.y += mix(uShiftA, uShiftB, te) * clip.w;
  gl_Position = clip;
}`;
const FRAG = `
varying vec4 vCol; uniform float uLight;
void main() {
  float r = length(gl_PointCoord - 0.5) * 2.0;
  if (r > 1.0) discard;
  if (uLight > 0.5) { gl_FragColor = vec4(vCol.rgb, vCol.a * (1.0 - smoothstep(0.7, 1.0, r))); return; }
  float f = 1.0 - smoothstep(0.3, 1.0, r);
  float a = vCol.a * f;
  gl_FragColor = vec4(vCol.rgb * a * 1.15, a);
}`;

/* ---------- boot ---------- */
async function boot() {
  let THREE;
  try { THREE = await import('three'); } catch (e) { console.warn('Swarm: three.js unavailable, page continues without it', e); return; }
  const R = await getRegion();

  /* page contract: canvas, stylesheet, data-swarm attributes (added only when missing) */
  if (!document.querySelector('link[href$="swarm.css"]')) { const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = new URL('swarm.css', import.meta.url).href; document.head.append(l); }
  let canvas = document.getElementById('swarm');
  if (!canvas) { canvas = document.createElement('canvas'); canvas.id = 'swarm'; canvas.setAttribute('aria-hidden', 'true'); document.body.prepend(canvas); }
  Object.entries(ID_FORM).forEach(([id, f]) => { const el = document.getElementById(id); if (el && !el.dataset.swarm) el.dataset.swarm = f; });
  const secs = [...document.querySelectorAll('[data-swarm]')];

  const P = buildPoints(R, MOBILE() ? 5000 : 14000);
  P.poly = makePolygon(P);
  const chain = ['nebula', ...secs.map(s => s.dataset.swarm)].filter(n => FORMS[n]);
  const built = {};
  chain.forEach(n => { if (!built[n]) built[n] = FORMS[n](P); });
  const forms = chain.map(n => built[n]);
  const hasScan = forms.map((_, k) => chain[k] === 'reproduce');
  const N = P.N;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: true, powerPreference: 'high-performance' });
  renderer.setClearColor(0x000000, 0);
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(30, 1, 1, 1000), cloud = new THREE.Group();
  scene.add(cloud);
  const geo = new THREE.BufferGeometry();
  const attr = (name, n, arr) => { const a = new THREE.BufferAttribute(arr, n); a.setUsage(THREE.DynamicDrawUsage); geo.setAttribute(name, a); return a; };
  const aPos = attr('position', 3, new Float32Array(3 * N)), aPosB = attr('posB', 3, new Float32Array(3 * N));
  const aColA = attr('colA', 4, new Float32Array(4 * N)), aColB = attr('colB', 4, new Float32Array(4 * N));
  const aFA = attr('aFA', 3, new Float32Array(3 * N)), aFB = attr('aFB', 3, new Float32Array(3 * N));
  const rnd = new Float32Array(4 * N); for (let i = 0; i < N; i++) { rnd[4 * i] = rn(i, 91); rnd[4 * i + 1] = rn(i, 92); rnd[4 * i + 2] = rn(i, 93); rnd[4 * i + 3] = rn(i, 94); }
  geo.setAttribute('aRand', new THREE.BufferAttribute(rnd, 4));
  const U = { uT: { value: 0 }, uTime: { value: 0 }, uPx: { value: 1 }, uDist: { value: 200 }, uBase: { value: 2.2 }, uFlowL: { value: 84 },
    uScanY: { value: 0 }, uScanK: { value: 0 }, uBreath: { value: REDUCE ? 0 : 1 }, uScan: { value: new THREE.Vector2() },
    uShiftA: { value: 0 }, uShiftB: { value: 0 }, uLight: { value: DARK ? 0 : 1 }, uVer: { value: new THREE.Vector4(...(DARK ? [0.62, 0.95, 0.74, 0.5] : [...C.ver, 0.9])) } };
  const mat = new THREE.ShaderMaterial({ vertexShader: VERT, fragmentShader: FRAG, uniforms: U, transparent: true, depthTest: false, depthWrite: false,
    blending: DARK ? THREE.CustomBlending : THREE.NormalBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor, blendSrcAlpha: THREE.OneFactor, blendDstAlpha: THREE.OneFactor });
  const pts = new THREE.Points(geo, mat); pts.frustumCulled = false; cloud.add(pts);

  let pa = -1, pb = -1;
  function setPair(a, b) {
    if (a === pa && b === pb) return;
    if (a !== pa) { const F = forms[a]; aPos.array.set(F.pos); aColA.array.set(F.col); aFA.array.set(F.fx); aPos.needsUpdate = aColA.needsUpdate = aFA.needsUpdate = true; }
    const G = forms[b]; aPosB.array.set(G.pos); aColB.array.set(G.col); aFB.array.set(G.fx); aPosB.needsUpdate = aColB.needsUpdate = aFB.needsUpdate = true;
    pa = a; pb = b; U.uScan.value.set(hasScan[a] ? 1 : 0, hasScan[b] ? 1 : 0);
  }

  /* size and camera: formation centre sits in the right ~55% on desktop */
  let vw = 1, vh = 1, desktop = true, visWnow = 222;
  function resize() {
    vw = document.documentElement.clientWidth || innerWidth; vh = innerHeight; desktop = vw >= 820;
    const dpr = Math.min(devicePixelRatio || 1, 2);
    renderer.setPixelRatio(dpr); renderer.setSize(vw, vh, false);
    camera.aspect = vw / vh;
    const visW = visWnow = desktop ? 222 : 112, visH = Math.max(visW / camera.aspect, desktop ? 0 : 120), dist = visH / (2 * Math.tan(camera.fov * Math.PI / 360));
    camera.position.set(0, 0, dist); camera.far = dist * 4;
    if (desktop) camera.setViewOffset(vw, vh, -0.225 * vw, 0, vw, vh); else camera.clearViewOffset();
    camera.updateProjectionMatrix();
    U.uPx.value = dpr; U.uDist.value = dist; U.uBase.value = desktop ? 3.4 : 2.8;
    camera.updateMatrixWorld(); fitHero(); trail.resize(dpr); lbl.resize(dpr); dirty = true;
  }

  /* hero map must clear the lede by 32px: measure the projected map extent, then scale/shift it (applied to the cloud by hero weight) */
  const heroIdx = chain.indexOf('hero'), hero = { k: 1, dx: 0, left: 0, need: 0 };
  function fitHero() {
    hero.k = 1; hero.dx = 0;
    const F = forms[heroIdx]; if (!desktop || !F || !F.bbox) return;
    const lede = document.querySelector('#top .lede'); let right = 0;
    if (lede) { const r = document.createRange(); r.selectNodeContents(lede); right = r.getBoundingClientRect().right; }
    hero.need = right + 32;
    const m = new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(...F.rot)), [x0, x1, y0, y1, z0, z1] = F.bbox, v = new THREE.Vector3();
    let L = 1e9, Rr = -1e9;
    [x0, x1].forEach(x => [y0, y1].forEach(y => [z0, z1].forEach(z => { v.set(x, y, z).applyMatrix4(m).project(camera); const px = (v.x * 0.5 + 0.5) * vw; L = Math.min(L, px); Rr = Math.max(Rr, px); })));
    v.set(0, 0, 0).project(camera); const cx = (v.x * 0.5 + 0.5) * vw, edge = vw - 14;
    hero.k = Math.min(1, (edge - hero.need) / (Rr - L));
    const left = cx + (L - cx) * hero.k; hero.left = Math.max(left, hero.need);
    hero.dx = Math.max(0, hero.need - left) * visWnow / vw;
  }
  /* ---------- annotations: tiny mono labels projected from each formation's `labels` ---------- */
  const lbl = (() => {
    const cv = document.createElement('canvas'); cv.id = 'swarm-labels'; cv.setAttribute('aria-hidden', 'true'); canvas.after(cv);
    const ctx = cv.getContext('2d'), v = new THREE.Vector3(), o = new THREE.Vector3(), q = new THREE.Vector3();
    let dpr = 1;
    return {
      resize(d) { dpr = d; cv.width = vw * d; cv.height = vh * d; },
      draw(a, b, f, time, shifts) {
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, vw, vh);
        if (!desktop) return;
        ctx.font = '500 10.5px "Geist Mono", ui-monospace, Menlo, monospace'; ctx.fillStyle = C.label; ctx.textBaseline = 'middle';
        if ('letterSpacing' in ctx) ctx.letterSpacing = '0.63px';
        cloud.updateMatrixWorld(true); camera.updateMatrixWorld();
        const sets = a === b ? [[a, 1]] : [[a, clamp(1 - f / 0.25, 0, 1)], [b, clamp((f - 0.7) / 0.3, 0, 1)]];
        sets.forEach(([k, w]) => {
          if (w <= 0.01) return;
          forms[k].labels.forEach(l => {
            let [x, y, z] = l.p, al = w;
            if (l.spin) { const c = Math.cos(l.spin * time), sn = Math.sin(l.spin * time); [x, z] = [c * x + sn * z, -sn * x + c * z]; }
            v.set(x, y, z).applyMatrix4(cloud.matrixWorld);
            if (l.back) { q.copy(v).applyMatrix4(camera.matrixWorldInverse); o.set(0, 0, 0).applyMatrix4(cloud.matrixWorld).applyMatrix4(camera.matrixWorldInverse); al *= clamp((q.z - o.z) / (l.back * 0.35), 0, 1); }
            if (al <= 0.01) return;
            v.project(camera); v.y += shifts[k];
            const px = (v.x * 0.5 + 0.5) * vw + (l.dx || 0), py = (-v.y * 0.5 + 0.5) * vh + (l.dy || 0);
            ctx.globalAlpha = al; ctx.textAlign = l.align === 'r' ? 'right' : l.align === 'l' ? 'left' : 'center';
            ctx.fillText(l.raw ? l.text : l.text.toUpperCase(), px, py);
          });
        });
        ctx.globalAlpha = 1;
      },
    };
  })();

  /* ---------- anchors: each formation rides with its section's .prose block (hero: header#top) and scrolls like page content ---------- */
  const anchorEls = chain.map((_, j) => { const sec = secs[Math.max(0, j - 1)]; return (sec.id === 'top' ? sec : sec.querySelector('.prose')) || sec; });
  const rects = new Array(chain.length), cys = new Array(chain.length), shifts = new Array(chain.length).fill(0);
  function readAnchors() {
    for (let j = 0; j < anchorEls.length; j++) {
      const r = rects[j] = anchorEls[j].getBoundingClientRect();
      cys[j] = r.top + r.height / 2;
      if (j <= 1) cys[j] = Math.min(cys[j], vh * 0.5);        /* the hero is clamped so it never sits low on first load */
    }
    /* morph into formation j starts when its .prose top enters the viewport bottom and ends when its centre reaches 50% of the viewport */
    let t = 1;
    for (let j = 2; j < anchorEls.length; j++) t += clamp((vh - rects[j].top) / (0.5 * vh + rects[j].height / 2), 0, 1);
    return t;
  }
  const _o = new THREE.Vector3();
  function computeShifts() {
    cloud.updateMatrixWorld(true);
    const oy = _o.set(0, 0, 0).applyMatrix4(cloud.matrixWorld).project(camera).y;
    for (let j = 0; j < cys.length; j++) shifts[j] = (1 - 2 * cys[j] / vh) - oy;
  }

  /* ---------- cursor trail (2D overlay, pointer: fine only) ---------- */
  const trail = (() => {
    const fine = matchMedia('(pointer: fine)').matches && !REDUCE;
    if (!fine) return { resize() {}, draw() {}, move() {} };
    const cv = document.createElement('canvas'); cv.id = 'swarm-trail'; cv.setAttribute('aria-hidden', 'true'); document.body.append(cv);
    const ctx = cv.getContext('2d'), F = [[0.28, 2.4], [0.15, 1.9], [0.08, 1.5]].map(([k, r]) => ({ k, r, x: -99, y: -99, h: [] }));
    let px = -99, py = -99, last = -1e9, dpr = 1, cleared = true, tick = 0;
    return {
      resize(d) { dpr = d; cv.width = innerWidth * d; cv.height = innerHeight * d; },
      move(x, y) { if (px < 0) F.forEach(f => { f.x = x; f.y = y; }); px = x; py = y; last = performance.now(); },
      draw(rgb, dt) {
        const idle = (performance.now() - last) / 1000, al = clamp(1 - (idle - 1.6) / 0.4, 0, 1) * 0.6;
        if (al <= 0) { if (!cleared) { ctx.clearRect(0, 0, cv.width, cv.height); cleared = true; } return; }
        cleared = false; tick++;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, innerWidth, innerHeight); ctx.globalCompositeOperation = DARK ? 'lighter' : 'source-over';
        const col = rgb.map(v => Math.round(v * 255)).join(',');
        F.forEach(f => {
          const k = 1 - Math.pow(1 - f.k, dt * 60); f.x += (px - f.x) * k; f.y += (py - f.y) * k;
          if (tick % 2 === 0) { f.h.unshift([f.x, f.y]); if (f.h.length > 8) f.h.pop(); }
          f.h.forEach(([x, y], j) => { ctx.fillStyle = `rgba(${col},${al * 0.5 * (1 - (j + 1) / 9)})`; ctx.beginPath(); ctx.arc(x, y, f.r * (1 - j / 12), 0, 6.2832); ctx.fill(); });
          ctx.fillStyle = `rgba(${col},${al})`; ctx.beginPath(); ctx.arc(f.x, f.y, f.r, 0, 6.2832); ctx.fill();
        });
      },
    };
  })();

  /* ---------- loop ---------- */
  let s = 0, focus = [0.5, 0.5], focusS = [0.5, 0.5], ptr = [0, 0], ptrS = [0, 0], dirty = true, raf = 0, last = performance.now(), t0 = last, intro = !REDUCE && scrollY < 200, introT = 0, lastKey = '', accentKey = '';
  addEventListener('pointermove', e => { ptr = [e.clientX / vw * 2 - 1, e.clientY / vh * 2 - 1]; trail.move(e.clientX, e.clientY); }, { passive: true });
  addEventListener('resize', resize);
  document.fonts && document.fonts.ready.then(() => { fitHero(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) { cancelAnimationFrame(raf); raf = 0; } else if (!raf) { last = performance.now(); raf = requestAnimationFrame(frame); } });
  const accentRgb = h => hex(h);

  function frame(now) {
    raf = requestAnimationFrame(frame);
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    const tg = readAnchors();
    if (REDUCE) s = Math.round(tg);
    else {
      if (intro && tg > 1.05) intro = false;
      if (intro) { introT += dt; const k = clamp(introT / 1.6, 0, 1); s = 1 - Math.pow(1 - k, 3); if (k >= 1) intro = false; }
      else { s += (tg - s) * (1 - Math.pow(1 - 0.15, dt * 60)); if (Math.abs(tg - s) < 0.0005) s = tg; }
    }
    const a = clamp(Math.floor(s), 0, forms.length - 1), b = Math.min(a + 1, forms.length - 1), f = a === b ? 0 : s - a;
    setPair(a, b);
    U.uT.value = f; U.uTime.value = REDUCE ? 4 : (now - t0) / 1000;
    /* reproduce: scan line sweeps top -> bottom, holds, then the verified glow fades out */
    const ph = REDUCE ? 7 : U.uTime.value % 9, top = P.MH / 2 + 1;
    U.uScanY.value = ph < 6 ? top - (ph / 6) * (P.MH + 2) : -top; U.uScanK.value = ph < 8 ? 1 : 9 - ph;
    /* rotation per formation + parallax */
    const e = f * f * (3 - 2 * f), A = forms[a].rot, B = forms[b].rot;
    ptrS[0] += (ptr[0] - ptrS[0]) * 0.05; ptrS[1] += (ptr[1] - ptrS[1]) * 0.05;
    focusS[0] += (focus[0] - focusS[0]) * 0.06; focusS[1] += (focus[1] - focusS[1]) * 0.06;
    const par = REDUCE ? 0 : 1;
    cloud.rotation.set(A[0] + (B[0] - A[0]) * e - ptrS[1] * 0.05 * par + Math.sin(scrollY * 0.0012) * 0.025 * par,
      A[1] + (B[1] - A[1]) * e + ptrS[0] * 0.06 * par, A[2] + (B[2] - A[2]) * e);
    const hw = (chain[a] === 'hero' ? 1 - e : 0) + (chain[b] === 'hero' && a !== b ? e : 0), sc = 1 - (1 - hero.k) * hw;
    cloud.scale.setScalar(sc);
    cloud.position.set((focusS[0] - 0.5) * 24 + hero.dx * hw, -(focusS[1] - 0.5) * 14, 0);
    computeShifts(); U.uShiftA.value = shifts[a]; U.uShiftB.value = shifts[b];
    /* accent */
    const ac = C.trail || mix3(accentRgb(forms[a].accent), accentRgb(forms[b].accent), e);
    const key = (f > 0.5 ? forms[b] : forms[a]).accent;
    if (key !== accentKey) { accentKey = key; document.documentElement.style.setProperty('--swarm-accent', key); }
    trail.draw(ac, dt); lbl.draw(a, b, f, U.uTime.value, shifts);
    const k = REDUCE ? `${s}|${vw}|${vh}` : '';
    if (!REDUCE || dirty || k !== lastKey) { renderer.render(scene, camera); lastKey = k; dirty = false; }
  }

  const trailRef = trail;
  resize();
  if (!intro) s = Math.round(readAnchors() * 100) / 100;
  setPair(...(() => { const a0 = clamp(Math.floor(s), 0, forms.length - 1); return [a0, Math.min(a0 + 1, forms.length - 1)]; })());
  raf = requestAnimationFrame(frame);
  canvas.classList.add('on');
  void trailRef;

  window.Swarm = {
    N, formations: chain, ready: Promise.resolve(),
    setFocus(x01, y01) { focus = [clamp(x01, 0, 1), clamp(y01, 0, 1)]; },
    state: () => ({ hero: { ...hero }, dark: DARK, shifts: shifts.slice(), s, a: pa, b: pb, name: chain[clamp(Math.round(s), 0, chain.length - 1)], N, fake: !!R.fake }),
  };
}
window.Swarm = { setFocus() {}, N: 0, ready: boot().catch(e => console.warn('Swarm failed', e)) };

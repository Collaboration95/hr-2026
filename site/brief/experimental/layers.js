/* #layers: scroll-driven 3D layer stack (three.js, orthographic isometric). Textures are the real region rasters.
   The stage is pinned with CSS position: sticky; scroll stays native and only reads window.scrollY. */
const { $, $$, h, fmt, esc } = UI;
const REDUCE = Brief.REDUCE;

const STEPS = [
  { title: 'Source rasters', text: 'Four GeoTIFFs cover the region: Hansen treecover2000, lossyear and datamask, and the JRC 2020 forest class.', row: 0 },
  { title: 'Layers separated', text: 'Each EUDR question reads a subset. treecover2000 alone is 414,142 B, 72% of the Hansen bytes.', row: 0 },
  { title: 'Unread: treecover2000', text: 'No question reads canopy %. The contract reads three files: lossyear, datamask and JRC.', row: 1 },
  { title: 'Unread: loss before 2021', text: 'JRC supplies forest at the cut-off, so loss years 2001–2020 are not read. JRC is read at 1 of every 9 cells. One screening plane remains.', row: 2 },
  { title: 'One decision plane', text: 'Loss year is also forgotten on land that was not forest in 2020. Each cell holds one of 20 codes.', row: 4 },
];
const B = BR.bytes;
const CHAIN = [
  { n: 'Original layers', sub: '4 GeoTIFFs', b: B.total, basis: 'GeoTIFF files' },
  { n: 'Without treecover2000', sub: '3 files the contract reads', b: B.contractInputs, basis: 'GeoTIFF files' },
  { n: 'Screening plane', sub: 'JRC at centres, no pre-2021 loss', b: B.zstd19Screen, basis: 'zstd-19 plane', alt: `${fmt(B.screenStore)} B as a store` },
  { n: 'Decision plane', sub: 'loss year forgotten on non-forest', b: B.zstd19Decision, basis: 'zstd-19 plane' },
  { n: 'Decision store', sub: '.plds, bit-planes + loss events', b: B.decisionStore, basis: '.plds file' },
];
const FILES = [
  { id: 'treecover', n: 'Hansen treecover2000', b: B.originals[0].b },
  { id: 'loss', n: 'Hansen lossyear', b: B.originals[1].b },
  { id: 'mask', n: 'Hansen datamask', b: B.originals[2].b },
  { id: 'jrc', n: 'JRC 2020 forest', b: B.originals[3].b },
];

/* ---------------------------------------------------------------- side panel */
const el = { no: $('#br-step-no'), title: $('#br-step-title'), text: $('#br-step-text'), n: $('#br-bytes-n'), b: $('#br-bytes-b'), chain: $('#br-chain'), steps: $('#br-steps') };
const rows = CHAIN.map((c, i) => {
  const bar = h('i', {}), val = h('span', { class: 'v' }, fmt(c.b) + ' B');
  const r = h('div', { class: 'br-crow' }, h('div', { class: 'l' }, h('b', {}, c.n), h('small', {}, `${c.sub} · ${c.basis}${c.alt ? ' · ' + c.alt : ''}`)), h('div', { class: 'tr' }, bar), val);
  bar.style.width = Math.max(1.2, 100 * c.b / B.total) + '%';
  el.chain.append(r); return r;
});
const stepBtns = STEPS.map((s, i) => { const b = h('button', { type: 'button', 'aria-label': `Step ${i + 1}: ${s.title}` }, String(i + 1)); el.steps.append(b); return b; });
let shownStep = -1, shownBytes = B.total, bytesRaf = 0;
function setStep(k) {
  if (k === shownStep) return; shownStep = k;
  const s = STEPS[k];
  el.no.textContent = `Step ${k + 1} of ${STEPS.length}`; el.title.textContent = s.title; el.text.textContent = s.text;
  const target = k === 4 ? B.decisionStore : CHAIN[s.row].b;
  const basis = k === 4 ? '.plds file · zstd-19 plane 9,874 B' : CHAIN[s.row].basis + (CHAIN[s.row].alt ? ' · ' + CHAIN[s.row].alt : '');
  el.b.textContent = basis;
  const from = shownBytes; cancelAnimationFrame(bytesRaf);
  if (REDUCE) { el.n.textContent = fmt(target); shownBytes = target; }
  else { const t0 = performance.now(); const tick = now => { const t = Math.max(0, Math.min(1, (now - t0) / 600)), e = 1 - Math.pow(1 - t, 3); shownBytes = Math.round(from + (target - from) * e); el.n.textContent = fmt(shownBytes); if (t < 1) bytesRaf = requestAnimationFrame(tick); }; bytesRaf = requestAnimationFrame(tick); }
  const activeRow = k === 4 ? 4 : s.row;
  rows.forEach((r, i) => { r.classList.toggle('on', i === activeRow); r.classList.toggle('done', i < activeRow); r.classList.toggle('off', i > activeRow); });
  stepBtns.forEach((b, i) => { b.classList.toggle('on', i === k); b.classList.toggle('done', i < k); });
  onStep && onStep(k);
}
let onStep = null;

/* state at progress p in [0,1]: the four transitions and their eased fractions */
const T0 = 0, SEG = 0.25, TR = 0.7;        /* four transitions fill the whole pinned run; the first one starts at the first pixel of scroll */
const RUN = 1.35;                           /* pinned run in viewport heights */
function phaseState(p) {
  const t = [0, 0, 0, 0];
  for (let k = 0; k < 4; k++) { const a = T0 + SEG * k; t[k] = Math.max(0, Math.min(1, (p - a) / (SEG * TR))); }
  const e = x => x * x * (3 - 2 * x);
  const eased = t.map(e);
  let step = 0; for (let k = 0; k < 4; k++) if (t[k] > 0.5) step = k + 1;
  return { t: eased, step };
}
const stepToP = k => k === 0 ? 0.0 : Math.min(0.99, T0 + SEG * (k - 1) + SEG * TR + 0.02);

/* ---------------------------------------------------------------- shared canvases */
function planeCanvases(R) {
  const { W, H, tree, loss, mask, klass, JW, JH } = R, mk = (w, h2) => { const c = document.createElement('canvas'); c.width = w; c.height = h2; return c; };
  const P = Brief.P, pack = Brief.pack;
  const draw = (fn, w = W, h2 = H) => { const c = mk(w, h2), ctx = c.getContext('2d'), img = ctx.createImageData(w, h2), out = new Uint32Array(img.data.buffer); fn(out); ctx.putImageData(img, 0, 0); return c; };
  const water = pack(P.water), nodata = pack(P.nodata), pale = pack([24, 31, 30]);
  const ramp = Uint32Array.from({ length: 101 }, (_, t) => pack(Brief.canopy(t, 0)));
  const cTree = draw(o => { for (let i = 0; i < o.length; i++) { const m = mask[i]; o[i] = m === 1 ? ramp[tree[i]] : m === 2 ? water : nodata; } });
  const lossC = pack(P.loss), past = pack(P.lossPast);
  const cLossAll = draw(o => { for (let i = 0; i < o.length; i++) { const m = mask[i], l = loss[i]; o[i] = m === 1 ? (l === 0 ? pale : l > 20 ? lossC : past) : m === 2 ? water : nodata; } });
  const cLossPost = draw(o => { for (let i = 0; i < o.length; i++) { const m = mask[i], l = loss[i]; o[i] = m === 1 ? (l > 20 ? lossC : pale) : m === 2 ? water : nodata; } });
  const landMask = pack([38, 49, 46]);
  const cMask = draw(o => { for (let i = 0; i < o.length; i++) { const m = mask[i]; o[i] = m === 1 ? landMask : m === 2 ? water : nodata; } });
  const cJrc = mk(JW, JH), jx = cJrc.getContext('2d'); jx.fillStyle = '#171E1D'; jx.fillRect(0, 0, JW, JH);
  const jf = document.createElement('canvas'); Brief.paintJrc(jf, R); jx.globalAlpha = 1; jx.drawImage(jf, 0, 0);
  /* decision plane: one colour per code class, loss on forest dilated so 341 cells stay visible */
  const dec = R.decision, forestC = pack([36, 178, 106]), nonf = pack([30, 38, 36]), funk = pack([150, 128, 66]);
  const base = draw(o => { for (let i = 0; i < o.length; i++) { const c = dec[i]; o[i] = c === 0 ? nodata : c === 1 ? water : c === 2 ? nonf : c < 14 ? forestC : funk; } });
  const S = 2, cDec = mk(W * S, H * S), dx = cDec.getContext('2d'); dx.imageSmoothingEnabled = false; dx.drawImage(base, 0, 0, W * S, H * S);
  dx.fillStyle = '#FF7A2E'; dx.strokeStyle = '#07090D'; dx.lineWidth = 1;
  for (let r = 0; r < H; r++) for (let c = 0; c < W; c++) { const code = dec[r * W + c]; if (code >= 9 && code <= 13) { dx.fillRect((c - 1.5) * S, (r - 1.5) * S, 4 * S, 4 * S); } }
  return { tree: cTree, lossAll: cLossAll, lossPost: cLossPost, mask: cMask, jrc: cJrc, dec: cDec, base };
}

/* ---------------------------------------------------------------- fallback (no WebGL) */
function buildFallback(R, host, cans) {
  host.hidden = false; $('#br-gl').hidden = true; $('#br-labels').hidden = true;
  host.innerHTML = '';
  const defs = [['treecover', 'Hansen treecover2000', cans.tree], ['loss', 'Hansen lossyear', cans.lossAll], ['mask', 'Hansen datamask', cans.mask], ['jrc', 'JRC 2020 forest', cans.jrc], ['dec', 'Decision plane · 20 codes', cans.dec]];
  const cards = {};
  defs.forEach(([id, name, cv]) => {
    const c = document.createElement('canvas'); c.width = 300; c.height = 147; c.getContext('2d').drawImage(cv, 0, 0, 300, 147);
    const card = h('figure', { class: 'br-fb ' + id }, c, h('figcaption', {}, name)); host.append(card); cards[id] = card;
  });
  return step => {
    cards.treecover.classList.toggle('gone', step >= 2);
    cards.loss.firstChild.getContext('2d').drawImage(step >= 3 ? cans.lossPost : cans.lossAll, 0, 0, 300, 147);
    ['mask', 'loss', 'jrc'].forEach(k => cards[k].classList.toggle('gone', step >= 4));
    cards.dec.classList.toggle('hid', step < 4);
  };
}

/* ---------------------------------------------------------------- main */
async function main() {
  const seq = $('#br-seq'), stage = $('#br-stage'), cv = $('#br-gl'), cvWrap = $('#br-cv'), labels = $('#br-labels'), fb = $('#br-fallback');
  setStep(0);
  let R;
  try { R = await Brief.ready; } catch (e) { cvWrap.innerHTML = '<p class="br-fb-msg">The region rasters could not be loaded.</p>'; seq.classList.add('static'); return; }
  const cans = planeCanvases(R);

  let THREE = null, renderer = null;
  try {
    const probe = document.createElement('canvas'); if (!(probe.getContext('webgl2') || probe.getContext('webgl'))) throw new Error('no WebGL');
    THREE = await import('three');
    renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true, alpha: true, powerPreference: 'low-power' });
  } catch (err) { console.warn('3D stack unavailable, using 2D fallback:', err.message || err); THREE = null; }

  const staticMode = REDUCE || !THREE;
  if (staticMode) seq.classList.add('static');

  /* step buttons: scroll to the plateau (animated mode) or jump (static mode) */
  let jump = null;
  stepBtns.forEach((b, k) => b.addEventListener('click', () => {
    if (staticMode) { jump(k); return; }
    const travel = seq.offsetHeight - stage.offsetHeight, top = seq.getBoundingClientRect().top + scrollY;
    scrollTo({ top: top + travel * stepToP(k), behavior: 'smooth' });
  }));

  if (!THREE) {
    const apply = buildFallback(R, fb, cans);
    onStep = apply; apply(shownStep);
    jump = k => { shownStep = -1; setStep(k); };
    return;
  }

  /* ---------- three.js scene ---------- */
  const Wd = 4.08, Dd = 2.0, C0 = 1.725, GAP = 1.15;
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-5, 5, 5, -5, -50, 50);
  
  const geo = new THREE.PlaneGeometry(Wd, Dd), edgeGeo = new THREE.EdgesGeometry(geo);
  const tex = c => { const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy()); t.minFilter = THREE.LinearMipmapLinearFilter; t.magFilter = THREE.LinearFilter; return t; };
  const planes = {};
  const make = (id, canvas, order, edge) => {
    const mat = new THREE.MeshBasicMaterial({ map: tex(canvas), transparent: true, opacity: 1, depthWrite: false, side: THREE.DoubleSide });
    const mesh = new THREE.Mesh(geo, mat); mesh.rotation.x = -Math.PI / 2; mesh.renderOrder = order;
    const line = new THREE.LineSegments(edgeGeo, new THREE.LineBasicMaterial({ color: edge, transparent: true, opacity: .8 })); line.rotation.x = -Math.PI / 2; line.renderOrder = order + 0.1;
    scene.add(mesh, line); planes[id] = { mesh, line, mat };
  };
  make('treecover', cans.tree, 0, 0x3C8A5E);
  make('mask', cans.mask, 1, 0x6B7387);
  make('lossPost', cans.lossPost, 2, 0xFF7A2E);
  make('loss', cans.lossAll, 3, 0x8A6452);
  make('jrc', cans.jrc, 4, 0x2BD47D);
  make('dec', cans.dec, 5, 0xE6E9EF);
  /* the visual order bottom to top: treecover, lossyear, datamask, JRC; masks sit under loss so loss shows on the plane */
  const slot = { treecover: 0, loss: 1, lossPost: 1, mask: 2, jrc: 3 };
  const LABELS = [
    { id: 'treecover', short: 'treecover2000', long: 'Hansen treecover2000', bytes: '414,142 B', corner: 'treecover' },
    { id: 'loss', short: 'lossyear', long: 'Hansen lossyear', bytes: '159,863 B', corner: 'loss' },
    { id: 'mask', short: 'datamask', long: 'Hansen datamask', bytes: '2,994 B', corner: 'mask' },
    { id: 'jrc', short: 'JRC 2020', long: 'JRC 2020 forest', bytes: '46,238 B', corner: 'jrc' },
    { id: 'dec', short: '20 codes', long: 'Decision plane · 20 codes', bytes: '9,874 B · 6,146 B store', corner: 'dec' },
  ];
  const labEls = {};
  LABELS.forEach(l => { const e = h('div', { class: 'br-l3', 'data-id': l.id }, h('span', { class: 'nm' }, h('span', { class: 'sw ' + l.id }), h('span', { class: 't' })), h('span', { class: 'by' }, l.bytes)); labels.append(e); labEls[l.id] = e; });
  const legend = h('div', { class: 'br-legend3d' }, h('span', {}, h('i', { style: 'background:#24B26A' }), 'forest 2020'), h('span', {}, h('i', { style: 'background:#1E2624;border:1px solid #2A3347' }), 'non-forest'), h('span', {}, h('i', { style: 'background:#4C9BE8' }), 'water'), h('span', {}, h('i', { style: 'background:#968042' }), 'forest state unknown'), h('span', {}, h('i', { style: 'background:#FF7A2E' }), 'loss on forest (drawn 4× wide)'));
  labels.append(legend);

  const motion = { az: 0, phase: 0 };   /* idle drift and the turn-in on enter */
  let size = { w: 0, h: 0, ppu: 1 }, dirty = true, p = 0, cur = { t: [0, 0, 0, 0] };
  const lerp = (a, b, t) => a + (b - a) * t;
  const EL0 = Math.asin(1 / Math.sqrt(3)), AZ0 = Math.PI / 4, EL1 = 86 * Math.PI / 180;
  function sizeRenderer() {
    const w = cvWrap.clientWidth, h2 = cvWrap.clientHeight; if (!w || !h2) return false;
    renderer.setPixelRatio(Math.min(2, devicePixelRatio || 1)); renderer.setSize(w, h2, false);
    size = { w, h2, ppu: 1 };
    const wide = w >= 560; LABELS.forEach(l => { labEls[l.id].querySelector('.t').textContent = wide ? l.long : l.short; labEls[l.id].classList.toggle('compact', !wide); });
    return true;
  }
  /* isometric view that turns top-down as the planes collapse; the frustum is refitted to the visible envelope each frame */
  function updateCamera(e3) {
    const { w, h2 } = size; if (!w) return;
    const el = lerp(EL0, EL1, e3) + (1 - e3) * 0.02 * Math.sin(motion.phase * 0.7), az = lerp(AZ0, 0, e3) + (1 - e3) * motion.az, R = 20;
    camera.position.set(Math.sin(az) * Math.cos(el) * R, C0 + Math.sin(el) * R, Math.cos(az) * Math.cos(el) * R);
    camera.lookAt(0, C0, 0); camera.updateMatrixWorld();
    const labelRoom = lerp(w < 560 ? 84 : 196, w < 560 ? 12 : 16, e3);
    const inv = camera.matrixWorldInverse; let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    const lo = lerp(-0.9, C0, e3), hi = lerp(3.5, C0, e3);
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) for (const y of [lo, hi]) { const q = new THREE.Vector3(sx * Wd / 2, y, sz * Dd / 2).applyMatrix4(inv); x0 = Math.min(x0, q.x); x1 = Math.max(x1, q.x); y0 = Math.min(y0, q.y); y1 = Math.max(y1, q.y); }
    const top = lerp(44, 64, e3);
    const ppu = Math.min((w - labelRoom - 16) / (x1 - x0), (h2 - top) / (y1 - y0));
    const cx = (x0 + x1) / 2 - (labelRoom / 2) / ppu, cy = (y0 + y1) / 2 + (top / 2 - 22) / ppu;
    camera.left = cx - w / (2 * ppu); camera.right = cx + w / (2 * ppu); camera.top = cy + h2 / (2 * ppu); camera.bottom = cy - h2 / (2 * ppu);
    camera.updateProjectionMatrix(); size.ppu = ppu;
  }

  function layout() {
    const t = cur.t, [e0, e1, e2, e3] = t;
    /* y: tight stack (e0 = 0) to exploded (1); then collapse to the centre (e3) */
    const tight = k => C0 + (k - 1.5) * 0.16, spread = k => C0 + (k - 1.5) * GAP;
    const yOf = id => { const k = slot[id]; return lerp(lerp(tight(k), spread(k), e0), C0, e3 * (id === 'treecover' ? 0 : 1)); };
    const set = (id, y, op, dx = 0) => { const pl = planes[id]; pl.mesh.position.set(dx, y, 0); pl.line.position.set(dx, y, 0); pl.mat.opacity = op; pl.mesh.visible = pl.line.visible = op > 0.004; pl.line.material.opacity = Math.min(.85, op); };
    set('treecover', yOf('treecover') - 0.5 * e1, Math.max(0, lerp(0.97, 0.06, e1)) * (1 - e3));
    set('mask', yOf('mask'), 0.96 * (1 - e3));
    set('lossPost', yOf('lossPost'), 0.96 * (1 - e3));
    set('loss', yOf('loss'), 0.96 * (1 - e2) * (1 - e3));
    set('jrc', yOf('jrc'), 0.9 * (1 - e3));
    set('dec', C0, e3 * 0.98);
    planes.dec.mesh.position.y = C0 + 0.001;
  }
  function placeLabels() {
    const v = new THREE.Vector3(), [e0, e1, e2, e3] = cur.t;
    LABELS.forEach(l => {
      const pl = planes[l.corner === 'dec' ? 'dec' : l.corner === 'loss' ? 'loss' : l.corner];
      const y = l.id === 'dec' ? C0 : l.id === 'loss' ? planes.lossPost.mesh.position.y : pl.mesh.position.y;
      v.set(-Wd / 2, y, Dd / 2).project(camera);
      const x = (v.x * .5 + .5) * size.w, yy = (-v.y * .5 + .5) * size.h2;
      let op = l.id === 'dec' ? e3 : l.id === 'treecover' ? lerp(1, 0.3, e1) * (1 - e3) : (1 - e3);
      if (l.id !== 'dec') op *= Math.max(0, Math.min(1, (e0 - 0.3) / 0.35));   /* labels wait until the planes have separated */
      const e = labEls[l.id], above = l.id === 'dec' && e3 > .35;
      if (above) v.set(-Wd / 2, C0, -Dd / 2).project(camera);
      const lx = above ? (v.x * .5 + .5) * size.w : x, ly = above ? (-v.y * .5 + .5) * size.h2 : yy;
      e.classList.toggle('above', above);
      e.style.transform = above ? `translate(${Math.round(lx)}px, ${Math.round(ly - 8)}px) translate(0, -100%)` : `translate(${Math.round(lx - 10)}px, ${Math.round(ly)}px) translate(-100%, -50%)`;
      e.style.opacity = op.toFixed(3);
      e.classList.toggle('strike', l.id === 'treecover' && e1 > .5);
    });
    legend.style.opacity = cur.t[3].toFixed(2); legend.hidden = cur.t[3] < .02;
  }
  function frame() {
    const st = phaseState(p); cur = st; setStep(st.step);
    updateCamera(st.t[3]);
    layout(); placeLabels(); renderer.render(scene, camera); dirty = false;
  }
  function progress() {
    const r = seq.getBoundingClientRect(), travel = seq.offsetHeight - stage.offsetHeight;
    return travel > 0 ? Math.max(0, Math.min(1, -r.top / travel)) : 0;
  }
  onStep = null;
  if (staticMode) {
    const request = () => requestAnimationFrame(frame);
    jump = k => { p = stepToP(k); if (k === 4) p = 1; request(); };
    jump(REDUCE ? 4 : 0);
    new ResizeObserver(() => { if (sizeRenderer()) request(); }).observe(cvWrap);
    sizeRenderer(); frame();
    return;
  }
  /* animated mode: the pinned run is about 1.35 viewport heights; displayed progress eases toward the scroll target */
  const sizeSeq = () => { seq.style.height = Math.round(stage.offsetHeight + RUN * innerHeight) + 'px'; };
  sizeSeq(); addEventListener('resize', sizeSeq);
  let target = progress(), shown = target, last = performance.now(), visible = false, running = false, enterAt = 0;
  p = shown;
  const loop = now => {
    const dt = Math.min(64, now - last); last = now;
    target = progress();
    shown += (target - shown) * (1 - Math.pow(1 - 0.18, dt / 16.7));
    if (Math.abs(target - shown) < 0.0004) shown = target;
    p = shown;
    motion.phase = now / 1000;
    const k = enterAt ? Math.min(1, (now - enterAt) / 1400) : 1, e = 1 - Math.pow(1 - k, 3);
    motion.az = -0.34 * (1 - e) + 0.05 * Math.sin(now / 1700);
    frame();
    running = visible || shown !== target || k < 1;
    if (running) requestAnimationFrame(loop);
  };
  const kick = () => { if (!running) { running = true; last = performance.now(); requestAnimationFrame(loop); } };
  new IntersectionObserver(es => es.forEach(en => { visible = en.isIntersecting; if (visible && !enterAt) enterAt = performance.now(); if (visible) kick(); }), { threshold: 0.15 }).observe(stage);
  addEventListener('scroll', kick, { passive: true });
  new ResizeObserver(() => { if (sizeRenderer()) kick(); }).observe(cvWrap);
  sizeRenderer(); frame(); kick();
}
main();

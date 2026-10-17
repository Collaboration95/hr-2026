/* #store: the .plds byte layout, parsed in the browser from a copy of artifacts/decision/decision.plds, plus the registry/table binding. */
(() => {
  const { $, $$, h, fmt, esc } = UI;
  const root = $('#br-store'); if (!root) return;
  const B = BR.bytes, S = B.sections;
  const FILE_SHA = B.decisionFileSha256;   /* artifacts/decision/stores.json levels.eudr-decision.v1.store.file_sha256 */

  /* CRC-32 (zlib polynomial), as zlib.crc32 in decision_store.py */
  const T = new Uint32Array(256).map((_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  const crc32 = u8 => { let c = 0xFFFFFFFF; for (let i = 0; i < u8.length; i++) c = T[(c ^ u8[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
  const hex = (n, w = 8) => n.toString(16).padStart(w, '0');

  const segs = [
    { id: 'prefix', name: 'Prefix', bytes: B.prefix, cls: 'prefix' },
    { id: 'header', name: 'Header', bytes: B.decisionHeader, cls: 'header' },
    { id: 'flags', name: 'Flags', bytes: S.flags, cls: 'flags' },
    { id: 'unknown', name: 'Unknown plane', bytes: S.unknown, cls: 'plane' },
    { id: 'water', name: 'Water plane', bytes: S.water, cls: 'plane w' },
    { id: 'forest', name: 'Forest plane', bytes: S.forest, cls: 'plane f' },
    { id: 'unknown_forest', name: 'Forest-unknown plane', bytes: S.unknown_forest, cls: 'plane u' },
    { id: 'events', name: 'Loss events', bytes: S.events, cls: 'events' },
    { id: 'years', name: 'Loss years', bytes: S.years, cls: 'years' },
  ];
  const total = B.decisionStore;
  const live = { prefix: null, header: null, flag: null, events: null };

  const info = {
    prefix: () => ({
      holds: `<code>PLDECID1</code> magic (8 B), u32 version <b>${live.prefix ? live.prefix.version : 2}</b>, u32 header length <b>${live.prefix ? live.prefix.hlen : B.decisionHeader}</b>, u32 CRC32 of the header bytes <b>0x${live.prefix ? hex(live.prefix.crc) : '…'}</b>. Little endian.`,
      check: 'Magic and version compared. Header length bounded to 2 B – 64 KiB. The header CRC32 is checked before the header is parsed.' }),
    header: () => ({
      holds: 'Canonical JSON with exactly nine fields: <code>shape</code>, <code>transform</code>, <code>crs</code>, <code>level</code>, <code>encoding</code>, <code>sources</code> (SHA-256 of the three Hansen chips and the JRC chip), <code>payload_bytes</code>, <code>payload_sha256</code>, <code>codes_sha256</code>.' + (live.header ? `<pre class="code br-json">${esc(JSON.stringify(live.header, (k, v) => typeof v === 'string' && v.length === 64 ? v.slice(0, 12) + '…' : v).replace(/,"/g, ',\n"').replace(/^\{/, '{\n'))}</pre>` : ''),
      check: 'CRC32 in the prefix. Re-serialising the parsed header must reproduce its bytes (canonical form). Unknown fields, duplicate keys, non-finite numbers and wrong digest lengths are rejected.' }),
    flags: () => ({
      holds: `One byte choosing how loss events are coded: 0 = a bit-plane, 1 = gaps between event positions, 3 = gaps ranked among forest and forest-unknown cells only. This file holds <b>${live.flag == null ? '…' : live.flag}</b>.`,
      check: 'Values other than 0, 1 and 3 are rejected.' }),
    unknown: () => ({
      holds: 'A single <code>0x00</code> byte: the all-zero marker. No cell of the region is code 0. The 2,439 land cells with no JRC value are forest-state unknown (codes 14–19), not unknown.',
      check: 'A plane may only be empty through this marker; any other stream must carry a declared size.' }),
    water: () => ({
      holds: `Bit-plane of the <b>${fmt(BR.hist.decision[1])}</b> water cells (code 1). Cells are packed in bands of 8 columns, rows top to bottom, then compressed with the smallest of stored, zstd-22 and tuned LZMA2.`,
      check: 'Stream size must equal the declared size; the zstd frame size must match; unused padding bits must be zero; planes may not overlap (a cell cannot be water and forest).' }),
    forest: () => ({
      holds: `Bit-plane of the <b>${fmt(BR.hist.decision.slice(8, 14).reduce((a, b) => a + b, 0))}</b> land cells whose JRC 2020 class at the cell centre is forest (codes 8–13). Same band layout and compression as the water plane.`,
      check: 'Same stream checks as the water plane, plus the overlap rule with the unknown, water and forest-unknown planes. It is 72% of the file: the forest map itself is the information.' }),
    unknown_forest: () => ({
      holds: `Bit-plane of the <b>${fmt(BR.hist.decision.slice(14).reduce((a, b) => a + b, 0))}</b> land cells with no JRC value, along the edge of the JRC chip (codes 14–19).`,
      check: 'Same stream and overlap checks.' }),
    events: () => ({
      holds: `Sparse post-2020 loss events: a count${live.events != null ? ` (<b>${fmt(live.events)}</b>)` : ''} followed by the gaps between event cells, ranked among forest and forest-unknown cells only, as varints. At the decision level loss survives only there: 341 cells on 2020 forest and 217 with unknown forest state.`,
      check: 'Event count may not exceed the grid; every rank must fall inside the eligible cells; an event on a non-land cell is rejected; at the decision level nonforest land with loss (codes 3–7) is refused.' }),
    years: () => ({
      holds: 'One symbol per event, 0–4 for 2021–2025, stored as the smaller of plain symbols and deltas modulo 5.',
      check: 'A symbol above 4 is rejected; the stream must end exactly at its declared size.' }),
  };

  /* bar */
  const bar = $('#br-bar'), det = $('#br-store-detail');
  let sel = 'forest';
  const els = {};
  segs.forEach(s => {
    const pct = 100 * s.bytes / total;
    const el = h('button', { type: 'button', role: 'listitem', class: `br-seg-bar ${s.cls}`, style: `flex: ${s.bytes} 1 0; min-width: ${s.bytes < 40 ? 4 : 10}px`, 'aria-label': `${s.name}, ${fmt(s.bytes)} bytes, ${pct.toFixed(1)}% of the file` });
    el.addEventListener('pointerenter', () => pickSeg(s.id)); el.addEventListener('focus', () => pickSeg(s.id)); el.addEventListener('click', () => pickSeg(s.id));
    bar.append(el); els[s.id] = el;
  });
  const list = h('div', { class: 'br-seglist' });
  segs.forEach(s => {
    const c = h('button', { type: 'button', class: 'br-segchip' }, h('i', { class: `sw ${s.cls}` }), h('span', { class: 'nm' }, s.name), h('span', { class: 'by' }, fmt(s.bytes) + ' B'), h('span', { class: 'pc' }, (100 * s.bytes / total).toFixed(s.bytes / total < 0.01 ? 2 : 1) + '%'));
    c.addEventListener('pointerenter', () => pickSeg(s.id)); c.addEventListener('focus', () => pickSeg(s.id)); c.addEventListener('click', () => pickSeg(s.id));
    c.dataset.id = s.id; list.append(c);
  });
  bar.after(list);
  const axis = h('div', { class: 'br-axis' }, h('span', {}, '0'), h('span', {}, `20 B prefix · ${B.decisionHeader} B header · ${fmt(B.decisionPayload)} B payload`), h('span', {}, '6,146 B'));
  bar.before(axis);
  function pickSeg(id) {
    sel = id;
    Object.entries(els).forEach(([k, e]) => e.classList.toggle('on', k === id));
    $$('.br-segchip', list).forEach(c => c.classList.toggle('on', c.dataset.id === id));
    const s = segs.find(x => x.id === id), d = info[id]();
    det.innerHTML = `<div class="head"><b>${esc(s.name)}</b> <span class="mono">${fmt(s.bytes)} B · ${(100 * s.bytes / total).toFixed(s.bytes / total < 0.01 ? 2 : 1)}% of the file</span></div>
      <div class="row"><span class="lab">Holds</span><div>${d.holds}</div></div>
      <div class="row"><span class="lab">Integrity</span><div>${d.check}</div></div>`;
  }
  pickSeg(sel);

  /* parse the real file */
  const varint = (u8, p) => { let v = 0, s = 0, n = 0; for (;;) { const b = u8[p + n++]; v |= (b & 127) << s; if (b < 128) return [v, n]; s += 7; } };
  const walk = (u8, base) => {
    let p = base; const out = {};
    out.flags = [1]; const flag = u8[p++]; out.flagValue = flag;
    const stream = (explicit, impl) => { const start = p; const m = u8[p++]; let size = impl; if (explicit) { const [v, n] = varint(u8, p); size = v; p += n; } const [len, n2] = varint(u8, p); p += n2 + len; return { start, len: p - start, size }; };
    const plane = () => { if (u8[p] === 0) { p += 1; return 1; } return stream(false).len; };
    out.unknown = plane(); out.water = plane(); out.forest = plane(); out.unknown_forest = plane();
    let ev = 0, n = 0;
    if (flag) { const [v, k] = varint(u8, p); n = v; ev = k; p += k; if (n) ev += stream(true).len; } else ev = plane();
    out.events = ev; out.eventCount = n;
    out.years = n ? stream(false, n).len : 0;
    out.end = p; return out;
  };
  const filePromise = fetch(Brief.BASE + 'decision.plds').then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.arrayBuffer(); }).then(buf => {
    const u8 = new Uint8Array(buf), dv = new DataView(buf);
    const magic = new TextDecoder().decode(u8.slice(0, 8)), version = dv.getUint32(8, true), hlen = dv.getUint32(12, true), crc = dv.getUint32(16, true);
    const hb = u8.slice(20, 20 + hlen);
    live.prefix = { magic, version, hlen, crc };
    live.header = JSON.parse(new TextDecoder().decode(hb));
    const w = walk(u8, 20 + hlen);
    live.flag = w.flagValue; live.events = w.eventCount;
    live.file = { u8, hb, magic, version, hlen, crc, walked: w, payload: u8.slice(20 + hlen) };
    pickSeg(sel);
    return live.file;
  }).catch(err => { console.warn('decision.plds unavailable', err); det.insertAdjacentHTML('beforeend', '<div class="row"><span class="lab">Note</span><div>The sample file could not be loaded; sizes come from stores.json.</div></div>'); });

  /* verification */
  const out = $('#br-verify-out'), btn = $('#br-verify');
  btn.addEventListener('click', async () => {
    out.hidden = false; out.innerHTML = '<div class="muted">Checking…</div>';
    const f = await filePromise;
    if (!f) { out.innerHTML = '<div class="muted">File unavailable.</div>'; return; }
    const rows = [];
    const ok = (good, text) => rows.push(`<li class="${good ? 'ok' : 'bad'}"><span class="st ${good ? 'ok' : 'bad'}">${good ? 'pass' : 'fail'}</span> ${text}</li>`);
    ok(f.magic === 'PLDECID1' && f.version === 2, `Magic <code>${esc(f.magic)}</code>, version ${f.version}`);
    const c = crc32(f.hb);
    ok(c === f.crc, `Header CRC32 computed 0x${hex(c)}, prefix says 0x${hex(f.crc)}`);
    ok(f.hlen === B.decisionHeader && f.u8.length === B.decisionStore, `Lengths: header ${f.hlen} B, payload ${f.payload.length} B, file ${f.u8.length} B`);
    ok(f.payload.length === live.header.payload_bytes, `Header <code>payload_bytes</code> = ${fmt(live.header.payload_bytes)}`);
    const w = f.walked;
    const same = ['flags', 'unknown', 'water', 'forest', 'unknown_forest', 'events', 'years'].every(k => (Array.isArray(w[k]) ? w[k][0] : w[k]) === S[k]);
    ok(same && w.end - (20 + f.hlen) === f.payload.length, 'Streams walked from the file bytes end exactly at the payload end and equal the section sizes in <code>stores.json</code>');
    if (crypto.subtle) {
      const ps = await Brief.sha256Hex(f.payload), fs = await Brief.sha256Hex(f.u8);
      ok(ps === live.header.payload_sha256, `Payload SHA-256 <code>${ps.slice(0, 12)}…</code> equals header <code>payload_sha256</code>`);
      ok(fs === FILE_SHA, `File SHA-256 <code>${fs.slice(0, 16)}…</code> equals <code>file_sha256</code> in <code>stores.json</code>`);
    } else rows.push('<li class="info"><span class="st">skip</span> SHA-256 needs a secure context.</li>');
    rows.push('<li class="info"><span class="st">not here</span> <code>codes_sha256</code> needs the full decode. The Python <code>read_store</code> checks it; this page does not decode the planes.</li>');
    out.innerHTML = `<ul>${rows.join('')}</ul>`;
  });

  /* ---- registry and table binding ---- */
  const chain = $('#br-bind-chain'), outBox = $('#br-bind-out'), ctl = $('#br-bind .br-seg');
  const modes = [
    ['none', 'No change', 'hit', 'Table hit. Keys match, so the stored outputs for the plot are returned: about 0.2 µs per plot hot. The same outputs come from the registry index (1.9 µs) or a fresh selection (16 µs).'],
    ['geom', 'Plot geometry edited', 'miss', '<code>geometry_sha256</code> differs from the registered one, so <code>registry_lookup</code> and <code>table_lookup</code> return nothing. The caller selects cells afresh from the store (the new-boundary path).'],
    ['store', 'Store replaced by another release', 'miss', 'The table is keyed by the store file SHA-256 per level. A different store file misses; the answer is recomputed from the new store instead of served stale.'],
    ['grid', 'Registry on a shifted grid', 'miss', 'The registry carries the grid identity (shape, transform, CRS). A different grid never matches, and metadata is required on every lookup.'],
    ['table', 'Table file edited', 'refuse', '<code>content_sha256</code> is recomputed from the canonical JSON on load. An edited, truncated or old-schema table is refused with a ValueError.'],
  ];
  let mode = 'none';
  function drawChain() {
    const bad = k => mode === k;
    const chip = (label, val, red) => h('div', { class: 'br-key' + (red ? ' bad' : '') }, h('span', { class: 'k' }, label), h('span', { class: 'v' }, val));
    const box = (title, sub, ...kids) => h('div', { class: 'br-bbox' }, h('b', {}, title), h('small', {}, sub), ...kids);
    chain.replaceChildren(
      box('Plot', 'ID + geometry (private, not shown)', chip('geometry_sha256', mode === 'geom' ? 'changed' : 'sha256 of canonical JSON', bad('geom'))),
      h('div', { class: 'br-barrow' }, '→'),
      box('Registry', `PLDREG2 · ${fmt(B.registry)} B · private`, chip('plot ID', 'P-0001 …'), chip('geometry_sha256', 'as registered'), chip('grid identity', mode === 'grid' ? 'shifted' : '1233 × 604, EPSG:4326', bad('grid')), chip('cell indices', 'run-length int32')),
      h('div', { class: 'br-barrow' }, '→'),
      box('Answer table', `decision-table.v2 · ${fmt(B.table)} B`, chip('stores[level]', mode === 'store' ? 'another file sha256' : 'file sha256 ' + FILE_SHA.slice(0, 8) + '…', bad('store')), chip('outputs', 'per plot, per level'), chip('content_sha256', mode === 'table' ? 'mismatch' : B.tableContentSha256.slice(0, 8) + '…', bad('table'))),
      h('div', { class: 'br-barrow' }, '←'),
      box('Store', 'decision.plds · 6,146 B', chip('file sha256', mode === 'store' ? 'replaced' : FILE_SHA.slice(0, 8) + '…', bad('store'))));
    const m = modes.find(x => x[0] === mode);
    outBox.className = 'br-bind-out ' + m[2];
    outBox.innerHTML = `<span class="st ${m[2] === 'hit' ? 'ok' : m[2] === 'miss' ? 'review' : 'bad'}">${m[2] === 'hit' ? 'Hit' : m[2] === 'miss' ? 'Miss, recompute' : 'Refused'}</span> ${m[3]}`;
    $$('button', ctl).forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === mode)));
  }
  modes.forEach(m => { const b = h('button', { type: 'button', 'data-mode': m[0], 'aria-pressed': 'false' }, m[1]); b.addEventListener('click', () => { mode = m[0]; drawChain(); }); ctl.append(b); });
  drawChain();
})();

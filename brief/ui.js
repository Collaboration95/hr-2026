/* Small shared helpers for the technical brief: DOM/SVG builders, segmented toggles, tooltip, nav, pipeline stepper. */
window.UI = (() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const NS = { svg: 'http://www.w3.org/2000/svg' };
  const SVG_TAGS = new Set(['svg', 'g', 'path', 'rect', 'circle', 'line', 'text', 'polyline', 'polygon', 'defs', 'pattern', 'title', 'tspan', 'clipPath']);
  function h(tag, attrs, ...kids) {
    const el = SVG_TAGS.has(tag) ? document.createElementNS(NS.svg, tag) : document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === 'class') el.setAttribute('class', v);
      else if (k === 'html') el.innerHTML = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(kid));
    return el;
  }
  const fmt = n => n.toLocaleString('en-GB');
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  /* segmented toggle: buttons carry data-<key>; exactly one is pressed */
  function seg(root, key, cb) {
    const btns = $$(`button[data-${key}]`, root);
    const set = (val, silent) => {
      btns.forEach(b => b.setAttribute('aria-pressed', String(b.dataset[key] === String(val))));
      if (!silent) cb(String(val));
    };
    btns.forEach(b => b.addEventListener('click', () => set(b.dataset[key])));
    return { set, get: () => (btns.find(b => b.getAttribute('aria-pressed') === 'true') || {}).dataset?.[key] };
  }

  /* tooltip */
  const tipEl = $('#br-tip');
  const tip = {
    show(html, x, y) {
      tipEl.innerHTML = html; tipEl.hidden = false;
      const r = tipEl.getBoundingClientRect();
      let left = x + 14, top = y + 14;
      if (left + r.width > innerWidth - 8) left = x - r.width - 14;
      if (top + r.height > innerHeight - 8) top = y - r.height - 14;
      tipEl.style.left = Math.max(8, left) + 'px'; tipEl.style.top = Math.max(8, top) + 'px';
    },
    hide() { tipEl.hidden = true; },
  };
  function bindTip(el, htmlFn) {
    const move = e => tip.show(htmlFn(), e.clientX, e.clientY);
    el.addEventListener('pointerenter', move); el.addEventListener('pointermove', move);
    el.addEventListener('pointerleave', tip.hide); el.addEventListener('blur', tip.hide);
    el.addEventListener('focus', () => { const r = el.getBoundingClientRect(); tip.show(htmlFn(), r.left + r.width / 2, r.top); });
  }

  /* sticky offsets and active nav link */
  const mast = $('.mast'), nav = $('#br-nav');
  const setOffsets = () => {
    document.documentElement.style.setProperty('--mast', (mast ? mast.offsetHeight : 0) + 'px');
    document.documentElement.style.setProperty('--nav', (nav ? nav.offsetHeight : 0) + 'px');
  };
  setOffsets(); addEventListener('resize', setOffsets); addEventListener('load', setOffsets);
  const secs = $$('main section[id]');
  const links = $$('a', nav);
  const sync = () => {
    const line = (mast ? mast.offsetHeight : 0) + (nav ? nav.offsetHeight : 0) + 40;
    let k = -1; secs.forEach((s, j) => { if (s.getBoundingClientRect().top < line) k = j; });
    links.forEach(a => { const on = k >= 0 && a.getAttribute('href') === '#' + secs[k].id; a.classList.toggle('on', on); if (on) a.setAttribute('aria-current', 'location'); else a.removeAttribute('aria-current'); });
    const on = $('a.on', nav);
    if (on && nav.scrollWidth > nav.clientWidth) nav.scrollTo({ left: on.offsetLeft - nav.clientWidth / 2 + on.offsetWidth / 2, behavior: 'auto' });
  };
  addEventListener('scroll', sync, { passive: true }); sync();
  /* anchors land below the sticky bars */
  document.documentElement.style.scrollPaddingTop = '0px';
  $$('section[id]').forEach(s => { s.style.scrollMarginTop = 'calc(var(--mast) + var(--nav) + 8px)'; });

  /* pipeline stepper in #framing */
  (() => {
    const row = $('#br-flow .br-flow-row'), note = $('#br-flow-note');
    if (!row) return;
    const nodes = [
      ['Inputs', 'Hansen 3 bands + JRC 2020', 'Three Hansen rasters on a 1,233 × 604 grid and one JRC raster on a 3,695 × 1,809 grid. The JRC lattice nests the Hansen lattice 3 × 3 with no resampling.', 'engine/source.py · engine/jrc.py'],
      ['Derive', 'one code per cell', 'JRC 2020 class is read at each Hansen cell centre (the middle of its 3 × 3 block); Hansen loss year becomes none or 2021–2025. Treecover and pre-2021 loss are dropped.', 'engine/decision.py'],
      ['Encode', '.plds store', 'Four bit-planes (unknown, water, forest, forest-unknown) plus sparse post-2020 loss events with one year symbol each. Lossless: it decodes to the identical raster.', 'engine/decision_store.py'],
      ['Query', 'polygon to histogram', 'A polygon selects cells whose centres it covers (exact GEOS covers). The selected codes become a 20-bin histogram. Registered plots skip selection through a cell index.', 'engine/query.py · engine/decision_index.py'],
      ['Answer', 'contract outputs', 'The histogram reduces to forest-2020 cell counts, mapped loss on mapped 2020 forest by year, unknown cells and a support flag. Unknown stays unknown.', 'engine/decision_summary.py'],
    ];
    const btns = nodes.map((n, i) => {
      const b = h('button', { type: 'button', role: 'tab', 'aria-pressed': 'false', class: 'br-flow-node' }, h('span', { class: 'n' }, String(i + 1)), h('b', {}, n[0]), h('small', {}, n[1]));
      b.addEventListener('click', () => show(i)); row.append(b); return b;
    });
    function show(i) { btns.forEach((b, k) => { b.setAttribute('aria-pressed', String(k === i)); b.classList.toggle('done', k < i); }); note.innerHTML = `${esc(nodes[i][2])} <code>${esc(nodes[i][3])}</code>`; }
    show(0);
  })();

  return { $, $$, h, fmt, esc, seg, tip, bindTip };
})();

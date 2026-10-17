/* #schema: the 20-code grid with a screening / decision toggle. Counts come from artifacts/decision/stores.json. */
(() => {
  const { $, h, fmt, esc, seg } = UI;
  const root = $('#br-schema'); if (!root) return;
  const grid = $('#br-codes'), detail = $('#br-code-detail');
  const cols = ['No loss after 2020', '2021', '2022', '2023', '2024', '2025'];
  const rows = [['Land · 2020 non-forest', 0, 'nf'], ['Land · 2020 forest (JRC)', 1, 'fo'], ['Land · forest state unknown', 2, 'un']];
  let level = 'decision', pick = 9;
  const hist = l => BR.hist[l];

  const feeds = (code, lv) => {
    if (code === 0) return ['unknown_cell_count'];
    if (code === 1) return ['water_cell_count'];
    const st = Math.floor((code - 2) / 6), post = (code - 2) % 6, out = [];
    out.push(['forest_2020.cell_counts.nonforest', 'forest_2020.cell_counts.forest', 'forest_2020.cell_counts.unknown'][st]);
    if (post && st === 1) out.push(`deforestation_after_2020.yearly_cell_counts.${2020 + post}`);
    if (post && st === 2) out.push('makes deforestation_after_2020.present unknown when no known loss exists');
    if (post && lv === 'screen') out.push(`hansen_loss_after_2020.yearly_cell_counts.${2020 + post}`);
    return out;
  };

  function render() {
    const H = hist(level), merged = level === 'decision';
    grid.replaceChildren();
    const cell = (code, cls, extra) => {
      const gone = merged && code >= 3 && code <= 7;
      const n = H[code];
      const b = h('button', { type: 'button', class: `br-code ${cls} ${gone ? 'gone' : ''} ${code === 2 && merged ? 'merge' : ''} ${pick === code ? 'sel' : ''}`, 'data-code': code, 'aria-label': `Code ${code}: ${Brief.codeInfo(code).label}, ${fmt(n)} cells${gone ? ', merged into code 2' : ''}` },
        h('span', { class: 'c' }, String(code)),
        h('span', { class: 'n' }, gone ? '→ 2' : fmt(n)),
        extra || null);
      b.addEventListener('click', () => { pick = code; render(); });
      b.addEventListener('pointerenter', () => preview(code));
      b.addEventListener('focus', () => preview(code));
      return b;
    };
    /* special row */
    grid.append(h('div', { class: 'br-rowlab' }, 'Not land'));
    grid.append(cell(0, 'unk span3'), cell(1, 'wat span3'));
    grid.append(h('div', { class: 'br-rowlab head' }, ''), ...cols.map((c, i) => h('div', { class: 'br-colhead' + (i ? ' loss' : '') }, c)));
    rows.forEach(([lab, st, cls]) => {
      grid.append(h('div', { class: 'br-rowlab' }, lab));
      for (let k = 0; k < 6; k++) grid.append(cell(2 + 6 * st + k, `${cls} ${k ? 'lossc' : ''}`));
    });
    show(pick);
    const total = H.reduce((a, b) => a + b, 0);
    $('#br-schema .br-total')?.remove();
    grid.after(h('div', { class: 'br-total' }, `${fmt(total)} cells · ${merged ? 'codes 3–7 hold 0 cells; their 79,871 cells moved into code 2' : 'every post-2020 loss year kept on all land'}`));
  }
  function preview(code) { show(code); }
  function show(code) {
    const info = Brief.codeInfo(code), H = hist(level);
    const gone = level === 'decision' && code >= 3 && code <= 7;
    const formula = code < 2 ? `code ${code}` : `2 + 6 × ${Math.floor((code - 2) / 6)} + ${(code - 2) % 6}`;
    detail.innerHTML = `<div class="head"><b>Code ${code}</b> <span class="mono muted">${formula}</span></div>
      <div>${esc(info.label)} · <b>${fmt(H[code])}</b> cells${gone ? ' · merged into code 2 at the decision level (loss year forgotten on 2020 non-forest land)' : ''}${level === 'decision' && code === 2 ? ' · screening codes 2–7 combined' : ''}</div>
      <div class="feeds"><span class="muted">Feeds</span> ${feeds(code, level).map(f => `<code>${esc(f)}</code>`).join(' ')}</div>`;
  }
  seg($('.br-seg', root), 'level', v => { level = v; render(); });
  render();

  Brief.ready.then(R => {
    const el = $('#br-selfcheck');
    el.innerHTML = R.histMatches
      ? `<span class="st ok">Re-derived</span> The browser rebuilt both code rasters from the display PNGs${R.verified ? ' (SHA-256 matches the manifest)' : ''}; all 40 histogram counts equal <code>stores.json</code>.`
      : `<span class="st bad">Mismatch</span> The browser-derived histogram differs from <code>stores.json</code>.`;
  }).catch(() => { $('#br-selfcheck').textContent = 'Display rasters unavailable; counts above are from stores.json.'; });
})();

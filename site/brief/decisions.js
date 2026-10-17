/* #decisions: filterable record of key decisions, rejected approaches and negative results. Each row names its repository file. */
(() => {
  const { $, $$, h, seg } = UI;
  const host = $('#br-dec-list'); if (!host) return;
  const L = { report: 'docs/lab/decision-layer-report.md', scale: 'docs/lab/decision-scale-notes.md', val: 'validation/decision/report.md', memo: 'docs/SUBMISSION_MEMO.md', summ: 'engine/decision_summary.py', idx: 'engine/decision_index.py', store: 'engine/decision_store.py' };
  const items = [
    ['decision', 'Drop <code>treecover2000</code>. It is 72% of the Hansen bytes and no EUDR question reads it.', 'report', '#the-questions-and-what-each-needs'],
    ['decision', 'Read the JRC 2020 class at the Hansen cell centre, 1 of 9 nested JRC cells. Majority and any-forest rules leave every plot decision unchanged.', 'scale', '#jrc-aggregation-sensitivity'],
    ['decision', 'Two levels share one code space. Screening keeps post-2020 loss on all land; the decision level forgets it on 2020 non-forest land. The lossless v1 store stays as the audit tier.', 'report', '#two-derived-layers-one-code-per-cell'],
    ['decision', 'Unknown stays unknown. Flags are tri-state, and a store records its level so a decision raster cannot be read as screening.', 'summ', ''],
    ['decision', 'Select cells by the centre rule with exact GEOS <code>covers</code>. The fast selector sends ambiguous centres to the exact test.', 'report', '#phase-2-15-oct-night-co-design-experiments'],
    ['decision', 'Index registered plots once; keep an answer table keyed by plot ID, geometry hash and store hash.', 'idx', ''],
    ['decision', 'Integrity, not authenticity: CRC32 on the header, SHA-256 on the payload and on the decoded raster. Callers needing authenticity pin the file hash.', 'store', ''],
    ['decision', 'Report the standard-format control beside the custom store, even where it is close: 8,532 B as a GeoTIFF against 6,146 B.', 'report', '#how-much-smaller'],
    ['rejected', 'Learned codec selector: dropped because it lost to a plain GeoTIFF.', 'memo', ''],
    ['rejected', 'GPU for queries: a plot is about 120 cells, launch and transfer cost about 10 µs (the whole query), and Metal has no float64.', 'report', '#research-pass'],
    ['rejected', 'GPU for the layer build: compression is 92% of build time and mostly LZMA. Free code derivation would make the build 1.06× faster.', 'report', '#research-pass'],
    ['rejected', 'Interpreter and compiler options: JIT 2–3% slower, tail-calling interpreter 2–5% faster, Cython about 6%, mypyc failed to import, numba 0.2–0.7 s to compile, PyPy has no wheels, GEOS 3.14 about 3%.', 'report', '#research-pass'],
    ['rejected', 'Hand-written geometry validity check: about 8× slower than GEOS in Python, with risky edge cases.', 'report', '#research-pass'],
    ['rejected', 'Calling the public shapely API instead of <code>shapely.lib</code>: +5.2 µs per plot on new boundaries (about 31% slower).', 'report', '#looked-at-not-changed'],
    ['rejected', 'Caching each plot\'s histogram, or counting at load time: would only help the benchmark, not a real re-check.', 'report', '#looked-at-not-changed'],
    ['rejected', 'Raster Join in its bounded form (gives up exactness), k²-raster (the store decodes once in about 0.7 ms) and integral histograms (plots are not rectangles, and row spans of about 10 cells are cheaper to scan).', 'report', '#research-pass'],
    ['negative', 'Phase 1 did not move end-to-end time (index path 52.4 to 50.0 ms). NumPy import (about 25 ms) and interpreter start-up (about 14 ms) dominate.', 'report', '#phase-1-15-oct-evening-faster-decode-reduction-and-selection'],
    ['negative', 'A Phase 3 note said 5 of the remaining 16 µs per new plot was the validity check. Measured in Phase 4, the check is 0.84 µs.', 'report', '#where-the-16-s-goes'],
    ['negative', 'The batch evaluator was slower from a cold start (3.6 ms against 1.6 ms) until Phase 3 removed a hidden <code>numpy.ma</code> import.', 'report', '#phase-3-15-oct-late-night-two-small-wins'],
    ['negative', 'Phase 4 left the 17-plot new-boundary figure unchanged. The step from 5.3× to 5.2× is P0 re-measuring 0.5% lower.', 'report', '#what-it-bought'],
    ['negative', 'Most of the 99.0% reduction is layer analysis, not the codec. A plain GeoTIFF of the decision codes is 98.6% smaller; the best standard composite is 7,038 B against 6,142 B.', 'val', ''],
    ['negative', 'The sensitivity test on JRC sampling is weak: only 1 of 17 plots has any forest cell.', 'scale', '#jrc-aggregation-sensitivity'],
    ['negative', 'The independent validator broke early versions: an unprotected header (15.3% of single-bit flips accepted), an <code>OverflowError</code> path, a 63–282 B blob that allocated 60–130 MB, a level mix-up and an overstated cost model. All fixed with tests.', 'val', ''],
  ];
  const label = { decision: 'Decision', rejected: 'Rejected', negative: 'Negative' };
  const KEEP = 4, seen = {};
  items.forEach(([k, text, src, anchor], i) => {
    seen[k] = (seen[k] || 0) + 1;
    host.append(h('li', { class: `br-item ${k}${seen[k] > KEEP ? ' extra' : ''}`, 'data-kind': k, hidden: seen[k] > KEEP },
      h('span', { class: 'kd' }, label[k]),
      h('span', { class: 'tx', html: text }),
      h('a', { class: 'sr', href: `${BR.GH}/blob/Main/${L[src]}${anchor}` }, L[src].split('/').pop())));
  });
  let kind = 'all', more = false;
  const moreBtn = h('button', { type: 'button', class: 'btn br-more' });
  const apply = () => {
    $$('.br-item', host).forEach(li => { li.hidden = !((kind === 'all' || li.dataset.kind === kind) && (more || !li.classList.contains('extra'))); });
    moreBtn.textContent = more ? 'Show fewer' : `Show all ${items.length} entries`;
  };
  moreBtn.addEventListener('click', () => { more = !more; apply(); });
  host.after(moreBtn);
  seg($('#br-dec'), 'kind', v => { kind = v; if (v !== 'all') more = true; apply(); });
  apply();
})();

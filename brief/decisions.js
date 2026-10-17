/* #decisions: filterable record of key decisions, rejected approaches and negative results. Each row names the code, artifact or validation output that records it. */
(() => {
  const { $, $$, h, seg } = UI;
  const host = $('#br-dec-list'); if (!host) return;
  const items = [
    ['decision', 'Drop <code>treecover2000</code> before any codec: <strong>72% of the Hansen GeoTIFF bytes</strong>, and no EUDR question reads it.', 'artifacts/decision/layer-analysis-v1.json'],
    ['decision', 'Read the JRC 2020 class at the Hansen cell centre, 1 of 9 nested cells, with exact 3×3 nesting and no resampling. Majority and any-forest rules leave every plot decision unchanged.', 'artifacts/decision/layer-analysis-v1.json'],
    ['decision', 'Two levels share one code space. Screening keeps post-2020 loss on all land; the decision level forgets it on 2020 non-forest land. The lossless v1 store stays as the audit tier.', 'engine/decision.py'],
    ['decision', 'Unknown stays unknown: flags are tri-state, and a store records its level so a decision raster cannot be read as screening.', 'engine/decision_summary.py'],
    ['decision', 'Select cells by the centre rule with exact GEOS <code>covers</code>. The fast selector sends ambiguous centres to the exact test.', 'engine/decision_index.py'],
    ['decision', 'Index registered plots once; keep an answer table keyed by plot ID, geometry hash and store hash.', 'engine/decision_index.py'],
    ['decision', 'Integrity, not authenticity: CRC32 on the header, SHA-256 on the payload and on the decoded raster.', 'engine/decision_store.py'],
    ['decision', 'Report the standard-format control beside the custom store: 8,532 B as a GeoTIFF against 6,146 B.', 'artifacts/decision/stores.json'],
    ['rejected', 'GPU for queries: a plot is about 120 cells, launch and transfer cost about 10 µs (the whole query), and Metal has no float64.', null],
    ['rejected', 'GPU for the layer build: compression is 92% of build time and mostly LZMA. Free code derivation would make the build 1.06× faster.', null],
    ['rejected', 'Interpreter and compiler options: JIT 2–3% slower, tail-calling interpreter 2–5% faster, Cython about 6%, mypyc failed to import, numba 0.2–0.7 s to compile, PyPy has no wheels.', null],
    ['rejected', 'Hand-written geometry validity check: about 8× slower than GEOS in Python.', null],
    ['rejected', 'Public shapely API in place of <code>shapely.lib</code>: +5.2 µs per plot on new boundaries (about 31% slower).', null],
    ['rejected', 'Caching a plot\'s histogram across calls, or counting at load time: every timed answer is bound to the expected digests instead.', 'artifacts/decision/benchmark-v1.json'],
    ['negative', 'A plain GeoTIFF of the decision codes is already 98.6% smaller: the layer analysis does most of the work, the split encoding the last 28%.', 'artifacts/decision/stores.json'],
    ['negative', 'The first perf pass moved hot and fresh-process time but not end-to-end: NumPy import (about 25 ms) dominates, which led to the numpy-free re-check (50.0 to 24.9 ms).', 'artifacts/decision/benchmark-v1.json'],
    ['negative', 'The batch evaluator was slower from a cold start (3.6 ms against 1.6 ms) until a hidden <code>numpy.ma</code> import was removed.', 'artifacts/decision/benchmark-v1.json'],
    ['negative', 'The JRC sampling sensitivity test has little power: only 1 of 17 plots has any forest cell.', 'artifacts/decision/layer-analysis-v1.json'],
    ['negative', 'The independent validator broke early versions: an unprotected header (15.3% of single-bit flips accepted), an <code>OverflowError</code> path, a 63–282 B blob that allocated 60–130 MB, a level mix-up. All fixed with tests.', 'validation/decision/report.md'],
  ];
  const label = { decision: 'Decision', rejected: 'Rejected', negative: 'Negative' };
  const KEEP = 4, seen = {};
  items.forEach(([k, text, src], i) => {
    seen[k] = (seen[k] || 0) + 1;
    host.append(h('li', { class: `br-item ${k}${seen[k] > KEEP ? ' extra' : ''}`, 'data-kind': k, hidden: seen[k] > KEEP },
      h('span', { class: 'kd' }, label[k]),
      h('span', { class: 'tx', html: text }),
      src ? h('a', { class: 'sr', href: `${BR.GH}/blob/Main/${src}` }, src.split('/').pop()) : h('span', { class: 'sr dim' }, 'scratch measurement')));
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

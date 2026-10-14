import { useId, useState } from 'react';
import { jrcCellPoint, jrcComparisonAgrees, jrcInCoverage, jrcStructuralEqual } from './jrc-data';
import type { JrcArtifact, JrcCell, JrcPlot, JrcResult } from './jrc-data';
import { Chip, Glyph, Icon, Info } from './components/Primitives';
import './styles/jrc-baseline.css';

const reasons: Record<string, string> = {
  no_selected_cells: 'No native cell centers selected by this polygon',
  out_of_coverage: 'Selected centers extend beyond chip coverage',
  band_mask_invalid: 'Covered cells have unavailable band or invalid mask support',
  no_valid_cells: 'No valid selected cells are available for analysis',
  missing_band: 'Required band unavailable; all analytical outputs suppressed',
};
const count = (n: number | null | undefined) => n === null || n === undefined ? 'Unavailable' : n.toLocaleString('en-US');
const coordinate = (n: number) => n.toFixed(9);

/** The three client-side checks that decide whether the companion comparison is confirmed. */
function agreement(data: JrcArtifact, plot: JrcPlot) {
  const comparison = jrcComparisonAgrees(plot);
  const binding = jrcStructuralEqual(plot.receipt.store, data.store) && jrcStructuralEqual(plot.receipt.full_chip, data.full_chip)
    && plot.receipt.geometry_sha256 === plot.geometry_sha256;
  const fullExact = ['raw_values_equal', 'mask_equal', 'metadata_equal'].every(k => data.full_chip[k] === true);
  return { ok: comparison && binding && fullExact };
}

function signalText(result: JrcResult): string {
  return result.mapped_forest_present === true ? 'Mapped forest class observed'
    : result.mapped_forest_present === false ? 'No mapped forest-class cells under this query' : 'Baseline observation unknown';
}

function NativeCells({ data, plot }: { data: JrcArtifact; plot: JrcPlot }) {
  const [page, setPage] = useState(0), [more, setMore] = useState(false);
  const heading = useId(), region = useId(), cells = plot.evidence.cells, size = 25;
  const pages = Math.max(1, Math.ceil(cells.length / size)), current = Math.min(page, pages - 1);
  const missing = plot.source_result.unknown_reasons.includes('missing_band');
  const visible = cells.slice(current * size, (current + 1) * size);
  function state(cell: JrcCell): string {
    if (missing) return 'Unknown — band unavailable';
    if (!jrcInCoverage(cell, data.native_grid)) return 'Unknown — outside coverage';
    if (!cell.valid) return 'Unknown — invalid mask';
    return cell.value === 0 ? 'Mapped non-forest' : cell.value === 1 ? 'Mapped forest' : 'Unknown';
  }
  return <div className="jrc-cells" data-more={more}>
    <div className="jrc-cells__head">
      <h3 id={heading}>Native JRC cells</h3>
      <button type="button" className="pl-btn pl-btn--sm jrc-more-toggle" aria-pressed={more} aria-controls={region} onClick={() => setMore(!more)}>More columns</button>
    </div>
    <p className="jrc-note">Zero-based JRC chip row/column. Cells are selected by their centers inside the polygon; whole footprints may extend beyond it. Raw invalid values are preserved and excluded from analytics. Focus the table to scroll with the arrow keys.</p>
    <div id={region} className="jrc-table-scroll" role="region" aria-labelledby={heading} tabIndex={0}>
      <table className="pl-table">
        <caption>{cells.length === 0 ? 'No selected centers' : `Showing ${current * size + 1}–${Math.min((current + 1) * size, cells.length)} of ${cells.length} selected centers`}</caption>
        <thead><tr>
          <th scope="col">Row / col</th><th scope="col">Raw class</th><th scope="col">Observation</th>
          <th scope="col" className="jrc-col-more">Stored mask</th><th scope="col" className="jrc-col-more">Native center (°E, °N)</th><th scope="col" className="jrc-col-more">Whole cell corners (°E, °N)</th>
        </tr></thead>
        <tbody>{visible.map(cell => {
          const center = jrcCellPoint(data.native_grid, cell.col + 0.5, cell.row + 0.5);
          const corners = [[cell.col, cell.row], [cell.col + 1, cell.row], [cell.col + 1, cell.row + 1], [cell.col, cell.row + 1]].map(([c, r]) => jrcCellPoint(data.native_grid, c, r));
          const known = !missing && jrcInCoverage(cell, data.native_grid) && cell.valid && cell.value !== null;
          return <tr key={`${cell.row}:${cell.col}`}>
            <th scope="row">{cell.row} / {cell.col}</th>
            <td>{cell.value === null ? 'Unavailable' : <>{cell.value}<span className="jrc-class-label"> — {data.dataset.classes[String(cell.value) as '0' | '1']}</span></>}</td>
            <td><span className={`jrc-cell-state ${known ? cell.value === 1 ? 'jrc-forest' : 'jrc-nonforest' : 'jrc-unknown'}`}>{state(cell)}</span></td>
            <td className="jrc-col-more">{cell.valid ? 'Valid' : 'Invalid'}</td>
            <td className="jrc-col-more jrc-coordinate">{coordinate(center[0])}, {coordinate(center[1])}</td>
            <td className="jrc-col-more"><details><summary>Inspect corners</summary><ol className="jrc-corners">{corners.map(([x, y], i) => <li key={i}>{coordinate(x)}, {coordinate(y)}</li>)}</ol></details></td>
          </tr>;
        })}</tbody>
      </table>
    </div>
    {cells.length > 0 && <div className="jrc-pagination">
      <button type="button" className="pl-btn pl-btn--sm" disabled={current === 0} onClick={() => setPage(current - 1)}>Previous cells</button>
      <span role="status">Page {current + 1} of {pages}</span>
      <button type="button" className="pl-btn pl-btn--sm" disabled={current + 1 === pages} onClick={() => setPage(current + 1)}>Next cells</button>
    </div>}
  </div>;
}

/** Integration owner must supply validateJrc output only after engine acceptance. */
export default function JrcBaseline({ data, plotId }: { data: JrcArtifact; plotId: string }) {
  const heading = useId(), plot = data.plots.find(p => p.plot_id === plotId);
  if (!plot) return <section className="jrc-baseline" aria-labelledby={heading}><h2 id={heading}>2020 baseline observation · JRC v4</h2><p className="jrc-proof-message jrc-proof-warning" role="status">Baseline unavailable for {plotId}. No mapped absence is inferred.</p></section>;
  const result = plot.source_result;
  const signal = signalText(result);
  const { ok } = agreement(data, plot);
  const unknown = result.unknown_cell_count > 0;
  return <section className="jrc-baseline" aria-labelledby={heading}>
    <header className="jrc-header">
      <div>
        <p className="jrc-eyebrow pl-eyebrow">Separate source · {plotId}</p>
        <h2 id={heading}><Glyph kind="forest" />2020 baseline observation · JRC v4</h2>
        <p className="jrc-source-name">JRC Global Forest Cover 2020 · a single reference layer, with no annual timeline.</p>
      </div>
      <span className="jrc-source-tag pl-chip pl-chip--forest">Reference 2020 · separate native grid</span>
    </header>
    <p className="jrc-signal" data-signal={result.mapped_forest_present === null ? 'unknown' : String(result.mapped_forest_present)}>
      {result.mapped_forest_present === true ? <Glyph kind="forest" /> : result.mapped_forest_present === null ? <Glyph kind="unknown" /> : null}
      {signal}
    </p>
    {!ok && <p className="jrc-proof-message jrc-proof-warning" role="status">Companion comparison is unconfirmed. The counts below describe the original source result; inspect the separate proof.</p>}
    <dl className="jrc-counts">
      <div><dt>0 — Non-forest</dt><dd>{count(result.class_counts?.['0'])}</dd></div>
      <div className={(result.class_counts?.['1'] ?? 0) > 0 ? 'is-forest' : undefined}><dt>1 — Forest</dt><dd>{count(result.class_counts?.['1'])}</dd></div>
      <div><dt>Selected centers</dt><dd>{count(result.selected_cell_count)}</dd></div>
      <div><dt>Valid analytical cells</dt><dd>{count(result.valid_cell_count)}</dd></div>
      <div className={unknown ? 'is-unknown' : undefined}><dt>Unknown cells</dt><dd>{count(result.unknown_cell_count)}</dd></div>
    </dl>
    <p className="jrc-support">Support: <strong>{result.support}</strong> · In coverage {count(result.in_coverage_cell_count)} · Outside coverage {count(result.out_of_coverage_cell_count)}</p>
    {result.unknown_reasons.length > 0 && <ul className="jrc-reasons">{result.unknown_reasons.map(reason => <li key={reason}>{reasons[reason] ?? reason}</li>)}</ul>}
    <div className="jrc-caveat">
      <p className="jrc-grid-warning">Own native grid: cell counts, not area, never added to or compared with Hansen. Mapped observations, not legal findings.</p>
      <Info label="About class 0 and comparisons">
        Class 0 is valid Non-forest (not missing data, even though the official style renders it transparent). JRC and Hansen use different definitions and grids; their cell counts are never added or compared as area. These are mapped observations, not legal findings.
      </Info>
    </div>
    <NativeCells key={plotId} data={data} plot={plot} />
    <details className="jrc-proof pl-disclosure"><summary><span>JRC original / compact comparison and provenance</span><span className="pl-disclosure__meta">{ok ? 'original = compact' : 'unconfirmed'}</span></summary>
      <div className="pl-disclosure__body">
        <p className={ok ? 'jrc-proof-message' : 'jrc-proof-message jrc-proof-warning'} role="status">
          {ok ? 'Original and compact result structures agree. Independent oracle and full-chip fidelity are declared by this export.' : 'JRC comparison or fidelity is not confirmed. Review the original result and declared proof before relying on this companion.'}
        </p>
        <dl className="jrc-proof-fields pl-dl"><div><dt>Actual result equality</dt><dd>{jrcStructuralEqual(plot.source_result, plot.compact_result) ? 'Equal' : 'Mismatch'}</dd></div>
          <div><dt>Declared comparison</dt><dd>{plot.comparison.equal === true ? 'Equal' : 'Mismatch'}</dd></div>
          <div><dt>Declared independent oracle</dt><dd>{plot.comparison.independent_oracle_equal === true ? 'Equal' : 'Mismatch'}</dd></div>
          <div><dt>Native grid</dt><dd>{data.native_grid.shape[0]} rows × {data.native_grid.shape[1]} columns · {data.native_grid.crs}</dd></div>
          <div><dt>Query</dt><dd>{data.query_version}</dd></div>
          <div><dt>Affine (a, b, c, d, e, f)</dt><dd className="jrc-hash">{data.native_grid.transform.join(', ')}</dd></div>
          <div><dt>Geometry digest (declared)</dt><dd className="jrc-hash">{plot.geometry_sha256}</dd></div>
          <div><dt>Receipt digest (declared)</dt><dd className="jrc-hash">{plot.receipt.receipt_sha256}</dd></div>
        </dl>
        <p className="jrc-note">Client checks establish internal consistency and geometry association. Engine verification owns source pixels, masks, actual store files and measurement binding. Hash declarations alone do not authenticate them.</p>
        <h3>Citation and metadata</h3>
        <p className="jrc-citation">{data.dataset.citation}</p>
        <p className="jrc-note">Reference year 2020 and version v4 are distinct from publication year {String(data.dataset.publication_year ?? 'Unavailable')}. Release date: {String(data.dataset.release_date ?? 'Unavailable')}. The v4 XML retains older dates and a v2 report link; these do not date the v4 release.</p>
        <details className="pl-disclosure"><summary><span>Preserved XML metadata</span></summary><div className="pl-disclosure__body"><pre>{JSON.stringify(data.dataset.xml_observations, null, 2)}</pre></div></details>
        <ul className="jrc-limitations">{data.limitations.map((limitation, i) => <li key={i}>{limitation}</li>)}</ul>
        <details className="pl-disclosure"><summary><span>Frozen JRC receipt and result structures</span></summary><div className="pl-disclosure__body"><pre>{JSON.stringify({ source_result: plot.source_result, compact_result: plot.compact_result, comparison: plot.comparison, receipt: plot.receipt }, null, 2)}</pre></div></details>
        <details className="pl-disclosure"><summary><span>JRC-only store and benchmark disclosure</span></summary><div className="pl-disclosure__body"><p className="jrc-note">Declared companion metadata only. Store byte fields use bytes; timing units are preserved per field. Shared inputs and accounting scope are defined by this companion, with no combined Hansen metric.</p><pre>{JSON.stringify(data.store, null, 2)}</pre>{data.benchmark === null ? <p>Benchmark: Unavailable</p> : <pre>{JSON.stringify(data.benchmark, null, 2)}</pre>}</div></details>
      </div>
    </details>
  </section>;
}

/**
 * Compact JRC row for the inspector's "Mapped" column. Never shows JRC numbers
 * as comparable to Hansen counts: it names the separate grid every time.
 */
export function JrcSummary({ data, status, error, plotId, onLoad }: {
  data: JrcArtifact | null; status: 'idle' | 'loading' | 'ready' | 'error'; error?: string; plotId: string; onLoad: () => void;
}) {
  if (status === 'idle') return <button type="button" className="pl-btn pl-btn--sm jrc-summary-load" onClick={onLoad}><Glyph kind="forest" />Load JRC 2020 baseline</button>;
  if (status === 'loading') return <p className="jrc-summary jrc-summary--loading" role="status"><span className="pl-spinner" aria-hidden="true" />Loading the separate JRC source…</p>;
  if (status === 'error' || !data) return <div className="jrc-summary jrc-summary--error" role="status">
    <p className="jrc-summary__title"><Glyph kind="unknown" />JRC 2020 v4 unavailable</p>
    <p>{error || 'JRC companion unavailable.'}</p>
    <p className="pl-fine">Hansen review remains usable. No baseline absence is inferred.</p>
    <button type="button" className="pl-btn pl-btn--sm" onClick={onLoad}>Retry JRC companion</button>
  </div>;
  const plot = data.plots.find(p => p.plot_id === plotId);
  if (!plot) return <p className="jrc-summary jrc-summary--missing" role="status"><Glyph kind="unknown" />Baseline unavailable for {plotId}. No mapped absence is inferred.</p>;
  const result = plot.source_result, forest = result.class_counts?.['1'];
  const { ok } = agreement(data, plot);
  const present = result.mapped_forest_present;
  const why = result.unknown_reasons.map(r => reasons[r] ?? r).join('; ');
  return <div className="jrc-summary" data-signal={present === null ? 'unknown' : String(present)}>
    <p className="jrc-summary__title">
      <Glyph kind="forest" /><strong>JRC 2020 v4</strong>
      {ok
        ? <Chip tone="proof" title="The separate JRC original and compact results agree. An engineering agreement, not a legal finding."><Icon name="check" size={12} />original = compact</Chip>
        : <Chip tone="review" title="The JRC comparison or its binding is not confirmed. Inspect the separate JRC proof."><Icon name="question" size={12} />comparison unconfirmed</Chip>}
    </p>
    <p className="jrc-summary__value">
      {forest === null || forest === undefined
        ? <>Forest-class count unavailable for <span className="pl-num">{count(result.selected_cell_count)}</span> JRC cells (separate grid)</>
        : <><span className={`pl-num${forest > 0 ? ' jrc-summary__n' : ''}`}>{count(forest)}</span> forest-class cells of <span className="pl-num">{count(result.selected_cell_count)}</span> JRC cells (separate grid)</>}
    </p>
    <p className="jrc-summary__signal">
      {present === null && <Glyph kind="unknown" />}
      {present === true ? 'Mapped forest present'
        : present === false ? 'No mapped forest-class cells'
          : `Unknown${why ? `: ${why}` : ''}`}
    </p>
  </div>;
}

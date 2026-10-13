import { useId, useState } from 'react';
import { jrcCellPoint, jrcComparisonAgrees, jrcInCoverage, jrcStructuralEqual } from './jrc-data';
import type { JrcArtifact, JrcCell, JrcPlot } from './jrc-data';
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

function NativeCells({ data, plot }: { data: JrcArtifact; plot: JrcPlot }) {
  const [page, setPage] = useState(0);
  const heading = useId(), cells = plot.evidence.cells, size = 25;
  const pages = Math.max(1, Math.ceil(cells.length / size)), current = Math.min(page, pages - 1);
  const missing = plot.source_result.unknown_reasons.includes('missing_band');
  const visible = cells.slice(current * size, (current + 1) * size);
  function state(cell: JrcCell): string {
    if (missing) return 'Unknown — band unavailable';
    if (!jrcInCoverage(cell, data.native_grid)) return 'Unknown — outside coverage';
    if (!cell.valid) return 'Unknown — invalid mask';
    return cell.value === 0 ? 'Mapped non-forest' : cell.value === 1 ? 'Mapped forest' : 'Unknown';
  }
  return <div className="jrc-cells">
    <h3 id={heading}>Native JRC cells</h3>
    <p>Zero-based JRC chip row/column. Selection uses cell centers covered by the supplied polygon; whole cell footprints may extend beyond it.</p>
    <p>Scroll horizontally to inspect all columns, or focus the table and use Left/Right arrows. Raw invalid values are preserved and excluded from analytics.</p>
    <div className="jrc-table-scroll" role="region" aria-labelledby={heading} tabIndex={0}>
      <table>
        <caption>{cells.length === 0 ? 'No selected centers' : `Showing ${current * size + 1}–${Math.min((current + 1) * size, cells.length)} of ${cells.length} selected centers. Raw invalid values are preserved and excluded from analytics.`}</caption>
        <thead><tr><th scope="col">Row / column</th><th scope="col">Raw class</th><th scope="col">Stored mask</th><th scope="col">Analytical observation</th><th scope="col">Native center (°E, °N)</th><th scope="col">Whole cell corners (°E, °N)</th></tr></thead>
        <tbody>{visible.map(cell => {
          const center = jrcCellPoint(data.native_grid, cell.col + 0.5, cell.row + 0.5);
          const corners = [[cell.col, cell.row], [cell.col + 1, cell.row], [cell.col + 1, cell.row + 1], [cell.col, cell.row + 1]].map(([c, r]) => jrcCellPoint(data.native_grid, c, r));
          const known = !missing && jrcInCoverage(cell, data.native_grid) && cell.valid && cell.value !== null;
          return <tr key={`${cell.row}:${cell.col}`}>
            <th scope="row">{cell.row} / {cell.col}</th>
            <td>{cell.value === null ? 'Unavailable' : `${cell.value} — ${data.dataset.classes[String(cell.value) as '0' | '1']}`}</td>
            <td>{cell.valid ? 'Valid' : 'Invalid'}</td>
            <td><span className={`jrc-cell-state ${known ? cell.value === 1 ? 'jrc-forest' : 'jrc-nonforest' : 'jrc-unknown'}`}>{state(cell)}</span></td>
            <td className="jrc-coordinate">{coordinate(center[0])}, {coordinate(center[1])}</td>
            <td><details><summary>Inspect corners</summary><ol className="jrc-corners">{corners.map(([x, y], i) => <li key={i}>{coordinate(x)}, {coordinate(y)}</li>)}</ol></details></td>
          </tr>;
        })}</tbody>
      </table>
    </div>
    {cells.length > 0 && <div className="jrc-pagination">
      <button type="button" disabled={current === 0} onClick={() => setPage(current - 1)}>Previous cells</button>
      <span role="status">Page {current + 1} of {pages}</span>
      <button type="button" disabled={current + 1 === pages} onClick={() => setPage(current + 1)}>Next cells</button>
    </div>}
  </div>;
}

/** Integration owner must supply validateJrc output only after engine acceptance. */
export default function JrcBaseline({ data, plotId }: { data: JrcArtifact; plotId: string }) {
  const heading = useId(), plot = data.plots.find(p => p.plot_id === plotId);
  if (!plot) return <section className="jrc-baseline" aria-labelledby={heading}><h2 id={heading}>2020 baseline observation · JRC v4</h2><p role="status">Baseline unavailable for {plotId}. No mapped absence is inferred.</p></section>;
  const result = plot.source_result;
  const signal = result.mapped_forest_present === true ? 'Mapped forest class observed'
    : result.mapped_forest_present === false ? 'No mapped forest-class cells under this query' : 'Baseline observation unknown';
  const comparison = jrcComparisonAgrees(plot);
  const binding = jrcStructuralEqual(plot.receipt.store, data.store) && jrcStructuralEqual(plot.receipt.full_chip, data.full_chip)
    && plot.receipt.geometry_sha256 === plot.geometry_sha256;
  const fullExact = ['raw_values_equal', 'mask_equal', 'metadata_equal'].every(k => data.full_chip[k] === true);
  return <section className="jrc-baseline" aria-labelledby={heading}>
    <header className="jrc-header"><div><p className="jrc-eyebrow">Separate source · {plotId}</p><h2 id={heading}>2020 baseline observation · JRC v4</h2></div><span className="jrc-source-tag">Reference 2020 · version v4</span></header>
    <p className="jrc-source-name">JRC Global Forest Cover 2020 · v4. A single reference layer; it contains no annual timeline.</p>
    <p className="jrc-grid-warning">JRC’s native grid differs from Hansen observation years 2001–2025 · v1.13. These source cell counts are not area; do not add or compare them as common area units.</p>
    <p className="jrc-signal" data-signal={result.mapped_forest_present === null ? 'unknown' : String(result.mapped_forest_present)}>{signal}</p>
    {(!comparison || !binding || !fullExact) && <p className="jrc-proof-message jrc-proof-warning" role="status">Companion comparison is unconfirmed. The counts below describe the original source result; inspect the separate proof.</p>}
    <dl className="jrc-counts">
      <div><dt>0 — Non-forest</dt><dd>{count(result.class_counts?.['0'])}</dd></div>
      <div><dt>1 — Forest</dt><dd>{count(result.class_counts?.['1'])}</dd></div>
      <div><dt>Selected centers</dt><dd>{count(result.selected_cell_count)}</dd></div>
      <div><dt>Valid analytical cells</dt><dd>{count(result.valid_cell_count)}</dd></div>
      <div><dt>Unknown cells</dt><dd>{count(result.unknown_cell_count)}</dd></div>
    </dl>
    <p className="jrc-support">Support: <strong>{result.support}</strong> · In coverage {count(result.in_coverage_cell_count)} · Outside coverage {count(result.out_of_coverage_cell_count)}</p>
    {result.unknown_reasons.length > 0 && <ul className="jrc-reasons">{result.unknown_reasons.map(reason => <li key={reason}>{reasons[reason] ?? reason}</li>)}</ul>}
    <p>Known class 0 remains Non-forest even though the official QML renders it transparent. Non-forest does not mean no tree canopy; JRC and Hansen use different source definitions. These are mapped observations, not legal forest or compliance findings.</p>
    <NativeCells key={plotId} data={data} plot={plot} />
    <details className="jrc-proof"><summary>JRC original / compact comparison and provenance</summary>
      <p className={comparison && binding && fullExact ? 'jrc-proof-message' : 'jrc-proof-message jrc-proof-warning'} role="status">
        {comparison && binding && fullExact ? 'Original and compact result structures agree. Independent oracle and full-chip fidelity are declared by this export.' : 'JRC comparison or fidelity is not confirmed. Review the original result and declared proof before relying on this companion.'}
      </p>
      <dl className="jrc-proof-fields"><div><dt>Actual result equality</dt><dd>{jrcStructuralEqual(plot.source_result, plot.compact_result) ? 'Equal' : 'Mismatch'}</dd></div>
        <div><dt>Declared comparison</dt><dd>{plot.comparison.equal === true ? 'Equal' : 'Mismatch'}</dd></div>
        <div><dt>Declared independent oracle</dt><dd>{plot.comparison.independent_oracle_equal === true ? 'Equal' : 'Mismatch'}</dd></div>
        <div><dt>Native grid</dt><dd>{data.native_grid.shape[0]} rows × {data.native_grid.shape[1]} columns · {data.native_grid.crs}</dd></div>
        <div><dt>Query</dt><dd>{data.query_version}</dd></div>
        <div><dt>Affine (a, b, c, d, e, f)</dt><dd className="jrc-hash">{data.native_grid.transform.join(', ')}</dd></div>
        <div><dt>Geometry digest (declared)</dt><dd className="jrc-hash">{plot.geometry_sha256}</dd></div>
        <div><dt>Receipt digest (declared)</dt><dd className="jrc-hash">{plot.receipt.receipt_sha256}</dd></div>
      </dl>
      <p>Client checks establish internal consistency and geometry association. Engine verification owns source pixels, masks, actual store files and measurement binding. Hash declarations alone do not authenticate them.</p>
      <h3>Citation and metadata</h3><p className="jrc-citation">{data.dataset.citation}</p>
      <p>Reference year 2020 and version v4 are distinct from publication year {String(data.dataset.publication_year ?? 'Unavailable')}. Release date: {String(data.dataset.release_date ?? 'Unavailable')}. The v4 XML retains older dates and a v2 report link; these do not date the v4 release.</p>
      <details><summary>Preserved XML metadata</summary><pre>{JSON.stringify(data.dataset.xml_observations, null, 2)}</pre></details>
      <ul>{data.limitations.map((limitation, i) => <li key={i}>{limitation}</li>)}</ul>
      <details><summary>Frozen JRC receipt and result structures</summary><pre>{JSON.stringify({ source_result: plot.source_result, compact_result: plot.compact_result, comparison: plot.comparison, receipt: plot.receipt }, null, 2)}</pre></details>
      <details><summary>JRC-only store and benchmark disclosure</summary><p>Declared companion metadata only. Store byte fields use bytes; timing units are preserved per field. Shared inputs and accounting scope are defined by this companion, with no combined Hansen metric.</p><pre>{JSON.stringify(data.store, null, 2)}</pre>{data.benchmark === null ? <p>Benchmark: Unavailable</p> : <pre>{JSON.stringify(data.benchmark, null, 2)}</pre>}</details>
    </details>
  </section>;
}

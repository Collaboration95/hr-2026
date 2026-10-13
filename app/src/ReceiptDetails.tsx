import { useId, type ReactNode } from "react";
import type { Demo, Plot } from "./types";
import "./styles/receipt.css";

type Fields = Record<string, unknown>;
const object = (value: unknown): Fields =>
  value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Fields)
    : {};
const scalar = (value: unknown): string => {
  if (typeof value === "string") return value.length ? value : "Unavailable";
  if (typeof value === "number")
    return Number.isFinite(value) ? String(value) : "Unavailable";
  if (typeof value === "boolean") return String(value);
  return "Unavailable";
};
const count = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString("en-US")
    : "Unavailable";
const flag = (value: unknown) =>
  value === true
    ? "Mapped loss present"
    : value === false
      ? "No mapped loss"
      : "Unavailable";
const claim = (value: unknown) =>
  value === true
    ? "Equal — engine claim"
    : value === false
      ? "Not equal — engine claim"
      : "Unavailable";
const bytes = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value)
    ? `${count(value)} bytes`
    : "Unavailable";

function Field({
  label,
  children,
  code = false,
}: {
  label: string;
  children: ReactNode;
  code?: boolean;
}) {
  return (
    <div className="pl-receipt__field">
      <dt>{label}</dt>
      <dd>{code ? <code>{children}</code> : children}</dd>
    </div>
  );
}

function Files({ value, bands = false }: { value: unknown; bands?: boolean }) {
  if (!Array.isArray(value) || value.length === 0)
    return <p className="pl-receipt__note">Unavailable</p>;
  return (
    <ul className="pl-receipt__files">
      {value.map((entry, index) => {
        const file = object(entry);
        return (
          <li key={index}>
            {bands && <h4>{scalar(file.band)}</h4>}
            <dl>
              <Field label="File path" code>
                {scalar(file.path)}
              </Field>
              <Field label="Stored size">{bytes(file.bytes)}</Field>
              {bands && (
                <>
                  <Field label="Compression">{scalar(file.compression)}</Field>
                  <Field label="Nodata metadata">{scalar(file.nodata)}</Field>
                </>
              )}
              <Field label="File SHA-256" code>
                {scalar(file.sha256)}
              </Field>
            </dl>
          </li>
        );
      })}
    </ul>
  );
}

/** Read-only presentation of the validated frozen response supplied by the app. */
export default function ReceiptDetails({
  data,
  plot,
  year,
}: {
  data: Demo;
  plot: Plot;
  year: number;
}) {
  const id = useId();
  const receipt = object(plot.receipt);
  const grid = object(receipt.grid === undefined ? data.dataset : receipt.grid);
  const shape = Array.isArray(grid.shape) ? grid.shape : [];
  const transform = Array.isArray(grid.transform) ? grid.transform : [];
  const store = object(receipt.compact_store);
  const benchmark = object(data.benchmark);
  const registry = object(benchmark.registry);
  const result = plot.source_result;
  const periods = [
    ...new Set([
      ...(Array.isArray(data.periods)
        ? data.periods
        : Object.keys(data.periods ?? {})),
      ...Object.keys(object(receipt.observed_periods)),
      ...Object.keys(result?.periods ?? {}),
    ]),
  ];
  const pair = (first: number, second: number) =>
    transform[first] == null || transform[second] == null
      ? "Unavailable"
      : `(${scalar(transform[first])}, ${scalar(transform[second])})`;
  const unknownReasons = result?.unknown_reasons;
  const benchmarkState = data.benchmark_status?.state;

  return (
    <section className="pl-receipt" aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`}>Receipt basis</h3>
      <p className="pl-receipt__note">
        From the loaded evidence export. Hashes identify records and files; this
        view does not independently verify their contents or certify compliance.
      </p>
      <dl className="pl-receipt__overview">
        <Field label="Plot">{plot.plot_id}</Field>
        <Field label="Source product / release">
          {scalar(data.dataset.product)}
        </Field>
        <Field label="Query contract" code>
          {scalar(data.query_version)}
        </Field>
        <Field label="Selected observation year">{scalar(year)}</Field>
        <Field label={`${year} observed loss cells`}>
          {count(result?.yearly_loss_counts?.[String(year)])}
        </Field>
        <Field label="Selected support">{scalar(result?.support)}</Field>
      </dl>

      <details className="pl-receipt__disclosure">
        <summary>Observation periods and support</summary>
        <p className="pl-receipt__note">
          Stored results for this plot. Counts describe observed native cells,
          not hectares. Mapped tree-cover loss is not a legal deforestation
          finding.
        </p>
        {periods.length > 0 ? (
          <div className="pl-receipt__table-wrap">
            <table>
              <caption>Mapped observations by query period</caption>
              <thead>
                <tr>
                  <th scope="col">Period</th>
                  <th scope="col">Mapped loss</th>
                  <th scope="col">Observed cells</th>
                </tr>
              </thead>
              <tbody>
                {periods.map((period) => (
                  <tr key={period}>
                    <th scope="row">{period}</th>
                    <td>
                      {flag(result?.periods[period]?.mapped_loss_present)}
                    </td>
                    <td>
                      {count(result?.periods[period]?.observed_loss_cell_count)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="pl-receipt__note">Periods: Unavailable</p>
        )}
        <dl>
          <Field label="Selected cell centers">
            {count(result?.selected_cell_count)}
          </Field>
          <Field label="Valid land cells">
            {count(result?.valid_land_cell_count)}
          </Field>
          <Field label="Unknown cells">
            {count(result?.unknown_cell_count)}
          </Field>
          <Field label="Unknown reasons">
            {Array.isArray(unknownReasons)
              ? unknownReasons.length
                ? unknownReasons.join(", ")
                : "None reported for this query"
              : "Unavailable"}
          </Field>
          <Field label="Partial-support rule">
            {scalar(receipt.partial_support_rule)}
          </Field>
        </dl>
      </details>

      <details className="pl-receipt__disclosure">
        <summary>Supplier record and geometry</summary>
        <p className="pl-receipt__note">
          Supplier statements remain declarations. Record and geometry hashes
          identify the supplied inputs, not the truth of those statements.
        </p>
        <dl>
          <Field label="Supplier final declaration (verbatim)">
            {scalar(plot.supplier.c5_deforestation_final_status)}
          </Field>
          <Field label="Supplier EUDR declaration (verbatim)">
            {scalar(plot.supplier.i1_eudr_status)}
          </Field>
          <Field label="Supplier row SHA-256" code>
            {scalar(receipt.supplier_row_sha256)}
          </Field>
          <Field label="Geometry SHA-256" code>
            {scalar(receipt.geometry_sha256)}
          </Field>
        </dl>
        <h4>Supplier input files</h4>
        <Files value={receipt.supplier_sources} />
      </details>

      <details className="pl-receipt__disclosure">
        <summary>Native grid and query rules</summary>
        <dl>
          <Field label="Coordinate reference system">{scalar(grid.crs)}</Field>
          <Field label="Rows × columns">
            {shape.length === 2 &&
            shape.every(
              (value) => typeof value === "number" && Number.isFinite(value),
            )
              ? `${count(shape[0])} × ${count(shape[1])}`
              : "Unavailable"}
          </Field>
          <Field label="Grid origin (x, y)" code>
            {pair(2, 5)}
          </Field>
          <Field label="Column step (Δx, Δy)" code>
            {pair(0, 3)}
          </Field>
          <Field label="Row step (Δx, Δy)" code>
            {pair(1, 4)}
          </Field>
          <Field label="Affine transform [a, b, c, d, e, f]" code>
            {transform.length === 6 &&
            transform.every(
              (value) => typeof value === "number" && Number.isFinite(value),
            )
              ? `[${transform.join(", ")}]`
              : "Unavailable"}
          </Field>
          <Field label="Cell-center / boundary rule">
            {scalar(receipt.boundary_rule)}
          </Field>
          <Field label="Valid-land rule">
            {scalar(receipt.valid_land_rule)}
          </Field>
        </dl>
        <p className="pl-receipt__note">
          Affine coordinates: x = a × column + b × row + c; y = d × column + e ×
          row + f. The transform locates cell corners; the query rule above
          selects centers.
        </p>
        <p className="pl-receipt__note">
          {grid.crs === "EPSG:4326"
            ? "Coordinates and steps are degrees, not area."
            : "Steps use the coordinate reference system’s units."}{" "}
          Canopy 2000 is not a forest-2020 baseline.
        </p>
      </details>

      <details className="pl-receipt__disclosure">
        <summary>Source band files and metadata</summary>
        <p className="pl-receipt__note">
          Files recorded in the export; paths are local identifiers, not
          download links. Sizes are exact stored bytes.
        </p>
        <Files
          value={
            receipt.sources === undefined
              ? data.dataset.sources
              : receipt.sources
          }
          bands
        />
        <dl>
          <Field label="Source metadata SHA-256" code>
            {scalar(receipt.source_metadata_sha256)}
          </Field>
          <Field label="Receipt SHA-256" code>
            {scalar(receipt.receipt_sha256)}
          </Field>
          <Field label="Export content SHA-256" code>
            {scalar(data.content_sha256)}
          </Field>
        </dl>
        <p className="pl-receipt__note">
          These identifiers are not signatures or independent evidence of source
          accuracy.
        </p>
      </details>

      <details className="pl-receipt__disclosure">
        <summary>Retained compact store · engine claims</summary>
        <dl>
          <Field label="Store path" code>
            {scalar(store.path)}
          </Field>
          <Field label="Full-grid raw band values">
            {claim(store.raw_bands_equal)}
          </Field>
          <Field label="Full-grid band validity masks">
            {claim(store.band_masks_equal)}
          </Field>
        </dl>
        <p className="pl-receipt__note">
          Equality here is reported by the engine for the full grid. It concerns
          encoding fidelity, not source accuracy or legal compliance. This
          component does not recheck the files.
        </p>
        <h4>Compact store files</h4>
        <Files value={store.files} />
      </details>

      {(data.benchmark != null || data.benchmark_status != null) && (
        <details className="pl-receipt__disclosure">
          <summary>Benchmark experiment identity</summary>
          <dl>
            <Field label="Binding status reported by export">
              {benchmarkState === "bound_retained"
                ? "Bound to retained experiment (bound_retained)"
                : benchmarkState === "not_included"
                  ? "Benchmark not included (not_included)"
                  : scalar(benchmarkState)}
            </Field>
            <Field label="Experiment ID" code>
              {scalar(benchmark.experiment_id)}
            </Field>
            <Field label="Measured run ID" code>
              {scalar(registry.run_id)}
            </Field>
            <Field label="Archived result path" code>
              {scalar(registry.result_path)}
            </Field>
          </dl>
          <p className="pl-receipt__note">
            Identity and binding status belong to this frozen export. Opening
            this receipt does not rerun the benchmark.
          </p>
        </details>
      )}
    </section>
  );
}

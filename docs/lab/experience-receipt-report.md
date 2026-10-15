# C3-B readable provenance receipt — delivery complete

Delivered 2026-10-13, after scoped verification at approximately 03:00 UTC. Owned writes only: `app/src/ReceiptDetails.tsx`, `app/src/styles/receipt.css`, this report. Previous note/component ownership ended. No App/types/package/engine/canonical/test edits, dependency installs, Git mutations or external uploads.

## Integration for Hooke

```tsx
import ReceiptDetails from './ReceiptDetails';
// Inside the existing named receipt dialog, using its current frozen data:
<ReceiptDetails data={data} plot={plot} year={year} />
```

Exact default-export API uses existing `Demo` and `Plot` types. CSS imports automatically from the component. Existing raw JSON disclosures, JSON download and dialog focus handling remain lead-owned. The component does not fetch artifacts, requery cells, mutate props, access storage or contact an external service.

## What the analyst can read

The compact overview gives plot, exact source product/release, query version, selected year/count and support. Six native disclosures expose:

- Observation periods and support: named period table, observed-cell counts, tri-state mapped-loss wording, selected/valid/unknown counts, reasons, and exact engine partial-support rule.
- Supplier record and geometry: verbatim supplier final/EUDR declarations explicitly labelled as declarations; full row/geometry hashes and supplier CSV/GeoJSON file paths, bytes and full hashes.
- Native grid and rules: CRS, rows × columns, origin, row/column steps, full six-value affine transform, exact boundary and valid-land rules. Degrees are not converted to area; canopy2000 is not presented as forest2020.
- Source band files and metadata: exact band, path, stored bytes, compression, nodata metadata and full file hashes, plus metadata/receipt/export hashes.
- Retained compact store: full store path and file details, with full-grid raw-value/mask equality explicitly labelled **engine claims**. False says “Not equal — engine claim”; missing/null says “Unavailable”.
- Benchmark identity when an export includes benchmark data or explicit benchmark status: exact experiment ID, run ID, archive path and reported binding status. No new benchmark measure, performance claim or inferred binding.

Missing/null values display “Unavailable”. Numeric zero remains 0 (including zero bytes), false mapped loss displays “No mapped loss”, and null flags display “Unavailable” even when observed counts are zero. An empty unknown-reasons array says “None reported for this query”; missing source result does not. Source metadata can come from the envelope when that receipt field is absent, while an explicit null field stays unavailable. Full paths and hashes are selectable/wrapping text, not fake download links. No optional copy button was added.

## Evidence and checks

Read actual updated assignment, interface, `app/src/types.ts`, frontend receipt validation, `engine/proof.py` receipt/binding code, current CSS and served artifact structure. Earlier project/charter/SystemEarth references remain applicable.

Validated artifact used by Node and browser checks:

```text
content_sha256:
d22b0cac287de0d12b1ecfdcf114aa549a886b86299ca8cd43384c6ff2e075b2
experiment_id:
exp-0109a8d6c4782217871315b92c63a971d11ebd164585c80981f24c55b4f68fea
```

These are input identities recorded for reproducibility, not independent verification claims.

Strict isolated TypeScript check passed before and after formatting:

```sh
app/node_modules/.bin/tsc --noEmit --strict --jsx react-jsx --moduleResolution bundler --module esnext --target es2022 --skipLibCheck app/src/ReceiptDetails.tsx
```

An in-memory Node render probe used existing esbuild (`write:false`, React external, CSS empty loader), React DOM `renderToStaticMarkup`, and the actual `validateDemo` function on the frontend artifact. No test/build files written. Assertions passed for:

1. Actual P-0005 source identity, 604 × 1233 grid, selected2025 count11, benchmark identity/status, full supplier/geometry/receipt/source-band/store-file hashes.
2. Actual P-0003 selected2023 count0 and known-false “No mapped loss”.
3. Synthetic missing receipt/source fixture: selected-year count unavailable and no invented “None reported” reasons; absent benchmark/status omits its disclosure.
4. Synthetic false raw-value claim, null mask claim and zero-byte file: distinct Not equal/Unavailable/0bytes outputs.
5. Synthetic period with null signal and zero observed cells: Unavailable signal alongside numeric0.
6. CSS parsed with existing esbuild and zero warnings.

Synthetic variants were isolated presentation fixtures, never written into supplied evidence. Existing Prettier formatted only the two owned implementation files.

## Browser verification

T3 `preview_status` then `preview_open` succeeded; new own tab `tab_r`. First mounted the actual React component with data from `loadDemo()` in a temporary host: P-0005/2025 displayed11 and the correct product/contract. Shared dev HMR later removed this temporary host, invalidating the following attempted keyboard probe; it was not counted as a pass. T3 main-tab resize timed out at5000ms, while status/open still reported available; no fallback browser was used.

To complete stable scoped layout/keyboard checks, rendered the actual component to HTML in memory and injected it with its exact system/receipt CSS into a same-tab, same-origin `srcdoc` iframe. This component's interactions are native details/summary; no event handler or network behavior is mocked. No fixture file or screenshot file was written. This isolates presentation from unrelated live App reloads. It is **not** a claim of integrated modal/mobile testing.

Observed results:

- Enter on first summary opened the period disclosure; computed keyboard outline was3px. Tab moved to “Supplier record and geometry”.
- Actual P-0005 period table showed2021–2023: “No mapped loss”,0;2024–2025: “Mapped loss present”,18. These are existing artifact results, not new measurements.
- All six disclosures open at iframe innerWidth390: document scrollWidth390; no dd/code/table/summary extended beyond viewport; code font12px.
- Repeat at320px: scrollWidth320, stacked field layout280px wide, zero inspected overflow elements.
- Repeat at720px: scrollWidth720, two-column label/value grid approximately252/416px, zero inspected overflow elements.
- T3 screenshots visually inspected for narrow period/declaration content and source-band file/hash wrapping. Full hashes remain in DOM and were exact-string checked by render assertions.

Own tab restored to the normal app after checks. No other browser tabs were touched.

## Lead review / remaining action

Integrate within the existing named receipt dialog, preferably replacing the redundant old short metadata list, then have W3 check real dialog scrolling, focus return and coexistence with raw JSON/download controls. The isolated checks establish component semantics, disclosure keyboard behavior and responsive wrapping; they do not certify source truth, independent hash verification or whole-app accessibility.

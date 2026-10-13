# C4-A runtime gate handoff — 13 October 2026

For Hooke Astra `01a132f8-f7e5-7fd0-9690-31faa43db819` and master `01a130e9-aaf5-7a53-9cff-96d579f69b35`. No callable agent messaging tool is exposed; this report is the shared-file handoff. One worker implements both C4-A and C4-B under the user's disjoint ownership instruction.

Status: implemented and reviewable; JRC candidate remains **unaccepted**. Reading the candidate for preliminary shape tests does not authorize an asset copy, mounting, publication or an accepted-evidence claim. Engine proof/export fixes and independent acceptance remain integration prerequisites.

## Exact files

- `app/src/jrc-data.ts` — public types, pure consistency/association gate, optional loader and native-grid/comparison helpers.
- `app/checks/jrc-ingest-contract.test.mjs` — paired contract/forgery/unknown/loader checks.
- `app/checks/jrc-ingest-fixtures.mjs` — frozen candidate/main test inputs, explicitly artificial shape controls and standalone synthetic display fixtures.
- `app/checks/jrc-ingest-browser.mjs` — isolated loopback display server and installed-browser verification, shared with C4-B.
- `docs/lab/experience-jrc-ingest-report.md` — this handoff.

C4-B's other three files are listed in `experience-jrc-view-report.md`. No App, configuration, package, copied asset, core, engine, source artifact or Git mutation was made by this worker.

## Integration API

- Exported types: `JrcArtifact`, `JrcPlot`, `JrcResult`, `JrcCell`, `JrcGrid`.
- `validateJrc(value: unknown, main: Demo): JrcArtifact` returns the exact input unchanged. `main` must already be the accepted, validated Hansen envelope. Geometry association reads each main plot's `receipt.geometry_sha256`, where the actual main export stores it.
- `loadJrc(main: Demo, signal?: AbortSignal): Promise<JrcArtifact>` fetches only `/data/jrc-baseline-v1.json`, with `cache: 'no-store'`, one response body read and explicit errors. It preserves cancellation and has no Hansen mutation or fallback result.
- `jrcStructuralEqual`, `jrcComparisonAgrees`, `jrcInCoverage`, `jrcCellPoint` support the separate panel. Comparison covers nested result extensions, independently of object key order. Coordinates use the original six-coefficient JRC affine.

Gate pins the actual schema `plotline.jrc-baseline.v1`, query `jrc2020-centers.v1`, product string `JRC Global Forest Cover Map 2020`, v4/reference2020 and acquired 1809×3695 EPSG:4326 grid/affine. It compares the declared acquired source/chip/provenance/QML/XML identities, required-input and QML associations, all17unique plot IDs/exact geometries/main geometry digests, support/reason/count/tri-state structure, complete selected cell records and source analytics. Invalid covered masks preserve raw0/1; outside records require null/invalid. `missing_band` globally suppresses analytics even when stored raw evidence has a valid mask. Sparse arrays, non-JSON extensions, excessive nesting/work and malformed scalar types fail explicitly.

Receipt source/query/version/reference/geometry/store/full-chip/run declarations must agree across the envelope. Result digest equality must agree with actual structural equality. Cohort summaries must reflect actual plot outputs. A truthful source/compact mismatch or false oracle/full-chip claim can remain inspectable, but must never appear confirmed; a forged equality flag fails validation. Benchmark is preserved as raw JRC-only declared metadata (or null), with its schema/run binding checked.

## Checks and evidence

```sh
node --test app/checks/jrc-ingest-contract.test.mjs
app/node_modules/.bin/tsc --project app/tsconfig.json --noEmit
node app/checks/jrc-ingest-browser.mjs --verify
```

- Runtime/loader suite: **76 passed, 0 failed**. Includes actual frozen preliminary candidate shape association; explicit valid0, positive1, partial absence/positive, no centers, invalid masks, missing band including no centers, outside support; paired forged signals, geometry/source identity/grid substitutions, deep extension mismatch, contradictory comparisons, evidence/summary/receipt bindings, one-body transport, malformed/HTML/HTTP/network failures and cancellation.
- TypeScript no-emit compile passed for the whole current `app/src` tree, including concurrent live modules. The project build command runs asset synchronization, so the worker used the compiler directly to respect asset ownership.
- Browser findings and the T3-first fallback evidence are in the view report. No actual candidate observations were mounted in either the main app or the synthetic display page.

The candidate was read once per check process, avoiding mid-test regenerated-file mixtures. The inspected input had content declaration `c13127c9f6d8654a1dae0d66945c981bfc340b20467124dd2e55829d79d754a3` and a separate JRC benchmark run. That identifies this preliminary test input; it is not an acceptance marker.

## Remaining gates and limits

- Hooke must wait for explicit engine acceptance, reread the resulting canonical envelope and rerun these checks before integrating. Accepted-data/browser QA remains unperformed while acceptance is pending. This worker does not copy or mount the candidate.
- The source identity/grid pins are deliberately bounded to this acquisition. If accepted provenance, chip, styles, source or grid changes, review and update this module; do not silently weaken the gate.
- The UI does not recompute Python object hashes, query polygon membership, verify actual source/store files, rerun the independent oracle or validate benchmark sample guards. Those remain engine/independent-verifier duties. A coordinated forgery can preserve hash declarations; hashes alone are not authenticity.
- Source counts are not area, no JRC/Hansen grid fusion exists, and mapped classes do not create legal forest, deforestation or compliance conclusions.

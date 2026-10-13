# C2-B ingestion handoff

Completed 2026-10-13 02:30 UTC; ready for independent recheck. Owned writes only: `app/src/data.ts`, `app/checks/ingest-validation.test.mjs`, this report. No Git mutations, engine/artifact/source edits, package/type edits, browser navigation, external publication, or uploads.

## Integration

- Named exports: `validateDemo(value: unknown): Demo` and `loadDemo(signal?: AbortSignal): Promise<Demo>`. Uses the existing `Demo` type via erased type-only import. No dependencies.
- Lead has now integrated `loadDemo(controller.signal)` into App (observed read-only at 02:30 UTC). It stores data only after validation resolves, preserves the last accepted artifact on reload failure, and aborts superseded requests. AbortSignal is supported; cancellation preserves its original exception/reason. Worker did not edit App.
- One `/data/demo-v1.json` fetch with `cache: 'no-store'`, one text-body read, one JSON parse. No alternate endpoint, automatic retries, fake fallback, benchmark-file fetch, or mutable canonical-file reread. Empty, unreadable, HTTP failure, non-JSON, network failure, and invalid-schema responses throw readable errors.
- Existing `sync-data.py` declaration-only fallback is accepted explicitly: `dataset.status='declarations_only'`, period-key array, all computed plot fields null, summary and benchmark null. It cannot retain computed observations/proof. Generic pending/null plot results/comparison are also allowed without converting them to mismatch or success.

## Validation and truth boundaries

- 17 unique plot IDs, exact `supplier.a3_plot_id` join, optional `geometry_properties.ProductionPlace` exact join, all supplied values remain strings. No trimming, coercion, inferred field meanings, or regenerated supplier values.
- Nonempty Polygon rings, at least four finite two-coordinate positions, exact closure; finite north-up EPSG:4326 dataset grid. No point-in-polygon, topology validity, CRS reprojection, source-raster reads, or new geospatial engine.
- Safe nonnegative integer counts, coverage accounting, diagnostic datamask bounds, valid-land/unknown support, fixed histogram lengths/sums, all 25 annual bins, period sums, and strictly typed true/false/null signals. Partial absence remains null, partial positive remains true; water-only/no centers/no valid land remain analytically null. Missing required bands disable analytics while retaining permitted diagnostic mask counts, including zero masks for missing datamask.
- Full structural source/compact comparison, including extension fields, scalar types, arrays and nested keys. Object key order is irrelevant. Boolean equality claims need both outputs and must match actual fields. Actual differing fields must match the declared list; pending comparison makes no equality/difference claim. Result hashes are not used to decide equality.
- Native evidence geometry/values/validity/coverage are checked, including nullable outside cells and duplicate lattice IDs. Evidence coverage, diagnostic datamask counts, valid land and unknown support must match the source query. Missing-band diagnostic fixtures may retain stored raw valid cells without making an analytical answer available; global missing datamask suppresses its diagnostic counts exactly as contracted.
- Supplied receipt query version, grid, source list, product, periods and unknown reasons must match the envelope/source result. Derived cohort counts cannot manufacture selected totals, agreement, tri-state counts or supplier indication counts.
- SHA-256 fields are checked for digest syntax and internal comparison consistency only. Content/receipt SHA is **not recomputed**: engine uses Python `json.dumps(sort_keys=True,separators=(',', ':'),allow_nan=False)`, whose Unicode escaping and float serialization differ from JavaScript JSON. No guessed canonicalization, crypto requirement, signatures or authenticity claim. Self hashes do not prove source accuracy, files, full-grid fidelity, legal compliance, or archived benchmark validity.
- Benchmark content remains an opaque object/null. If present, envelope `benchmark_status.state` must be `bound_retained` when metrics exist and `not_included` when null. This validates the declared inclusion state, not its underlying proof. Deep scanning that large artifact would add cost without verifying archived files or actual measurements. Engine owns benchmark/source/code/file binding and full-grid checks (see interface proof-binding update); client acceptance is not a substitute for `engine.verify`.

## Checks

- `node --test app/checks/ingest-validation.test.mjs` — final **95 passed, 0 failed, 0 skipped** on Node 26.3.1 (initial handoff had 92). Node strips TypeScript directly; no generated JS or new tooling.
- `app/node_modules/.bin/tsc --noEmit --strict --target ES2022 --module ESNext --moduleResolution bundler --lib ES2022,DOM app/src/data.ts` — **passed**.
- `app/node_modules/.bin/tsc --noEmit --incremental false -p app/tsconfig.json` — **passed** after lead integrated the loader. Read-only typecheck; no build/sync-generated assets.
- Tests freeze each canonical/synthetic file once on startup; no data writes. Include exact `validation/ui_false_equality_repro.js` mutation, canopy-only differences, extension-field type differences, key-order independence, truthful mismatch, malformed/truthy signals, nullable pending states, all six actual engine synthetic results, missing datamask/no-center diagnostics, raw missing-band evidence retention, and valid nullable outside-cell values.
- Loader checks cover fixed endpoint/no-store/one frozen body, HTTP/empty/HTML/invalid schema/unreadable stream/network errors and fetch/body cancellation. Invalid equality never returns a `Demo`.
- Diagnostic timing: final frozen real 17-plot/1048-cell validation averaged **1.39 ms** over 25 warmed calls (initial validation was 1.09 ms before evidence consistency checks). This is local ingestion timing, not a source query, benchmark, or browser performance claim.
- Actual loopback served artifact fetched read-only with built-in Node fetch and passed `validateDemo`: **17 plots, 1048 selected cells**, content digest `9186daad50c07579369b3e918da8a7e72f86958806dce925c96f507344741add`, declared benchmark state `bound_retained`. No browser navigation or UI recheck claimed; the digest identifies this observed response, not authenticated provenance.

## Coordination and remaining integration

Read `docs/lab/validator-report.md`, `validation/ui_unknown_repro.js` and `validation/ui_false_equality_repro.js`; no validator files changed. V7's exact inconsistent equality claim rejects at `comparison.equal`. V5's valid nullable cell/result state remains nullable; rendering belongs to the lead. The original V5 repro also leaves old receipt and cohort summaries, so lead/validator should refresh those claims or explicitly null them when testing a logically consistent synthetic response.

The lead has already expanded Cell's nullable values/coverage/band validity in types.ts. Optional future type improvements: expose envelope `periods`, `benchmark_status` and `content_sha256`, and comparison `status`; no worker type changes made. Loader returns original runtime fields unchanged.

No ingestion implementation blocker. App integration is now observed and its types compile; independent browser recheck remains parent/validator-owned. Lead should retain schema checking before state replacement and continue using its separate defensive comparison and nullable-cell rendering helpers. The current browser repro for null cells must update/null receipt and cohort summary claims as described above; a valid unknown fixture must not retain contradictory computed claims.

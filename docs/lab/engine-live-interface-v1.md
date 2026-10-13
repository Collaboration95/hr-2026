# Live Hansen query API v1

Owner: engine lead. Companion to the accepted frozen17plot contract, not a replacement. Implementation task: engine-live-worker-task.md. Service is optional, local, read-only, and Hansen-only. Experience lead may build against this contract now. First implementation may refine additive metadata but must not silently rename these fields.

## Transport and lifecycle

Start `.venv-data/bin/python -B -m engine.live_server --port 8765`. Bind IPv4 `127.0.0.1` only. No host/file-path/dataset selection in requests. Default allowed browser origins are exactly `http://127.0.0.1:5173`, `http://localhost:5173`, `http://127.0.0.1:4173`, `http://localhost:4173`. CLI `--allow-origin` may add an exact HTTP loopback origin with an explicit port. Never wildcard, suffix-match, remote-host or credentialed CORS. Validate Host against localhost/127.0.0.1 and actual bound port. Requests without Origin are allowed for local CLI use. OPTIONS performs explicit preflight. No request writes files or changes supplier records.

At startup verify the accepted retained benchmark/store against current pinned source/cohort/code, decode source and compact fully, compare all raw values/masks/metadata, then keep read-only arrays in memory. The immutable in-memory snapshot is the input for all requests until restart. A later disk edit does not silently refresh it. Health describes this lifetime. No new measurement or canonical export occurs. Startup failure leaves service unavailable; never serve source-only results as agreement. Keep startup identity stable before/after loading to reject concurrent changes.

## GET /v1/health

HTTP200 JSON:

- `schema_version`: `plotline.live-health.v1`
- `status`: `ready`
- `snapshot_id`: SHA256 of the exact UTF8 `snapshot_canonical_json` string
- `snapshot`: descriptor with `query_version`, `product`, `source_metadata_sha256`, source files/hashes, native `grid` (`shape`, `crs`, `transform`), retained experiment/run/store identity+file hashes, query implementation hashes, and `full_raw_masks_equal:true`.
- `snapshot_canonical_json`: engine canonical JSON encoding of `snapshot`, permitting byte-level hash verification without cross-language float formatting assumptions.
- `limits`: `max_body_bytes:65536`, `max_vertices:512`, `max_candidate_cells:4096`, `max_selected_cells:4096`, `evidence_mode:"all_selected_cells"`.
- `periods`: `{"2021-2023":[2021,2023],"2024-2025":[2024,2025]}`.
- `lifetime`: `immutable_loaded_snapshot_until_restart`.

Snapshot identity must not include arbitrary startup time/port/request timing. Full raw/mask equality describes this loaded source/store pair, not environmental truth.

## POST /v1/query

Content-Type application/json (optional UTF8 charset). Exact request fields:

```json
{
  "schema_version": "plotline.live-request.v1",
  "request_id": "lab-1",
  "expected_snapshot_id": "<health snapshot_id>",
  "geometry": {"type":"Polygon","coordinates":[[[98.78,8.50],[98.781,8.50],[98.781,8.501],[98.78,8.501],[98.78,8.50]]]}
}
```

`request_id` is1–64ASCII letters/digits/underscore/hyphen. Snapshot mismatch gives409. Geometry must be a bare Polygon/MultiPolygon with exactly `type` and `coordinates`, finite2D numeric coordinates, longitude[-180,180], latitude[-90,90], closed rings, valid nonempty topology and at most512positions. No Feature/properties, supplier ID, missing-band simulation, arbitrary paths, buffers or alternate rules. Reject duplicate JSON keys, NaN/Infinity, invalidUTF8, unknown request fields and booleans in numeric positions.

Work budget is the bounding candidate rectangle used by the accepted selector, including its one-cell safety margin, BEFORE allocation. Compute from the original loaded affine with the same floor/ceil formula; reject above4096cells. This counts outside-chip candidates too; never clip away unknowns to meet the limit. Reuse core select_cells/evaluate, without changing their global limits or code. All accepted queries return complete evidence; oversized queries are rejected rather than silently sampled. The rectangle in this example is only a shape example, not a supplier record.

## Successful query response

HTTP200:

- `schema_version`: `plotline.live-query.v1`
- `request_id`: exact submitted string
- `request_body_sha256`: hash of exact received request bytes
- `snapshot_id`: matches health and expected request snapshot
- `query_version`: `hansen-centers.v1`
- `region_kind`: `temporary_user_geometry`
- `geometry`: exact submitted geometry, no normalization/rounding
- `geometry_sha256`: engine object_hash of that geometry
- `source_result`, `compact_result`: complete unchanged result dictionaries from interface-v1.md, including allhistograms/yearcounts, bothperiods, support and unknown reasons
- `comparison`: `{"equal":true,"differing_fields":[]}` after strict type-aware comparison; mismatch is an error, never a successful proof
- `native_grid`: the snapshot grid, chip-relative indices
- `evidence`: `{"complete":true,"selected_cell_count":N,"returned_cell_count":N,"cells":<existing evidence_cells FeatureCollection>}`. Every selected center including outside cells appears once. Same properties/footprints as frozen contract; no hidden truncation.
- `receipt`: `{"payload":{...},"canonical_json":"...","sha256":"..."}`. Hash the exact canonical_json UTF8 string; parsed content must equal payload. Payload contains request_id, request_body_sha256, snapshot_id, query_version, geometry_sha256, source_result_sha256, compact_result_sha256, evidence_sha256, boundary_rule, valid_land_rule, partial_support_rule and periods. Result/evidence hashes use engine object_hash. This is an integrity receipt, not a signature.
- `runtime`: source_query_ms, compact_query_ms, evidence_ms, total_request_ms; finite nonnegative numbers measured with perf_counter. `scope:"single_request_preloaded_arrays_no_network_or_UI"`, `benchmark:false`. Receipt generation/evidence/validation may be included only in total; query timings are separate and not a speedup claim.
- `interpretation`: `Mapped observations for a temporary geometry on a frozen local snapshot; no supplier or legal finding.`

Partial positive remains true; absent positive with unknown support remains null. No centers, water-only and outside-loaded-sample states retain the accepted contract. A successful zero-center query is distinct from an HTTP error. No supplier rows/totals or frozen receipts are recomputed/replaced by this service.

## Errors and consumer race handling

JSON error envelope: `{"schema_version":"plotline.live-error.v1","request_id":null,"error":{"code":"INVALID_JSON","message":"..."}}`. Echo request_id only after validated. Codes/statuses:400INVALID_JSON/INVALID_REQUEST,403ORIGIN_NOT_ALLOWED/HOST_NOT_ALLOWED,404NOT_FOUND,405METHOD_NOT_ALLOWED,409SNAPSHOT_MISMATCH,413BODY_TOO_LARGE,415UNSUPPORTED_MEDIA_TYPE,422INVALID_GEOMETRY/QUERY_TOO_LARGE,500COMPARISON_MISMATCH/INTERNAL_ERROR,503NOT_READY/BUSY. No tracebacks or filesystem contents in HTTP responses. Socket read timeout and bounded active query capacity prevent unlimited work; explain busy responses rather than silently queueing many requests. Connection refusal means optional service unavailable, not zero observations.

Client must keep an active request ID and the exact body string sent. Accept a response only if that ID is still current, expected snapshot matches, response geometry structurally matches the submitted geometry, and request_body_sha256 matches TextEncoder bytes of the sent body. Abort prior fetch when geometry changes; still check identity because cancellation can race. Clear or label previous results stale during edits/loading; never show an old result as the current region. Check strict result equality, complete evidence/counts, receipt canonical hash and payload bindings before displaying verified. Python object_hash formats some floats differently from JS; use provided canonical strings for receipt/snapshot hashing and exact request bytes for request binding, not an assumed JSON.stringify equivalence.

CORS origins/port configuration are local development settings, not UI controls. Keep supplier review usable when this optional service is absent. This contract adds no JRC fusion, global monitoring, storage benchmark update or compliance verdict.

## Required additive binding fields — 04:06UTC coordination

Successful query responses MUST additionally include `source_result_canonical_json`, `compact_result_canonical_json`, and `evidence_canonical_json`. Each is the exact UTF8-decodable string produced by `engine.source.canonical_bytes` for the correspondingly named returned object. Evidence means the **whole `evidence` wrapper**, including complete/count fields and the nested FeatureCollection, not only its cells. The receipt payload's source_result_sha256, compact_result_sha256 and evidence_sha256 MUST respectively hash these exact UTF8 strings.

Client acceptance requires JSON.parse(canonical_string) structurally/type-exactly equal the corresponding returned field, then SHA256(TextEncoder(canonical_string)) equal the receipt payload digest. Missing strings must fail closed as BINDING_UNAVAILABLE; a validreceiptselfhash alone does not bind result/evidence objects. An edited evidence cell with an unchanged canonical string, or an edited canonical string with an unchanged receipt digest, must reject. Do not invent a JS equivalent of Python's float serialization. These three strings are required in actualHTTPresponses, not only augmentedtestfixtures.

The implemented snapshot descriptor names are now fixed for client coordination: `sources`, `retained` (experiment_id,run_id,store_path,candidate,files), `query_implementation_sha256`, and `verified_files`, plus the grid/product/query_version/source_metadata_sha256/full_raw_masks_equal fields already specified. Source/store/code identities must agree with their verified-file entries. Keep parsed snapshot equal to snapshot_canonical_json and snapshot_id equal to its exactUTF8hash. Receipt payload remains request/body/snapshot/geometry bound as before. No query/evidence semantics or acceptedbenchmark changes.

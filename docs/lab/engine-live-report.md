# Live local Hansen backend — COMPLETE, ready for master / Volta review

W2 implemented the disjoint live backend. Earlier oracle files, existing query/source/codec/proof/export code, contracts, packaging, app, retained stores, accepted measurements and canonical artifacts were not edited. No Git mutations, agents, dependencies, downloads, publication, private uploads, or external messages.

## Additive browser hash-binding update — ready for C5-B / Volta

Implemented the exact fields requested by `experience-live-client-report.md`:

- `source_result_canonical_json`: parses to the complete `source_result`; its exact UTF-8 SHA-256 equals receipt payload `source_result_sha256`.
- `compact_result_canonical_json`: parses to the complete `compact_result`; its exact UTF-8 SHA-256 equals receipt payload `compact_result_sha256`.
- `evidence_canonical_json`: parses to the **whole evidence wrapper**, including `complete`, counts and `cells`; its exact UTF-8 SHA-256 equals receipt payload `evidence_sha256`.

The response strings and receipt digests are derived from the same cached canonical byte sequences. Existing objects, result fields, receipt fields and rules remain intact; `object_hash` equivalence is preserved. No JS/Python serializer equivalence is assumed. The engine-owned interface remains Volta's write responsibility; these names/scope are ready for its additive contract update.

Extended owned tests cover parsed-object equality with type-aware comparisons, canonical bytes and hash consistency across all17 plots plus tiny/partial/outside cases, and actual HTTP field delivery. **46 backend methods pass** (1.154 s recorded). Read-only execution of C5-B's unchanged suite passes **112/112**, explicitly reporting: “Canonical binding fields came directly from current engine implementation.” Its fixture generator no longer adds these fields.

Actual HTTP smoke still matches all17 frozen answers/evidence and confirms unchanged pinned files. The refreshed known-plot/tiny/outside HTTP response files were then accepted by C5-B's unmodified JavaScript validators: **3/3**, without field augmentation. Proof: `data/experimental/live-service/cross-language-verification.json`; reproduction helper: `verify-client.mjs` in that directory.

```sh
.venv-data/bin/python -B -m unittest engine.tests.test_live_query engine.tests.test_live_server -q
node --test --test-reporter=tap app/checks/live-client-binding.test.mjs
PYTHONPATH=. .venv-data/bin/python -B data/experimental/live-service/smoke.py
node data/experimental/live-service/verify-client.mjs
```

All exited0. Latest recorded snapshot ID is `84219023e64fad041d5b063353a8fd0cb1543802b094c28f3b6b009dc0525e06`; the fresh load observation was49.085 ms, not a benchmark. The implementation change changes snapshot identity. **Restart any already-running backend and fetch fresh health/request bindings** before browser integration; old processes keep their old implementation/snapshot lifetime. The earlier measurements below are retained as initial-delivery history. Current hashes/examples are in the refreshed owned scratch proof.

**Additive-field blocker resolved: master/Volta/C5-B may proceed with contract/UI integration.** Backend changes were confined to live_query.py, owned live tests, scratch helpers/examples and this report. Client and contract files were read-only.

## Delivered files and interfaces

- `engine/live_query.py`: `LiveSnapshot.load(root=ROOT)`, `.health()`, `.query(request: dict, request_body: bytes)`, strict `parse_request`, bounded `preflight_geometry`, reusable `LiveError`.
- `engine/live_server.py`: optional stdlib IPv4 loopback service and CLI.
- `engine/tests/test_live_query.py`: snapshot/proof/request/geometry/fidelity tests.
- `engine/tests/test_live_server.py`: real ephemeral-port HTTP/adversarial/concurrency tests.
- `data/experimental/live-service/smoke.py`: reproducible real-HTTP check and example writer.
- Owned scratch: `health-example.json`, three `*-request.json` / `*-response.json` pairs (known-plot, temporary-tiny, outside), and `verification.json`.
- This report. Lead retains contract, packaging and integration ownership.

Contract field names are unchanged. Receipt `evidence_sha256` hashes the entire response `evidence` envelope, including complete/counts/cells. Snapshot/receipt canonical strings use the engine's canonical encoding and hash the exact UTF-8 bytes.

## Run and reproduce

Run from the repository root:

```sh
.venv-data/bin/python -B -m engine.live_server --port 8765
```

Default port is **8765**; the bind address is always **127.0.0.1**. There is no host/root/store CLI or HTTP override. `--allow-origin http://localhost:9123` can add one exact HTTP loopback origin with an explicit port; it does not change the bind address.

Read health and submit the recorded local example while its expected snapshot ID remains current:

```sh
curl --silent --show-error http://127.0.0.1:8765/v1/health
curl --silent --show-error -H 'Content-Type: application/json' --data-binary @data/experimental/live-service/known-plot-request.json http://127.0.0.1:8765/v1/query
```

A later code/input change can make the recorded request stale; 409 SNAPSHOT_MISMATCH then correctly requires fetching health and forming a new request. Automated reproduction generates current example bodies:

```sh
.venv-data/bin/python -B -m unittest engine.tests.test_live_query engine.tests.test_live_server -v
PYTHONPATH=. .venv-data/bin/python -B data/experimental/live-service/smoke.py
```

Both commands exited 0. The smoke helper uses an ephemeral port and stops its listener afterward. No persistent server was left running by this worker. Its example/proof files are local scratch; the service itself never writes requests or responses.

## First working health / query and initial-delivery measurements

The first loopback check returned HTTP200 health `status=ready`, then HTTP200 for known-plot, tiny and outside queries. Final saved examples:

| Case | Selected | In coverage | Unknown | Support | Reasons |
| --- | ---: | ---: | ---: | --- | --- |
| Known plot P-0001 geometry | 121 | 121 | 0 | complete | none |
| Temporary tiny rectangle | 0 | 0 | 0 | none | no_selected_cells |
| Temporary rectangle near 0°, 0° | 1 | 0 | 1 | none | out_of_coverage, no_valid_land |

The known-plot response contains the submitted temporary geometry, complete native evidence, exact source/compact results, and a request-bound receipt. It does not inject supplier fields or classify the request as a supplier record.

**46 focused test methods passed**, 0 failures/errors/skips; the recorded suite run took **1.138 seconds**. A separate real-HTTP smoke queried **all 17 supplied geometries**, matching both frozen result dictionaries and all native evidence features: **17/17**, with **1,048 selected cells summed across plots**. Each response's body/geometry/evidence/receipt bindings were checked. This sum is not deduplicated area.

Final observed snapshot load: **29.734 ms** in one run. P-0001 example: source query **0.257 ms**, compact query **0.157 ms**, evidence **0.219 ms**, total in-process request **1.312 ms**. These are individual observations, not repeated benchmarks or speedup claims. Every runtime response states `benchmark:false` and excludes network/UI.

Final scratch proof snapshot ID:
`b27664dc52b552c23750ddd805fb62f444e392458d782277ad056e9cb76c0434`.

Implementation SHA-256:
- live_query.py: `f15aa1e5878c136535dbf696123920fff793dc72f17788dd026b9bed1de32c20`
- live_server.py: `05a6c6a0d523dbb23480f39f9d6e86640fddb3a9c7300204d55f2855d5894c2b`

## Snapshot and proof behavior

Startup uses the existing retained benchmark proof checker, verifies every current pinned source/cohort/code/measured-store/archived-run/selection input required by that proof, then fully decodes source and retained compact. Full raw arrays, masks and strictly typed metadata must match. A second proof check and before/after file hash/size comparison reject load-time changes. Current root implementation hashes must match the modules imported by this process.

The descriptor binds the retained experiment/run/store and store files, source metadata/grid/files, query implementation and verified input files. It contains no port, timestamp or request timing. Repeated loads of identical input/code produce the same snapshot ID. A copied minimal required file set loads successfully without the full source-tile cache.

Arrays are backed by immutable bytes, so ordinary writes and `setflags(write=True)` fail. Health/response metadata and request geometry are returned as detached JSON structures. A disk edit after startup deliberately does not refresh or change this snapshot; restarting after a stale input edit rejects startup. Requests do not read current disk inputs and do not recompute accepted benchmark/export artifacts.

Tests reject raw-value, mask, metadata and metadata-type mismatches; altered retained proof; changed runtime code; and edits during loading. This provides integrity and identified lifetime semantics, not a signature or protection against an adversarial process that can rewrite runtime memory/code.

## Query and transport verification

- Strict parsing rejects invalid UTF-8/JSON, duplicate keys, nonfinite constants, unknown request fields and invalid IDs. Parsed dict versus exact body comparison is type-aware; integer/float and boolean/integer substitutions cannot bind an unrelated supplied dict.
- Request/body/snapshot/geometry/result/evidence/receipt hashes and canonical-string equality are checked. Stale expected snapshots yield409. Strict source/compact differences, including boolean replaced by integer1, yield500 COMPARISON_MISMATCH without an agreement receipt.
- Geometry preflight enforces bare Polygon/MultiPolygon, finite 2D numeric geographic coordinates, no booleans, closed rings, valid topology and at most512 positions.
- The **4096 candidate rectangle** is computed with exactly the accepted original-affine floor/ceil safety margin before native-grid allocation. Outside candidates count toward the budget. Sixty seeded boundary/one-ULP probes compare preflight rectangles to actual core meshgrid dimensions. The exact4096 boundary passes; one ULP over the tested bound rejects.
- Existing core selection/evaluation/evidence functions are reused without modifying their globals. The known window-reassociation boundary witness retains original cell1:1 exactly. No buffer, tolerance change, normalization or resampling.
- All selected evidence is returned, including outside cells and raw masked values. Tiny/no-center, partial witnessed-positive, absent-with-unknown, fully outside, holes and multipart tests match the independent scalar oracle.
- HTTP uses real ephemeral127.0.0.1 ports. Exact allowed/denied Origins, Host with bound port, duplicate Host/Origin, OPTIONS origin/method/header checks, malformed/missing/duplicate Content-Length, Transfer-Encoding/chunked requests, invalid media types, forbidden routes/methods and concise JSON errors are tested.
- An actual blocked query proves that a second query receives503 BUSY at capacity while health still works. A delayed older request and a newer completed request retain their own exact request IDs/body hashes. Browser stale-result rejection remains experience/master integration work.
- Request handlers were run with Python file-open APIs forbidden; pinned files plus canonical demo/example hashes stayed unchanged. Responses contain no filesystem traceback or request-body logs.

## Bounded service limits and handoff

Default origin allowlist is exactly:
`http://127.0.0.1:5173`, `http://localhost:5173`, `http://127.0.0.1:4173`, `http://localhost:4173`.
No wildcard/credentialed CORS. Requests without Origin are allowed for local CLI use. Extra origins must be exact HTTP localhost/127.0.0.1 plus an explicit valid port, without credentials/path/query/fragment.

Limits: **65536 body bytes**, **512 positions**, **4096 candidate/selected cells**, **8 active connections**, **2 active queries**, **2-second socket read timeout**, **5-second absolute connection lifetime**. No unbounded query queue; overload returns503 BUSY. At the connection cap the server returns a minimal503 before parsing headers, so that transport-level overload reply has no Origin-specific CORS header. Idle/incomplete connections close at the tested deadlines; a peer can see connection closure when the absolute deadline prevents sending an error envelope.

HTTP is deliberately optional and read-only. It has no supplier mutation, missing-band simulation, alternate dataset/path, JRC fusion or legal decision route. A query error is not a zero-observation answer. Snapshot arrays stay fixed until restart, even if disk files change. Hash receipts establish local integrity, not authenticity/source accuracy.

**Final signal to master and Volta: LIVE BACKEND COMPLETE — ready for independent review and UI/packaging integration.** No unresolved backend blocker or contract-change request. Volta owns packaging/contracts; master/experience own proxy configuration, browser consumer validation and UI race tests. Re-run the focused suite and current smoke if the accepted contract/core changes.

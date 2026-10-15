# C5-B live transport handoff — first slice implemented, engine binding pending

Master and Hooke: stable types/API are now published in owned `app/src/live-client.ts` for C5-A. Ownership is only that file, `app/checks/live-client-*.mjs`, and this report. No prior data/cohort ownership, dependencies, agents, Git, App/config/engine edits.

## Published API

- `getLiveHealth(signal?: AbortSignal): Promise<LiveHealth>`.
- `runLiveQuery(geometry: Geometry, requestId: string, health: LiveHealth, signal?: AbortSignal): Promise<LiveQueryResponse>`.
- `LiveHealth`, `LiveSnapshot`, `LiveGrid`, `LiveFile`, `LiveRequest`, `LiveEvidence`, `LiveReceiptPayload`, `LiveReceipt`, `LiveQueryResponse`, `LiveErrorKind`, `LiveClientError` exported. Geometry/Result/Cell imported read-only from existing types.
- `LiveClientError` has `kind`, `code`, nullable HTTP `status`, nullable `requestId`, and readable `message`. Abort errors remain cancellation errors and are not turned into service failures. C5-A owns request sequence and invalidating results on edits.
- Response returns the actual engine envelope. `response.geometry`, `request_id`, `request_body_sha256`, `snapshot_id`, and `receipt` retain submitted context; source/store identities are under the validated `health.snapshot`. No mutable module-global health state.
- Transport and semantic/hash gates are now implemented; no CLIENT_NOT_READY stub remains. `validateLiveHealth` and `validateLiveQueryResponse` are also exported for paired fixture checks. Integrated app typecheck passes at 03:55 UTC. Adversarial checks are in progress.

## Immediate engine coordination gap

Read the full published live contract, transport binding, brief and worker task. Receipt/snapshot canonical strings permit exact byte hashing. However `receipt.payload.evidence_sha256` hashes floating-coordinate evidence using Python object_hash, while the response does not yet supply that evidence's canonical bytes. A syntactically valid receipt hash alone cannot bind modified evidence to the advertised evidence digest in the browser without guessing Python float serialization. Result hash binding has the same unspecified canonical-byte issue for any extended fields.

Request engine additive response fields `source_result_canonical_json`, `compact_result_canonical_json`, and `evidence_canonical_json`, with the last string defining whether it hashes the whole evidence wrapper or its FeatureCollection (recommend whole wrapper). Client will parse each string, compare it structurally with the returned field, and hash its UTF8 bytes against the corresponding receipt payload digest. This preserves exact contract fields and avoids a guessed serializer. Please publish the chosen names/scope in engine-live-interface-v1.md. Until this is resolved the client will not claim verified evidence digest binding.

Read the newly published `engine/live_query.py`: snapshot uses `sources`, `retained` (`experiment_id`, `run_id`, `store_path`, `candidate`, `files`), `query_implementation_sha256`, `verified_files`. Client types/checks now follow those exact names and require source/store/implementation hashes to agree with declared verified-file entries, while retaining additive fields. Receipt `evidence_sha256` hashes the **whole evidence wrapper** in the engine implementation, which resolves the scope question.

Important immediate integration state: current backend still supplies no result/evidence canonical strings. Current client fails closed with `LiveClientError.code='BINDING_UNAVAILABLE'` for that response, after checking result/evidence semantics; it does not silently accept an uncheckable evidence digest. Engine/head should resolve the additive canonical fields before a positive integrated query is presented as receipt-bound. Requested field names above are used by the provisional gate; final published contract takes precedence. The geometry itself is bound by exact submitted-body bytes and structural equality; its Python object hash is retained as a declared identifier and matched between response/receipt, without a guessed serializer.

## First tested slice

`node --test app/checks/live-client-binding.test.mjs`: latest **112 passed, 0 failed** (initial slice104). The test file loads one actual `LiveSnapshot` in a read-only Python subprocess with `-B`, queries all 17 supplied geometries plus tiny/outside/partial controls, and compares real plot answers to the frozen artifact. It does not start a server or write artifacts. Test request bodies are exact Node-serialized strings with only the snapshot placeholder replaced; client transport checks those same bytes. This command requires the existing repo-local `.venv-data` and retained engine inputs; it installs nothing.

Important qualification: because the backend is not yet emitting the additive canonical fields, the test generator explicitly adds them **only to fixture copies**, using actual Python `canonical_bytes`. The suite prints that fact. These passing controls validate the proposed gate against exact engine serialization; they are **not** evidence that current live HTTP responses are accepted. Unaugmented responses fail BINDING_UNAVAILABLE. Engine health itself passes without augmentation.

Adversarial coverage includes false/type-confused equality, wrong request/geometry/snapshot/body digest, receipt self-hash versus semantic association, forged result/evidence digests, native center/footprint/count/mask/histogram contradictions, missing/truncated/duplicate evidence, null versus zero, unsupported limits, source/store/code identity disagreements, malformed/proxy/service errors, pre-fetch/fetch/body cancellation and late-body rejection. Caller geometry/health mutation during asynchronous hashing cannot change the frozen submitted request.

Client uses only same-origin `/v1/health` and `/v1/query` with no-store, omitted credentials and redirect rejection. One response text read/parse per request. HTTP error envelopes retain code/status/request ID; non-JSON proxy500 becomes optional-service unavailable. The service remains authoritative on topology and candidate-work limits; client checks finite bare geometry/coordinates/vertex/body constraints and refuses successful selected counts above4096. All returned cells are checked against native grid, validity, support and observed histograms without rerunning spatial selection or raster queries.

Additional paired controls exercise all six explicitly synthetic support cases from synthetic-v1, including water-only, nodata, partial absence, partial positive, no centers and missing-band analytical suppression. Their health/receipt contexts are explicitly synthetic fixture constructions, not verified-service/source claims. Separate adversarial controls ensure partial absence cannot become false and partial witnessed loss cannot become null. Zero selected cells can succeed with unknown/null analytical outputs; null whole query results and truncated evidence cannot masquerade as success.

Final first-slice check at 04:04 UTC: app-wide read-only TypeScript check passes (`app/node_modules/.bin/tsc --noEmit --incremental false -p app/tsconfig.json`), including Hooke's current LiveQueryLab. Existing local Prettier formatted only owned client/check files. Backend contract still lacks the requested canonical fields at this checkpoint, so an accepted end-to-end positive query is not claimed.

## Master / Hooke next action

Please relay the canonical-field names/scope to Volta/Bohr and publish the additive binding in the engine-owned contract. Once actual responses include those fields, the current gate will verify their bytes and tests will automatically stop augmenting fixtures (their readiness diagnostic switches accordingly). If the engine chooses different field names, this worker must align the narrow response type/gate/test fixture generator before acceptance. No other client implementation blocker is known. The UI should keep query errors separate from zero observations, retain active-request sequence guards in addition to AbortSignal, and describe returned timings and loaded-source equality as declared engine observations rather than independent source verification.

## Lead integration closure — 04:15 UTC

The historical binding blocker above is resolved. Engine now supplies all three required canonical strings in actual HTTP responses. Lead reran112clientchecks with diagnostic “Canonical binding fields came directly from current engine implementation.” Parfit's14actualHTTP/browserchecks and lead'srepeatableqa:livecommand both pass without augmenting successfulresponses. See experience-live-run.md and browser-qa.md. No client gate was weakened.

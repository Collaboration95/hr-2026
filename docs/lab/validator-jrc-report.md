# Independent JRC v4 companion audit

**J1/J2 focused fix verification complete at04:15UTC: RESOLVED on fresh companion `c13127c9…`.** Fresh accepted positives and original transient-answer rejection, five rehashed sample/guard/child rejections, and clean46-file no-tile lifecycle all pass. First-pass REVISE history below is preserved. Canonical packaging inventory needs refresh for one changed interface document; details are appended.

Started 2026-10-13 03:29 UTC. First-pass handoff 03:39 UTC: **REVISE J1 measurement integrity and J2 ordinary-export lifecycle before companion acceptance.** Source/codec/query and targeted proof gates pass within this scope. JRC remains separate from the accepted Hansen V1–V7 fix history. No UI checks or integration acceptance are claimed.

Read actual task, interface, worker report, five jrc modules, pinned acquisition manifest/QML and source paths. QML explicitly labels 0 Non-forest with alpha0 and 1 Forest with alpha255; alpha must not determine observation validity. Native chip contract is 1809×3695 on the acquired JRC affine grid, reference2020/version4.

Early issue under targeted reproduction: the worker report claims guarded inputs/implementation and per-sample timing answer checks, but current `jrc_benchmark.py` records identity only once and `timed()` retains only the last answer. No start/end/child identity guard or per-sample digest check appears in actual code. This will be tested with a bounded, labelled transient wrong-answer control in a validator-owned experiment root; no canonical benchmark will be regenerated.

Independent source-window, pixels/masks, 17-plot queries, codec decoding, byte accounting and rehashed proof controls are underway. All writes remain under `validation/` and `docs/lab/validator-*`.

## Confirmed issues — immediate lead review

### J1 — P1: a wrong intermediate timed answer is accepted and proof-bound

`.venv-data/bin/python -B validation/jrc_timing_repro.py` exits **1** because the negative control is accepted. The second measured source-hot answer is deliberately changed from P-0001 selected=1083 to **1084**, then subsequent answers are correct. Actual `run_jrc_benchmark` finishes and writes a run; actual `validate_benchmark` accepts that run. `timed()` returns only its last answer, and the source-hot caller discards even that result. The archive's `answer_sha256` comes from the pre-timing expected answer rather than all sampled answers.

This is a bounded synthetic measurement-integrity repro in `validation/jrc/transient-timing-repro`, not a claim that the existing canonical samples were observed wrong. Actual source/encode/decode/hot loops execute; existing valid cold records are replayed to keep this negative test bounded and are explicitly labelled non-measurement evidence. No canonical archive or source is changed. Evidence: `validator-jrc-timing-repro.json`.

Fix: compare every warmup/measured query result to pinned expected output and archive per-sample digests (or enforce per-call equality); similarly validate repeated loads/decodes rather than just the last returned dataset. Add start/end and child source/code/store guards as requested in the task. Current code has none, despite the worker report's guard claim. The fresh canonical positive and all independently recomputed source/codec/query results pass; this finding concerns the measured-work guarantee.

### J2 — P2: ordinary export still requires full source cache and reruns measurement

A validator-owned minimal bundle with required chip/provenance/QML/XML, exact plot inputs, code, all stores and benchmark archive successfully supports **explicit benchmark export → verify** with `full_source_cache_present=false`. Calling ordinary `export_jrc(output=..., root=minimal)` on that same valid bundle fails with missing `JRC_GFC2020_V4_N10_E90.tif`: it unconditionally starts `run_jrc_benchmark` and `check_source_readback` when no store/benchmark argument is supplied. The CLI exposes no stored-benchmark reuse option. This reproduces the outstanding operational gate in `engine-jrc-task.md`.

Expected ordinary regeneration to reuse the accepted companion/measurement without the optional197MB cache or new timing timestamp. Explicit measurement may require that cache. Evidence is in `validator-jrc-proof-controls.json`, keys `minimal_explicit_positive` and `ordinary_export_without_full_cache`. All minimal-bundle files are copies under owned validation paths; the real source cache was preserved.

## Independent positive evidence so far

`validation/check_jrc.py` passes without importing production JRC query/codec/oracle/proof helpers. Full original tile/chip hashes and window pixels/masks match; native grid1809×3695 and step1/12000degree match. All6684255 masks are valid, and QML code0 remains known. Exact scalar membership/reduction reproduces all17queries,9511selected centers,8957class0 and554class1 cells; every evidence record matches. All8candidate stores independently decode every raw pixel/mask/metadata exactly, including selected21459-byte packedlevel19 store.

Actual required baseline sums to57653bytes. Keeping identical11415-byte provenance/QML/XML alongside compact gives32874bytes; including19265 common plot bytes yields76918source versus52139compact. No crop savings or Hansen count/area equivalence is used. Fresh measured export equals canonical and is accepted; a fresh metric-free export is accepted too. Targeted rehashed source/geometry/cohort/type/receipt/summary/store/benchmark negative controls are being finalized, with no accepted false artifact found so far.

## Completed proof/unknown controls and handoff

All **20 targeted rehashed artifact controls reject**, paired with current accepted measured and metric-free positives. Covered altered reference/version, plot geometry with refreshed geometry hashes, removed cohort member, source class/flag changes, summary totals, receipt query/reference/full-mask claims, benchmark cohort/vintage/bytes/timing, and separate off-plot raw/mask stores. Boolean/integer controls include `0→false`, `true→1`, and summary one→true. Canonical JSON comparisons reject those type differences. Evidence changes with refreshed receipt hashes are rejected at independently recomputed receipt/evidence binding; no unrehashed outer-hash failure is being counted as the semantic check.

Off-plot witness is row0/col0, originally raw0/validtrue and outside all17plot selections. Raw toggle and mask toggle fail explicitly at full-chip raw/mask comparison before benchmark identity checks. Fresh minimal-bundle verification reports full source cache absent and still passes. Only default ordinary regeneration fails, as J2 describes.

`validation/jrc_unknown_checks.py` passes **168 synthetic checks** using independent expected results: all16mask patterns over a2×2binary fixture, missing-band true/false, complete/partial/outside/no-center polygons, valid transparent0, native JRC one-ULP boundary inclusion/exclusion, and all4codecs preserving raw1 under invalid masks. These are separate from the real17plot evidence. The exact pinned XML hash, old2023/2025dates and requiredcitation were independently checked against the artifact;2020reference andv4 are kept distinct from Hansen's2025release.

### Measurement scope assessment

Normal source-load and compact-decode timings both load the full identical JRC chip and include their respective loader validation; hot queries use preloaded arrays on both sides. Process-cold inner timing includes load+17queries after imports/commonplotload, while spawn-inclusive time includes process startup. Warm/uncontrolled OS cache and whole-child RSS are explicitly disclosed. Stored min/median/p95 values independently recompute; p95 uses NumPy's linear interpolation (not Hansen's nearest-rank method), which should be named in the JRC method metadata. The major blocker is J1's missing per-sample answer/identity checks, not an observed timing arithmetic error. No new broad speedup claim is supported here.

Current storage comparison is against the supplied native DEFLATE chip and the listed custom candidates. It establishes no custom-over-all-standard-formats optimum. Lead's03:32review independently confirms J2 and requests both lifecycle/race gates; a separate stronger standard-format study is pending. That pending study is not treated as accepted evidence or mixed into these metrics.

### Reproduction and exact audited artifact

```sh
.venv-data/bin/python -B validation/check_jrc.py
.venv-data/bin/python -B validation/jrc_proof_controls.py
.venv-data/bin/python -B validation/jrc_unknown_checks.py
.venv-data/bin/python -B validation/jrc_timing_repro.py
```

First three exit **0** (independent source/codec/query checks, positive/negative artifact gate controls, synthetic unknown checks). Last exits **1** while a deliberately wrong timed answer is accepted; this is the reproduced J1 defect. The proof-controls JSON separately records J2's expected ordinary-export failure without full cache; its `proof_controls_pass` field concerns the positive/negative evidence gates, not lifecycle acceptance.

Audited artifact content: `f774b5c569c9cac0dc6b9b0e4e7ce2e8d19611b9e339e0beb1c183c87a1b2475`; experiment `exp-b5ab7c4c4db8cf855d03ce3744ffc5ec905ab287b66097f5fb7e2f6ffa8886d4`; run `run-764fcd1a3d1e1e90f105205a9d52b8b898b8a0ed9ff48ace84065eb894862c8f`. These are the pre-fix bindings, not a claim to verify a later refreshed measurement.

Reports: `validator-jrc-independent.json`, `validator-jrc-proof-controls.json`, `validator-jrc-unknown.json`, `validator-jrc-timing-repro.json`. Only owned validation/report paths were written; inputs, accepted Hansen artifacts, JRC canonical files, engine/app/package files and Git state were preserved. No browser, upload, acquisition rerun or external publishing was performed. Ready for parent relay and focused positive/negative recheck after JRC worker fixes.

## J1/J2 fix confirmation — fresh positives, original attack, clean lifecycle

Current companion content `c13127c9f6d8654a1dae0d66945c981bfc340b20467124dd2e55829d79d754a3`, experiment `exp-bfd3067040ae3fb83331667fba2ece195e9372893c81ac1930edbdfc68444f3a`, run `run-5b318b210c244c60458942f67281a8abc6f8ebcc2b3949effc12feb3013cd261` is accepted by the actual verifier. Fresh ordinary export to owned scratch is **byte-identical** to canonical. `run_jrc_benchmark` was patched to raise if ordinary export called it; no call occurred.

**J1:** Original `jrc_timing_repro.py` mutation still changes P-0001's second measured answer from1083to1084, then would return correct later answers. New runner rejects immediately with **JRC timed result mismatch at sample 2**; no run archive is produced. This paired positive/negative result is not stale-artifact rejection. Actual implementation now checks every warmup/sample result and guards outside inner timers. Five additional controls modify warmup result hash, intermediate result hash, intermediate decode guard, cold child answer and cold warmup guard, rebuilding both archive and artifact/receipt hashes. All reject at intermediate timing or child result/guard checks.

**J2:** Generated a current package inventory only under `validation/jrc-fix/current-bundle-manifest.json`, copied exactly **46files**, confirmed the197739699-byte full tile absent, then ran fresh-process CLI **verify → ordinary export → verify**. All three exit0. Every file hash/count remains unchanged, no new files/runs appear, and artifact measurement timestamp/run identity is retained. This tests the actual ordinary CLI route, not merely explicit `store/benchmark` arguments.

Independent current source/window/pixels/masks, all17queries and all8candidate decodes also still pass. Selected21459bytes and symmetric source/compact support accounting are unchanged. First-pass standalone independent implementation was rerun against the new artifact without adopting production verifier/oracle outputs as expected values.

Actual commands (all exit0):

```sh
.venv-data/bin/python -B validation/jrc_timing_repro.py --scratch validation/jrc-fix/transient --report docs/lab/validator-jrc-fix-timing.json
.venv-data/bin/python -B validation/check_jrc.py --report docs/lab/validator-jrc-fix-independent.json
.venv-data/bin/python -B validation/jrc_fix_verification.py
```

Results: `validator-jrc-fix-timing.json`, `validator-jrc-fix-independent.json`, `validator-jrc-fix-verification.json`. Original J1/J2 evidence was preserved with alternate report/scratch paths. No canonical/engine/research/source file was written by the validator.

**Remaining packaging action (not J1/J2):** the existing canonical `artifacts/jrc-bundle-manifest.json` was stale only for `docs/lab/engine-jrc-interface.md`. It correctly stopped an exact-inventory copy at the mismatched hash. The owned freshly generated inventory passes all lifecycle checks. Lead should regenerate the canonical inventory after documentation settles; validator did not overwrite it. JRC UI remains outside this audit.

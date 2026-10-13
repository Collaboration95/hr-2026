# Independent validator — first pass

**Focused fix verification complete (02:33–02:41 UTC): V1–V7 RESOLVED in the checked current export/runtime.** Fresh retained and metric-free positive controls are accepted; forgeries fail for their specific defects. The final section below records binding IDs, runtime evidence and commands. First-pass findings and their original REVISE decision remain below as historical evidence.

Started 2026-10-13 02:17 UTC. First-pass handoff 02:25 UTC. **REVISE evidence gates before final acceptance**; current source/codec/query correctness passed within the independently tested scope. No final all-layer pass is claimed.

Scope: source → codec → plot query → benchmark → export → frontend. Owned writes are limited to `validation/` and `docs/lab/validator-*`. Existing source data, canonical artifacts, package files, and Git state will be preserved.

Method: independently reconstruct source support and query counts, challenge unknown handling and input validation with bounded fixtures, inspect benchmark work/storage accounting, and compare served UI data against canonical artifacts. Passing existing tests is supporting evidence only.

## Confirmed findings — available for immediate lead review

### V1 — P1: export and verification accept an unrelated/false benchmark

`engine/export.py` copies `artifacts/benchmark-v1.json` into a newly generated proof without binding it to the source metadata, source/query hashes, actual store files, or immutable registered run. `engine/verify.py` does not inspect `benchmark` at all.

Bounded reproducer: `.venv-data/bin/python -B validation/repro_proof_gaps.py` (exit **1** deliberately means invalid proof accepted). The script writes only owned validation fixtures and the validator JSON report. A benchmark with `identity.queries_sha256` replaced by 64 zeros, source product changed to `WRONG SOURCE VINTAGE — VALIDATOR FIXTURE`, and baseline `total_bytes=1` was accepted by both export and `verify_artifact`. Expected rejection or explicit unavailable/unbound benchmark. Actual verifier result: `valid=true`, no failures, 17 compact plots.

This is a concrete evidence gate issue, not a claim of malicious authentication bypass. Self hashes can be recomputed; semantic checks must bind the claims to actual inputs and archived measurements. The normal benchmark runner has stronger guards; export currently bypasses them. Lead should validate benchmark identity/input/query bindings and archive/file evidence at export/verification, or clearly quarantine historical/unbound metrics.

### V2 — P1: verifier accepts a false full-pixel round-trip claim

The same repro encodes a separate **owned** store with just canopy cell `(0,0)` changed from **85 → 86**. That cell belongs to none of the 17 plots, so all plot queries still match. Receipts point to the actual new file hashes and advertise `raw_bands_equal=true`. `verify_artifact` returns **valid=true**: it decodes/checks file integrity and requeries plots, but never compares the decoded full arrays/masks against source or checks the receipt's raw fidelity booleans. The normal exporter correctly rejects this store with `compact store failed full raw-value or mask fidelity`.

Expected verifier rejection of the false full-pixel evidence. Recompute full-array/mask equality once per cached store and validate the advertised booleans. This does not establish corruption in any canonical store; independently checked canonical stores round-trip exactly.

### V3 — P2: receipt contract/period and support-summary claims are not verified

The repro replaces every receipt query version with `wrong-query.v99`, receipt observed periods with `[2099,2099]`, and summary selected count with **1** instead of **1048**, then recomputes receipt/content hashes. Verification still returns **valid=true**. Expected rejection because these claims disagree with the executed frozen query. Validate receipt constants, source/supplier file lists, observed periods, and all derived summaries rather than accepting a matching self hash.

### V4 — P2 integration freshness gap, not yet a final failure

At first check, the served app matches canonical **demo** bytes, but its embedded benchmark is `exp-8ae93e…` while canonical benchmark is `exp-73e498…`. Five embedded implementation fingerprints differ from current files (`benchmark.py`, `codecs.py`, `experiments.py`, `query.py`, `source.py`). The earlier embedded separate-band candidate is **786400 bytes**, rather than the later reported best sweep's **592190 bytes**. UI says frozen experiment, which is honest about static data, but final integration should deliberately select/refresh one bound benchmark/store and expose its experiment identity/freshness. Leads are still iterating; this is not treated as a final regression yet.

## Independent checks completed

`.venv-data/bin/python -B validation/run_checks.py` passed. The standalone implementation imports no engine query/selection/reduction/codec helpers. It independently hashes **all three full original source tiles**, reads their acquisition windows, and compares every chip pixel and validity bit. Full histograms and original-window transforms match provenance.

Independent exact scalar ray casting (Fraction arithmetic on binary floats) plus scalar reductions reproduce **all 17 complete result dictionaries**, **1048 selected centers**, period counts, and native evidence selection, raw values, masks, centers and cell footprints. All examined encoded candidates decode independently to **2234196 raw values** plus masks/metadata with zero differences. Baseline/candidate stored byte sums, measured file hashes, timed answer digests and timing statistics also check out. Six synthetic unknown cases independently match the v1 contract. The original source data remains unchanged.

Evidence: `docs/lab/validator-checks.json` and `docs/lab/validator-proof-gaps.json`. Browser adversarial checks used validator-owned `tab_k` and owned fixtures. No final all-layer pass verdict is claimed while confirmed evidence-gate issues remain.

### V5 — P2: null cell values become absence in table, tooltip and inspector

Confirmed live on validator-owned `tab_k`, with an explicitly synthetic one-cell out-of-coverage fixture injected only into that tab's fetch response. `lossyear=null`, all validity bits false, unknown count=1. The period cards correctly show **Mapped result unknown**, but the cell table says **None mapped**, SVG tooltip says **loss none mapped**, and inspector says **Loss year: No mapped event**. Canopy/mask render empty values (`%` and `Datamask: · not valid land`). This contradicts the promised unknown semantics at the cell-inspection layer. All 17 current real plots have known support, so this does not alter today's real-cohort counts.

Repro: `validation/ui_unknown_repro.js`; then Commands → Reload local evidence → open native-cell table → Show on map. Expected Unknown/Unavailable when a field is null or its band validity is false; known raw zero can say no mapped event. Fix the truthiness checks in `app/src/App.tsx` and `app/src/CellTable.tsx`, and represent nullable values and band validity/coverage in frontend types. Actual browser text is retained in `docs/lab/validator-ui-unknown.json`. Tab was restored to real data afterward; no shared tab or app asset was changed.

### V6 — P2: source storage denominator includes an unused duplicate manifest

The source benchmark counts generated `source_geotiff/metadata.json` (**948 bytes**) as required storage. `load_source/open_sources` never opens this file: it loads the three TIFFs and acquisition provenance, deriving metadata itself. Necessary inputs total **585293 bytes**, while reported baseline is **586241 bytes**. Count this manifest as optional/export overhead separately or make it a genuinely required input, consistently with the stated every-file-needed method. This modest **0.16%** overstatement does not reverse any examined candidate's loss to source; no severity inflation or fabricated compression-win claim is attached.

Supplemental production suite run: **69 tests passed**, using project-local `validation/tmp` and suppressed bytecode writes. Command: `env TMPDIR="$PWD/validation/tmp" PYTHONDONTWRITEBYTECODE=1 .venv-data/bin/python -B -m unittest engine.tests.test_codecs engine.tests.test_indexed engine.tests.test_query_oracle engine.tests.test_adversarial`. Independent checks above provide the correctness evidence beyond those existing assertions.

### V7 — P1: UI accepts contradictory encoding proof as success

`App.load` checks only schema and nonempty plots. Proof status and cohort matches use `comparison.equal` directly. In a validator-only corrupted response, P-0003 original 2023 count stays **0**, compact count becomes **1** (histogram/period consistently changed), and the advertised equality flag stays true. Live UI displays **Same query outputs**, **Exact output equality for this plot**, and **17 / 17 plots with measured matching outputs**, immediately above a table showing original **0** versus compact **1**. Expected rejection/mismatch; actual false success is recorded in `docs/lab/validator-ui-false-equality.json`.

Repro: `validation/ui_false_equality_repro.js`, then Commands → Reload local evidence → Show proof. This is an explicitly invalid fixture, not a claim that current canonical outputs differ. The existing Node contract checker rejects this condition, but it is only an offline test and is not used by either runtime loading or the schema/length-only sync script. Validate incoming contract/equality before replacing loaded state; compute proof/cohort status from validated outputs rather than trusting the flag. Browser was restored afterward.

Actual offline contrast check: `node app/scripts/browser-check.mjs --file validation/repro-proof/ui-false-equality.json` exits **1**, correctly identifying advertised equality versus different outputs. `node app/scripts/browser-check.mjs --file validation/repro-proof/wrong-benchmark.json` exits **0**, so the benchmark evidence gate remains absent in that checker too.

## Additional bounded adversarial evidence

`.venv-data/bin/python -B validation/adversarial_checks.py` passed **196 checks**: 180 seeded native-decimal-grid geometries/masks/missing-band combinations, 6 exact one-ULP/winding cases, and 10 compressed/parser probes. Scalar expected results independently agree with both production full evaluation and global-lattice indexed reduction (via a synthetic reader). Rectangles, holes and disjoint multipart islands are included. This verifies indexed reduction/selection semantics; the earlier 69-test suite additionally exercises the actual TIFF/compact reader implementations.

Compressed checks use only tiny frames/stores and at most a 64KiB actual decompressed fixture. Oversized *advertised* history (1GiB), concatenated/trailing/truncated frames, unknown frame size, self-checksummed trillion-cell/raw-size declarations and duplicate JSON keys were all rejected. No stress allocation or machine-destructive test was run. No further codec/query correctness bug was found in this bounded scope. Details: `docs/lab/validator-adversarial.json`.

## Lead handoff and follow-up

- **Engine priority:** V1 benchmark export/verification binding, V2 actual full-array/mask verification, V3 receipt/summary semantic verification. V6 accounting correction is small and should be documented accurately.
- **Experience priority:** V7 runtime false-success gate and V5 nullable/masked cell rendering. V4 final deliberate benchmark/store freeze and canonical-to-served freshness remains an integration checkpoint. The 02:22 experience report acknowledges V4 and is delegating a robust loader.
- Reproduce proof-gate gaps with `.venv-data/bin/python -B validation/repro_proof_gaps.py`. Its expected current **exit 1** denotes accepted invalid evidence; after fixes all negative fixtures should reject and exit **0**. It tolerates explicit verifier rejection exceptions. Original source/store bytes are never changed.
- Recheck independent positive evidence with `.venv-data/bin/python -B validation/run_checks.py`, and bounded adverse conditions with `.venv-data/bin/python -B validation/adversarial_checks.py`. Both expected **exit 0**. `run_checks.py --artifact PATH` can check a deliberately selected newer canonical export. Browser JS repros are isolated to the validator tab and reset on reload.
- The scripts currently cover the real cohort and six synthetic unknown states, four embedded first-pass encoding candidates, full-array/metadata fidelity, accounting/digests/statistics, exact native selection, and bounded compressed-input rejection. New level9/19 retained configurations should be independently decoded once the lead exports them. Window benchmark timing, broader global data, arbitrary geometry exhaustion and application-wide accessibility remain outside this first pass. Existing documented center-sampling and selected-chunk-only integrity limits are not classified as bugs.

Only `validation/` and `docs/lab/validator-*` were written. No source, engine/app, canonical artifact, package, Git, shared-tab, external publication/upload or cloud changes were made. The synthetic browser responses were removed and `tab_k` restored to real data. Report is ready for parent relay; validator is ready for focused fix verification.

## Focused fix verification — resolved evidence

The corrected retained measurement was available when this pass began. This verdict is **not** based on rejection of stale exports: a newly generated export in `validation/fix-verification/positive/demo-v1.json` is accepted by the current verifier and equals the current canonical demo exactly. A separate current-store metric-free export is also accepted. All 12 targeted negative controls reject for their specific altered claims. No canonical artifacts were regenerated by this validator.

| Finding | Resolution evidence |
| --- | --- |
| V1 | Fresh retained benchmark/export accepted. Separate wrong-vintage and wrong-cohort controls reject as source metadata/query cohort errors; altered measured bytes reject as archive mismatch. Upstream exporter itself rejects a wrong benchmark body injected only into the process's read, while all normal paths remain available. |
| V2 | Both a changed off-plot canopy value and an off-plot validity bit reject as actual full raw-value/full mask mismatches. These controls omit benchmark claims deliberately, so a non-retained path rejection cannot mask missing pixel verification. Both modified stores also fail export's raw/mask gate. Valid metric-free store/export accepted. |
| V3 | Individually altered receipt query version, receipt period, receipt source hash and summary total all reject. The source-hash case changes only one receipt and fails specifically at that receipt's contract/source/hash check. Fresh unaltered receipt/summary accepted. |
| V4 | Canonical demo, fresh validator export and loopback served JSON share content `d22b0cac287de0d12b1ecfdcf114aa549a886b86299ca8cd43384c6ff2e075b2`. Embedded benchmark equals current canonical benchmark, selected store matches explicit retention, and no measured implementation fingerprint differs from live files. Live proof shows 0/0 for P-0003 in 2023, 17/17 cohort equality, and current level19 storage choice. |
| V5 | Original V5 mutation is now inconsistent with the stronger loader because it leaves obsolete receipt/summary claims. A corrected, logically consistent synthetic outside-cell fixture updates geometry/footprint/counts/comparison/summary and explicitly omits benchmark claims. Loader accepts it. Actual browser table, SVG tooltip and open inspector all say **Unavailable** for null canopy/loss/mask; period cards remain **Mapped result unknown**. Restoring the real artifact through normal reload succeeds with 87 known P-0003 cells and no stale inspected cell. |
| V6 | Actual required baseline files are the three TIFFs (**576999**) plus acquisition provenance (**8294**), totaling **585293 bytes**. The **948-byte** generated duplicate manifest exists and matches `research_overhead`, explicitly excluded from required totals and ratios. |
| V7 | Exact original false-equality mutation rejects in `validateDemo` and actual live reload at `plots[1].comparison.equal`. The UI shows a reload rejection and retains the previously accepted real 0-event state. The consistent unknown response and later restored real export both load successfully; this is not blanket rejection. |

Retained experiment: `exp-0109a8d6c4782217871315b92c63a971d11ebd164585c80981f24c55b4f68fea`; run: `run-71a5b90b05bdce363044d8e232ae33d20b31f3868a6f5ba50bf61372b98194a9`. Selected store is `separate_zstd_l19`, chunk1024, **535012 bytes**, a **50281-byte / 8.59%** storage reduction against required original inputs. Level3, level9 and level19 candidates in this retained experiment were all independently decoded using validator code, with **2234196 raw values** plus masks and metadata matching original source per store. Original full-tile/window hashes/pixels, 17 independent scalar queries, 1048 selected centers, measured-file accounting and timing answer digests remain exact. This makes no additional hot-speed or disk-cold claim.

Actual focused commands (all exit **0**):

```sh
.venv-data/bin/python -B validation/verify_fixes.py
.venv-data/bin/python -B validation/repro_proof_gaps.py --output-dir validation/fix-verification/original-repros --report docs/lab/validator-fix-original-repros.json
.venv-data/bin/python -B validation/run_checks.py --output docs/lab/validator-fix-independent.json
node validation/verify_ui_fixes.mjs
```

The original reproducer now supports alternate output/report paths so its first-pass evidence is preserved. `verify_fixes.py` supplies fresh positive controls and isolates each failure; it also checks input implementation/artifact stability during the run. Browser checks used only `tab_k` after T3 status/open. Synthetic overrides were removed; tab is left on the real current proof.

Evidence files: `validator-fix-engine.json` (fresh positives and individual rejection reasons), `validator-fix-original-repros.json` (original attacks), `validator-fix-independent.json` (independent source/codec/query/accounting), `validator-fix-loader.json` (paired loader/helper controls), `validator-fix-ui.json` (live negative/unknown states), `validator-fix-ui-positive.json` (restored real proof and current benchmark).

No remaining V1–V7 waiting condition or concrete unresolved defect was found in this focused pass. Scope is these fixes/current retained cohort, not an exhaustive new application audit. Frontend hashes still do not authenticate sources or prove archive correctness; those bindings were checked against actual local engine evidence. First-pass limits on broader data, arbitrary geometries and application-wide accessibility remain unchanged.

## Separate JRC companion audit — 03:39 UTC

Hansen V1–V7 remain resolved. The new, separately owned JRC2020v4 companion has an independent report in [validator-jrc-report.md](validator-jrc-report.md). Source/window/codec/query and20rehashed proof controls pass with fresh positives, but JRC acceptance needs two fixes: a wrong intermediate timed answer is accepted by runner and benchmark proof (J1), and ordinary export reruns measurement/requires the optional fulltile despite a valid minimal retained bundle (J2). JRC UI is not assessed or assumed integrated. This finding does not alter accepted Hansen results.

## Latest independent checkpoint — 04:15 UTC

JRC J1/J2 above are now **resolved** against fresh companion `c13127c9…`: original transient-answer attack rejects at sample2, five rebuilt sample/guard/child forgeries reject, and46-file verify→ordinary export→verify preserves every byte without the full tile or remeasurement. Canonical package inventory needs refresh for the edited JRC interface document; owned current inventory passes. See the appended fix evidence in `validator-jrc-report.md`.

Independent strong-control/source/masks/storage and exact-rational spatial sensitivity checks pass. Allfive changedflags and15witnesses are reproduced; productioncenterquery remains unchanged. Strong-control actual measured-answer checks reject transient failures acrossallfourrepresentations/full+indexed, but its **known pending Volta/W3 verifier revision** is independently confirmed with six rehashed type/count/bounds/settings inconsistencies accepted. See `validator-strong-spatial-report.md`. No new tuning or production mutation was performed; focused fresh-W3 verification awaits that revision.

# W2 independent query oracle — COMPLETE, ready for lead review

Implemented only W2 owned modules/tests/report and W2 scratch. No core or other-worker file edits, Git mutations, source-data changes, uploads, external publication/messages, dependency installation, or hidden agent runtimes. No fast-mode toggle is exposed or claimed.

## Cycle 2 — original-lattice boundary regression complete

Read `docs/lab/engine-review-notes.md` and the lead's immutable `data/experimental/lead/window-origin-witness.json`. Added four focused tests in `engine/tests/test_adversarial.py`, class `TestWindowOriginRegression`; the witness's exact values are copied into the test so this regression also runs without ignored lead scratch. No oracle algorithm, core, codec, indexed path, or witness edits. No tolerance relaxation, snapping, or geometry buffer.

Concrete independent proof at native row 1 / column 1:

| Measurement | Original lattice | Reassociated window |
| --- | --- | --- |
| X expression | `c + a * (col + 0.5)` | `(c + a * col) + a * 0.5` |
| X decimal | `98.772625` | `98.77262499999999` |
| X exact binary-float representation | `0x1.8b172b020c49cp+6` | `0x1.8b172b020c49bp+6` |
| Y | `8.581625` | `8.581625` |
| Scalar ring membership | boundary, covered | strictly outside |
| Selected cells | 1 | 0 |

The X difference is **exactly one ULP: 1.4210854715202004e-14 degrees**. Scalar enumeration identifies the original selected cell as `(1,1)`. The synthetic 2×2 fixture puts raw `[canopy=100, loss=25, datamask=1]` at that cell; its 1×1 window preserves every band value and validity bit exactly. The original result is complete with one observed 2024–2025 event and `mapped_loss_present=true`. Re-evaluating the window transform produces zero selected cells, no support, and a null event answer. Thus equality of decoded pixels does not establish equality of a query recomputed on a shifted transform.

The additional one-ULP boundary test asserts original/window selected counts `(1,1)`, `(1,0)`, `(0,0)` when the left polygon edge is respectively one ULP left of, equal to, or one ULP right of the original center. Both ring windings are tested. Approximate equality or a buffer admitting the one-ULP-outside point fails these assertions.

The actual source check independently preserves the same native cell, whose raw values are `[85,0,1]` with all three masks valid: selected=1, valid land=1, canopy histogram bin 85=1, loss histogram bin 0=1, unknown=0, support=complete. This is a constructed boundary query against the real source, separate from the 17 supplied geometries. Full-result oracle/core equality is checked throughout, including the original and deliberately reassociated synthetic paths.

Commands from the repository root:

```sh
.venv-data/bin/python -B -m unittest engine.tests.test_adversarial.TestWindowOriginRegression -v
.venv-data/bin/python -B -m data.experimental.w2.cycle2_window_regression
```

Both exited 0. Focused run: **4/4 methods passed**. Complete W2 suite: **45 methods, 0 failures/errors/skips**, **239.40 ms** wall time for one correctness run. The complete suite includes the existing 360 seeded fixtures, 144 exhaustive cases, and all 17 supplied-plot comparisons. This timing is not a performance claim.

Reproducible proof is in `data/experimental/w2/cycle2-verification.json`; its runner is `cycle2_window_regression.py` in the same W2 scratch directory. Cycle-1 evidence was retained. The runner verifies that the frozen fixture matches the lead's witness, and confirms witness bytes and query/oracle/test implementation hashes were unchanged during the run. Witness SHA-256 remains `f3e2386ebae72e130254117bd2196c965246d7e0d44f8c47029f7ab0fa2af2ed`.

**Cycle-2 final signal: W2 COMPLETE, ready for lead review.** No indexed-query API is exercised or claimed verified here. Lead integration should select original global centers once, fetch corresponding raw cells by index/offset, and compare the indexed result against the full original-dataset oracle result for this witness. The intentionally incorrect shifted-transform query must remain different; merging its result through a tolerance would hide the bug.

## Paths and interface

- `engine/oracle.py`: `oracle_evaluate(dataset: Dataset, geometry: dict, missing_bands: tuple[str, ...] = ()) -> dict`.
- `engine/tests/test_query_oracle.py`: golden results, contract invariants, seeded differential cases, exhaustive masks/classes/events, and 17 supplied plots.
- `engine/tests/test_adversarial.py`: malformed geometry rejection, geometry/grid/work limits, boundary cases, and input validation.
- `data/experimental/w2/verify_oracle.py`: reproducible local verification runner.
- `data/experimental/w2/verification.json`: measured outcome, per-plot comparisons, source/implementation SHA-256 hashes, environment, and limitations. This is W2 scratch evidence, not the canonical benchmark registry.

The oracle imports only Dataset/BAND_NAMES from the engine, with no core query/selection/reduction helpers. Cell membership uses independent scalar ray casting and on-segment checks. Aggregation uses scalar counters and lists. GEOS validates input topology only; it does not select cells. Topology validation is therefore shared, while membership and reduction are independently implemented.

Implemented exact result keys, outside-chip selection, holes, multipart islands, exterior/hole boundaries, unknown union, mask diagnostics, years 0–25, histograms, yearly counts, period tri-state flags, and deterministic reason order. Simulated absent bands are globally invalid; absent datamask removes its diagnostic counts.

Membership uses no geometric buffer or snapping. Orientation checks near cancellation fall back to exact Fraction arithmetic on binary floating-point inputs. The threshold selects arithmetic, not geometric inclusion. Tests include representable dyadic coordinates, one-ULP neighbors, and the native 0.00025-degree decimal grid.

Oracle work limits: 2,000,000 candidate cells and 10,000 vertices, rejected before scanning. They are intentionally lower than the core's 10,000,000-cell/100,000-vertex limits. Output equivalence is tested within the oracle limits; acceptance limits need not match.

## Exact reproduction commands

From `/Users/speedpowermac/Documents/projects/CODE_MAIN/personal/hack_roll`:

```sh
.venv-data/bin/python -B -m unittest engine.tests.test_query_oracle engine.tests.test_adversarial -v
.venv-data/bin/python -B -m data.experimental.w2.verify_oracle
```

Both exited 0. The second writes only W2 scratch verification.json. It hashes implementation/interface files before and after verification and fails if they change during the run. Subsequent runs refresh this scratch evidence. `-B` suppresses bytecode writes.

Environment: Python 3.14.7, NumPy 2.5.4, Shapely 2.1.2, macOS 26.6.2 arm64. No packages added.

## Cycle 1 actual measurements

Recorded verification: **41 test methods; 0 failures, 0 errors, 0 skips**. Suite wall time **191.75 ms**. An additional 17-plot oracle/core comparison took **7.93 ms**. These are single correctness-run durations, not comparative throughput/speedup claims. W2 makes no codec storage or performance claims.

Synthetic evidence is separate from real observations:

- **360 seeded randomized fixtures:** 240 dyadic-grid fixtures with seed `20261013`; 120 native decimal-grid/one-ULP fixtures with seed `20261014`. Rectangles, holes, multipart islands, triangles, outside coverage, masks, full raw band ranges, and missing-band simulation.
- **144 exhaustive single-cell fixtures:** 8 band-validity combinations × 3 datamask classes × 6 event values (0, 20, 21, 23, 24, 25). Direct expected counts/reasons plus differential checks.
- **22 malformed geometries:** bad/unsupported types, missing/empty coordinates, unclosed/short/self-crossing/zero-area rings, nonfinite/non-numeric/boolean/3D positions, outside holes, and overlapping islands. Both implementations reject with ValueError.
- Additional golden cases: every year 0–25, canopy 0/100, zero centers, exterior/diagonal/hole boundaries, islands touching at a point, concavity, every missing-band subset, all applicable reasons in order, invalid raw values even when masked, grid restrictions, oversized windows, and nonmutation.

Actual data: **17/17 plots match every result field**, zero mismatches. Dataset shape is **height 604 × width 1233**, bands `[3,604,1233]`. All real plots have complete selected support and zero unknown cells. Selected sum is **1,048 across plots**, not deduplicated area. Counts are native centers, never hectares.

| Plot | Selected / valid land | Observed loss 2021–2023 | Observed loss 2024–2025 |
| --- | ---: | ---: | ---: |
| P-0001 | 121 | 38 | 0 |
| P-0003 | 87 | 0 | 0 |
| P-0004 | 47 | 0 | 0 |
| P-0005 | 262 | 0 | 18 |
| P-0006 | 256 | 0 | 18 |
| P-0008 | 27 | 0 | 0 |
| P-0009 | 28 | 0 | 0 |
| P-0010 | 27 | 0 | 0 |
| P-0011 | 42 | 0 | 0 |
| P-0013 | 25 | 0 | 3 |
| P-0014 | 7 | 0 | 7 |
| P-0015 | 39 | 0 | 0 |
| P-0016 | 14 | 1 | 1 |
| P-0017 | 9 | 0 | 0 |
| P-0018 | 34 | 1 | 0 |
| P-0019 | 15 | 0 | 0 |
| P-0020 | 8 | 0 | 0 |

Three real plots have witnessed 2021–2023 loss; five have witnessed 2024–2025 loss. These independently reproduce mapped observations under this release/query, not ground-truth compliance or supplier declaration truth.

Verified core query SHA-256: `7c3948f6f9ec4e1403fbf5c3d663601e9df77fba96ff4373f6ef2d0c2405edd7`. Scratch evidence records all implementation and input hashes. Files were stable throughout the measured run.

## Findings and resolved coordination

Early core validation allowed malformed rings through Shapely repair. Minimal reproducer: `evaluate(dataset(), {'type':'Polygon','coordinates': [[[0,0],[1,0],[1,1],[0,1]]]})`; expected ValueError for an unclosed ring. W2 recorded ring/non-dict/3D gaps in this shared report. The lead independently hardened core while tests were authored; final rejection tests pass. W2 did not edit core.

Missing-band diagnostic side effects were initially underspecified. The lead now explicitly records them in interface-v1.md: absent validity is false, valid land becomes zero, unknown becomes selected, and absent datamask suppresses its diagnostics. Tests cover reason ordering, zero-selected, and outside cases. Resolved in the current interface.

No remaining W2 blocker. Core/source APIs were available; no substitute core was needed.

## Limits and handoff

This verifies query behavior and reproducibility within tested inputs. It does not establish satellite accuracy, forest-at-2020 status, legal deforestation/compliance, or supplier truth. No ML labels were invented. Real inputs remained local and immutable.

GEOS validity is shared, so topology validation is not independently implemented. Finite deterministic fixtures do not exhaust arbitrary geometries/floating-point configurations. Lower work limits, full-array raw-range validation on each call, and scalar scanning make this oracle unsuitable as a production performance baseline. W1/W3 own compression and fair performance measurements.

**Final signal: W2 COMPLETE — ready for lead review/integration.** Master may relay this report and reproduction commands. Lead should include both test modules in the integrated suite and rerun after core/source/contract changes.

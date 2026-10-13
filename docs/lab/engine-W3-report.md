# W3 fair benchmark and deterministic registry — ready for lead review

**Current retained choice: corrected cycle2 `separate_zstd_l19`, chunk1024,
535,012 total bytes versus 585,293-byte required original baseline (8.59%
smaller).** The unused generated948-byte source manifest is research overhead,
excluded from necessary bytes. Canonical
`artifacts/benchmark-v1.json` is frozen to the explicit cycle2 selection below;
the original first-handoff sections remain historical evidence.

**Current store for lead refresh:**
`artifacts/stores/exp-0109a8d6c4782217871315b92c63a971d11ebd164585c80981f24c55b4f68fea/separate_zstd_l19`.
Lead `engine.proof.validate_benchmark` accepts this corrected retained binding;
see the final correction section for archived equality/code/store checks.

Completed 2026-10-13, within the authorized session. Ownership respected:
`engine/benchmark.py`, `engine/experiments.py`, `engine/tests/test_experiments.py`,
this report, `data/experimental/w3/`, and assigned benchmark/store/registry
artifacts only. No core/codec/oracle/export edits, Git mutations, source writes,
private uploads, external publication, new dependencies, agent runtimes or ML.

## Deliverable and API

- `.venv-data/bin/python -B -m engine.benchmark` creates `artifacts/benchmark-v1.json`.
- `.venv-data/bin/python -B -m engine.experiments` invokes the same runner/registry.
- `run_benchmark(root=None, repetitions=7, warmups=2, chunk_size=128, candidates=None)` returns the complete measured result.
- `experiment_id(identity)` hashes canonical JSON inputs/settings/implementation.
- `record_experiment(identity, result, directory=None)` stores immutable measured run JSON, atomically updates a locked index, and reports duplicate/repeat status.
- `atomic_write_json(path, value)` flushes then atomically replaces JSON; temporary files are cleaned on failure.

Registry identity includes all three chip hashes/metadata, acquisition-provenance
hash, supplier/geometry input hashes, exact query geometry fingerprint, query and
benchmark versions, implementation hashes, candidate list, chunk size, warmups
and repetitions. Different timings create separate content-addressed run files;
identical retries reuse evidence. Existing stores are preserved: repeat encoding
uses W3 scratch and must match every stored byte/hash. Code/input changes during
a measured run reject that run; implementation changes between runs produce new
experiment IDs. Four concurrent registry writers were tested.

## Fair measurement method

- Every representation covers the same complete native AOI: **604 rows × 1233 columns**, EPSG:4326, unchanged grid and source product dates. No tile-to-chip savings or plot crops enter storage/timing denominators.
- Original baseline includes actual three DEFLATE GeoTIFFs (**576,999 bytes**), required acquisition provenance (**8,294 bytes**), and generated source identity metadata (**948 bytes**): **586,241 bytes total**. Embedded TIFF grid/mask/index bytes remain in TIFF payload. All necessary on-disk files have measured bytes and SHA-256.
- Separate-band zstd is the recompressed second baseline, preserving all raw cells and masks with the same chunk size as other candidates. Payload, metadata JSON value, remaining chunk-index/format overhead, combined metadata/index, and total are reported separately. Zstd level 3 is recorded.
- Common supplier/geometry files total **19,265 bytes**, reported separately and excluded symmetrically. The UI and network acquisition are excluded.
- Hot: a dedicated ordinary Python child per representation, full load once, two warmups, seven measured complete 17-plot batches. Source and compact both exclude load.
- Process-cold: seven fresh ordinary Python children per representation; both loader modules are imported before operation timers. Full native load/validation/integrity hashing plus all 17 queries is measured. Common geometry reading/imports are excluded from operation timing and included in separate parent-observed subprocess wall timing. Load and query timings are also separated.
- **OS cache is uncontrolled and likely warm after verification/encoding. Process-cold is not disk-cold.** No cache eviction is claimed.
- Wall/CPU timing samples retain median/p95/min; p95 uses nearest rank and is the maximum with seven samples. Benchmark children run sequentially with numerical thread limits set to one.
- RSS is a fresh child lifetime high-water mark including interpreter/imports/input data, not incremental operation-only memory. macOS native bytes and Linux native KiB are reported and normalized to bytes. Encode, hot and each cold child have separate RSS evidence.
- Encoding wall/CPU time excludes source loading and includes validation, packing, compression, checksums and file writes. Existing source-chip production was not remeasured; its preprocessing fields are null with an explicit historical note.

## Actual results

Every candidate and every final sweep setting passed full **744,732-cell**
roundtrip, all **2,234,196 raw band values**, all band masks, identical metadata,
and **17/17 exact real-plot query results** with no differing fields. Timed hot
and cold answers also matched source result digests. The real cohort is 17 unique
supplied plots, repeatedly evaluated; synthetic registry/accounting tests are
separate. This proves encoding/query equality, not source accuracy or compliance.

Final default chunk128 result (bytes; timings ms per complete 17-query batch):

| Representation | Payload | Metadata | Index | Total | Encode wall / CPU | Hot median / p95 | Process-cold median / p95 | Cold peak RSS bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Source DEFLATE TIFF | 576999 | 9242 | 0 external | 586241 | unavailable | 1.627 / 1.737 | 11.390 / 11.761 | 77283328 |
| packed14_zstd | 889391 | 947 | 24851 | 915189 | 19.671 / 19.664 | 1.448 / 1.599 | 16.050 / 16.401 | 64258048 |
| uint16_zstd | 736387 | 947 | 24843 | 762177 | 6.839 / 6.839 | 1.451 / 1.466 | 7.037 / 7.929 | 63324160 |
| separate_zstd | 584578 | 947 | 46431 | 631956 | 7.353 / 7.343 | 1.428 / 1.495 | 7.342 / 8.634 | 63012864 |
| bitplane_zstd | 745231 | 947 | 24847 | 771025 | 22.597 / 22.504 | 1.459 / 2.594 | 10.549 / 11.058 | 64307200 |

Bounded chunk sweep was justified by the substantial index overhead observed in
the first run. Total bytes, using the same final implementation fingerprint:

| Chunk size | packed14 | uint16 | Separate bands | Bitplane |
| --- | ---: | ---: | ---: | ---: |
| 32 | 1327688 | 1172261 | 1341555 | 1179430 |
| 64 | 991647 | 857500 | 786400 | 858881 |
| 128 | 915189 | 762177 | 631956 | 771025 |
| 256 | 885759 | 733199 | **592190** | 759940 |

Smallest encoded candidate across the measured sweep: separate-band zstd at
256, **592,190 bytes**, comprising payload 577,036, metadata 947, index 14,207.
It is **5,949 bytes / 1.01% larger** than the corrected compressed-original
baseline. At that setting its hot median was 1.460 ms versus source 1.411 ms;
process-cold median was 5.951 ms versus source 11.487 ms. These are small local
samples with uncontrolled host activity/frequency. No consistent hot advantage
is established; startup-inclusive timing is separately available in JSON.

`winner` selects minimum total bytes among fully exact encoded candidates within
the run; `overall_storage_choice` explicitly selects **source_geotiff** when the
original is smaller. The default128 encoded winner is separate-band zstd,
7.80% larger than source. No compression victory over original is claimed.

An early baseline omitted the provenance file after the lead strengthened the
source loader. That omission was corrected, fingerprints changed, and all final
settings were rerun. Early runs with 577,947-byte denominators remain historical
superseded evidence. A commentary percentage of 1.48% was an arithmetic error;
the verified final difference is 1.01%. W1 codec safety changes between runs also
correctly produced new IDs. Final IDs below share one implementation fingerprint.

## Commands and verification

Actually executed:

```sh
.venv-data/bin/python -B -m unittest engine.tests.test_experiments -v
.venv-data/bin/python -B -m engine.benchmark
.venv-data/bin/python -B -m engine.benchmark --chunk-size 32
.venv-data/bin/python -B -m engine.benchmark --chunk-size 64
.venv-data/bin/python -B -m engine.benchmark --chunk-size 256
.venv-data/bin/python -B -m engine.experiments
```

The final consistent sweep and repeat were executed programmatically:

```sh
.venv-data/bin/python -B -c 'from engine.benchmark import run_benchmark; import json
for size in (32,64,256,128,128):
 b=run_benchmark(chunk_size=size); print(json.dumps({"chunk_size":size,"registry":b["registry"],"winner":b["winner"],"overall_storage_choice":b["overall_storage_choice"]}),flush=True)'
```

**12 tests passed**, including concurrent writers, atomic-write failure preserving
old JSON, interrupted-index recovery, repeated-result preservation/deduplication,
nonfinite rejection, missing storage files in accounting, nested mismatch paths,
timing digest failures, actual source child-process equality, and generated
artifact verification against actual file bytes/hashes and full cohort counts.
Optional generated-artifact test skips only if no benchmark exists yet.

Final default experiment:
`exp-73e4981e4fe5b1eef3b33de5928458e32d46c3fd51a416ff3aa8a1607a2e9203`.
Final run:
`run-70c8e98e0c2fc90f145ab1ec3a866c897ec739eed3fea0ee128b0750e140e59b`.
The default registry now preserves **three measured runs**, reports `is_repeat=true`,
and repeat encodings are byte-identical without overwriting original stores.

Final sweep IDs:

- 32: `exp-12a6bf574eac4458170c3273b0ec0d39fffce33b2ff7d4e4c64a31d241a70eda`
- 64: `exp-a4ab76966b51b94e381504da38ec59e95c571ded8fd4e14a059359939c5346bd`
- 256: `exp-a72612066646a3cdf274d6ebc0d1895c7c5a251aa037aca588af4023f37e2bf7`

Stores are at `artifacts/stores/<experiment_id>/<candidate>/`. Canonical benchmark
is the final default128 run; the best encoded sweep store is
`artifacts/stores/exp-a72612066646a3cdf274d6ebc0d1895c7c5a251aa037aca588af4023f37e2bf7/separate_zstd`.
The immutable registry run omits the outer registry pointer; the canonical
benchmark includes it. Hash verification confirmed run filenames match their
measured content and the final benchmark implementation hashes match live files.

Environment: Apple M5, Mac17,2, arm64, 10 logical CPUs, 34,359,738,368 RAM bytes;
macOS 26.6.2; Python 3.14.7, numpy 2.5.4, rasterio 1.5.2, GDAL 3.12.2, shapely
2.1.2. No additional dependency installed.

## Blockers and integration notes

No W3 blocker remains. W1 initially pending; actual codec API arrived and the
runner integrated without touching it. Lead should rerun after any further
core/codec change; IDs detect these changes and old evidence remains preserved.
The benchmark currently measures full decode + core query. It does **not**
measure the optional indexed-window query API or make claims about it. W2 owns
independent semantic/oracle tests; these measurements are source/compact fidelity
checks. Lead retains final export/UI integration and review of all worker code.

Master relay signal: **W3 implementation, verified benchmark artifacts and report
are ready for Volta review.**

## Cycle2 in progress — lead review notes accepted

Read `docs/lab/engine-review-notes.md` on resume. The provenance accounting
requirement is already satisfied by the corrected 586,241-byte baseline above.
W1's level9/19 additions were not present at the initial cycle2 read; W3 will
measure those actual candidates after arrival, without writing codec/core files.

Implemented before the cycle2 measurements: guarded source/provenance/geometry
and implementation hashes at parent start/end and in every measured child;
changed cached implementation requires a fresh Python runner. Hot/cold answer
fingerprint mismatch now raises `BenchmarkRaceError`, never quietly produces an
eligible alternate winner. Aborts archive visible failure evidence under
`artifacts/experiments/failures/` and re-raise to a nonzero CLI exit. Measured store
file hashes are checked again before registration and retention.

Added explicit `retain_benchmark(result, reason)` and atomic
`artifacts/experiments/retained-choice.json` plus archived selection decisions.
Exploratory `publish=False` / CLI `--no-publish` records registry evidence without
changing canonical benchmark. Once a choice is explicitly frozen, ordinary
subsequent benchmark runs cannot replace it. Only another deliberate retention
call changes the decision. Canonical output binds to one immutable registered
run and carries its retained choice/store path/reason. Lead still owns demo refresh.

17 W3 tests passed after these changes, including new retention/tamper tests and
visible timing, implementation, input and measured-file race failures. Earlier
v1 runs remain retained as historical evidence. This section will be followed by
actual cycle2 results and a frozen explicit choice after W1's variants stabilize.

## Cycle2 complete — explicit retained choice for lead review

Followed the lead's actual review notes, including the new core aggregation and
source context-manager refactor. All three cycle2 configurations share one new
implementation/input fingerprint and use the existing full-load query scope.
W1's actual six-candidate codec API was available; its extended suite passed
**19 tests** before the performance run. No W3 edits to codecs, core, indexed
readers, the window benchmark, demo or example artifacts.

Measured levels 3/9/19 at chunk256 and512. At512 the smallest candidate's chunk
index alone cost 1.098% of total storage; the bounded predeclared rule was to
measure1024 once if index cost exceeded0.5%. That justified1024. No further tuning
was performed. All **nine** cycle2 level/chunk combinations passed exact full raw
values, masks, metadata, 17/17 real query fields and every timed answer digest.
These are still the same17real plots, not nine independent cohorts.

| Chunk | Candidate | Payload bytes | Metadata bytes | Index bytes | Total bytes | Encode wall / CPU ms | Hot median / p95 ms | Process-cold median / p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 256 | level3 | 577036 | 947 | 14207 | 592190 | 5.498 / 5.499 | 1.461 / 1.484 | 6.003 / 7.376 |
| 256 | level9 | 559752 | 947 | 14209 | 574908 | 22.783 / 22.726 | 1.492 / 1.702 | 6.286 / 7.136 |
| 256 | level19 | 528069 | 947 | 14205 | 543221 | 277.741 / 277.136 | 1.464 / 1.591 | 6.286 / 7.000 |
| 512 | level3 | 590782 | 947 | 5906 | 597635 | 5.891 / 5.891 | 1.475 / 1.525 | 5.787 / 6.073 |
| 512 | level9 | 563053 | 947 | 5907 | 569907 | 24.045 / 24.025 | 1.467 / 1.708 | 5.733 / 6.757 |
| 512 | level19 | 531266 | 947 | 5909 | 538122 | 237.658 / 235.402 | 1.456 / 1.498 | 6.187 / 6.758 |
| 1024 | level3 | 585396 | 947 | 2213 | 588556 | 6.796 / 6.547 | 1.475 / 1.615 | 5.557 / 6.999 |
| 1024 | level9 | 559708 | 947 | 2216 | 562871 | 19.997 / 19.982 | 1.449 / 1.583 | 5.677 / 6.187 |
| 1024 | **level19 retained** | **531847** | **947** | **2218** | **535012** | **212.594 / 212.497** | **1.655 / 1.765** | **5.868 / 7.003** |

All timings are ms per complete17-query batch except one-time encode. Seven
samples, two hot warmups, nearest-rank p95, isolated sequential ordinary Python
processes, native platform RSS and uncontrolled likely-warm OS cache are unchanged.
No disk-cold claim. Store metadata/index counts include the original identity;
original baseline still counts the acquisition manifest required by its loader.

**Smallest encoded AND overall original-vs-encoded storage choice:**
`separate_zstd_l19` at1024. It saves **51,229 bytes / 8.74%** against the complete
586,241-byte original load baseline. Against the TIFF payloads alone its complete
store is also smaller (535,012 vs576,999); tile crops never enter the comparison.
Level19 at1024 is3,110bytes smaller than level19 at512, and27,859bytes smaller than
level9 at1024. Original source remains present and unchanged.

Reason for retention: the lead-requested minimum total-storage criterion chooses
535,012bytes among fully exact candidates. The measured ~213ms one-time encoding
cost is acceptable for this bounded AOI ingestion. It is ~10.6× level9's20ms and
requires higher encode RSS: **101,711,872 bytes** versus level9 **92,405,760 bytes**
at1024. Cold-process query RSS max was72,450,048bytes for both. These are child
lifetime peaks including interpreter/imports/input data, not incremental costs.
At the retained run, source hot median was1.435ms and process-cold median11.374ms.
Compact hot was1.655ms, so **no hot speedup is claimed**; process-cold was5.868ms.
Full runtime/CPU/min/p95/sample/RSS and startup-inclusive measurements remain in
immutable JSON. Lead owns indexed-window tradeoffs; large-chunk window performance
is not measured or implied here.

Frozen selection paths:

- Decision: `artifacts/experiments/retained-choice.json`.
- Canonical: `artifacts/benchmark-v1.json`, with `retained_selection` bound to immutable evidence.
- Retained experiment: `exp-26ba2d043721e20e770efc52bd46f9536eb02b494eed7264aa01e3d41cf5f856`.
- Retained run: `run-c2d69662d2b4202f868e985636f1037ce79fc65ce76dc37bb816583008547568`.
- **Store for lead demo refresh:** `artifacts/stores/exp-26ba2d043721e20e770efc52bd46f9536eb02b494eed7264aa01e3d41cf5f856/separate_zstd_l19`.
- 256 experiment: `exp-ee12a8a6a5b0b62f6c23b855ac3889bf3b06434b9a45f20a912ec86e75f42472`.
- 512 experiment: `exp-4c80d5b0efa44f1726b05a1ffe6d92082905a437ffb0aa4bc344d87b0e085a0d`.

The explicit selection decision itself is archived under
`artifacts/experiments/selections/choice-<content hash>.json`. All previous runs,
including first-cycle losers and superseded-accounting runs, remain present.
The three exploratory cycle2 runs used `publish=False`; selection was made by
minimum measured total size across them, then `retain_benchmark(chosen, reason)`
verified current source/implementation/store hashes and deliberately froze it.
It was not retained merely because1024 ran last. Ordinary later runs cannot
replace this decision; deliberate retention is required.

Actual cycle2 commands:

```sh
.venv-data/bin/python -B -m unittest engine.tests.test_codecs -q
.venv-data/bin/python -B -m unittest engine.tests.test_experiments -v
.venv-data/bin/python -B data/experimental/w3/cycle2-run.py
```

The bounded scratch runner records complete results in
`data/experimental/w3/cycle2-results.json` and all immutable registry runs. Its
adaptive1024 rule and settings are visible in that script. Retention used the
public Python API on the smallest measured result with the full reason now
stored in `retained-choice.json`.

**18 W3 tests passed**, including a real ordinary child rejecting a wrong
provenance fingerprint with nonzero exit, timing-digest mismatch aborts, input and
implementation races, modified measured files, archived failure evidence,
retention tamper/reason rejection, concurrent registry writes and blocked later
publication. Race failures re-raise visibly and archive failure records; they are
never converted to an alternate eligible winner. Parent/children verify guarded
fingerprints outside timed operation intervals. No spontaneous cycle2 race was
observed; injected test faults are labeled tests, not real data failures.

No blocker remains. This retained choice is W3's evidence-backed handoff for lead
review; the lead owns independent final review and canonical demo refresh.

Post-freeze end-to-end check: reran chunk256 at levels3/9/19 with normal
`publish=True`. It created a second immutable run in its existing experiment,
verified deterministic re-encoding against untouched stores, and returned
`canonical_updated=false` despite publication being requested. SHA-256 of
`artifacts/benchmark-v1.json` was identical before/after. The last experiment's
543,221-byte winner did not replace the retained535,012-byte configuration.
This verifies the real runner's retention behavior, in addition to unit tests.

Cycle2 master relay signal: **W3 retained choice, measured stores, guarded runner,
registry and report are ready for Volta review; use the explicit retained store
path above for lead-owned demo refresh.**

## Priority accounting correction — fresh run in progress

Accepted lead/xhigh validator correction in engine-review-notes.md: the generated
948-byte source identity metadata.json is not read by load_source. Previous
586,241-byte denominator is superseded. Necessary baseline is **585,293 bytes**:
576,999 actual TIFF bytes +8,294 loader-required acquisition-provenance bytes.
The duplicate remains measured under `baseline.research_overhead` only, with
bytes/hash/files separate from required storage and excluded from all ratios.
Older archives/decisions remain unchanged as historical evidence. Updated tests
assert the required baseline file set is exactly three TIFFs + acquisition JSON.
Fresh corrected cycle2 measurements and an explicit retained choice follow.

## Priority correction finalized — fresh bound retention ready

This section and the report header supersede all earlier required-storage
baseline numbers and retained store paths. The accepted independent-validator
correction is implemented: **required source storage =585,293 bytes** (576,999
TIFFs +8,294 acquisition-provenance JSON). Required `storage.files` is exactly
those four files. The unused generated948-byte metadata duplicate is measured
only under `baseline.research_overhead`, not included in required bytes, ratios
or winner selection. Both required and research file hashes are checked during
run/retention. Earlier immutable runs and selection decisions were not edited.

Reran the complete bounded level3/9/19 × chunk256/512/1024 cycle with stable
source/query/code fingerprints. All9combinations again passed full744,732-cell
roundtrip, all2,234,196 raw values, all masks, identical metadata and17/17real plot
query outputs, including every hot/process-cold timing digest. The predeclared
512-index>0.5% rule again justified1024. Complete encoded sizes remain unchanged;
only the necessary source denominator and fresh fingerprints/measurements changed.

**Fresh explicit retained choice:** `separate_zstd_l19`, chunk1024. Smallest
encoded and overall original-vs-encoded choice remains **535,012 bytes**, now
correctly **50,281bytes /8.59% smaller** than585,293. Store breakdown:531,847-byte
payload +947-byte metadata +2,218-byte index. Optional source research duplication
is never used to claim that saving. Same full native AOI; no crop savings.

Fresh retained timing samples (ms per17-query batch): hot min1.405, median1.446,
p951.455; process-cold min5.768, median5.800, p956.266. Source hot median1.418 and
process-cold median11.182. Seven repetitions/two hot warmups, likely warm and
uncontrolled OS cache; no hot speedup or disk-cold claim. One-time encode wall
212.443ms /CPU212.037ms; encode child RSS101,629,952bytes; cold query child RSS max
72,630,272bytes. Resource scope includes child interpreter/imports/input data.
Retention accepts that bounded preprocessing cost for minimum measured storage.

Fresh bindings for lead positive control and validator recheck:

- **Store:** `artifacts/stores/exp-0109a8d6c4782217871315b92c63a971d11ebd164585c80981f24c55b4f68fea/separate_zstd_l19`.
- Experiment: `exp-0109a8d6c4782217871315b92c63a971d11ebd164585c80981f24c55b4f68fea`.
- Run: `run-71a5b90b05bdce363044d8e232ae33d20b31f3868a6f5ba50bf61372b98194a9`.
- Archive: `artifacts/experiments/exp-0109a8d6c4782217871315b92c63a971d11ebd164585c80981f24c55b4f68fea/run-71a5b90b05bdce363044d8e232ae33d20b31f3868a6f5ba50bf61372b98194a9.json`.
- Canonical and decision: `artifacts/benchmark-v1.json` and `artifacts/experiments/retained-choice.json`.
- Read-only binding evidence: `data/experimental/w3/corrected-cycle2-proof.json`.
- Store `index.json`:3,165bytes, SHA-256 `33fb7c401550898853ee09c1a1e82fadb8114a234d840893cc96a2ee003b1a84`.
- Store `payload.bin`:531,847bytes, SHA-256 `db7ba9295eccc2e816b73ab0ac321af05febf3cd2f2b8204b07778ba7fdd0a6c`.

Actually executed after correction:

```sh
.venv-data/bin/python -B -m unittest engine.tests.test_experiments.RegistryTests engine.tests.test_experiments.BenchmarkAccountingTests -q
.venv-data/bin/python -B data/experimental/w3/cycle2-run.py
.venv-data/bin/python -B -m unittest engine.tests.test_experiments -v
.venv-data/bin/python -B data/experimental/w3/corrected-cycle2-proof.py
```

The15registry/accounting tests passed before fresh measurements; **all19W3tests
passed** after fresh explicit retention. The added real-artifact test calls the
lead proof guard on the corrected binding, then rejects altered archive metrics,
stale query code fingerprint and wrong store binding. It also asserts the exact
required baseline file set/bytes and research-only separation.

The scratch proof script passed a real positive `engine.proof.validate_benchmark`
call with current source/plots/selected store. It independently checked canonical
payload equality to immutable measurement archive, run-content hash, all6live
implementation SHA-256 fingerprints, all6source/cohort input fingerprints and
current retained store binding. Those hashes/bytes and positive result are
archived in `corrected-cycle2-proof.json`. It rejected four labeled negative test
controls: altered archived metric, stale query implementation, a real valid
level9store substituted for retainedlevel19, and the superseded pre-correction
retained benchmark. This is W3 proof-binding evidence, not a claim that the
external validator has already completed its own recheck.

Prior cycle2 scratch summary and retained canonical snapshot were also saved as
`cycle2-results-before-baseline-correction-674360b53187b0f8dede9826554e071a24f9a387c5562e6625058732ca555044.json`
and
`retained-before-required-baseline-correction-d60cc176ac5f943695ae25efdb3a6c37cbbccebca42aa03f55034f9133846104.json`
underW3scratch. All prior registered evidence/decisions remain intact. Selection
was explicitly made from fresh measured minima, not from the last run; later
experimental publication remains blocked by the deliberate retained decision.

**No W3 blocker. Corrected retained benchmark passes the lead proof guard and is
ready for lead-owned demo positive-control refresh plus independent validator
recheck.** No demo/example/proof/verify/core/codec/other-worker files were edited.

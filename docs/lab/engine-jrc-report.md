# JRC native-grid companion worker

## Current J1/J2 handoff — fixed, ready for focused review

Read the lead review and `validator-jrc-report.md`. The earlier timing-integrity
claim was too broad: intermediate answers and measurement identity were not
checked. J1 and J2 are now fixed and covered by fresh controls. **All 28 JRC test
methods passed in 6.928 seconds**, including seven new measurement/lifecycle
methods with multiple adversarial cases. Ready for master relay to Volta and
the independent validator; final acceptance remains theirs.

Only JRC production modules/tests, separate JRC artifacts/stores, JRC scratch and
this report were written. `package_jrc.py` and accepted Hansen files were not
edited. No Git mutations. Historical first-handoff timings/bindings below are
retained as superseded evidence; the current run and commands are in this section.

### J1: each measured operation is checked and bound

`timed()` now checks every warmup and measured result immediately, outside the
timed interval. A mismatching intermediate result aborts the runner before any
run archive is published. Source loads and compact decodes are validated against
the complete raw-array/mask/metadata fingerprint. Every encoded store is decoded
and checked after its timed encode; repeated encoded file identities must also
match. Every hot query batch is checked against the independently established
expected 17-plot output, rather than retaining only the last answer.

Each timing block records its expected result hash and guard hash, two warmup
records and seven measured records. Each record includes its result hash and
before/after guard hashes. The proof verifier reconstructs these expected hashes
from actual pinned source data, actual store files and the current measurement
identity; changing/re-hashing an intermediate digest is rejected even when the
attacker supplies an equally rehashed benchmark archive and matching run ID.

Before and after each call, guards rehash actual source/semantic/plot inputs and
implementation files, compare the implementation captured at module import, and
check settings, runtime, geometry cohort, relevant in-memory dataset, and compact
store identity. Run-level start/end guards additionally bind the full source
readback identity and every measured store before archive publication. These are
observed boundary checks, not filesystem locks or cryptographic authentication.

Every fresh cold child receives the parent's pinned identity, expected full
dataset/answer hashes and source/store guard. The child checks them before and
after its workload; the parent checks every warmup and measured child before
retaining it. Warmup child records are now archived too. Proof checks all these
records against current pinned evidence. There are 234 checked in-process
warmup/sample records and 18 checked child records in the refreshed run.

The identity explicitly names `numpy.percentile(method=linear)` for p95.
Validation/guard work is outside inner timing intervals; spawn-inclusive time
includes child validation. Whole-child peak RSS includes imports and post-timing
validation. These scopes replace the incomplete earlier measurement description.

### J2: retained ordinary export, explicit new measurement

Ordinary `export_jrc()` and `python -m engine.jrc` now verify and reuse the
measurement embedded in the existing `artifacts/jrc-baseline-v1.json`. They
perform no new measurement and retain the measurement timestamp/run ID. No extra
retention file is needed: the existing companion is already included by the
lead-owned package manifest. Missing/stale retained evidence raises a clear error;
ordinary export does not silently fall back to measurement.

New measurements require `--measure` or `new_measurement=True` and the full source
cache. The direct benchmark module remains an explicit measurement entry point.
Explicit metric-free export through `store=...` remains supported. Ordinary
verification/export works without the 197,739,699-byte acquisition tile; in that
case its historical readback record is checked against pinned source/hash/grid
metadata, while all available chip/store pixels and masks are recomputed.

Current commands:

```sh
# Explicit new measurement and publication of the separate JRC companion:
PYTHONDONTWRITEBYTECODE=1 .venv-data/bin/python -B -m engine.jrc --measure
# Ordinary retained-result regeneration; no measurement/full tile required:
PYTHONDONTWRITEBYTECODE=1 .venv-data/bin/python -B -m engine.jrc
PYTHONDONTWRITEBYTECODE=1 .venv-data/bin/python -B -m engine.jrc --verify artifacts/jrc-baseline-v1.json
PYTHONDONTWRITEBYTECODE=1 .venv-data/bin/python -B -m unittest engine.tests.test_jrc engine.tests.test_jrc_codec engine.tests.test_jrc_proof engine.tests.test_jrc_measurement -v
```

### Current bindings and evidence

Refreshed measurement timestamp: `2026-10-13T04:00:55.844598+00:00`.
Artifact: `artifacts/jrc-baseline-v1.json`, 591,831 bytes;
content identity `c13127c9f6d8654a1dae0d66945c981bfc340b20467124dd2e55829d79d754a3`.
Actual file SHA-256 (distinct from the embedded content hash):
`933b3d302b8ec961444a7f252f74deb87f3f186f1b7f8d5bcb5012cb55658f71`.

```text
experiment exp-bfd3067040ae3fb83331667fba2ece195e9372893c81ac1930edbdfc68444f3a
run        run-5b318b210c244c60458942f67281a8abc6f8ebcc2b3949effc12feb3013cd261
```

Archive is the named run JSON under
`artifacts/jrc-stores/exp-bfd3067040ae3fb83331667fba2ece195e9372893c81ac1930edbdfc68444f3a/`.
Selected store is that directory's `binary_packed_zstd19-1024` subdirectory.
All current source/code/runtime/settings fingerprints are in its `identity.json`.

The refreshed artifact passes a fresh measured positive and a fresh metric-free
positive. Earlier raw/mask/receipt/summary/type controls still reject. New controls
prove the actual runner rejects a wrong **second measured source-hot answer** and
a wrong second measured source load; the error is `JRC timed result mismatch at
sample 2`, and no run JSON is archived. Additional controls reject warmup errors,
real copied input/code/store changes, a bad child context, and self-consistently
rehashed sample/guard/child forgeries in the verifier.

Persistent new control evidence:
`data/experimental/jrc-engine/J1-J2-controls-3c603b3c0e7761714b9f10f129c13031e6335880efcf692c42479d9eed1273da.json`.
Fresh prior proof controls for this run:
`data/experimental/jrc-engine/proof-controls-e539b02dbe623e15c0a994d2e165e3db6d99ebe1b073db5437c82c442ef60854.json`.

The new lifecycle test uses the lead's manifest function with an **owned scratch
output**, copies exactly its 46 files into a clean project-local bundle, and
asserts the full tile is absent. Both direct ordinary export (with measurement
mocked to fail if called) and fresh-process CLI **verify → ordinary export →
verify** pass. Every bundle file's bytes remain identical, no run/files appear,
and timestamp/run ID remain unchanged. Tested inventory was 1,321,035 bytes before
this report update; that is proof/code/document overhead, not a codec denominator.
The persistent control records the actual tested inventory. Volta should regenerate
the canonical package inventory after this report change; package code needs no
new runtime-file rule and has not been edited by this worker.

### Refreshed measured scope

Raw values/masks, all 17 source/oracle/compact results, and every candidate's byte
count remain exact. Selected store remains 21,459 bytes against the provided
native DEFLATE loader's 57,653 required bytes. This comparison covers that supplied
chip and the four named custom codecs only; it is **not** a custom-over-all-standard
formats optimum. The lead's separate standard-TIFF control study is not mixed
into this artifact or any Hansen claim.

Seven measured repetitions after two warmups; medians in milliseconds:

| Path | Encode | Full load/decode | All 17 hot queries |
| --- | ---: | ---: | ---: |
| Source loader | — | 6.053 | 5.195 |
| Selected packed level19/chunk1024 | 226.406 | 2.824 | 5.221 |

Process-cold, OS-cache-warm source load + queries: median 17.258 ms, p95 26.882 ms;
selected compact: median 10.236 ms, p95 10.804 ms. Spawn-inclusive medians are 166.189
and 154.252 ms respectively. Median whole-child peak RSS is 96,354,304 and 85,000,192
bytes; maxima are 96,567,296 and 85,098,496 bytes. Child RSS now includes result/guard
validation. Full samples and all losing candidates remain in the refreshed
archive. No new general hot-query speedup claim is made.

Conservative storage views remain as recorded below: keeping identical semantic
provenance on both sides yields 57,653 versus 32,874 bytes; adding common exact plot
inputs yields 76,918 versus 52,139 bytes. No crop savings, duplicate denominator
padding, or Hansen/JRC percentage aggregation is introduced.

## Historical first handoff — superseded timing/lifecycle bindings below

Status: **COMPLETE — ready for Volta review and master relay.** First working
artifact was generated by 03:01 UTC; final measured run was recorded at 03:15 UTC on
2026-10-13. No blocker. Lead retains final integration/acceptance ownership.

Writes were restricted to new `engine/jrc*.py`, `engine/tests/test_jrc*.py`,
`artifacts/jrc-baseline-v1.json`, `artifacts/jrc-stores/`, this report, and new files
under `data/experimental/jrc-engine/`. Accepted Hansen code/store/benchmark/main
artifact, frontend, package code, and acquired source files were not modified.
No Git mutations, dependency installation, source acquisition rerun, private
upload, publication, or agent spawning was performed.

Initial independent result: the pinned full source window matches all 6,684,255
chip pixels AND mask bits. Production native-center queries and the W2 scalar
ray-casting membership plus independent JRC scalar reduction match for all 17
plots. Recomputed P-0001 has 554 class 1 cells among 1,083 selected; P-0003 has
793 selected valid class 0 cells. These were computed from source, not copied from
the lead cross-check. GEOS topology validation is shared; membership/reduction
are independent. Source uncertainty is not evaluated by this equality.

The QML hash is pinned and parsed: 0 = Non-forest, alpha 0; 1 = Forest, alpha 255.
Both are valid values; alpha is not used as a validity mask. The v4 XML's older
dates and v2 report DOI remain explicit metadata caveats. JRC stays on its own
1809×3695 chip affine lattice, with zero-based chip evidence indices.

## Deliverable and reproduction

- `engine/jrc.py`: pinned source loader, `JrcDataset`, native query, evidence,
  `export_jrc(...)`, `verify_jrc_artifact(path)`, and CLI.
- `engine/jrc_codec.py`: separate one-band packed/byte codecs at Zstandard levels
  3 and 19. No conversion into Hansen bands.
- `engine/jrc_oracle.py`: scalar membership and reduction independent of the
  production selector/reducer. Uses W2's ray-casting helpers, with exact Fraction
  fallback near cancellation; GEOS validates topology only.
- `engine/jrc_benchmark.py`: same-chip measurements, source/mask readback,
  runtime/source/code/settings fingerprints and immutable result archives.
- `engine/jrc_proof.py`: pinned-source recomputation, full-chip comparisons,
  per-plot/receipt/evidence/summary checks, and actual benchmark-file binding.
- `engine/tests/test_jrc.py`, `test_jrc_codec.py`, `test_jrc_proof.py`: **21 methods
  passed in 2.587 seconds** in the final run, including subcases described below.

Run from repository root using the existing environment:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv-data/bin/python -B -m engine.jrc
PYTHONDONTWRITEBYTECODE=1 .venv-data/bin/python -B -m engine.jrc --verify artifacts/jrc-baseline-v1.json
PYTHONDONTWRITEBYTECODE=1 .venv-data/bin/python -B -m unittest engine.tests.test_jrc engine.tests.test_jrc_codec engine.tests.test_jrc_proof -v
```

The first command generates a new measured run and the separate companion. Old
content-addressed experiment records remain. The tests generate fresh measured
and metric-free positive controls from the current artifact/store; run export
first in a new checkout or after an implementation change. The verifier returns
`valid:false` with a reason and its CLI exits `1` for a rejected artifact.

Canonical companion: `artifacts/jrc-baseline-v1.json`, **522,376 bytes**, content
SHA-256 `f774b5c569c9cac0dc6b9b0e4e7ce2e8d19611b9e339e0beb1c183c87a1b2475`.
Schema is `plotline.jrc-baseline.v1`; query is `jrc2020-centers.v1`.

Measured identity:

```text
exp-b5ab7c4c4db8cf855d03ce3744ffc5ec905ab287b66097f5fb7e2f6ffa8886d4
run-764fcd1a3d1e1e90f105205a9d52b8b898b8a0ed9ff48ace84065eb894862c8f
```

Selected encoded store:
`artifacts/jrc-stores/exp-b5ab7c4c4db8cf855d03ce3744ffc5ec905ab287b66097f5fb7e2f6ffa8886d4/binary_packed_zstd19-1024`.
The same experiment directory contains `identity.json` (6,972 bytes), all eight
candidate stores, and the named run JSON (28,165 bytes). These proof/research
archives and the 522,376-byte companion are explicitly separate output overhead;
they are not required by the timed array decoder/query paths and are not hidden
inside the compression denominator. No total application-storage reduction is
claimed. Earlier experiment directories preserve preliminary results.

## Semantics, dates and native-grid evidence

The loader verifies fixed SHA-256 identities for the chip, acquisition manifest,
QML and XML, then derives labels from the pinned QML rather than color visibility.
`0 = Non-forest` with alpha 0 and `1 = Forest` with alpha 255. The chip has no nodata
value, and all 6,684,255 acquired mask bits are valid. Raw 0 remains known even
though its display style is transparent. Invalid masks and outside-chip centers
remain unknown; masked raw values are still preserved in the codec.

The artifact includes the manifest's complete required dataset citation, official
source URLs, class-label source URL/hash, source/chip/provenance/XML/QML hashes,
and native shape/CRS/affine transform. The [official product page](https://forobs.jrc.ec.europa.eu/GFC)
and [official catalog](https://developers.google.com/earth-engine/datasets/catalog/JRC_GFC2020_V4)
describe mapped 2020 forest observations and state that the v4 technical report
was expected in December 2026. They do not establish legal findings for these plots.

Reference year 2020, version v4 and citation/publication year 2026 are separate
metadata fields. Exact release date is `null`; the observed source HTTP
Last-Modified is 14 September 2026 and is retained separately. The pinned XML title
says version 4 but its create/publication dates are 7 December 2023, its revision is
28 November 2025, and its report link is DOI 10.2760/1975879 (the older v2 report).
This discrepancy remains explicit; those dates do not replace v4's reference or
citation year. V3 remains unavailable and is never relabelled as v4.

Native query grid is the **acquired chip's declared affine lattice**: EPSG:4326,
1,809 rows × 3,695 columns, step 1/12000 degree. All centers are computed from that
original chip transform. Evidence contains all 9,511 selected centers as compact
`{row,col,value,valid}` records, with zero-based **JRC chip** indices and a shared
grid. The artifact also retains exact original geometries and geometry hashes.
No resampling, Hansen-grid projection, area conversion, combined deforestation
flag, supplier-label ML, or legal-compliance rule is introduced.

Mapped class 1 present is true if any valid selected 1 exists; partial positive
remains true. No observed 1 is false only when selected support is nonempty and
entirely known. Missing band, no valid observations or absent positive with
partial support yields null. Result reason order is no_selected_cells,
out_of_coverage, band_mask_invalid, no_valid_cells, missing_band. Missing-band
simulation invalidates all in-coverage observations while retaining selected and
coverage diagnostics. Counts are cells, not hectares or whole-plot area.

## Independently recomputed plot results

All 17 source dictionaries match both the scalar oracle and every exact codec
candidate. All real plots have complete known support. These numbers were
computed from immutable inputs; the lead observations were used only afterward
as a review cross-check.

| Plot | Selected JRC centers | Valid class 0 | Valid class 1 |
| --- | ---: | ---: | ---: |
| P-0001 | 1,083 | 529 | 554 |
| P-0003 | 793 | 793 | 0 |
| P-0004 | 416 | 416 | 0 |
| P-0005 | 2,370 | 2,370 | 0 |
| P-0006 | 2,309 | 2,309 | 0 |
| P-0008 | 246 | 246 | 0 |
| P-0009 | 270 | 270 | 0 |
| P-0010 | 250 | 250 | 0 |
| P-0011 | 392 | 392 | 0 |
| P-0013 | 222 | 222 | 0 |
| P-0014 | 64 | 64 | 0 |
| P-0015 | 371 | 371 | 0 |
| P-0016 | 140 | 140 | 0 |
| P-0017 | 99 | 99 | 0 |
| P-0018 | 291 | 291 | 0 |
| P-0019 | 113 | 113 | 0 |
| P-0020 | 82 | 82 | 0 |
| Sum over plots | 9,511 | 8,957 | 554 |

The sum may double-count cells where plots overlap. It is not an area estimate
and must not be added to Hansen counts as if the resolutions were equal.

## Same-chip codec accounting and measured choice

Full source-window pixels AND masks were independently reread from the pinned
197,739,699-byte source tile and compared to the native chip. That source cache
is optional for normal loading, required for a new readback experiment, and is
excluded from codec savings. No tile-to-chip crop reduction is counted.

Actual normal source-loader inputs are all consumed and verified:

| Required source-loader file | Bytes |
| --- | ---: |
| Native DEFLATE chip | 46,238 |
| Acquisition provenance | 4,680 |
| Pinned v4 QML | 976 |
| Pinned v4 XML used for metadata caveat | 5,759 |
| Total | 57,653 |

No unused duplicate metadata manifest is counted. Compact metadata embeds all
the query/label/grid/provenance information returned by the source loader; normal
compact decoding requires its two measured files only.

Every candidate below preserves **all 6,684,255 raw 0/1 values plus all 6,684,255 mask
bits**, identical metadata, and all 17 complete query dictionaries. Bytes include
the full payload/header, JSON index, grid, class labels, citation and provenance.

| Candidate | Chunk side | Payload bytes | Metadata/index bytes | Total bytes |
| --- | ---: | ---: | ---: | ---: |
| binary_packed_zstd3 | 256 | 21,491 | 34,870 | 56,361 |
| binary_byte_zstd3 | 256 | 39,346 | 34,927 | 74,273 |
| binary_packed_zstd19 | 256 | 18,576 | 34,860 | 53,436 |
| binary_byte_zstd19 | 256 | 22,228 | 34,883 | 57,111 |
| binary_packed_zstd3 | 1024 | 19,811 | 6,149 | 25,960 |
| binary_byte_zstd3 | 1024 | 41,722 | 6,151 | 47,873 |
| **binary_packed_zstd19** | **1024** | **15,310** | **6,149** | **21,459** |
| binary_byte_zstd19 | 1024 | 25,270 | 6,152 | 31,422 |

**Measured smallest encoded and normal-loader storage choice: packed level 19,
chunk side 1024, 21,459 bytes.** This saves 36,194 bytes (62.78%) against the 57,653-byte
source-loader inputs. This is a JRC-only representation result, with no extension
of any accepted Hansen percentage.

Conservative retained-provenance comparison: retain the same 11,415-byte
provenance/QML/XML files alongside both representations, even though the compact
decoder does not read them. Original remains 57,653 bytes; compact becomes 32,874:
**24,779 bytes (42.98%) less**. Retaining the exact common supplier CSV/GeoJSON
(19,265 bytes) on both sides gives 76,918 versus 52,139 bytes, or 32.21% less. These
views expose the metadata choice rather than using it to inflate the denominator.
The byte level 3 / chunk 256 candidate loses even to the normal source-loader total;
all losing candidates remain archived.

## Timing and resources

Seven repetitions after two warmups, same full AOI/native support, same query
cohort. In-process source and compact hot queries both use already loaded arrays.
Decode includes checksums, bounds/range checks and all array assembly. Encoding
includes packing/compression/metadata and buffered writes/close, with no fsync;
durable disk latency is excluded. Median wall milliseconds:

| Candidate | Chunk | Encode | Full decode | All 17 hot queries |
| --- | ---: | ---: | ---: | ---: |
| binary_packed_zstd3 | 256 | 2.961 | 3.988 | 5.044 |
| binary_byte_zstd3 | 256 | 5.291 | 6.681 | 5.106 |
| binary_packed_zstd19 | 256 | 51.478 | 3.990 | 5.002 |
| binary_byte_zstd19 | 256 | 365.979 | 6.950 | 5.153 |
| binary_packed_zstd3 | 1024 | 2.221 | 2.950 | 5.326 |
| binary_byte_zstd3 | 1024 | 5.769 | 5.425 | 5.203 |
| binary_packed_zstd19 | 1024 | 223.097 | 2.919 | 4.990 |
| binary_byte_zstd19 | 1024 | 111.228 | 5.345 | 5.177 |

Source load median 6.244 ms; source hot 17-query median 5.022 ms. The 4.990 versus 5.022
hot medians do not support a meaningful generalized speed claim. Level 19 saves
4,501 bytes versus packed level 3 at 1024 while costing 223.097 ms versus 2.221 ms
preprocessing; storage was the declared selection criterion.

Fresh ordinary Python child processes measured source/store load plus 17 queries,
after imports and common plot loading. OS cache is warm; this is **process-cold,
not disk-cold**. Parent spawn-inclusive timing is separately recorded.

| Process-cold path | Inner median ms | Inner p95 ms | Spawn-inclusive median ms | Median peak RSS bytes | Maximum peak RSS bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Source chip loader + 17 queries | 17.327 | 19.452 | 148.143 | 95,911,936 | 95,977,472 |
| Selected compact loader + 17 queries | 10.018 | 10.715 | 141.831 | 84,541,440 | 84,836,352 |

RSS is the whole child high-water mark including imports, reported in bytes on
this macOS host (the code labels Linux units KiB). These are local measurements
with seven samples, not robust tail-latency estimates. Source-window readback,
proof verification, frontend and full application memory are outside these timed
scopes. Every child answer digest is checked against the actual query output.

Environment: Python 3.14.7, NumPy 2.5.4, Rasterio 1.5.2 / GDAL 3.12.2,
Shapely 2.1.2, libzstd 1.5.7, macOS 26.6.2 arm64, 10 logical CPUs. The archive includes
all wall/CPU samples and min/median/p95; environment is part of the experiment
identity so different implementations/runtimes do not reuse the same store path.

## Proof gate and forged controls

Read `validator-report.md` before implementation. The JRC gate explicitly covers
the prior V1–V3 failure modes, rather than accepting a content hash as truth:

- Reopen fixed pinned chip/provenance/QML/XML and pinned exact plot inputs.
- Reopen the selected store and compare the **entire** raw array, mask and
  metadata before checking benchmark path identity. A false off-plot raw/mask
  claim therefore fails for pixel fidelity, not merely a stale archive.
- Reconstruct every source/compact result, independent scalar result, exact
  geometry/hash, evidence record, receipt field/hash, summary and content hash.
- Bind a supplied benchmark to current input/cohort/query/code/runtime/settings
  identity, archived identity and content-addressed measurement. Recompute actual
  source/store file hashes and byte sums, fully decode/requery all eight measured
  candidates, and recalculate smallest encoded and overall choices.
- Recalculate timing summaries from recorded samples and check child answer
  digests. If the full tile cache is present, repeat source-window pixels/masks;
  otherwise verify the archived readback contract against pinned source identity
  while keeping normal runtime independent of the full cache.

Fresh measured export equals the current canonical companion and is accepted.
A freshly generated metric-free export is also accepted. **Seventeen rehashed
negative controls reject**, including off-plot pixel and validity changes, wrong
summary, wrong receipt query/year/source/fidelity, changed evidence/geometry/class
label/plot result/comparison, wrong benchmark cohort/vintage/bytes/winner. A
self-consistent forged benchmark plus forged archive and matching run hashes is
also rejected because its claimed byte total disagrees with actual source files.
The forged archive is simulated in the test process; real archives are untouched.

Persistent control decisions (two fresh positives + 17 negatives, all expected):
`data/experimental/jrc-engine/proof-controls-90fe9703a08ab8fe78f565ad7dcd8096279e4490393035ec123250c9fc9609f5.json`.
Both bad off-plot stores also fail the exporter. Tests retain raw 1 under invalid
masks, reject malformed values/shapes/masks/grids, and cover valid 0, partial
positive/negative, missing band, outside support, no centers, holes/hole
boundaries, multipart islands, exact decimal boundary and a one-ULP exclusion.
Random query seed 20261013 covers 80 further cases; codec seed 414 covers skinny,
single-cell and chunk-edge grids with mixed validity. Every candidate is tested
on the complete real chip as well as synthetic masks.

The decoder checks index/header version and hashes, exact chunk tiling/indices/
offsets, compressed/raw sizes, nonzero padding, raw binary range, truncated and
trailing frames/data, decompression output and advertised history bounds. Limits
are 16,777,216 cells, 16,384 per dimension, 65,536 chunks, chunk side 2048, index 8 MiB and
payload 64 MiB; the reused bounded zstd reader caps advertised history at 8 MiB.
Malformed index tests trap allocation to ensure rejection precedes output arrays.
Tests include a correctly rehashed frame advertising 1 GiB history and corrupted
raw checksums. None requires a dangerous stress allocation.

## Input/code identities and limits

Pinned input SHA-256:

```text
source tile fbae885505a5ee7a481775401f27c23b1b8ef1e5451b69156a70c04aa42f38d7
native chip 3019c19bca064ac8f31747da856f40ce04146da6759c2f36dc30d0ff2e07e7c5
provenance  c99d7780af8778be4c1ad7123c31fbee3b09401d3ff4d48e2eeece15ea434f7b
v4 QML      d089a9d21a10537a13c77f206fd8ac844d364800b48580361893179d902080b0
v4 XML      cdccfb393e306cf6775a2041263c09885a275a67b8098acde6536f06358a66b9
```

JRC production code SHA-256 (the archived identity additionally fingerprints all
five reused engine helper modules, plus supplier input hashes and runtime):

```text
jrc.py           295c2ad1caa6a1b5c42b0bc8ed847b6922d3bb88bc1ce19154f63e4f7e877ab3
jrc_codec.py     7c70fd55564b8861612961b397d1583f3db538493034371598ef60670f198fad
jrc_oracle.py    c5b89b451007a9238803c8f24f208daeded963a7bdb352c7117cf2efc8fd8c2c
jrc_benchmark.py 19eceb18e21838e5fc19b2989bc853e27061177b6f50e5622b93fc02ab5fc414
jrc_proof.py     b28a46452f4649ff6057ed7f0ee1f03171cec0c19903da0326c46f677c4c32c5
```

Hashes are reproducibility/integrity bindings, not signatures. The verifier
trusts the local pinned input identities and implementation. Historical timing
records cannot authenticate themselves against an attacker who controls the
whole trusted workspace. The independent oracle shares topology validation and
underlying source arrays, and does not establish satellite accuracy. Codec bounds
are tested limits, not a comprehensive adversarial-parser certification.

Store writes are serialized in this workflow; replacing the two store files is
not a transactional concurrent-reader/writer protocol. Encoding is deterministic
for identical input/settings in the recorded runtime; cross-libzstd byte identity
is not promised. No indexed JRC window query is introduced; any later indexed
path must select on the original declared chip lattice before fetching samples.

The companion is complete for lead review. Volta owns package/main-artifact/app
integration and any final choice to display it; this handoff does not modify or
extend accepted Hansen metrics or compliance semantics.

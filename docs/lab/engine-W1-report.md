# W1 codec handoff

Status: **cycles 1 and 2 COMPLETE — ready for engine-lead review**.
First handoff completed at 02:11 UTC; cycle 2 measured at 02:16 UTC on 2026-10-13.
No integration blocker. No core files or final artifacts were edited. No Git
mutations, additional dependencies, private uploads, external publication, or
agent spawning were performed. The master should relay this report to the lead.

## First handoff: owned deliverable and interfaces

- `engine/codecs.py`: deterministic chunked encoder, bounded checked decoder,
  and indexed window reader. No dependency on core modules.
- `engine/tests/test_codecs.py`: 17 unittest methods with real-source checks and
  synthetic/adversarial subcases.
- `data/experimental/w1/measure_codecs.py`: bounded exploratory measurement runner.
- `data/experimental/w1/codec-measurements.json`: measured samples, environment,
  source identities, roundtrip/query checks, candidate file hashes.
- Scratch stores are under `data/experimental/w1/measure-stores/` and `smoke/`;
  the symmetric original-metadata manifest is `baseline-metadata.json`.

Public API exactly matches the dispatched signatures:

```python
CANDIDATES = ('packed14_zstd', 'uint16_zstd', 'separate_zstd', 'bitplane_zstd')
encode_store(bands, masks, metadata, path, candidate, chunk_size=128) -> dict
decode_store(path) -> (bands, masks, original_metadata)
read_window(path, row_start, row_stop, col_start, col_stop) -> (bands, masks, window_metadata)
```

`path` is a dedicated candidate directory. The encode report contains
`candidate`, `total_bytes`, `payload_bytes`, `metadata_index_bytes`, `encode_ms`,
`chunk_size`, and `files = [{'path': 'index.json', 'bytes': ...},
{'path': 'payload.bin', 'bytes': ...}]`. Every required decoding file is counted.
Timing is returned only; it is absent from store bytes.

Full decode returns uint8 bands, bool masks, and the identical JSON-native
metadata dictionary, including extra provenance. Metadata containing non-JSON
types (e.g. tuples, NumPy scalars, non-string dictionary keys), nonfinite values,
or excessive nesting is rejected rather than silently changed. All raw values
are preserved and range checked, including invalid-mask cells.

Window reads reject empty, noninteger, or out-of-coverage windows. They decode
only intersecting chunks and return updated shape and affine origin, preserving
other metadata. For `[a,b,c,d,e,f]`, the origin is shifted to
`[c + col_start*a + row_start*b, f + col_start*d + row_start*e]`.
All 17 supplied plots also give identical results when evaluated on their
selected-cell bounding windows. This uses the lead's evaluator on both paths;
it is codec integration evidence, not W2's independent oracle.

## Format and bounded validation

- `payload.bin` begins with `PLCODEC1` plus uint32 little-endian version 1.
  The remaining data is a deterministic row-major sequence of independent
  Zstandard frames at fixed level 3. No dictionaries, timestamps, random headers,
  or pickle are used.
- `index.json` uses canonical JSON and records version, candidate, full original
  metadata/grid/CRS, chunk positions/shapes/indices, each stream's offset,
  compressed/raw byte counts, and compressed/raw SHA-256. It includes a payload
  SHA-256 and an index SHA-256 computed with the latter field excluded.
- Packed14 interleaves each cell's 7 canopy, 5 loss-year and 2 datamask bits.
  Uint16 uses the same 14-bit word in little-endian bytes with two reserved bits.
  Bitplane groups the same 14 bit positions by plane before packing. Separate
  stores three independent byte-band streams per chunk. All four have a separate
  packed three-band validity-mask stream. Unused packed padding/reserved bits
  must be zero.
- Chunks tile the complete grid without gaps, overlap, duplicate indices,
  reordered offsets, or extra streams. Dimensions, chunk shapes, raw byte counts,
  offsets, file length and magic are checked before output arrays are allocated.
- Limits: each dimension at most 16,384, grid at most 16,777,216 cells, chunk side
  1–1,024, at most 65,536 chunks, index at most 16 MiB, payload at most 128 MiB,
  metadata nesting at most 32 levels. These are implementation limits, not claims
  to handle all global rasters. The index cap may reject a store before other
  limits are reached.
- Each compressed frame must advertise the expected bounded raw size, require no
  dictionary, and have at most an 8 MiB advertised window. Output is limited to
  expected raw size plus one byte; exact size/EOF and absence of trailing frames
  or data are checked. A library-only window setting accepted a tiny frame
  advertising a 1 GiB window in our local experiment, so the implementation also
  parses and rejects oversized window descriptors explicitly. The regression
  tests a real mutated frame; no large allocation is required.

The bounded decompressor follows the [Python 3.14 Zstandard API](https://docs.python.org/3.14/library/compression.zstd.html).
The explicit header/window test follows [RFC 8878 sections 3.1.1.1.1–2](https://www.rfc-editor.org/rfc/rfc8878.html#section-3.1.1.1.1).

## Verification

Run from repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv-data/bin/python -m unittest engine.tests.test_codecs -v
PYTHONDONTWRITEBYTECODE=1 .venv-data/bin/python data/experimental/w1/measure_codecs.py
```

Final test run: **17 methods passed in 0.571 seconds**. Earlier test iterations
used the same unittest command without the bytecode environment setting. The
measurement runner was rerun after the decoder's explicit window check was added.

- Every source cell round-trips for all four candidates: 744,732 spatial cells,
  2,234,196 raw band values and the same number of validity-mask entries.
- All 7,878 legal canopy/loss/datamask value triplets round-trip, including
  completely masked raw values. Additional fixtures include one-cell and skinny
  grids, all maxima, noncontiguous arrays, and deterministic random seeds
  13514–13523 across chunk sides 1, 3, 7, 8 and 17.
- Invalid ranges are rejected before writing even when their masks are false.
  Float/signed/negative inputs, malformed shapes/masks/metadata and invalid chunk
  sizes are rejected.
- Tests cover bad payload magic/version, index checksums, raw/compressed/payload
  checksums, truncation/trailing bytes and concatenated frames, duplicate/invalid
  JSON, index bounds, illegal dimensions/chunk indices/shapes/offsets/raw sizes,
  padding/reserved bits, illegal decoded raw values, output/window bounds, and
  local symlink/unrelated-file rejection. Invalid layouts are tested with an
  allocation trap to prove they are rejected before `np.empty`.
- Re-encoding identical input/settings produces identical index and payload
  bytes. Encoded file accounting equals actual necessary file sizes.
- Window tests check pixels/masks, shape, north-up and rotated affine origin,
  chunk-boundary reads, and that only intersecting frames are decompressed.
- The exploratory runner checked 16 candidate/chunk combinations on the same
  full 1233×604 source. **Zero mismatches across all 17 real plot results for each
  combination**, plus exact full arrays/masks/metadata and a 32×32 window.

Source SHA-256 identities in the measurement JSON:

```text
treecover2000 f69b3f59e943a9830cd4076fa71c8f09c301de6f6635a683db536c5d956fdfcc
lossyear      7a0307acecab4056bdbe09d200834e979daea17579f5e17b504050a8307150cf
datamask      041e62e410f908c47a7c48fe16f8884460ea69d5103fc753bdb5bec9a044d458
```

## Measured candidate sizes and tradeoffs

Default 128-cell chunks; byte counts include all required index/provenance and
payload/header bytes. Timings below are median wall milliseconds over five
same-process repetitions after one warmup, OS cache warm. Source loading is
excluded from encode; full decode includes index parsing/validation, all
decompression, array assembly, range checks and hashes. These are preliminary
codec timings; W3 owns the canonical benchmark/resource/process-cold comparison.

| Candidate | Payload bytes | Metadata/index bytes | Total bytes | Encode ms | Full decode ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| packed14_zstd | 889,391 | 25,798 | 915,189 | 19.233 | 13.564 |
| uint16_zstd | 736,387 | 25,790 | 762,177 | 6.474 | 4.549 |
| separate_zstd | 584,578 | 47,378 | 631,956 | 6.622 | 4.936 |
| bitplane_zstd | 745,231 | 25,794 | 771,025 | 21.810 | 8.007 |

Because default chunk overhead was material, one bounded sweep tested larger
chunk sides. All sizes below are total bytes on identical support and all are
exact; no crop savings are counted.

| Candidate | 128 | 256 | 512 | 1024 |
| --- | ---: | ---: | ---: | ---: |
| packed14_zstd | 915,189 | 885,759 | 860,582 | 851,585 |
| uint16_zstd | 762,177 | 733,199 | 724,075 | 721,219 |
| separate_zstd | 631,956 | 592,190 | 597,635 | 588,556 |
| bitplane_zstd | 771,025 | 759,940 | 743,699 | 748,618 |

**Smallest tested candidate: separate_zstd at 1024, 588,556 bytes.** This still
does **not** beat the actual three DEFLATE GeoTIFF chips: 576,999 payload bytes,
or 577,946 bytes with the same 947-byte original metadata manifest explicitly
stored in W1 scratch. The smallest candidate is 1.84% larger than that symmetric
reference. No storage-reduction claim is supported by these candidates.

Separate_zstd at 256 is only 3,634 bytes larger than at 1024 and its measured
32×32 window read is 0.580 ms median versus 2.005 ms at 1024. These are actual
grid reads, not complete polygon queries. The reader validates the whole index
but decompresses intersecting chunks only. Different window locations/chunk
intersections can alter the tradeoff; 256 is a useful follow-up configuration for
W3 rather than a declared universal winner. Default remains the required 128.

Packed14 and bitplane lose here despite using fewer raw bits; bit-width alone
does not predict compressed size. These measurements justify retaining the
separate-band comparator and reporting the negative packed result. No sparse
event representation was added: the four complete candidates already provide a
bounded, reviewable experiment without additional format complexity.

Measurement environment: Python 3.14.7, NumPy 2.5.4, libzstd 1.5.7,
macOS 26.6.2 arm64. The JSON records every wall/CPU sample plus median/min/p95
for encode, full decode, window read, and fairly preloaded source/compact batches
of 17 hot queries. Five-sample p95 is only an exploratory statistic. No disk-cold,
memory/RSS, UI timing, supplier-derived ML ground truth, legal-compliance
fidelity, or satellite-source accuracy claim is made.

## Limitations and integration notes

- Hashes detect accidental corruption; anyone able to rewrite payload and index
  can also rewrite hashes. This is not authenticated storage. Safety claims are
  limited to implemented caps and the tested rejection cases; this is not a
  general adversarial-parser audit.
- Window reads validate index/header/file length and selected stream hashes;
  they intentionally do not validate the global payload hash or unselected
  chunks. Use full decode for complete-store integrity verification.
- Array limits and zstd windows are bounded, but peak process memory was not
  measured by W1. Canonical resource benchmarking belongs to W3.
- Store replacement publishes payload then index. Concurrent readers may reject
  the transitional checksum; concurrent writers are unsupported. Only owned
  temporary files are cleaned up. Use separate candidate directories/serialize
  rewrites. Parent-directory filesystem races are not audited.
- Determinism was demonstrated in this environment for identical data/settings;
  output bytes are not promised identical across different libzstd versions.
- Full source/compact query equality here uses the same core evaluator and proves
  encoding preservation. W2 must supply independent query-implementation checks.
  Metadata affine shifts can incur normal floating-point arithmetic rounding;
  all real plot-window comparisons and representable synthetic shifts passed.
- Full original metadata preserves source path/hash identity. The index's own
  layout is not a replacement for legal provenance or source layer limitations.
- No required dependency was missing; no changes are requested to core APIs.

## Cycle 2 follow-up — complete

Read the actual lead request in `docs/lab/engine-review-notes.md` at 02:13 UTC.
The first handoff and its measured results above are retained as historical
evidence. W1 added only `separate_zstd_l9` and `separate_zstd_l19`, fixed
levels 9 and 19, preserving all existing v1 stores and extending safety tests.
New measurements are in `data/experimental/w1/codec-measurements-cycle2.json`;
the first-run JSON and its stores are preserved. No canonical artifacts or other
workers' files were edited.

Accounting correction for subsequent comparisons: the stabilized source loader
now requires `data/public/provenance.json`. The first baseline figure above
did not include that acquisition manifest; it is not the complete current source
load path. Cycle 2 will count the manifest explicitly and publish a symmetric
common-provenance view as well. W3 retains responsibility for canonical accounting.

Window warning from lead's actual witness: source row1/col1 x center is
98.772625, while regenerating it from the shifted transform yields
98.77262499999999. A boundary polygon selects one cell on the original grid and
zero on the shifted grid. The 17 real plot checks passing does not eliminate
this hazard. `read_window` preserves raw values but must not be used to regenerate
query centers from the shifted grid. Select original global centers once, then
fetch their values/masks. Lead owns that query integration; W1 will not change it.

### Current APIs and compatibility

Current `CANDIDATES` is the original four names, in their original order, followed
by `separate_zstd_l9` and `separate_zstd_l19`. All signatures are unchanged.
`CANDIDATE_LEVELS` maps each candidate to its fixed integer level. Original
candidates still declare level 3. The encode report additionally exposes
`compression_level`. The store format/version remains v1, with the same band,
mask, stream-layout and safety semantics. Higher levels apply to all four
separate-band/mask streams.

Index validation requires the exact candidate-specific integer level; a valid
recomputed checksum does not permit relabeling a level3 store as level9/19 or
declaring a conflicting/noninteger compression level. New aliases use the same
separate-band stream layout. The four original candidates' stored bytes are
unchanged for identical inputs in this environment.

The cycle2 runner verified **all 16 actual cycle1 store directories** against
their recorded file SHA-256, then decoded them with the new code and compared
full raw bands, masks and original metadata. A separate unit test preserves
frozen cycle1 minimal-store hashes for all four original candidates. That byte
compatibility assertion is explicitly limited to the recorded libzstd 1.5.7;
the format still decodes independently of compressor-byte determinism.

### Commands and verification

```sh
PYTHONDONTWRITEBYTECODE=1 .venv-data/bin/python -m unittest engine.tests.test_codecs -v
PYTHONDONTWRITEBYTECODE=1 .venv-data/bin/python data/experimental/w1/measure_codecs.py --cycle2
```

Latest test run: **19 methods passed in 1.412 seconds**. The roundtrip, real-grid,
all-legal-triplet, deterministic encoding, random-boundary and window tests now
cover all six candidates. Shared malformed-store tests run for each candidate:
magic/version, truncation/trailing data, compressed/raw/index/payload hashes,
illegal dimensions/indices/shapes/offsets/raw sizes, invalid JSON, decompression
bounds, invalid input and unrelated-file/symlink rejection. New separate variants
also check all illegal band values and mask padding. New tests explicitly reject
mismatched candidate/level declarations and preserve cycle1 byte compatibility.

The cycle2 runner tested separate-band levels 3, 9 and 19 at chunk sides 128,
256, 512 and 1024 on the same
1233×604 full source. Every one of the **12 configurations** round-trips all raw
values/masks/metadata, matches the sampled window, and has **zero mismatches
across all 17 real plot query dictionaries**. Level 19 at chunk sides 512 and
1024 was measured
because cycle1 showed material index savings at larger chunk sizes. None of these
checks claims independent source accuracy or legal compliance.

Measurements have five repetitions, one warmup, process/OS cache warm as before.
The runner now records code hashes and UTC measurement time. Encode timing covers
buffered file write/close/replace, with no `fsync`; durable disk-write latency is
excluded. Existing measurement JSON is never overwritten: replays receive a
content-hash suffix. Cycle2 stores are in `measure-stores-cycle2/` and cannot
replace cycle1 stores.

### Complete data storage accounting

The source loader requires chips plus the **8,294-byte acquisition manifest**.
Current source-load data bytes are therefore **585,293**, before geometry input.
The optional generated original-metadata archive adds 947 bytes, giving 586,240;
this optional file is not read by `load_source`. It is reported separately rather
than used to improve the apparent comparison.

For a symmetric complete review-data comparison, both paths retain all common
inputs below. Acquisition provenance is counted for the compact path even though
`decode_store` itself needs only its two store files. Supplier CSV/geometry are
shared inputs to `load_plots`/review, rather than hidden outside the totals.
Runtime code/dependencies and UI assets are excluded equally from this data-only
storage scope.

| Common file | Bytes |
| --- | ---: |
| `data/public/provenance.json` | 8,294 |
| Exact supplied CSV | 13,381 |
| Exact supplied GeoJSON | 5,884 |
| Total common review inputs | 27,559 |

Original full review-data baseline: **576,999 + 27,559 = 604,558 bytes**. Native
GeoTIFF grid/header bytes are already inside the 576,999. The separate optional
947-byte metadata archive is excluded from this conservative baseline. Source,
provenance, CSV and GeoJSON hashes are in the cycle2 JSON.

| Candidate | Chunk | Payload bytes | Metadata/index bytes | Decode-required total | Total with all common review inputs |
| --- | ---: | ---: | ---: | ---: | ---: |
| separate_zstd | 128 | 584,578 | 47,378 | 631,956 | 659,515 |
| separate_zstd_l9 | 128 | 562,504 | 47,378 | 609,882 | 637,441 |
| separate_zstd_l19 | 128 | 533,107 | 47,373 | 580,480 | 608,039 |
| separate_zstd | 256 | 577,036 | 15,154 | 592,190 | 619,749 |
| separate_zstd_l9 | 256 | 559,752 | 15,156 | 574,908 | 602,467 |
| separate_zstd_l19 | 256 | 528,069 | 15,152 | 543,221 | 570,780 |
| separate_zstd | 512 | 590,782 | 6,853 | 597,635 | 625,194 |
| separate_zstd_l9 | 512 | 563,053 | 6,854 | 569,907 | 597,466 |
| separate_zstd_l19 | 512 | 531,266 | 6,856 | 538,122 | 565,681 |
| separate_zstd | 1024 | 585,396 | 3,160 | 588,556 | 616,115 |
| separate_zstd_l9 | 1024 | 559,708 | 3,163 | 562,871 | 590,430 |
| separate_zstd_l19 | 1024 | 531,847 | 3,165 | 535,012 | 562,571 |

**Smallest tested complete encoded store: separate_zstd_l19 at chunk side 1024,
535,012 bytes.** Its full review-data total is 562,571 bytes versus 604,558 bytes
original: a measured
41,987-byte, **6.95% reduction** with identical common provenance/supplier inputs.
The store total alone is 7.28% below the original chip-only bytes, but the 6.95%
figure is the complete symmetric review-data comparison. The default 128 variant
still loses: even level 19 has 608,039 full-review bytes versus 604,558 original.
No payload-only storage-win claim is made.

Smallest store path for W3/lead inspection:
`data/experimental/w1/measure-stores-cycle2/separate_zstd_l19-1024`.
This is an exploratory candidate, not the final accepted artifact/store binding.
W3 and lead own canonical benchmarking and selection.

### Measured preprocessing and window tradeoff

Median wall milliseconds; full decode includes all integrity/range checks;
window read is the same fixed 32×32 IO window, not a polygon query:

| Candidate | Chunk | Encode ms | Full decode ms | Window read ms |
| --- | ---: | ---: | ---: | ---: |
| separate_zstd | 256 | 5.427 | 3.771 | 0.612 |
| separate_zstd_l9 | 256 | 22.206 | 3.446 | 0.622 |
| separate_zstd_l19 | 256 | 272.265 | 3.844 | 0.636 |
| separate_zstd | 512 | 5.815 | 3.650 | 1.127 |
| separate_zstd_l9 | 512 | 24.618 | 3.244 | 1.093 |
| separate_zstd_l19 | 512 | 245.431 | 3.536 | 1.049 |
| separate_zstd | 1024 | 5.224 | 2.673 | 1.974 |
| separate_zstd_l9 | 1024 | 18.362 | 2.731 | 1.957 |
| separate_zstd_l19 | 1024 | 217.412 | 2.929 | 2.104 |

Level 19 at chunk side 256 costs 8,209 additional bytes versus 1024, while its
sampled window is 0.636 ms versus 2.104 ms. W3 should evaluate representative plot access before
selecting a chunk size. Higher preprocessing cost is visible rather than hidden:
level 19 at chunk side 1024 takes 217.412 ms median encode versus 5.224 ms for
level 3. CPU samples,
p95/min, per-file hashes and all sample values are retained in cycle2 JSON. These
are local exploratory measurements, not process-cold, disk-cold, resource/RSS or
UI benchmarks. All first-handoff safety/integrity/concurrency limitations remain.

No blocker or additional core API change is requested. Cycle2 is ready for lead
review and W3 measurements; first results remain available as losing candidates.

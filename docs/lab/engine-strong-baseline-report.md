# Strong-control proof-hardening checkpoint — 2026-10-13T04:21:21.566394+00:00

Master + Volta: **implementation and focused worker checks PASS; independent acceptance pending**. Stopping at the human-requested checkpoint. No more experiments or tuning are running. Feynman can now recheck the fresh positive and six self-consistent forgeries. The previous bundle inventory is stale after these code/artifact changes; Volta must regenerate it before copied-bundle validation. This worker did not run the validator-owned scripts or write their reports.

Changed implementation files: `engine/strong_baseline_measure.py`, new `engine/strong_baseline_validation.py`, and `engine/tests/test_strong_baseline.py`. Updated only additive `artifacts/strong-baseline-v1.json`, new content-addressed files below `artifacts/strong-baseline-stores/`, this report, and owned scratch `data/experimental/strong-baseline/` (including `proof-hardening-checks.json` and the implementation replacement text). No Hansen accepted/JRC/source files, dependencies, Git state, or other workers' files were changed by this work. `engine/strong_baseline.py` was read-only during this revision.

Strict canonical JSON comparisons now reconstruct source/custom/control proof, counts, nested comparison flags, complete storage and preprocessing reports, environment, method and common-input/derived structures. Unknown/missing keys are rejected. Settings require unique supported integer blocks, level19/predictor1/band interleave, bounded integer repetitions/warmups, and an exactly matching ordered control set. Timing vectors require the declared sample count, finite nonnegative numeric entries, reconstructed summaries and consistent cold load+query sums. RSS records require positive typed counts and consistent unit conversion. Non-JSON types and nonfinite JSON values are rejected. All changed modules compile successfully.

`engine/export.py` is included in `CODE_NAMES`/the guard as explicitly requested, along with the new validation helper. Feynman's correction is acknowledged: the currently imported `differing_fields` is defined in `engine.benchmark`, already guarded; export.py is an additional requested binding, not a reproduced missing active import.

Fresh additive experiment: `exp-7daaf163af701f29eefac7f988a7b556ec9e9c84c74417af11bc9d72691e9ebc`.
Archive: `artifacts/strong-baseline-stores/exp-7daaf163af701f29eefac7f988a7b556ec9e9c84c74417af11bc9d72691e9ebc/runs/run-88872a2c4746ed0a2f0666e538712c8334f65ef8316cf952c0cb2428ad10332c.json`.
Archive SHA256: `8b8a6054fcc0d8b6b7b57da8c2fa4afd8845e11638ba5125796c6fc492625623`.
Current artifact SHA256: `f36e83f4d8df214eb5770a9eeb906f3f4a6f74ec224ea9f7d04d0e20a36bc80b`.

The already-running refresh completed with the existing256/512controls, seven repetitions/two hot warmups and unchanged methods. No new parameter search. Required bytes remain **532444 for256**, **537920 for512**, versus immutable accepted custom **535012** and native required source **585293**. Old runs remain historical. These new timings are stored in the fresh archive; older timing numbers in the historical report below are not the new run. OS cache remains uncontrolled/likely warm, never disk-cold.

Executed successfully:

```sh
.venv-data/bin/python -B -m engine.strong_baseline --blocks 256 512
.venv-data/bin/python -B -m unittest engine.tests.test_strong_baseline -q
.venv-data/bin/python -B -m engine.strong_baseline --verify artifacts/strong-baseline-v1.json
```

**20 tests passed in1.785s**. Fresh verifier returns valid=true, two controls,17real plots and accepted_artifacts_unchanged=true. The new test rehashes payload/archive/run identity and rebinds experiment/store paths where needed; it checks a fresh positive before negatives. Detailed actual reasons and forged-payload digests: `data/experimental/strong-baseline/proof-hardening-checks.json`.

| Validator forgery | Actual rejection |
| --- | --- |
| Integer1 replacing proof true | control full-value/mask/metadata/query proof claim mismatch |
| Hot timing reduced to one sample | timing sample count differs from settings |
| Cold timing reduced to one sample | timing sample count differs from settings |
| Encoder wall time -1ms | encode_wall_ms: finite nonnegative number required |
| Identity level3 with level19 stores | unsupported constant settings |
| Remove declared block512 control | control set does not match identity settings |

Six additional rehashed negatives reject source float counts, custom numeric booleans, nested numeric booleans, unknown proof fields, common-input float counts and unknown derived comparison fields. Existing off-plot raw/mask/metadata/byte forgeries still reject after making their rehashed fixtures consistent with the stricter schema. An initial refresh stopped before publishing because the verifier looked for the custom compression level in the wrong index field; that implementation lookup was corrected to `compression.level`, and the successful fresh run above replaced only the additive artifact.

Accepted Hansen hashes remain:
- benchmark-v1.json: `a356ce606eec338d9c2d7efafad406fa994915cb15506397e72bfc04d96a7e09`.
- retained-choice.json: `fe76fb839ed166d66f290a23f9e4c6d8497a188e8fac8a357cfdd8939aff8612`.

No implementation blocker remains in this bounded checkpoint. Independent Feynman/Volta review and regenerated bundle inventory remain **pending**, not claimed complete. Hashes prove local integrity, not external authentication or satellite accuracy.

Final signal: **W3 checkpoint saved; safe to close worker.**

---

## Historical pre-hardening report (superseded identity/timings; preserved evidence)

# Additive optimized GeoTIFF control — ready for Volta review

**The small storage advantage survives complete accounting and proof:** the
block256 GeoTIFF control requires **532,444 bytes**, versus **535,012 bytes** for
the accepted custom store: **2,568 bytes / 0.480% smaller**. This is an additive,
seen-AOI control result, not an accepted replacement. The accepted Hansen
benchmark, retained choice, store, measurement archive and production modules
remain byte-identical. The lead decides any later adoption/UI change.

First reviewable implementation, full measurements and proof were recorded by
03:26 UTC, approximately27minutes after dispatch. Final verification below includes
19 passing tests, immutable accepted-file checks and preserved prior run evidence.

## Scope and files

Read the full assignment, actual selector audit and its actual script at
`data/experimental/selector/study.py`, original/current grid/query/indexed APIs,
and the recorded one-ULP witness. Only assigned new paths were written:

- `engine/strong_baseline.py`: encode/decode/control indexed reader.
- `engine/strong_baseline_measure.py`: isolated measurements, file/code/input guards, separate archive and verifier.
- `engine/tests/test_strong_baseline.py`: synthetic, real-cohort and forged-proof tests.
- `artifacts/strong-baseline-v1.json` and `artifacts/strong-baseline-stores/`.
- Owned scratch under `data/experimental/strong-baseline/` and this report.

No former W3 benchmark/experiments edits, source writes, accepted-store writes,
other-worker/selector/JRC/app edits, dependencies, Git mutations, uploads,
publication, cloud spending or nested agents.

## API and representation

```python
encode_control(dataset, path, block_size=256) -> dict
decode_control(path) -> Dataset
with ControlWindowReader(path) as reader:
    bands, masks = reader.read_window(r0, r1, c0, c1)
    result = engine.indexed.evaluate_reader(reader, geometry)
```

The three-band uint8 GeoTIFF uses native EPSG:4326 grid, Zstd19, predictor1,
band interleave, MINISBLACK and explicit band descriptions. Allowed block sizes
are256/512 only. The required canonical `manifest.json` preserves the exact
source reconstruction metadata, candidate/settings, masks, required file
bytes/SHA-256 and a manifest checksum. This file is actually read by the decoder;
it is not the unused duplicate removed from the source baseline.

All three real band masks were checked to be all-valid. `implicit_all_valid`
records three zero invalid counts and uses zero mask payload bytes. Independently
different nontrivial masks use a separately stored, lossless, little-endian
three-band bitpack/Zstd3 stream. No shared TIFF mask can collapse band differences.
Raw values of invalid pixels are preserved. Original metadata, including all
source hashes/product/date information, is reconstructed exactly.

The encoder refuses an existing destination. Repeats encode into owned scratch
and compare every file byte/hash against existing evidence. Full-file checksums
are verified before raster reads, with a256KiB bounded manifest, fixed filenames,
128MiB file cap, codec dimension/cell limits, header dtype/count/grid/settings
checks, and bounded mask decompression through the existing codec helper.
Path escapes, unknown files, symlinks, invalid raw ranges/types/shapes/CRS,
nonfinite metadata, implicit-mask contradictions and nonzero packed padding are
rejected. The mask frame has a size cap derived from its validated raw size.
MaskedArray inputs are rejected in favor of explicit raw arrays plus masks.
These are tested local-file safeguards, not a general malicious-GeoTIFF audit.

## Storage and complete fidelity

Every representation covers the same **604×1233 full native AOI**, 744,732 spatial
cells, 2,234,196 raw band values and 2,234,196 validity entries. No crop/tile-size
savings enter the denominator. Both controls and the accepted custom store passed
full values/masks/metadata equality, all17real plot dictionaries, and W2's
independent scalar oracle. No synthetic cases are counted as extra real plots.

| Representation | Raster/payload bytes | Required manifest/index bytes | Mask payload | Complete required bytes |
| --- | ---: | ---: | ---: | ---: |
| Original three DEFLATE TIFFs | 576,999 | 8,294 acquisition provenance | included/implicit in source | **585,293** |
| Accepted custom level19/chunk1024 | 531,847 | 3,165 | included in payload | **535,012** |
| GeoTIFF Zstd19/predictor1/block256 | 531,006 | 1,438 | 0, checked implicit mode | **532,444** |
| GeoTIFF Zstd19/predictor1/block512 | 536,482 | 1,438 | 0, checked implicit mode | **537,920** |

The preliminary selector total531,953 used947bytes of reconstruction-only
metadata. Complete control validation adds491bytes, giving532,444. Relative to
custom,841bytes of the advantage come from the raster payload and1,727bytes from
manifest/index size. The custom index provides per-chunk hash information that
the TIFF control does not duplicate; this is a real format/integrity tradeoff.

Block512 was the only added setting, justified by the preliminary audit's lower
encoding CPU but larger payload. It remains a measured loser on storage:2,908bytes
larger than accepted custom and5,476bytes larger than block256. No broad tuning
or claim of universal optimality is made.

The symmetric common-input view adds the same acquisition provenance and exact
supplier/geometry files to each representation, counting provenance once:
source604,558; custom562,571; control256560,003; control512565,479bytes. The common
supplier/geometry files total19,265bytes and provenance8,294bytes. No optional
unused source metadata is added to the necessary source total.

## Fair timing and resource results

All paths hash whole stored raster/payload files during reader/load initialization.
The expected metadata-file hash is also checked inside initialization for every
representation: acquisition JSON for source, index for custom, manifest for
control. Guards hash all inputs/stores before and after each measurement child;
therefore **OS file cache is uncontrolled/likely warm, never disk-cold**.

Full hot timings load the entire identical grid once, then two warmups and seven
17-query batches. Full process-cold timings use seven fresh ordinary Python
children and include full load/integrity validation plus17queries. Indexed hot
and fresh-process indexed timings use the same original global cell selection,
then each reader fetches the selected bounding window. Imports and common plot
reading are excluded from operation timers but included in separately recorded
startup-inclusive subprocess wall times. Children run sequentially with thread
limits set to one. UI/network costs are excluded.

**Integrity/cache distinction:** original and control TIFF readers keep GDAL
handles/block caches warm after initialization. The current custom indexed reader
has no decoded-chunk cache and additionally verifies selected compressed/raw
chunk hashes on every query. Control windows check file identity/stat changes
but do not perform per-tile SHA checks. Thus initialization integrity is aligned;
per-window integrity and cache policies are explicitly different. Indexed speed
is a result of these actual readers, not an unavoidable property of either format.

Latest archived run, milliseconds per complete17-query batch; median / p95:

| Representation | Full hot | Full process-cold | Indexed hot | Indexed process-cold |
| --- | ---: | ---: | ---: | ---: |
| Original source | 1.526 / 1.674 | 11.163 / 12.462 | 2.425 / 2.591 | 8.869 / 10.061 |
| Accepted custom | 1.476 / 1.607 | **5.867 / 6.277** | 27.717 / 29.240 | 29.038 / 30.183 |
| Control256 | 1.480 / 1.650 | 8.498 / 9.430 | **1.991 / 2.033** | **7.735 / 15.675** |
| Control512 | 1.484 / 1.717 | 8.766 / 11.355 | 2.061 / 2.439 | 8.482 / 8.793 |

The custom full-load path is faster than control. Control256 has faster indexed
medians, but its indexed process-cold p95 is worse than source in this small run
because of an outlier; it is preserved, not discarded. Seven-sample nearest-rank
p95 is simply the maximum. Raw wall/CPU samples, min/median/p95, separate load/query
costs and startup-inclusive measurements are all in JSON. Hot fully preloaded
queries are essentially the same computation; no useful codec-specific hot-query
speedup is established.

Fresh encoding was measured once per candidate in its own child, source load
excluded. Accepted custom was re-encoded into temporary owned scratch and proved
byte-identical, without modifying its accepted directory. Writes are buffered;
no durable-ingest/fsync performance claim is made.

| Representation | Encode wall ms | Encode CPU ms | Encode peak RSS bytes | Full-cold max RSS | Indexed-cold max RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Source | not re-created | unavailable | unavailable | 78,217,216 | 69,140,480 |
| Accepted custom scratch reproduction | 210.568 | 210.358 | **101,613,568** | 72,695,808 | 67,944,448 |
| Control256 | 302.488 | 295.550 | 163,741,696 | 76,087,296 | 69,976,064 |
| Control512 | 231.213 | 230.784 | 164,151,296 | 78,135,296 | 72,056,832 |

RSS is an isolated child lifetime peak including interpreter/imports/input data,
not incremental operation memory. Native macOS bytes are retained; Linux units
are normalized by the reused read-only helper. This is a small seen-AOI study
with uncontrolled host scheduling, not a held-out generalization or population
confidence interval. Storage repeats are deterministic here; timing noise remains.

Environment: Apple M5/Mac17,2,10logical CPUs,32GiB RAM, macOS26.6.2, Python3.14.7,
numpy2.5.4, rasterio1.5.2, GDAL3.12.2, shapely2.1.2. Control compression is GDAL
GeoTIFF ZSTD; custom/mask compression uses Python's standard-library Zstd. The
Python libzstd version is recorded separately; GDAL's linked libzstd version is
not asserted merely from the Python version.

## Proof, tests, reproduction and immutable evidence

Actual successful commands:

```sh
.venv-data/bin/python -B -m engine.strong_baseline --blocks 256 512
.venv-data/bin/python -B -m unittest engine.tests.test_strong_baseline -v
.venv-data/bin/python -B -m engine.strong_baseline --verify artifacts/strong-baseline-v1.json
```

The last verification was also performed automatically by the final measurement
runner before publishing the separate artifact. **19 tests pass**. Tests include
real full pixels/masks/exact metadata and17plot/oracle agreement; independently
different synthetic masks and masked raw values; implicit-mode validation;
invalid ranges/types/CRS; malformed/truncated/hash-changed files; header/manifest
shape/dtype mismatch; excessive dimensions before raster opening; bounded JSON;
fixed paths; mask padding/counts; read-window bounds/close/change detection;
original-lattice one-ULP regression; partial/outside/missing-band semantics;
nonmutation; fingerprint-race child rejection; and fresh artifact verification.

Four stronger negative controls rebuild archives and their hashes after changing
an off-plot pixel, an off-plot independent mask, reconstruction metadata, or a byte
claim. All are rejected. The three data changes leave **all17plot results equal**,
so full raw/mask/metadata verification is what rejects them. This avoids treating
plot equality as complete source fidelity. The exact one-ULP fixture selects1cell
with the original lattice and0with incorrectly reassociated window coordinates;
`evaluate_reader(ControlWindowReader(...))` preserves the original result.

A same-code repeated study preserved its prior archive hash and reproduced the
real control files byte-for-byte. Later environment-description refinement created
a new code fingerprint; previous successful runs remain in separate experiment
folders as historical evidence. No old result or accepted file was rewritten.

Current separate artifact: `artifacts/strong-baseline-v1.json`.
Current experiment: `exp-4f50de5cd9b90b2d6399cbd0835bc40ad9566b17b9406287a4194aff97f0e3d1`.
Current immutable measurement:
`artifacts/strong-baseline-stores/exp-4f50de5cd9b90b2d6399cbd0835bc40ad9566b17b9406287a4194aff97f0e3d1/runs/run-ed80ce7537ca5ae1c97745c40944dfe88de192772b707e78a3ab386245826adc.json`.
Archive SHA-256: `58196324069673203cff2e354cd68cce7c64975bdaec0d9fc26c047b3e96643e`.

Control256 store for independent review only:
`artifacts/strong-baseline-stores/exp-4f50de5cd9b90b2d6399cbd0835bc40ad9566b17b9406287a4194aff97f0e3d1/gtiff_zstd19_p1_b256`.
Its TIFF SHA-256 is
`d298e366fb7eecd20a9ca7019a2ee350983b3f537e0a0dd29a482d9e7dbb3d2a`;
required manifest SHA-256 is
`fcb86902162a0ba597bff56432fccdfee46491c0801ae8f597185bc72063be58`.
Block512 is preserved beside it as `gtiff_zstd19_p1_b512`.

Accepted immutable anchors verified throughout the experiment:

- Hansen benchmark SHA-256: `a356ce606eec338d9c2d7efafad406fa994915cb15506397e72bfc04d96a7e09`.
- Retained choice SHA-256: `fe76fb839ed166d66f290a23f9e4c6d8497a188e8fac8a357cfdd8939aff8612`.
- Accepted run archive SHA-256: `6db1b4bbed1f13e667c1485ad2816d875dd806ce76635ba5b8d9dc64cba8bfd1`.
- Accepted custom index/payload remain the bound535,012-byte level19/chunk1024 store under `exp-0109a8d6c4782217871315b92c63a971d11ebd164585c80981f24c55b4f68fea`.

No blocker remains. The result supports a modest standard-format storage advantage
and a substantial current indexed-reader advantage against the custom reader,
with slower full loading and higher encoding CPU/RSS. Lead scientific review
must weigh these tradeoffs; no accepted winner or production artifact is changed.

**Master relay: additive strong-baseline result, proof, tests and separate stores
are ready for Volta review.**

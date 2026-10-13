# Engine Sol worker dispatch — v1

Published by engine lead for master proxy dispatch. Read `docs/lab/charter.md`, `docs/lab/interface-v1.md`, this file, and actual relevant project references. Three independent Sol workers, reasoning medium/high as appropriate. Requested fast mode has no exposed field; do not claim it was set. Do not spawn other leads or hidden runtimes. No Git mutations, source edits, external publication/messages, private uploads, cloud spend. GitHub only authenticated gh. Shared workspace: edit ONLY assigned files. Existing `.venv-data` Python 3.14.7, numpy 2.5.4, rasterio 1.5.2, shapely 2.1.2. Python 3.14 standard library `compression.zstd` is available to try; coordinate before installing dependencies.

Write your findings/commands/results/blockers to `docs/lab/engine-Wn-report.md`; parent/master will relay arrival. Work toward first usable implementation in 20–35 minutes, then meaningful tests/experiments. Do not stop at a plan. Core lead will review and integrate. Source data stays immutable.

## Shared APIs (engine lead owns these)

`engine/model.py`:

```python
BAND_NAMES = ('treecover2000', 'lossyear', 'datamask')
@dataclass
class Dataset:
    bands: np.ndarray  # uint8 [3,height,width]; raw values, including masked cells
    masks: np.ndarray  # bool [3,height,width], True = band validity
    metadata: dict  # shape [height,width], transform [a,b,c,d,e,f], crs 'EPSG:4326'; source information may be additional
```

`engine/source.py`: `load_source(root: Path | None = None) -> Dataset`; `load_plots(root: Path | None = None) -> list[dict]` with plot_id, geometry exact GeoJSON, supplier exact CSV strings. Default root repository root.

`engine/query.py`: `evaluate(dataset: Dataset, geometry: dict, missing_bands: tuple[str,...] = ()) -> dict` follows interface-v1 result. `select_cells(metadata: dict, geometry: dict) -> tuple[np.ndarray,np.ndarray]` returns all selected global row/col indices, including outside chip. Native north-up grid only; invalid geometries rejected with ValueError, Polygon/MultiPolygon with holes accepted. Point centers included with `covers`, including boundary. Limits reject excessive bounding windows explicitly, not silently truncate. Metadata shape available to count coverage. Missing-band simulation uses missing_bands parameter; source loader itself requires three source bands. Every raw integer range is validated by source/codec.

Exact query output keys: selected_cell_count, in_coverage_cell_count, out_of_coverage_cell_count, valid_land_cell_count, unknown_cell_count, datamask_counts (`0`,`1`,`2`), canopy_histogram (length101 or null), lossyear_histogram (length26 or null), yearly_loss_counts (2001…2025 string keys or null), periods (2021-2023 and 2024-2025, values `{mapped_loss_present: bool|null, observed_loss_cell_count: int|null}`), support (`complete`,`partial`,`none`,`unavailable`), unknown_reasons (deterministic order described below).

Mask diagnostics count raw datamask classes only when datamask band validity is true. Unknown selected cells are union of datamask0, any invalid band mask, out-of-coverage (count each cell once). Valid land requires datamask1 and all band masks valid. Water is known but not analytical land. Missing required band disables analytical results; unknown_cell_count becomes selected_cell_count. Reasons order: no_selected_cells, out_of_coverage, nodata, band_mask_invalid, no_valid_land, then missing_band:<name> in BAND_NAMES order. no_valid_land reason applies whenever selected_cell_count>0 and valid_land_cell_count==0. support: missing bands→unavailable; zero selected or no valid land→none; unknown_cell_count>0→partial; else complete. Histograms/period observed counts null if no valid land, no selected cells, or missing band. Otherwise count observed valid-land pixels. Period flag true if positive observed count, false only when unknown_cell_count==0, otherwise null. Histograms are retained with partial support (resolved v0 contradiction).

## W1 — codec candidates and safe decoder

**Write ownership:** `engine/codecs.py`, `engine/tests/test_codecs.py`, optional `engine/codec_*.py`, `docs/lab/engine-W1-report.md`. Write experiment scratch only to `data/experimental/w1/`. Do NOT write engine/model.py, query.py, source.py, export.py, artifacts final outputs, benchmark.py or W2 files.

**API:**

```python
CANDIDATES: tuple[str,...]
def encode_store(bands: np.ndarray, masks: np.ndarray, metadata: dict,
                 path: Path, candidate: str, chunk_size: int = 128) -> dict: ...
def decode_store(path: Path) -> tuple[np.ndarray,np.ndarray,dict]: ...
```

Path is a candidate directory. Returned encode dict must include `candidate`, `total_bytes`, `payload_bytes`, `metadata_index_bytes`, `encode_ms`, `chunk_size`, `files` (relative file names/bytes). Total equals every file necessary to decode/query. JSON metadata/index includes format version, shape/grid/crs, candidate, chunk layout/offsets/sizes, hashes; preserve original metadata (decoder returns identical dict). If compression uses masks, preserve all band masks and raw masked values. Encode deterministically excluding timing report; no timestamps/random archive headers.

Implement packed14 candidate (7 canopy +5 loss +2 mask bits), uint16+zstd, separate-band zstd, and useful bitshuffle/bitplane alternative if feasible. Chunk payloads for fair indexed queries. Consider sparse event candidate only if preserves all raw source values and bounded complexity. Reject canopy outside0–100, loss outside0–25, datamask outside0–2 before packing, regardless of masks; reject floats, negative, malformed shapes/masks. Tests: random/synthetic/all real pixels roundtrip, invalid ranges, bad magic/version, truncation, trailing data, corrupt checksums, illegal dimensions/indices/offsets/padding, decompression bounds. Never allocate from unbounded malicious header; do not claim adversarial safety beyond tests. Avoid pickle.

Optional valuable API: `read_window(path, row_start,row_stop,col_start,col_stop) -> tuple[bands,masks,metadata]`, metadata transform shifted to window origin. If provided, report it early; main initially uses full decode. Measure basic candidate sizes on same full AOI (1233×604), including metadata/index. Keep all measurements honest; packed14 may lose. Document format and winner hypotheses, not legal/source fidelity claims.

## W2 — independent oracle and adversarial query verification

**Write ownership:** `engine/oracle.py`, `engine/tests/test_query_oracle.py`, `engine/tests/test_adversarial.py`, `docs/lab/engine-W2-report.md`; scratch `data/experimental/w2/`. Do NOT change core query/source/model or codec/harness files. If tests expose core bug, record minimal reproducer and expected result; lead fixes core.

**API:** `oracle_evaluate(dataset: Dataset, geometry: dict, missing_bands: tuple[str,...]=()) -> dict`. Implement independently from engine.query: no imports/calls of evaluate, select_cells, or reduction helpers. Use a separate point-in-polygon implementation (scalar ray casting with boundary checks) and scalar reduction; avoid sharing geometry rasterization logic. It may import Dataset/BAND_NAMES only. Match exact output contract and deterministic reason order above. For floating-point boundary tests use explicitly representable coordinates; report tolerances if used, avoiding an unexplained buffer.

Tests include actual17plots against source main evaluator; tiny zero-center polygon, grid-edge centers, holes (hole boundary covered), multipart islands, out-of-coverage fully/partially, no-data0, water-only, masked raw event, positive partial→true, absent partial→null neverfalse, missing bands→null, unknown union not double-counting, all years incl0 and 25, invalid geometry/ring/self-crossing and unsupported geom types. Include randomized deterministic fixtures with recorded seed. Distinguish synthetic edge-case count from17realplots. Oracle is independent implementation evidence, not ground truth satellite accuracy.

## W3 — fair benchmarks and deterministic experiment registry

**Write ownership:** `engine/benchmark.py`, `engine/experiments.py`, `engine/tests/test_experiments.py`, `docs/lab/engine-W3-report.md`; scratch `data/experimental/w3/`; generated final benchmark outputs only `artifacts/benchmark-v1.json`, `artifacts/experiments/`, `artifacts/stores/`. Do NOT write demo-v1/example-v1 or core/codec/oracle files. Coordinate by reading available APIs; codec may arrive after initial harness work.

**CLI:** `.venv-data/bin/python -m engine.benchmark` creates `artifacts/benchmark-v1.json`; `.venv-data/bin/python -m engine.experiments` may wrap it with deterministic experiment IDs. No need to redownload any data.

Use load_source/load_plots and W1 CANDIDATES/encode_store/decode_store plus query.evaluate. Compare on identical full1233×604 AOI/grid/source dates. Baseline1 actual three DEFLATE GeoTIFF chips (576999bytes) plus necessary metadata; baseline2 fairly recompressed separate-band codec candidate. Do not count raw-tile-to-chip crop savings. Report every candidate total bytes payload/index/metadata separately, preprocessing wall/cpu time, full raw bands/masks roundtrip,17exact query comparisons and mismatch fields. Winner by measured total bytes among fully exact candidates; explicitly report query tradeoff.

Measure hot queries with loaded data and cold-process load+query in isolated child **ordinary Python benchmark processes**, not agent runtimes. Label OS file-cache warmness accurately: process-cold is not disk-cold. Include repeated timings median/p95/min, repetitions/warmups, resource peak RSS with platform units, environment versions/hardware, number queries, scope excluding UI. Fair warm/hot equivalence; don't compare source load+query to preloaded compact-only. Use deterministic run/content fingerprint from source hashes+query/version+candidate settings; timings naturally vary. Atomic results registry writes; source hashes; repeated runner should preserve prior experiment evidence or identify repeat. Total storage required for answering query includes index/metadata; common geometry/source identities can be reported separately if symmetric. Optional chunk-size sweep32/64/128/256 only after first full end-to-end. Prefer bounded adaptive experiments justified by earlier results, not random tuning or complianceML. Keep artifact compact and document method precisely.

## Lead integration reservation

Lead owns `engine/__init__.py`, `engine/model.py`, `engine/source.py`, `engine/query.py`, `engine/export.py`, `engine/README.md`, `engine/requirements.txt`, `engine/tests/__init__.py`, remaining integration tests, `artifacts/demo-v1.json`, `artifacts/example-v1.json`, `artifacts/evidence/`, `docs/lab/interface-v1.md`, `docs/lab/engine-report.md`. Workers never overwrite another write set. Add requests/blockers to own report immediately. Master can relay messages. Lead will review each implementation and independently run full suite before accepting results.

## Optional W4 Luna — bounded public JRC availability retry

Master proxy may dispatch this bounded supporting task when capacity permits; it does not block the Hansen engine. **Model preference Luna**, no extra Astra lead. Own only `data/experimental/w4/` (new files) and `docs/lab/engine-W4-report.md`. Read layer-acquisition.md and relevant original SystemEarth references. No edits to data/public/, source files, core/codecs/benchmarks, or app. No Git mutations, external publication/messages, private uploads or cloud spend.

Check official JRC Global Forest Cover Map2020v3 page and its tile N10_E90 download route already documented in layer-acquisition.md. Prior route returned HTTP500. Use official sources only; browser tooling must start T3preview_status/open per charter. Record status/date/URL/version/licensing and whether a bounded retry now succeeds. Do not download the~50GBmosaic. Do not upload plot geometry; the public standard tile identifier suffices. At most two bounded HTTPattempts after inspecting official metadata. If a valid tile response advertises<=256MiB and download fits<=5minutes, acquire atomically within owned scratch; otherwise report availability/size and stop. Unknown size: cap bytes256MiB, abort/label incomplete without claiming usable data. No infinite retries.

If a complete public tile is acquired within bound, verify rasterio decode, native CRS/grid/nodata/classes and coverage of the already known sample bbox. Preserve native grid (noresampling); if deriving a local AOIchip keep it within w4 and include URL/sourcehash/chiphash/window/transform/coverage/readback evidence. Do not splice it into Hansen codec or claim legalforest status. Return runnable commands and whether data is genuinely ready vs merely linkavailable. This optional research result informs a later separatelyversioned baseline, not currentartifact semantics.

## W2 optional focused indexed verification

Indexed API is now implemented in engine/indexed.py. Same W2 ownership may be resumed to independently compare SourceWindowReader/CompactWindowReader+evaluate_reader against oracle_evaluate on17realplots and existing boundary/partialfixtures, including the recorded one-ULPwitness. Do not edit indexed.py; report any minimal mismatches. Existing45W2tests and lead5indexedtests pass. Xhighvalidator independently checked global-lattice indexed reduction too; focus on actual reader plumbing and masked/raw value retention only if this adds evidence, not redundant test volume.

## W4 dispatch update (master instruction takes precedence)

Master actually dispatched LunaW4 `01a13317-a7ac-7b32-a012-ec9d1a3b2c6a` with ownership `data/experimental/jrc/` and `docs/lab/engine-data-W4.md`, bounded~20minutes/~1GB and official alternate/UI routes. That explicit dispatch supersedes the earlier suggested w4 paths/caps above. Lead will review any acquisition before integration; Hansen contract unchanged.

## Next bounded Sol R&D — generalization of codec choice (resume W1 or new W5)

**Own only:** `engine/research_regions.py`, `engine/tests/test_research_regions.py`, `data/experimental/regions/`, `docs/lab/engine-W5-report.md`. Do not change codecs/core/benchmark/proof/demo/source files. This is a research runner, not a new production codec. Read current core APIs and W1/W3 results. No dependencies or downloads needed: existing ignored raw official Hansen10N_090E source tiles can be read locally.

Question: is separate-band zstd19 a cohort-specific choice or consistently preferable over packed14/uint16/bitplane? Lead inspected all measured chunks at128/256/512/1024in W1 stores: **separate_zstd_l19 is the smallest payload on every chunk**, so a learned/per-chunk adaptive selector is unjustified for the current company AOI (best possible payload saving0 before selector overhead). Do not build adaptive ML without a measured counterexample.

Produce a deterministic bounded multi-AOI experiment from four fixed public windows on the SAME raw source tile, each604rows×1233cols. Suggested top-left coordinates native-grid-aligned near92E2N(open-water control),95.4E5.4N(Aceh landscape),98.5E2.5N(Sumatra inland),99.5E7.5N(peninsula coast). These are geographic anchor labels, not independently verified landcover classifications; use actual datamask/canopy histograms to describe observed composition. Record exact integer windows, bounds, transform, nativeproduct/hash identities. Read local raw GeoTIFFs only; preserve masks/rawvalues and validate ranges. Do not alter supplied/public raw files. All new windows are **public-layer research AOIs**, not additional company plots or legal groundtruth.

For each window, create reasonably compressed separate-band GeoTIFF originals with full native support (DEFLATE level9,tiled256, explicit metadata), then evaluate existing6codec candidates at bounded chunk256and1024(or prune second setting if first shows no useful question). Account complete payload/index/metadata plus exact raw/mask/metadata roundtrip. Record encoding/decoding repeated timings honestly in-process, separate from canonical isolated17plotbenchmark; don't mix denominators. Include source window pixel equality and two synthetic query geometries per researchAOI (bbox/subrectangle/hole) as explicitly synthetic geometries, oracle comparison bounded by work limits. No new real-plot fidelity percentage.

Report winner variation, per-chunk payload-only hypothetical best-choice bound and whether selector overhead could matter. Keep every negative result. If all winner choices remain uniform, reject adaptive complexity and report that evidence. Do not modify CANDIDATES or canonical retained choice. A new candidate proposal must first show bounded measured advantage, then be reviewed by lead. Keep entire run<20minutes and derivative scratch<40MiB; use sequentialordinary Python for measurements, no agents spawned. Return runnable CLI/tests, JSON experiment IDs/source/code fingerprints and uncertainty limits. Master may close worker after report; lead integrates selected research conclusions only.

## R&D dispatch coordination updates

Master dispatched independent Solxhigh selector study `01a1331f-024a-7ec3-8ae1-f8ee5423680f`, owning data/experimental/selector/ and docs/lab/engine-selector-report/results. It studies spatialholdouts/modeloverhead/fixedbaselines/roundtrip/regret onexistingpublicrawtile. This covers the core generalizationquestion above; do not separately dispatch the overlapping W5multi-AOI task until lead reviews that study. CurrentAOI's zero adaptivepayloadgain remains a measurednegative; newregions maydiffer.

LunaW4 successfully acquired JRCv4. A separate bounded nativeJRCworker assignment is now in `docs/lab/engine-jrc-task.md`. Lead verified officialQMLcode0=Non-forest,1=Forest; acquisition/sourcefiles remainimmutable. NoJRC/Hansenresampling orlegalverdict authorized.

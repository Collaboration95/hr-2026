# Plotline evidence engine

Python3.14 native-grid forest-change queries on verified Hansen2025v1.13 chips and17supplied plot geometries. Supplier declarations remain separate from mapped observations. No legal/compliance label is computed.

## Run

From repository root, use the existing isolated environment:

```sh
.venv-data/bin/python -m pip install -r engine/requirements.txt
.venv-data/bin/python -B -m engine.export
.venv-data/bin/python -B -m engine.verify
.venv-data/bin/python -B -m unittest discover -s engine/tests -v
```

Export selects the explicitly retained measured store and creates `artifacts/demo-v1.json` and `artifacts/example-v1.json`. It rejects stale/unbound benchmark evidence. Verification reopens original and compact inputs, compares all raw values/masks, requeries every plot, recomputes receipts/summaries and validates the retained measurement archive/files/code. Hashes prove integrity against local evidence, not authentication or satellite accuracy.

Query one plot or local GeoJSON without the frontend:

```sh
.venv-data/bin/python -B -m engine --plot P-0003
.venv-data/bin/python -B -m engine --plot P-0003 --access indexed
.venv-data/bin/python -B -m engine --geometry path/to/polygon.geojson --store path/to/compact-store
```

`--store` compares compact and original results. Exit0 means execution succeeded (see the equal field); exit1 means a comparison mismatch; exit2 is a structured input/read error. `--access indexed` uses original-grid selection then window reads. The default full preload is retained for this small AOI; indexed access is optional and not presumed faster.

For explicitly metric-free work during experiments:

```sh
.venv-data/bin/python -B -m engine.export --without-benchmark
.venv-data/bin/python -B -m engine.synthetic
```

Without a store, that metric-free export marks compact results pending. Synthetic examples remain separate from17realplots.

## Experiments and retained evidence

```sh
.venv-data/bin/python -B -m engine.benchmark --chunk-size 1024 --candidates separate_zstd separate_zstd_l9 separate_zstd_l19 --no-publish
.venv-data/bin/python -B -m engine.window_benchmark --store path/to/compact-store
.venv-data/bin/python -B -m engine.package
```

The benchmark records source/code/query fingerprints, repeated wall/CPU timing, isolated child peak RSS, complete store accounting and exact fidelity. Process-cold includes native load+query after imports; OS cache is uncontrolled and likely warm, not disk-cold. UI/network/full-tile acquisition and crop savings are excluded.

Experiments never silently replace an explicitly retained choice. `engine.benchmark.retain_benchmark(result, reason)` deliberately freezes one registered run after checking live inputs/stores/code. A later code change makes its evidence stale until remeasured and explicitly retained. `engine.package` lists the minimal local proof bundle; it never stages, commits, uploads or publishes. See [engine-report.md](../docs/lab/engine-report.md) for the actual accepted experiment and measured tradeoffs.

## Contract and implementation

The canonical JSON contract is [interface-v1.md](../docs/lab/interface-v1.md).

- `source.py` verifies chips against acquisition provenance, checks native alignment, and joins exact CSV strings to exact GeoJSON geometry. No resampling or silent source replacement.
- `model.py` validates raw ranges even on masked cells: canopy0–100, lossyear0–25, datamask0–2. Three boolean band-validity masks remain separate.
- `query.py` selects original native centers using polygon `covers`, including exterior/hole boundaries. Outside-chip selected centers remain unknown. All indices come from the original lattice, avoiding shifted-window floating-point boundary changes.
- `codecs.py` implements packed14, uint16, bitplane and separate-band zstd variants. Bounded decoders preserve raw values/masks and reject unsupported values or malformed streams.
- `oracle.py` independently selects with scalar ray casting and reduces with scalar counters. GEOS topology validation is shared; membership/reduction are independent.
- `indexed.py` fetches only selected-center bounding windows after original-grid selection. The higher-level reader verifies complete input hashes at initialization; the lower-level codec window API checks selected chunks only.
- `export.py`, `proof.py`, `verify.py` bind exact observations, source/store identities, executable contract, receipt/summary and deliberately retained measured evidence.

With partial support, a witnessed event remains true; absent events remain null while any support is unknown. False requires known selected support and at least one valid land cell. Zero selected centers, water-only support, missing bands or no valid land produce null analytical outputs. Histograms on partial support are observed valid-land counts, never complete-plot area. Counts are cells, not hectares.

Malformed, unclosed, self-intersecting, non-polygon, nonfinite or oversized geometries are rejected; no silent repair occurs. Production query limits are100000vertices and10000000candidatecells. The independent oracle has lower bounded-work limits. Dataset raw validation occurs at loading/decoding; the shared internal reduction expects validated samples.

## Reproducibility and limits

Pinned dependencies are in requirements.txt; Python3.14 supplies `compression.zstd`. Source inputs remain immutable. Encoded bytes are deterministic for fixed input/settings/libzstd; cross-version byte identity is not promised. Benchmark timing naturally varies. Retained files are content-addressed, and prior losing/failed experiments remain distinct evidence.

Artifacts include private supplied values. Keep them local; no publication permission is inferred. Full original source tiles are an ignored acquisition cache, unnecessary for normal queries/export/proof checks. Independent original-download readback verification can use that cache or reacquire official tiles.

Canopy2000 is not forest2020. Latest-release loss observations may differ from the supplier's historical source vintage. Tree-cover loss is not legal deforestation. Current Hansen inputs cannot establish a2020forest baseline or regulatory compliance.

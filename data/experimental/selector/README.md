# Source-only spatial codec selector

Experimental research for Volta's review. No production integration or canonical
benchmark changes. Data comes exclusively from the already-downloaded three-band
Hansen source tile. No supplier declaration or compliance label is read.

The immutable original study files are `dataset-manifest.json`, `policy.json`,
`measurements/*.json`, `results.json`, and `verification.json`. `analysis.json`
adds descriptive strata, actual package-window timings, and training-only timing
reproduction. `heldout-per-patch.csv` is a small inspection table. All data needed
to decode/query each compared package is physically in `heldout-packages/`;
complete package accounting includes those files. `aoi-control-results.json`
is a separate audit of the existing AOI, never a second generalization cohort.
`matching-level-control.json` adds a fixed GeoTIFF3 comparison chosen solely on
development costs after the sealed challenge; all its candidate settings were
already registered and measured. The learned policy is unchanged.

The first pilot was 12 training patches from six regions. Its aggregate is
`pilot-results.json`; its early report checkpoint is preserved in
`docs/lab/engine-selector-report.md`.

## Reproduce

From the repository root, using the existing environment and no installation:

```sh
.venv-data/bin/python -B data/experimental/selector/replay.py prepare --directory fresh-run
.venv-data/bin/python -B data/experimental/selector/replay.py develop --directory fresh-run
.venv-data/bin/python -B data/experimental/selector/replay.py freeze --directory fresh-run
.venv-data/bin/python -B data/experimental/selector/replay.py challenge --directory fresh-run
.venv-data/bin/python -B data/experimental/selector/replay.py verify --directory fresh-run
```

Choose a new subdirectory for a new run. Preparation refuses an existing
manifest; freezing refuses an existing policy or previously opened holdout.
Development measurements resume only when implementation/settings match.
Policies bind the exact source manifest, implementation hashes and development
measurement hashes. Verification rereads original native source windows,
checks every retained file hash/byte count, and checks full raw arrays/masks plus
five windows per retained store. Timestamps and timings vary across replays;
spatial coordinates, frozen trees and store bytes are deterministic in the
recorded environment. `reproduction-proof.json` records a successful independent
fresh-directory replay; its redundant scratch was removed afterward.

The original study commands were `study.py prepare`, `pilot`, `develop`,
`freeze`, `challenge`, and `verify`. Do not rerun `pilot` against a finished
study: it writes the early report checkpoint. Use the fresh-directory commands
above to preserve the final report and evidence.

Additional descriptive checks and the separate seen-AOI audit:

```sh
.venv-data/bin/python -B data/experimental/selector/analyze.py
.venv-data/bin/python -B data/experimental/selector/aoi_control.py
.venv-data/bin/python -B data/experimental/selector/matching_control.py
```

`analyze.py` does not fit on holdout or change policies. Its refit timing uses
only the original training rows and requires equality to frozen trees.
The AOI audit reads the current retained choice and refuses source/codec/baseline
changes during the run. It writes only the selector directory and preserves the
previous result under a content hash when rerun.

Example real window query against a retained package:

```sh
.venv-data/bin/python -B data/experimental/selector/study.py package-window \
  --package level3-selected --patch R0C1-B01 --window 240 272 240 272
```

Arguments are patch-local native rows/columns. The global index records each
patch's original native coordinates and the original full-tile affine transform.
Coverage consists only of the listed sparse patches; gaps are unavailable.
This reader demonstrates query feasibility and encoding preservation. It does
not implement polygon semantics or make compliance decisions.

## Resource and storage scope

Only bounded raster windows are returned to NumPy. Full compressed source files
are streamed for SHA-256 checks. GDAL's source strip organization can decompress
a whole row internally; no full source array is constructed. The feature sample
is a fixed 32×32 lattice inside each 512×512 patch, taken from arrays already
needed for encoding. Feature computation is timed separately, with no extra
source read attributed to it.

Research scratch is about 250 MB, including all losing stores and approximately
113 MB of uncompressed patch arrays/masks. The actual complete heldout packages
are each under 0.9 MB. Research caches/labels/results are disclosed separately
and are not required to query a package. Runtime code/libraries are excluded
symmetrically from data-only package totals; the standalone script's byte count
is disclosed. No dependencies were added. Timing is local, cache uncontrolled,
with buffered writes and no durability synchronization; it is not a disk-cold or
end-to-end application benchmark.

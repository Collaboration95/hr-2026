# Clean-checkout setup and retained-proof reproduction

This procedure installs the pinned Python geospatial dependencies and the app's locked npm dependencies, then verifies the retained Hansen and JRC proofs, reproduces the P-0003 Hansen query through both access paths, and builds the app. It does not run a benchmark, regenerate retained artifacts, or require the ignored full Hansen or JRC source-tile caches.

Requirements: Python 3.14, Node.js, and npm. From the repository root:

```sh
scripts/setup-local.sh
scripts/verify-local.sh
```

`setup-local.sh` creates `.venv-data` when needed, installs `engine/requirements.txt`, and runs `npm ci --prefix app`. If Python 3.14 is not named `python3.14` on the machine, set `PLOTLINE_PYTHON` to its executable path. The setup script rejects another Python minor version and reports missing tool prerequisites.

`verify-local.sh` checks the complete Hansen retained proof and the separate JRC v4 proof, then queries P-0003 against the retained Hansen compact store using full preload and indexed reads. Both query commands exit nonzero on a source/compact mismatch. It finishes with the production app build, including local evidence synchronization. The script reports a clear setup instruction if the virtual environment or app dependencies are absent.

## Fresh-export audit record

On 14 October 2026, the tracked repository files were exported to a temporary directory, without ignored source tile caches or the existing project virtual environment. Since the new setup and verification scripts were still untracked during this audit, those two scripts and this report were copied into the export before invoking them. A new Python 3.14.7 virtual environment installed the three direct pins from `engine/requirements.txt`; `npm ci --prefix app` completed from the lockfile. The retained Hansen verifier passed for all 17 plots. The JRC verifier passed for all 17 plots and 6,684,255 chip pixels, and reported `full_source_cache_present: false`. The P-0003 Hansen result selected 87 supported cells and reproduced through full and indexed access. The app production build passed and synchronized the frozen Hansen, synthetic, and accepted separate JRC assets.

Audit exports: `/tmp/hackroll-audit` (initial manual reproduction) and `/tmp/hackroll-final-audit` (setup/verification command replay). It was created from tracked Git files, is a temporary copy on the same physical machine, and does not represent a second-machine test. The pre-existing untracked `data/experimental/jrc-engine/tests/` directory was left untouched and excluded from the export. No retained measurement was rerun or rewritten.

The package install emitted npm's `allow-scripts` notice for `esbuild` and `fsevents`; `npm ci` and the Vite production build both succeeded in this environment. Native Python/npm package resolution and timings can vary by operating system. These checks establish local retained-input consistency, not source authenticity, satellite accuracy, legal compliance, or cross-platform byte identity.

The integrated setup also rejects an existing `.venv-data` with the wrong Python minor version before running pip. Browser verification uses app-local Playwright, a separately installed browser, configurable loopback origin and isolated evidence directories; see `app/README.md`.

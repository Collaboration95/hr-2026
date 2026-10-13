# Plotline — local evidence desk

A working React/TypeScript application for the 17 supplied SystemEarth plots. The app links exact declarations, plot boundaries, annual native-cell evidence, original/compact output comparison, provenance receipts, and frozen engine measurements. It does not determine legal compliance.

## Run locally

Verified with Node 26.3.1, npm 11.16.0 and Python 3. Python is used only for read-only asset preparation; the application is static after build.

From the repository root:

```sh
npm ci --prefix app
npm run dev --prefix app -- --port 5173 --strictPort
```

Open http://127.0.0.1:5173/. Vite is bound to loopback. All map geometry, evidence, styles, icons and fonts work without third-party map tiles, font services or application APIs. No cloud deployment is configured.

```sh
npm run build --prefix app
npm run preview --prefix app -- --port 4173 --strictPort
```

Build emits `app/dist/`. It includes the local company sample and is not a publication package. Keep it local under the current authorization.

## Data boundary

`npm run sync-data --prefix app` copies the engine-owned `artifacts/demo-v1.json` into ignored `app/public/data/`. It copies the optional, separately labelled `artifacts/synthetic-v1.json` into a separate file. The app never modifies those canonical artifacts or raw inputs. Dev startup and production build run the copy automatically; after a later explicit sync, Commands → Reload local evidence validates and loads the new frozen response.

If the canonical export does not exist, the sync builds a declaration-only view from the actual CSV and GeoJSON. Every uncomputed source/compact/receipt/benchmark field remains null. The full-proof check deliberately does not pass that fallback.

The engine owns the selected benchmark/store and its verification. The frontend does not pick whichever experiment happens to be newest. Experiment identity, full stored bytes, timing method, cohort and environment remain inspectable. Query timings are per 17-plot batch, not per plot. Loaded-query timings exclude loading; fresh-process load+query is not disk-cold.

Runtime loading validates shape and internal semantics before replacing accepted data: IDs, nullable analytical states, count/histogram consistency, receipt/envelope consistency, and full actual source/compact equality. It does not authenticate source files or replace the engine verifier. A rejected reload preserves the last accepted artifact and shows the error.

## Main interactions

- Search or filter the queue; J/K changes the selected plot outside text inputs.
- Select a loss year; the map and observed-cell count change together. Canopy is year-2000 context; Land mask shows selected support.
- All 17 plots opens a location index. Select a marker to focus the exact supplied geometry. Layer controls are disabled in location overview.
- Inspect native cells as a table for keyboard-accessible raw values and per-year event filtering. Unknown/masked values remain unavailable, never no-event.
- Click the observed-cell count or Show proof to compare the same query on original/compact outputs. Back returns to the originating count or header.
- Receipt exposes source/grid/hash/declaration details and downloads local JSON.
- Commands (Cmd/Ctrl+K) provides contextual actions. Escape closes its native dialog. `/` focuses plot search.
- Analyst questions are separate local browser annotations keyed by exact supplier record. Saved notes survive refresh; unsaved drafts survive plot switches in that tab but not refresh. Export notes separately from source receipts.
- Query-limit cases below proof use a fictitious 4×4 engine test grid. They never enter real cohort counts.

## Repeatable checks

```sh
npm test --prefix app
node app/scripts/browser-check.mjs --file artifacts/demo-v1.json --url http://127.0.0.1:5173
```

Browser regression from repository root, using an already installed Playwright module and Chromium (no automatic installation):

```sh
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs node app/tests/live-journey.mjs
```

The initial QA machine has Playwright at `/Users/speedpowermac/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs`. That machine path is not a portable dependency. The browser runner restricts requests to loopback and closes its isolated browser. See `docs/lab/browser-qa.md` for covered journeys, screenshots, limitations and evolving checks. T3 preview is the first browser path; isolated Playwright was used only after actual T3 resize/host failures.

## Interpretation limits

The five declaration-backed indication/mitigation records are review leads, not violations. Opaque reference keys do not supply the mitigation files. A current Hansen release may differ from the supplier's historical source and query rule. A source/compact match establishes representation agreement under the same query, not satellite ground truth or legal compliance. Native cell counts are not hectares; canopy2000 is not a forest2020 baseline. Missing JRC/protected-area evidence is not fabricated.

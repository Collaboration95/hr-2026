# Plotline — local evidence desk

A working React/TypeScript application for the 17 supplied SystemEarth plots. The app links exact declarations, plot boundaries, annual native-cell evidence, original/compact output comparison, provenance receipts, and frozen engine measurements. It does not determine legal compliance.

## Run locally

Verified with Node 26.3.1, npm 11.16.0 and Python 3. Frozen review uses Python for read-only asset preparation and works as static files after build. The optional live Query lab also uses the repository-local Python engine service.

From the repository root:

```sh
scripts/setup-local.sh
scripts/verify-local.sh
npm run dev --prefix app -- --port 5173 --strictPort
```

Open http://127.0.0.1:5173/. Vite is bound to loopback. All map geometry, evidence, styles, icons and fonts work without third-party map tiles, font services or application APIs. No cloud deployment is configured.

```sh
npm run build --prefix app
npm run preview --prefix app -- --port 4173 --strictPort
```

Build emits `app/dist/` for offline frozen review through a local HTTP server. It includes the supplied company sample. The user has authorized the tracked GitHub repository publication; this command does not deploy the app or change source terms.

## Data boundary

`npm run sync-data --prefix app` copies the engine-owned `artifacts/demo-v1.json` into ignored `app/public/data/`. It copies the optional, separately labelled `artifacts/synthetic-v1.json` into a separate file. The accepted optional JRC companion is copied separately only when its file SHA-256 matches the reviewed pin in `scripts/sync-data.py`; an absent or changed file leaves it unavailable. The app never modifies those canonical artifacts or raw inputs. Dev startup and production build run the copy automatically; after a later explicit sync, Commands → Reload local evidence validates and loads the new frozen response.

If the canonical export does not exist, the sync builds a declaration-only view from the actual CSV and GeoJSON. Every uncomputed source/compact/receipt/benchmark field remains null. The full-proof check deliberately does not pass that fallback.

The engine owns the selected benchmark/store and its verification. The frontend does not pick whichever experiment happens to be newest. Experiment identity, full stored bytes, timing method, cohort and environment remain inspectable. Query timings are per 17-plot batch, not per plot. Loaded-query timings exclude loading; fresh-process load+query is not disk-cold.

Runtime loading validates shape and internal semantics before replacing accepted data: IDs, nullable analytical states, count/histogram consistency, receipt/envelope consistency, and full actual source/compact equality. It does not authenticate source files or replace the engine verifier. A rejected reload preserves the last accepted artifact and shows the error.

## Main interactions

The UI was redesigned on 15 October 2026 ("Night survey", see [design/DESIGN.md](../design/DESIGN.md)). Routes are hash-based and deep-linkable: `#/map`, `#/map/P-0001/2022`, `#/cohort`, `#/proof/P-0005/2025`, `#/live`.

- **Map** opens on the region view. The basemap is the pinned Hansen 2025 v1.13 chip, packed losslessly into `public/region/hansen-bands.png` by `scripts/render-region.py` and recoloured in the browser; the JRC 2020 v4 overlay is drawn on its own grid. These rasters are display only, and counts always come from the validated export. **Loss** / **Canopy 2000** / **Land mask** change the raster; **JRC 2020 forest** toggles the overlay. Wheel zoom and drag pan work; **Region** and **Fit plot** reset the view.
- **Year scrubber:** ▶ plays 2001→2025. ←/→/Home/End work when the scrubber has focus. It marks the supplier's 2021–23 window and the EUDR cut-off.
- **Plot rail:** search (`/`), filters (*All*, *Declared indication*, *Mapped loss 2021–23*, *Declared ≠ mapped*) and J/K. Filters affect only the rail.
- **Inspector:**
  - ◆ *Declared by supplier* and ■ *Mapped by Plotline* side by side, with a review question generated from fixed templates;
  - the selected-year count, which opens Proof (`#annual-proof-trigger`) and shows the compact-copy agreement;
  - disclosures for **Native cells** (keyboard table, "Show on map"), **JRC 2020 baseline (separate source)** and **Analyst note** (local only, same storage key and limits as before).
- **Cohort:** declared-vs-mapped matrix for 2021–23, and a 17 × 25 loss barcode. Positive cells open the plot and year. **Export displayed counts · CSV** keeps the earlier escaping and context rows.
- **Proof:** export-derived hero numbers (exact-match plots, pixel fidelity, storage change, fresh-process and hot-query timing), the field-by-field original/compact comparison, every storage candidate including the losers and the separate standard-format control, timing distributions, a research summary and the fictitious-grid query-limits lab.
- **Receipt** (inspector button or ⌘K): readable fields, raw JSON disclosures and **Download receipt JSON**.
- **Live query:** an exact plot polygon or a temporary rectangle, with every lifecycle state shown, the bound live receipt and complete native-cell evidence.
- **Keyboard:** ⌘/Ctrl+K opens commands. Esc closes dialogs; on the map it returns to the region view.

## Repeatable checks

```sh
npm test --prefix app
node app/scripts/browser-check.mjs --file artifacts/demo-v1.json --url http://127.0.0.1:5173
```

Browser regression uses pinned app-local Playwright 1.63.0. Install its headless Chromium into the ignored project-local cache, then run the frozen-review suites with the loopback dev server running:

```sh
npm run qa:install-browser --prefix app
npm run qa:browser --prefix app
```

Browser installation is an explicit setup step; test runs do not download browsers. The runner selects the app-local dependency, uses `app/.cache/playwright`, and runs from the repository root. Suites restrict requests to loopback and close isolated browsers. An optional `PLAYWRIGHT_MODULE` remains supported when invoking individual test files directly, but the standard setup needs no machine-specific npm cache. See `docs/lab/browser-qa.md` for coverage and evidence. T3 preview was used first; isolated Playwright followed actual T3 resize/host failures.

## Interpretation limits

The five declaration-backed indication/mitigation records are review leads, not violations. Opaque reference keys do not supply the mitigation files. A current Hansen release may differ from the supplier's historical source and query rule. A source/compact match establishes representation agreement under the same query, not satellite ground truth or legal compliance. Native cell counts are not hectares; canopy2000 is not a forest2020 baseline. The optional accepted JRC 2020 v4 companion uses its own grid, classes and receipt. Its cell counts are not comparable area units with Hansen. Protected-area evidence is not supplied.

### Local query lab: one command

After the existing app dependencies and repository `.venv-data` engine environment are installed, run from `app/`:

```sh
npm run dev:local
```

This starts the read-only Hansen API on `127.0.0.1:8765`, waits for its verified snapshot health response, copies exported app data, then starts Vite on `127.0.0.1:5173`. Open **Query lab**. Ctrl-C terminates both processes started by this command. If either process exits, the other is terminated. Existing processes are never killed; occupied ports produce an error. No dependencies are installed and no cloud services are used.

Stop an existing `npm run dev` before using the combined command, or choose separate local ports:

```sh
PLOTLINE_WEB_PORT=5183 PLOTLINE_LIVE_PORT=8766 npm run dev:local
```

The launcher passes that exact loopback browser origin to the API and configures the matching Vite proxy. `npm run dev` still works independently: frozen review remains usable and Query lab shows service unavailable until the optional API is started. The live snapshot is immutable until API restart; reconnect after restarting. Live queries do not modify supplier records, exported results, or the retained benchmark.

### Live acceptance checks

With API and Vite running (for example through `npm run dev:local`), run from a second terminal:

```sh
npm run qa:live --prefix app
```

For the documented alternate web port:

```sh
PLOTLINE_QA_ORIGIN=http://127.0.0.1:5183 npm run qa:live --prefix app
```

This separate 14-check suite requires actual unaugmented HTTP success responses. It checks exact P-0003 reproduction, temporary bounds, tiny/outside/partial/oversized regions, complete native evidence, exact receipt bytes, delayed-response rejection, cancellation, unavailable-service recovery and 390px keyboard use. It neither starts nor kills shared servers. Transport faults and delays affect only disposable test browser contexts. Missing health produces an explicit blocked report and exit code 2, not a passing skip. New results and screenshots are written to a unique directory under `app/.cache/qa/`; the runner prints its path. Historical evidence under `docs/lab/browser-evidence/` is preserved.

`npm test` also includes the live-client binding checks; those require the existing `.venv-data` environment and retained local engine inputs. No test command installs dependencies or uploads data.

## Completion checks and demo fallback

All standard browser suites now honor `PLOTLINE_QA_ORIGIN`. Set `PLOTLINE_QA_OUTPUT` to a repository-relative or absolute output directory when retaining a run. Without it, each invocation gets a unique ignored cache directory. The older `PLOTLINE_QA_URL` remains an alias. Only HTTP loopback origins are accepted.

```sh
PLOTLINE_QA_ORIGIN=http://127.0.0.1:5183 npm run qa:browser --prefix app
PLOTLINE_QA_ORIGIN=http://127.0.0.1:5183 npm run qa:live --prefix app
PLOTLINE_QA_ORIGIN=http://127.0.0.1:5183 npm run qa:jrc --prefix app
PLOTLINE_QA_ORIGIN=http://127.0.0.1:5183 npm run demo:record --prefix app
```

The recording command uses the installed browser and a healthy live service. It captures the pitch flow (region playback → JRC overlay → P-0001 accounts → cohort → P-0005 proof → receipt → live query), with no synthetic successful responses. It writes a silent WebM and a chapter JSON; narrate using [the demo script](../docs/lab/demo-script.md). Recording is a demo fallback, not a substitute for the proof verifiers.

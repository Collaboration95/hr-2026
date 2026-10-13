# Plotline — local evidence desk

A working React/TypeScript application for the 17 supplied SystemEarth plots. The app links exact declarations, plot boundaries, annual native-cell evidence, original/compact output comparison, provenance receipts, and frozen engine measurements. It does not determine legal compliance.

## Run locally

Verified with Node 26.3.1, npm 11.16.0 and Python 3. Frozen review uses Python for read-only asset preparation and works as static files after build. The optional live Query lab also uses the repository-local Python engine service.

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

`npm run sync-data --prefix app` copies the engine-owned `artifacts/demo-v1.json` into ignored `app/public/data/`. It copies the optional, separately labelled `artifacts/synthetic-v1.json` into a separate file. The accepted optional JRC companion is copied separately only when its file SHA-256 matches the reviewed pin in `scripts/sync-data.py`; an absent or changed file leaves it unavailable. The app never modifies those canonical artifacts or raw inputs. Dev startup and production build run the copy automatically; after a later explicit sync, Commands → Reload local evidence validates and loads the new frozen response.

If the canonical export does not exist, the sync builds a declaration-only view from the actual CSV and GeoJSON. Every uncomputed source/compact/receipt/benchmark field remains null. The full-proof check deliberately does not pass that fallback.

The engine owns the selected benchmark/store and its verification. The frontend does not pick whichever experiment happens to be newest. Experiment identity, full stored bytes, timing method, cohort and environment remain inspectable. Query timings are per 17-plot batch, not per plot. Loaded-query timings exclude loading; fresh-process load+query is not disk-cold.

Runtime loading validates shape and internal semantics before replacing accepted data: IDs, nullable analytical states, count/histogram consistency, receipt/envelope consistency, and full actual source/compact equality. It does not authenticate source files or replace the engine verifier. A rejected reload preserves the last accepted artifact and shows the error.

## Main interactions

- Evidence index shows actual counts across all 17 plots and 25 years, with supplier declarations in a separate column. Positive counts open their exact plot/year; displayed counts export locally as CSV. Sidebar filters only affect the review queue.
- Search or filter the queue; J/K changes the selected plot outside form inputs and editable fields.
- Select a loss year; the map and observed-cell count change together. Canopy is year-2000 context; Land mask shows selected support.
- All 17 plots opens a location index. Select a marker to focus the exact supplied geometry. Layer controls are disabled in location overview.
- Inspect native cells as a table for keyboard-accessible raw values and per-year event filtering. Unknown/masked values remain unavailable, never no-event.
- Click the observed-cell count or Show proof to compare the same query on original/compact outputs. Back returns to the originating count or header.
- Receipt presents source/grid/rule/hash/declaration details in readable disclosures, retains raw JSON, and downloads local JSON.
- Commands (Cmd/Ctrl+K) provides contextual actions. Escape closes its native dialog. `/` focuses plot search.
- Analyst questions are separate local browser annotations keyed by exact supplier record. Saved notes survive refresh; unsaved drafts survive plot switches in that tab but not refresh. Export notes separately from source receipts.
- Query-limit cases below proof use a fictitious 4×4 engine test grid. They never enter real cohort counts.

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

This separate 14-check suite requires actual unaugmented HTTP success responses. It checks exact P-0003 reproduction, temporary bounds, tiny/outside/partial/oversized regions, complete native evidence, exact receipt bytes, delayed-response rejection, cancellation, unavailable-service recovery and 390px keyboard use. It neither starts nor kills shared servers. Transport faults and delays affect only disposable test browser contexts. Missing health produces an explicit blocked report and exit code 2, not a passing skip. Results and screenshots are written under `docs/lab/browser-evidence/`.

`npm test` also includes the live-client binding checks; those require the existing `.venv-data` environment and retained local engine inputs. No test command installs dependencies or uploads data.

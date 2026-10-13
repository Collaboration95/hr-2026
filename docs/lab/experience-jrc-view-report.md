# C4-B baseline panel handoff — 13 October 2026

For Hooke Astra `01a132f8-f7e5-7fd0-9690-31faa43db819` and master `01a130e9-aaf5-7a53-9cff-96d579f69b35`. No callable agent messaging tool exists in this worker's inventory; this file and the ingest report are the handoff to both sessions.

Status: implemented as a separate, compile-valid module, **not mounted**. The actual JRC candidate is still unaccepted; engine approval and integration belong to Hooke. No canonical candidate was copied or shipped into the running app.

## Exact files and interface

- `app/src/JrcBaseline.tsx` — default export `JrcBaseline({data,plotId}:{data:JrcArtifact;plotId:string})`.
- `app/src/styles/jrc-baseline.css` — component-scoped typography, containment, table, focus and reduced-motion styles.
- `docs/lab/experience-jrc-view-report.md` — this handoff.

Shared isolated QA uses the C4-A-owned `app/checks/jrc-ingest-browser.mjs` and `jrc-ingest-fixtures.mjs`. All worker files are within the user's allowed paths. App/configuration/assets/package/core/Git were not changed.

## Resulting behavior

The panel presents “2020 baseline observation · JRC v4” for the selected plot. Reference year/version, single-layer scope and different native grids are adjacent to source-class counts. It shows explicit0Non-forest/1Forest analytical counts, selected/valid/unknown/in/out support, reasons and mapped-class true/false/null wording. Unavailable analytics remain Unavailable rather than zero. Invalid raw0/1 remain inspectable and excluded from analytics; stored valid evidence also remains analytically unknown when `missing_band` suppresses the query.

An inspectable native-cell table is the bounded alternative to a mini-map. Every selected cell is reachable in25-row pages, without truncating evidence. Row/column, raw class, stored validity, analytical state and exact native center coordinates are separate columns. Keyboard disclosures expose four whole native cell corners computed from the original JRC affine. The table labels center selection and explains why footprints can extend beyond the supplied polygon. A missing plot displays an unavailable state rather than absence.

The separate proof recomputes full result structural equality and checks declared comparison/oracle flags, receipt/store/full-chip association and full-chip fidelity declarations. An unconfirmed comparison produces a visible warning beside the observations and a warning in proof; a forged true equality never produces confirmed copy. Displayed counts remain explicitly original-source outputs. The disclosure preserves source citation, XML dates/report caveat, geometry/receipt digests, result structures and raw JRC-only store/benchmark fields with units and scope. Null benchmark says Unavailable. It makes no combined metric or Hansen compression claim.

## Checks and browser evidence

```sh
app/node_modules/.bin/tsc --project app/tsconfig.json --noEmit
node --test app/checks/jrc-ingest-contract.test.mjs
node app/checks/jrc-ingest-browser.mjs
```

The last command starts **only synthetic display QA** at `http://127.0.0.1:5187/__jrc_fixture__?case=valid0`. It uses config-free Vite middleware and installed dependencies, without touching the lead's dev app or copying the candidate. Display fixtures use an artificial plot/geometry, declared lattice, artificial counts and synthetic receipt/citation text; they are separate from the candidate shape tests and real observations.

T3 policy followed: `preview_status` and `preview_open` first; a separate preview tab then navigated to port5187. T3 snapshot/visual inspection confirmed known0visibility, native coordinates and separate proof. T3 checks passed positive1, partial absence/positive, no centers, invalid masks, missing band, outside, truthful mismatch and forged equality. Mobile `preview_resize` then returned “Preview automation resize timed out after15000ms”; the next navigation explicitly returned “No preview automation host is available … Do not retry … use a headless browser … such as Playwright”. Only then was installed local Playwright used.

```sh
node app/checks/jrc-ingest-browser.mjs --verify
```

Fallback checks passed **12 synthetic display cases**, at375×812mobile and1280×800desktop: correct true/false/null signals; raw0distinct from unknown; invalid-mask/missing-band analytics; visible truthful/forged mismatch warnings; no page horizontal overflow while the table remains scrollable; minimum evidence font≥12px; reduced-motion transition0s; no page errors. Keyboard activated horizontal table scrolling, cell corner disclosure, next/previous pagination across31cells, proof and JRC-only benchmark disclosure, then Tab between summaries. Controls are44pxhigh and table/summary focus is visible. Table evidence text is13px, labels≥12px. Final mobile screenshot review caught narrow character-by-character table wrapping despite passing containment. The table now keeps a980pxminimum width and readable raw/mask columns inside the scroll region; the browser check asserts those dimensions as well.

The runtime gate suite passed76checks and the full current source tree passed TypeScript no-emit compilation. Full project build was not invoked because its first step synchronizes assets owned by integration.

## Integration gaps

- Engine acceptance remains pending. Hooke owns copying the accepted optional asset and mounting below Hansen observations. Pass only validated `JrcArtifact`; optional loader failures must leave Hansen review usable.
- Real accepted class0/class1 browser checks and the integrated queue/plot/Hansen-proof journey are reserved for C4-C after approval. The isolated fixture page is not an accepted-data demo.
- Recheck the integrated parent's sizing and color variables. Mobile containment is verified in isolation; the component CSS uses scoped `jrc-` classes, system font and safe variable fallbacks.
- These are native source cell counts, never hectares or whole-plot area. Non-forest does not mean no canopy. No raster fusion, legal classification, annual JRC selector or extended Hansen savings claim is implemented.

# Plotline design system and redesign spec

**Status:** v2 redesign, 15 October 2026. Owner: Claude (design), implemented by Claude Sonnet 5.5 subagents and reviewed by the design owner.
This document is both the **design reference** (reuse it for slides, videos and HTML writeups) and the **implementation contract** for the redesign of `app/`.

Tokens live in one file: [`app/src/styles/tokens.css`](../app/src/styles/tokens.css). Shared primitives: [`app/src/styles/base.css`](../app/src/styles/base.css) and [`app/src/components/Primitives.tsx`](../app/src/components/Primitives.tsx). A living style guide is in [`design/style-guide.html`](style-guide.html). Serve it from the repo root, for example with `python3 -m http.server 8090`, then open `/design/style-guide.html`.

---

## 1. What we are designing for

**The pitch audience:** SystemEarth engineers judging a geospatial-data challenge. They want a specific use case, multiple layers across time, a compact encoding, efficient queries, and proof that plot-level decisions survive the encoding. They will see the app for about three minutes, probably on a projector or shared screen.

**The product user:** an analyst checking supplier plot declarations against mapped layers, plus a technical reviewer checking that the compact copy gives the same answers.

**The one question the UI answers:** *"What do the layers say about this plot, how does that compare with what the supplier declared, and does the compact copy give exactly the same answer?"*

## 2. Principles

1. **The map is the data.** The basemap is the actual Hansen raster we encode (1,233 × 604 native cells, about 28 m each), recoloured in the browser. There are no third-party tiles, photos or fake imagery. When you zoom in, the pixels are the native cells.
2. **Time is a scrubber.** 25 annual loss layers become a single control with playback. Loss "burns in" year by year.
3. **Layers stack visibly.** Canopy 2000, annual loss, the land/water mask and the JRC 2020 forest map are toggles on the same stage. This makes the multi-layer argument without a slide.
4. **Two accounts, one plot.** *Declared* (what the supplier said) and *Mapped* (what the layers show) always sit side by side in different colours. The UI never merges them into a verdict. It asks the human a question instead.
5. **Proof is a first-class view.** "Same question, two representations" gets its own tab with big, honest numbers, including where we lose.
6. **Say it once.** Caveats are condensed into short labels, one legend and ⓘ popovers. We do not repeat a three-line disclaimer on every panel. The meaning is kept and the noise is removed.
7. **Unknown looks different from zero.** Unknown or unavailable is always grey and hatched. A computed zero is a plain `0`.

## 3. Visual language: "Night survey"

A dark, map-first instrument. Panels sit quietly around a luminous raster, and colour is reserved for data meaning.

### Colour: one hue per meaning

| Token | Meaning | Use |
| --- | --- | --- |
| `--pl-loss` ember `#ff7a3d` | Tree-cover loss (selected year, post-cut-off) | Map pixels, counts, scrubber bars |
| `--pl-loss-past` rust | Loss in earlier years | Map context only |
| `--pl-forest` mint `#6fe3a0` | JRC 2020 forest class | JRC overlay, JRC counts |
| canopy ramp | Treecover 2000 | Map base only |
| `--pl-water` | Permanent water (datamask 2) | Map |
| `--pl-declared` lilac `#c3a6ff` | Supplier declaration | Declared column, rail dots, cohort declaration column |
| `--pl-proof` lime `#c8f04f` | Exact match / proof / primary action | Proof badges, primary buttons |
| `--pl-review` amber `#ffc94a` | A question for a human (declared ≠ mapped) | Review-question callouts, rail markers |
| `--pl-error` red | Load or integrity failure, encoding mismatch | Errors only |
| `--pl-unknown` + `--pl-hatch` | Unknown / unavailable | Always hatched, never empty |

Rules: lilac never marks an observation, and ember never marks a declaration. Red is never used for a supplier record. A declaration that differs from the map is amber (a question), not red (a violation). Every colour is paired with text or a glyph, so colour is never the only signal.

### Type
- System sans for UI, system mono (`--pl-font-mono`, tabular numerals) for every number, ID, hash and coordinate.
- Scale: 11 / 12 / 13 / 14 / 16 / 20 / 28 / 40 / 56. Eyebrow labels are 11px uppercase with `--pl-tracking-label`.
- Big numbers (stats) use display weight 600 at 28–56px in mono.

### Shape and depth
Hairline borders (`--pl-line`), 8px radius on cards, 4px on chips and cells, and the pill radius on filter chips. Floating map controls use `--pl-shadow-float` over the raster. Avoid nested cards more than two deep.

### Motion
The map camera flies over `--pl-slow` (600ms) and UI transitions take 140–240ms. Year playback runs at about 350ms per year. All motion collapses to zero under `prefers-reduced-motion`, and playback then steps without tweening.

### Iconography
1.7px-stroke 24-grid line icons from `Primitives.tsx`. Glyph vocabulary:
- ◆ lilac, **Declared**
- ■ ember, **Mapped loss**
- ▲ mint, **JRC forest**
- ✓ lime, **Proof**
- ? amber, **Question**
- ▨ hatched, **Unknown**

## 4. Information architecture

Top bar (52px): `plotline` wordmark · `Lot 200001 · Chai Buri, Surat Thani, TH (declared) · 17 plots` · tabs **Map · Cohort · Proof · Live query** · ⌘K · data status chip (`Frozen export · 17/17 identical`).

Hash routes are the source of truth for view, plot and year, so they deep-link for demos and recordings:

| Route | View |
| --- | --- |
| `#/map` | Region overview (no plot selected). This is the landing page. |
| `#/map/P-0005` · `#/map/P-0005/2025` | Plot focus (year optional) |
| `#/cohort` | Cohort barcode and declared-vs-mapped matrix |
| `#/proof` · `#/proof/P-0005/2025` | Representation proof for a plot and year |
| `#/live` | Live query |

The default year is the latest year with data (2025). Unknown or invalid routes fall back to `#/map`. Keyboard: `J`/`K` next/previous plot in the rail (outside editable fields), `/` focuses plot search, ⌘/Ctrl+K opens commands, `Esc` closes dialogs and, on the map, returns to the region view. `←`/`→` change year when the scrubber is focused.

## 5. Screens

### 5.1 Map (review), desktop ≥ 1180px

```
┌ topbar ────────────────────────────────────────────────────────────────────────────┐
├ rail 232 ─┬ map stage (flex) ──────────────────────────────┬ inspector 420 ────────┤
│ search /  │ [Loss|Canopy 2000|Land mask] [+JRC 2020 forest]│ Region brief  (no plot)│
│ All 17    │                                                │   or                   │
│ ◆ Decl. 5 │        Hansen raster, plots outlined           │ Plot detail            │
│ ■ Map. 3  │        (plot focus: native cells, centers)     │                        │
│ ? ≠   8   │ legend ▢▢▢        coords · scale · ⟲ Region    │                        │
│ rows…     ├────────────────────────────────────────────────┤                        │
│           │ scrubber: ▶ 2001 ▁▁▃▁▂…█▅ 2025 | cut-off | win │                        │
└───────────┴────────────────────────────────────────────────┴────────────────────────┘
```

**Rail rows** (36–44px): plot ID (mono), declared ha, ◆ dot (filled = declared indication, hollow = none), ■ dot (filled = mapped loss 2021–23, hollow = none, hatched = unknown), and an amber `?` when ◆ ≠ ■. Filters are pill chips: *All*, *Declared indication*, *Mapped loss 2021–23*, *Declared ≠ mapped*. Counts are derived from data, not hard-coded. Filters affect only the rail, and the UI says so where it matters.

**Map stage**
- Region view: the full raster plus all 17 plot outlines with ID labels at sensible zoom. Click or Enter on a plot flies to it.
- Plot view: the camera fits the plot bbox with padding. The raster stays crisp (no smoothing). Overlays: the exact supplied boundary (`--pl-plot-line`, 2px), outlines of selected native cells (thin), a small dot at each cell centre (shows the centre rule), and the selected year's loss cells filled ember. The data comes from the validated export `plot.evidence`, not the raster.
- Layer modes on the raster: **Loss**, with the selected year bright ember, earlier years rust, later years not yet shown, so playback animates; **Canopy 2000** (ramp); **Land mask** (land grey, water blue, no data hatched). **JRC 2020 forest** is an independent overlay toggle drawn on JRC's own grid. Class 1 shows as a mint tint, and class 0 (valid non-forest) stays transparent.
- Floating legend bottom-left with one line per visible layer. Bottom-right: corner coordinates, the "EPSG:4326 · native cells ≈ 28 m" text, and a "⟲ Region" button. Wheel zoom and drag pan are allowed, but fit buttons are the primary control.
- Hover or focus a pixel to get a small tooltip: `Hansen cell r:c · canopy 2000 78% · loss 2022 · land`, plus `JRC: forest` when the overlay is on. The tooltip footer says *display raster*. Click a selected cell in plot view to pin the exact export values.
- Footnote (single line): *Rendered from the source rasters, not imagery. Counts come from the verified export.*

**Time scrubber** (104px, under the map): a play/pause button, then 25 year columns 2001–2025 with bar heights. In plot view, the bars are the plot's verified `yearly_loss_counts`. In region view, they are the loss-pixel totals from the display raster, labelled *Region · loss pixels (display raster)*. The selected year shows its number, and clicking the number goes to the proof (plot view only). Overlays: a lilac bracket over 2021–2023 marked *Supplier analysis window*, and a vertical tick between 2020 and 2021 marked *EUDR cut-off · 31 Dec 2020*. Unknown counts are hatched bars, never zero-height bars.

**Inspector, region brief (no plot)**
1. Eyebrow `REGION` with the title *17 supplier plots, three layers, 25 years*.
2. One sentence: *The map is the Hansen 2025 v1.13 raster itself. Pick a plot to see what the layers say and what the supplier declared.*
3. Three stat tiles: `17/17` *plots give identical answers from the compact store* (from `summary.exact_match_count` / `plot_count`); `5` *declared indications* (◆); `3` *plots with mapped loss in 2021–23* (■). All are computed from data.
4. A mini declared-vs-mapped matrix for 2021–2023 (rows: declared indication / none; columns: mapped loss / none / unknown; cells list plot IDs as buttons).
5. "Good places to start": up to three plot buttons chosen from data, namely the first ◆-only plot, the first ■-only plot and the plot with the most 2024–25 loss cells. Each has a one-line reason.

**Inspector, plot detail**
1. Header: `P-0001` (h2 `#plot-review-heading`, focusable) · `9.14 ha declared` · small chips (`Smallholder`, `Tier 4+`, supplier `D001`). Actions: **Receipt**, **Proof →** (primary lime).
2. **Two accounts** card, with two columns of equal weight:
   - ◆ *Declared by supplier* (lilac rule): Analysis 2021–23 (named layer `c1_…`), result, mitigation, final status, EUDR declaration, evidence reference (mono) with "file not supplied" when relevant.
   - ■ *Mapped by Plotline* (ember rule): `Hansen 2025 v1.13 · centre rule`, 2021–23 loss cells, 2024–25 loss cells, support state, selected cells. If JRC has loaded: ▲ `JRC 2020 v4`, forest-class cells / selected JRC cells (separate grid).
   - Bottom band: an amber **Question for review**, or a neutral *Declaration and map agree for 2021–23*. Templates are in §6.
3. **Year detail**: `2025` · big count button (`#annual-proof-trigger`, accessible name `Inspect proof for 2025 observed loss cells`) · `of 262 selected cells`. Unknown counts show hatched with their reasons.
4. **Compact copy** line: ✓ *Same answer from compact store* (or mismatch/unavailable) → link to proof.
5. Disclosures (closed by default): **Native cells** (table, year-event filter, "show on map"), **JRC 2020 baseline (separate source)** (full JRC panel, lazy-loaded), and **Analyst note** (local only).

### 5.2 Cohort

- Header: *17 plots × 25 years* · period chips **All years · 2001–2025** / **2021–2023** / **2024–2025** · **Export displayed counts · CSV**.
- **Declared vs mapped** matrix (2021–2023) as a hero. It puts the two accounts side by side, and plot IDs are buttons. Footnote: *Two explanations were tested and do not account for the difference: Hansen 2023 v1.11 (the supplier's era) gives the same 2021–23 counts, and a footprint-overlap rule flags different plots (P-0014, P-0015). See Proof → Research.*
- **Loss barcode**: an accessible `<table>` with one row per plot and one column per year. Cell fill is ember intensity on a log scale, and zero is a faint dot. Positive cells are buttons named `Review P-0001, 2022: 38 observed loss cells`, which open `#/map/P-0001/2022`. Unknown cells are hatched. The left columns show plot ID and ◆ declaration; the optional right column shows ▲ JRC forest cells when JRC has loaded. Column overlays: the lilac 2021–23 bracket and the EUDR cut-off line.
- Period chips restrict the columns, while the barcode remains the same component.

### 5.3 Proof

- h2 `#proof-heading` *Same question. Two representations.* plus a plot/year chip.
- Hero stat row: **17/17** plots with identical full query outputs; **100%** pixel fidelity (raw values + masks across all three bands); **−8.59%** storage at the loader-input boundary; **1.93×** fresh-process load+query and **≈1.0×** hot query (*no hot-query speedup*). Values are read from the export, with each number's boundary in a ⓘ popover.
- Selected plot comparison table: field / original / compact / ✓. The selected year row has `id="proof-selected-year"`. Differing fields are shown in red when present. **Inspect provenance receipt** and **Download comparison**.
- **Storage** chart: horizontal bars for every candidate, including losers and the original. A separately labelled *Standard GeoTIFF control (separate study)* bar shows that it is 0.48% smaller than custom. Lead with the honest sentence: *A standard format with the right settings is within 0.5%; what we ship is the verified pipeline, not a magic codec.*
- **Timing** small multiples (hot vs fresh-process) with dot distributions, units and repetitions.
- **Research** disclosure: what was tried, what lost and what was kept, with links to reports. It covers the learned selector that lost, indexed reads that were slower, the overlap-rule study and the vintage study.
- **Query limits lab** disclosure: the six synthetic cases, clearly labelled *fictitious 4×4 grid*.

### 5.4 Live query

Two columns: **1 · Define a region** (exact plot polygon or temporary rectangle, with bounds inputs) and **2 · Original ↔ compact answer** (status, result, evidence cells, bound receipt). Connection status is a chip in the header. All existing lifecycle states remain (ready, connecting, running, cancelled, rejected, unavailable, invalid response, completed), each with its own styled state, never a generic spinner.

### 5.5 Responsive
- **760–1179px:** the rail becomes a horizontally scrolling plot strip under the top bar, and the map and inspector form two columns (inspector 360px).
- **< 760px:** single column. The plot strip comes first, then the map (55vh), the scrubber (horizontal scroll, selected year centred), then the inspector. The tabs become a scrollable segmented bar. Tables collapse their less-important columns behind a "More columns" toggle instead of forcing a 980px scroll. There must be no horizontal page overflow at 390px.

## 6. Copy

Voice: short, plain, specific. Name the source and version once per panel. Use these replacements consistently:

| Instead of | Say |
| --- | --- |
| "No mapped loss under this query" | `0 loss cells` with the support state beside it |
| repeated disclaimers | one ⓘ popover: *Mapped tree-cover loss is not a legal deforestation finding. Counts are native cells, not hectares.* |
| "Compliant" (as our output) | `EUDR: Compliant` under ◆ *Declared*, never under *Mapped* |

**Question-for-review templates** (2021–2023, declared `c2` vs mapped `periods["2021-2023"].mapped_loss_present`):
- ◆ indication, ■ false: *The supplier reports an indication in 2021–23; the current layer shows no loss under the centre rule. Which layer version and inclusion rule produced it, and what is in `{ref}`?*
- ◆ none, ■ true: *The layer shows loss in {years} (2021–23) that the declaration does not mention. Was it assessed, and was it forest or plantation rotation? Compare the JRC 2020 forest layer.*
- ◆ indication, ■ true: *Both report loss in 2021–23. Inspect `{ref}` for the mitigation evidence.*
- ◆ none, ■ false: *Declaration and map agree for 2021–23.* (neutral, not lime)
- ■ unknown: *Mapped result unknown: {reasons}. No conclusion either way.*

## 7. Truth-state rules (non-negotiable)
Carried over from `HANDOFF.md` §5 and kept in force by the existing validators:
- Known zero ≠ unknown. Partial support with no event = unknown. Partial support with a witnessed event = event (with support shown).
- No `value || 0`, no blanket `Number()`. Use `cell-values.ts`, `comparison-state.ts`, `data.ts` and `jrc-data.ts` helpers.
- Source/compact equality is an engineering agreement, not satellite truth or legal compliance. Mismatch is a technical discrepancy, not evidence against a supplier.
- Supplier fields are shown verbatim with attribution. Plotline never issues a compliance badge.
- JRC stays separate: its own grid, counts, proof and receipt. Never add or compare its counts with Hansen as area. The Hansen year selector does not apply to JRC.
- Raster display images are for display only. Every count presented as evidence comes from the validated exports.
- Cell counts are not hectares. Canopy 2000 is not a 2020 forest baseline.

## 8. Implementation contract

Stack unchanged: React 19 + TypeScript + Vite, no new runtime dependencies. Validation boundaries are unchanged: `data.ts`, `jrc-data.ts`, `live-client.ts`, `comparison-state.ts`, `cell-values.ts` and `types.ts` are **read-only**, apart from additive helpers that are explicitly agreed. `artifacts/`, `engine/`, `data/` and `validation/` are read-only.

**Styling:** every component imports `styles/tokens.css` values through `var(--pl-*)` and uses `styles/base.css` primitives (`.pl-btn`, `.pl-chip`, `.pl-card`, `.pl-eyebrow`, `.pl-stat`, `.pl-table`, `.pl-disclosure`, `.pl-hatch`, `.pl-num`, `.pl-kbd`). View-specific CSS lives in the owning file listed below. `app.css` and `styles/system.css` are retired, so no new code may rely on their classes.

**File ownership (disjoint)**

| Area | Files |
| --- | --- |
| Design system (design owner) | `styles/tokens.css`, `styles/base.css`, `components/Primitives.tsx`, `review/plot-facts.ts` (shared declared/mapped semantics), `design/*` |
| Map | `map/region-raster.ts`, `map/MapStage.tsx`, `map/TimeScrubber.tsx`, `map/projection.ts`, `styles/map.css` |
| Shell | `App.tsx`, `main.tsx`, `index.html`, `shell/*` (routing, top bar, plot rail, command palette, receipt dialog), `ReceiptDetails.tsx`, `styles/shell.css`, `styles/receipt.css`; deletes `app.css` and `styles/system.css` at the end |
| Inspector | `review/*` except `plot-facts.ts` (`RegionBrief.tsx`, `PlotInspector.tsx` and its parts), `CellTable.tsx`, `AnalystNotes.tsx`, `styles/review.css`, `styles/notes.css` |
| Cohort + proof | `CohortIndex.tsx`, `proof/ProofView.tsx`, `Benchmark.tsx`, `EdgeLab.tsx`, `styles/cohort.css`, `styles/proof.css` |
| Live + JRC | `LiveQueryLab.tsx`, `JrcBaseline.tsx`, `styles/live-query.css`, `styles/jrc-baseline.css` |
| Tests (later phase) | `app/tests/*`, `app/checks/*browser*`, `app/checks/experience-*.mjs`, `app/scripts/record-demo.mjs` |

**Component APIs**

```ts
// map/MapStage.tsx (default export)
type MapLayer = "loss" | "canopy" | "mask";
type MapStageProps = {
  plots: Plot[];                       // validated plots
  selectedPlotId: string | null;       // null = region view
  year: number;                        // 2001..2025
  layer: MapLayer; onLayerChange: (l: MapLayer) => void;
  showJrc: boolean; onShowJrcChange: (v: boolean) => void;
  onSelectPlot: (id: string | null) => void;  // null = back to region
  pinnedCell: Cell | null; onPinCell: (c: Cell | null) => void;
};
// map/region-raster.ts
export function useRegionRaster(): {
  status: "loading" | "ready" | "unavailable"; error?: string;
  yearlyLossPixels: number[] | null; // index 0 = 2001 … 24 = 2025, land pixels only (display stat)
  /* plus whatever MapStage needs internally */
};
// map/TimeScrubber.tsx (default export)
type TimeScrubberProps = {
  year: number; onYear: (y: number) => void;
  counts: (number | null)[] | null;  // 25 entries for 2001..2025; null entry = unknown; null = unavailable
  mode: "plot" | "region";
  label: string;                     // e.g. "P-0005 · observed loss cells · Hansen 2025 v1.13"
  onProof?: () => void;              // plot mode: activate the selected-year count
};
// proof/ProofView.tsx (default export)
type ProofViewProps = { plot: Plot; data: Demo; year: number; onReceipt: () => void; onOpenPlot: (id: string, year: number) => void };
// CohortIndex.tsx (default export, existing name)
type CohortProps = { data: Demo; jrc: JrcArtifact | null; onReview: (plotId: string, year: number) => void };
// review/RegionBrief.tsx (default export)
type RegionBriefProps = { data: Demo; onSelectPlot: (id: string) => void };
// review/PlotInspector.tsx (default export)
type PlotInspectorProps = {
  data: Demo; plot: Plot; year: number;
  jrc: JrcArtifact | null; jrcStatus: "idle" | "loading" | "ready" | "error"; jrcError?: string; onLoadJrc: () => void;
  onProof: (origin: "count" | "header") => void; onReceipt: () => void; onPinCell: (cell: Cell) => void;
};
// review/plot-facts.ts: declaredIndication, mappedLoss, periodCount, yearCount, yearSeries, lossYears,
// differs, cleanLabel, evidenceReference, reviewQuestion. Use these everywhere; do not re-derive.
// JrcBaseline.tsx: keep default export JrcBaseline({data, plotId}); add named export
export function JrcSummary(props: { data: JrcArtifact | null; status: "idle" | "loading" | "ready" | "error"; error?: string; plotId: string; onLoad: () => void }): JSX.Element;
// LiveQueryLab.tsx: default export unchanged ({ data, selectedPlotId })
```

**Stable hooks for tests and focus:** `#plot-review-heading`, `#annual-proof-trigger`, `#proof-heading`, `#proof-selected-year`, `#cohort-heading`, `#live-heading`, `#supplier-declaration`. Prefer role and accessible-name queries in tests. Keep these accessible names: tab buttons `Map`, `Cohort`, `Proof`, `Live query`; `Receipt`; `Download receipt JSON`; `Run region`; `Check connection`; `Save note`; `Question or observation`; `Search plots`; `Export displayed counts · CSV`.

**Accessibility:** visible focus (`--pl-focus` 2px outline, 2px offset); dialog focus trap and restore (native `<dialog>`); every map interaction has a non-map path (rail, tables, scrubber buttons); `aria-pressed` on toggles; live regions for async status; contrast ≥ 4.5:1 for text.

## 9. Priorities

- **P0:** shell, Map view (raster + plot focus + scrubber + inspector with two accounts), Cohort barcode + matrix, Proof hero + table + storage, receipts, notes. No regressions in truth states.
- **P1:** Live query restyle, JRC overlay + JRC summary, responsive layout down to 390px, updated browser suites and demo recording.
- **P2:** wheel zoom / pan polish, hover tooltips, playback polish, style-guide page completeness.

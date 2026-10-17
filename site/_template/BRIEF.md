# Writer brief: Plotline explainer pack

Repository: `/Users/speedpowermac/Documents/projects/CODE_MAIN/personal/hack_roll` (branch `guru/explainer-pack`). The pack lives in `site/` and will be published as a static GitHub Pages site. The hub is `site/index.html`.

## Who reads this and why

The project owner has been hands-off while AI agents built Plotline for the SystemEarth track of Hack & Hire Sustainability Edition 2026. Finals and the pitch are on **17 October 2026** (tomorrow). The owner and teammates will read this pack to understand the challenge, the company, the data, what we built, how we made it fast, what we found and what to say on stage. They are smart but not geospatial specialists. The whole pack should take 2½–3 hours. They asked for something **visual and engaging, with motion graphics**, that they can hand to other people.

## Pages and owners

The `event`, `company`, `pitch`, `submit` and `sprites-lab` pages now live in `site/_internal/` and are not published. The published pages are the hub, `brief/`, `data/`, `glossary/` and `presentation/`. See `STYLE.md` for the reader and the limits and citation rules; where this brief says the repo is private or links to docs, `STYLE.md` takes precedence.

| Slug | Title | Minutes | Writer |
| --- | --- | --- | --- |
| `start` | The whole story | 15 | A |
| `event` | The event and the brief | 15 | B |
| `company` | SystemEarth and the EUDR | 20 | C |
| `data` | The data | 25 | C |
| `solution` | How Plotline works | 25 | D |
| `speed` | The speed story | 20 | E |
| `findings` | What the plots show | 15 | D |
| `pitch` | Tomorrow's pitch | 20 | E |
| `submit` | Submission checklist | 10 | B |
| `glossary` | Glossary | look-up | A |

Write only your own pages, as `site/<slug>/index.html`. Do not edit `site/assets/*`, `site/index.html` or other writers' pages. If you need a shared style or helper, put it in your page's own `<style>`/`<script>` with a slug prefix and mention it in your report.

## Look and build rules

- Start from `site/_template/index.html`: same `<head>`, fonts, `../assets/pack.css`, `<body data-page="<slug>">`, `../assets/pack.js` at the end. `pack.js` adds the masthead, table of contents (from each `<section id>` with an `h2`), prev/next pager, scroll reveals (`.rv`), count-ups (`data-count`), bar fills (`.track i[data-w]`), `Pack.instrument(el, {ms, render(t)})` and `Pack.stepper(el, n, show)`. Read both asset files first.
- Visual reference: the ResearchAgent explainers, extracted at `/tmp/tftf-pages/` (live at collaboration95.github.io/theFastandtheFungible). Read `/tmp/tftf-pages/talk/index.html`: prose column plus full-width white "instrument" panels that replay a real result, with a Replay button, a caption line (`.say`) and a source footnote (`.foot`). Match that feel: light only, generous whitespace, big display numbers, the yellow `.hl` marker.
- **Motion graphics:** each page (except the glossary) needs at least three animated or interactive instruments in inline SVG/HTML/CSS/JS. Examples: a grid that fills cell by cell, layers stacking and collapsing, a polygon sweeping over cell centres, bars racing, a timeline scrubber, a stepper walking through a pipeline, a swarm of dots that sort themselves. They must explain something, not decorate. Respect `prefers-reduced-motion` (the helpers already do; your own CSS animations must too).
- Self-contained: no build step, no new libraries or CDNs beyond the Google Fonts link already in the template, no `fetch` of local files. Relative links only (`../data/`, `../speed/#breakthroughs`). Everything must work when served from any sub-path (GitHub Pages serves it under `/<repo>/`).
- Links to repo files: write them as plain text paths in `<code>` (the repo is private, so do not link to github.com).
- Accessible: real headings, `aria-label` on SVGs, buttons are `<button>`, colour is never the only signal, works at 375 px wide.
- Levelled reading: main text at a plain, normal level; extra technical depth inside `<details class="deeper">`.
- Data colours have fixed meanings (see `pack.css`): `--loss` post-2020 loss, `--forest` JRC 2020 forest, `--declared` supplier declarations, `--proof` same answer/exact match, `--review` a question for a reviewer, `--water`, `--unknown`. Label synthetic illustrations with `<span class="chip syn">Synthetic</span>`.

## Truth rules (do not break these)

- **Every number must come from a repo file.** Name the source in the page header `.meta` or panel `.foot`. Do not round differently from the source or invent figures. If two docs disagree, use `docs/lab/decision-layer-report.md` (latest, Phase 4) and say so.
- **Private data:** SystemEarth's sample is private. Never include plot coordinates, real plot outlines, cell footprints, or rows copied from the supplier CSV, and never read or embed files listed in `data/PRIVATE_FILES.txt`. Draw plots as clearly labelled synthetic shapes. Prose analysis, the region's bounding box, plot IDs and aggregate per-plot counts already quoted in the README/writeups are fine.
- **Wording:** follow the "Words to use / avoid" table in `docs/writeups/04-pitch.md`. Say "mapped loss on mapped 2020 forest", not "deforestation found"; "a question for the reviewer", not "red flag"; keep registered plots and new boundaries separate, never one blended "N× faster"; hot times are not end-to-end times; the batch figure needs a batch in hand. Supplier declarations are declarations, not proven violations. Our results are encoding and query evidence, not legal compliance findings.
- **History framing:** the speed work is told as **Decision layers (15 Oct afternoon) → Phase 1 (15 Oct evening) → Phase 2 (night) → Phase 3 (late night) → Phase 4 (16 Oct early morning)**. Leave out the pre-14-October lab history ("Astra" era) except where needed as background (for example, the retained v1 path is the baseline every multiple is measured against).
- Keep required work, suggestions, targets and unknowns distinct (see `AGENTS.md`). Submission format, pitch length and judging weights are **unknown**; say so rather than guessing.

## Sources to read (pick what your pages need, read the actual files)

- Context: `AGENTS.md`, `README.md`, `SystemEarth-track.md`, `docs/writeups/*.md` (start with its README).
- Briefs: `docs/problem_statement_reference.txt`, `docs/transcript_rules_and_constraints.txt`, `docs/sustainability_kickoff_reference.txt`, `docs/event_rules_and_open_questions.txt`.
- Data: `docs/research/company-sample-audit.md`, `docs/research/layer-acquisition.md`, `docs/lab/engine-data-W4.md`, `docs/lab/engine-jrc-report.md`.
- Build and results: `docs/lab/decision-layer-report.md`, `docs/lab/decision-benchmark-notes.md`, `docs/lab/decision-scale-notes.md`, `docs/lab/decision-layer-plan.md`, `validation/decision/report.md`, `docs/lab/interface-v1.md`, `docs/HANDOVER.md`, `engine/README.md`, `app/README.md`, `design/DESIGN.md`.
- The older dark-theme course in `docs/explainer/*.html` covers rasters, plot queries, decision layers, speed and proof with synthetic interactive demos. Mine it for ideas and correct explanations, but rewrite in this pack's style and re-check every number against the sources above.

## Check your work

- Serve with the already-running server at `http://127.0.0.1:8763/` (it serves `site/`), or start your own `python3 -m http.server <free port>` from `site/`. If browser preview tools are available, open your page in a **new tab** (`reuseExistingTab: false`), scroll through it and look at a screenshot; fix layout bugs. At minimum, check there are no console errors and that every relative link resolves.
- Do not commit. Report back: files written, the instruments on each page (one line each), any number you could not source, any style or helper you wished `pack.css`/`pack.js` had, and open questions.

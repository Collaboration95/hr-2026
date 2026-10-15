# W2 visual system — first delivery complete

Owner: W2, managed by Hooke. Delivered 2026-10-13 02:01 UTC. Only three assigned files written; no package edits, dependency installs or Git mutations.

## Changed files

- `app/src/styles/system.css`: offline system typography, mineral/pine/lime/orange tokens, base controls, explicit focus, reduced-motion and forced-color rules. Styles only base HTML, opt-in `pl-` helpers and owned component classes; no assumed application layout.
- `app/src/components/Primitives.tsx`: exact requested named exports `Icon`, `Pill`, `EmptyState`; no extra runtime dependencies. Ten decorative inline SVG icons, four text-bearing pill tones, labelled empty-state section with heading/detail.
- `docs/lab/experience-visual-report.md`: this handoff and verified evidence.

## Integration instructions for Hooke

Import `./styles/system.css` once in `main.tsx`, before lead-owned `app.css`. Import components with `import { Icon, Pill, EmptyState } from './components/Primitives'`.

Main tokens: `--pl-canvas`, `--pl-surface`, `--pl-surface-raised`, `--pl-surface-muted`, `--pl-ink`, `--pl-ink-strong`, `--pl-muted`, `--pl-line`, `--pl-line-strong`, `--pl-accent`, `--pl-accent-ink`, `--pl-warning`, `--pl-warning-surface`, `--pl-warning-ink`, `--pl-positive`, `--pl-positive-surface`, `--pl-positive-ink`, `--pl-focus`. Font tokens: `--pl-font-sans`, `--pl-font-mono`; size tokens: `--pl-text-xs/sm/base/lg/xl/display`; spacing: `--pl-space-1` through `--pl-space-7`; radius: `--pl-radius-sm/md/pill`.

Opt-in button classes: `pl-button--accent` and `pl-button--quiet`. `pl-sr-only` provides visually hidden accessible labels. Base buttons/input/select/textarea have a 44px minimum height; layout overrides remain the lead's responsibility.

`Icon` is decorative (`aria-hidden`, not focusable). Icon-only buttons need their own accessible name. Pills are ordinary spans, not interactive elements or live regions. Always provide explicit text. Use orange for declaration leads, lime for selected/action state, and positive tone for measured agreement where appropriate. Neither positive color nor a check icon establishes legal compliance. Unknown states need explicit text and must not be presented as clear/compliant.

Example integration:

```tsx
<button className="pl-button--accent"><Icon name="proof" />Inspect proof</button>
<Pill tone="warning">Supplier declaration</Pill>
<Pill tone="positive">Source and compact agree</Pill>
<EmptyState title="No matching plots" detail="Try a different plot identifier or clear the search." />
```

## Verification evidence

React/dependencies were initially absent; the lead installed them during this delivery, allowing actual isolated verification. No setup wait was necessary.

- Isolated strict TypeScript check passed with exit code 0:
  `app/node_modules/.bin/tsc --noEmit --strict --jsx react-jsx --moduleResolution bundler --module esnext --target es2022 --skipLibCheck app/src/components/Primitives.tsx`
- Existing esbuild parsed the CSS with zero warnings using `transform(readFileSync('app/src/styles/system.css','utf8'), {loader:'css'})`. No output file written.
- Existing esbuild transformed TSX to CommonJS with automatic JSX; existing React DOM `renderToStaticMarkup` successfully rendered every one of the 10 icons, every one of the 4 pill tones, and an empty state. Actual exports were exactly `EmptyState, Icon, Pill`. The empty-state output had its title as the section accessible label, an h2, detail paragraph, and hidden decorative SVG. No output file written.
- Python standard-library calculation of WCAG sRGB relative luminance checked actual CSS hex values, not guessed contrast. Results:

| Foreground / background | Contrast |
| --- | --- |
| Ink / canvas | 10.80:1 |
| Ink / muted surface | 9.99:1 |
| Muted text / canvas | 5.47:1 |
| Muted text / surface | 6.01:1 |
| Muted text / muted surface | 5.06:1 |
| Accent ink / accent | 9.40:1 |
| Accent ink / accent hover | 8.11:1 |
| Warning ink / warning surface | 7.28:1 |
| Positive ink / positive surface | 8.63:1 |
| Focus / canvas | 5.86:1 |
| Focus / surface | 6.44:1 |
| Focus / muted surface | 5.42:1 |
| Focus / accent | 4.96:1 |

All nine checked text pairs exceed 4.5:1; all four checked focus pairs exceed 3:1. Script also verified every referenced `--pl-` variable is defined and CSS block braces balance. These checks do not establish application-wide accessibility; lead layout/overrides may change actual pairs.

## Browser status and next actions

Discovered actual T3 preview tools through `ALL_TOOLS`. Called `preview_status` first; it reported an available existing research tab. Called `preview_open({reuseExistingTab:false,open:false})` to preserve that shared research tab. New `tab_g` returned `available:false`, `url:null`. No fallback browser or screenshot claim. No local dev endpoint was announced in `docs/lab/experience-report.md` at inspection time.

1. Hooke can integrate these files immediately; no worker blocker remains for first delivery.
2. Run the full app type/build check once `App.tsx` and data integration exist. Isolated component typing has already passed.
3. W3/lead should visually inspect integrated focus, pill wrapping, empty state and controls at mobile width with real app content, and check reduced-motion behavior. No integrated browser validation is claimed here.

## Context read

Read actual `AGENTS.md`, `README.md`, `docs/lab/experience-worker-tasks.md`, `docs/lab/charter.md`, `docs/lab/interface-v1.md`, `docs/problem_statement_reference.txt`, `docs/transcript_rules_and_constraints.txt`, and `docs/sustainability_kickoff_reference.txt`. Design honors declaration versus observation, unknown versus absent loss, and encoding agreement versus source accuracy/compliance. No data or metric was invented to fill the app.

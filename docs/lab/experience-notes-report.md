# C2-A local analyst questions — delivery complete

Delivered 2026-10-13 02:29 UTC. Ownership limited to `app/src/AnalystNotes.tsx`, `app/src/styles/notes.css`, and this report. Prior W2 ownership ended. No integration/package/source changes, dependency installs, Git mutations, external transport or uploads.

## Implemented

Default export `AnalystNotes({plotId,contextKey}:{plotId:string;contextKey:string})`. Importing it also imports its CSS. It reuses the existing download icon, tokens and focus/control styles.

- Blank initial state; labelled native textarea; 4000-character limit enforced both by maxLength and change handler.
- Explicit “Local-only annotation” with text explaining that the note belongs to this plot and supplier record and is not added to evidence.
- Save/edit/clear-via-delete-and-save; status includes local save time and explicit unsaved warning. Success feedback is a polite atomic status. Storage errors are alerts.
- Namespaced localStorage key: `plotline:analyst-note:v1:` + `JSON.stringify([contextKey, plotId])`. Tuple encoding avoids delimiter collisions. Records include schema version, plot ID, context key, exact note text and ISO save timestamp. Saved records are shape/length/identity/date checked before display.
- Module-local drafts survive plot switches and temporary component unmounts. Keyed editor initialization prevents the previous plot's text appearing under a new plot ID. An unsaved draft for another plot/version prompts a nonblocking warning; it is never auto-saved. Reload/close loses unsaved session drafts, explicitly stated.
- Local JSON export includes exact text and context, annotation type, export time, and whether this text was saved locally. Unsaved draft export has `saved_locally:false` and `saved_at:null`. Download is a local Blob with object URL cleanup; no fetch or external endpoint.
- Storage read failures and damaged records produce an honest warning without overwrite. Save/quota failures preserve the draft and previous saved record; export stays available. Save retries storage, clearing the error on actual success.

## Hooke integration

```tsx
import AnalystNotes from './AnalystNotes';
// Under Declaration, with a stable hash of the exact supplier row:
<AnalystNotes plotId={plot.plot_id} contextKey={supplierRowHash} />
```

The lead supplies `supplierRowHash`. Use the exact supplier-row hash, not content_sha256 of the whole evolving artifact or a benchmark/receipt binding. Source/codec regeneration must not detach a note from an unchanged supplier row. Different supplier versions deliberately have separate notes. The component does not edit supplier values, source results, benchmarks, receipts, or compliance status. Lead retains App/types/package integration.

## Actual verification

Strict isolated type check passed twice with exit code 0:

```sh
app/node_modules/.bin/tsc --noEmit --strict --jsx react-jsx --moduleResolution bundler --module esnext --target es2022 --skipLibCheck app/src/AnalystNotes.tsx
```

Existing esbuild parsed `app/src/styles/notes.css` without warnings (`transform(css,{loader:'css'})`). No generated file was written.

T3 `preview_status` then `preview_open` succeeded on my own previously-created `tab_g` at http://127.0.0.1:5173. Used only that tab. Mounted the actual new component in a temporary DOM host via served Vite modules; no app integration file changed. Synthetic UI strings and `TEST-*` IDs were used, never fabricated evidence attached to real plots. No fallback browser was needed.

| Check | Actual result |
| --- | --- |
| Blank and label | Empty textarea; associated label “Question or observation”; maxLength 4000. |
| Unsaved plot switch | Typed synthetic question on TEST-A, switched to TEST-B: blank editor and warning naming TEST-A. Returned to TEST-A: exact unsaved text restored. |
| Supplier-version isolation | Same TEST-A with different context key was blank; original context restored original text. |
| Save and refresh | Saved TEST-A, reloaded page and remounted component: exact 52-character text loaded from localStorage with save time. |
| Quota failure | Injected QuotaExceededError in own tab's Storage.setItem. Save showed “Save failed”, retained revised draft, and storage still held the previous saved text. Restored native function. |
| Export semantics | Intercepted local Blob/anchor click without writing a downloaded file. JSON contained exact revised text, TEST-A, context key, `saved_locally:false`, `saved_at:null`; filename TEST-A-analyst-note.json. Status explicitly said draft remained unsaved. |
| Length boundary | Attempted 4001 characters; actual textarea and state contained 4000. |
| Clear and save | Deleted text then saved: persisted text was empty and feedback said “Note cleared and saved in this browser.” |
| Blocked storage read | Injected SecurityError on getItem for a fresh key. Editor remained blank with a readable alert explaining unavailable/damaged storage and export/retry options. |
| Damaged stored JSON | Seeded only TEST-CORRUPT with `not-json`: warning displayed and malformed original value remained untouched. |
| Keyboard save and recovery | Typed correction, Tab focused Save note with computed 3px outline, Enter saved actual JSON and cleared prior load error. |
| Narrow component rendering | 358px host (310px content): scrollWidth equalled clientWidth 358; textarea width 310. Screenshot visually inspected: heading, scope, label, textarea, counter and both buttons fit. This is a narrow component check, not an integrated mobile-viewport claim. |

Three synthetic storage keys were removed after verification; own tab reloaded to restore the app and discard temporary DOM/mocks. No screenshot files or test files were created outside ownership.

Harness issues, distinguished from product defects: initial dynamic import used a named createRoot export although Vite served CommonJS default; corrected before tests. A live Vite reload later removed the temporary host between checks; remounted. An interrupted storage-fault probe left its mock in that tab; reloaded the realm and repeated the damaged-record and keyboard-save checks cleanly. Final results above are from completed probes, not those interrupted attempts.

## Reproduction and review scope

After lead integration, open a plot, type a question without saving, change plots and return; save and refresh; then edit and export the unsaved draft. Delete and save to clear. Change only contextKey in an isolated render to verify supplier-version isolation. To simulate storage failures in a disposable tab, temporarily replace Storage.prototype.setItem/getItem with throwing functions and always restore in finally or reload afterward. Use only test-prefixed context keys.

Remaining lead/W3 check: integrated declaration placement and actual end-to-end download behavior. This run verified Blob payload and filename without creating a download file. No new benchmark or source-proof assertions were made. The component has no cross-tab editing synchronization; normal explicit last save wins across simultaneous tabs. Browser-site-data deletion removes saved local notes, and development full reload/HMR resets unsaved in-memory drafts as a refresh does.

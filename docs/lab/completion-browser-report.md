# Independent integrated JRC browser review — 14 October 2026

## Result

**Pass with one non-blocking mobile usability suggestion.** This closes the deferred second independent integrated JRC browser review. The review used the real local application and canonical JSON artifacts. It did not change application code or manufacture a successful service response.

## Coverage and evidence

- At 1440px, expanded the separate JRC 2020 v4 companion for P-0003 and P-0001. P-0003's 793 valid class-0 cells render as “Mapped non-forest”; the source result has zero class-1 cells and zero unknown cells. P-0001's 554 class-1 cells render with the positive forest-mapped signal.
- Verified that the browser served the exact Hansen canonical export bytes (SHA-256 `11d5ca337e142dcb6080028f09d5573265dc67e9826e55131aa7515876336555`) and the pinned JRC JSON bytes (SHA-256 `933b3d302b8ec961444a7f252f74deb87f3f186f1b7f8d5bcb5012cb55658f71`). JRC retains its own version, grid, classes, proof and receipt. Selecting a different plot updates its JRC observation. The Hansen 2025 review stays visible and separate; JRC counts are labeled as non-area units that must not be added to or compared as common-resolution Hansen counts.
- Downloaded `plotline-jrc-P-0001.json` from the actual UI and compared the downloaded plot object to the canonical P-0001 JRC artifact. They match exactly; receipt SHA-256 is `4abdfbdabe62c99b9eb5c5e6147c02fc487b07dcbc7ce055c697e80b1f15d6b2`.
- Verified desktop J navigation moves selection away from P-0001 and updates the selected JRC binding. At a 390×844 mobile viewport, J/K moves P-0003 → P-0005 → P-0003; the document remains 390px wide. Left/Right keyboard navigation works on the native-cell region.
- The actual JRC artifact has no unknown plot results (`unknown` summary count 0). To verify the distinct unavailable state without inventing data, a separate browser context aborted the JRC fetch. The UI kept the companion unavailable, inferred no mapped absence, and retained Hansen review. The expected browser network error from that deliberate abort is recorded separately from unexpected console errors.
- No unexpected page errors or console errors occurred.

## UX suggestion

At 390px, the native-cell table is 980px wide inside a 296px horizontal scroll region. The initial view exposes row/column, raw class and mask; the analytical label, native center and corner details need horizontal scrolling. The page explains the scroll and keyboard controls work, so this is not a blocker. For a live demo, consider pinning the analytical observation column or offering a compact mobile row view.

## Repeat

The independent run used an isolated server at port 5193. The integrated runner now uses installed app-local Playwright and the common origin/output settings. With the app running, repeat from the repository root:

```sh
PLOTLINE_QA_ORIGIN=http://127.0.0.1:5183 npm run qa:jrc --prefix app
```

The check reads `artifacts/demo-v1.json` and `artifacts/jrc-baseline-v1.json`, verifies served bytes and the receipt against those files, then writes [machine-readable results](completion-browser-results.json), [the exact downloaded receipt](completion-browser-jrc-receipt-P-0001.json), and three viewport screenshots: [desktop P-0003](completion-browser-jrc-desktop-p0003.png), [desktop P-0001](completion-browser-jrc-desktop-p0001.png), and [390px mobile](completion-browser-jrc-mobile.png).

This browser review verifies integrated display, interaction and artifact binding. It does not independently establish satellite accuracy, environmental ground truth or legal compliance. The keyboard review at the mobile viewport uses browser key events; it does not emulate a physical mobile keyboard.

The lead replayed the portable runner on port 5183 after integration. New runs write to the printed cache directory; the linked evidence above preserves the independent audit.

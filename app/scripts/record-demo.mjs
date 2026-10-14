// Record a real local walkthrough. Installs nothing and uses no remote services.
import assert from "node:assert/strict";
import { rename, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { qaOrigin, qaEvidence } from "./qa-config.mjs";

process.env.PLAYWRIGHT_BROWSERS_PATH ||= fileURLToPath(new URL("../.cache/playwright", import.meta.url));
const { chromium } = await import("playwright");
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  recordVideo: { dir: qaEvidence, size: { width: 1440, height: 1000 } },
});
await context.route("**/*", route =>
  new URL(route.request().url()).origin === qaOrigin ? route.continue() : route.abort(),
);
const page = await context.newPage();
const video = page.video();
const started = Date.now();
const chapters = [];
const errors = [];
page.on("pageerror", error => errors.push(error.message));
async function hold(title, description) {
  chapters.push({ seconds: Math.round((Date.now() - started) / 100) / 10, title, description });
  // Deliberate reading time in the recording; never used as a readiness check.
  await page.waitForTimeout(4000);
}
try {
  await page.goto(qaOrigin);
  await page.getByRole("button", { name: "Show proof", exact: true }).waitFor();
  await hold("Review desk", "P-0003: declarations and missing evidence remain separate from mapped observations.");
  await page.getByRole("button", { name: "Evidence index", exact: true }).click();
  await page.getByRole("heading", { name: "Cohort / year evidence index", exact: true }).waitFor();
  await hold("Cohort evidence", "The 17 real plots share a linked annual observation index.");
  await page.getByRole("button", { name: "Review P-0005, 2025: 11 observed loss cells", exact: true }).click();
  await page.locator("#plot-review-heading").waitFor();
  await hold("Native cells", "P-0005 has 11 selected loss cells in 2025; cell counts are not hectares.");
  await page.getByRole("button", { name: "Show proof", exact: true }).click();
  await page.locator("#proof-heading").waitFor();
  await hold("Encoding proof", "Original and compact results match under the same declared query rule.");
  await page.getByRole("button", { name: "Review desk", exact: true }).click();
  await page.getByRole("button", { name: /^P-0001 / }).click();
  await page.locator(".companion-panel > summary").click();
  await page.getByRole("heading", { name: "2020 baseline observation · JRC v4", exact: true }).scrollIntoViewIfNeeded();
  await page.locator(".jrc-baseline").evaluate(element =>
    window.scrollBy(0, element.getBoundingClientRect().top - 110),
  );
  await hold("Separate forest baseline", "JRC v4 retains its own native grid, classes and receipt. It is not fused with Hansen.");
  await page.getByRole("button", { name: /^P-0003 / }).click();
  await page.getByRole("button", { name: "Query lab", exact: true }).click();
  await page.getByText("Local snapshot ready", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Run region", exact: true }).click();
  await page.getByRole("heading", { name: "Same answer. Inspect the evidence.", exact: true }).waitFor();
  await hold("Live query", "A new read-only P-0003 request reproduces the original and compact answer with bound evidence.");
  assert.deepEqual(errors, []);
} finally {
  await context.close();
  await browser.close();
}
const destination = resolve(qaEvidence, "plotline-demo.webm");
await rename(await video.path(), destination);
await writeFile(resolve(qaEvidence, "plotline-demo.json"), JSON.stringify({
  recorded_at: new Date().toISOString(), origin: qaOrigin,
  recording: "plotline-demo.webm", narration: false,
  note: "Actual local browser walkthrough; use the demo script for narration. No successful service responses were injected.",
  chapters, errors,
}, null, 2) + "\n");
console.log(`Demo recording: ${destination}`);

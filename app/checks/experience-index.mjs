import { qaOrigin, qaEvidence } from '../scripts/qa-config.mjs';
import { resolve } from 'node:path';
import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
process.env.PLAYWRIGHT_BROWSERS_PATH ||= fileURLToPath(
  new URL("../.cache/playwright", import.meta.url),
);
const { chromium } = await import("playwright");
const data = JSON.parse(await readFile("artifacts/demo-v1.json", "utf8"));
const browser = await chromium.launch({ headless: true });
const results = [];
try {
  for (const width of [1440, 390]) {
    const context = await browser.newContext({
      viewport: { width, height: 1000 },
      acceptDownloads: true,
    });
    await context.route("**/*", (route) =>
      new URL(route.request().url()).origin === qaOrigin
        ? route.continue()
        : route.abort(),
    );
    const page = await context.newPage();
    await page.goto(qaOrigin);
    await page
      .getByRole("button", { name: "Evidence index", exact: true })
      .click();
    await page
      .getByRole("heading", {
        name: "Cohort / year evidence index",
        exact: true,
      })
      .waitFor();
    assert.equal(await page.locator(".cohort-table tbody tr").count(), 17);
    const downloadPromise = page.waitForEvent("download");
    await page
      .getByRole("button", {
        name: "Export displayed counts · CSV",
        exact: true,
      })
      .click();
    const download = await downloadPromise;
    const csv = await readFile(await download.path(), "utf8");
    assert.equal(csv.split("\r\n").filter(Boolean).length, 35);
    await page
      .getByRole("button", { name: "All years · 2001–2025", exact: true })
      .click();
    assert.equal(
      await page
        .locator(".cohort-table tbody td:not(.cohort-declaration)")
        .count(),
      425,
    );
    const positives = data.plots.reduce(
      (n, p) =>
        n +
        Object.values(p.source_result.yearly_loss_counts).filter((v) => v > 0)
          .length,
      0,
    );
    assert.equal(
      await page.locator(".cohort-positive button").count(),
      positives,
    );
    await page.screenshot({
      path: resolve(qaEvidence, `index-${width}.png`),
      fullPage: true,
    });
    await page
      .getByRole("button", {
        name: "Review P-0005, 2025: 11 observed loss cells",
        exact: true,
      })
      .click();
    await page.locator("#plot-review-heading").waitFor();
    assert.match(
      await page.locator("#plot-review-heading").innerText(),
      /P-0005/,
    );
    assert.equal(
      await page
        .getByRole("button", {
          name: "Year 2025, 11 observed loss cells",
          exact: true,
        })
        .getAttribute("aria-pressed"),
      "true",
    );
    const focus = await page.evaluate(() => ({
      id: document.activeElement.id,
      top: document.activeElement.getBoundingClientRect().top,
      headerBottom: document.querySelector(".topbar").getBoundingClientRect()
        .bottom,
      overflow: document.documentElement.scrollWidth > innerWidth,
    }));
    assert.equal(focus.id, "plot-review-heading");
    assert.ok(focus.top >= focus.headerBottom);
    assert.equal(focus.overflow, false);
    results.push({
      width,
      rows: 17,
      annualCells: 425,
      positiveButtons: positives,
      csvRows: 34,
      focus,
    });
    await context.close();
  }
  await writeFile(
    resolve(qaEvidence, "index-check.json"),
    JSON.stringify({ captured_at: new Date().toISOString(), results }, null, 2),
  );
  console.log(JSON.stringify({ passed: results.length, results }));
} finally {
  await browser.close();
}

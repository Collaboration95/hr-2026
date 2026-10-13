import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
process.env.PLAYWRIGHT_BROWSERS_PATH ||= fileURLToPath(
  new URL("../.cache/playwright", import.meta.url),
);
const { chromium } = await import("playwright");
import { writeFile } from "node:fs/promises";
const browser = await chromium.launch({ headless: true });
const results = [];
try {
  for (const width of [1440, 390]) {
    const context = await browser.newContext({
      viewport: { width, height: 1000 },
    });
    const page = await context.newPage();
    await context.route("**/*", (route) =>
      new URL(route.request().url()).origin === "http://127.0.0.1:5173"
        ? route.continue()
        : route.abort(),
    );
    await page.goto("http://127.0.0.1:5173");
    await page
      .getByRole("button", { name: "All 17 plots", exact: true })
      .click();
    const measured = await page.evaluate(() => {
      const title = document
        .querySelector(".overview-context")
        .getBoundingClientRect();
      const markers = [...document.querySelectorAll(".plot-geometry")].map(
        (el) => {
          const b = el.getBoundingClientRect();
          return {
            name: el.getAttribute("aria-label"),
            overlapsTitle:
              b.left < title.right &&
              b.right > title.left &&
              b.top < title.bottom &&
              b.bottom > title.top,
          };
        },
      );
      return { title: title.toJSON(), markers, viewport: innerWidth };
    });
    assert.equal(measured.markers.length, 17);
    assert.equal(
      measured.markers.some((m) => m.overlapsTitle),
      false,
    );
    await page.screenshot({
      path: `docs/lab/browser-lead-evidence/overview-${width}.png`,
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Select P-0003 on map", exact: true })
      .focus();
    await page.keyboard.press("Enter");
    assert.equal(await page.locator(".is-overview").count(), 0);
    assert.equal(await page.locator(".native-cell").count(), 87);
    assert.equal(
      await page
        .getByRole("button", { name: "Annual loss", exact: true })
        .isEnabled(),
      true,
    );
    results.push({
      width,
      allMarkersClearTitle: true,
      samePlotKeyboardSelectionFocusesBoundary: true,
      ...measured,
    });
    await context.close();
  }
  console.log(
    JSON.stringify({
      passed: results.length,
      viewports: results.map((x) => x.width),
    }),
  );
  await writeFile(
    "docs/lab/browser-lead-evidence/overview-check.json",
    JSON.stringify({ captured_at: new Date().toISOString(), results }, null, 2),
  );
} finally {
  await browser.close();
}

import { fileURLToPath } from "node:url";
process.env.PLAYWRIGHT_BROWSERS_PATH ||= fileURLToPath(
  new URL("../.cache/playwright", import.meta.url),
);
const { chromium } = await import("playwright");
import { writeFile } from "node:fs/promises";
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  reducedMotion: "reduce",
});
await context.route("**/*", (route) =>
  new URL(route.request().url()).origin === "http://127.0.0.1:5173"
    ? route.continue()
    : route.abort(),
);
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
try {
  await page.goto("http://127.0.0.1:5173");
  await page.getByRole("button", { name: "Show proof", exact: true }).waitFor();
  await page.screenshot({
    path: "docs/lab/browser-lead-evidence/review-p3-desktop.png",
    fullPage: true,
  });
  await page.locator(".queue-row").filter({ hasText: "P-0005" }).click();
  await page
    .getByRole("button", {
      name: "Year 2025, 11 observed loss cells",
      exact: true,
    })
    .click();
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({
    path: "docs/lab/browser-lead-evidence/review-p5-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Show proof", exact: true }).click();
  await page.screenshot({
    path: "docs/lab/browser-lead-evidence/proof-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Back to review", exact: true })
    .click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({
    path: "docs/lab/browser-lead-evidence/review-p5-mobile.png",
    fullPage: true,
  });
  await writeFile(
    "docs/lab/browser-lead-evidence/capture.json",
    JSON.stringify(
      {
        captured_at: new Date().toISOString(),
        errors,
        title: await page.title(),
        fixture:
          "actual canonical P-0003/P-0005; screenshots only, no new engine verification",
      },
      null,
      2,
    ),
  );
  console.log(JSON.stringify({ screenshots: 4, errors }));
} finally {
  await context.close();
  await browser.close();
}

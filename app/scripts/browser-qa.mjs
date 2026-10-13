import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
const appRoot = fileURLToPath(new URL("..", import.meta.url));
const repoRoot = resolve(appRoot, "..");
const env = {
  ...process.env,
  PLAYWRIGHT_MODULE: resolve(appRoot, "node_modules/playwright/index.mjs"),
  PLAYWRIGHT_BROWSERS_PATH: resolve(appRoot, ".cache/playwright"),
};
const install = process.argv.includes("--install");
const live = process.argv.includes("--live");
if (install && live)
  throw new Error("Run browser installation separately from live QA.");
const commands = install
  ? [
      [
        resolve(appRoot, "node_modules/playwright/cli.js"),
        "install",
        "chromium",
        "--only-shell",
      ],
    ]
  : live
    ? [["app/tests/live-service-journey.mjs"]]
    : [
        ["app/tests/live-journey.mjs"],
        ["app/tests/cycle3-journey.mjs"],
        ["app/tests/index-receipt-journey.mjs"],
        ["app/checks/experience-index.mjs"],
        ["app/checks/experience-overview.mjs"],
      ];
for (const args of commands) {
  const result = spawnSync(process.execPath, args, {
    cwd: repoRoot,
    env,
    stdio: "inherit",
  });
  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }
  if (result.status !== 0) {
    if (!install)
      console.error(
        "If the browser is missing, run npm run qa:install-browser --prefix app. Keep the loopback dev server running for QA.",
      );
    process.exit(result.status || 1);
  }
}

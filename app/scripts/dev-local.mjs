// Start only repository-local executables. No installs, exports or remote calls.
import { spawn } from "node:child_process";
import { access } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import net from "node:net";
const root = fileURLToPath(new URL("../../", import.meta.url));
const app = fileURLToPath(new URL("../", import.meta.url));
const python = fileURLToPath(
  new URL("../../.venv-data/bin/python", import.meta.url),
);
const vite = fileURLToPath(
  new URL("../node_modules/vite/bin/vite.js", import.meta.url),
);
const apiPort = Number(process.env.PLOTLINE_LIVE_PORT || 8765);
const webPort = Number(process.env.PLOTLINE_WEB_PORT || 5173);
for (const p of [apiPort, webPort])
  if (!Number.isInteger(p) || p < 1 || p > 65535)
    throw new Error("Local ports must be integers from 1 through 65535.");
if (apiPort === webPort) throw new Error("API and web ports must differ.");
for (const path of [python, vite])
  try {
    await access(path);
  } catch {
    throw new Error(
      `Required local executable missing: ${path}. Follow app/README.md setup first; this command does not install dependencies.`,
    );
  }
async function available(port) {
  await new Promise((resolve, reject) => {
    const s = net.createServer();
    s.once("error", () =>
      reject(
        new Error(
          `127.0.0.1:${port} is already occupied. Stop your existing local service or choose PLOTLINE_WEB_PORT/PLOTLINE_LIVE_PORT. No process was killed.`,
        ),
      ),
    );
    s.listen(port, "127.0.0.1", () => s.close(resolve));
  });
}
await available(apiPort);
await available(webPort);
const children = new Set();
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  process.exitCode = code;
  for (const child of children) child.kill("SIGTERM");
  const timer = setTimeout(() => {
    for (const child of children) child.kill("SIGKILL");
  }, 3000);
  timer.unref();
}
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => stop(0));
function launch(command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: root,
    stdio: "inherit",
    ...options,
  });
  children.add(child);
  child.on("error", (error) => {
    console.error(error.message);
    stop(1);
  });
  child.on("exit", (code) => {
    children.delete(child);
    if (!stopping) stop(code || 1);
  });
  return child;
}
const api = launch(python, [
  "-B",
  "-m",
  "engine.live_server",
  "--port",
  String(apiPort),
  "--allow-origin",
  `http://127.0.0.1:${webPort}`,
]);
let ready = false;
const deadline = Date.now() + 30000;
for (
  let attempt = 0;
  attempt < 120 && Date.now() < deadline && !stopping;
  attempt++
) {
  try {
    const response = await fetch(`http://127.0.0.1:${apiPort}/v1/health`, {
      signal: AbortSignal.timeout(1000),
    });
    const value = await response.json();
    if (
      response.ok &&
      value.schema_version === "plotline.live-health.v1" &&
      value.status === "ready"
    ) {
      ready = true;
      break;
    }
  } catch {}
  await new Promise((resolve) => setTimeout(resolve, 250));
}
if (!ready) {
  if (!stopping)
    console.error(
      "Local API did not become ready within 30 seconds. Check its startup proof/configuration error above.",
    );
  stop(1);
} else if (!stopping) {
  // Copy only exported app artifacts; the canonical files stay unchanged.
  const sync = spawn(python, ["scripts/sync-data.py"], {
    cwd: app,
    stdio: "inherit",
  });
  children.add(sync);
  const code = await new Promise((resolve) => {
    sync.once("error", () => resolve(1));
    sync.once("exit", resolve);
  });
  children.delete(sync);
  if (code !== 0) stop(1);
  else if (!stopping) {
    launch(
      process.execPath,
      [vite, "--host", "127.0.0.1", "--port", String(webPort), "--strictPort"],
      {
        cwd: app,
        env: { ...process.env, PLOTLINE_LIVE_PORT: String(apiPort) },
      },
    );
    console.log(
      `Plotline local lab: http://127.0.0.1:${webPort} — Ctrl-C stops both owned processes.`,
    );
  }
}

import { defineConfig } from "vite";

// Optional read-only service. The destination host can never become remote.
const livePort = Number(process.env.PLOTLINE_LIVE_PORT || "8765");
if (!Number.isInteger(livePort) || livePort < 1 || livePort > 65535) {
  throw new Error("PLOTLINE_LIVE_PORT must be an integer TCP port.");
}
const proxy = {
  "/v1": {
    target: `http://127.0.0.1:${livePort}`,
    changeOrigin: true,
    timeout: 15000,
    proxyTimeout: 15000,
  },
};
export default defineConfig({
  server: { host: "127.0.0.1", proxy },
  preview: { host: "127.0.0.1", proxy },
});

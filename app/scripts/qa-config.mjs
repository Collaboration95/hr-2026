import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = fileURLToPath(new URL("../../", import.meta.url));
const endpoint = new URL(
  process.env.PLOTLINE_QA_ORIGIN ||
    process.env.PLOTLINE_QA_URL ||
    "http://127.0.0.1:5173",
);
if (
  endpoint.protocol !== "http:" ||
  !["127.0.0.1", "localhost", "[::1]"].includes(endpoint.hostname) ||
  endpoint.username || endpoint.password ||
  endpoint.pathname !== "/" || endpoint.search || endpoint.hash
) {
  throw new Error("PLOTLINE_QA_ORIGIN must be an HTTP loopback origin without credentials, a path, query or fragment.");
}

export const qaOrigin = endpoint.origin;
export const qaEvidence = resolve(
  repoRoot,
  process.env.PLOTLINE_QA_OUTPUT ||
    `app/.cache/qa/${new Date().toISOString().replaceAll(":", "-")}-${process.pid}`,
);
mkdirSync(qaEvidence, { recursive: true });

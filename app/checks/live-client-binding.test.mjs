import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import {
  LiveClientError,
  getLiveHealth,
  runLiveQuery,
  validateLiveHealth,
  validateLiveQueryResponse,
} from "../src/live-client.ts";

const root = fileURLToPath(new URL("../../", import.meta.url));
const demo = JSON.parse(
  readFileSync(
    new URL("../../artifacts/demo-v1.json", import.meta.url),
    "utf8",
  ),
);
const synthetic = JSON.parse(
  readFileSync(
    new URL("../../artifacts/synthetic-v1.json", import.meta.url),
    "utf8",
  ),
);
const hash = (text) => createHash("sha256").update(text, "utf8").digest("hex");
const rectangle = (w, s, e, n) => ({
  type: "Polygon",
  coordinates: [
    [
      [w, n],
      [e, n],
      [e, s],
      [w, s],
      [w, n],
    ],
  ],
});
const [step, , west, , , north] = demo.dataset.transform;
const inputs = [
  ...demo.plots.map((p) => ({ id: p.plot_id, geometry: p.geometry })),
  {
    id: "tiny",
    geometry: rectangle(
      west + 0.00001,
      north - 0.00002,
      west + 0.00002,
      north - 0.00001,
    ),
  },
  {
    id: "outside",
    geometry: rectangle(
      west - 0.002,
      north + 0.001,
      west - 0.0015,
      north + 0.0015,
    ),
  },
  {
    id: "partial",
    geometry: rectangle(west - step, north - 2 * step, west + step, north),
  },
].map((x) =>
  JSON.stringify({
    schema_version: "plotline.live-request.v1",
    request_id: x.id,
    expected_snapshot_id: "0".repeat(64),
    geometry: x.geometry,
  }),
);

// Read-only paired controls from the actual Python snapshot/query implementation.
// Until the additive binding fields land, annotate only test copies, explicitly.
const generated = spawnSync(
  fileURLToPath(new URL("../../.venv-data/bin/python", import.meta.url)),
  [
    "-B",
    "-c",
    String.raw`
import json, sys
from engine.live_query import LiveSnapshot
from engine.source import canonical_bytes
snapshot = LiveSnapshot.load()
cases = []
augmented = False
for template in json.load(sys.stdin):
    body = template.replace('"expected_snapshot_id":"' + '0'*64 + '"', '"expected_snapshot_id":"' + snapshot.snapshot_id + '"')
    request = json.loads(body)
    response = snapshot.query(request, body.encode('utf-8'))
    for key in ('source_result', 'compact_result', 'evidence'):
        field = key + '_canonical_json'
        if field not in response:
            augmented = True
            response[field] = canonical_bytes(response[key]).decode('utf-8')
    cases.append({'request':request,'body':body,'response':response})
print(json.dumps({'health':snapshot.health(),'cases':cases,'test_only_canonical_fields_added':augmented},allow_nan=False))
`,
  ],
  {
    cwd: root,
    input: JSON.stringify(inputs),
    encoding: "utf8",
    maxBuffer: 12 * 1024 * 1024,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  },
);
assert.equal(generated.status, 0, generated.stderr);
const controls = JSON.parse(generated.stdout),
  health = controls.health;
const base = controls.cases.find((x) => x.request.request_id === "P-0003");
const clone = () => structuredClone(base.response);
const validate = (value, context = base) =>
  validateLiveQueryResponse(value, context.request, hash(context.body), health);
const reject = (
  name,
  mutate,
  pattern = /Live response rejected|binding|canonical/i,
) =>
  test(name, async () => {
    const value = clone();
    mutate(value);
    await assert.rejects(validate(value), pattern);
  });
const resealReceipt = (r) => {
  r.receipt.canonical_json = JSON.stringify(r.receipt.payload);
  r.receipt.sha256 = hash(r.receipt.canonical_json);
};
const resealHealth = (h) => {
  h.snapshot_canonical_json = JSON.stringify(h.snapshot);
  h.snapshot_id = hash(h.snapshot_canonical_json);
};
const jsonResponse = (value, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
async function mocked(impl, fn) {
  const original = globalThis.fetch;
  globalThis.fetch = impl;
  try {
    return await fn();
  } finally {
    globalThis.fetch = original;
  }
}

test("control provenance and binding-field readiness are explicit", (t) => {
  t.diagnostic(
    controls.test_only_canonical_fields_added
      ? "Canonical fields currently added ONLY to test copies using actual Python canonical_bytes; not an accepted live transport response."
      : "Canonical binding fields came directly from current engine implementation.",
  );
  assert.equal(controls.cases.length, 20);
});
test("actual loaded health passes canonical and declared identity checks", async () =>
  assert.strictEqual(await validateLiveHealth(health), health));
for (const c of controls.cases)
  test(`positive engine control: ${c.request.request_id}`, async () => {
    const response = await validate(c.response, c);
    assert.strictEqual(response, c.response);
    const frozen = demo.plots.find((p) => p.plot_id === c.request.request_id);
    if (frozen)
      assert.deepStrictEqual(response.source_result, frozen.source_result);
    if (c.request.request_id === "tiny")
      assert.equal(response.source_result.selected_cell_count, 0);
    if (c.request.request_id === "outside") {
      assert.ok(response.source_result.out_of_coverage_cell_count > 0);
      assert.equal(
        response.source_result.periods["2021-2023"].mapped_loss_present,
        null,
      );
    }
  });
test("object key order does not change structural equality", async () => {
  const r = clone();
  r.compact_result = Object.fromEntries(
    Object.entries(r.compact_result).reverse(),
  );
  r.receipt.payload = Object.fromEntries(
    Object.entries(r.receipt.payload).reverse(),
  );
  await validate(r);
});
// Explicit synthetic transport controls, not a claim of a verified loaded source.
// Canonical strings below are the exact fixture bytes; no Python serializer is guessed.
function syntheticControl(name) {
  const c = synthetic.cases.find((c) => c.case_id === name),
    h = structuredClone(health),
    r = clone();
  h.snapshot.product = synthetic.dataset.product;
  h.snapshot.grid = {
    shape: synthetic.dataset.shape,
    transform: synthetic.dataset.transform,
    crs: synthetic.dataset.crs,
  };
  resealHealth(h);
  const request = {
    schema_version: "plotline.live-request.v1",
    request_id: `synthetic-${name}`,
    expected_snapshot_id: h.snapshot_id,
    geometry: c.geometry,
  };
  const body = JSON.stringify(request);
  r.request_id = request.request_id;
  r.request_body_sha256 = hash(body);
  r.snapshot_id = h.snapshot_id;
  r.geometry = structuredClone(c.geometry);
  r.geometry_sha256 = hash(JSON.stringify(c.geometry));
  r.native_grid = structuredClone(h.snapshot.grid);
  r.source_result = structuredClone(c.result);
  r.compact_result = structuredClone(c.result);
  r.evidence = {
    complete: true,
    selected_cell_count: c.result.selected_cell_count,
    returned_cell_count: c.evidence.features.length,
    cells: structuredClone(c.evidence),
  };
  for (const key of ["source_result", "compact_result", "evidence"]) {
    r[key + "_canonical_json"] = JSON.stringify(r[key]);
    r.receipt.payload[key + "_sha256"] = hash(r[key + "_canonical_json"]);
  }
  for (const key of [
    "request_id",
    "request_body_sha256",
    "snapshot_id",
    "geometry_sha256",
  ])
    r.receipt.payload[key] = r[key];
  resealReceipt(r);
  return { response: r, request, body, health: h };
}
for (const c of synthetic.cases)
  test(`explicit synthetic nullable/support control: ${c.case_id}`, async () => {
    const f = syntheticControl(c.case_id);
    await validateLiveHealth(f.health);
    const r = await validateLiveQueryResponse(
      f.response,
      f.request,
      hash(f.body),
      f.health,
    );
    assert.deepStrictEqual(r.source_result.periods, c.result.periods);
    assert.deepStrictEqual(
      r.source_result.lossyear_histogram,
      c.result.lossyear_histogram,
    );
  });
test("partial absence cannot become false even after self-rehashing", async () => {
  const f = syntheticControl("partial_absence_unknown");
  f.response.source_result.periods["2021-2023"].mapped_loss_present = false;
  await assert.rejects(
    validateLiveQueryResponse(f.response, f.request, hash(f.body), f.health),
    /tri-state/,
  );
});
test("partial witnessed loss cannot disappear into null", async () => {
  const f = syntheticControl("partial_positive_known");
  f.response.source_result.periods["2024-2025"].mapped_loss_present = null;
  await assert.rejects(
    validateLiveQueryResponse(f.response, f.request, hash(f.body), f.health),
    /tri-state/,
  );
});
for (const [name, change] of [
  [
    "wrong snapshot digest",
    (h) => {
      h.snapshot_id = "0".repeat(64);
    },
  ],
  [
    "snapshot object differs from canonical",
    (h) => {
      h.snapshot.product = "altered";
    },
  ],
  [
    "false full raw/mask claim",
    (h) => {
      h.snapshot.full_raw_masks_equal = false;
      resealHealth(h);
    },
  ],
  [
    "unsupported limits",
    (h) => {
      h.limits.max_selected_cells = 100000;
    },
  ],
  [
    "wrong periods",
    (h) => {
      h.periods["2021-2023"][0] = 2020;
    },
  ],
  [
    "missing band identity",
    (h) => {
      h.snapshot.sources.pop();
      resealHealth(h);
    },
  ],
  [
    "source hash missing from declared verified files",
    (h) => {
      h.snapshot.sources[0].sha256 = "0".repeat(64);
      resealHealth(h);
    },
  ],
  [
    "store hash missing from declared verified files",
    (h) => {
      h.snapshot.retained.files[0].sha256 = "0".repeat(64);
      resealHealth(h);
    },
  ],
  [
    "implementation identity changed",
    (h) => {
      h.snapshot.query_implementation_sha256["query.py"] = "0".repeat(64);
      resealHealth(h);
    },
  ],
  [
    "invalid grid",
    (h) => {
      h.snapshot.grid.transform[0] = 0;
      resealHealth(h);
    },
  ],
])
  test(`reject health: ${name}`, async () => {
    const h = structuredClone(health);
    change(h);
    await assert.rejects(validateLiveHealth(h), LiveClientError);
  });
reject("wrong request ID", (r) => {
  r.request_id = "other";
});
reject("wrong exact request-body digest", (r) => {
  r.request_body_sha256 = "0".repeat(64);
});
reject("wrong snapshot ID", (r) => {
  r.snapshot_id = "0".repeat(64);
});
reject("wrong response geometry", (r) => {
  r.geometry.coordinates[0][1][0] += 0.0001;
});
reject("wrong native grid", (r) => {
  r.native_grid.transform[2] += 0.0001;
});
reject("false advertised agreement", (r) => {
  const h = r.compact_result.canopy_histogram;
  const i = h.findIndex((n) => n > 0);
  h[i]--;
  h[(i + 1) % 101]++;
});
reject("nested type-aware difference", (r) => {
  r.source_result.extra = { value: 1 };
  r.compact_result.extra = { value: true };
});
reject("successful mismatch is forbidden by v1", (r) => {
  r.comparison.equal = false;
});
for (const signal of ["true", "false", 0, 1, {}, []])
  reject(`malformed truthy signal ${JSON.stringify(signal)}`, (r) => {
    r.source_result.periods["2021-2023"].mapped_loss_present = signal;
  });
reject("null result is not successful empty result", (r) => {
  r.source_result = null;
});
reject("fractional histogram count", (r) => {
  r.source_result.canopy_histogram[0] = 0.5;
});
reject("year/histogram disagreement", (r) => {
  r.source_result.yearly_loss_counts["2023"]++;
});
reject("count limit cannot be raised by response", (r) => {
  r.source_result.selected_cell_count = 4097;
});
reject("truncated evidence explicitly rejected", (r) => {
  r.evidence.complete = false;
});
reject("missing returned cells rejected", (r) => {
  r.evidence.cells.features.pop();
});
reject("false returned count rejected", (r) => {
  r.evidence.returned_cell_count--;
});
reject("duplicate evidence cell rejected", (r) => {
  r.evidence.cells.features[1] = structuredClone(r.evidence.cells.features[0]);
});
reject("evidence center not native grid rejected", (r) => {
  r.evidence.cells.features[0].properties.center[0] += 0.0001;
});
reject("evidence polygon not native grid rejected", (r) => {
  r.evidence.cells.features[0].geometry.coordinates[0][1][0] += 0.0001;
});
reject("invalid mask cannot claim valid land", (r) => {
  r.evidence.cells.features[0].properties.band_validity[0] = false;
});
reject("evidence canopy cannot contradict returned histogram", (r) => {
  const p = r.evidence.cells.features[0].properties;
  p.treecover2000 = (p.treecover2000 + 1) % 101;
});
reject("receipt hash mismatch", (r) => {
  r.receipt.sha256 = "0".repeat(64);
});
reject("receipt object/canonical mismatch", (r) => {
  r.receipt.payload.request_id = "other";
});
reject("rehashed receipt wrong request ID", (r) => {
  r.receipt.payload.request_id = "other";
  resealReceipt(r);
});
reject("rehashed receipt wrong body digest", (r) => {
  r.receipt.payload.request_body_sha256 = "0".repeat(64);
  resealReceipt(r);
});
reject("rehashed receipt wrong geometry hash", (r) => {
  r.receipt.payload.geometry_sha256 = "0".repeat(64);
  resealReceipt(r);
});
reject("rehashed receipt wrong query rule", (r) => {
  r.receipt.payload.boundary_rule = "intersect any pixel";
  resealReceipt(r);
});
reject("rehashed receipt wrong periods", (r) => {
  r.receipt.payload.periods["2024-2025"] = [2020, 2025];
  resealReceipt(r);
});
reject("result canonical object must match returned result", (r) => {
  r.source_result_canonical_json = "{}";
});
reject("evidence canonical object must match returned wrapper", (r) => {
  r.evidence_canonical_json = JSON.stringify(r.evidence.cells);
});
reject("self-hashed receipt cannot invent evidence hash", (r) => {
  r.receipt.payload.evidence_sha256 = "0".repeat(64);
  resealReceipt(r);
});
reject("self-hashed receipt cannot invent result hashes", (r) => {
  r.receipt.payload.source_result_sha256 =
    r.receipt.payload.compact_result_sha256 = "0".repeat(64);
  resealReceipt(r);
});
reject(
  "unverifiable evidence binding is explicit failure",
  (r) => {
    delete r.evidence_canonical_json;
  },
  /canonical result\/evidence bytes/,
);
reject("request timing cannot claim benchmark", (r) => {
  r.runtime.benchmark = true;
});
for (const n of [-1, Infinity, NaN, "0"])
  reject(`invalid runtime timing ${String(n)}`, (r) => {
    r.runtime.source_query_ms = n;
  });

test("health fetch is fixed same-origin and reads one frozen no-store body", async () => {
  let requests = 0,
    reads = 0;
  await mocked(
    async (url, options) => {
      requests++;
      assert.equal(url, "/v1/health");
      assert.equal(options.method, "GET");
      assert.equal(options.cache, "no-store");
      assert.equal(options.redirect, "error");
      assert.equal(options.mode, "same-origin");
      assert.equal(options.credentials, "omit");
      const response = jsonResponse(health);
      return {
        ok: true,
        status: 200,
        headers: response.headers,
        text: async () => {
          reads++;
          return response.text();
        },
      };
    },
    async () => {
      assert.deepStrictEqual(await getLiveHealth(), health);
    },
  );
  assert.equal(requests, 1);
  assert.equal(reads, 1);
});
test("query serializes exact frozen body, snapshot and geometry once", async () => {
  let requests = 0;
  await mocked(
    async (url, options) => {
      requests++;
      assert.equal(url, "/v1/query");
      assert.equal(options.method, "POST");
      assert.equal(options.body, base.body);
      assert.equal(options.headers["Content-Type"], "application/json");
      return jsonResponse(base.response);
    },
    async () => {
      assert.deepStrictEqual(
        await runLiveQuery(
          base.request.geometry,
          base.request.request_id,
          health,
        ),
        base.response,
      );
    },
  );
  assert.equal(requests, 1);
});
test("caller geometry/health edits cannot change a request during async validation", async () => {
  const g = structuredClone(base.request.geometry),
    h = structuredClone(health);
  await mocked(
    async (_url, options) => {
      assert.equal(options.body, base.body);
      return jsonResponse(base.response);
    },
    async () => {
      const pending = runLiveQuery(g, base.request.request_id, h);
      g.coordinates[0][1][0] += 1;
      h.snapshot_id = "0".repeat(64);
      await pending;
    },
  );
});
for (const geometry of [
  null,
  { type: "Feature", coordinates: [] },
  { type: "Polygon", coordinates: [] },
  {
    type: "Polygon",
    coordinates: [
      [
        [0, 0],
        [1, 1],
        [true, 0],
        [0, 0],
      ],
    ],
  },
  {
    type: "Polygon",
    coordinates: [
      [
        [181, 0],
        [1, 1],
        [0, 1],
        [181, 0],
      ],
    ],
  },
  {
    type: "Polygon",
    coordinates: [
      [
        [0, 0],
        [1, 1],
        [0, 1],
        [2, 2],
      ],
    ],
  },
])
  test(
    "invalid request geometry rejects before fetch " + JSON.stringify(geometry),
    async () => {
      let calls = 0;
      await mocked(
        async () => {
          calls++;
          throw Error("must not fetch");
        },
        async () =>
          await assert.rejects(
            runLiveQuery(geometry, "bad", health),
            (e) => e instanceof LiveClientError && e.kind === "invalid_request",
          ),
      );
      assert.equal(calls, 0);
    },
  );
test("invalid request ID rejects before fetch", async () =>
  await assert.rejects(
    runLiveQuery(base.request.geometry, "bad id", health),
    (e) => e.code === "INVALID_REQUEST",
  ));
test("request geometry limit rejects oversized rings", async () => {
  const ring = Array.from({ length: 513 }, (_, i) => [i % 2, 0]);
  ring[512] = ring[0];
  await assert.rejects(
    runLiveQuery({ type: "Polygon", coordinates: [ring] }, "large", health),
    (e) => e.kind === "invalid_request",
  );
});
test("network failure is optional-service unavailable", async () =>
  await mocked(
    async () => {
      throw new TypeError("connection refused");
    },
    async () =>
      await assert.rejects(
        getLiveHealth(),
        (e) => e.kind === "unavailable" && e.code === "SERVICE_UNAVAILABLE",
      ),
  ));
for (const [name, response, code] of [
  [
    "non-JSON proxy 500",
    () => new Response("proxy failed", { status: 500 }),
    "SERVICE_UNAVAILABLE",
  ],
  [
    "HTML success",
    () =>
      new Response("<html>vite fallback</html>", {
        status: 200,
        headers: { "Content-Type": "text/html" },
      }),
    "INVALID_RESPONSE",
  ],
  [
    "empty JSON success",
    () => new Response("", { headers: { "Content-Type": "application/json" } }),
    "INVALID_RESPONSE",
  ],
  [
    "malformed JSON success",
    () =>
      new Response("{", { headers: { "Content-Type": "application/json" } }),
    "INVALID_JSON_RESPONSE",
  ],
  [
    "wrong success schema",
    () => jsonResponse({ schema_version: "nope" }),
    "INVALID_RESPONSE",
  ],
  [
    "unstructured 404",
    () => new Response("not found", { status: 404 }),
    "HTTP_ERROR",
  ],
])
  test(`transport rejects ${name}`, async () =>
    await mocked(
      async () => response(),
      async () =>
        await assert.rejects(
          getLiveHealth(),
          (e) => e instanceof LiveClientError && e.code === code,
        ),
    ));
for (const [status, code] of [
  [409, "SNAPSHOT_MISMATCH"],
  [422, "QUERY_TOO_LARGE"],
  [500, "COMPARISON_MISMATCH"],
  [503, "BUSY"],
  [503, "NOT_READY"],
])
  test(`structured service error ${code} preserves actionable context`, async () =>
    await mocked(
      async () =>
        jsonResponse(
          {
            schema_version: "plotline.live-error.v1",
            request_id: base.request.request_id,
            error: {
              code,
              message: "Use the current snapshot or a smaller region.",
            },
          },
          status,
        ),
      async () =>
        await assert.rejects(
          runLiveQuery(base.request.geometry, base.request.request_id, health),
          (e) =>
            e.kind === "service" &&
            e.code === code &&
            e.status === status &&
            e.requestId === base.request.request_id,
        ),
    ));
test("service error from different request is rejected", async () =>
  await mocked(
    async () =>
      jsonResponse(
        {
          schema_version: "plotline.live-error.v1",
          request_id: "other",
          error: { code: "BUSY", message: "Busy" },
        },
        503,
      ),
    async () =>
      await assert.rejects(
        runLiveQuery(base.request.geometry, base.request.request_id, health),
        (e) => e.kind === "invalid_response",
      ),
  ));
test("pre-aborted request preserves reason and does not fetch", async () => {
  const c = new AbortController();
  c.abort(new Error("user cancelled"));
  let calls = 0;
  await mocked(
    async () => {
      calls++;
    },
    async () =>
      await assert.rejects(
        getLiveHealth(c.signal),
        (e) => e === c.signal.reason,
      ),
  );
  assert.equal(calls, 0);
});
test("abort during fetch preserves reason", async () => {
  const c = new AbortController();
  await mocked(
    async () => {
      c.abort();
      throw c.signal.reason;
    },
    async () =>
      await assert.rejects(
        getLiveHealth(c.signal),
        (e) => e === c.signal.reason,
      ),
  );
});
test("abort during frozen body read preserves reason", async () => {
  const c = new AbortController();
  await mocked(
    async () => ({
      ok: true,
      status: 200,
      headers: new Headers({ "Content-Type": "application/json" }),
      text: async () => {
        c.abort();
        throw c.signal.reason;
      },
    }),
    async () =>
      await assert.rejects(
        getLiveHealth(c.signal),
        (e) => e === c.signal.reason,
      ),
  );
});
test("late successful body is discarded after cancellation", async () => {
  const c = new AbortController();
  await mocked(
    async () => ({
      ok: true,
      status: 200,
      headers: new Headers({ "Content-Type": "application/json" }),
      text: async () => {
        c.abort();
        return JSON.stringify(health);
      },
    }),
    async () =>
      await assert.rejects(
        getLiveHealth(c.signal),
        (e) => e === c.signal.reason,
      ),
  );
});

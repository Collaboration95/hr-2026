import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  DECISION,
  DECISION_SCHEMA,
  SCREEN,
  decisionFor,
  loadDecisionSummary,
  percentSmaller,
  validateDecisionSummary,
} from "../src/decision-data.ts";
import {
  controlRows,
  deforestFact,
  describeFacts,
  fmtPct,
  fmtSig,
  fmtSize,
  fmtX,
  forestFact,
  heroModel,
  isBaselineRow,
  ladderRows,
  scaleModel,
  yearsText,
} from "../src/decision-model.ts";

// The real engine artifact and the real demo export. No expected figure below is typed in by hand:
// every number is read back from these files, so a regenerated artifact does not break the tests.
const read = async (path) => JSON.parse(await readFile(new URL(path, import.meta.url), "utf8"));
const raw = await read("../../artifacts/decision/summary-v1.json");
const demo = await read("../../artifacts/demo-v1.json");
const fresh = () => structuredClone(raw);
const summary = validateDecisionSummary(raw);
const firstId = Object.keys(raw.plots)[0];
const rejects = (mutate, message) => {
  const bad = fresh();
  mutate(bad);
  assert.throws(() => validateDecisionSummary(bad), /Invalid decision summary/, message);
};

test("the real engine summary validates and covers every demo plot", () => {
  assert.equal(summary.schema, DECISION_SCHEMA);
  assert.deepEqual(Object.keys(summary.plots).sort(), demo.plots.map((p) => p.plot_id).sort());
  for (const plot of demo.plots) {
    // The receipt digest ties each decision answer to the boundary the map shows.
    assert.equal(summary.plots[plot.plot_id].geometry_sha256, plot.receipt.geometry_sha256, plot.plot_id);
    assert.equal(decisionFor(summary, plot.plot_id, plot.receipt.geometry_sha256).status, "ok");
  }
});

test("lookups reject a different boundary and unknown plots", () => {
  assert.equal(decisionFor(summary, firstId, "0".repeat(64)).status, "stale");
  assert.equal(decisionFor(summary, "P-9999").status, "missing");
  assert.equal(decisionFor(summary, "__proto__").status, "missing");
  assert.equal(decisionFor(summary, firstId, null).status, "ok");
});

test("malformed or inconsistent input is rejected, never rendered", () => {
  for (const value of [null, undefined, 3, "text", [], {}]) assert.throws(() => validateDecisionSummary(value), /Invalid decision summary/);
  rejects((b) => { b.schema = "plotline.decision-summary.v2"; }, "schema");
  rejects((b) => { delete b.storage; }, "storage missing");
  rejects((b) => { delete b.contracts[DECISION]; }, "contract text missing");
  rejects((b) => { b.fidelity.cells_compared = "744732"; }, "numeric string");
  rejects((b) => { b.fidelity.cell_mismatches = b.fidelity.cells_compared + 1; }, "more mismatches than cells");
  rejects((b) => { b.fidelity.fuzz_polygons_equal = b.fidelity.fuzz_polygons_compared + 1; }, "more equal than compared");
  rejects((b) => { b.storage.levels[DECISION].file_bytes = 0; }, "zero-byte store");
  rejects((b) => { b.storage.levels[DECISION].vs_baselines.original_all_layers.percent_smaller += 5; }, "percent disagrees with bytes");
  rejects((b) => { b.storage.levels[SCREEN].vs_baselines.original_all_layers.baseline_bytes += 1; }, "baseline disagrees with storage.baselines");
  rejects((b) => { b.speed.push(structuredClone(b.speed[0])); }, "duplicate speed path");
  rejects((b) => { b.speed[0].hot_17_plots_ms = "1.4"; }, "string timing");
  rejects((b) => { b.speed[0].speedup_vs_v1.hot = 0; }, "non-positive speed-up");
  rejects((b) => { b.speed = []; }, "no speed rows");
  rejects((b) => { b.layer_analysis[0].verdict = ""; }, "empty verdict");
  rejects((b) => { b.layer_analysis[0].needed_for = "forest"; }, "needed_for not a list");
  rejects((b) => { b.evidence["stores.json"] = "abc"; }, "short digest");
  rejects((b) => { b.limitations = "none"; }, "limitations not a list");
  rejects((b) => { b.plots = {}; }, "no plots");
  rejects((b) => { b.plots[firstId].geometry_sha256 = "XYZ"; }, "bad geometry digest");
  rejects((b) => { delete b.plots[firstId].outputs[DECISION]; }, "decision output missing");
  rejects((b) => { b.plots[firstId].outputs[DECISION].support = "compliant"; }, "invented support word");
  rejects((b) => { b.plots[firstId].outputs[DECISION].contract = SCREEN; }, "wrong contract tag");
});

test("tri-state outputs must agree with their own counts", () => {
  const out = (b) => b.plots[firstId].outputs[DECISION];
  const withForest = Object.keys(raw.plots).find((id) => raw.plots[id].outputs[DECISION].forest_2020.present === true);
  assert.ok(withForest, "the real artifact has a plot with mapped forest");
  const o = (b) => b.plots[withForest].outputs[DECISION];
  rejects((b) => { o(b).forest_2020.cell_counts.nonforest += 1; }, "classes no longer sum to land cells");
  rejects((b) => { o(b).forest_2020.present = false; }, "present=false with forest cells");
  rejects((b) => { out(b).forest_2020.present = true; out(b).forest_2020.cell_counts = null; }, "present without counts");
  rejects((b) => { o(b).deforestation_after_2020.cell_count += 1; }, "yearly counts disagree with total");
  rejects((b) => { o(b).deforestation_after_2020.yearly_cell_counts.abc = 1; }, "non-year key");
  const zero = Object.keys(raw.plots).find((id) => raw.plots[id].outputs[DECISION].deforestation_after_2020.present === false);
  assert.ok(zero, "the real artifact has a plot with a known zero");
  rejects((b) => { b.plots[zero].outputs[DECISION].deforestation_after_2020.present = true; }, "present=true with zero cells");
});

test("an unanalysable plot (null counts, unknown present, support none) is valid and reads as unknown", () => {
  const b = fresh();
  const o = b.plots[firstId].outputs[DECISION];
  o.forest_2020 = { cell_counts: null, present: null };
  o.deforestation_after_2020 = { yearly_cell_counts: null, cell_count: null, present: null };
  o.valid_land_cell_count = 0;
  o.support = "none";
  const v = validateDecisionSummary(b).plots[firstId].outputs[DECISION];
  assert.equal(forestFact(v).kind, "unknown");
  assert.equal(deforestFact(v).kind, "unknown");
  assert.deepEqual(describeFacts(v), { forest: "unknown", deforestation: "unknown" });
});

test("count present but possibly hidden by unknown cells reads as unknown, never as none", () => {
  const b = fresh();
  const zero = Object.keys(raw.plots).find((id) => raw.plots[id].outputs[DECISION].forest_2020.present === false);
  const o = b.plots[zero].outputs[DECISION];
  const land = o.valid_land_cell_count;
  o.forest_2020 = { cell_counts: { forest: 0, nonforest: land - 3, unknown: 3 }, present: null };
  o.deforestation_after_2020.present = null;
  const v = validateDecisionSummary(b).plots[zero].outputs[DECISION];
  const forest = forestFact(v);
  assert.equal(forest.kind, "unknown");
  assert.match(forest.reason, /no forest seen/);
  assert.equal(deforestFact(v).kind, "unknown");
});

test("panel facts equal the summary for every plot: counts, known zeros, years", () => {
  for (const [id, plot] of Object.entries(raw.plots)) {
    const out = plot.outputs[DECISION];
    const f = forestFact(summary.plots[id].outputs[DECISION]);
    const d = deforestFact(summary.plots[id].outputs[DECISION]);
    if (out.forest_2020.present === true) {
      assert.equal(f.kind, "count", id);
      assert.equal(f.count, out.forest_2020.cell_counts.forest, id);
      assert.equal(f.landCells, out.valid_land_cell_count, id);
    } else assert.equal(f.kind, out.forest_2020.present === false ? "none" : "unknown", id);
    if (out.deforestation_after_2020.present === true) {
      const years = Object.entries(out.deforestation_after_2020.yearly_cell_counts).filter(([, n]) => n > 0);
      assert.equal(d.kind, "count", id);
      assert.equal(d.count, out.deforestation_after_2020.cell_count, id);
      assert.deepEqual(d.years, years, id);
    } else assert.equal(d.kind, out.deforestation_after_2020.present === false ? "none" : "unknown", id);
  }
  // The documented reading for a plot with forest and mapped loss: counts of cells, and the year of the loss.
  const loss = Object.keys(raw.plots).find((id) => raw.plots[id].outputs[DECISION].deforestation_after_2020.present === true);
  const o = raw.plots[loss].outputs[DECISION];
  const [[year, n]] = Object.entries(o.deforestation_after_2020.yearly_cell_counts).filter(([, c]) => c > 0);
  assert.deepEqual(describeFacts(summary.plots[loss].outputs[DECISION]), {
    forest: `${o.forest_2020.cell_counts.forest.toLocaleString("en-US")} cells`,
    deforestation: `${n} cells in ${year}`,
  });
  assert.equal(yearsText([["2022", 2]]), "in 2022");
  assert.equal(yearsText([["2022", 2], ["2024", 1]]), "2022: 2 · 2024: 1");
});

test("headline model reads the summary: storage, identical answers, speed", () => {
  const h = heroModel(summary);
  const vs = raw.storage.levels[DECISION].vs_baselines.original_all_layers;
  assert.equal(h.storage.percent, vs.percent_smaller);
  assert.equal(h.storage.ratio, vs.ratio);
  assert.equal(h.storage.decisionBytes, raw.storage.levels[DECISION].file_bytes);
  assert.equal(h.storage.originalBytes, raw.storage.baselines.original_all_layers);
  assert.equal(h.same.cells, raw.fidelity.cells_compared);
  assert.equal(h.same.equalCells, raw.fidelity.cells_compared - raw.fidelity.cell_mismatches);
  assert.equal(h.same.plotsTotal, Object.keys(raw.plots).length);
  assert.equal(h.same.exact, true, "the exported evidence is fully exact");
  const p5d = raw.speed.find((r) => r.path === "P5d");
  assert.equal(h.speed.index.speedup_vs_v1.hot, p5d.speedup_vs_v1.hot);
  assert.equal(h.speed.index.registered_plots_only, true);
  assert.equal(h.speed.table.path, "P6d");
  // A single mismatch must withdraw the "exact" tone.
  const bad = structuredClone(summary);
  bad.fidelity.cell_mismatches = 1;
  assert.equal(heroModel(bad).same.exact, false);
});

test("ladder rows: bytes and percentages come from storage; drops split by level", () => {
  const rows = Object.fromEntries(ladderRows(summary).map((r) => [r.key, r]));
  assert.deepEqual(Object.keys(rows), ["l0", "l1", "l2", "table"]);
  assert.equal(rows.l0.bytes, raw.storage.baselines.retained_lossless_l0);
  assert.equal(rows.l1.bytes, raw.storage.levels[SCREEN].file_bytes);
  assert.equal(rows.l2.bytes, raw.storage.levels[DECISION].file_bytes);
  assert.equal(rows.table.bytes, raw.speed.find((r) => r.path === "P6d").bytes_read);
  assert.ok(Math.abs(rows.l2.percent - raw.storage.levels[DECISION].vs_baselines.original_all_layers.percent_smaller) < 0.01);
  assert.ok(Math.abs(rows.l1.percent - raw.storage.levels[SCREEN].vs_baselines.original_all_layers.percent_smaller) < 0.01);
  assert.equal(rows.l1.answers, raw.contracts[SCREEN]);
  assert.equal(rows.l2.answers, raw.contracts[DECISION]);
  const only = raw.dropped.filter((d) => /^decision level only:/i.test(d));
  assert.ok(only.length > 0);
  assert.equal(rows.l1.drops.length, raw.dropped.length - only.length);
  assert.equal(rows.l2.drops.length, raw.dropped.length);
  assert.ok(rows.l1.drops.every((d) => !/decision level only/i.test(d)));
  assert.ok(rows.l2.drops.every((d) => !/decision level only/i.test(d)));
  assert.ok(rows.l1.shipped && rows.l2.shipped && !rows.l0.shipped && !rows.table.shipped);
  // Ratios and percentages describe the same quantity.
  for (const r of Object.values(rows)) assert.ok(Math.abs(r.percent - percentSmaller(r.bytes, raw.storage.baselines.original_all_layers)) < 1e-9);
});

test("scale and standard-control lines are derived from the summary and agree with the engine's percentages", () => {
  const s = scaleModel(summary);
  const p = raw.tile_scale.percent_smaller;
  assert.ok(Math.abs(s.screenPercent - p.L1_percent_smaller_than_original_total) < 0.01);
  assert.ok(Math.abs(s.decisionPercent - p.L2_percent_smaller_than_original_total) < 0.01);
  assert.ok(Math.abs(s.screenVsYardstick - p.L1_percent_smaller_than_zstd19_yardstick) < 0.01);
  assert.ok(Math.abs(s.decisionVsYardstick - p.L2_percent_smaller_than_zstd19_yardstick) < 0.01);
  const [dec, scr] = controlRows(summary);
  assert.equal(dec.contract, DECISION);
  assert.equal(dec.control, raw.storage.levels[DECISION].best_standard_control_bytes);
  assert.equal(dec.controlName, raw.storage.levels[DECISION].best_standard_control);
  assert.equal(scr.control, raw.storage.levels[SCREEN].best_standard_control_bytes);
  assert.equal(dec.oursIsSmaller, dec.ours < dec.control);
});

test("exactly one speed row is the baseline", () => {
  assert.deepEqual(summary.speed.filter(isBaselineRow).map((r) => r.path), ["P0"]);
});

test("formatters", () => {
  assert.equal(fmtSize(6142), "6.1 KB");
  assert.equal(fmtSize(623237), "623 KB");
  assert.equal(fmtSize(421910035), "421.9 MB");
  assert.equal(fmtSize(512), "512 B");
  assert.equal(fmtPct(99.015), "99.0%");
  assert.equal(fmtX(529.06), "529×");
  assert.equal(fmtX(26.09), "26×");
  assert.equal(fmtX(2.24), "2.2×");
  assert.equal(fmtX(0.79), "0.79×");
  assert.equal(fmtSig(117.137), "117");
  assert.equal(fmtSig(1.4766), "1.48");
  assert.equal(fmtSig(0.002791), "0.00279");
  assert.equal(fmtSig(12345.6), "12,346");
});

test("loader: valid file resolves; missing, HTML, invalid and aborted requests reject", async (t) => {
  const real = globalThis.fetch;
  t.after(() => { globalThis.fetch = real; });
  const reply = (body, init = { status: 200 }) => { globalThis.fetch = async () => new Response(body, init); };
  reply(JSON.stringify(raw));
  assert.deepEqual((await loadDecisionSummary()).plots[firstId], summary.plots[firstId]);
  reply("Not found", { status: 404 });
  await assert.rejects(loadDecisionSummary(), /HTTP 404/);
  reply("<!doctype html><title>Plotline</title>");
  await assert.rejects(loadDecisionSummary(), /not valid JSON/);
  reply(JSON.stringify({ ...raw, schema: "other" }));
  await assert.rejects(loadDecisionSummary(), /Invalid decision summary/);
  reply("");
  await assert.rejects(loadDecisionSummary(), /not valid JSON/);
  globalThis.fetch = async () => { throw new TypeError("network down"); };
  await assert.rejects(loadDecisionSummary(), /could not be fetched/);
  const controller = new AbortController();
  controller.abort();
  reply(JSON.stringify(raw));
  await assert.rejects(loadDecisionSummary(controller.signal), (e) => e.name === "AbortError");
});

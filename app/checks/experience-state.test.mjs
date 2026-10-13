import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { comparisonState, sameValue } from "../src/comparison-state.ts";
import {
  availableBand,
  canopyLabel,
  lossLabel,
  maskLabel,
  isYearEvent,
} from "../src/cell-values.ts";
const demo = JSON.parse(
  await readFile(
    new URL("../../artifacts/demo-v1.json", import.meta.url),
    "utf8",
  ),
);
const p = demo.plots.find((p) => p.plot_id === "P-0003");
test("real compared plots agree by full output, not just the flag", () => {
  for (const plot of demo.plots)
    assert.equal(
      comparisonState(plot),
      plot.compact_result ? "match" : "unavailable",
    );
});
test("contradictory advertised equality cannot produce a success state", () => {
  const bad = structuredClone(p);
  bad.compact_result = structuredClone(bad.source_result);
  bad.compact_result.yearly_loss_counts["2023"] += 1;
  bad.comparison = { ...bad.comparison, equal: true };
  assert.equal(comparisonState(bad), "mismatch");
});
test("uncomputed compact is unavailable even with a claimed match", () => {
  assert.equal(
    comparisonState({
      ...p,
      compact_result: null,
      comparison: { ...p.comparison, equal: true },
    }),
    "unavailable",
  );
});
test("equality preserves null false and zero while ignoring object key order", () => {
  assert.equal(
    sameValue({ a: null, b: false, c: 0 }, { c: 0, b: false, a: null }),
    true,
  );
  for (const v of [false, 0, "", undefined])
    assert.equal(sameValue({ flag: null }, { flag: v }), false);
  assert.equal(sameValue([0, null], [null, 0]), false);
});
const fixture = () => ({
  properties: {
    row: 0,
    col: 0,
    treecover2000: 80,
    lossyear: 0,
    datamask: 1,
    valid_land: true,
    in_coverage: true,
    band_validity: [true, true, true],
    center: [0, 0],
  },
  geometry: { type: "Polygon", coordinates: [] },
});
test("known land zero is a mapped-absence code; null is unavailable", () => {
  const c = fixture();
  assert.equal(lossLabel(c), "No mapped event");
  c.properties.lossyear = null;
  assert.equal(lossLabel(c), "Unavailable");
  assert.equal(isYearEvent(c, 2000), false);
});
test("outside coverage and masked raw values cannot appear as absence", () => {
  const outside = fixture();
  outside.properties.in_coverage = false;
  outside.properties.valid_land = false;
  assert.equal(lossLabel(outside), "Unavailable");
  assert.equal(canopyLabel(outside), "Unavailable");
  assert.equal(maskLabel(outside), "Unavailable");
  const masked = fixture();
  masked.properties.band_validity[1] = false;
  assert.equal(availableBand(masked, 1), null);
  assert.equal(lossLabel(masked), "Unavailable");
});
test("nonland raw zero is excluded, not an analytical no-loss finding", () => {
  const water = fixture();
  water.properties.datamask = 2;
  water.properties.valid_land = false;
  assert.equal(lossLabel(water), "Raw code 0 · excluded");
  water.properties.lossyear = 25;
  assert.equal(isYearEvent(water, 2025), false);
  assert.match(maskLabel(water), /Permanent water/);
});

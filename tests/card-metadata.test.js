// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
import { measurementFacts, sourceSelection } from "../web/src/card-metadata.js";

test("uncalibrated video retains frame coverage without inventing physical units", () => {
  const facts = measurementFacts(
    { uncalibrated: true, position_unit: "px" },
    { unit: "frames", mode: "all", used: 45, total: 45 },
  );
  assert.deepEqual(
    facts.map((f) => f.value),
    ["45/45", "Interval unverified", "px · Scale unverified"],
  );
  assert.equal(facts[0].label, "Frames");
  assert.ok(facts[1].unverified && facts[2].unverified);
});

test("counts distinct time points in an uncalibrated repeated-frame export", () => {
  const facts = measurementFacts(
    { uncalibrated: true, position_unit: "video px" },
    { unit: "timepoints", mode: "all", used: 34, total: 34 },
  );
  assert.equal(facts[0].label, "Time points");
  assert.equal(facts[1].value, "Interval unverified");
});

test("matrix metadata uses time points and its recorded physical coordinate range", () => {
  const facts = measurementFacts(
    {
      time_range_h: [0, 19.6666666667],
      spatial_range: [0, 383.64],
      position_unit: "µm",
    },
    { unit: "timepoints", mode: "all", used: 119, total: 119 },
  );
  assert.equal(facts[0].label, "Time points");
  assert.equal(facts[1].value, "0–19.67 h");
  assert.equal(facts[2].value, "0–383.64 µm");
  assert.ok(!facts[1].unverified && !facts[2].unverified);
});

test("measurement gaps keep measured coverage rather than reporting the whole padded time grid", () => {
  const facts = measurementFacts(
    { time_range_h: [0, 7.475], spatial_range: [10, 310], position_unit: "µm" },
    {
      unit: "timepoints",
      mode: "measured",
      used: 210,
      total: 300,
      duration_label: "0.25–5.50 h",
    },
  );
  assert.equal(facts[0].value, "Measured 210/300");
  assert.equal(facts[1].value, "0.25–5.50 h");
});

test("a time-calibrated pixel ROI retains its subset count and only flags spatial scale", () => {
  const facts = measurementFacts(
    {
      time_range_h: [0, 16.3333],
      spatial_range: [-119, 119],
      position_unit: "video px",
    },
    { unit: "frames", mode: "subset", used: 99, total: 362 },
  );
  assert.equal(facts[0].value, "Subset 99/362");
  assert.equal(facts[1].value, "0–16.33 h");
  assert.equal(facts[1].unverified, false);
  assert.equal(facts[2].value, "-119–119 video px · Scale unverified");
});

test("source identifiers and developmental conditions remain available in details without duplicate names", () => {
  const record = {
    sample: "Movie 4 · day 4",
    card_context: {
      sample: "Movie 4 · day 4",
      condition: "Temperature unverified",
    },
  };
  const before = JSON.stringify(record);
  assert.deepEqual(sourceSelection(record, {}), ["Movie 4 · day 4"]);
  assert.equal(JSON.stringify(record), before);
  assert.deepEqual(
    sourceSelection(
      { sample: "video5", card_context: { sample: "Video 5" } },
      {},
    ),
    ["Video 5"],
  );

  assert.deepEqual(
    sourceSelection(
      { sample: "Video 1", card_context: { sample: "Video 1 · 0–10 h" } },
      {},
    ),
    ["Video 1 · 0–10 h"],
  );
});

test("distinct sample numbers are never collapsed by substring matching", () => {
  assert.deepEqual(
    sourceSelection({ sample: "P1", card_context: { sample: "P10" } }, {}),
    ["P1", "P10"],
  );
});

test("an approximate physical scale stays visibly qualified without changing numerical limits", () => {
  const record = {
    position_unit: "µm",
    spatial_range: [0, 254.55835989862058],
    spatial_scale_approximate: true,
  };
  const before = JSON.stringify(record);
  const facts = measurementFacts(record);
  assert.equal(facts[2].value, "≈ 0–254.56 µm");
  assert.equal(facts[2].unverified, true);
  assert.equal(JSON.stringify(record), before);
});

test("fixed embryos are counted in phase order independently of elapsed time", () => {
  const facts = measurementFacts(
    {
      phase_ordered: true,
      origin_short: "A–P position in the published plot",
      shape_space_time: [101, 76],
    },
    { mode: "subset", unit: "embryos", used: 76, total: 77 },
  );
  assert.deepEqual(facts, [
    { label: "Embryos", value: "Subset 76/77" },
    { label: "Order", value: "Expression phase" },
    { label: "Position", value: "A–P position in the published plot" },
  ]);
});

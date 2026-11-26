// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
import {
  validRange,
  displayColor,
  selectionData,
} from "../web/src/kymograph.js";

test("inclusive range accepts one sample and rejects reversed/out-of-bounds/fractional indices", () => {
  assert.ok(validRange(1, 1, 3));
  for (const [a, b] of [
    [2, 1],
    [-1, 1],
    [0, 3],
    [0.5, 1],
    [NaN, 2],
  ])
    assert.equal(validRange(a, b, 3), false);
});
test("cropping preserves irregular timestamps, zeros, missing values and original scale", () => {
  const variant = {
    id: "wt",
    x: [0, 0.2, 0.9, 1.3],
    y: [0, 20],
    shape: [2, 4],
    values: new Float32Array([4, 0, NaN, 20, 10, 12, 14, 16]),
    x_unit: "h",
    source_sha256: "verified",
    data_path: "source.npz",
  };
  const copy = [...variant.values];
  const out = selectionData({ id: "example" }, variant, { start: 1, end: 2 });
  assert.deepEqual(out.time, [0.2, 0.9]);
  assert.deepEqual(out.intensity, [
    [0, null],
    [12, 14],
  ]);
  assert.deepEqual(out.inclusive_range, [1, 2]);
  assert.equal(out.source_matrix_sha256, "verified");
  assert.deepEqual([...variant.values], copy);
  assert.throws(
    () => selectionData({ id: "x" }, variant, { start: 3, end: 2 }),
    RangeError,
  );
});
test("fixed full-sample color scale retains missing mask and constant samples are defined", () => {
  const colors = [
    [255, 255, 255],
    [255, 100, 0],
    [120, 0, 0],
  ];
  assert.deepEqual(displayColor(0, 0, 20, colors), colors[0]);
  assert.deepEqual(displayColor(10, 0, 20, colors), colors[1]);
  assert.deepEqual(displayColor(20, 0, 20, colors), colors[2]);
  assert.deepEqual(displayColor(NaN, 0, 20, colors), [241, 243, 246]);
  assert.deepEqual(displayColor(5, 5, 5, colors), colors[0]);
});

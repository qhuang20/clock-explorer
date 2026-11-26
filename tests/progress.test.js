// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
import { redrawStatus, progressCounts } from "../web/src/progress.js";
test("two datasets from one paper count as one redrawn paper", () => {
  const papers = [
    { id: "miao" },
    { id: "pending" },
    { id: "reference", library_role: "reference" },
  ];
  const datasets = [{ id: "miao" }, { id: "segmentoid", paper_id: "miao" }];
  assert.deepEqual(progressCounts(papers, datasets), {
    total: 3,
    redrawn: 1,
    needs_data: 1,
    reference: 1,
  });
  assert.equal(redrawStatus({ id: "new" }, datasets), "needs_data");
});

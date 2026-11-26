// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { videosForDataset } from "../web/src/video-selection.js";
import { sourceSelection } from "../web/src/card-metadata.js";

const read = (name) =>
  JSON.parse(
    readFileSync(new URL(`../catalog/${name}.json`, import.meta.url), "utf8"),
  );
const paper = read("literature").papers.find((p) => p.id === "sonnen-2018");
const media = read("videos").papers[paper.id];
const datasets = read("comparison").datasets;

for (const [id, movie, sample] of [
  ["sonnen-2018-embryo", "movie-s1", "Movie S1"],
  ["sonnen-2018-microfluidic", "movie-s3", "Movie S3"],
]) {
  test(`${sample} keeps its own source label and playback instead of inheriting S2`, () => {
    const record = datasets.find((d) => d.id === id);
    assert.deepEqual(sourceSelection(record, paper), [sample]);
    const selected = videosForDataset(media, paper.id, id);
    assert.deepEqual(
      selected.map((v) => v.id),
      [movie],
    );
    assert.ok(selected[0].source_dataset_ids.includes(id));
    assert.ok(selected[0].sampling_rois[id]);
  });
}

test("unlocated Sonnen Mesp2 sources remain an explicit gap rather than another paper's movie", () => {
  const audit = read("source-audits/sonnen-2018");
  const marker = audit.signals.find((s) => s.target_gene === "Mesp2");
  assert.equal(marker.status, "source_not_found_in_checked_attachments");
  assert.equal(marker.source_movie, null);
  assert.equal(marker.dataset_id, null);
  assert.ok(marker.figure_panels.includes("Figure 1G"));
  assert.equal(
    datasets.filter((d) => d.paper_id === paper.id && /Mesp2/i.test(d.reporter))
      .length,
    0,
  );
});

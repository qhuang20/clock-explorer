// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { videosForDataset } from "../web/src/video-selection.js";

const { papers } = JSON.parse(
  readFileSync(new URL("../catalog/videos.json", import.meta.url), "utf8"),
);
const ids = (paper, dataset = paper) =>
  videosForDataset(papers[paper], paper, dataset).map((video) => video.id);

test("Masamizu shows only the current kymograph source without deleting other movies", () => {
  const before = JSON.stringify(papers["masamizu-2006"]);
  assert.deepEqual(ids("masamizu-2006"), ["movie-2"]);
  assert.equal(JSON.stringify(papers["masamizu-2006"]), before);
  assert.equal(papers["masamizu-2006"].videos.length, 3);
});

test("different Lauschke preparations retain their own source videos", () => {
  assert.deepEqual(ids("lauschke-2013"), ["video-5"]);
  assert.deepEqual(ids("lauschke-2013", "lauschke-2013-mpsm"), ["video-2"]);
  assert.deepEqual(ids("lauschke-2013", "lauschke-2013-embryo"), ["video-1"]);
  assert.deepEqual(ids("lauschke-2013", "lauschke-2013-mesp2"), ["video-6"]);
  assert.deepEqual(ids("lauschke-2013", "unknown-dataset"), []);
});

test("Somitoid and Segmentoid do not inherit each other's selected movie", () => {
  assert.deepEqual(ids("miao-2023"), ["movie-2"]);
  assert.deepEqual(ids("miao-2023", "miao-2023-segmentoid"), ["movie-8"]);
});

test("an illustrative default retains its evidence note and empty catalogues stay empty", () => {
  const [reference] = videosForDataset(papers["rohde-2024"], "rohde-2024");
  assert.equal(reference.id, "position2-her1");
  assert.ok(reference.relation_note.includes("Same embryo"));
  assert.deepEqual(ids("chhabra-2026"), []);
  assert.deepEqual(videosForDataset(undefined, "missing"), []);
});

test("one kymograph keeps one preferred signal movie even with multiple matching inputs", () => {
  const paper = {
    preferred_by_dataset: { sample: "signal" },
    videos: [
      { id: "bf", reporter: "Brightfield", source_dataset_ids: ["sample"] },
      { id: "alternate", reporter: "LuVeLu", source_dataset_ids: ["sample"] },
      { id: "signal", reporter: "LuVeLu", source_dataset_ids: ["sample"] },
    ],
  };
  const before = JSON.stringify(paper);
  assert.deepEqual(
    videosForDataset(paper, "paper", "sample").map((v) => v.id),
    ["signal"],
  );
  assert.equal(JSON.stringify(paper), before);
});

test("structural-only inputs never become playback choices or fallbacks", () => {
  const paper = {
    default_video: "bf",
    preferred_by_dataset: { sample: "bf" },
    videos: [
      {
        id: "bf",
        reporter: "Brightfield",
        used_for_kymograph: true,
        source_dataset_ids: ["sample"],
      },
    ],
  };
  assert.deepEqual(videosForDataset(paper, "paper", "sample"), []);
  assert.deepEqual(videosForDataset(paper, "paper"), []);
  paper.videos[0] = {
    ...paper.videos[0],
    reporter: "Structural channel",
    playback_role: "analysis_only",
  };
  assert.deepEqual(videosForDataset(paper, "paper", "sample"), []);
});

test("an actual marker/brightfield composite remains eligible and unrelated marker movies stay hidden", () => {
  const paper = {
    videos: [
      { id: "other-marker", reporter: "Mesp2-GFP" },
      {
        id: "composite",
        reporter: "LuVeLu / Brightfield",
        source_dataset_ids: ["sample"],
      },
    ],
  };
  assert.deepEqual(
    videosForDataset(paper, "paper", "sample").map((v) => v.id),
    ["composite"],
  );
});

test("Sonnen S2 does not inherit microfluidic or dual-reporter playback", () => {
  assert.deepEqual(ids("sonnen-2018"), ["movie-s2"]);
  const [movie] = videosForDataset(
    papers["sonnen-2018"],
    "sonnen-2018",
    "sonnen-2018",
  );
  assert.equal(
    movie.source_url,
    "https://pmc-oa-opendata.s3.amazonaws.com/PMC5847172.1/mmc3.mp4",
  );
});

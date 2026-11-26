// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import {
  samplingRoiForVideo,
  validateRoiDocument,
  sourceFrameAtTime,
  roiPath,
  rectangleRoi,
  roiReferencePoints,
} from "../web/src/video-roi.js";

const video = {
  id: "source",
  source_sha256: "original",
  playback_sha256: "playback",
  width: 100,
  height: 80,
  frames: 4,
};
const payload = () => ({
  schema_version: 1,
  dataset_id: "sample",
  video_id: "source",
  source_sha256: "original",
  playback_sha256: "playback",
  width: 100,
  height: 80,
  frame_starts_s: [0, 0.1, 0.4, 0.5],
  frames: [
    {
      index: 0,
      bands: [
        [
          [10, 10],
          [20, 10],
          [20, 30],
          [10, 30],
        ],
      ],
      lines: [
        [
          [15, 10],
          [15, 30],
        ],
      ],
    },
    {
      index: 2,
      bands: [
        [
          [25, 10],
          [35, 10],
          [35, 30],
          [25, 30],
        ],
      ],
      lines: [],
    },
  ],
});

test("playback frame lookup follows actual PTS, including variable durations and the final frame", () => {
  const starts = payload().frame_starts_s;
  assert.deepEqual(
    [0, 0.099, 0.1, 0.35, 0.4, 0.499, 0.5, 0.6].map((s) =>
      sourceFrameAtTime(starts, s),
    ),
    [0, 0, 1, 1, 2, 2, 3, 3],
  );
  assert.equal(sourceFrameAtTime(starts, NaN), 0);
  const sanakiPts = [1.872722222, 1.890911111, 1.909088889];
  assert.equal(sourceFrameAtTime(sanakiPts, 1.890911, true), 1);
  assert.equal(sourceFrameAtTime(sanakiPts, 1.89091, false), 0);
});

test("a subset has no ROI outside its measured source frames", () => {
  const data = validateRoiDocument(payload(), video, "sample");
  const frames = new Map(data.frames.map((f) => [f.index, f]));
  assert.equal(
    frames.get(sourceFrameAtTime(data.frame_starts_s, 0.2)),
    undefined,
  );
  assert.equal(
    frames.get(sourceFrameAtTime(data.frame_starts_s, 0.41)).index,
    2,
  );
});

test("a changed primary extraction cannot silently reuse an older overlay", () => {
  assert.throws(() =>
    validateRoiDocument(payload(), video, "sample", "new-matrix"),
  );
  assert.doesNotThrow(() =>
    validateRoiDocument(
      { ...payload(), geometry_input_sha256: "new-matrix" },
      video,
      "sample",
      "new-matrix",
    ),
  );
});

test("fixed references remain separate from a moving supported interval", () => {
  const data = payload();
  data.frames[0].guide_lines = [
    [
      [5, 5],
      [15, 10],
      [15, 30],
    ],
  ];
  data.frames[0].reference_points = [
    [5, 5],
    [15, 35],
  ];
  const frame = validateRoiDocument(data, video, "sample").frames[0];
  assert.deepEqual(roiReferencePoints(frame), [
    [5, 5],
    [15, 35],
  ]);
  assert.notDeepEqual(roiReferencePoints(frame)[0], frame.lines[0][0]);
  assert.deepEqual(roiReferencePoints(payload().frames[0]), [
    [15, 10],
    [15, 30],
  ]);
  for (const extra of [
    {
      guide_lines: [
        [
          [0, NaN],
          [1, 2],
        ],
      ],
    },
    { reference_points: [[0, 0]] },
    {
      reference_points: [
        [0, 0],
        [1, Infinity],
      ],
    },
  ]) {
    const bad = payload();
    Object.assign(bad.frames[0], extra);
    assert.throws(() => validateRoiDocument(bad, video, "sample"));
  }
});

test("overlays reject another dataset, movie, playback copy, dimensions, unsafe coordinates and duplicate frames", () => {
  for (const change of [
    { dataset_id: "other" },
    { video_id: "other" },
    { source_sha256: "wrong" },
    { playback_sha256: "wrong" },
    { width: 99 },
    { frame_starts_s: [0, 0.4, 0.1, 0.5] },
    {
      frames: [
        {
          index: 0,
          bands: [
            [
              [10, NaN],
              [20, 30],
            ],
          ],
        },
      ],
    },
    { frames: [{ index: 0 }, { index: 0 }] },
    { frames: [{ index: 4 }] },
    { frames: [{ index: 0, bands: null }] },
  ])
    assert.throws(() =>
      validateRoiDocument({ ...payload(), ...change }, video, "sample"),
    );
});

test("matching ROI mappings take priority without borrowing another dataset's rectangle", () => {
  const item = {
    source_dataset_ids: ["sample"],
    roi: { x: 1, y: 2, width: 3, height: 4 },
    sampling_rois: { sample: "data/derived/paper/sampling-roi.json" },
  };
  assert.deepEqual(samplingRoiForVideo(item, "sample"), {
    path: "data/derived/paper/sampling-roi.json",
  });
  assert.equal(samplingRoiForVideo(item, "other"), null);
  assert.equal(
    samplingRoiForVideo(
      { sampling_rois: { sample: "data/derived/../secret.json" } },
      "sample",
    ),
    null,
  );
  assert.deepEqual(
    samplingRoiForVideo({ ...item, sampling_rois: {} }, "sample"),
    { rect: item.roi },
  );
  assert.deepEqual(
    samplingRoiForVideo(
      { sampling_roi_diagrams: item.sampling_rois },
      "sample",
    ),
    { path: item.sampling_rois.sample, diagram: true },
  );
});

test("source-coordinate drawing preserves curved vertices and the fixed rectangle", () => {
  assert.equal(
    roiPath([
      [5, 10],
      [15, 25],
      [30, 15],
    ]),
    "M5,10L15,25L30,15",
  );
  assert.equal(
    roiPath(
      [
        [5, 10],
        [15, 25],
      ],
      true,
    ),
    "M5,10L15,25Z",
  );
  assert.deepEqual(
    rectangleRoi({ x: 60, y: 50, width: 35, height: 160 }).bands,
    [
      [
        [60, 50],
        [95, 50],
        [95, 210],
        [60, 210],
      ],
    ],
  );
  assert.throws(() => rectangleRoi({ x: 0, y: 0, width: 0, height: 5 }));
});

const catalog = JSON.parse(readFileSync("catalog/videos.json", "utf8"));
test("each direct video-derived card has an exact dataset-scoped sampling overlay", () => {
  const ids = [
    "masamizu-2006",
    "lauschke-2013",
    "lauschke-2013-embryo",
    "lauschke-2013-mpsm",
    "lauschke-2013-mesp2",
    "sonnen-2018",
    "delaune-2012",
    "sanaki-2022",
    "miao-2023",
  ];
  for (const id of ids) {
    const item = Object.values(catalog.papers)
      .flatMap((p) => p.videos)
      .find((v) => v.source_dataset_ids?.includes(id));
    assert.ok(samplingRoiForVideo(item, id), id);
    for (const [dataset, path] of Object.entries(item.sampling_rois || {})) {
      if (!existsSync("assets/" + path)) continue;
      const doc = JSON.parse(readFileSync("assets/" + path, "utf8"));
      assert.doesNotThrow(
        () => validateRoiDocument(doc, item, dataset),
        dataset,
      );
    }
  }
});

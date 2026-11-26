// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const read = (path) => JSON.parse(fs.readFileSync(path, "utf8"));
const papers = read("catalog/literature.json").papers;
const paper = papers.find((p) => p.id === "masamizu-2006");
const lauschke = papers.find((p) => p.id === "lauschke-2013");
const sonnen = papers.find((p) => p.id === "sonnen-2018");
const other = { ...paper, id: "unchanged-paper" };
const detail = { innerHTML: "" };
const decision = { value: "" };
const dialog = { showModal() {}, scrollTop: 0 };
const savedNotes = { "masamizu-2006": { text: "Existing private note" } };
globalThis.addEventListener = () => {};
globalThis.localStorage = {
  getItem: (key) =>
    key === "clock-explorer-notes-v1" ? JSON.stringify(savedNotes) : null,
  setItem() {},
};
globalThis.location = { href: "http://127.0.0.1/", hash: "" };
globalThis.document = {
  addEventListener() {},
  querySelector: (selector) => {
    if (selector === "#detail") return detail;
    if (selector === "#detailDialog") return dialog;
    if (selector === "#detail select[data-decision]")
      return detail.innerHTML.includes("data-decision=") ? decision : null;
    return null;
  },
};
globalThis.window = {
  CLOCK_DATA: {
    papers: [paper, lauschke, sonnen, other],
    comparison: read("catalog/comparison.json"),
    temporal_coverage: read("catalog/temporal-coverage.json"),
    card_presentation: read("catalog/card-presentation.json"),
  },
  CLOCK_VIDEO_CATALOG: read("catalog/videos.json"),
};
const { openDetail } = await import("../web/src/library.js");
const { dataSources } = await import("../web/src/data-sources.js");
const { notes } = await import("../web/src/context.js");

const pane = (id) =>
  detail.innerHTML.match(
    new RegExp(
      `id="pane-${id}"[^>]*>([\\s\\S]*?)(?=<section class="detailPane"|$)`,
    ),
  )[1];

{
  test(`the first paper opens without Notes and keeps file links and field evidence in their intended panes`, () => {
    assert.doesNotThrow(() => openDetail(paper.id));
    const tabs = [...detail.innerHTML.matchAll(/data-pane="([^"]+)"/g)].map(
      (m) => m[1],
    );
    assert.deepEqual(tabs, ["overview", "media", "data"]);
    assert.ok(detail.innerHTML.includes("Data & sources"));
    assert.ok(!detail.innerHTML.includes('id="pane-sources"'));
    assert.ok(!detail.innerHTML.includes('id="pane-notes"'));
    const overview = pane("overview");
    assert.ok(overview.includes('class="overviewExperiment"'));
    assert.ok(overview.includes('data-verification-source="M7"'));
    assert.ok(overview.includes("37°C"));
    const data = pane("data");
    assert.match(data, /<a href="[^"]*kymograph\.npz" download>/);
    assert.match(data, /<a href="[^"]*provenance\.json" download>/);
    assert.ok(data.includes("Open original video"));
    assert.ok(!data.includes("Source ↗"));
    assert.ok(!/<details[^>]*\sopen(?:[\s>])/.test(detail.innerHTML));
    for (const source of paper.sources)
      assert.ok(
        detail.innerHTML.includes(`data-verification-source="${source.id}"`),
        `Missing verification source ${source.id}`,
      );
    assert.deepEqual(notes, savedNotes);
  });
}

test("other papers retain their existing detail tabs and notes controls", () => {
  openDetail(other.id);
  const tabs = [...detail.innerHTML.matchAll(/data-pane="([^"]+)"/g)].map(
    (m) => m[1],
  );
  assert.deepEqual(tabs, ["overview", "media", "data", "sources", "notes"]);
  assert.ok(detail.innerHTML.includes('id="pane-notes"'));
  assert.equal(decision.value, "Undecided");
});

const cases = [
  [
    "lauschke-2013",
    "video-5",
    "video5-wavefront-comparison.npz",
    "mPSM culture · Segmentation stage",
  ],
  [
    "lauschke-2013-embryo",
    "video-1",
    "video1-fixed-reference/kymograph.npz",
    "Posterior embryo explant",
  ],
  [
    "lauschke-2013-mpsm",
    "video-2",
    "video2-kymograph.npz",
    "mPSM culture · Spreading stage",
  ],
];
{
  for (const [dataset, videoId, matrix, preparation] of cases) {
    test(`${dataset} keeps its experiment, source movie and downloads together`, () => {
      const before = JSON.stringify(lauschke.assets);
      openDetail("lauschke-2013", dataset);
      const tabs = [...detail.innerHTML.matchAll(/data-pane="([^"]+)"/g)].map(
        (m) => m[1],
      );
      assert.deepEqual(tabs, ["overview", "media", "data"]);
      assert.ok(!detail.innerHTML.includes('id="pane-notes"'));
      const overview = pane("overview");
      assert.ok(overview.includes(preparation));
      assert.ok(overview.includes(`data-method-figure="${dataset}"`));
      const figures = pane("media");
      if (dataset === "lauschke-2013") {
        assert.ok(figures.includes('class="methodFlowGrid"'));
        assert.ok(figures.includes("video5-center-rois.png"));
        assert.ok(figures.includes("video5-wavefront-roi.png"));
        assert.ok(figures.includes('class="fold methodReferenceComparison"'));
        assert.ok(figures.includes("video5-wavefront-spatial-comparison.json"));
        assert.ok(figures.includes("video5-center-kymographs.svg"));
        assert.ok(figures.includes("video5-wavefront-spatial-comparison.npz"));
        assert.ok(figures.includes('class="methodComparisonResult"'));
        assert.ok(figures.includes("video5-wavefront-spatial-comparison.svg"));
        assert.ok(!figures.includes("video2-author-line"));
      } else if (dataset === "lauschke-2013-embryo") {
        assert.ok(figures.includes('class="methodFlowGrid"'));
        assert.ok(figures.includes("video1-fixed-reference/roi.png"));
        assert.ok(figures.includes("video1-fixed-reference/provenance.json"));
        assert.ok(figures.includes("video1-fixed-reference/kymograph.npz"));
        assert.ok(figures.includes("20.92 h"));
        assert.ok(!figures.includes('class="fold methodReferenceComparison"'));
        assert.ok(!figures.includes("video1-curved-vs-straight.svg"));
        assert.ok(!figures.includes("video1-processing-roi-450.png"));
        assert.ok(!figures.includes("0–350"));
        assert.ok(!figures.includes("0–450"));
        assert.ok(figures.includes("video1-fixed-reference/all126.png"));
        assert.ok(!figures.includes('class="methodComparisonResult"'));
        assert.ok(!figures.includes("video5-center-rois.png"));
        assert.ok(!figures.includes("video2-author-line"));
      } else {
        assert.ok(figures.includes('class="methodFlowGrid"'));
        assert.ok(figures.includes("video2-roi-review.png"));
        assert.ok(figures.includes("video2-kymograph-comparison-review.svg"));
        assert.ok(figures.includes('class="fold methodReferenceComparison"'));
        assert.ok(!figures.includes("video5-center-rois.png"));
        assert.ok(!figures.includes("video1-roi-review.png"));
      }
      const data = pane("data");
      if (dataset === "lauschke-2013") {
        assert.ok(data.includes("video5-wavefront-center.json"));
        assert.ok(data.includes("video5-wavefront-spatial-comparison.npz"));
        assert.ok(data.includes("video5-wavefront-spatial-comparison.json"));
      }
      assert.match(
        data,
        new RegExp(`<a href="[^"]*${matrix.replaceAll(".", "\\.")}" download>`),
      );
      const video = window.CLOCK_VIDEO_CATALOG.papers[
        "lauschke-2013"
      ].videos.find((v) => v.id === videoId);
      const movieLinks = [...data.matchAll(/href="([^"]+\.mov)"/g)].map(
        (m) => m[1],
      );
      assert.deepEqual([...new Set(movieLinks)], [video.source_url]);
      assert.ok(!data.includes("MOESM295_ESM.mov"));
      assert.ok(!data.includes("MOESM297_ESM.mov"));
      assert.ok(!data.includes("MOESM298_ESM.mov"));
      assert.ok(
        !/<a href="[^"]*\.mov"[^>]*>[^<]*(?:Download matrix)/.test(data),
      );
      for (const [, otherVideoId, otherMatrix] of cases) {
        if (otherVideoId !== videoId) assert.ok(!data.includes(otherMatrix));
      }
      assert.equal(JSON.stringify(lauschke.assets), before);
      assert.deepEqual(notes, savedNotes);
    });
  }
}

test("nested review records expose correctly labeled JSON downloads", () => {
  const path = "data/derived/masamizu-2006/review/record.json";
  const reviewPaper = {
    ...paper,
    assets: [
      {
        level: "matrix",
        label: "Review record",
        local_path: path,
        format: "JSON",
        status: "verified_content",
      },
    ],
  };
  const html = dataSources(reviewPaper);
  assert.ok(html.includes(`href="${path}" download`));
  assert.ok(html.includes("Download file (JSON)"));
  assert.ok(!html.includes("Download matrix (NPZ)"));
});

test("review downloads reject traversal through nested path components", () => {
  const path = "data/derived/masamizu-2006/review/../private.json";
  const reviewPaper = {
    ...paper,
    assets: [
      {
        level: "matrix",
        label: "Invalid record",
        local_path: path,
        format: "JSON",
        status: "verified_content",
      },
    ],
  };
  assert.ok(!dataSources(reviewPaper).includes(`href="${path}"`));
});

test("ROI contact archives have ZIP downloads while unsafe figure paths stay rejected", () => {
  const path =
    "figures/sonnen-2018/s2-candidate-review/all-frame-roi-contacts.zip";
  const unsafe = "figures/sonnen-2018/s2-candidate-review/../private.zip";
  const reviewPaper = {
    ...paper,
    assets: [path, unsafe].map((local_path) => ({
      level: "figure",
      label: "All-frame ROI contacts",
      local_path,
      format: "ZIP",
      status: "verified_content",
    })),
  };
  const html = dataSources(reviewPaper);
  assert.ok(html.includes(`href="${path}" download`));
  assert.ok(html.includes("Download file (ZIP)"));
  assert.ok(!html.includes(`href="${unsafe}"`));
});

{
  test(`Movie S2 keeps the extended ray, approximate-scale record and matching signal video together`, () => {
    openDetail("sonnen-2018");
    assert.deepEqual(
      [...detail.innerHTML.matchAll(/data-pane="([^"]+)"/g)].map((m) => m[1]),
      ["overview", "media", "data"],
    );
    assert.ok(pane("overview").includes('data-verification-source="M9"'));
    const figures = pane("media"),
      data = pane("data");
    assert.ok(figures.includes('class="methodFlowGrid"'));
    assert.ok(figures.includes("s2-final-reference/roi.png"));
    assert.ok(figures.includes("s2-final-reference/all-frames.pdf"));
    assert.ok(figures.includes("sonnen-ap-review.json"));
    assert.ok(figures.includes("s2-smoothed/kymograph.svg"));
    assert.ok(figures.includes("s2-smoothed/smoothing-comparison.svg"));
    assert.ok(data.includes('movie-s2-kymograph.npz" download'));
    assert.ok(data.includes('s2-review/review-provenance.json" download'));
    assert.ok(data.includes("Download file (JSON)"));
    assert.ok(data.includes("movie-s2-origin-review.jpg"));
    assert.ok(data.includes("View review figure"));
    const movieLinks = [...data.matchAll(/href="([^"]+\.mp4)"/g)].map(
      (m) => m[1],
    );
    assert.deepEqual(
      [...new Set(movieLinks)],
      ["https://pmc-oa-opendata.s3.amazonaws.com/PMC5847172.1/mmc3.mp4"],
    );
    assert.ok(!data.includes("mmc4.mp4"));
  });
}

test("local review figure paths reject traversal", () => {
  const reviewPaper = {
    ...paper,
    assets: [
      {
        level: "figure",
        label: "Invalid figure",
        local_path: "figures/paper/review/../private.jpg",
        status: "verified_content",
      },
    ],
  };
  assert.ok(
    !dataSources(reviewPaper).includes(
      'href="figures/paper/review/../private.jpg',
    ),
  );
});

for (const [dataset, movie, primary, directory] of [
  [
    "sonnen-2018-embryo",
    "S1",
    "s1-fixed-70um/kymograph.npz",
    "s1-candidate-review",
  ],
  ["sonnen-2018", "S2", "s2-smoothed/kymograph.npz", "s2-candidate-review"],
  [
    "sonnen-2018-microfluidic",
    "S3",
    "s3-moving-center-review/kymograph.npz",
    "s3-candidate-review",
  ],
]) {
  test(`Movie ${movie} keeps review files scoped to its selected measurement`, () => {
    openDetail("sonnen-2018", dataset);
    const figures = pane("media"),
      data = pane("data"),
      config = window.CLOCK_DATA.card_presentation[dataset];
    assert.ok(figures.includes('class="methodFlowGrid"'));
    assert.ok(
      figures.includes(
        movie === "S3"
          ? "Fixed origin vs tracked center"
          : movie === "S1"
            ? "Midline split · previous vs tracked half"
            : "Outer extension · previous vs extended ray",
      ),
    );
    assert.ok(data.includes(`${primary}" download`));
    assert.ok(data.includes(directory));
    assert.ok(data.includes("Download file (NPZ)"));
    for (const review of config.method_figure.review_comparisons) {
      assert.ok(figures.includes(review.preview));
      if (review.roi) assert.ok(figures.includes(review.roi));
    }
    if (movie !== "S2")
      assert.ok(figures.includes("Spatial-filter comparison"));
    if (movie === "S3") {
      assert.ok(figures.includes("Direction control · matched coverage"));
      assert.ok(!config.axis_polarity);
    }
    for (const other of ["s1", "s2", "s3"]) {
      if (`${other}-candidate-review` !== directory) {
        assert.ok(!figures.includes(`${other}-candidate-review/`));
        assert.ok(!data.includes(`${other}-candidate-review/`));
      }
    }
  });
}

{
  test(`Mesp2 keeps its own target, movie and numeric download`, () => {
    openDetail("lauschke-2013", "lauschke-2013-mesp2");
    assert.ok(pane("overview").includes("<em>Mesp2</em>"));
    assert.ok(!pane("overview").includes("<em>Lfng</em>"));
    const figure = pane("media");
    assert.ok(figure.includes("video6-mesp2-roi.png"));
    assert.ok(figure.includes("video6-mesp2-spatial-comparison.json"));
    assert.ok(figure.includes("video6-mesp2-spatial-comparison.npz"));
    assert.ok(figure.includes("video6-mesp2-spatial-comparison.svg"));
    assert.ok(figure.includes('class="methodComparisonResult"'));
    assert.ok(!figure.includes("video5-wavefront-spatial-comparison.npz"));
    const data = pane("data");
    assert.match(data, /<a href="[^"]*video6-mesp2-kymograph\.npz" download>/);
    assert.ok(data.includes("MOESM297_ESM.mov"));
    assert.ok(!data.includes("video5-wavefront-comparison.npz"));
    assert.ok(!data.includes("MOESM296_ESM.mov"));
    assert.ok(!data.includes("MOESM295_ESM.mov"));
    assert.ok(!data.includes("MOESM298_ESM.mov"));
    assert.ok(!/<a href="[^"]*\.mov"[^>]*>[^<]*(?:Download matrix)/.test(data));
  });
}

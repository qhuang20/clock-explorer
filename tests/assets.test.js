// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
globalThis.window = {};
const { resolveAsset } = await import("../web/src/assets.js");
test("missing research assets use exact registered source and local files retain cache revisions", () => {
  const missing = {
    "figures/x.svg": "https://example.org/x.svg",
    "videos/a.mp4": "https://example.org/a.mp4",
  };
  assert.equal(
    resolveAsset("figures/x.svg?v=1", missing),
    "https://example.org/x.svg",
  );
  assert.equal(resolveAsset("figures/y.svg?v=1", missing), "figures/y.svg?v=1");
  assert.equal(
    resolveAsset("https://example.org/a", missing),
    "https://example.org/a",
  );
});

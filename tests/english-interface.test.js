// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const header = fs
  .readFileSync("web/src/site-header.js", "utf8")
  .replace(/^import .*;\n/m, "");

for (const page of ["app", "help", "license"]) {
  test(`${page}: English navigation works without a translation dictionary despite an old language preference`, () => {
    const mount = { outerHTML: "" };
    vm.runInNewContext(header, {
      initCitationCopy() {},
      document: {
        body: { dataset: { page } },
        querySelector: (selector) => {
          assert.equal(selector, "#siteHeader");
          return mount;
        },
      },
      localStorage: { getItem: () => "zh" },
    });
    assert.match(mount.outerHTML, /Clock Explorer/);
    assert.match(mount.outerHTML, />Kymographs</);
    assert.match(mount.outerHTML, />Library</);
    assert.match(mount.outerHTML, /href="help\.en\.html"/);
    assert.doesNotMatch(mount.outerHTML, /data-language|languageSwitch/);
    if (page !== "app") {
      assert.match(mount.outerHTML, /href="index\.html#view=kymographs"/);
      if (page === "help") assert.match(mount.outerHTML, /aria-current="page"/);
      else assert.doesNotMatch(mount.outerHTML, /aria-current="page"/);
    } else {
      assert.match(mount.outerHTML, /id="kymographsNav"/);
      assert.match(mount.outerHTML, /id="libraryNav"/);
    }
  });
}

test("existing saved decisions migrate to English while private note text and storage remain intact", async () => {
  const saved = {
    paper: {
      decision: "\u4f18\u5148\u8bd5\u9a8c",
      text: "Existing private note: \u539f\u59cb\u7b14\u8bb0",
    },
  };
  let writes = 0;
  globalThis.window = { CLOCK_DATA: { papers: [] } };
  globalThis.location = { hash: "" };
  globalThis.localStorage = {
    getItem: (key) => {
      assert.equal(key, "clock-explorer-notes-v1");
      return JSON.stringify(saved);
    },
    setItem() {
      writes += 1;
    },
  };
  const { notes, DB, t } = await import("../web/src/context.js");
  assert.equal(notes.paper.decision, "Prioritize");
  assert.equal(notes.paper.text, saved.paper.text);
  assert.equal(writes, 0);
  assert.equal(DB, window.CLOCK_DATA);
  assert.equal(t("Selected {count} papers", { count: 2 }), "Selected 2 papers");
});

// SPDX-License-Identifier: MIT

export { formatText as t } from "./text.js";
export const DB = window.CLOCK_DATA;
export const RAW_DB = DB;
export const state = {
  view: "table",
  selected: new Set(),
  filters: {},
  query: "",
  section:
    location.hash === "#library" ||
    new URLSearchParams(location.hash.slice(1)).get("view") === "library"
      ? "library"
      : "kymographs",
};
export let notes = {};
try {
  notes = JSON.parse(localStorage.getItem("clock-explorer-notes-v1") || "{}");
  // Preserve previously saved system decisions; free-text notes stay untouched.
  const legacyDecisions = {
    "\u672a\u51b3\u5b9a": "Undecided",
    "\u4f18\u5148\u8bd5\u9a8c": "Prioritize",
    "\u7b49\u5f85\u6570\u636e": "Awaiting data",
    "\u80cc\u666f\u53c2\u8003": "Background reference",
    "\u6682\u4e0d\u91c7\u7528": "Not selected",
  };
  for (const note of Object.values(notes)) {
    if (note && legacyDecisions[note.decision])
      note.decision = legacyDecisions[note.decision];
  }
} catch {}

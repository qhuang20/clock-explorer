// SPDX-License-Identifier: MIT
import { t, DB } from "./context.js";
import { assetUrl } from "./assets.js";
export const $ = (s) => document.querySelector(s);
export const esc = (v) =>
  String(v ?? t("Unknown")).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
export const safeUrl = (u) => {
  try {
    const x = new URL(assetUrl(u), location.href);
    return ["https:", "http:"].includes(x.protocol) ? x.href : "#";
  } catch {
    return "#";
  }
};
export const link = (u, label) =>
  u
    ? `<a href="${esc(safeUrl(u))}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`
    : "";
let toastTimer;
export function toast(t) {
  $("#toast").textContent = t;
  $("#toast").classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("#toast").classList.remove("show"), 3200);
}
export function csvCell(v) {
  let s =
    typeof v === "object" && v !== null ? JSON.stringify(v) : String(v ?? "");
  if (/^[=+@\-\t\r]/.test(s)) s = "'" + s;
  return '"' + s.replace(/"/g, '""') + '"';
}
export const localFigurePath = (u) =>
  /^figures\/[a-z0-9-]+\/(?:[A-Za-z0-9_-][A-Za-z0-9_.-]*\/)*[A-Za-z0-9_-][A-Za-z0-9_.-]*\.(svg|png|pdf|jpg)$/.test(
    u || "",
  );
export const figureUrl = (u) =>
  localFigurePath(u)
    ? assetUrl(`${u}?v=${encodeURIComponent(DB.asset_revision || "1")}`)
    : safeUrl(u);

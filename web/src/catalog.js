// SPDX-License-Identifier: MIT
import { t, DB } from "./context.js";
import { esc } from "./dom.js";
import { redrawStatus } from "./progress.js";
const summaries = {
  "chhabra-2026": [
    "Temperature scaling",
    "Intensity / phase matrices read",
    "Her7–mVenus",
  ],
  "ilagan-2011": [
    "Real-time Notch activation",
    "Methods reference · no somitogenesis kymograph",
    "Notch-LCI",
  ],
  "lauschke-2013": [
    "Phase-gradient scaling",
    "Video decoded · ROI redrawn",
    "LuVeLu",
  ],
  "sonnen-2018": [
    "Wnt × Notch phase shift",
    "Video decoded · ROI redrawn",
    "Axin2T2A · LuVeLu",
  ],
  "delaune-2012": [
    "Single-cell clock dynamics",
    "Video decoded · ROI redrawn",
    "Her1–Venus",
  ],
  "soroldoni-2014": [
    "A Doppler effect",
    "ROI / LOI annotations only",
    "Looping · Her1::YFP",
  ],
  "tsiairis-2016": [
    "Self-organizing oscillators",
    "Single-frame preview · no time series",
    "LuVeLu",
  ],
  "masamizu-2006": [
    "Unstable cellular oscillators",
    "Video not yet verified",
    "Hes1-Ub1-Luc",
  ],
  "jiang-2000": [
    "Notch synchronization",
    "Cell-movement video only",
    "Bodipy-ceramide",
  ],
  "giudicelli-2007": [
    "Setting the tempo",
    "No continuous imaging data located",
    "ISH / FISH",
  ],
};
export const compact = (p) =>
  (p.compact_title
    ? [p.compact_title, p.availability_summary, p.reporter_short]
    : summaries[p.id] || [p.title, p.availability_summary, p.reporter_short]
  ).map((value) => t(value));
export const species = (p) => p.species_label.split(" · ").pop();
export const datasetPaper = (c) =>
  DB.papers.find((p) => p.id === (c.paper_id || c.id));
// The comparison gallery is the source of truth for completed redraws.
// References are explicitly classified in the catalogue; new candidates need data.
export const comparisonRecords = () => [
  ...DB.comparison.datasets,
  ...methodPreviewRecords(),
];
// Hidden presentations retain their scientific records and files.
export const visibleComparisonRecords = () =>
  comparisonRecords().filter(
    (record) => !DB.card_presentation?.[record.id]?.hidden,
  );
export const progressKeys = ["redrawn", "needs_data", "reference"];
export function paperProgress(p) {
  return redrawStatus(p, comparisonRecords());
}

export function progressInfo(key) {
  return {
    redrawn: [
      t("Redrawn"),
      t(
        "Included in the Kymographs comparison. See each plot for calibration status.",
      ),
    ],
    needs_data: [
      t("Needs data"),
      t(
        "Not redrawn yet: usable time-series data are still missing from our collection.",
      ),
    ],
    reference: [
      t("Background reference"),
      t(
        "Background or methods reference; not included in the Kymographs comparison.",
      ),
    ],
  }[key];
}
export function progressBadge(p) {
  const key = paperProgress(p),
    [label, help] = progressInfo(key);
  return `<span class="redrawStatus ${key}" title="${esc(help)}">${esc(label)}</span>`;
}
export function pendingReason(p) {
  return (
    DB.reconstruction_review.find((r) => r.id === p.id)?.reason ||
    p.missing[0] ||
    t("Awaiting usable time-series data for a redraw.")
  );
}
export function statusLabel(s) {
  return (
    {
      verified_content: t("File read"),
      verified_headers: t("Headers verified"),
      verified_article: t("Article verified"),
      listed: t("Attachment listing only"),
      restricted: t("Restricted access"),
      format_mismatch: t("Format mismatch"),
      unknown: t("Not located / unknown"),
      contact: t("Available on request"),
      not_applicable: t("Not applicable"),
      dead: t("Broken link"),
    }[s] || s
  );
}
export function statusClass(s) {
  return ["verified_content", "verified_headers", "verified_article"].includes(
    s,
  )
    ? "verified"
    : ["listed", "contact"].includes(s)
      ? "listed"
      : ["restricted", "format_mismatch", "dead"].includes(s)
        ? "restricted"
        : "unknown";
}
export function size(a) {
  if (a.bytes != null)
    return t("{count} bytes (measured / response headers)", {
      count: a.bytes.toLocaleString("en"),
    });
  return a.size || t("Size unknown");
}
export function methodPreviewRecords() {
  return DB.papers
    .filter(
      (p) =>
        p.method_figure?.card_preview &&
        !DB.comparison.datasets.some((c) => (c.paper_id || c.id) === p.id),
    )
    .map((p) => {
      const m = p.method_figure;
      return {
        id: p.id,
        short: p.short,
        reporter: p.reporter_short,
        target_gene: p.target_gene,
        compact_card: Boolean(m.compact_card),
        kind: "video",
        uncalibrated: true,
        position_unit: "px",
        common_preview: m.card_preview,
        full_preview: m.card_preview,
        source_url: m.source_url,
        data_url: m.source_url,
        coverage_note: t("{count} frames", { count: m.frame_count }),
        origin_short: t("Frame / pixel axes"),
      };
    });
}

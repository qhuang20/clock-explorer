// SPDX-License-Identifier: MIT
import { RAW_DB, DB, t, state, notes } from "./context.js";
import { $, esc, safeUrl, toast } from "./dom.js";
import { assetUrl } from "./assets.js";
import {
  progressKeys,
  paperProgress,
  progressInfo,
  datasetPaper,
  comparisonRecords,
} from "./catalog.js";
import {
  render,
  updateCompareBar,
  reset,
  openDetail,
  showPane,
  compare,
  download,
} from "./library.js";
import { renderKymographs } from "./gallery.js";
import { showRoi, switchStudyFigure, switchFigureView } from "./figures.js";
import { hideMethodHelp, toggleMethodHelp } from "./tooltips.js";

export function showSection(id) {
  hideMethodHelp();
  state.section = id;
  document.body.classList.toggle("kymoMode", id === "kymographs");
  $("#stats").hidden = id === "kymographs";
  ["library", "kymographs"].forEach((key) => {
    $("#" + key).hidden = key !== id;
    const nav = $("#" + key + "Nav");
    if (!nav) return;
    nav.classList.toggle("active", key === id);
    if (key === id) nav.setAttribute("aria-current", "page");
    else nav.removeAttribute("aria-current");
  });
  updateCompareBar();
}
export function openRedraw(id) {
  const record = comparisonRecords().find((c) => (c.paper_id || c.id) === id);
  if (!record) return;
  renderKymographs();
  showSection("kymographs");
  document.querySelectorAll("dialog[open]").forEach((d) => d.close());
  const card = [...document.querySelectorAll(".kymoCompareCard")].find(
    (el) => el.dataset.dataset === record.id,
  );
  card?.querySelector(".cardOpen")?.focus({ preventScroll: true });
  card?.scrollIntoView({ block: "center" });
}
export function openMethodFigure(id) {
  const c = DB.comparison.datasets.find((c) => c.id === id),
    p = c ? datasetPaper(c) : DB.papers.find((p) => p.id === id);
  if (!p) return;
  if (c && state.figureViews) delete state.figureViews[c.id];
  openDetail(p.id, c?.id);
  showPane("media");
}
export function init() {
  if (!DB || !Array.isArray(DB.papers))
    throw new Error(t("Literature data is missing. Run npm run build first."));
  if (document.body.dataset.page === "review") {
    $(".hero .eyebrow").textContent = "Local review";
    $(".hero h1").textContent = "Candidate kymographs";
    const count = DB.comparison.datasets.length;
    $(".hero .intro").textContent = count
      ? t(
          count === 1
            ? "{count} card awaiting review."
            : "{count} cards awaiting review.",
          { count },
        )
      : "No cards awaiting review.";
    if (DB.catalog_review) {
      $(".hero h1").textContent = "Kymograph review";
      $(".hero .intro").hidden = true;
    }
    $(".hero .audit").hidden = true;
    state.section = "kymographs";
  }
  $("#date").textContent = DB.checked;
  const counts = Object.fromEntries(
    progressKeys.map((key) => [
      key,
      DB.papers.filter((p) => paperProgress(p) === key).length,
    ]),
  );
  const countLabels = {
    redrawn: t("redrawn"),
    needs_data: t("need data"),
    reference: t("references"),
  };
  $("#stats").innerHTML = [
    [DB.papers.length, t("papers"), "total"],
    ...progressKeys.map((key) => [counts[key], countLabels[key], key]),
  ]
    .map(
      ([count, label, key]) =>
        `<div class="stat" data-stat="${key}"><strong>${count}</strong><span>${esc(label)}</span></div>`,
    )
    .join("");
  const fs = [
    ["redraw_status", t("Redraw status")],
    ["species_label", t("Species")],
    ["reporter_tags", "Reporter"],
    ["systems", t("System")],
    ["patterns", "Pattern"],
    ["origin_label", t("Imaging")],
  ];
  $("#filterSelects").innerHTML = fs
    .map(([key, label]) => {
      const values =
        key === "redraw_status"
          ? progressKeys
          : [
              ...new Set(
                RAW_DB.papers.flatMap((p) =>
                  Array.isArray(p[key]) ? p[key] : [p[key]],
                ),
              ),
            ]
              .filter(Boolean)
              .sort();
      return `<select aria-label="${esc(label)}" id="filter-${key}" data-filter="${key}"><option value="">${esc(label)} · ${t("All")}</option>${values.map((value) => `<option value="${esc(value)}" ${state.filters[key] === value ? "selected" : ""}>${esc(key === "redraw_status" ? progressInfo(value)[0] : t(value))}</option>`).join("")}</select>`;
    })
    .join("");
  render();
  renderKymographs();
  showSection(state.section);
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.viewRedraw) {
    openRedraw(b.dataset.viewRedraw);
    return;
  }
  if (b.dataset.missingData) {
    openDetail(b.dataset.missingData);
    showPane("data");
    return;
  }
  if (b.dataset.sourceKind) {
    toggleMethodHelp(b);
    return;
  }
  if (b.dataset.studyFigure) {
    switchStudyFigure(b);
    return;
  }
  if (b.dataset.figureView) {
    switchFigureView(b);
    return;
  }
  if (b.dataset.watchVideo) {
    openMethodFigure(b.dataset.watchVideo);
    showPane("videos");
    return;
  }
  if (b.dataset.methodFigure) {
    openMethodFigure(b.dataset.methodFigure);
    return;
  }
  if (b.dataset.kymoRoi) {
    showRoi(b.dataset.kymoRoi);
    return;
  }
  if (b.dataset.pane) {
    showPane(b.dataset.pane);
    return;
  }
  if (b.dataset.detail) {
    openDetail(b.dataset.detail);
    return;
  }
  if (b.classList.contains("closeDialog")) {
    b.closest("dialog").close();
    return;
  }
  if (b.dataset.preview) {
    const p = DB.papers.find((p) => p.id === b.dataset.preview),
      m = p.media[+b.dataset.mediaIndex],
      stage = b.parentElement;
    stage.innerHTML = `<span class="status">${t("Loading from the original source…")}</span>`;
    const img = new Image();
    img.alt = `${p.short} · ${m.label} · ${m.description}`;
    img.referrerPolicy = "no-referrer";
    img.onload = () => {
      stage.replaceChildren(img);
    };
    img.onerror = () => {
      stage.innerHTML = `<span class="status">${t("Figure failed to load or access is restricted. Use the article link below.")}</span>`;
    };
    img.src = safeUrl(m.url);
    return;
  }
  switch (b.id) {
    case "reset":
    case "emptyReset":
      reset();
      break;
    case "cardsView":
      state.view = "cards";
      render();
      break;
    case "tableView":
      state.view = "table";
      render();
      break;
    case "clearSelection":
      state.selected.clear();
      render();
      break;
    case "compare":
      compare();
      break;
    case "exportJson":
      download("json");
      $(".exportMenu").open = false;
      break;
    case "exportCsv":
      download("csv");
      $(".exportMenu").open = false;
      break;
    case "kymographsNav":
    case "libraryNav":
      showSection(b.id.replace("Nav", ""));
      break;
  }
});
document.addEventListener("change", (e) => {
  const el = e.target;
  if (el.dataset.filter) {
    state.filters[el.dataset.filter] = el.value;
    render();
  }
  if (el.dataset.select) {
    if (el.checked && state.selected.size >= 3) {
      el.checked = false;
      toast(t("Compare up to 3 papers. Remove one first."));
      return;
    }
    el.checked
      ? state.selected.add(el.dataset.select)
      : state.selected.delete(el.dataset.select);
    updateCompareBar();
  }
  if (el.dataset.decision) saveNote(el.dataset.decision, "decision", el.value);
});
document.addEventListener("input", (e) => {
  if (e.target.id === "search") {
    state.query = e.target.value;
    render();
  }
  if (e.target.dataset.note)
    saveNote(e.target.dataset.note, "text", e.target.value);
});
export function saveNote(id, key, value) {
  notes[id] = {
    ...notes[id],
    [key]: value,
    updated_at: new Date().toISOString(),
  };
  try {
    localStorage.setItem("clock-explorer-notes-v1", JSON.stringify(notes));
  } catch {
    toast(t("Local storage is unavailable. Export JSON to save these notes."));
  }
}
$(".brand").addEventListener("click", (e) => {
  if (document.body.dataset.page !== "app") return;
  e.preventDefault();
  $("#libraryNav").click();
});
init();

const initialMethod = new URLSearchParams(location.hash.slice(1)).get("method");
if (initialMethod) openMethodFigure(initialMethod);

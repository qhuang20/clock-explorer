// SPDX-License-Identifier: MIT
import { RAW_DB, DB, t, state, notes } from "./context.js";
import { $, esc, link, safeUrl, toast, csvCell } from "./dom.js";
import { assetUrl } from "./assets.js";
import {
  compact,
  species,
  paperProgress,
  progressBadge,
  pendingReason,
  statusLabel,
  statusClass,
  size,
} from "./catalog.js";
import { figureDetails } from "./figures.js";
import {
  combinedSources,
  detailPresentation,
  fieldVerification,
  overviewExperiment,
  dataSources,
} from "./data-sources.js";
export function refs(p, key) {
  const ids = p.field_evidence[key] || [];
  return (Array.isArray(ids) ? ids : [ids])
    .map((id) => {
      const s = p.sources.find((s) => s.id === id);
      return s
        ? `<a class="evidenceRef" title="${esc(s.location)}" href="${esc(safeUrl(s.url))}" target="_blank" rel="noopener noreferrer">${t("Evidence")} ${esc(id)}</a>`
        : "";
    })
    .join("");
}
export function field(p, k, label, datasetId) {
  const verification = combinedSources(p, datasetId)
    ? fieldVerification(p, p.field_evidence[k])
    : `<br>${refs(p, k)}`;
  return `<div class="field"><dt>${esc(label)}</dt><dd>${esc(p[k])}${verification}</dd></div>`;
}
export function matches(p) {
  const raw = RAW_DB.papers.find((x) => x.id === p.id),
    q = state.query.trim().toLocaleLowerCase();
  if (q && !JSON.stringify([p, raw]).toLocaleLowerCase().includes(q))
    return false;
  return Object.entries(state.filters).every(
    ([k, v]) =>
      !v ||
      (k === "redraw_status"
        ? paperProgress(p) === v
        : Array.isArray(raw[k])
          ? raw[k].includes(v)
          : raw[k] === v),
  );
}
const filtered = () => DB.papers.filter(matches);
export function selectionBox(p) {
  return `<label class="check"><input type="checkbox" data-select="${esc(p.id)}" aria-label="${t("Compare")} ${esc(p.short)}" ${state.selected.has(p.id) ? "checked" : ""}>${t("Compare")}</label>`;
}
export function kymoLink(p, datasetId) {
  if (p.method_figure || p.kymograph?.comparison)
    return `<button class="kymoLink hasKymo" data-method-figure="${esc(datasetId || p.id)}">${t("Experimental redraw · method ↗")}</button>`;
  const k = p.kymograph;
  return k
    ? `<button class="kymoLink ${k.kind === "experimental" ? "hasKymo" : ""}" data-method-figure="${esc(datasetId || p.id)}">${esc(k.short)} ${k.kind === "experimental" ? "↗" : "ⓘ"}</button>`
    : "";
}
export function progressAction(p) {
  const status = paperProgress(p);
  if (status === "redrawn")
    return `<button class="progressLink" data-view-redraw="${esc(p.id)}" aria-label="${esc(t("View the kymograph for {paper}", { paper: p.short }))}">${t("View kymograph")} ↗</button>`;
  if (status === "needs_data")
    return `<button class="progressLink pendingLink" data-missing-data="${esc(p.id)}" aria-label="${esc(t("View missing data for {paper}", { paper: p.short }))}">${t("Not redrawn · Missing data")} →</button>`;
  return `<span class="notInGallery">${t("Not in Kymographs")}</span>`;
}
export function card(p) {
  const [title, , reporter] = compact(p);
  return `<article class="paper" data-id="${esc(p.id)}" data-redraw-status="${paperProgress(p)}"><div class="cardTop"><span class="citation">${esc(p.short)}</span>${progressBadge(p)}</div><h3><button class="cardTitle" data-detail="${esc(p.id)}" title="${esc(p.title)}">${esc(title)}</button></h3><div class="tags"><span class="tag">${esc(species(p))}</span><span class="tag">${esc(p.systems[0])}</span><span class="tag">${esc(p.origin_badge || (p.origin === "live" ? "Time-lapse" : p.origin === "fixed" ? t("Fixed sample") : t("Expression / morphology")))}</span></div><div class="cardFacts"><div><small>REPORTER</small><strong>${esc(reporter)}</strong></div><div><small>${t("Sampling")}</small><strong>${esc(p.calibration_short)}</strong></div></div><div class="cardBottom">${progressAction(p)}${selectionBox(p)}</div></article>`;
}
export function table(ps) {
  return `<div class="tableWrap"><table><thead><tr><th>${t("Paper")}</th><th>${t("System")}</th><th>Reporter</th><th>${t("Redraw status")}</th><th>${t("Compare")}</th></tr></thead><tbody>${ps.map((p) => `<tr data-id="${esc(p.id)}" data-redraw-status="${paperProgress(p)}"><td class="titleCell"><button data-detail="${esc(p.id)}" title="${esc(p.title)}">${esc(compact(p)[0])}</button><small>${esc(p.short)}</small></td><td>${esc(species(p))} · ${esc(p.systems[0])}</td><td>${esc(compact(p)[2])}</td><td><div class="tableProgress">${progressBadge(p)}${progressAction(p)}</div></td><td>${selectionBox(p)}</td></tr>`).join("")}</tbody></table></div>`;
}
export function render() {
  const ps = filtered();
  $("#resultCount").textContent = t("{count} / {total} papers", {
    count: ps.length,
    total: DB.papers.length,
  });
  $("#results").className = state.view === "cards" ? "cards" : "";
  $("#results").innerHTML = ps.length
    ? state.view === "cards"
      ? ps.map(card).join("")
      : table(ps)
    : `<div class="empty"><h3>${t("No matching papers")}</h3><p>${t("Try removing a filter, or search by author or reporter.")}</p><button id="emptyReset">${t("Reset filters")}</button></div>`;
  document
    .querySelectorAll("[data-filter]")
    .forEach((el) => el.classList.toggle("active", !!el.value));
  $("#cardsView").setAttribute("aria-pressed", state.view === "cards");
  $("#tableView").setAttribute("aria-pressed", state.view === "table");
  updateCompareBar();
}
export function updateCompareBar() {
  const ps = DB.papers.filter((p) => state.selected.has(p.id));
  $("#compareBar").hidden = !ps.length || state.section !== "library";
  $("#selectionCount").textContent = t("{count} / 3 selected", {
    count: ps.length,
  });
  $("#selectionNames").textContent = ps.map((p) => p.short).join("  ·  ");
  $("#compare").disabled = ps.length < 2;
}
export function reset() {
  state.filters = {};
  state.query = "";
  $("#search").value = "";
  document.querySelectorAll("[data-filter]").forEach((e) => (e.value = ""));
  render();
}
export function localDownload(a) {
  return /^data\/(?:samples|derived)\/[a-z0-9-]+\/[A-Za-z0-9_.-]+$/.test(
    a.local_path || "",
  )
    ? `<a class="sampleDownload" href="${esc(assetUrl(a.local_path))}" download>${t("Download verified sample ↓")}</a>`
    : "";
}
export function asset(p, a) {
  return `<div class="asset"><div class="assetHead"><div><small>${esc(a.level_label)}</small><h3>${esc(a.label)}</h3></div><span class="badge ${statusClass(a.status)}">${esc(statusLabel(a.status))}</span></div>${link(a.url, ["verified_content", "verified_headers"].includes(a.status) ? (a.source_is_input ? t("Source video") : t("File")) : t("Source"))}${localDownload(a)}<details class="fold"><summary>${t("Verification record")}</summary><p>${esc(a.evidence)}</p><div class="assetMeta">${esc(a.format || t("Format unknown"))} · ${esc(size(a))}<br>${t("Checked")} ${esc(a.checked || DB.checked)} · ${t("License")}: ${esc(a.license || t("Unknown"))}</div></details></div>`;
}
export function openDetail(id, datasetId) {
  const p = DB.papers.find((p) => p.id === id);
  if (!p) return;
  window.ClockVideos?.unmount();
  datasetId ||= p.kymograph?.default_dataset || id;
  state.dialog = { kind: "detail", id, datasetId };
  const n = notes[id] || {};
  const presentation = detailPresentation(p, datasetId);
  const merged = combinedSources(p, datasetId);
  const tabs = [
    ["overview", t("Overview")],
    ["media", t("Figures")],
    ["data", merged ? t("Data & sources") : t("Data")],
    ...(merged
      ? []
      : [
          ["sources", t("Evidence")],
          ["notes", t("Notes")],
        ]),
  ];
  const fullFields = [
    ["species", t("Species")],
    ["system_description", t("Experimental system")],
    ["tissue", t("Tissue")],
    ["conditions", t("Conditions")],
    ["reporter_construct", "Reporter construct"],
    ["reported_target", t("Reported target")],
    ["origin_label", t("Imaging source")],
    ["figure_focus", t("Figures and data types")],
    ["time_axis", t("Time axis")],
    ["space_axis", t("Space axis")],
    ["time_resolution", t("Time resolution")],
    ["space_resolution", t("Spatial sampling")],
    ["replicates", t("Replicates")],
    ["preprocessing", t("Processing and registration")],
  ];
  $("#detail").innerHTML =
    `<div class="detailHeader"><span class="eyebrow">${esc(p.short)} · ${esc(p.journal)}</span><h2 id="detailTitle">${esc(p.title)}</h2><div class="links">${link(p.url, t("Article"))}${link("https://doi.org/" + p.doi, "DOI")}</div></div><div class="detailTabs" role="tablist" aria-label="${t("Paper detail tabs")}">${tabs
      .map(
        ([id, label], i) =>
          `<button role="tab" id="tab-${id}" aria-controls="pane-${id}" aria-selected="${i === 0}" data-pane="${id}">${label}</button>`,
      )
      .join("")}</div>
 <section class="detailPane" id="pane-overview" role="tabpanel" aria-labelledby="tab-overview"><p class="brief">${esc(detailPresentation(p, datasetId).overview_summary || p.summary)}</p>${kymoLink(p, datasetId)}${
   merged
     ? overviewExperiment(p, datasetId)
     : `<div class="miniFacts">${[
         [t("System"), species(p) + " · " + p.systems.join(" / ")],
         ["Reporter", p.reporter_short],
         [t("Sampling"), presentation.calibration_short || p.calibration_short],
         [t("Data"), compact(p)[1]],
       ]
         .map(
           ([l, v]) =>
             `<div class="miniFact"><small>${esc(l)}</small><strong>${esc(v)}</strong></div>`,
         )
         .join("")}</div>`
 }<div class="tags">${p.patterns.map((v) => `<span class="tag">${esc(v)}</span>`).join("")}</div><details class="fold"><summary>${t("Methods and calibration · 14 fields")}</summary><dl class="fieldGrid">${fullFields.map(([k, l]) => field(p, k, l, datasetId)).join("")}</dl></details><details class="fold"><summary>${t("Interpretation and gaps")}</summary><div class="warning"><ul>${p.caveats.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div><h3>${t("Missing information")}</h3><ul class="authorList">${p.missing.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></details></section>
 <section class="detailPane" id="pane-media" role="tabpanel" aria-labelledby="tab-media" hidden>${figureDetails(p, datasetId)}</section>
 <section class="detailPane" id="pane-data" role="tabpanel" aria-labelledby="tab-data" hidden>${paperProgress(p) === "needs_data" ? `<p class="pendingDataSummary"><strong>${t("Needs data")}</strong> · ${esc(pendingReason(p))}</p>` : ""}${merged ? dataSources(p, datasetId) : `<p class="notesStatus">${t("File access and raw-data availability are verified separately.")}</p>${(presentation.sample_asset ? [presentation.sample_asset, ...p.assets.filter((a) => !a.local_path)] : p.assets).map((a) => asset(p, a)).join("")}`}</section>
 ${
   merged
     ? ""
     : `<section class="detailPane" id="pane-sources" role="tabpanel" aria-labelledby="tab-sources" hidden><p class="authorList">${esc(p.authors.join(", "))}</p><p class="notesStatus">${esc(p.verification_scope)}</p>${p.sources.map((s) => `<div class="source"><strong>${esc(s.id)} · ${esc(s.location)}</strong><p>${esc(s.note || s.supports || "")}</p>${link(s.url, t("Source"))}<small> · ${esc(s.access || t("Checked"))}</small></div>`).join("")}</section>
 <section class="detailPane" id="pane-notes" role="tabpanel" aria-labelledby="tab-notes" hidden><div class="notes"><label>${t("Review decision")}<select data-decision="${esc(id)}"><option value="Undecided">${t("Undecided")}</option><option value="Prioritize">${t("Prioritize")}</option><option value="Awaiting data">${t("Awaiting data")}</option><option value="Background reference">${t("Background reference")}</option><option value="Not selected">${t("Not selected")}</option></select></label><label>${t("Discussion notes")}<textarea data-note="${esc(id)}" placeholder="${t("Notes from your PI discussion…")}">${esc(n.text || "")}</textarea></label></div><p class="notesStatus">${t("Saved in this browser · notes included in JSON export")}</p></section>`
 }`;
  window.ClockVideos?.mount(
    id,
    datasetId || p.kymograph?.default_dataset || id,
  );
  const decision = $("#detail select[data-decision]");
  if (decision) decision.value = n.decision || "Undecided";
  $("#detailDialog").showModal();
  $("#detailDialog").scrollTop = 0;
}
export function showPane(id) {
  window.ClockVideos?.onPane(id);
  document
    .querySelectorAll(".detailPane")
    .forEach((e) => (e.hidden = e.id !== "pane-" + id));
  document
    .querySelectorAll("[data-pane]")
    .forEach((e) => e.setAttribute("aria-selected", e.dataset.pane === id));
}
export function compare() {
  const ps = DB.papers.filter((p) => state.selected.has(p.id));
  if (ps.length < 2) return;
  const brief = [
    ["Kymograph", (p) => p.kymograph?.short || t("Unverified")],
    [t("System"), (p) => species(p) + " · " + p.systems.join(" / ")],
    ["Reporter", (p) => compact(p)[2]],
    [t("Imaging"), (p) => p.origin_label],
    [t("Sampling"), (p) => p.calibration_short],
    [t("Data status"), (p) => compact(p)[1]],
    [t("Gaps"), (p) => p.missing.slice(0, 2).join(";")],
  ];
  const full = [
    ["Reporter construct", (p) => p.reporter_construct],
    [t("Reported target"), (p) => p.reported_target],
    ["Pattern", (p) => p.patterns.join(";")],
    [t("Experimental figures"), (p) => p.figure_focus],
    [t("Time calibration"), (p) => p.time_axis + ";" + p.time_resolution],
    [t("Spatial calibration"), (p) => p.space_axis + ";" + p.space_resolution],
    [t("Replicates"), (p) => p.replicates],
    [
      t("Data sources"),
      (p) =>
        p.assets
          .map((a) => `${a.level_label}:${statusLabel(a.status)} — ${a.label}`)
          .join("\n"),
    ],
    [t("Registration"), (p) => p.preprocessing],
    [
      t("Discussion notes"),
      (p) =>
        t(notes[p.id]?.decision || "Undecided") +
        " · " +
        (notes[p.id]?.text || ""),
    ],
  ];
  const rows = (rs) =>
    rs
      .map(
        ([l, f]) =>
          `<tr><th class="rowlabel">${esc(l)}</th>${ps.map((p) => `<td style="white-space:pre-line">${esc(f(p))}</td>`).join("")}</tr>`,
      )
      .join("");
  $("#comparison").innerHTML =
    `<table class="compareTable"><thead><tr><th>${t("Papers: {count}", { count: ps.length })}</th>${ps.map((p) => `<th><h3>${esc(p.short)}</h3><p class="compareSubject">${esc(compact(p)[0])}</p>${link(p.url, t("Article"))}<button data-detail="${esc(p.id)}">${t("Details")}</button></th>`).join("")}</tr></thead><tbody>${rows(brief)}</tbody></table><details class="fold"><summary>${t("Full methods and evidence comparison")}</summary><table class="compareTable"><tbody>${rows(full)}</tbody></table></details>`;
  $("#compareDialog").showModal();
  $("#compareDialog").scrollTop = 0;
}
export function exportObject() {
  const ps = filtered();
  return {
    ...DB,
    interface_language: "en",
    papers: ps,
    exported_at: new Date().toISOString(),
    filter_state: { query: state.query, filters: { ...state.filters } },
    annotations: Object.fromEntries(
      ps.filter((p) => notes[p.id]).map((p) => [p.id, notes[p.id]]),
    ),
  };
}
export function toCsv(ps) {
  const keys = [
    "id",
    "title",
    "authors",
    "year",
    "doi",
    "url",
    "species",
    "systems",
    "reporter_construct",
    "reported_target",
    "patterns",
    "origin_label",
    "time_axis",
    "space_axis",
    "time_resolution",
    "space_resolution",
    "replicates",
    "preprocessing",
    "kymograph",
    "assets",
    "sources",
    "field_evidence",
    "missing",
    "checked",
    "review_decision",
    "review_note",
  ];
  return (
    "\ufeff" +
    [
      keys.map(csvCell).join(","),
      ...ps.map((p) =>
        keys
          .map((k) =>
            csvCell(
              k === "review_decision"
                ? notes[p.id]?.decision
                : k === "review_note"
                  ? notes[p.id]?.text
                  : p[k],
            ),
          )
          .join(","),
      ),
    ].join("\r\n")
  );
}
export function download(type) {
  const x = exportObject();
  const content =
    type === "json" ? JSON.stringify(x, null, 2) : toCsv(x.papers);
  const b = new Blob([content], {
    type:
      type === "json"
        ? "application/json;charset=utf-8"
        : "text/csv;charset=utf-8",
  });
  const u = URL.createObjectURL(b);
  const a = document.createElement("a");
  a.href = u;
  a.download = `clock-literature-${DB.checked}-en.${type}`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(u), 1000);
  toast(
    t("Exported {count} papers as {format} (current filters)", {
      count: x.papers.length,
      format: type.toUpperCase(),
    }),
  );
}

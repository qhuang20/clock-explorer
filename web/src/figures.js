// SPDX-License-Identifier: MIT
import { DB, t, state } from "./context.js";
import { $, esc, figureUrl, link, localFigurePath } from "./dom.js";
import { assetUrl } from "./assets.js";
import { datasetPaper, visibleComparisonRecords } from "./catalog.js";
import { kindLabel } from "./tooltips.js";
import {
  coverageSummary,
  coverageMethod,
  comparisonSourceLinks,
  datasetSourceDetails,
} from "./gallery.js";
export function media(p, m, i) {
  const sourceOnly = !m.url && m.source_link_only;
  return `<div class="mediaBox"><h3>${esc(m.label)}</h3><p>${esc(m.description)}</p>${sourceOnly ? link(m.source_url, t("View published figure")) : `<div class="mediaStage" id="media-${esc(p.id)}-${i}">${m.url ? `<button data-preview="${esc(p.id)}" data-media-index="${i}">${t("Load original figure ↗")}</button>` : `<span class="status">${t("No preview available")}</span>`}</div>${link(m.source_url, t("Figure source"))}`}<p>${esc(m.attribution || m.license || t("Reuse permission unknown; the image is not stored locally."))}</p>${window.ClockVideos?.licenseLink(m) || ""}${window.ClockVideos?.licenseCredit(m) || ""}<p>${sourceOnly ? t("Linked for licensing reasons") : esc(m.status)}</p></div>`;
}
export function showRoi(id) {
  state.dialog = { kind: "roi", id };
  const c = DB.comparison.datasets.find((c) => c.id === id);
  if (!c?.roi) return;
  $("#detail").innerHTML =
    `<div class="detailHeader"><span class="eyebrow">${esc(c.short)}</span><h2 id="detailTitle">${t("Sampling ROI")}</h2><p class="brief">${esc(c.roi_note || t("Sampling paths in the first, middle, and last frames. Translation correction does not account for tissue deformation or track individual cells."))}</p></div><img class="fullKymo" src="${esc(figureUrl(c.roi))}" alt="${esc(c.short + t(" sampling ROI"))}"><p class="kymoAttribution">${t("See the paper's Data and Evidence tabs for source files, calibration, and processing parameters.")}</p>`;
  $("#detailDialog").showModal();
  $("#detailDialog").scrollTop = 0;
}
function referenceComparison(m, datasetId) {
  const comparisons = [...(m.review_comparisons || [])];
  if (m.reference_comparison)
    comparisons.push({
      ...m.reference_comparison,
      preview:
        DB.card_previews?.[datasetId]?.reference_preview ||
        m.reference_comparison.preview,
    });
  return comparisons
    .map(
      (
        reference,
      ) => `<details class="fold methodReferenceComparison"><summary>${esc(reference.label)}</summary>
   <p class="samplingCaption">${esc(reference.note)}</p>
   ${window.ClockVideos?.licenseLink(reference) || ""}${window.ClockVideos?.licenseCredit(reference) || ""}
   ${reference.roi ? `<a class="methodRoiPreview" href="${esc(figureUrl(reference.roi))}" target="_blank" rel="noopener noreferrer"><img class="fullKymo" src="${esc(figureUrl(reference.roi))}" alt="${esc(reference.roi_alt)}"></a>` : ""}
   <div class="methodComparisonResult"><a class="methodResultPreview" href="${esc(figureUrl(reference.preview))}" target="_blank" rel="noopener noreferrer"><img class="fullKymo" src="${esc(figureUrl(reference.preview))}" alt="${esc(reference.alt)}"></a><p class="samplingCaption comparisonPanHint">${t("Swipe horizontally to compare, or tap to enlarge.")}</p></div>
  </details>`,
    )
    .join("");
}
export function methodFigure(p, m = p.method_figure, c = null) {
  const selectedId = c?.id || p.id,
    preview = DB.card_previews?.[selectedId],
    result = m.result_preview
      ? preview?.method_preview || m.result_preview
      : preview?.preview || (c ? c.full_preview : m.card_preview || m.preview),
    hasGeneratedResult = m.result_preview
      ? !!preview?.method_preview
      : !!preview?.preview,
    plotNote = hasGeneratedResult
      ? DB.card_presentation?.[selectedId]?.axis_polarity?.note ||
        DB.card_presentation?.[selectedId]?.coordinate_note ||
        ""
      : "";
  const samplingVideo =
    m.sampling_video_id &&
    window.CLOCK_VIDEO_CATALOG?.papers[p.id]?.videos.find(
      (v) => v.id === m.sampling_video_id,
    );
  const samplingPlayer = samplingVideo?.src
    ? `<details class="fold samplingVideo"><summary>${esc(samplingVideo.title)}</summary><p class="samplingCaption">${esc(samplingVideo.description)}</p>${window.ClockVideos?.licenseLink(samplingVideo) || ""}<video controls playsinline preload="none" poster="${esc(assetUrl(samplingVideo.poster))}" src="${esc(assetUrl(samplingVideo.src))}" aria-label="${esc(samplingVideo.title)}"></video>${window.ClockVideos?.licenseCredit(samplingVideo) || ""}${link(samplingVideo.source_url, t("Original video"))}</details>`
    : "";
  const coordinateRecord =
    c && m.coordinate_reference
      ? { ...c, origin_short: m.coordinate_reference }
      : c;
  const heading = (number, label) =>
    `<h4 class="methodStageTitle"><span aria-hidden="true">${number}</span>${t(label)}</h4>`;
  const sourceLinks = [
    ...(m.figure_sources || []),
    ...(c?.author_file_links || []),
  ]
    .map((source) => link(source.url, source.label))
    .join("");
  return `<section class="methodFigure methodWalkthrough">
   <header class="methodIntro"><h3>${esc(m.title)}</h3><p class="methodContext">${esc(m.context)}</p></header>${datasetSourceDetails(p, coordinateRecord)}
   <div class="methodFlowGrid">
    <section>${heading(1, "Sampling")}${m.roi ? `<a class="methodRoiPreview" href="${esc(figureUrl(m.roi))}" target="_blank" rel="noopener noreferrer"><img class="fullKymo" src="${esc(figureUrl(m.roi))}" alt="${esc(m.roi_alt || t("The same fixed sampling strip in the first, middle, and last frames"))}"></a>` : ""}${m.roi_note ? `<p class="samplingCaption">${esc(m.roi_note)}</p>` : ""}${samplingPlayer}</section>
    <section>${heading(2, "Extraction")}<ol class="methodSteps">${m.steps.map((step) => `<li>${esc(step)}</li>`).join("")}</ol></section>
    <section${m.comparison ? ' class="methodComparisonResult"' : ""}>${heading(3, c?.phase_ordered ? "Phase reconstruction" : "Kymograph")}<a class="methodResultPreview" href="${esc(figureUrl(result))}" target="_blank" rel="noopener noreferrer"><img class="fullKymo" src="${esc(figureUrl(result))}"${plotNote ? ` title="${esc(plotNote)}"` : ""} alt="${esc(m.card_preview ? p.short + " · " + t(c?.phase_ordered ? "Phase-ordered expression domains" : "Extracted kymograph") : m.alt)}"></a>${m.comparison ? `<p class="samplingCaption comparisonPanHint">${t("Swipe horizontally to compare, or tap to enlarge.")}</p>` : ""}</section>
    <section class="methodReadout${m.comparison ? " methodComparisonReadout" : ""}">${heading(4, "Reading the plot")}
     ${m.axes?.length ? `<dl class="samplingFacts">${m.axes.map(([label, value]) => `<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`).join("")}</dl>` : ""}
     <p class="samplingMethod">${esc(m.color_note || t("Light = low, dark = high. Absolute brightness is not comparable across samples."))}</p><p class="methodLimit">${esc(m.limit)}</p>
    </section>
   </div>
   ${referenceComparison(m, selectedId)}
   ${c ? relatedDatasets(p, c) : ""}
   <footer class="methodLinks">${Object.entries(m.downloads)
     .filter(([, u]) => localFigurePath(u))
     .map(([fmt, u]) => link(figureUrl(u), fmt.toUpperCase()))
     .join(
       "",
     )}${c?.author_file_links ? "" : link(m.source_url, m.source_label || t("Source video"))}${sourceLinks}${link(assetUrl(m.data_path), m.data_label || t("Matrix"))}${link(assetUrl(m.provenance_path), t("Processing record"))}${m.audit_path ? link(assetUrl(m.audit_path), t("ROI review record")) : ""}${m.review_preview ? link(figureUrl(m.review_preview), m.review_label || t("Wavefront diagnostics")) : ""}</footer>
  </section>`;
}
export function relatedDatasets(p, c) {
  const datasets = visibleComparisonRecords().filter(
    (d) => (d.paper_id || d.id) === p.id,
  );
  const switchLabel = DB.card_presentation?.[p.id]?.dataset_switch_label;
  if (switchLabel && datasets.length > 1) {
    return `<div class="relatedDatasets" role="group" aria-label="${esc(switchLabel)}"><span>${esc(switchLabel)}</span><div class="segmented">${datasets
      .map(
        (d) =>
          `<button type="button" data-method-figure="${esc(d.id)}" aria-pressed="${d.id === c.id}">${esc(DB.card_presentation[d.id].conditions[0])}</button>`,
      )
      .join("")}</div></div>`;
  }
  const others = datasets.filter((d) => d.id !== c.id);
  function label(item) {
    const peers = datasets.filter((d) => d.system_label === item.system_label);
    if (peers.length === 1) return item.system_label || item.reporter;
    if (peers.some((d) => d.id !== item.id && d.reporter === item.reporter))
      return `${item.reporter} · ${item.sample}`;
    return item.reporter;
  }
  return others.length
    ? `<div class="relatedDatasets"><span>${t("Also in this paper")}</span>${others.map((d) => `<button data-method-figure="${esc(d.id)}">${esc(label(d))} ↗</button>`).join("")}</div>`
    : "";
}
export function matrixStudyFigure(p, c) {
  const selected = state.studyFigures?.[c.id] || c.detail_figures[0].id;
  return `<section class="methodFigure matrixStudy" data-matrix-study="${esc(c.id)}">
  <h3>${esc(c.detail_title)}</h3><p class="brief">${esc(c.detail_summary)}</p>${coverageMethod(c)}${datasetSourceDetails(p, c)}
  <div class="segmented studyFigureTabs" role="group" aria-label="${t("Choose a detail figure")}">${c.detail_figures.map((f) => `<button data-study-figure="${esc(f.id)}" aria-pressed="${f.id === selected}" aria-controls="study-${esc(c.id)}-${esc(f.id)}">${esc(f.label)}</button>`).join("")}</div>
  ${c.detail_figures
    .map(
      (
        f,
      ) => `<section id="study-${esc(c.id)}-${esc(f.id)}" data-study-panel="${esc(f.id)}" ${f.id === selected ? "" : "hidden"}>
   <a class="studyFigureLink" href="${esc(figureUrl(f.preview))}" target="_blank" rel="noopener noreferrer" aria-label="${t("Enlarge detail figure")}"><img class="fullKymo" src="${esc(figureUrl(f.preview))}" alt="${esc(f.alt)}"></a>
  </section>`,
    )
    .join("")}
  <dl class="samplingFacts">${c.detail_facts.map(([label, value]) => `<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`).join("")}</dl>
  <h4>${t("Extraction & rendering")}</h4><ol class="methodSteps">${c.detail_steps.map((step) => `<li>${esc(step)}</li>`).join("")}</ol>
  <p class="methodLimit">${esc(c.detail_limit)}</p>
  ${relatedDatasets(p, c)}
  <footer class="methodLinks">${c.detail_figures
    .map((f) =>
      Object.entries(f.downloads)
        .map(
          ([fmt, url]) =>
            `<a href="${esc(figureUrl(url))}" target="_blank" rel="noopener noreferrer" data-study-panel="${esc(f.id)}" ${f.id === selected ? "" : "hidden"}>${fmt.toUpperCase()} ↗</a>`,
        )
        .join(""),
    )
    .join(
      "",
    )}${c.detail_data.map((a) => link(assetUrl(a.path), a.label)).join("")}${link(c.author_code_url, t("Author code"))}${comparisonSourceLinks(c)}</footer>
 </section>`;
}
export function switchStudyFigure(button) {
  const section = button.closest("[data-matrix-study]"),
    id = button.dataset.studyFigure;
  if (!section) return;
  (state.studyFigures ??= {})[section.dataset.matrixStudy] = id;
  section
    .querySelectorAll("[data-study-figure]")
    .forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.studyFigure === id)),
    );
  section
    .querySelectorAll("[data-study-panel]")
    .forEach((panel) => (panel.hidden = panel.dataset.studyPanel !== id));
}
// Redraws use the full extracted range; keep the optional range controls hidden for now.
const RANGE_VIEW_ENABLED = false;

// One gallery, with all figure variants inside the existing paper detail dialog.
export function figureDetails(p, datasetId) {
  const key = datasetId || p.kymograph?.default_dataset || p.id;
  const record = DB.comparison.datasets.find((c) => c.id === key);
  const hasRedraw = !!p.method_figure || !!record;
  const views = [];
  if (hasRedraw)
    views.push({
      id: "redraw",
      label: t(record?.phase_ordered ? "Expression domains" : "Intensity"),
      html: samplingFigure(p, datasetId),
    });
  if (RANGE_VIEW_ENABLED && window.ClockRangeExplorer?.has(key))
    views.push({
      id: "range",
      label: t("Range & source files"),
      html: window.ClockRangeExplorer.markup(key),
    });
  if (
    p.kymograph?.rendered?.phase &&
    key === (p.kymograph?.default_dataset || p.id)
  )
    views.push({ id: "phase", label: t("Phase"), html: phaseFigure(p) });
  if (p.media.length)
    views.push({
      id: "original",
      label: t("Published figure"),
      html: originalFigures(p, key),
    });
  if (!views.length) return samplingFigure(p, datasetId);
  const saved = state.figureViews?.[key],
    selected = views.some((v) => v.id === saved) ? saved : views[0].id;
  return `<div class="figureDetails" data-figure-detail="${esc(key)}">
  ${views.length > 1 ? `<div class="segmented figureDetailTabs" role="group" aria-label="${t("Figure version")}">${views.map((v) => `<button type="button" data-figure-view="${v.id}" aria-pressed="${v.id === selected}" aria-controls="figure-${esc(key)}-${v.id}">${v.label}</button>`).join("")}</div>` : ""}
  ${views.map((v) => `<section id="figure-${esc(key)}-${v.id}" data-figure-panel="${v.id}" ${v.id === selected ? "" : "hidden"}>${v.html}</section>`).join("")}
 </div>`;
}
export function switchFigureView(button) {
  const section = button.closest("[data-figure-detail]"),
    id = button.dataset.figureView;
  if (!section) return;
  (state.figureViews ??= {})[section.dataset.figureDetail] = id;
  section
    .querySelectorAll("[data-figure-view]")
    .forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.figureView === id)),
    );
  section
    .querySelectorAll("[data-figure-panel]")
    .forEach((panel) => (panel.hidden = panel.dataset.figurePanel !== id));
}
export function phaseFigure(p) {
  const k = p.kymograph,
    r = k.rendered.phase;
  return `<section class="methodFigure phaseFigure">
  <h3>${esc(r.panel)}</h3><p class="brief">${esc(r.panel_note)}</p>
  <a class="phaseFigureLink" href="${esc(figureUrl(r.preview))}" target="_blank" rel="noopener noreferrer" aria-label="${t("Enlarge detail figure")}"><img class="fullKymo" src="${esc(figureUrl(r.preview))}" alt="${esc(p.short + " · " + r.panel)}"></a>
  <p class="methodLimit">${esc(r.limit)}</p>
  <dl class="samplingFacts">${[
    ["Reporter", r.reporter || k.reporter],
    [t("Time axis"), r.time],
    [t("Space axis"), r.space],
    [t("Color"), r.signal],
  ]
    .map(
      ([label, value]) =>
        `<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`,
    )
    .join("")}</dl>
  <section class="samplingDetails"><h4>${t("Rendering method")}</h4><p class="samplingMethod">${esc(r.model_note)}</p><p class="samplingCaption">${esc(r.attribution)}</p></section>
  <footer class="methodLinks">${Object.entries(r.downloads || {})
    .filter(([, url]) => localFigurePath(url))
    .map(([fmt, url]) => link(figureUrl(url), fmt.toUpperCase()))
    .join("")}${link(r.source_url, t("Source data"))}</footer>
 </section>`;
}
export function originalFigures(p, datasetId) {
  const scoped = p.media.some((m) => m.dataset_ids?.includes(datasetId));
  const originals = p.media
    .map((m, index) => ({ m, index }))
    .filter(({ m }) =>
      scoped ? m.dataset_ids?.includes(datasetId) : !m.dataset_ids,
    );
  const k = scoped ? null : p.kymograph;
  const explanation =
    k && !k.no_original
      ? `<details class="fold originalFigureNotes"><summary>${t("Figure notes")}</summary>
  <p>${esc(k.panel_note || "")}</p><p>${esc(k.takeaway || "")}</p>
  <dl class="samplingFacts">${[
    ["Reporter", k.reporter],
    [t("Time axis"), k.time],
    [t("Space axis"), k.space],
    [t("Color"), k.signal],
  ]
    .filter(([, value]) => value)
    .map(
      ([label, value]) =>
        `<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`,
    )
    .join("")}</dl>
  ${k.limit ? `<p class="methodLimit">${esc(k.limit)}</p>` : ""}${k.model_note ? `<p>${esc(k.model_note)}</p>` : ""}
  <div class="links">${link(k.dataset_url, t("Public numerical data"))}${link(k.movie_url, t("Source video"))}${link(k.related_figure_url, t("Baseline waves · Fig. 1"))}${k.related ? `<button data-method-figure="${esc(k.related)}">${t("Related live wave patterns →")}</button>` : ""}</div>
 </details>`
      : "";
  return (
    originals.map(({ m, index }) => media(p, m, index)).join("") + explanation
  );
}
function matrixWalkthrough(p, c) {
  const [rows, columns] = c.shape_space_time;
  const formatRange = (values) =>
    values.map((value) => Number(value.toFixed(2))).join("–");
  const method = DB.card_presentation?.[c.id]?.matrix_method;
  const heatmap = methodFigure(
    p,
    {
      title: "Sampling & kymograph",
      context: c.detail_primary_context || `${c.reporter} · ${c.sample}`,
      roi_note:
        method?.sampling ||
        `The author’s intensity TIFF for ${c.sample} contains ${rows} spatial rows and ${columns} time points. Each column is one intensity profile along the sampled tissue.`,
      steps:
        method?.steps ||
        (c.sampling_method
          ? [c.sampling_method]
          : [
              "Read the stored intensity TIFF at 10 min per column and 1.38 µm per row. Preserve row and column order.",
              "Scale finite intensity values across the complete matrix to 0–1.",
            ]),
      axes: [
        ["Time", `${formatRange(c.time_range_h)} h · ${columns} time points`],
        [
          "Position",
          `${formatRange(c.spatial_range)} ${c.position_unit} · ${c.origin_short}`,
        ],
      ],
      limit:
        method?.reading ||
        DB.card_presentation?.[c.id]?.axis_polarity?.note ||
        "Distance increases downward from the first stored row. Each temperature has its own time and position range.",
      alt: `${c.sample} · ${c.reporter}`,
      downloads: Object.fromEntries(
        ["svg", "png", "pdf"].map((fmt) => [
          fmt,
          c.full_preview.replace(/\.svg$/, "." + fmt),
        ]),
      ),
      data_path: c.input,
      provenance_path: c.provenance,
      source_url: c.data_url || c.source_url,
      source_label: "Author data",
    },
    c,
  );
  if (!c.detail_figures?.length) return heatmap;
  const movie = window.CLOCK_VIDEO_CATALOG?.papers[p.id]?.videos.find(
    (video) => video.id === c.comparison_video_id,
  );
  return `${heatmap}<details class="fold methodReferenceComparison"><summary>${esc(c.detail_title)}</summary>
    ${movie ? link(assetUrl(movie.src) || movie.source_url, movie.title) : ""}
    ${matrixStudyFigure(p, c)}
  </details>`;
}
export function samplingFigure(p, datasetId) {
  if (p.method_figure) return methodFigure(p);
  const c = DB.comparison.datasets.find(
    (c) => c.id === (datasetId || p.kymograph?.default_dataset || p.id),
  );
  const walkthrough = DB.card_presentation?.[c?.id]?.method_figure;
  if (walkthrough) return methodFigure(p, walkthrough, c);
  if (
    c?.kind === "matrix" &&
    (c.detail_primary_context || p.id === "chhabra-2026")
  )
    return matrixWalkthrough(p, c);
  if (c?.detail_figures) return matrixStudyFigure(p, c);

  if (!c)
    return `<p class="brief">${esc(p.kymograph?.note || p.kymograph?.panel_note || p.figure_focus)}</p>`;
  const r = p.kymograph?.rendered?.intensity || p.kymograph || {},
    roi = c.roi || r.roi_preview;
  const coverage = coverageSummary(c);
  const plot = (url, caption, alt) =>
    `<figure><figcaption>${esc(caption)}</figcaption><a href="${esc(figureUrl(url))}" target="_blank" rel="noopener noreferrer"><img src="${esc(figureUrl(url))}" alt="${esc(alt)}"></a></figure>`;
  const matrixNote =
    c.kind === "matrix"
      ? t(
          "Rendered directly from an author-provided matrix; no video was resampled for this plot.",
        )
      : t(
          "A sampling-region illustration is not yet available for this entry.",
        );
  const method =
    c.sampling_method ||
    (p.id === "chhabra-2026"
      ? t(
          "The author-processed intensity TIFF is displayed at 10 min per column and 1.38 µm per row. Stored ordering is retained, with one min–max normalization over the complete sample’s finite values; no resampling, smoothing, or phase inference.",
        )
      : r.model_note || p.preprocessing);
  const provenance =
    c.provenance ||
    (["lauschke-2013", "sonnen-2018"].includes(p.id)
      ? `data/derived/${p.id}/extraction-provenance.json`
      : null);
  return `${relatedDatasets(p, c)}<section class="methodFigure samplingDetails">
  <h3>${t("Experimental replot and sampling documentation")}</h3><p class="methodContext">${esc(kindLabel(c))} · ${esc(coverage)}</p>${coverageMethod(c)}${datasetSourceDetails(p, c)}
  ${!roi ? `<p class="brief">${esc(matrixNote)}</p>` : ""}
  <div class="samplingFigureGrid ${!roi ? "singleSource" : ""}">
   ${roi ? plot(roi, t("Sampling region & reference frames"), c.roi_note || t("Sampling region & reference frames")) : ""}
   ${plot(c.kind === "matrix" ? DB.card_previews?.[c.id]?.preview || c.full_preview : c.full_preview, t("Full extracted range"), p.short + " " + c.reporter)}
  </div>
  ${roi ? `<p class="samplingCaption">${esc(c.roi_note || t("Sampling paths in the first, middle, and last frames. Translation correction does not account for tissue deformation or track individual cells."))}</p>` : ""}
  <dl class="samplingFacts">${[
    [t("Time axis"), r.time || p.time_axis],
    [t("Space axis"), r.space || p.space_axis],
  ]
    .map(
      ([label, value]) =>
        `<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`,
    )
    .join("")}</dl>
  <h4>${t("Extraction & rendering")}</h4><p class="samplingMethod">${esc(method)}</p>
  <p class="samplingMethod">${t("Each complete sample is normalized independently: 0 is light, 1 is dark, and gray marks missing values. Colors do not compare absolute expression across samples.")}</p>
  ${r.limit ? `<p class="methodLimit">${esc(r.limit)}</p>` : ""}
  <footer class="methodLinks">${["svg", "png", "pdf"].map((fmt) => link(figureUrl(c.full_preview.replace(/\.svg$/, "." + fmt)), fmt.toUpperCase())).join("")}
   ${link(assetUrl(c.input), t("Matrix"))}${provenance ? link(assetUrl(provenance), t("Processing record")) : ""}${comparisonSourceLinks(c)}
  </footer>
 </section>`;
}

// SPDX-License-Identifier: MIT
import { DB, t } from "./context.js";
import { $, esc, figureUrl, link } from "./dom.js";
import {
  datasetPaper,
  comparisonRecords,
  visibleComparisonRecords,
  species,
} from "./catalog.js";
import { sourceBadge, hideMethodHelp } from "./tooltips.js";
import {
  datasetContext,
  measurementFacts,
  sourceSelection,
} from "./card-metadata.js";
export function renderKymographs() {
  renderKymoComparison();
}
export function coverageSummary(c) {
  const m = DB.temporal_coverage?.[c.id];
  if (c.phase_ordered)
    return t("{count} phase-ordered embryos", { count: c.shape_space_time[1] });
  if (!m)
    return (
      c.coverage_note ||
      t("Full record: {frames} frames · {hours} h", {
        frames: c.shape_space_time[1],
        hours: (c.time_range_h[1] - c.time_range_h[0]).toFixed(2),
      })
    );
  const values = { used: m.used, total: m.total };
  const count =
    m.mode === "measured"
      ? t("Measured: {used}/{total} time points", values)
      : m.unit === "frames"
        ? m.mode === "all"
          ? t("All {used}/{total} frames", values)
          : t("Subset: {used}/{total} frames", values)
        : m.mode === "all"
          ? t("All {used}/{total} time points", values)
          : t("Subset: {used}/{total} time points", values);
  const duration =
    m.duration_label ||
    (c.time_range_h
      ? (c.time_range_h[1] - c.time_range_h[0]).toFixed(2) + " h"
      : "");
  return count + (duration ? " · " + duration : "");
}
export function coverageMethod(c) {
  const m = DB.temporal_coverage?.[c.id];
  return m ? `<p class="samplingCaption">${esc(m.note)}</p>` : "";
}
export function kymoCardContext(id) {
  const record = comparisonRecords().find((c) => c.id === id),
    paper = record && datasetPaper(record),
    presentation = DB.card_presentation?.[id] || {},
    context = record && datasetContext(record, paper),
    conditions =
      presentation.conditions || [context?.condition].filter(Boolean);
  return conditions.length
    ? `<p class="kymoCardContext">${conditions.map((condition) => `<span ${condition === record?.system_label && record.system_meaning ? `title="${esc(record.system_meaning)}"` : ""}>${esc(condition)}</span>`).join('<span class="conditionDivider" aria-hidden="true">·</span>')}</p>`
    : "";
}
export function datasetSourceDetails(paper, selected) {
  const record = selected || comparisonRecords().find((c) => c.id === paper.id);
  if (!record) return "";
  const model = [record.system_label, record.system_meaning]
      .filter(Boolean)
      .join(" · "),
    signalNote =
      record.reporter_note || DB.card_presentation?.[record.id]?.signal_note,
    facts = [
      [t("Source / sample"), sourceSelection(record, paper).join(" · ")],
      [t("Experimental model"), model],
      [t("Coordinate reference"), record.origin_short || record.origin],
      [t("Signal note"), signalNote],
    ].filter(([, value]) => value);
  return facts.length
    ? `<dl class="datasetSourceDetails">${facts.map(([label, value]) => `<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`).join("")}</dl>`
    : "";
}
export function comparisonSourceLinks(c) {
  const p = datasetPaper(c),
    assets = p?.assets || [];
  const input = assets.find((a) => a.source_is_input && a.url);
  const movies = assets.filter(
    (a) => a.level === "movie" && a.status === "verified_content" && a.url,
  );
  const dataUrl =
    c.data_url ||
    input?.url ||
    p?.kymograph?.dataset_url ||
    p?.kymograph?.movie_url ||
    (c.source_url !== p?.url ? c.source_url : null) ||
    (movies.length === 1 ? movies[0].url : null) ||
    c.source_url;
  return `<span class="kymoCompareSources">${link(p?.url, t("Paper"))}${link(dataUrl, t("Data"))}</span>`;
}
const speciesIllustrations = {
  "Mus musculus": "mouse",
  "Danio rerio": "zebrafish",
  "Oryzias latipes": "medaka",
  "Homo sapiens": "human-model",
  "Gallus gallus": "chicken",
};
function speciesHeadingIllustration(key) {
  const name = speciesIllustrations[key];
  return name
    ? `<img class="speciesSectionIllustration" src="brand/species/${name}.png" alt="" aria-hidden="true" width="84" height="56" decoding="async">`
    : "";
}
// Sort by paper year before grouping, so species sections also start with
// the earliest represented paper. Equal-year datasets from one paper stay together.
export function comparisonSpeciesGroups(records) {
  const chronological = [...records].sort((a, b) => {
    const pa = datasetPaper(a),
      pb = datasetPaper(b);
    return pa.year - pb.year || pa.id.localeCompare(pb.id, "en");
  });
  const groups = new Map();
  for (const record of chronological) {
    const paper = datasetPaper(record),
      key = paper.species;
    if (!groups.has(key))
      groups.set(key, { key, label: species(paper), records: [] });
    groups.get(key).records.push(record);
  }
  return [...groups.values()];
}

function playableCardsFirst(records) {
  const playable = [];
  const remaining = [];
  for (const record of records) {
    const paperId = record.paper_id || record.id;
    if (window.ClockVideos?.hasCardPlayback(paperId, record.id)) {
      playable.push(record);
    } else {
      remaining.push(record);
    }
  }
  return [...playable, ...remaining];
}

export function renderKymoComparison() {
  hideMethodHelp();
  const records = visibleComparisonRecords();
  if (!records.length) {
    $("#kymographs").replaceChildren();
    return;
  }
  const renderCards = (rows) =>
    `<div class="kymoCompareGrid">${rows
      .map((c) => {
        const p = datasetPaper(c),
          range = c.phase_ordered
            ? t("Phase-ordered expression domains")
            : c.uncalibrated
              ? t("Frame-index preview")
              : t("Full time range"),
          presentation = DB.card_presentation?.[c.id] || {},
          experimentalFacts = presentation.experimental_facts || [],
          targets =
            presentation.target_genes ||
            [c.target_gene || p.target_gene].filter(Boolean),
          targetMarkup = targets.length
            ? targets.map((gene) => `<em>${esc(gene)}</em>`).join(" / ")
            : `<span>${t(presentation.target_gene_applicable === false ? "Not applicable" : "Unspecified")}</span>`,
          facts = measurementFacts(c, DB.temporal_coverage?.[c.id], t),
          generatedPreview = DB.card_previews?.[c.id],
          preview = generatedPreview?.preview || c.full_preview,
          alignedPlot = !!generatedPreview?.layout,
          plotNote = generatedPreview
            ? presentation.axis_polarity?.note ||
              presentation.coordinate_note ||
              ""
            : "";
        return `<article class="kymoCompareCard${experimentalFacts.length ? " hasExperimentFacts" : ""}${alignedPlot ? " hasAlignedPlot" : ""}" data-dataset="${esc(c.id)}">
   <div class="kymoCompareTop"><div><span class="eyebrow kymoIdentity"><span class="speciesLabel">${esc(species(p))}</span><span class="identityDivider" aria-hidden="true"> · </span><span class="paperCitation">${esc(c.short)}</span></span><h4>${esc(c.card_title || c.reporter)}</h4>${experimentalFacts.length ? "" : `<p class="targetGene">${t("Target gene")} · ${targetMarkup}</p>`}${experimentalFacts.length ? "" : kymoCardContext(c.id)}</div>${sourceBadge(c)}</div>
   ${experimentalFacts.length ? `<dl class="cardExperiment"><div class="targetGene"><dt>${t("Target gene")}</dt><dd>${targetMarkup}</dd></div>${experimentalFacts.map((fact) => `<div><dt>${esc(fact.label)}</dt><dd${fact.unverified ? ' class="unverified"' : ""}>${esc(fact.value)}</dd></div>`).join("")}</dl>` : ""}
   <img src="${esc(figureUrl(preview))}"${plotNote ? ` title="${esc(plotNote)}"` : ""} alt="${esc(c.short + " " + c.reporter + " " + range + (c.phase_ordered ? "" : t(" redrawn kymograph")) + (plotNote ? " · " + plotNote : ""))}">
   <dl class="cardMeasurements">${facts.map((fact) => `<div><dt>${esc(fact.label)}</dt><dd${fact.unverified ? ' class="unverified"' : ""}>${esc(fact.value)}</dd></div>`).join("")}</dl>
   <div class="kymoCompareActions"><button class="cardOpen" data-method-figure="${esc(c.id)}" aria-haspopup="dialog" aria-label="${esc(t("View {paper} figure and sampling methods", { paper: p.short }))}">${t("Figure & sampling")} <span class="cardOpenArrow" aria-hidden="true">↗</span></button>${window.ClockVideos?.cardLink(p.id, c.id) || ""}<span class="kymoCompareSources">${link(p.url, t("Paper"))}</span></div>
  </article>`;
      })
      .join("")}</div>`;
  const speciesSections = (rows, prefix) =>
    comparisonSpeciesGroups(rows)
      .map((group, index) => {
        const ordered =
          prefix === "gallery" && group.key === "Mus musculus"
            ? playableCardsFirst(group.records)
            : group.records;
        return `<section class="speciesSection" data-species="${esc(group.key)}" aria-labelledby="${prefix}-species-${index}"><h3 id="${prefix}-species-${index}" class="speciesSectionTitle">${speciesHeadingIllustration(group.key)}<span>${esc(group.label)}</span></h3>${renderCards(ordered)}</section>`;
      })
      .join("");
  if (DB.catalog_review) {
    const published = new Set(DB.catalog_review.published);
    const candidates = new Set(DB.catalog_review.candidates);
    const sections = [
      [
        "candidates",
        "Awaiting review",
        records.filter((c) => candidates.has(c.id)),
      ],
      [
        "local-additions",
        "Local additions",
        records.filter((c) => !published.has(c.id) && !candidates.has(c.id)),
      ],
      [
        "published",
        "Published on the website",
        records.filter((c) => published.has(c.id) && !candidates.has(c.id)),
      ],
    ].filter(([, , rows]) => rows.length);
    const links = sections.map(
      ([id, title, rows]) => `<a href="#${id}">${title} (${rows.length})</a>`,
    );
    $("#kymographs").innerHTML =
      `<nav aria-label="Review groups">${links.join(" · ")}</nav>` +
      sections
        .map(
          ([id, title, rows]) =>
            `<section id="${id}"><h2>${title} (${rows.length})</h2>${speciesSections(rows, id)}</section>`,
        )
        .join("");
    return;
  }
  $("#kymographs").innerHTML =
    `<div class="kymoHeading"><div><h2>${t("Compare kymographs")}</h2></div></div>${speciesSections(records, "gallery")}`;
}

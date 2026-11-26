// SPDX-License-Identifier: MIT
import { DB, t } from "./context.js";
import { esc, link, figureUrl, localFigurePath } from "./dom.js";
import { assetUrl } from "./assets.js";
import { statusLabel, statusClass, size } from "./catalog.js";
import { videosForDataset } from "./video-selection.js";

export const combinedSources = (p, datasetId) =>
  detailPresentation(p, datasetId).detail_layout === "combined_sources";

function selectedDataset(p, datasetId) {
  return DB.comparison.datasets.find(
    (record) =>
      record.id === (datasetId || p.kymograph?.default_dataset || p.id),
  );
}
export function detailPresentation(p, datasetId) {
  const id = datasetId || p.kymograph?.default_dataset || p.id;
  return {
    ...DB.card_presentation?.[p.id],
    ...DB.card_presentation?.[id],
  };
}
function sourceRecord(source) {
  const label = /\.(mov|mp4)(?:[?#]|$)/i.test(source.url || "")
    ? t("Open original video")
    : source.url?.includes("eutils.ncbi.nlm.nih.gov")
      ? t("View metadata")
      : t("View paper");
  return `<div class="verificationSource" data-verification-source="${esc(source.id)}"><strong>${esc(source.location)}</strong><p>${esc(source.note || source.supports || "")}</p>${link(source.url, label)}</div>`;
}
function sourceRecords(p, ids = []) {
  return [...new Set(ids)]
    .map((id) => p.sources.find((source) => source.id === id))
    .filter(Boolean)
    .map(sourceRecord)
    .join("");
}
export function fieldVerification(p, ids = []) {
  const records = sourceRecords(p, ids);
  return records
    ? `<details class="fieldVerification"><summary>${t("Basis")}</summary>${records}</details>`
    : "";
}
export function overviewExperiment(p, datasetId) {
  const presentation = detailPresentation(p, datasetId);
  const record = selectedDataset(p, datasetId);
  const facts = [
    {
      label: "Reporter",
      value: record?.reporter || p.reporter_short,
      evidence_ids: p.field_evidence.reporter_construct,
    },
    {
      label: t("Target gene"),
      value:
        presentation.target_gene_applicable === false
          ? t("Not applicable")
          : presentation.target_genes.join(" / "),
      gene: presentation.target_gene_applicable !== false,
      evidence_ids: p.field_evidence.reported_target,
    },
    ...(presentation.experimental_facts || []),
  ];
  return `<dl class="overviewExperiment">${facts.map((fact) => `<div class="overviewFact"><dt>${esc(fact.label)}</dt><dd${fact.unverified ? ' class="unverified"' : ""}>${fact.gene ? `<em>${esc(fact.value)}</em>` : esc(fact.value)}${fieldVerification(p, fact.evidence_ids)}</dd></div>`).join("")}</dl>`;
}
function download(path, label) {
  const dataFile =
    /^data\/(?:samples|derived)\/[a-z0-9-]+\/(?:[A-Za-z0-9_-][A-Za-z0-9_.-]*\/)*[A-Za-z0-9_-][A-Za-z0-9_.-]*$/.test(
      path || "",
    );
  const figureArchive =
    /^figures\/[a-z0-9-]+\/(?:[A-Za-z0-9_-][A-Za-z0-9_.-]*\/)*[A-Za-z0-9_-][A-Za-z0-9_.-]*\.zip$/.test(
      path || "",
    );
  return dataFile || figureArchive
    ? `<a href="${esc(assetUrl(path))}" download>${esc(label)} ↓</a>`
    : "";
}
function fileLinks(p, a) {
  if (a.source_only) return link(a.url, t("Open author file"));
  if (a.level === "figure" && a.local_path && localFigurePath(a.local_path))
    return link(figureUrl(a.local_path), t("View review figure"));
  if (a.level === "derived" && a.local_path) {
    return (
      download(a.local_path, t("Download matrix (NPZ)")) +
      download(
        p.method_figure?.provenance_path,
        t("Download processing record (JSON)"),
      )
    );
  }
  if (a.local_path) {
    const format = a.local_path.split(".").pop().toUpperCase();
    return download(
      a.local_path,
      a.primary_matrix
        ? t("Download matrix ({format})", { format })
        : t("Download file ({format})", { format }),
    );
  }
  const label = {
    figure: t("View paper figure"),
    movie: t("Open original video"),
    document: t("View supplementary materials"),
    supplement: t("View supplementary materials"),
    matrix: t("Open author matrix"),
    raw: t("Open raw imaging files"),
  }[a.level];
  return link(a.url, label || t("Open file"));
}
function sourceAsset(p, a, presentation) {
  const ids = presentation.asset_evidence?.[a.level] || [];
  const title =
    a.level === "matrix" && !a.local_path && !a.source_only
      ? t("Author intensity matrix")
      : a.level === "raw"
        ? t("Raw imaging stacks")
        : a.label;
  const subtitle =
    !["matrix", "raw"].includes(a.level) && a.level_label !== title;
  return `<div class="asset"><div class="assetHead"><div>${subtitle ? `<small>${esc(a.level_label)}</small>` : ""}<h3>${esc(title)}</h3></div><span class="badge ${statusClass(a.status)}">${esc(statusLabel(a.status))}</span></div><div class="dataSourceLinks">${fileLinks(p, a)}</div><details class="fold"><summary>${t("Verification record")}</summary><p>${esc(a.evidence)}</p>${sourceRecords(p, ids)}<div class="assetMeta">${esc(a.format || t("Format unknown"))} · ${esc(size(a))}<br>${t("Checked")} ${esc(a.checked || DB.checked)} · ${t("License")}: ${esc(a.license || t("Unknown"))}</div></details></div>`;
}
export function filesForDataset(p, datasetId) {
  const presentation = detailPresentation(p, datasetId);
  const record = selectedDataset(p, datasetId);
  let files = p.assets.filter((a) => a.level !== "contact");
  if (record?.input && presentation.sample_asset?.local_path === record.input) {
    return [
      { ...presentation.sample_asset, primary_matrix: true },
      ...files.filter((a) => !a.local_path),
    ];
  }
  if (
    !record ||
    (!presentation.detail_asset_paths && !record.author_file_links)
  )
    return files;
  const paths = new Set([
    record.input,
    ...(presentation.detail_asset_paths || []),
  ]);
  const id = datasetId || p.kymograph?.default_dataset || p.id;
  const [video] = videosForDataset(
    window.CLOCK_VIDEO_CATALOG?.papers[p.id],
    p.id,
    id,
  );
  const source =
    video?.source_url ||
    record.data_url ||
    (id === p.id ? p.kymograph?.rendered?.intensity?.source_url : null);
  files = files.filter((a) =>
    a.local_path
      ? paths.has(a.local_path)
      : a.level === "movie"
        ? a.url === source
        : true,
  );
  if (record.author_file_links) {
    const authorFiles = record.author_file_links.map((file) => ({
      ...file,
      level: "matrix",
      level_label: t("Author data"),
      status: "verified_content",
      evidence: t(
        "Source file for this kymograph. The original is available from the authors.",
      ),
      license: t("Redistribution permission unconfirmed"),
      source_only: true,
    }));
    return [
      ...authorFiles,
      ...files.filter((a) => a.local_path || a.level !== "matrix"),
    ];
  }
  if (!record.input) return files;
  const input = files.find((a) => a.local_path === record.input);
  if (input) {
    files = files.map((a) =>
      a === input
        ? {
            ...a,
            primary_matrix: true,
            label: presentation.primary_matrix_label || a.label,
          }
        : a,
    );
  } else {
    // The plotted input is authoritative even when the paper asset list only
    // contains its CSV export or additional processing records.
    const terms = p.assets.find((a) => a.local_path)?.license;
    files.push({
      level: "matrix",
      level_label: t("Locally extracted matrix"),
      label:
        presentation.primary_matrix_label || t("Matrix for this kymograph"),
      local_path: record.input,
      format: "NPZ",
      status: "verified_content",
      primary_matrix: true,
      evidence: t(
        "Numerical input used for this redraw; see Figure & sampling for extraction and calibration.",
      ),
      license: terms,
    });
  }
  return files;
}
export function dataSources(p, datasetId) {
  const presentation = detailPresentation(p, datasetId);
  const order = [
    "movie",
    "derived",
    "figure",
    "document",
    "supplement",
    "matrix",
    "raw",
  ];
  const rank = (a) =>
    a.primary_matrix
      ? 1
      : a.local_path
        ? 2
        : a.level === "movie"
          ? 0
          : 3 + order.indexOf(a.level);
  const files = filesForDataset(p, datasetId).sort((a, b) => rank(a) - rank(b));
  const contacts = p.assets.filter((a) => a.level === "contact");
  return `<p class="notesStatus">${t("Videos, matrices and supplementary materials. Expand a verification record for details.")}</p>${files.map((a) => sourceAsset(p, a, presentation)).join("")}<details class="fold"><summary>${t("Verification scope and missing data")}</summary><p>${esc(p.verification_scope)}</p><ul>${p.missing.map((value) => `<li>${esc(value)}</li>`).join("")}</ul>${contacts.map((a) => `<p>${esc(a.evidence)}</p>`).join("")}</details>`;
}

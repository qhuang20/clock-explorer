// SPDX-License-Identifier: MIT
import { drawRoi } from "./roi-drawing.js";
import { assetUrl } from "./assets.js";
import { videosForDataset } from "./video-selection.js";
import {
  samplingRoiForVideo,
  validateRoiDocument,
  sourceFrameAtTime,
  rectangleRoi,
} from "./video-roi.js";
("use strict");

// Playback copies are separate from the source movies used for analysis.
// This module owns only the Videos pane; the existing detail tabs own navigation.
window.ClockVideos = (() => {
  const memories = new Map();
  let active = null;
  let mediaLoad = null;
  const roiVisibility = new Map();
  const roiCache = new Map();
  let roiLoad = null;
  function releaseRoi() {
    if (!roiLoad) return;
    roiLoad.controller.abort();
    if (roiLoad.callback !== undefined)
      roiLoad.video.cancelVideoFrameCallback?.(roiLoad.callback);
    roiLoad = null;
  }

  function updateRoi(seconds) {
    const request = roiLoad;
    if (!request) return;
    const toggle = document.querySelector("#videoRoiToggle");
    const svg = document.querySelector("#videoRoi");
    const status = document.querySelector("#videoRoiStatus");
    if (!toggle || !svg || !status) return;
    document
      .querySelector("#videoRoiDiagram")
      ?.toggleAttribute("hidden", !toggle.checked);
    svg.toggleAttribute("hidden", !toggle.checked);
    status.hidden = true;
    if (!toggle.checked) return;
    if (!request.data && !request.fixed) {
      svg.setAttribute("hidden", "");
      status.hidden = false;
      status.textContent = request.error
        ? "Sampling ROI could not load"
        : "Loading sampling ROI…";
      return;
    }
    const index = request.fixed
      ? 0
      : sourceFrameAtTime(
          request.data.frame_starts_s,
          seconds ?? request.video.currentTime,
          seconds !== undefined,
        );
    const frame = request.fixed || request.frames.get(index);
    if (!frame || (!frame.bands.length && !frame.show_reference_only)) {
      svg.setAttribute("hidden", "");
      status.hidden = false;
      status.textContent = frame
        ? "No valid sampling region in this frame"
        : "This frame was not used for this kymograph";
      return;
    }
    if (request.drawnIndex !== index) {
      drawRoi(
        svg,
        frame,
        request.data?.direction_labels,
        undefined,
        request.item.sampling_style,
      );
      request.drawnIndex = index;
    }
    svg.dataset.frameIndex = String(index);
  }

  async function loadRoi(request) {
    if (request.data || request.fixed || request.loading) return;
    request.loading = true;
    request.error = false;
    updateRoi();
    try {
      const cacheKey = request.path + ":" + (request.inputHash || "");
      let data = roiCache.get(cacheKey);
      if (!data) {
        const path = assetUrl(request.path);
        const response = await fetch(
          path +
            (request.inputHash
              ? (path.includes("?") ? "&" : "?") +
                "v=" +
                request.inputHash.slice(0, 12)
              : ""),
          {
            signal: request.controller.signal,
          },
        );
        if (!response.ok) throw new Error("ROI HTTP " + response.status);
        data = await response.json();
      }
      validateRoiDocument(
        data,
        request.item,
        request.datasetId,
        request.inputHash,
      );
      roiCache.set(cacheKey, data);
      if (roiLoad !== request) return;
      request.data = data;
      request.frames = new Map(data.frames.map((f) => [f.index, f]));
    } catch (error) {
      if (roiLoad !== request || error.name === "AbortError") return;
      request.error = true;
    } finally {
      request.loading = false;
      if (roiLoad === request) updateRoi();
    }
  }

  function bindRoi(video, item, datasetId, config, memoryKey) {
    const toggle = document.querySelector("#videoRoiToggle");
    if (!toggle) return;
    const request = {
      video,
      item,
      datasetId,
      inputHash: window.CLOCK_DATA?.comparison?.datasets?.find(
        (c) => c.id === datasetId,
      )?.input_sha256,
      controller: new AbortController(),
      path: config.path,
      fixed: config.rect ? rectangleRoi(config.rect) : null,
    };
    roiLoad = request;
    toggle.checked = roiVisibility.get(memoryKey) ?? true;
    toggle.addEventListener("change", () => {
      roiVisibility.set(memoryKey, toggle.checked);
      if (toggle.checked) loadRoi(request);
      updateRoi();
    });
    for (const event of [
      "timeupdate",
      "seeked",
      "loadeddata",
      "loadedmetadata",
      "ended",
    ])
      video.addEventListener(event, () => updateRoi());
    if (video.requestVideoFrameCallback) {
      const tick = (_, metadata) => {
        if (roiLoad !== request) return;
        updateRoi(metadata.mediaTime);
        request.callback = video.requestVideoFrameCallback(tick);
      };
      request.callback = video.requestVideoFrameCallback(tick);
    }
    if (toggle.checked) loadRoi(request);
    updateRoi();
  }
  // Pages returns whole files for Range requests. A selected, on-demand Blob
  // gives the native player a seekable source without fetching other movies.
  function releaseMedia() {
    if (!mediaLoad) return;
    mediaLoad.controller.abort();
    if (mediaLoad.objectUrl) URL.revokeObjectURL(mediaLoad.objectUrl);
    mediaLoad = null;
  }
  async function loadSeekableVideo(video, button, path) {
    const request = {
      controller: new AbortController(),
      objectUrl: null,
      playWhenReady: true,
    };
    releaseMedia();
    mediaLoad = request;
    button.disabled = true;
    button.textContent = "Loading…";
    document.querySelector("#videoError").hidden = true;
    try {
      const response = await fetch(path, { signal: request.controller.signal });
      if (!response.ok) throw new Error("Video HTTP " + response.status);
      const blob = await response.blob();
      if (mediaLoad !== request) return;
      request.objectUrl = URL.createObjectURL(blob);
      video.src = request.objectUrl;
      video.controls = true;
      video.playbackRate = Number(
        document.querySelector("#videoSpeed")?.value || 1,
      );
      button.remove();
      video.load();
      if (
        request.playWhenReady &&
        !document.querySelector("#pane-videos").hidden &&
        !document.hidden
      ) {
        try {
          await video.play();
        } catch {
          /* Native play remains available. */
        }
      }
    } catch (error) {
      if (mediaLoad !== request || error.name === "AbortError") return;
      button.disabled = false;
      button.textContent = "Retry video";
      document.querySelector("#videoError").hidden = false;
    }
  }
  const escape = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const mediaPath = (path) =>
    /^videos\/[a-z0-9-]+\/[a-z0-9-]+\.(mp4|jpg)$/.test(path || "")
      ? assetUrl(path)
      : "";
  const sourceUrl = (url) => {
    try {
      const u = new URL(url);
      return u.protocol === "https:" ? u.href : "#";
    } catch {
      return "#";
    }
  };
  const link = (url, label, className = "") =>
    `<a${className ? ` class="${escape(className)}"` : ""} href="${escape(sourceUrl(url))}" target="_blank" rel="noopener noreferrer">${escape(label)} ↗</a>`;
  const licenseLink = (item) =>
    item.reuse_license
      ? link(item.reuse_license.url, item.reuse_license.label, "videoLicense")
      : "";
  const licenseCredit = (item) =>
    item.reuse_license?.credit
      ? `<p class="videoAttribution">${escape(item.reuse_license.credit)}</p>`
      : "";
  const originalLabel = (movie) =>
    movie.source_link_label ||
    (movie.generated_from_images
      ? "Original image sequence"
      : "Original video");
  const externalVideo = (videos) =>
    videos.length === 1 && videos[0].availability === "external_only"
      ? videos[0]
      : null;
  const videoSourceNotice = (movie) =>
    `<div class="videoSourceNotice">${link(movie.source_url, originalLabel(movie), "videoShortcut")}<span>Source link · Hosting permission unconfirmed</span></div>`;

  function pause() {
    if (mediaLoad) mediaLoad.playWhenReady = false;
    document.querySelector("#paperVideo")?.pause();
  }
  function pauseSamplingVideo() {
    document.querySelector(".samplingVideo video")?.pause();
  }
  function unmount() {
    pauseSamplingVideo();
    releaseRoi();
    const video = document.querySelector("#paperVideo");
    if (video) {
      video.pause();
      video.removeAttribute("src");
      video.load();
    }
    releaseMedia();
    active = null;
  }
  function mount(paperId, datasetId) {
    unmount();
    const paper = window.CLOCK_VIDEO_CATALOG?.papers[paperId];
    if (!paper) return;
    datasetId ||= paperId;
    const videos = videosForDataset(paper, paperId, datasetId);
    if (!videos.length) return;
    const memoryKey = paperId + ":" + datasetId;
    const selected = videos.some(
      (video) => video.id === memories.get(memoryKey),
    )
      ? memories.get(memoryKey)
      : videos[0].id;
    active = {
      paperId,
      paper,
      videos,
      datasetId,
      memoryKey,
      selected,
      rendered: false,
    };
    const tab = document.createElement("button");
    tab.type = "button";
    tab.id = "tab-videos";
    tab.dataset.pane = "videos";
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-controls", "pane-videos");
    tab.setAttribute("aria-selected", "false");
    tab.textContent = videos.length === 1 ? "Video" : "Videos";
    document.querySelector("#tab-media").after(tab);
    const pane = document.createElement("section");
    pane.id = "pane-videos";
    pane.className = "detailPane";
    pane.hidden = true;
    pane.setAttribute("role", "tabpanel");
    pane.setAttribute("aria-labelledby", "tab-videos");
    document.querySelector("#pane-media").after(pane);
    const original = externalVideo(videos);
    if (original) {
      document
        .querySelector("#pane-media")
        .insertAdjacentHTML("afterbegin", videoSourceNotice(original));
      return;
    }
    const shortcut = document.createElement("button");
    shortcut.type = "button";
    shortcut.className = "videoShortcut";
    shortcut.dataset.pane = "videos";
    shortcut.textContent = videos.some((v) => v.src)
      ? videos.length === 1
        ? "▷ Watch video"
        : "▷ Watch videos"
      : "Video availability";
    const paneMedia = document.querySelector("#pane-media");
    if (videos.length === 1 && videos[0].reuse_license) {
      const notice = document.createElement("div");
      notice.className = "videoSourceNotice";
      notice.append(shortcut);
      notice.insertAdjacentHTML("beforeend", licenseLink(videos[0]));
      paneMedia.prepend(notice);
    } else {
      paneMedia.prepend(shortcut);
    }
  }
  function onPane(id) {
    if (id !== "media") pauseSamplingVideo();
    if (id !== "videos") {
      pause();
      return;
    }
    if (active && !active.rendered) render();
  }
  function render() {
    if (!active) return;
    pause();
    releaseMedia();
    releaseRoi();
    const { paper, videos, paperId, datasetId, memoryKey } = active;
    if (!videos.length) {
      active.rendered = true;
      document.querySelector("#pane-videos").innerHTML =
        `<div class="videoUnavailable"><p>${escape(paper.unavailable_note)}</p>${link(paper.data_url || paper.article_url, "Public data")}</div>`;
      return;
    }
    const item = videos.find((v) => v.id === active.selected) || videos[0];
    active.selected = item.id;
    active.rendered = true;
    memories.set(memoryKey, item.id);
    const available = Boolean(mediaPath(item.src));
    const externalOnly = item.availability === "external_only";
    const sourceTerms =
      item.license || paper.license || "Reuse terms unconfirmed.";
    const seekableCopy = location.protocol !== "file:";
    const title = item.title;
    const description = item.description;
    const poster = mediaPath(item.poster);
    const isSource = item.source_dataset_ids?.includes(datasetId || paperId);
    const roi = samplingRoiForVideo(item, datasetId);
    // The loopback preview can display the saved ROI directly on the frame.
    const roiDiagram =
      roi?.diagram &&
      !["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
    const frameStyle = `aspect-ratio:${item.width}/${item.height};max-width:${Math.round((420 * item.width) / item.height)}px`;
    const roiSvg = roi
      ? `<svg id="videoRoi" class="videoRoi" viewBox="0 0 ${item.width} ${item.height}" aria-hidden="true" hidden></svg>`
      : "";
    const relation = item.relation_note
      ? item.relation_note
      : isSource
        ? "Source for this kymograph"
        : item.used_for_kymograph
          ? "Source for another kymograph in this paper"
          : "Related experiment · Same sample not confirmed";
    const kind =
      item.kind === "rotation"
        ? "3D rotation · Not time-lapse"
        : item.kind === "zstack"
          ? "Z-stack · Not time-lapse"
          : item.generated_from_images
            ? "Image sequence → Video"
            : "Time-lapse";
    const stage = available
      ? `<div class="sourceVideoStage"><div class="sourceVideoFrame" style="${frameStyle}">
      <video id="paperVideo" ${seekableCopy ? "" : `controls src="${mediaPath(item.src)}"`} playsinline preload="none"${poster ? ` poster="${poster}"` : ""} aria-label="${escape(title)}"></video>
      ${item.specimen_label ? `<span class="videoSpecimenLabel">${escape(item.specimen_label)}</span>` : ""}
      ${seekableCopy ? `<button type="button" class="videoStart" id="videoStart">▶ Play video</button>` : ""}
      ${roiDiagram ? "" : roiSvg}
      </div></div>`
      : externalOnly
        ? videoSourceNotice(item)
        : `<div class="videoUnavailable"><p>In-page playback is not available yet. Open the original source below.</p>${link(item.source_url, "Open source video")}</div>`;
    const playback =
      available && roiDiagram
        ? `<div class="videoRoiComparison">
          ${stage}
          <figure id="videoRoiDiagram" class="videoRoiDiagram">
            <div class="sourceVideoStage"><div class="sourceVideoFrame" style="${frameStyle}">${roiSvg}</div></div>
            <figcaption>Sampling ROI · Synchronized with video</figcaption>
          </figure>
        </div>`
        : stage;
    document.querySelector("#pane-videos").innerHTML = `
      ${videos.length > 1 ? `<div class="videoToolbar"><label for="videoSelect">Select video<select id="videoSelect">${videos.map((v) => `<option value="${escape(v.id)}" ${v.id === item.id ? "selected" : ""}>${escape(v.title)}${v.src ? "" : " · Source link"}</option>`).join("")}</select></label><span class="videoCount">${videos.length} videos</span></div>` : `<h3 class="videoTitle">${escape(title)}</h3>`}
      <div class="videoFacts"><span>${escape(item.reporter || paper.reporter)}</span><span>${escape(item.temperature || paper.temperature)}</span><span class="videoUsed">${escape(kind)}</span>${available ? licenseLink(item) : ""}</div>
      <p class="videoRelation">${escape(relation)}</p>
      ${playback}
      ${available ? '<p id="videoError" class="videoError" role="status" hidden>The video could not load. Open the original source or download the playback copy.</p>' : ""}
      ${available ? `<div class="videoControls"><label>Speed <select id="videoSpeed" aria-label="Playback speed"><option value="0.25">0.25×</option><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option></select></label>${roi ? `<label class="videoRoiToggle"><input type="checkbox" id="videoRoiToggle">Show sampling ROI</label><span id="videoRoiStatus" class="videoRoiStatus" role="status" hidden></span>` : ""}<span>${item.frames} frames</span></div>` : ""}
      ${description ? `<p class="videoDescription">${escape(description)}</p>` : ""}
      ${externalOnly ? '<p class="videoAttribution">' + escape(sourceTerms) + "</p>" : available ? licenseCredit(item) : ""}
      ${available ? `<p class="videoTimeNote">The progress bar shows playback time, not elapsed experiment time.</p>` : ""}
      <div class="videoLinks">${externalOnly ? "" : link(item.source_url, originalLabel(item))}${item.source_page_url && item.source_page_url !== item.source_url ? link(item.source_page_url, "Supplementary materials") : ""}${link(paper.article_url, "Paper")}${available ? `<a href="${mediaPath(item.src)}" download>Download playback copy ↓</a>` : ""}</div>
      <details class="videoDetails"><summary>${externalOnly ? "Source record" : "Source and playback copy"}</summary><p>${escape(paper.citation)} · ${escape(item.source_filename || "")}</p>${available ? `<p>${item.conversion_note ? escape(item.conversion_note) : "Web playback uses an H.264 MP4 copy with all video frames in their original order. Sampling analysis continues to use the source file."}</p>` : ""}${externalOnly ? "" : "<p>" + escape(sourceTerms) + "</p>"}</details>`;
    const video = document.querySelector("#paperVideo");
    if (video && roi) bindRoi(video, item, datasetId, roi, memoryKey);
    document
      .querySelector("#videoStart")
      ?.addEventListener("click", (event) =>
        loadSeekableVideo(video, event.currentTarget, mediaPath(item.src)),
      );
    video?.addEventListener("error", () => {
      if (document.querySelector("#paperVideo") === video)
        document.querySelector("#videoError").hidden = false;
    });
  }
  document.addEventListener("change", (event) => {
    if (!active) return;
    if (event.target.id === "videoSelect") {
      active.selected = event.target.value;
      render();
    }
    if (event.target.id === "videoSpeed") {
      const video = document.querySelector("#paperVideo");
      if (video) video.playbackRate = Number(event.target.value);
    }
  });
  document.addEventListener(
    "toggle",
    (event) => {
      if (event.target.matches?.("details.samplingVideo") && !event.target.open)
        event.target.querySelector("video")?.pause();
    },
    true,
  );
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      pause();
      pauseSamplingVideo();
    }
  });
  document
    .querySelector("#detailDialog")
    ?.addEventListener("close", (event) => {
      // A queued close event can arrive after the next card has opened.
      if (!event.currentTarget.open) unmount();
    });
  const cardVideos = (paperId, datasetId) =>
    videosForDataset(
      window.CLOCK_VIDEO_CATALOG?.papers[paperId],
      paperId,
      datasetId,
    );
  const hasPlayback = (videos) => videos.some((video) => mediaPath(video.src));

  function cardLink(paperId, datasetId) {
    const videos = cardVideos(paperId, datasetId);
    if (hasPlayback(videos))
      return `<button class="cardVideoLink" data-watch-video="${escape(datasetId)}" aria-haspopup="dialog">▷ Video</button>`;
    const original = externalVideo(videos);
    return original
      ? link(original.source_url, originalLabel(original), "cardVideoLink")
      : "";
  }
  return Object.freeze({
    mount,
    onPane,
    unmount,
    cardLink,
    hasCardPlayback: (paperId, datasetId) =>
      hasPlayback(cardVideos(paperId, datasetId)),
    licenseLink,
    licenseCredit,
  });
})();

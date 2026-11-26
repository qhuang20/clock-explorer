// SPDX-License-Identifier: MIT
import { sourceFrameAtTime, validateRoiDocument } from "./video-roi.js";
import { drawRoi } from "./roi-drawing.js";
import { assetUrl } from "./assets.js";

async function bindCase(article) {
  const key = article.dataset.case;
  const { movie, inputHash, hours } = window.CLOCK_TUTORIAL_CASES[key];
  const video = article.querySelector("video");
  const svg = article.querySelector("svg");
  const toggle = article.querySelector(".roiToggle");
  const play = article.querySelector(".playToggle");
  const slider = article.querySelector("input[type=range]");
  const status = article.querySelector(".mediaStatus");
  const readout = article.querySelector(".frameTime");

  const plot = article.querySelector(".plotStage");
  plot.href = assetUrl(plot.getAttribute("href"));
  plot.querySelector("img").src = plot.href;

  const source = article.querySelector(".sourceMovieLink");
  if (!source.hasAttribute("href")) source.href = movie.source_url;
  source.hidden = false;
  if (movie.availability === "external_only" || !movie.src) {
    const title = document.createElement("h3");
    title.textContent = "Source movie";
    source.classList.add("videoShortcut");
    const note = document.createElement("span");
    note.textContent = "Linked for licensing reasons";
    const notice = document.createElement("div");
    notice.className = "videoSourceNotice";
    notice.append(source, note);
    video.closest("figure").replaceChildren(title, notice);
    return;
  }

  if (movie.reuse_license) {
    const license = article.querySelector(".videoLicense");
    license.href = movie.reuse_license.url;
    license.textContent = movie.reuse_license.label + " ↗";
    license.hidden = false;
    const attribution = article.querySelector(".videoAttribution");
    attribution.textContent = movie.reuse_license.credit;
    attribution.hidden = false;
  }
  video.closest(".movieStage").style.aspectRatio =
    movie.width + " / " + movie.height;
  if (movie.poster) video.poster = assetUrl(movie.poster);
  async function getAsset(url) {
    const response = await fetch(assetUrl(url));
    if (!response.ok) throw new Error("Tutorial media unavailable");
    return response;
  }

  try {
    const response = await getAsset(movie.sampling_rois[key]);
    const roi = validateRoiDocument(
      await response.json(),
      movie,
      key,
      inputHash,
    );
    const frames = new Map(roi.frames.map((frame) => [frame.index, frame]));
    svg.setAttribute("viewBox", `0 0 ${roi.width} ${roi.height}`);
    let previous = -1;
    function display(seconds, decodedFrame = false) {
      const index = sourceFrameAtTime(
        roi.frame_starts_s,
        seconds,
        decodedFrame,
      );
      if (index === previous) return;
      previous = index;
      slider.value = index;
      readout.textContent = `Frame ${index + 1} of ${movie.frames} · ${hours[index].toFixed(2)} h`;
      const frame = frames.get(index);
      svg.replaceChildren();
      if (frame?.bands.length) drawRoi(svg, frame, roi.direction_labels, key);
      svg.dataset.frameIndex = index;
    }

    toggle.addEventListener("change", () =>
      svg.toggleAttribute("hidden", !toggle.checked),
    );
    slider.max = movie.frames - 1;
    display(0);
    status.hidden = true;
    // A blob keeps repeated seeks accurate on local static servers without Range support.
    const blob = await (await getAsset(movie.src)).blob();
    const url = URL.createObjectURL(blob);
    video.addEventListener(
      "loadeddata",
      () => {
        slider.disabled = false;
        play.disabled = false;
      },
      { once: true },
    );
    video.addEventListener("error", () => {
      status.hidden = false;
      status.textContent = "This browser could not play the movie.";
    });
    video.src = url;
    video.preload = "auto";
    video.load();
    play.addEventListener("click", async () => {
      if (!video.paused) {
        video.pause();
        return;
      }
      try {
        await video.play();
      } catch {
        status.hidden = false;
        status.textContent = "Playback unavailable.";
      }
    });
    video.addEventListener("play", () => {
      play.textContent = "Pause";
    });
    video.addEventListener("pause", () => {
      play.textContent = "Play";
    });
    slider.addEventListener("input", () => {
      video.pause();
      video.currentTime = roi.frame_starts_s[Number(slider.value)] + 0.00001;
    });
    for (const event of ["seeked", "timeupdate", "ended"]) {
      video.addEventListener(event, () => display(video.currentTime));
    }
    if (video.requestVideoFrameCallback) {
      function tick(_, metadata) {
        display(metadata.mediaTime, true);
        video.requestVideoFrameCallback(tick);
      }
      video.requestVideoFrameCallback(tick);
    }
    window.addEventListener("pagehide", (event) => {
      if (!event.persisted) URL.revokeObjectURL(url);
    });
  } catch {
    status.hidden = false;
    status.textContent =
      "Video or sampling ROI unavailable. Open the source link or the sampling record.";
  }
}

for (const article of document.querySelectorAll("[data-case]"))
  bindCase(article);

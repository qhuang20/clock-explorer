// SPDX-License-Identifier: MIT
import { assetUrl } from "./assets.js";
import { validRange, displayColor, selectionData } from "./kymograph.js";
("use strict");
// Local source-range viewer. Never modifies saved analysis arrays or the comparison gallery.
window.ClockRangeExplorer = (() => {
  const cache = new Map(),
    pending = new Set(),
    selections = new Map(),
    initialized = new WeakSet();
  // Older generated source payloads may wrap display text in an English field.
  const displayText = (value) =>
    value && typeof value === "object" ? value.en || "" : value;
  const esc = (v) =>
    String(v ?? "").replace(
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
  const info = (id) => window.CLOCK_RANGE_INDEX?.[id];
  const fmt = (n) => Number(n).toFixed(2).replace(/\.00$/, "");
  function markup(id) {
    return info(id)
      ? `<section class="rangeExplorer" data-range-explorer="${esc(id)}"><p>Loading source range…</p></section>`
      : "";
  }
  function sourceFiles(id) {
    const paper = info(id)?.paper,
      files = (window.CLOCK_SOURCE_ARCHIVE?.files || []).filter(
        (x) => x.paper === paper,
      );
    const ready = files.filter((x) => x.status === "archived"),
      missing = files.filter((x) => x.status !== "archived");
    const scope = window.CLOCK_SOURCE_ARCHIVE?.scope_notes?.[paper];
    return `<details class="rangeSources"><summary>Source files · ${ready.length}</summary>${scope ? `<p>${esc(displayText(scope))}</p>` : ""}<ul>${ready.map((f) => `<li><a href="${esc(assetUrl(f.path))}" download>${esc(f.label)}</a><span>${fmt(f.bytes / 1048576)} MB${f.video_frames != null ? " · " + f.video_frames + " " + "frames" : ""}</span></li>`).join("")}</ul>${missing.length ? `<p>Some additional attachments remain unavailable: ${missing.map((f) => `<a href="${esc(f.url)}" target="_blank" rel="noopener noreferrer">${esc(f.label)}</a>`).join(" · ")}</p>` : ""}<a href="${esc(assetUrl("data/source-archive/audit.json"))}" download>Download source manifest and hashes ↓</a></details>`;
  }
  function receive(data) {
    for (const v of data.variants) {
      const b = atob(v.array_f32_le),
        u = new Uint8Array(b.length);
      for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i);
      v.values = new Float32Array(u.buffer);
      delete v.array_f32_le;
    }
    cache.set(data.id, data);
    pending.delete(data.id);
    document
      .querySelectorAll(`[data-range-explorer="${data.id}"]`)
      .forEach((el) => render(el, data));
  }
  function state(data) {
    let s = selections.get(data.id);
    if (!s) {
      s = {
        variant: data.variants[0].id,
        start: 0,
        end: data.variants[0].x.length - 1,
      };
      selections.set(data.id, s);
    }
    return s;
  }
  function render(el, data) {
    const s = state(data),
      v = data.variants.find((x) => x.id === s.variant) || data.variants[0];
    el.innerHTML = `<div class="rangeHeading"><h3>Explore the full source range</h3>${data.variants.length > 1 ? `<label>Dataset <select data-range-variant>${data.variants.map((v) => `<option value="${v.id}" ${s.variant === v.id ? "selected" : ""}>${esc(displayText(v.label))}</option>`).join("")}</select></label>` : ""}</div>
   <p class="rangeLimit">${esc(displayText(v.note))}</p>
   <form class="rangeControls"><button type="button" data-range-all>All available</button>${v.previous ? `<button type="button" data-range-previous>Earlier selection</button>` : ""}<label>From index<input data-range-start type="number" min="0" max="${v.x.length - 1}" step="1" value="${s.start}" required></label><label>To index<input data-range-end type="number" min="0" max="${v.x.length - 1}" step="1" value="${s.end}" required></label><button type="submit">Apply</button></form>
   <output class="rangeStatus" aria-live="polite"></output><canvas class="rangeCanvas" width="1200" height="490" role="img" aria-label="${esc(data.title + " " + "source-range kymograph")}"></canvas>
   <p class="rangeFoot">Indices start at 0. Colours use the complete selected dataset’s min–max; cropping does not rescale them. Gray = missing or masked.</p>
   <div class="methodDownloads"><a href="${esc(assetUrl(v.data_path))}" download>Full matrix ↓</a><button data-range-export>Export this selection ↓</button>${v.roi ? `<a href="${esc(assetUrl(v.roi))}" target="_blank" rel="noopener">Full-range ROI audit ↗</a>` : ""}</div>
   ${sourceFiles(data.id)}`;
    const update = () => {
      const a = Number(el.querySelector("[data-range-start]").value),
        b = Number(el.querySelector("[data-range-end]").value);
      if (!validRange(a, b, v.x.length)) {
        el.querySelector("output").textContent =
          "Use whole-number indices with start ≤ end.";
        return;
      }
      s.start = a;
      s.end = b;
      draw(el, data, v, s);
    };
    el.querySelector("form").addEventListener("submit", (e) => {
      e.preventDefault();
      update();
    });
    el.querySelector("[data-range-all]").addEventListener("click", () => {
      s.start = 0;
      s.end = v.x.length - 1;
      render(el, data);
    });
    el.querySelector("[data-range-previous]")?.addEventListener("click", () => {
      [s.start, s.end] = v.previous;
      render(el, data);
    });
    el.querySelector("select")?.addEventListener("change", (e) => {
      s.variant = e.target.value;
      s.start = 0;
      s.end = data.variants.find((x) => x.id === s.variant).x.length - 1;
      render(el, data);
    });
    el.querySelector("[data-range-export]").addEventListener("click", () =>
      exportSelection(data, v, s),
    );
    draw(el, data, v, s);
  }
  function draw(el, data, v, s) {
    const cv = el.querySelector("canvas"),
      ctx = cv.getContext("2d"),
      left = 106,
      top = 38,
      width = 912,
      height = 356,
      n = v.x.length,
      rows = v.shape[0];
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, 1200, 490);
    ctx.fillStyle = "#f1f3f6";
    ctx.fillRect(left, top, width, height);
    const a = s.start,
      b = s.end,
      span = v.x[b] - v.x[a],
      dx = span || (n > 1 ? v.x[1] - v.x[0] : 1),
      x0 = span ? v.x[a] : v.x[a] - dx / 2,
      x1 = span ? v.x[b] : v.x[b] + dx / 2;
    const tile = document.createElement("canvas");
    tile.width = b - a + 1;
    tile.height = rows;
    const tc = tile.getContext("2d"),
      im = tc.createImageData(tile.width, rows),
      low = v.normalization[0],
      high = v.normalization[1];
    let validFrames = 0;
    for (let j = a; j <= b; j++) {
      let valid = false;
      for (let i = 0; i < rows; i++) {
        const z = v.values[i * n + j],
          row = data.position_increases_up ? rows - 1 - i : i,
          k = (row * tile.width + j - a) * 4,
          c = displayColor(z, low, high, data.palette);
        if (Number.isFinite(z)) valid = true;
        im.data.set([...c, 255], k);
      }
      if (valid) validFrames++;
    }
    tc.putImageData(im, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.save();
    ctx.beginPath();
    ctx.rect(left, top, width, height);
    ctx.clip();
    for (let j = a; j <= b; j++) {
      const l = j ? (v.x[j - 1] + v.x[j]) / 2 : v.x[j] - (v.x[1] - v.x[0]) / 2;
      const r =
        j < n - 1
          ? (v.x[j] + v.x[j + 1]) / 2
          : v.x[j] + (v.x[j] - v.x[j - 1]) / 2;
      ctx.drawImage(
        tile,
        j - a,
        0,
        1,
        rows,
        left + ((l - x0) / (x1 - x0)) * width,
        top,
        ((r - l) / (x1 - x0)) * width + 0.3,
        height,
      );
    }
    ctx.restore();
    ctx.strokeStyle = "#9ca4b2";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(left, top);
    ctx.lineTo(left, top + height);
    ctx.lineTo(left + width, top + height);
    ctx.stroke();
    ctx.fillStyle = "#566276";
    ctx.font = "17px Arial";
    ctx.textAlign = "center";
    for (let k = 0; k <= 5; k++) {
      const x = left + (width * k) / 5;
      ctx.fillText(fmt(x0 + ((x1 - x0) * k) / 5), x, top + height + 30);
      ctx.beginPath();
      ctx.moveTo(x, top + height);
      ctx.lineTo(x, top + height + 7);
      ctx.stroke();
    }
    ctx.fillText(
      v.x_unit === "h" ? "Time (h)" : "Frame index",
      left + width / 2,
      top + height + 65,
    );
    ctx.textAlign = "right";
    const yTop = data.position_increases_up ? v.y[rows - 1] : v.y[0];
    const yBottom = data.position_increases_up ? v.y[0] : v.y[rows - 1];
    for (let k = 0; k <= 4; k++)
      ctx.fillText(
        fmt(yTop + ((yBottom - yTop) * k) / 4),
        left - 14,
        top + (height * k) / 4 + 6,
      );
    ctx.save();
    ctx.translate(27, top + height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillText(v.position_label || data.position_label, 0, 0);
    ctx.restore();
    for (let k = 0; k < 256; k++) {
      const c = data.palette[k];
      ctx.fillStyle = `rgb(${c.join(",")})`;
      ctx.fillRect(
        left + width + 31,
        top + (height * (255 - k)) / 256,
        22,
        height / 256 + 1,
      );
    }
    ctx.fillStyle = "#566276";
    ctx.textAlign = "left";
    for (const z of [0, 0.5, 1])
      ctx.fillText(String(z), left + width + 61, top + height * (1 - z) + 6);
    ctx.save();
    ctx.translate(1150, top + height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillText("Relative display value", 0, 0);
    ctx.restore();
    ctx.textAlign = "left";
    ctx.fillStyle = "#252936";
    ctx.font = "20px Arial";
    ctx.fillText(data.title, left, 25);
    const unit = v.unit === "frames" ? "frames" : "time points";
    el.querySelector("output").textContent =
      `Selected ${b - a + 1}/${n} ${unit} · indices ${a}–${b} · ${fmt(v.x[a])}–${fmt(v.x[b])} ${v.x_unit}${validFrames < b - a + 1 ? " · " + validFrames + " " + "with valid measurements" : ""}`;
  }
  function exportSelection(data, v, s) {
    const out = selectionData(data, v, s);
    const url = URL.createObjectURL(
        new Blob([JSON.stringify(out)], { type: "application/json" }),
      ),
      a = document.createElement("a");
    a.href = url;
    a.download = `${data.id}-${s.start}-${s.end}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function initialize() {
    document.querySelectorAll("[data-range-explorer]").forEach((el) => {
      if (initialized.has(el)) return;
      initialized.add(el);
      const id = el.dataset.rangeExplorer;
      if (cache.has(id)) {
        render(el, cache.get(id));
        return;
      }
      if (pending.has(id)) return;
      pending.add(id);
      const script = document.createElement("script");
      script.src = assetUrl(info(id).script);
      script.onerror = () => {
        pending.delete(id);
        el.innerHTML = `<p>Source data could not be loaded.</p>`;
      };
      document.head.append(script);
    });
  }
  new MutationObserver(initialize).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
  return { has: (id) => !!info(id), markup, receive };
})();

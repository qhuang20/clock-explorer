// SPDX-License-Identifier: MIT
import { t } from "./context.js";
import { $, esc } from "./dom.js";
export function sourceMethod(c) {
  const methods = {
    phase_figure: [
      t("Phase reconstruction"),
      t(
        "Each column represents a different fixed embryo in the authors’ phase order. The card legend identifies either published expression categories or stain values sampled from the figure.",
      ),
    ],
    matrix: [
      t("Author matrix"),
      t(
        "Read the author's position × time numerical table and redraw it in a consistent style. Values may already have been processed by the authors.",
      ),
    ],
    video: [
      t("Video extraction"),
      t(
        "Sample pixel intensities from a selected region in each experimental video frame to build a space–time plot. These are video display values, not raw fluorescence counts.",
      ),
    ],
    spots: [
      t("Binned spots"),
      t(
        "Sum measured transcription spot intensities within each spatial bin at each acquisition time.",
      ),
    ],
    tracks: [
      t("Binned tracks"),
      t(
        "Group author-provided cell tracks by spatial position and aggregate intensities at each time point to build a space–time plot.",
      ),
    ],
    video_lut: [
      t("Color reconstruction"),
      t(
        "Approximately recover color-scale values from a pseudocolor video to build a space–time plot. For qualitative comparison only; these are not raw fluorescence intensities.",
      ),
    ],
  };
  if (!methods[c.kind]) throw new Error("Unsupported source method: " + c.kind);
  return methods[c.kind];
}
export const kindLabel = (c) => sourceMethod(c)[0];
export function sourceBadge(c) {
  const label = kindLabel(c);
  return `<button type="button" class="sourcePill ${c.kind === "matrix" ? "numeric" : ""}" data-source-kind="${esc(c.kind)}" aria-label="${esc(t("{method}: show definition", { method: label }))}"><span>${esc(label)}</span></button>`;
}
export function calibrationNote(c) {
  return c.uncalibrated
    ? t("Time / length unverified")
    : c.position_unit && c.position_unit !== "µm"
      ? t("Length unverified")
      : "";
}

// One viewport-clamped tooltip avoids clipping inside rounded cards. Hover,
// keyboard focus and a touch/click toggle share the same translated definition.
let methodAnchor = null,
  methodPinned = false,
  methodHideTimer;
export function hideMethodHelp() {
  clearTimeout(methodHideTimer);
  if (methodAnchor) methodAnchor.removeAttribute("aria-describedby");
  const tip = $("#sourceMethodTooltip");
  if (tip) tip.hidden = true;
  methodAnchor = null;
  methodPinned = false;
}
export function showMethodHelp(button) {
  clearTimeout(methodHideTimer);
  if (methodAnchor === button && !$("#sourceMethodTooltip").hidden) return;
  hideMethodHelp();
  methodAnchor = button;
  const tip = $("#sourceMethodTooltip"),
    [label, description] = sourceMethod({ kind: button.dataset.sourceKind });
  tip.innerHTML = `<strong>${esc(label)}</strong><p>${esc(description)}</p>`;
  tip.hidden = false;
  button.setAttribute("aria-describedby", tip.id);
  positionMethodHelp();
}
export function positionMethodHelp() {
  if (!methodAnchor) return;
  const tip = $("#sourceMethodTooltip"),
    rect = methodAnchor.getBoundingClientRect(),
    box = tip.getBoundingClientRect();
  if (!methodAnchor.isConnected || rect.bottom < 0 || rect.top > innerHeight) {
    hideMethodHelp();
    return;
  }
  tip.style.left =
    Math.max(
      12,
      Math.min(rect.right - box.width, innerWidth - box.width - 12),
    ) + "px";
  tip.style.top =
    Math.max(
      12,
      rect.bottom + 8 + box.height <= innerHeight - 12
        ? rect.bottom + 8
        : rect.top - box.height - 8,
    ) + "px";
}
export function queueHideMethodHelp() {
  clearTimeout(methodHideTimer);
  if (methodPinned) return;
  methodHideTimer = setTimeout(() => {
    if (
      !methodAnchor?.matches(":hover, :focus") &&
      !$("#sourceMethodTooltip").matches(":hover")
    )
      hideMethodHelp();
  }, 120);
}
export function toggleMethodHelp(button) {
  if (methodAnchor === button && methodPinned) {
    hideMethodHelp();
    return;
  }
  showMethodHelp(button);
  methodPinned = true;
}
document.addEventListener("pointerover", (e) => {
  const b = e.target.closest("[data-source-kind]");
  if (b) showMethodHelp(b);
  else if (e.target.closest("#sourceMethodTooltip"))
    clearTimeout(methodHideTimer);
});
document.addEventListener("pointerout", (e) => {
  const b = e.target.closest("[data-source-kind],#sourceMethodTooltip");
  if (b && !b.contains(e.relatedTarget)) queueHideMethodHelp();
});
document.addEventListener("focusin", (e) => {
  const b = e.target.closest("[data-source-kind]");
  if (b) showMethodHelp(b);
});
document.addEventListener("focusout", (e) => {
  if (e.target.closest("[data-source-kind]")) {
    methodPinned = false;
    queueHideMethodHelp();
  }
});
document.addEventListener("pointerdown", (e) => {
  if (!e.target.closest("[data-source-kind],#sourceMethodTooltip"))
    hideMethodHelp();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && methodAnchor) {
    hideMethodHelp();
    e.stopPropagation();
  }
});
addEventListener("scroll", positionMethodHelp, {
  passive: true,
  capture: true,
});
addEventListener("resize", positionMethodHelp, { passive: true });

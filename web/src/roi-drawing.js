// SPDX-License-Identifier: MIT
import { roiPath, roiReferencePoints } from "./video-roi.js";

export function drawRoi(
  svg,
  frame,
  labels,
  markerId = "samplingRoiArrow",
  style,
) {
  const guideColor = style === "cell-tracks" ? "#57e1e8" : "#ffb45c";
  const bandColor = style === "cell-tracks" ? "#fa57dd" : "#ffb45c";
  const bands = (frame.bands || []).map((p) => roiPath(p, true)).join("");
  const lines = frame.lines || [];
  svg.innerHTML = `<defs><marker id="${markerId}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0L10,5L0,10" fill="#ffb45c"/></marker></defs>
    ${(frame.guide_lines || []).map((p) => `<path d="${roiPath(p)}" fill="none" stroke="${guideColor}" stroke-opacity=".85" stroke-dasharray="5 4" stroke-width="1.25" vector-effect="non-scaling-stroke"/>`).join("")}
    <path d="${bands}" fill="#ffb45c" fill-opacity="${lines.length ? ".12" : "0"}" fill-rule="evenodd" stroke="${bandColor}" stroke-width="${style === "cell-tracks" ? 1 : 2}" vector-effect="non-scaling-stroke"/>
    ${lines.map((p) => `<path d="${roiPath(p)}" fill="none" stroke="#ffb45c" stroke-width="1.5" vector-effect="non-scaling-stroke" marker-end="url(#${markerId})"/>`).join("")}
    ${(frame.reference_points || []).map((p) => `<circle cx="${p[0]}" cy="${p[1]}" r="4" fill="none" stroke="white" stroke-width="1.5" vector-effect="non-scaling-stroke"/>`).join("")}`;
  const points = roiReferencePoints(frame);
  if (labels?.length === 2 && points.length === 2) {
    const size = Number(svg.getAttribute("viewBox").split(" ")[2]) / 40;
    for (const [point, label] of [
      [points[0], labels[0]],
      [points[1], labels[1]],
    ]) {
      const el = document.createElementNS("http://www.w3.org/2000/svg", "text");
      el.setAttribute("x", point[0] + size / 2);
      el.setAttribute("y", Math.max(size, point[1] - size / 2));
      el.setAttribute("font-size", size);
      el.setAttribute("fill", "white");
      el.setAttribute("stroke", "#101115");
      el.setAttribute("stroke-width", size / 7);
      el.setAttribute("paint-order", "stroke");
      el.textContent = label;
      svg.append(el);
    }
  }
}

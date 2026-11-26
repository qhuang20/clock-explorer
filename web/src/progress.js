// SPDX-License-Identifier: MIT
export function redrawStatus(paper, datasets) {
  if (datasets.some((dataset) => (dataset.paper_id || dataset.id) === paper.id))
    return "redrawn";
  return paper.library_role === "reference" ? "reference" : "needs_data";
}
export function progressCounts(papers, datasets) {
  const counts = {
    total: papers.length,
    redrawn: 0,
    needs_data: 0,
    reference: 0,
  };
  for (const paper of papers) counts[redrawStatus(paper, datasets)]++;
  return counts;
}

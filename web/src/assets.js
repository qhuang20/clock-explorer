// SPDX-License-Identifier: MIT
/** Resolve optional research files without changing their recorded provenance. */
export function resolveAsset(path, missing = {}) {
  if (typeof path !== "string" || !path) return path;
  const split = path.search(/[?#]/);
  const key = split < 0 ? path : path.slice(0, split);
  return missing[key] || path;
}
export const assetUrl = (path) =>
  resolveAsset(path, window.CLOCK_MISSING_ASSETS || {});
window.ClockAssets = Object.freeze({ url: assetUrl });

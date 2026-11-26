// SPDX-License-Identifier: MIT
/** One signal movie for the selected kymograph; retain all archived inputs. */
export function isKymographSignalVideo(video) {
  return (
    video.playback_role !== "analysis_only" &&
    video.channel_type !== "brightfield" &&
    !/^(?:bright[\s-]*field|bf)$/i.test(video.reporter?.trim() || "")
  );
}
export function videosForDataset(paper, paperId, datasetId = paperId) {
  const videos = (paper?.videos || []).filter(isKymographSignalVideo);
  const selected = paper?.preferred_by_dataset?.[datasetId];
  if (Array.isArray(selected)) {
    return selected
      .map((id) => videos.find((video) => video.id === id))
      .filter(Boolean);
  }
  const preferred = videos.find((video) => video.id === selected);
  if (preferred) return [preferred];
  const matched = videos.find((video) =>
    video.source_dataset_ids?.includes(datasetId),
  );
  if (matched) return [matched];
  // A specific dataset never inherits an unrelated experiment's movie.
  if (datasetId !== paperId) return [];
  const legacy = videos.find(
    (video) => video.used_for_kymograph && !video.source_dataset_ids?.length,
  );
  if (legacy) return [legacy];
  // A matrix study's explicitly documented illustrative movie remains possible.
  const reference = videos.find((video) => video.id === paper?.default_video);
  return reference ? [reference] : [];
}

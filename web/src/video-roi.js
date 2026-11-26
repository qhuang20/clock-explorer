// SPDX-License-Identifier: MIT
/** Video ROI drawings use source-frame coordinates. */
export function samplingRoiForVideo(video, datasetId) {
  const diagram = video.sampling_roi_diagrams?.[datasetId];
  const path = diagram || video.sampling_rois?.[datasetId];
  if (
    /^data\/derived\/[a-z0-9-]+\/(?:[a-zA-Z0-9_-]+\/)*[a-zA-Z0-9_-]+\.json$/.test(
      path || "",
    )
  )
    return diagram ? { path, diagram: true } : { path };
  if (video.source_dataset_ids?.includes(datasetId) && video.roi)
    return { rect: video.roi };
  return null;
}

export function validateRoiDocument(data, video, datasetId, inputHash) {
  if (
    data?.schema_version !== 1 ||
    data.dataset_id !== datasetId ||
    data.video_id !== video.id ||
    data.source_sha256 !== video.source_sha256 ||
    data.playback_sha256 !== video.playback_sha256 ||
    (inputHash && data.geometry_input_sha256 !== inputHash) ||
    data.width !== video.width ||
    data.height !== video.height ||
    data.frame_starts_s?.length !== video.frames ||
    !Array.isArray(data.frames)
  )
    throw new Error("Sampling ROI does not match the selected movie/dataset");
  if (
    data.frame_starts_s.some(
      (t, i, all) => !Number.isFinite(t) || t < 0 || (i && t <= all[i - 1]),
    )
  )
    throw new Error("Invalid playback frame times");
  const indices = new Set();
  for (const frame of data.frames) {
    if (
      !Array.isArray(frame.bands) ||
      !Array.isArray(frame.lines || []) ||
      !Array.isArray(frame.guide_lines || []) ||
      (frame.reference_points !== undefined &&
        (!Array.isArray(frame.reference_points) ||
          frame.reference_points.length !== 2))
    )
      throw new Error("Invalid ROI footprint");
    if (
      !Number.isInteger(frame.index) ||
      frame.index < 0 ||
      frame.index >= video.frames ||
      indices.has(frame.index)
    )
      throw new Error("Invalid ROI frame index");
    indices.add(frame.index);
    for (const points of [
      ...(frame.bands || []),
      ...(frame.lines || []),
      ...(frame.guide_lines || []),
      ...(frame.reference_points ? [frame.reference_points] : []),
    ]) {
      if (
        !Array.isArray(points) ||
        points.length < 2 ||
        points.some(
          (p) =>
            !Array.isArray(p) ||
            p.length !== 2 ||
            p.some((x) => !Number.isFinite(x) || Math.abs(x) > 100000),
        )
      )
        throw new Error("Invalid ROI coordinates");
    }
  }
  return data;
}

export function sourceFrameAtTime(starts, seconds, decodedFrame = false) {
  if (!starts.length || !Number.isFinite(seconds) || seconds < 0) return 0;
  let low = 0,
    high = starts.length;
  while (low + 1 < high) {
    const mid = (low + high) >>> 1;
    if (starts[mid] <= seconds + 1e-7) low = mid;
    else high = mid;
  }
  // A decoded frame timestamp can be rounded by the browser. Snap it to its
  // nearest saved PTS. Ordinary playhead times still use the containing frame.
  if (
    decodedFrame &&
    high < starts.length &&
    Math.abs(starts[high] - seconds) < Math.abs(seconds - starts[low])
  ) {
    return high;
  }
  return low;
}

export function roiPath(points, close = false) {
  return points.length
    ? "M" + points.map((p) => p.join(",")).join("L") + (close ? "Z" : "")
    : "";
}

export function roiReferencePoints(frame) {
  if (frame.reference_points) return frame.reference_points;
  const line = frame.lines?.[0];
  return line?.length ? [line[0], line.at(-1)] : [];
}

export function rectangleRoi(rect) {
  const { x, y, width, height } = rect;
  if (
    ![x, y, width, height].every(Number.isFinite) ||
    width <= 0 ||
    height <= 0
  )
    throw new Error("Invalid fixed sampling ROI");
  return {
    bands: [
      [
        [x, y],
        [x + width, y],
        [x + width, y + height],
        [x, y + height],
      ],
    ],
    lines: [],
  };
}

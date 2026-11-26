// SPDX-License-Identifier: MIT
// Card summaries describe the plotted record, without guessing missing units.
export function datasetContext(record, paper) {
  return record.card_context || paper.kymograph?.card_context || {};
}

function number(value) {
  return Number(value.toFixed(2)).toString();
}
function span(values, unit) {
  return Array.isArray(values) &&
    values.length === 2 &&
    values.every(Number.isFinite)
    ? `${number(values[0])}–${number(values[1])} ${unit}`
    : "";
}
export function measurementFacts(
  record,
  coverage,
  t = (s, values = {}) =>
    s.replace(/\{(\w+)\}/g, (_, key) => values[key] ?? `{${key}}`),
) {
  const frames = coverage?.unit
    ? coverage.unit === "frames"
    : record.uncalibrated;
  const values = { used: coverage?.used, total: coverage?.total };
  const count = coverage
    ? coverage.mode === "subset"
      ? t("Subset {used}/{total}", values)
      : coverage.mode === "measured"
        ? t("Measured {used}/{total}", values)
        : `${coverage.used}/${coverage.total}`
    : record.shape_space_time?.[1]?.toString() || t("Unspecified");
  const time = record.uncalibrated
    ? ""
    : coverage?.duration_label || span(record.time_range_h, "h");
  const unit = record.position_unit || (record.uncalibrated ? "px" : "");
  const unitName =
    { px: t("px"), "video px": t("video px"), row: t("rows") }[unit] || unit;
  const space =
    span(
      coverage?.measured_space_range ||
        record.full_space_um ||
        record.spatial_range,
      unitName,
    ) || unitName;
  if (record.phase_ordered) {
    return [
      { label: t("Embryos"), value: count },
      { label: t("Order"), value: t("Expression phase") },
      { label: t("Position"), value: record.origin_short || space },
    ];
  }
  const physical = unit === "µm";
  return [
    { label: frames ? t("Frames") : t("Time points"), value: count },
    {
      label: t("Time"),
      value: time || t("Interval unverified"),
      unverified: !time,
    },
    {
      label: coverage?.measured_space_range ? t("Measured space") : t("Space"),
      value: physical
        ? `${record.spatial_scale_approximate ? "≈ " : ""}${space}`
        : [space, t("Scale unverified")].filter(Boolean).join(" · "),
      unverified: !physical || !!record.spatial_scale_approximate,
    },
  ];
}

export function sourceSelection(record, paper) {
  const context = datasetContext(record, paper);
  const values = [record.sample, context.sample].filter(Boolean);
  const parts = (value) =>
    value
      .toLowerCase()
      .split("·")
      .map((part) => part.trim().replace(/^(video|movie)\s*(\d+)$/, "$1 $2"));
  return values.filter(
    (value, i) =>
      !values.some(
        (other, j) =>
          i !== j &&
          parts(value).every((part) => parts(other).includes(part)) &&
          (parts(other).length > parts(value).length || j > i),
      ),
  );
}

// SPDX-License-Identifier: MIT
/** Pure numeric operations shared by the range viewer and tests. */
export function validRange(start, end, count) {
  return (
    Number.isInteger(start) &&
    Number.isInteger(end) &&
    start >= 0 &&
    end < count &&
    start <= end
  );
}

export function displayColor(value, low, high, palette) {
  if (!Number.isFinite(value)) return [241, 243, 246];
  const fraction = high > low ? (value - low) / (high - low) : 0;
  return palette[
    Math.max(
      0,
      Math.min(palette.length - 1, Math.round(fraction * (palette.length - 1))),
    )
  ];
}

export function selectionData(data, variant, range) {
  const count = variant.x.length;
  if (!validRange(range.start, range.end, count))
    throw new RangeError("Invalid inclusive range");
  const rows = [];
  for (let row = 0; row < variant.shape[0]; row++) {
    const values = [];
    for (let column = range.start; column <= range.end; column++) {
      const value = variant.values[row * count + column];
      values.push(Number.isFinite(value) ? value : null);
    }
    rows.push(values);
  }
  return {
    dataset: data.id,
    variant: variant.id,
    source_matrix_sha256: variant.source_sha256,
    source_matrix: variant.data_path,
    index_origin: 0,
    inclusive_range: [range.start, range.end],
    time_unit: variant.x_unit,
    time: variant.x.slice(range.start, range.end + 1),
    position: variant.y,
    intensity: rows,
    note: "Numeric values are float32 copies of the saved analysis matrix; null preserves missing data. No interpolation or re-normalization.",
  };
}

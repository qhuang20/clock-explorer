// SPDX-License-Identifier: MIT
// English UI messages with named-value interpolation.
export function formatText(message, values = {}) {
  if (typeof message !== "string") return message;
  return message.replace(/\{(\w+)\}/g, (match, name) =>
    Object.hasOwn(values, name) ? String(values[name]) : match,
  );
}

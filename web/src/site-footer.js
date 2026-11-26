// SPDX-License-Identifier: MIT
// Shared, offline-capable citation action for the app and Help pages.
export function initCitationCopy() {
  const timers = new WeakMap();
  document.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-copy-citation]");
    if (!button || button.disabled) return;
    const footer = button.closest("footer");
    const ready = button.querySelector(".citationCopyReady");
    const copied = button.querySelector(".citationCopyDone");
    const fallback = footer.querySelector("[data-citation-fallback]");
    clearTimeout(timers.get(button));
    ready.hidden = false;
    copied.hidden = true;
    fallback.hidden = true;
    button.disabled = true;
    try {
      await window.navigator.clipboard.writeText(button.dataset.citation);
      ready.hidden = true;
      copied.hidden = false;
      timers.set(
        button,
        setTimeout(() => {
          ready.hidden = false;
          copied.hidden = true;
        }, 2400),
      );
    } catch {
      // Clipboard permissions or file:// restrictions must not report success.
      // Keep the citation available for selection without downloading a file.
      fallback.hidden = false;
      const field = fallback.querySelector("textarea");
      field.focus();
      field.select();
    } finally {
      button.disabled = false;
    }
  });
}

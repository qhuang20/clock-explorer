// SPDX-License-Identifier: MIT
import { initCitationCopy } from "./site-footer.js";

initCitationCopy();

// Shared English navigation for the explorer and secondary pages, including file:// use.
(() => {
  "use strict";
  const isApp = document.body.dataset.page === "app";
  const isHelp = document.body.dataset.page === "help";
  const isTutorial = document.body.dataset.page === "tutorials";
  const tutorialLink = document.body.dataset.tutorials
    ? `<a class="nav ${isTutorial ? "active" : ""}" href="tutorials.html" ${isTutorial ? 'aria-current="page"' : ""}>Tutorials</a>`
    : "";
  const navItem = (section, label) =>
    isApp
      ? `<button id="${section}Nav" class="nav">${label}</button>`
      : `<a class="nav" href="index.html#view=${section}">${label}</a>`;
  const mount = document.querySelector("#siteHeader");
  mount.outerHTML = `<header class="topbar">
  <a class="brand" href="${isApp ? "#" : "index.html#view=library"}" aria-label="Return to the library"><span class="logo" aria-hidden="true"><img src="brand/icon.svg?v=clock" alt="" width="28" height="28"></span>Clock Explorer</a>
  <nav aria-label="Main navigation">${navItem("kymographs", "Kymographs")}${navItem("library", "Library")}${tutorialLink}<a id="helpLink" class="nav ${isHelp ? "active" : ""}" href="help.en.html" ${isHelp ? 'aria-current="page"' : isApp ? 'target="_blank" rel="noopener"' : ""}>Help${isApp ? " ↗" : ""}</a></nav>
 </header>`;
})();

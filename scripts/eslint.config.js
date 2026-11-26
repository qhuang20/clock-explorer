// SPDX-License-Identifier: MIT
export default [
  {
    files: ["web/src/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: Object.fromEntries(
        [
          "window",
          "document",
          "location",
          "localStorage",
          "setTimeout",
          "clearTimeout",
          "innerWidth",
          "innerHeight",
          "addEventListener",
          "URL",
          "URLSearchParams",
          "Blob",
          "Image",
          "fetch",
          "AbortController",
          "TextDecoder",
          "atob",
          "btoa",
          "requestAnimationFrame",
          "console",
          "MutationObserver",
        ].map((name) => [name, "readonly"]),
      ),
    },
    rules: {
      "no-undef": "error",
      "no-unreachable": "error",
      "no-dupe-args": "error",
      "no-dupe-keys": "error",
    },
  },
];

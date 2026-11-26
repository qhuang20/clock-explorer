# Optional research assets

This directory is ignored by Git except for this file. Local matrices, figures,
videos and source archives retain their original licensing terms.

- `npm run data:fetch` downloads the small core asset collection.
- `npm run data:fetch -- --group videos` adds playback copies.
- `npm run data:fetch -- --group sources --paper miao-2023 --dry-run` lists original source files before downloading.

The website can run without these downloads; it resolves missing files through
`catalog/assets.json`. SHA-256 validation prevents silent replacement of sources.
See [data provenance](../docs/data-provenance.md).

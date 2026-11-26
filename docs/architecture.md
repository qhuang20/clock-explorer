# Architecture

Clock Explorer is a static browser application. Node/esbuild bundles authored
JavaScript and CSS; Python standard-library scripts validate catalogue metadata,
assemble the site and manage optional assets. There is no production server,
account database or framework runtime.

## Browser modules

| Module                      | Responsibility                                               |
| --------------------------- | ------------------------------------------------------------ |
| `context.js`                | Current catalogue, language and UI state                     |
| `catalog.js`, `progress.js` | Paper/dataset relationships and progress classification      |
| `library.js`                | Search, filters, paper details, comparison and note exports  |
| `gallery.js`, `figures.js`  | Dataset cards, figure variants and sampling details          |
| `kymograph.js`              | Pure range selection, masking and display-color calculations |
| `range-explorer.js`         | Canvas rendering and range controls                          |
| `videos.js`                 | On-demand playback, speed, ROI and media cleanup             |
| `assets.js`                 | Local asset/source URL resolution                            |
| `text.js`, `site-header.js` | English message formatting and shared navigation             |
| `app.js`                    | Navigation, initialization and DOM event coordination        |

Modules import their dependencies explicitly. Small numeric/progress modules are
independent of the DOM and have regression tests. `window.Clock*` adapters remain
for the generated data scripts and optional player/range integrations; they are
not a promise of a stable third-party extension API.

## Authored and generated data

- `catalog/literature.json`: papers and evidence. No duplicated comparison records.
- `catalog/comparison.json`: datasets; several can refer to the same paper.
- `catalog/temporal-coverage.json`: used versus available frames/time points.
- `catalog/assets.json`: optional file sources, sizes, checksums and rights notes.
- `catalog/card-presentation.json`: reviewed target genes and concise experimental conditions for cards; source/sample IDs remain in scientific records and detail views.
- `assets/`: optional numeric/media files, ignored by Git.
- `dist/`: generated bundles, runtime catalogue and available asset copies.

`npm run build` merges metadata into browser data without modifying source files.
Missing optional files are mapped to recorded source URLs. Source archives remain
external in the website build even if present locally. A fresh clone can run
online without downloading gigabytes first.

Notes are stored per browser origin in localStorage. They are not sent to the
maintainer, synchronized across colleagues or translated automatically. Video
Blob URLs are released on switching or closing the player. The player loads only
the selected short movie, which allows seeking even on static hosts that return
whole-file responses for Range requests.

`video-roi.js` validates dataset/movie-bound sampling overlays and maps playback
PTS to native frame indices. `videos.js` loads geometry on demand, draws the saved
sampling footprint over the original video, and updates it with decoded-frame
callbacks plus seek/time events. ROI loads/callbacks are released with the player;
the toggle survives tab/language changes per dataset. Unmeasured source frames
show no ROI. `analysis/export_video_rois.py` exports these display-only JSONs
from saved scientific arrays without re-estimating the extraction geometry.

Card measurement summaries are formatted by `web/src/card-metadata.js` without
assuming missing acquisition intervals or physical pixel scales. Frames and
numerical time points remain distinct; measured subsets retain their coverage.
During the site build, `scripts/card_previews.py` creates card-only SVG copies
with duplicate reporter titles and method captions removed. Reviewed cards opt
into a shared physical axis box through `plot_layout` in the presentation
catalog. SVG group placement aligns main axes/colorbars and retains text size;
embedded images, scientific marks, tick values, units and masks are preserved.
Evidence-qualified A/P gutter letters are also opt-in per dataset; provisional
polarity retains question marks. A comparison preview declares its own orientation
and gets an annotated UI copy without replacing its original export.
For the reviewed A-above-P convention, opt-in `flip_y` reverses data marks and
moves y ticks together. Explicit data-axis lists keep time and colorbars upright
in multi-panel comparisons. Matrices, extraction origins and source ROI pixels
are unchanged; the generated catalogue records the display reversal.
Original figure assets stay intact. Missing local SVGs retain the existing source
fallback without claiming the generated layout.

The Masamizu and Lauschke detail views opt into a combined Data & sources panel through
`catalog/card-presentation.json`. `web/src/data-sources.js` places experimental
checks beside the corresponding Overview fields and file checks inside collapsed
records. Lauschke facts, movies and file subsets follow the selected dataset; other papers
retain their configured detail layout. The combined layout hides Notes without
deleting previously saved browser notes.

The Video 5 gallery primary is the reviewed wavefront-fit `intensity`; its
centroid reference is retained as a separate unchanged file and inside the
comparison NPZ. The plot renderer honors the selected Video 5 input/coordinate
in `catalog/comparison.json`. Its detail method can provide a
`reference_comparison` foldout using the same typography, imagery and links as
the primary walkthrough. Single-primary normalization and shared comparison
normalization are described separately.

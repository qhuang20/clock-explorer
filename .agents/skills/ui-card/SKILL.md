---
name: ui-card
description: >-
  Maintain Clock Explorer's kymograph card UI and the detail dialogs opened
  from those cards: metadata layout, plots, tabs, file links, field evidence and
  English text. Use for card-interface work in segmentation-kymograph-explorer,
  rather than site-wide navigation, branding, deployment or scientific extraction.
---

# ui-card

Use the checkout containing this skill. Start with its `AGENTS.md` and the
[shared ui-card guidelines](../../../docs/ui-card-guidelines.md). The guide is the shared
reference for people and agents; keep detailed design rules there rather than
copying them into this skill. Read architecture guidance when a card change
crosses component boundaries.

The scope is the card and its opened detail dialog. Site-wide headers,
navigation, homepage introductions and branding redesigns are separate work.

Keep the closed card and all opened detail tabs visually consistent; use the
shared guide's visual-consistency reference rather than giving each method its
own typography, spacing or control style. For aligned cards, follow the guide's
[plot geometry rules](../../../docs/ui-card-guidelines.md#plot-geometry-and-alignment):
match physical axis boxes while retaining each dataset's numerical limits and
units. For rows mixing short condition labels and full experimental facts, compare
the rendered heatmap and colorbar bounds, measurement rows and footer borders.
For a temperature series, check each sample’s time and space limits independently.
Keep the full author-matrix extent when displaying A above P, including any
measured margin beyond the posterior zero reference.

## Work within the requested rollout

Identify the paper, dataset, surface affected. A single-paper
trial does not authorize changing every card. Check the current presentation
configuration and user request for rollout scope rather than treating an older
example as permanent policy.

Masamizu 2006 is the initial reviewed example. Its field order, layout and tab
structure are an editable reference, not a fixed template for every future
version. Adapt them to the dataset and current requirements, preserving clear
scientific meaning and explicit uncertainty. Prefer evolving the presentation
configuration and shared components to copying a fixed card implementation.

Find the existing component and presentation configuration before adding
another representation. Preserve the distinction between reporter and target
gene, tissue and preparation, anatomical view and sampling coordinates, and
available files and claims supported by the paper. Missing acquisition or view
information stays explicitly unresolved.

## Show anatomical polarity with its evidence

Follow the guide's [A/P annotation rules](../../../docs/ui-card-guidelines.md#anatomical-direction-beside-the-vertical-axis).
Use the actual displayed direction for each plot, including comparisons. Keep
provisional `A?` / `P?` distinct from supported A/P, retain neutral image/pixel
coordinates when registration is unresolved, and do not relabel a radial center
as anatomical posterior without evidence. Neutral center/periphery plots can
share the same physical axis box without A/P letters. Approximate export scales
remain visibly approximate even when a numerical µm coordinate is available. A geometry handoff supplies polarity
and confidence; UI styling must not invent them. Do not withhold regional direction solely
because exact endpoints or center registration remain unresolved; explain that
scope beside the reviewed labels. A fixed AP pair must not imply time-resolved
marker identity across an early-to-late culture without supporting evidence. When a reviewer confirms a
case's direction, record that basis and update both plot labels and hover text,
removing superseded provisional question marks.

For supported AP plots, apply the reviewed A-above-P display preference. If a y
reversal is needed, move data, masks and y ticks together while keeping time,
text and colorbar orientation intact. Keep source ROI frames in their original
movie orientation. Follow the guide's display-reversal checks; changing only
the letters or applying a CSS flip to the whole figure is not sufficient.

## Keep media tied to the active kymograph

Give each independently measured target channel its own gallery card and default
kymograph. Two cards can link to the same multi-channel movie and specimen.
A shared signal such as HES7 / UNCX stays together when separate measurements
are unavailable. A folded channel comparison supplements the individual cards.

Show one reviewed signal movie for the active dataset, including when a paper
contains several samples, views or reporters. Hide brightfield-only playback;
retain structural analysis inputs and archived source records. Carry the dataset
selection through the detail tabs. Follow the shared guide
for current mappings and rollout; a paper-wide video dropdown is not the default.

For each video-derived card, expose **Show sampling ROI** in its
matching video. ROI is the finite-width sampling region; its centerline is the
sampling path. Reuse saved scientific geometry rather than drawing a cosmetic
line. Enable the overlay by default and bind it to the actual playback frame.
Use the [overlay guide](../../../docs/ui-card-guidelines.md#sampling-roi-overlay-in-the-video)
to check seeking, speed changes and source-pose jumps.

On primary replacement, synchronize previews, ranges, links, sampling text and
the hash-bound overlay. Keep reference markers separate from valid sample
endpoints. For radial cards with an extent guide, use the same saved validity
for the [solid band, dashed extension and missing heatmap region](../../../docs/ui-card-guidelines.md#radial-extent-and-missing-coverage).
Verify the browser loads the current ROI asset after drawing-only changes.

## Locate the implementation

- Cards and geometry: `web/src/gallery.js`, `web/src/card-metadata.js`,
  `web/styles/styles.css`; generated SVG placement: `scripts/card_previews.py`.
- Details and field/file verification: `web/src/library.js`,
  `web/src/data-sources.js`.
- Matching videos and figure views: `web/src/videos.js`,
  `web/src/video-selection.js`, `web/src/video-roi.js`, `web/src/figures.js`.
- Reviewed display facts: `catalog/card-presentation.json`; scientific records
  and evidence IDs: `catalog/literature.json` and related catalog files.
- English message formatting: `web/src/text.js`; generated output: `dist/`.

UI work does not change scientific arrays, ROIs, units, masks or extraction
methods. If a visual change would require doing so, separate that research task
and keep the unresolved UI label accurate.

## Finish with observable checks

Follow the repository's relevant checks and build instructions. Check changed
English views, a narrow layout, and any affected modal navigation,
foldouts or tooltips. For downloads, confirm that each label points to its
actual file, especially NPZ/JSON versus a source movie. Inspect the screenshot
itself before using it as evidence of the result. Report verification limits.

Report the selected paper/dataset/movie, not just a card ordinal. Use the shared
[review outcomes](../../../docs/kymograph-extraction.md#review-outcomes): a passed
layout/media check or an adopted primary is a UI result, while camera view,
anatomical registration and physical calibration retain their own evidence and
uncertainty. Do not relabel those scientific items as verified to close a UI task.

## Shared work and maintenance

When parallel work is authorized, assign ownership of shared renderers, CSS and
central catalog files before editing. A research handoff should include the
reviewed value, units, uncertainty and supporting source; a UI handoff should
include affected surfaces and validation. Coordinate integration instead of
having several agents rewrite the same files. This skill does not initiate
parallel work or deployment.

Any collaborator contributing to this repository can maintain the skill and
shared guide through the project's normal workflow. They are not tied to the
original author or chat. Follow the user's current design goals when evolving
a version; an earlier example does not block a requested redesign.

Maintain the same skill entrypoint and guide as the design evolves, using Git
history for versions rather than duplicating skills for each revision. Update
accepted guidance, implementation/configuration, English text and relevant
checks together. Update this entrypoint when routing or implementation locations
change. Keep rollout scope explicit and remove superseded guidance.

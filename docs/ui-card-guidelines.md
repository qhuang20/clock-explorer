# ui-card guidelines

Clock Explorer helps readers compare segmentation-clock kymographs across
species. Cards should make the biological context and limitations easy to read;
details should explain the sampling and provide usable files and sources.
This is the shared card UI reference for collaborators and agents. Its scope
is the gallery card and the detail dialog opened from it. Site-wide navigation,
headers, homepage introductions and branding redesigns are separate work. Read
[architecture](architecture.md) when a card change crosses component boundaries.

This guide records the current design baseline, not a permanent UI specification.
Collaborators can revise the layout, field selection/order, labels and tabs as
requirements evolve. Keep scientific meaning, provenance and uncertainty clear
while adapting the presentation. The user's current request and the checked-in
configuration determine the intended version and rollout scope.

## Lessons from the card and detail revisions

| Problem encountered                                        | Reusable decision                                                                                                                             |
| ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Reporter names were read as gene names.                    | Keep the reporter construct and reviewed target gene distinct. Do not parse a target gene from a construct name by guesswork.                 |
| Specimen shape was treated as a camera angle.              | Record tissue, preparation and view separately. A caudal embryo fragment and a spread mPSM culture differ in preparation as well as geometry. |
| Source-method badges also implied calibration status.      | The badge describes where the displayed values came from; time and length calibration belong with the axes and measurement summary.           |
| Data and Evidence repeatedly linked to the same article.   | Put experimental support beside its field and file verification beside its file. Name the link's destination or action.                       |
| Labels and method captions appeared in both card and plot. | Give each item a clear home; card-only plot copies can omit repeated titles while preserving scientific marks and original exports.           |
| Removing content left awkward spacing or broken controls.  | Check the resulting layout and optional controls, including dialogs without a Notes selector.                                                 |
| A screenshot crop omitted the card heading.                | Inspect the delivered screenshot, including its context and legibility; successful capture alone is insufficient.                             |

## Visual consistency between cards and details

Treat the gallery card and its opened detail dialog as one interface. Reuse the
same typography, heading hierarchy, spacing scale, muted labels, violet links and
controls, border treatment and orange-red experimental palette. A detail tab
should not introduce a separate visual style merely because it explains a
different extraction method. Keep scientific content and optional comparisons
specific to the active dataset.

For the current Masamizu 2006, Lauschke 2013 and Sonnen 2018 review, use the reviewed first-card
Figures view as the visual reference, including the numbered Sampling,
Extraction, Kymograph and Reading the plot hierarchy where those sections apply.
Check both the closed card and every affected detail tab when reviewing a change.
This reference remains revisable through the same project workflow.

## Current card-list conventions

- Admit a card to the main Kymographs gallery only when its measured signal has an explicitly identified target gene or set of genes. Structural stains such as SiR-actin can be reviewed locally.
- Set `hidden: true` in a dataset's presentation record to omit its card and
  same-paper navigation entry while retaining its scientific records and files.
  Lauschke Video 2 is currently hidden; Videos 1, 5 and 6 remain visible.
- Group datasets by species and order studies from older to newer within each
  group. In the main Mouse gallery, show cards with on-site playback first,
  keeping the chronological order within each set. One paper may supply
  several genuinely different datasets.
- Keep species visually prominent in orange-red and the paper citation muted.
  Keep card links and badges consistent with the existing violet accent.
- The card title identifies the reporter. Show a reviewed target gene separately,
  retaining appropriate gene-name italics and organism-specific naming.
- By default, show card-header metadata in two aligned columns above the plot.
  Put each field label on the left and its value on the right, on the same row.
  Select fields to suit the dataset and keep them in the order used by the
  first Mouse card (Masamizu 2006): Target gene, Tissue, Preparation, View,
  Temperature.
- Keep optional signal/channel notes in the detail view's **Signal note**
  field, rather than adding subtitles below selected reporter titles. Prefer the
  dataset's detailed `reporter_note`, with presentation `signal_note` as a fallback.
  Keep mixed-channel qualifications explicit there; do not reserve an empty
  subtitle line on sibling cards.
- The upper-right badge describes the source/extraction method. Its four current
  categories are author matrix, video extraction, binned tracks and video color
  reconstruction. Definitions in `web/src/tooltips.js` support hover, focus and
  click/touch on the label itself; omit a separate question-mark icon. Do not
  use this badge for calibration status.
- Center the complete plot, including axes and colorbar, with balanced space
  between context, plot and measurements. Check intrinsic SVG margins before
  adding CSS offsets. Use the configured shared axis box for reviewed rows,
  rather than forcing equal numerical ranges or cropping image elements.
- Keep frame counts or numerical time-point counts, elapsed time and spatial
  range/units below the plot. Report used/available coverage when known;
  distinguish a measured subset from a full acquisition and from biological n.
- Video playback seconds, exposure duration and acquisition interval are different
  quantities. A pixel coordinate is not automatically a physical length or an
  anatomical P-to-A distance.
- Experimental intensity uses light-to-dark orange-red for low-to-high values;
  simulations retain blue when present. Keep colorbar direction consistent,
  missing/masked values distinct and cyclic phase palettes meaningful. Avoid a
  comparison legend for data types absent from the current gallery.
- Keep the footer focused on Figure & sampling, a matching video when available,
  and Paper. Detailed file downloads belong in the detail view.

## Plot geometry and alignment

For reviewed cards, `plot_layout: "compact"` in
`catalog/card-presentation.json` opts into one physical canvas, main axis
rectangle and colorbar rectangle. Read the current configuration for the active
rollout; additional Lauschke and Sonnen cards now use the initial Masamizu plot
as their alignment reference. Keep each dataset's own tick values, coordinate
limits, units, normalization and missing-data display. Equal axis dimensions do
not imply equal biological scales or comparable absolute intensities.

`scripts/card_previews.py` positions the existing SVG axes in that shared card
viewport while preserving embedded image data and text size. Keep outside-axis
label gutters in physical points as well: shrinking a wide export's margins
while retaining its font size causes labels to overlap ticks and colorbars. Original research
figures and arrays stay unchanged. Both the closed card and its primary detail
plot use the generated preview; diagnostic comparisons retain their own layout.
For multi-reporter or multi-genotype matrices, open the selected specimen and
channel as one plot. Put paired figures and comparison movies in a closed
comparison disclosure. Verify the visible default figure against the gallery
preview and open each disclosure to check its specimen and movie.
A source fallback without a local SVG does not claim this alignment.

Let spare card height sit below the experimental facts, keeping plots,
measurement summaries and footers aligned. Check actual axis bounds, not only
image-element bounds: equal CSS image widths can hide different internal SVG
margins. Inspect wrapped facts, long labels and both languages at desktop and
narrow widths; do not hide scientific context to force alignment. Extend this
rollout through configuration when other cards are reviewed.

## View and preparation

Keep preparation (embryo explant or planar mPSM culture) separate from anatomical
camera view. Match a view to the actual source movie: Lauschke Video1 explicitly
uses a side view; Sonnen S1/Fig1A explicitly uses a dorsal view. Their tail-shaped
outlines do not make those views interchangeable. Culture-plane imaging describes
the planar culture presentation without assigning embryonic dorsal/ventral identity.

When only the broad imaging class is supported, it can be shown with an explicit
angle qualification, as in Masamizu Movie2's “Embryo imaging · angle unverified”.
Link the reviewed caption/method evidence in Overview. A/P polarity or a bright
bilateral pattern alone does not establish a dorsal, ventral or lateral view.

## Anatomical direction beside the vertical axis

Use small A / P letters in the existing left gutter near the vertical axis ends,
with A = anterior and P = posterior. Keep them separate from tick numerals and
the distance label, without moving the fixed axis box or adding a second scale.
Use the existing violet accent for supported polarity and the uncertainty color
with `A?` / `P?` for an explicitly reviewed provisional inference. Explain the
status in the image's hover description; keep the card concise.

Configure `axis_polarity` per dataset in `catalog/card-presentation.json`, with
`top`, `bottom`, `status`, an evidence-linked note and its translation. Inspect
the source coordinate direction first. The reviewed display preference is
**A above P** once polarity is supported. If the source puts P above A, opt into
`flip_y: true` and declare the resulting A/P order; do not merely swap letters. A diagnostic `method_figure.result_preview` opts in separately
through its own `axis_polarity`, since it may use a different orientation. A
shared-y comparison needs one pair beside its first axis. Card-only SVG copies
carry these annotations while original exports and numeric arrays stay intact.

Polarity and anatomical registration are different claims. A label at an end
means anteriorward/posteriorward, not a verified tissue boundary, arrest front or
exact author ROI. Unknown frame intervals or pixel scales remain unknown even
when orientation is supported. Omit A/P when there is no adequate evidence; a
radial center-to-periphery coordinate is not automatically P→A.

For Masamizu Movie 2, the reviewer confirmed upper=A and lower=P from the lower
pale triangular growth zone and posterior tail elongation. Display plain `A`
above `P`, including in the detail plot, and retain that review basis in the
presentation record and hover description. Remove superseded question marks
when a case's polarity is confirmed. Image-y/pixel coordinates, physical
calibration and framewise registration remain separate from this orientation
confirmation. The two reviewed Lauschke cards also show A above P: Video 5 maps
central posterior-side tissue toward the peripheral segmenting anterior side;
Video 1 follows its posterior-side reference toward anterior PSM. Their source
plots had zero at the top and are reversed for display. These are case-supported
polarity assignments, not anatomy defaults for arbitrary movies.

For a neutral coordinate, `coordinate_note` can describe the reviewed origin,
outward direction and unresolved anatomical correspondence in the same image
hover description. It does not create A/P gutter letters. Only show the note
for the actual generated preview, rather than claiming a source fallback has
received a display transformation.

### Reverse the plotted coordinate, not the screenshot

For a reviewed y reversal, move heatmap samples, their missing-data display,
spatial overlays and y tick positions together. Keep numerical tick values and
units attached to the same samples. Keep glyphs upright, time increasing to the
right and colorbars high-at-top. Do not use a CSS flip on the complete image or
change only the A/P letters. Origin stays the same: in the current Lauschke
P→A distance plots, zero is at the bottom and distance increases upward.

The SVG adapter handles the reviewed Matplotlib raster plots. Each multi-panel
comparison declares its data `plot_axes` explicitly; colorbar axes are excluded.
Card, primary detail plot and included reference comparisons follow the same
convention. Source ROI frames retain their movie orientation and pixel mapping;
explain the P→A sampling direction beside them instead of rotating source videos.
If a local SVG is absent and the app falls back to an original source figure,
do not describe that fallback as reversed or annotated. Only attach the display
polarity hover note to a generated preview; keep the readout's units independent
of optional display processing. Original matrices and original exports remain intact. Record display reversal
separately from a new extraction, registration, resampling or axis-origin change.

The reviewed convention is A above P for datasets with supported anatomical
polarity. Sonnen S2 has supported regional P→A orientation from the paper
and the same-specimen Fig. 1D match, while its center and exact endpoints remain
unregistered. Add A-above-P to S2 with this qualification. Video2 retains neutral
labels because its full interval combines stage dependence, missing same-specimen
anterior identity and late FOV-truncated sampling. Both standalone previews
already put zero below, so `flip_y` remains false. Review these examples before batch
extension; style preferences do not supply missing anatomical evidence.

A numerical µm vector does not certify an export scale. Use
`spatial_scale_approximate` to qualify an approximate conversion on the card and
keep the scale's basis/limitations in the method and source records. Local JSON,
NPZ and review-figure links must identify their actual format.

## Dataset-matched video and file presentation

A kymograph opens one corresponding signal movie. Resolve its reviewed
`preferred_by_dataset` / `source_dataset_ids` mapping; a paper-wide movie list
is not the selection scope. Marker-positive movies from a different sample or
reporter do not become choices for this kymograph merely because they belong to
the same paper. A separate dataset/view keeps its own source movie.

Hide brightfield-only movies from playback and the selected dataset's visible
movie entries. Retain the original catalog and structural files used for drift,
masking or other analysis. Signal movies that include a brightfield composite
remain eligible when they are the actual source. An author-matrix dataset can
retain an explicitly documented illustrative movie with its relation note.

The combined detail layout is currently enabled for Masamizu 2006 and Lauschke 2013. For papers with multiple datasets, retain the active dataset through
Overview, Figures, Video, Data & sources. Experimental
facts and downloadable matrices/records follow that dataset. Local numeric files
link to their actual NPZ/CSV/JSON; they are not labeled author matrices or linked
to source movies. Other papers keep their configured layout until included in a
requested rollout.

### Sampling ROI overlay in the video

Use **Sampling ROI** for the sampled region and **sampling path** for its centerline. A region can be a fixed rectangle, moving finite-width
straight/curved strip, or the saved projection footprint. Each video-derived
card must provide the matching **Show sampling ROI** checkbox in
its Video pane. Check it by default so the overlay appears on the video poster.
Keep it beside Speed with the existing accent and typography.
For Sonnen 2018 Movies S1–S3, the hosted player draws the synchronized ROI
beside the original movie. Loopback previews use the same geometry in the
on-video overlay, including when previewing the public build.

Display the actual saved region/width in original source xy coordinates. Show
curved band edges and its path, not just a chord or a first-frame screenshot.
Movement follows decoded playback-frame PTS, including seeking, speed changes,
pausing and source-pose jumps. Experimental hours are not playback seconds.
Source frames remain unflipped even when the kymograph uses A-above-P display.
Use neutral direction labels where anatomical polarity remains unresolved.

`analysis/export_video_rois.py` exports playback-only outlines from the current
matrix and saved geometry, with source/playback/input hashes and native frame
indices. `catalog/videos.json` maps `sampling_rois` by dataset; the Masamizu fixed
rectangle remains supported. Drawings show the geometric footprint, not every
rejected pixel or an exact anatomical boundary. Do not re-estimate centers or
modify scientific arrays just to add the overlay. New cards must hand off their
geometry when extraction is implemented.

For a measured subset, remove the overlay outside its source-frame range and
state that the frame was not used. Do not extrapolate the last ROI to the rest
of the movie. An illustrative movie for an author matrix/track dataset must not
borrow an unrelated extraction ROI. Clear pending loads/frame callbacks on
dataset changes or dialog close, and preserve the toggle during language/tab
changes. Check poster, mid/late frames, scrubbing, speed, replay and narrow layout.

When a replacement primary changes geometry, update its card/detail previews,
measurement ranges, file links, sampling text, range payload and video overlay
together. Bind the overlay to the active numeric input hash. When only the
drawing changes, refresh affected asset URLs or cache versions and update their
catalog mappings and checksums. An unchanged matrix hash cannot distinguish old
and new drawings from the same input. Remove superseded comparison UI when
requested.
For fixed-reference paths with unsupported extensions, draw the retained band
as solid and the reference extension as dashed. Store A/P reference positions
separately from valid measurement endpoints; a missing prefix must not make the
P label migrate onto the first retained sample. Both reference markers and bands
follow their saved source-frame mapping during seeking and playback.

### Radial extent and missing coverage

For a radial card with a reference extent beyond the measured band, derive
the static sampling board and video overlay from the same saved native-frame
path and validity used by the kymograph. Draw the solid band through the last
supported position for each frame. Label that position **E** and carry a
dashed guide outward to the dataset's saved distance limit. Render unsupported
distances as missing in the kymograph. The guide indicates a reference extent
even when the usable endpoint changes between frames.

Compare the last supported row and its source xy position with both drawings.
In local playback, check the first, middle and last source frames and seek
across them. Confirm the active asset has loaded and the dashed segment starts
at the solid endpoint. See the [Sonnen S2 and S3 case](../.agents/skills/kymograph-radial/references/sonnen-2018.md#current-selections)
for fixed-reference and tracked-center examples.

## Initial reference: Masamizu 2006

The following design was reviewed on the first card and is a useful starting
point. Check the current configuration for which cards use it. Change or extend
the reference when a newer design is requested; a one-card task still does not
imply a gallery-wide rollout.

The initial card uses aligned label/value rows above the plot in this order:

1. Target gene.
2. Tissue, including stage when known.
3. Preparation.
4. View.
5. Temperature.

Use explicit uncertainty: **Unverified** means not yet confirmed;
**Not reported** requires checking that the source does not report it;
**Not applicable** is appropriate only when the field has no relevant meaning.
Do not infer anatomical view from image orientation or label a geometric center
as a verified posterior/oscillation origin. Preserve the reviewed sources.

The detail tabs are Overview, Figures, a dataset-matched Video tab when available,
and Data & sources. The combined layout has no separate Evidence or Notes tab.

- **Overview:** Put specimen facts and their expandable supporting checks beside
  one another. Retain the paper section/figure and its link. An unresolved view
  remains unresolved without a manufactured supporting citation.
- **Figures:** Show the four numbered stages on the default view: Sampling,
  Extraction, Kymograph and Reading the plot. For author matrices, describe the
  specimen, input and spatial rows in Sampling. Reserve ROI overlays for
  datasets with a documented sampling geometry. Preserve the distinction between a local redraw and the paper's
  original figure.
- **Data & sources:** Put accessible source movies and local derived matrices
  first. Use labels such as Open original video, Download matrix (NPZ), Download
  processing record (JSON), View paper figure and View supplementary materials.
  Distinguish an unavailable author matrix/raw stack from a locally derived
  matrix. Do not label a movie URL as a matrix download.
- Keep verification records collapsed by default. Field and file records retain
  their evidence IDs; do not replace them with an additional repeated article
  list. Keep limitations, missing files and uncertain reuse terms available.
- Hiding Notes is a presentation change. Preserve existing browser notes unless
  the user asks to delete them, and handle the absent control safely.

The reviewed facts and opt-in detail layout live in
`catalog/card-presentation.json`. Scientific sources remain in the catalog;
`web/src/data-sources.js` renders their contextual placement. Avoid copying the
same facts into hardcoded HTML or a second source-of-truth record.

## Verification and collaboration

For the changed scope, run the relevant repository checks and build. Inspect
the English interface, desktop and narrow layouts, keyboard-accessible tabs and
foldouts, matching media, and affected file URLs. Do not invent checks or claim
browser validation when only markup was inspected. Keep temporary screenshots
out of the repository.

Name the paper, dataset and movie when reporting completed cards; gallery order
can change and a row can contain different papers. Report UI checks separately
from the [source/numerical/scientific review outcomes](kymograph-extraction.md#review-outcomes).
A user-approved primary can retain explicit registration or calibration limits.
Do not convert a scientific uncertainty to a verified label merely because its
card, overlay and downloads now agree. These distinctions belong in the existing
method/evidence records and progress reports; they do not require new UI badges.

When parallel work is authorized, give shared CSS/renderers and central catalog
files an integration owner. Research work can hand off verified metadata and
source IDs; UI work can integrate their presentation. Separate worktrees help
isolate concurrent edits, but shared conventions do not resolve file conflicts
or authorize unrelated changes. Follow the user's chosen Git workflow.

A detail-only processing pair may opt into `method_figure.result_preview` while
leaving the gallery's `full_preview`, input and root presentation unchanged.
Give that comparison its own orientation/axes configuration. Video5's new pair
uses the same four-stage walkthrough and retains its COM foldout; do not replace
the gallery primary just to expose a spatial filter. Verify the generated gallery
preview hash as well as the original matrix when that surface is promised unchanged.

For candidate ROI reviews, use `method_figure.review_comparisons` for the
dataset's ROI evidence and previous/candidate plots. These use the same foldout
style as `reference_comparison`, which can retain an existing spatial-filter
comparison. State which geometry is a candidate and whether its center or
registration remains unresolved. Comparisons use explicit origins and a shared
intensity scale; standalone review exports carry their own correct axis
orientation. A matched-support control can omit a repeated ROI board and show
only its note and plots. Adding a review does not select a new gallery input or replace
its playback ROI. Put candidate matrices, geometry and independent review
records in the active dataset's Data & sources with their actual formats.

## Maintaining future versions

Any repository collaborator can contribute updates to this guide and the
[ui-card skill](../.agents/skills/ui-card/SKILL.md) through the project's normal
workflow. Keep one maintained skill entrypoint and use Git history to track
versions. A new design does not need a separate frozen copy of the skill.

When a design changes, update the applicable presentation configuration, shared
components, English text, checks and accepted guidance together. Record the
reason and rollout scope with the change, and replace superseded instructions.
People and non-Codex tools can read this guide directly; agent tasks can cite the
same skill path. Masamizu remains an initial example, not a restriction on later
versions.

Regional direction, molecular identity over time and exact anatomical endpoints
are separate review outcomes. A supported coarse P→A direction may be annotated
without claiming a fitted pacemaker or precise A/P boundary. Keep the image
hover/readout explicit. Use same-specimen evidence where available; a movie
snapshot correspondence is not a marker-onset timestamp. Store new keyframes,
feature-match records and endpoint audits in Data & sources, retaining old audits
as history rather than rewriting their measured data.

## Include each relevant gene signal

Within an explicitly requested paper rollout, inventory the independent
marker-positive source movies. A nonoscillatory differentiation marker such as
Mesp2 still produces a meaningful intensity kymograph and is not excluded for
being a different reporter from the initial clock example. Give it its own
dataset, target gene, signal movie, numeric matrix and method record. Record
which requested signals are complete or still awaiting extraction; one redrawn
paper does not mean every signal in that paper is finished.

Lauschke Video 6 now has a separate Mesp2-GFP card alongside Video 5 LuVeLu.
The two channels share a specimen and reviewed sampling geometry, while retaining
independent signal arrays and normalization. Video 7 is the registered merged
view of those channels plus brightfield, so keep it as correspondence evidence
rather than count it as another independent gene measurement. Do not hide an
independent gene channel merely to simplify playback: dataset-matched playback
and completeness of the paper's signal inventory are separate concerns.

For a one-sided axial extraction, the midline guide and the sampled band have
different roles. Draw the saved seam as a guide and the actual finite-width ROI
as the sampling footprint. Identify the selected side in native image coordinates
in the method and video note. A previous/new comparison that changes width also
states both widths and keeps its own shared normalization. The gallery, detail
plot and video overlay select the same geometry hash after local adoption.

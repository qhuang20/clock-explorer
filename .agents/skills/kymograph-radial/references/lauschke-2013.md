# Lauschke 2013: geometry-aware kymograph reconstruction

Read when working on this paper, transferring an illustrated ROI into a movie,
or distinguishing an inferred center from an author's drawn starting point.
This is a worked example, not a universal parameter preset.

## Current selections

| Movie and dataset | Selected measurement | Implementation and limits |
| --- | --- | --- |
| Video 2 · `lauschke-2013-mpsm` | Independent early-wavefront fit, extended through the movie by brightfield translation. The illustrated author line is a comparison. | `analysis/reproduce_lauschke_views.py --only 2` rebuilds the reference. The [independent audit](#independent-video-2-review-2026-11-15) records mask reproducibility and the limits on full-interval A/P. |
| Video 5 · `lauschke-2013` | Wavefront fit seeded near the dark core, using the reviewed 45° ray. The centroid and spatial control are detail comparisons. | `analysis/fit_lauschke_video5.py` supplies the reviewed fit and `analysis/render_video5_primary.py` renders the selected result. The origin is geometric evidence, with biological source identity unresolved. |
| Video 6 · `lauschke-2013-mesp2` | Mesp2 display intensity on the paired Video 5 geometry, with its own matrix. | `analysis/extract_lauschke_mesp2.py` uses the red display channel. Same-frame correspondence supports geometry transfer, while subpixel alignment remains unresolved. |

## Biological and measurement context

[Lauschke et al., Nature 493, 101–105 (2013), DOI 10.1038/nature11804](https://www.nature.com/articles/nature11804)
uses different preparations:

| Reference                           | Preparation                                    | Spatial coordinate                                              |
| ----------------------------------- | ---------------------------------------------- | --------------------------------------------------------------- |
| Fig. 1b/c, Supplementary Video 1    | Posterior embryo fragment, side view           | Along anatomical P→A                                            |
| Fig. 1d/f, Supplementary Videos 2/3 | Tailbud-derived spreading quasi-monolayer mPSM | Center-side toward periphery                                    |
| Supplementary Videos 4–7            | Separate later segmentation-stage culture      | Review its own radial geometry; not the Fig. 1f source sequence |

The Fig. 1d arrow depicts a center-to-periphery sampling line. Its red square
belongs to the separate local intensity trace; it must not be used as the line
origin. The illustrated line does not supply an exact deposited coordinate ROI
or its full temporal trajectory. Center-side/peripheral coordinates are not a
license to label arbitrary image directions as anatomical P/A.

## Two separate reconstructions in Clock Explorer

**Independent wavefront fit:** fit approximately circular fronts across distinct
early times, estimate a shared curvature center, and extend its position with
matched brightfield translation. This is a geometric estimate, not validation of
a biological oscillator source or a reproduction of the drawn author line.
The reviewed fit used six times over 1.28–5.10 h; median arc residual 7.5 µm,
disjoint-time center difference 14.6 µm. These diagnostics are not statistical
confidence intervals. Center-estimation filters were not used for primary
sampled intensities.

**Illustrated-line reconstruction:** match Fig. 1d image features to the movie,
then map the approximate dashed-line tail and arrow direction. In this example:

- Publisher full image: 1417 × 1629 pixels. Fig. 1d first-panel crop:
  x=28, y=597, width=290, height=290 pixels.
- Approximate crop-local endpoints: tail (55,158), tip (107,−2).
  Graphic reading precision is about ±2 panel pixels; this is not biological
  uncertainty or an estimate derived from the feature residual.
- The panel labeled “0 min” matches source frame 85, zero-based, with burned-in
  video overlay 18.07 h. Later panels match frames 88,91,94,97 and overlays
  18.70,19.34,19.98,20.62 h. Do not redefine the movie clock from the inset labels.
- Reference affine transform, crop pixels to decoded movie pixels:

```text
[[2.5562229543181494, -0.0011255974601931155, 10.260472234727937],
 [0.0005978087213380594, 2.5544429678772462, 3.420565782413769]]
```

- 142 reference-frame inliers; median residual 0.31 decoded video pixels.
  Four other thumbnails independently confirm the mapping sequence.
- Mapped start at frame 85: (150.6749,407.0554) movie pixels. Direction −71.96°
  when image x points right and y points down. This differs from the independent
  wavefront fit; do not relabel the latter as the author's illustrated center.

In the paired extraction both lines use the same existing BF displacement,
relative to their respective anchors, and a fixed direction. This continuation
is a controlled assumption because the author trajectory is unavailable. A
literal fixed-image line is saved separately as a motion-assumption check.

Both use all 160 Video 2 frames, unchanged overlays 0–33.80 h,
100 µm / 111 decoded-pixel scale, a 20 px-wide transverse strip, the existing
tissue masks and the same width-validity threshold. The main pair uses original
decoded mean RGB display values without additional filtering. It requires at
least 75% valid transverse samples and retains the longest continuous valid
interval, allowing leading missing distances. Re-sampling the independent
reference with this rule reproduces its matrix exactly.

The illustrated path intersects tissue in 142/160 frames, first at 3.83 h.
An empty early column is missing sampling coverage, not absent expression.
Do not shift the origin onto bright tissue to recreate the look of Fig. 1f.
A separate Gaussian σ=9.66 µm spatial control does not filter along time.

## Existing implementation and artifacts

When this repository is available, locate it through the current project or
`segmentation-kymograph-explorer`; do not assume a fixed machine path.

- `analysis/reproduce_lauschke_views.py`: Video 1 AP and Video 2 reference extraction.
- `analysis/lauschke_wavefront_center.py`: independent wavefront-center estimate.
- `analysis/extract_lauschke_author_line.py`: illustrated-line transfer, common
  sampling rules, paired figures, original-matrix identity check and provenance.
- `tests/test_lauschke_author_line.py`: coordinate, motion, missing-prefix,
  true-zero, disconnected-island and registration-tampering checks.
- `assets/data/derived/lauschke-2013/video2-author-line-registration.json`:
  reviewed endpoints, affine transform, feature correspondences and source hash.
- `assets/data/derived/lauschke-2013/video2-author-line.npz`: paired arrays,
  coordinates, masks/counts, shared limits, spatial-filter and fixed-image controls.
- `assets/data/derived/lauschke-2013/video2-author-line-provenance.json`:
  source/script hashes, processing parameters and limitations.

The code and data are project resources, not bundled requirements of this skill.
A new movie needs its own calibration, masks, origin, motion validation and ROI
review. The skill does not claim to reproduce the paper's phase analysis,
cell tracking, deformation correction or exact published panel.

## Isolated reproduction of the illustrated-line pair

The current comparison needs the existing Video 2 reference matrix and BF
geometry as inputs. With the scientific environment active, run from the checkout
root and seed only those inputs plus the reviewed registration into a temporary
asset root. The adapter expects its figure output directory to exist, so create
both directories explicitly:

```sh
radial_review_root="$(mktemp -d)"
mkdir -p "$radial_review_root/data/derived/lauschke-2013" \
  "$radial_review_root/figures/lauschke-2013"
cp assets/data/derived/lauschke-2013/video2-kymograph.npz \
  assets/data/derived/lauschke-2013/video2-geometry.npz \
  assets/data/derived/lauschke-2013/video2-author-line-registration.json \
  "$radial_review_root/data/derived/lauschke-2013/"
CLOCK_ASSET_ROOT="$radial_review_root" python analysis/extract_lauschke_author_line.py \
  --source-dir assets/data/source-archive/lauschke-2013 \
  --registration "$radial_review_root/data/derived/lauschke-2013/video2-author-line-registration.json"
```

This comparison command decodes original Video 2; the copied geometry already
contains the previously estimated Video 3 BF masks and translation. It does not
re-estimate the wavefront center or replace the reference. The existing
`reproduce_lauschke_views.py --only 2` command independently rebuilds the
wavefront-fit reference and requires original Videos 1–3 plus timestamp audits;
see the [reproduction guide](../../../../docs/reproducing.md). Keep those two
operations distinct and use isolated roots for either review.

## Video 5 initial audit: keep the centroid proxy distinct

Video 5 is a separate segmentation-stage culture, paired with structural Video 4.
Its existing `radial-com-v1` matrix uses the binary-mask area centroid and a
manually selected image-space 45° strip. Neither is the Video 2 illustrated line
or a deposited author ROI. At that initial audit, P/A correspondence had not
yet been reviewed. The later regional-polarity review below supersedes that
presentation limitation for this segmentation-stage sample.

The initial review reproduces all 61 stored profiles and valid-width counts
exactly, preserving the input matrix. Raster-mask centroids differ from the
saved subpixel centers by at most 0.69 px. The finite strip ends around
290–293 µm; its 381 µm display grid includes masked distances beyond that.
These checks establish implementation consistency, not oscillation-center
validity or perpendicularity to the wavefronts.

An exploratory use of the existing Video 2 contour protocol found eight
candidate contours across five Video 5 frames, but did not establish the
required temporal center consensus. It has not been independently tuned or
validated for this specimen; failure does not demonstrate absence of radial
waves. At that stage, the displayed origin remained an explicit area-centroid proxy.
Inspect the candidate overlays before choosing a later fitting/manual method;
do not lower support requirements merely to produce a center.

Reproduce the read-only review with the scientific environment active:

```sh
python analysis/audit_lauschke_video5.py \
  --source-dir assets/data/source-archive/lauschke-2013 \
  --output-root work/lauschke-video5-review --probe-wavefronts
```

This command replays the earlier centroid-baseline audit, not the currently
selected wavefront-fit primary. It reads that saved geometry/intensity and writes
only review outputs to the requested root. Its signal-only overlays at0,5 and10h
show the centroid-reference strip and mask; `video5-roi-review.json` records its
origins, ends, preservation hashes, probe contours and limitations. Treat these
as historical review artifacts when reproducing this step. The selected
wavefront-fit handoff is described below. Brightfield remains an analysis input
while the matching card player shows Video5.

## Video 5 dark-core-guided wavefront comparison

The user subsequently identified the persistent dark core above the old area
centroid. This is a reviewed candidate region, not a reason to track the darkest
pixel or call it a biological pacemaker. The approximate source-frame-0 point
(369.8, 270.2) px screens contour-center candidates within 65 px. The common
center fit is unconstrained by that manual point or COM.

`analysis/fit_lauschke_video5.py` uses the existing circle-contour rules with the
actual green display channel and every consecutive frame in 0.5–9.5 h. The
previous Video 2 probe used a coarser frame stride and a mean display channel;
its failed consensus was not proof that this specimen lacked a shared center.
The revised protocol retains one contour per time, with 13 supported times over
1.67–9.17 h. In BF-registered source coordinates the shared center is about
(388.6, 294.4) px. The manual point is a regional hypothesis rather than the
final fitted position.

The two disjoint time groups differ by 2.1 µm; leaving one temporal contour
block out shifts the center by at most 3.3 µm. Geometry-filter alternatives at
14 and 20 µm shift it by at most 6.7 µm. The median common-circle radial
residual is 9.9 µm, so the model remains approximate. Consecutive temporally
filtered contours are correlated; these diagnostics are not confidence
intervals or biological replicate counts.
On the same held-out contour blocks, median absolute radial deviation from
the best per-contour radius is about 37.8 µm around the centroid reference and
9.9 µm around the fitted center. This is a geometry check on that selected
contour set, not a significance test or whole-tissue validation.

The main comparison retains the old 45° ray to isolate the origin/trajectory
choice. It crosses the supported contours with median local-normal error about
13°, so it is approximately radial rather than exactly perpendicular. The
35/55° sample controls remain in the NPZ. Do not select a new angle merely for a
cleaner heatmap. The fitted anchor is continued with the saved Video 4 BF
translation; the old reference retains its per-frame mask-centroid trajectory.
Outside the supported contour times this is a continuation assumption.

Both panels use all 61 Video 5 frames, the same original green values,
100 µm/105 px calibration, 20 px width (21 transverse samples), saved tissue
masks, first-exit/75%-valid-width rule and a common full-data color scale.
No extra filtering is applied to primary intensity samples. Equal radius does
not identify the same cells. The original centroid NPZ is reproduced exactly
and its hash is checked before and after the operation.

Reproduce from the scientific environment:

```sh
python analysis/fit_lauschke_video5.py \
  --source-dir assets/data/source-archive/lauschke-2013 \
  --output-root work/video5-wavefront-comparison
```

`video5-wavefront-comparison.npz` stores fitted `intensity`, unchanged
`centroid_intensity`, coordinates, both origin trajectories, validity counts,
shared color limits and angle controls. `video5-wavefront-center.json` saves
all candidate/selected contours, sensitivities, source and reference hashes,
processing and limitations. The three figure families show paired ROI overlays,
shared-scale kymographs and every selected contour with its common-center circle.
After user review, the fitted intensity is the Video 5 gallery/detail primary;
`comparison.json` selects `video5-wavefront-comparison.npz` and its `intensity`
key. The unchanged centroid matrix and shared-scale pair remain in the detail
foldout. The primary is normalized over its complete fitted matrix, while the
comparison uses a shared scale over both versions; the UI explains that
difference. No duplicate dataset/card is created. Regenerating comparison panels
must preserve this reviewed primary selection rather than revert to the older
centroid loader.

## Primary references

- [Publisher Figure 1 and caption](https://www.nature.com/articles/nature11804/figures/1).
- [Publisher article and supplementary information](https://www.nature.com/articles/nature11804).
- [ImageJ KymoResliceWide](https://imagej.net/plugins/kymoreslicewide) for the broader line-reslicing method family.

## Segmentation-stage Video 5 regional polarity and display convention

The polarity review uses the paper's Fig. 2a–f and main text: Wnt/FGF targets
are central, whereas Mesp2 activation and segment formation are peripheral.
Fig. 2f explains reorganization of embryonic AP into the central–peripheral
coordinate. The Video 5 caption identifies the same segmentation-stage specimen
as Videos 4, 6 and 7. This supports **central side = posterior, peripheral
segmenting side = anterior** for this preparation; it does not identify a fitted
circle center as an exact molecularly verified posterior landmark or pacemaker.

A local source review decoded all 61 frames of Videos 5, 6 and 7 (each 742 × 749
RGB), inspecting frames 0, 30 and 60 at the matching burned-in 0, 5 and 10 h.
The Mesp2 channel and merged view show peripheral differentiation around the
central region. Video hashes and the contact sheet are review outputs, while
source inputs and extraction arrays remain unchanged. The supplemental Mesp2
movie is evidence for this review, not an extra playback choice for the LuVeLu
card. The recorded source identifiers are L9 (Fig. 2 regional polarity), L6
(matched movie identity) and R5 (the fitted sampling geometry).

The UI shows A above P, with zero distance from the fitted center at the bottom
and larger outward distances above. Both centroid/fitted comparison panels use
that display convention, preserving all color values and missing measurements.
ROI frames retain their original pixel orientation and center-to-rim arrows.
Use regional-direction labels without claiming the measured endpoint is the
anatomical anterior boundary. In particular, the paper's early, incomplete mPSM
can be entirely posterior-like: central/peripheral geometry alone does not
justify applying this AP interpretation to Video 2 or another new sample.

Primary evidence: [Fig. 2 and main text, author-hosted paper](https://www.mcgill.ca/francois-group/files/francois-group/nature_2013_lauschke.pdf),
[publisher captions for Videos 4–7](https://www.nature.com/articles/nature11804#Sec12).

## Independent Video 2 review (2026-11-15)

Keep full-interval center/periphery coordinates. The main text (p. 103,
paragraph beginning “In principle”) describes incomplete mPSM before roughly
20 h as posterior-like throughout, lacking Mesp2/Aldh1a2 and segments. Fig. 2
supports regional polarity later, not a specimen-specific anterior onset in
Video 2. Do not draw a fixed AP axis across the whole 0–33.8 h series or impose
an exact 20 h switch.

`analysis/audit_lauschke_video2.py` independently reproduces all five primary,
illustrated-line and processing variants. Center, direction and BF translation
also match exactly. Rebuilt masks differ at 2,186/89,399,040 pixels (0.00245%);
both strips' values and width-validity counts remain exact. The cause of the
mask difference remains unresolved; reviewed saved masks remain primary.
This distinguishes extraction reproducibility from complete mask regeneration.

The original source is 751×744; playback pads one column on the right. ROI and
scale coordinates refer to the unpadded source. The new ROI-only sheet in
`figures/lauschke-2013/video2-review/` separates sampling from the primary plot.
Its standalone plot and new fit-left/illustrated-right comparison have zero
below already; do not reverse them again. Original matrices/exports remain
unchanged. See `data/derived/lauschke-2013/video2-review/video2-review.json`.

## Video 5 detail-only spatial control

The current gallery primary stays the unsmoothed wavefront-fit `intensity` in
`video5-wavefront-comparison.npz`; the COM reference and original exports remain
unchanged. The detail walkthrough adds an Unsmoothed / Spatial filter pair,
without changing the fitted center or reusing arrays from a different origin.

`analysis/compare_lauschke_video5_spatial.py` reproduces the current raw primary
exactly from green display channel 1, then applies a masked normalized Gaussian
inside each source frame's x/y grid before the same 45° / 20 px strip extraction.
The explicit first control is σ = 9.66 µm / (100/105 µm per px) = 10.143 source px,
not the 16.61 µm geometry-estimation filter or a universal best bandwidth. Keep
filtering for geometry, filtering for intensity and temporal processing separate.

Use `G(signal × valid)/G(valid)` with valid=saved analysis mask and finite data;
excluded pixels contribute zero weight, not zero-valued observations. This
prevents outside-mask background from bleeding into or darkening the control.
Normalized extension near a mask is only an intermediate interpolation surface;
the original tissue/FOV/width mask still determines measured positions. Neither
filtering nor shared axes can add measurements. Preserve the same 1,321 NaNs and
valid-width counts, 61 original times, saved origins/directions and 0–380.95 µm grid.
Both variants use the raw-primary min/max, not joint COM limits or independent
contrast stretching. No time smoothing, temporal baseline or phase is added.

The independent control files are under `video5-spatial-review/` in derived
records and figure folders. The new two-panel SVG already has zero below;
UI data axes 1–2 get A above P without another y flip, while colorbar axis 3 stays
upright. Root gallery configuration and its generated preview hash stay unchanged.
`tests/test_video5_spatial.py` checks mask normalization, bright exterior rejection,
green-only signal, true zeros, matching coverage and absence of time mixing.

## Video2 AP-scope review with fresh consecutive frames

Re-examining all160 signal frames and matched BF frames72–159 adds a specific
coverage limitation:98 measured endpoints lie at y16.56–17.59 source pixels,
near the existing15px exclusion. This persists from frame64/13.60h onward;
first occurrences are frames60–61. It is not a biological-stage threshold.
The late arrow terminates at a measurement/FOV cutoff, not a verified tissue
rim or anterior boundary. No clear segment boundary was established along
this sampled ray in the matched BF review.

Supplementary Fig6 independently verifies stage-dependent identity using6h
versus21h fixed cultures. It cannot supply an exact molecular-onset timestamp
for Video2. Mature central-posterior/peripheral-anterior orientation is supported
at preparation level, but same-specimen late anterior identity and the clipped
biological rim remain missing. Retain neutral center→outward coordinates for
the full series; do not infer AP solely from the geometric center or invent
an exact20h label switch. Imprecise origin alone is not the rejection criterion.
See `data/derived/lauschke-2013/ap-review/video2-ap-review.json` and the linked
signal/BF keyframes for the completed audit and explicit remaining observations.

## Video 6: an independent Mesp2 signal at the paired radius

The request to cover gene-positive movies includes the Mesp2 differentiation
marker; lack of sustained oscillations is not an exclusion criterion for an
intensity kymograph. Video 6 has its own dataset, not an alternate movie under
the LuVeLu card. Video 7 is the same-specimen red/green/brightfield composite,
used to check correspondence, not a new independent gene measurement.

The published Mesp2-GFP movie is red pseudo-colored: extract RGB index 0,
not index 1 inferred from the construct name. All 61 frames match Videos 5/7 in
native 749×742 geometry and playback timestamps; same-frame, label-excluded
high-pass comparisons to Video 7's red component peak at zero integer-pixel
shift throughout. This does not certify subpixel chromatic registration.

Use the reviewed Video 5 fitted center, saved BF translation, 45°/20 px strip,
100 µm/105 source px scale and existing masks. The masks are LuVeLu-support/BF
informed; check the Mesp2 ray's coverage and keep the field-of-view-only control
as a diagnostic. Do not call the mask a full segmentation of differentiated
Mesp2 tissue. This extraction transfers a geometric reference, not a Mesp2
pacemaker. Keep Mesp2 independently normalized from LuVeLu, preserve true zeros
and missing values, and show A above P in the annotated UI.

Reproduce into an isolated output root:

```sh
python analysis/extract_lauschke_mesp2.py \
  --source-dir assets/data/source-archive/lauschke-2013 \
  --output-root outputs/video6-mesp2-review/assets
```

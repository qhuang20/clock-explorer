# Axial kymograph extraction

Extract K(s,t) along a reviewed straight or curved anatomical axis. In the
current segmentation-clock case, s starts at a posterior-side landmark and grows
toward anterior PSM. Apply the shared [measurement and review requirements](kymograph-extraction.md).
This guide and `kymograph-axial` are the axial counterparts of the radial workflow.

## Establish the AP direction

Read the specimen/preparation description and source captions, then inspect the
movie. Use anatomical landmarks or documented labels to distinguish posterior
from anterior. The lower image edge, tail shape, brightest signal and direction
of apparent wave travel alone do not establish P/A identity.

When the evidence establishes only a posterior-side approximation, label it as
such. Record the P/A evidence, image coordinate convention and uncertainty.
Exact author-deposited ROIs and reconstructed landmarks remain different origins.
If direction remains ambiguous, retain neutral image-space coordinates or request
the consequential orientation information; do not assign P/A by guesswork.

## Review origin, direction and endpoint separately

For landmarks P(t), A(t), use u(t)=(A−P)/|A−P| and an explicitly reviewed origin,
usually P(t). Reject coincident points. Choose the strip's spatial endpoint or
maximum length independently; the anterior landmark may establish direction only.
Do not call the FOV boundary the anterior tissue boundary.

Review first, intermediate and last frames and additional keyframes around
rotation, drift, bending or specimen growth. A time-interpolated pair of manually
reviewed landmarks is a semi-manual moving ROI, not automated cell tracking.
Record the interpolation and restrict it to reviewed intervals; do not extrapolate
an early straight axis through later bending without inspection.

Choose whether the question uses a fixed physical ROI, a translated/rotated
anatomical ROI, or another explicitly supported reference. Preserve physical
distance, growth and actual elapsed time unless a separate normalized-coordinate
analysis is requested. Avoid treating tissue motion as phase-wave velocity.

If the anatomical path bends enough that a straight strip leaves the intended
PSM or crosses neighboring structures, limit the interval/region or use a reviewed
curved-path method. A curved centerline requires its own arc-length and normal
implementation; neither the straight axial nor radial sampler supplies that
behavior automatically.

## Extract and verify

Apply the common guide for calibration, finite-width sampling, original zeros,
NaN/FOV/tissue masks, signal identity and filtering controls. Define the endpoint,
width, validity threshold and channel estimator before comparing appearance.
Keep a mask covering only FOV/text distinct from one covering anatomical tissue.
Changing the mask to remove background is a scientific method change requiring
its own provenance and comparison.

Review a P/A-labeled overlay alongside the kymograph and numerical output. Check
that distance increases in the documented P→A direction, rotation of the displayed
movie does not change the sampled physical profile, and changing pixel calibration
changes coordinate conversion correctly. Retain the exact timestamp vector and
selected frame interval. Primary arrays and any reference promised unchanged must
remain unchanged while testing another method.

## Existing implementation and worked case

`analysis/reproduce_lauschke_views.py` preserves the earlier Lauschke Video 1
straight reference: reviewed landmark keyframes, interpolation over the first 61/126 frames,
20 px-wide sampling, the audited 0–10 h clock and 100 µm / 103 decoded-pixel scale.
It is a study-specific adapter, not a general automatic AP detector. The movie
combines LuVeLu with brightfield; its mean RGB is a display measurement.

Its anterior point defines direction, not the final sampled endpoint. The saved
451 × 61 grid extends to 450 µm subject to FOV/text validity. It has no anatomical
tissue mask, so finite background samples cannot be treated as tissue expression
or as proof of the biological tissue boundary. Its reviewed default detail
comparison now uses the same0–450 µm cap, retaining missing FOV extensions;
the old350 comparison is archived. A cap selected for display is not a measured
PSM length or an exact A endpoint. This earlier adapter does not validate later
curved frames. The current full-sequence adapter is described below.

## Reviewed curved-strip extension

`analysis/curved_strip.py` resamples a supplied smooth path by physical arc
length, builds local unit normals, and averages transverse samples. It does
not infer anatomy. Check that strip normals do not fold at tight turns and
that the complete band stays in the reviewed corridor, not just its centerline.
Keep measured distance instead of stretching every path onto a common normalized
length. A wider band is a separate sensitivity choice, not a substitute for
correct geometry. Preserve real zeros and missing coverage.

The earlier `analysis/extract_lauschke_video1_curved.py` analysis used all126
source frames, 0–20.92h, a 20px normal-width mean and 0–450µm
arc-length grid. Twelve manually reviewed structural keyframes follow the PSM-side
corridor; natural spatial cubics and time-PCHIP interpolation produce the paths.
The source pose jumps between frames100/101 (16.67/16.92h). Separate adjacent-frame
keys bracket it; do not interpolate an old pose through the displaced specimen.
These are approximate P-side references, not exact posterior endpoints or
material cell coordinates. FOV/text validity still is not anatomical segmentation.

The whole sequence uses the new method, including 0–10h; do not silently splice
old straight values to later curved values. Keep the earlier matrix unchanged and
compare the common interval with shared color limits. The optional spatial filter
acts independently per frame; no temporal baseline or phase inference is added.
New records/overlays live in `video1-full-curve/` below the Lauschke derived/figure
directories. Source-pose correction does not eliminate deformation or establish
wave speed. Review each new specimen's paths separately.

The [worked reference](../.agents/skills/kymograph-axial/references/lauschke-2013.md)
contains source requirements, audited landmarks, the isolated reproduction command
and these case limitations. The reproduction command currently verifies/decodes
Videos 1–3 even when `--only 1` is selected; obtain all three original inputs.

Related numerical checks are `tests/test_axial_geometry.py` for orientation,
rotation/calibration and motion invariance, and `tests/test_radial_geometry.py`
for shared strip filtering/timestamps. Follow the [reproduction guide](reproducing.md)
for the optional scientific environment. Do not copy this case's coordinates,
width or time window to another sample.

## Lessons to retain

- Establish anatomical direction from evidence, not from vertical/horizontal
  display orientation, brightness or wave-travel direction alone.
- A direction landmark and the biological ROI endpoint are separate decisions.
- Manual landmark interpolation corrects only the motion represented by those
  landmarks; it is not a recovered author ROI or a deformation/cell trajectory.
- Do not extend a validated early straight ROI into an unreviewed bent interval.
- A compressed composite display is not isolated reporter fluorescence, and an
  FOV-only validity mask is not a tissue segmentation.

Keep case evidence and general principles distinct as new axial datasets arrive.

## Dorsal right-side sampling (Sonnen Movie S1)

**Current selection.** Movie S1 · `sonnen-2018-embryo` uses the
[one-sided strip with fixed final-frame A/P references](#sonnen-s1--fixed-final-frame-p-reference).
Extract with `analysis/extract_sonnen_fixed_reference.py --only s1` and render
with `analysis/render_sonnen_half_and_extent.py --fixed --only s1`. Registration
remains sensitive to the structural window. The earlier corridors below are
review history.

The reviewer identified a clearer corridor on the image-right side toward the
anterior region in dorsal Movie S1. Thirteen manual keyframes guide the strip
along that corridor in native movie coordinates across all 88 frames. The
control retains the existing approximate 70 µm width, 300 µm distance and
original timestamps. Its new zero is the start of that corridor. Compare both
plots on a shared intensity scale, with distance measured from each strip's own
start. The full-width validity check covers the exported image and annotation
exclusions. The frame overlays document the visual tissue check.

Run `analysis/review_sonnen_s1_dorsal_right.py` in the scientific environment to
produce the detail comparison and review matrix. This case uses the reviewer
marked corridor and source-specific landmarks. Apply a fresh corridor review
for another dorsal movie.

## Fixed-reference geometry review and handoff (Video 1)

`analysis/review_video1_stable_roi.py` compares the earlier moving-P strip with
a fixed curve and a contour-guided curve after rigid stabilization. This is a
geometry review, without re-extracting intensities or changing the gallery.
These initial reviews preceded the selected primary described below; the
registration limitations remain relevant after that UI selection.
The optional environment extension is `analysis/requirements-tracking.txt`.

```sh
python analysis/review_video1_stable_roi.py
```

Outputs under `outputs/video1-stabilized-roi-review/` include the comparison
movie, a native-resolution candidate movie, keyframes, numeric geometry and a
parameter/quality report. Source hashes and the original primary's hash are
checked. SIFT/RANSAC selects structural feature correspondences; a separate
unit-scale rigid fit estimates translation/rotation only. Uniform scale in an
affine estimator must not absorb biological growth. Every frame maps to the
last source frame's reference coordinates, including the jump at100/101.

The candidate uses fixed prospective A/P reference endpoints, not a moving
anatomical posterior tip or the same cells. Its interior follows an inward
offset of the lower visible contour. The local-texture foreground proxy is
**not validated PSM segmentation**. COM is a point, not an anatomical centerline;
the whole tail's medial axis is not automatically the PSM sampling corridor.

Review all three alternatives. A completely fixed image/reference curve can
leave early tissue even when it fits the last frame. Show unsupported extensions
as dashed, with no reporter value assigned. Retain real growth, bending and
physical arc length; no length normalization or intensity smoothing is applied.
The finite-width band also needs a local-fold check and anatomical review.

This pilot remains unvalidated: registration depends substantially on the
structural window (about73px maximum disagreement at the prospective P reference
between the two tested cumulative registrations). Low feature-fit residuals
do not establish anatomical accuracy. Calibrate stable structural landmarks and
review the source-to-reference overlay before accepting a replacement kymograph.
The numerical safeguards are in `tests/test_video1_stable_roi.py`.

### Inward-placement comparison

Following the user's review that the first contour-guided strip hugged the
outer flank, `analysis/review_video1_inward_roi.py` reuses that exact saved
registration, mask and reference endpoints. It compares the previous path with
nominal20px and30px inward adjustments at the same20px strip width. The inward
direction is this specimen's reviewed P→A left-normal convention; do not assume
that convention applies to other paths or specimens.

```sh
python analysis/review_video1_inward_roi.py
```

The middle of the path is displaced along a spatially smoothed direction field
(40µm sigma); displacement tapers to zero over120µm at each fixed endpoint.
Only geometry is processed. Each new path is remeasured by physical arc length;
no reporter smoothing, intensity extraction or primary replacement is performed.
Outputs are in `outputs/video1-inward-roi-review/`. The two offsets are placement
candidates, not biological defaults or choices optimized for clean wave bands.

Following the contour does not require sampling immediately beside its edge.
Review the complete finite-width band inside the intended PSM corridor. Moving
toward the whole tail's center can enter neighboring structures, so a foreground
mask alone cannot certify the new location. Inward parallel offsets of sharp
local bends can also form cusps; check the recomputed strip for folds rather
than translating normals blindly. The current three variants have positive
local width Jacobians in all126 frames, but remain anatomical review candidates.

Fixed A/P reference coordinates do not establish stationary anatomical tips,
same-cell tracking, fixed physical arc length, or validated registration. Keep
those claims separate; the earlier structural-window sensitivity still applies.

### Selected inward30 extraction and current primary

The user selected the30px candidate first for comparison and then for the local
gallery primary on2026-11-16.
`analysis/extract_video1_inward30.py` reads that exact saved variant, keeps the
fixed reference endpoints and saved registration, and maps the geometry back
into native source pixels before sampling. It does not measure a resampled
stabilization movie. The saved2µm-spaced path is linearly interpolated onto a
1µm physical arc-length grid, without a new curve fit, extrapolation or length
normalization. Every exact A endpoint is checked separately for width support.

```sh
python analysis/extract_video1_inward30.py
```

The output directory is `outputs/video1-inward30-kymograph/`: a numeric matrix,
per-frame native/reference geometry, counts, validity, provenance and PNG/SVG/PDF
comparisons. All126 frames and the0–20.92h clock, including the100/101 gap, are
retained. `analysis/render_video1_primary.py` copies the reviewed matrix unchanged
to `data/derived/lauschke-2013/video1-fixed-reference/kymograph.npz` and renders
matching ROI/figure assets. The catalogue, range payload and hash-bound playback
overlay select that new file; the active UI removes older comparisons and links.
Historical analyses remain separate from the selected card. Both methods use20px transverse
mean RGB display intensity, without reporter smoothing or temporal filtering.

For this fixed-origin specimen, early P-reference intervals lie outside tissue.
The generic sampler's origin-connected default would discard the whole profile.
The new adapter explicitly requests `last_supported_run`, after independently
checking that the exact A endpoint is supported in every frame. It retains the
contiguous foreground-supported interval connected toward A, leaving the P-side
prefix missing. In several frames around4–7h an earlier supported island is
separated from that interval by insufficient coverage: exclude the island and
retain the gap instead of bridging it or moving the reference point. This is a
case-specific connectivity choice, not a replacement default for other methods.

Coverage is16/21 transverse points within the original FOV/text mask and the
unchanged display-derived foreground proxy. This does not certify anatomical
PSM identity. The old primary uses only FOV/text validity, so the main comparison
changes both geometry and coverage; the figure and provenance state this.
Additional comparisons isolate the inward shift with identical fixed references
and coverage, and compare the old/new paths under FOV-only validity. Full-array
shared color limits, common physical axes and A-above-P direction are used;
different origins do not identify matching cells at equal distance.

`tests/test_video1_inward30.py` checks missing prefixes, true zeros, separated
islands, inverse rigid mapping, distance and native-frame reproduction. Existing
origin-connected extraction behavior is preserved by default.

This remains the existing axial skill, not a new method class. The reusable
lessons are to distinguish fixed references from moving anatomy, review contour
offsets instead of hugging an edge automatically, preserve missing prefixes and
gaps with an explicitly checked anchor, sample original pixels through inverse
geometry, and update UI/overlays when a primary changes. Specimen parameters,
foreground assumptions and unresolved registration belong in the case record.

## Midline-split tracking (Sonnen Movie S1)

A dorsal bilateral preparation can resolve one side more clearly. Following the
reviewer's seam annotation, `analysis/review_sonnen_s1_half.py` marks nine seam
keyframes and tracks texture patches exclusively on the image-right side with
forward/backward Lucas–Kanade flow. Patch return error and displacement limits
reject unreliable matches. Accepted neighboring displacements supply local
interpolation when a station lacks texture. Endpoint correction constrains both
tracking directions to the reviewed keyframes, retaining growth and bending.
Save the remaining forward/backward geometry disagreement for review.

The selected curved corridor is offset 85 source pixels from this seam, with a
60 px transverse width (approximately 37 µm). Recompute physical arc length
and normal directions after placing the corridor. Every retained width sample
must lie on the selected side, inside the FOV/text mask and within a conservative
outer-envelope proxy. A row-filled envelope avoids treating dim internal waves
as tissue holes. Its threshold and anatomical coverage remain case assumptions.
Keep the longest connected supported run at its original distances, including
any missing prefix. The matrix contains unfiltered source display values.

The old/new comparison changes width, geometry and coverage together. Record
those changes with shared color limits and physical axes. The seam, full-width
band and every-frame review movie allow a reviewer to inspect tracking directly.
This moving-reference matrix preceded the fixed-reference primary and remains
a detail comparison. `analysis/render_sonnen_half_and_extent.py` renders the
saved values. The playback exporter binds the selected primary's geometry to
its matrix hash.

This extends the existing axial workflow. Keyframe-constrained geometry and
regional AP direction still require specimen-specific review. The optical-flow
patches provide structural motion estimates, with cell identity unresolved.

## Sonnen S1 · fixed final-frame P reference

Following the moving-half review, the user requested the final-frame posterior
reference convention used for Lauschke Video 1. The selected P reference is the
approved half-strip's frame87 posterior endpoint. Its registered coordinates are
fixed once. Anterior structural texture supplies unit-scale rigid registration,
with an independent shorter structural window recorded for sensitivity. These
fits exclude the posterior end so posterior extension remains visible relative
to the reference. The interior follows the approved seam-side corridor, with
smooth endpoint corrections and physical arc-length resampling.

`analysis/extract_sonnen_fixed_reference.py --only s1` saves the fixed P/A
references, inverse-mapped source markers, masks and geometry. It uses original
source pixels for the transverse mean. The missing early P-side interval is
retained. `analysis/render_sonnen_half_and_extent.py --fixed --only s1` renders
the earlier 36.6 µm matrix, and `analysis/review_sonnen_fixed_reference.py --only s1`
compares native and final-frame views. The preceding moving-P result remains
available in the detail comparison.

The current Movie S1 card uses `analysis/extract_sonnen_s1_wide.py` and the same registered centerline with a 70 µm-wide band. The primary shows all 88 frames with 5 µm Gaussian smoothing within each frame and along arc length. The fitted geometry and timestamps are shared with the unsmoothed strip mean. Both detail comparisons span all 88 frames (0–14.5 h) and show unsmoothed and spatially filtered intensities side by side. The full corridor covers 0–592 µm and the anterior zoom covers 275–540 µm. Both use the full-recording color scale and the same valid mask. The single Axin2T2A recording corresponds to Fig. 1A/B. Fig. 1C supplies the width precedent from a dual-reporter experiment.

Check reference round trips, unit-scale transforms, full-width support, local
strip folds and framewise source reproduction. Cumulative structural-window
sensitivity remains a measured registration limitation. Fixing the coordinates
alone establishes the chosen reference convention, with anatomical accuracy
requiring its own evidence.

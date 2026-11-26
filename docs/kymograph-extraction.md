# Kymograph extraction: axial and radial

Choose a spatial coordinate justified by the preparation, then sample the
sequence in that coordinate. These two project workflows share measurement and
review requirements, while keeping anatomical-axis and radial-center decisions
separate.

| Evidence and question                                    | Workflow                                           | Coordinate                                                               |
| -------------------------------------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------ |
| A reviewed anatomical AP axis or curved P-to-A corridor  | [Axial](kymograph-axial.md) · `kymograph-axial`    | Straight distance or physical arc length from a posterior-side reference |
| A supported center-side origin and outward radial fronts | [Radial](kymograph-radial.md) · `kymograph-radial` | Distance from the reviewed radial origin toward the periphery            |

Camera vertical/horizontal is not a method classification. A top view does not
prove radial biology. A strongly bent axis requires the explicitly reviewed
curved-strip adapter in the axial guide. Angular averaging, deforming material
coordinates and cell tracking remain additional methods; a moving curve does
not silently implement them.

## Calibration and revision

Both extraction skills are working methods under active calibration. Their current
routing, procedures and examples can change as new specimens, comparisons and
failure cases supply evidence. Validation on an existing case does not certify
all future inputs or freeze that case as the final method.

In each case distinguish observations verified on that input, provisional
assumptions and unresolved questions. When a finding changes a method decision,
record the evidence and practical consequence, update the relevant guide/case
and any affected implementation or meaningful checks, and replace superseded
guidance. Keep earlier outputs when useful for comparison and use Git history
for method revisions rather than creating duplicate skills for each version.

Promote a case lesson into shared guidance only when its scope is supported.
Keep specimen-specific coordinates, thresholds and limits in the worked case.
Start each case with the selected dataset and measurement, the relevant
analysis commands, and open questions. Identify earlier methods as history.
A better-supported result may revise a previous choice. Card design quality,
reference reproducibility and anatomical/calibration validity remain separate
assessments throughout that process.

## Method selection and extraction readiness

Use the preparation, anatomical evidence and observed front geometry to choose
one extraction route, then check the input/ROI requirements of that method.
Record the selected skill, the reason the other geometry is unsupported, the
current extraction state and the unresolved evidence. A chosen method is not
proof that its anatomical ROI has already been established.

Unverified time/length calibration permits explicitly qualitative frame/pixel
review. Unmapped P/A landmarks or an unvalidated center prevent an anatomical
registration claim, even if a fixed-strip heatmap can already be generated.
If geometry itself remains ambiguous, retain that uncertainty instead of forcing
a choice based on display orientation or how clean the heatmap looks.

The [Masamizu first-card case](../.agents/skills/kymograph-axial/references/masamizu-2006.md)
is an axial-route example whose existing fixed-image strip is verified but whose
anatomical registration and physical calibration remain unresolved.

## Review outcomes

Report completion against the question actually checked, rather than giving a
single unqualified “all good”. These outcomes can differ for the same dataset:

| Outcome                            | What the check establishes                                                                                | What it does not establish                                            |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Source correspondence and coverage | The selected movie, gene/channel, sample and interval match the record; checked source gaps are listed    | Every gene or experiment in the paper has been reconstructed          |
| UI integration                     | Card, details, downloads, range data and playback overlay use the selected input and agree                | Anatomical validity of that input or ROI                              |
| Numerical reproduction             | Values, coordinates and masks reproduce under the stated saved geometry and processing                    | Independent validation of the center, registration or tissue identity |
| Scientific support                 | Particular origin, view, polarity, calibration and motion claims have evidence for this specimen/interval | Other claims, specimens, time intervals or biological mechanisms      |

Name the paper, dataset and movie in handoffs; card ordinals can change and can
span several papers. State the material unresolved items beside the passed
checks. A user-selected primary can remain explicitly under calibration;
successful adoption and a good-looking plot do not settle the remaining anatomy.
These are reporting distinctions, not additional UI badges or blanket release
gates. Qualitative frame/pixel results remain useful when their limits are clear.

## Source and calibration

Identify the paper, preparation, specimen, exact movie, reporter/channel and
projection. Verify any matched structural channel is the same specimen and has
corresponding times. Prefer original image stacks. For display movies, identify
grayscale, mixed RGB, pseudocolor and display remapping. State what their values
measure; unverified color inversion cannot recover raw fluorescence or isolate
mixed reporters.

Use source hashes and keep a frame index tied to the actual experimental clock.
Audit burned-in timestamps if metadata are absent. Preserve irregular intervals,
gaps and explicitly selected time ranges. Playback seconds, nominal frame rates
and inset-relative labels do not establish experimental elapsed time. Do not
infer missing biological frames from a static image.

Use verified spatial calibration or a measured scale bar with its precision and
video resolution recorded. Account for unequal x/y pixel dimensions in physical
distances and geometric fits. When units are unknown, keep frame/pixel axes and
state the limitation rather than filling in typical values.

## Separate geometry from motion

An anatomical landmark, a wavefront-fit center, a geometric centroid and a drawn
arrow are different evidence. Keep origin selection, figure-to-movie registration
and inter-frame motion correction distinct. A small image-matching residual does
not make an approximately read arrow exact or verify an anatomical identity.

Prefer stable structural content for motion estimation when available. Choose
translation, rigid or affine motion according to the observed motion; justify
any more complex model. Review overlays at the first, reference, intermediate
and final frames, plus abrupt changes. Translation is not rotation/deformation
correction. A moving sampling strip does not track the same cells.

Separate feature-fit consistency from independent registration accuracy. Where
possible, check structural landmarks not used in fitting and compare plausible
structural windows, especially across cumulative drift and source-pose jumps.
Low inlier residuals or endpoints fixed by construction cannot resolve a large
disagreement between registrations. Keep the uncertainty explicit instead of
choosing the transform that makes cleaner waves. Do not let an unjustified scale
change absorb biological growth; model choice and tolerances are specimen-specific.

For figure transfer, exclude annotation text, insets, arrows and scale bars from
feature matching. Save the transform convention and its source/destination
frames, spatial distribution of matched features, inliers, residuals and checks
on independently identifiable movie frames. Transfer both endpoints or the full
path, not just an angle. Full temporal ROI motion cannot be recovered from a
single arrow without an additional assumption.

## Finite-width sampling

For these straight-strip modes, write a centerline as p(s,t)=o(t)+s·u(t) in
compatible units, with a unit direction and a separately specified length. The
axial guide supplies P/A evidence; the radial guide supplies center/outward
evidence. A second landmark defining a direction is not necessarily a sampling
endpoint. Review the requested strip extent explicitly.

Sample transverse offsets along the normal. State interpolation, strip width,
mean versus maximum, and minimum valid-width coverage. Interpolate signal values
and handle binary masks categorically. Keep filters used to estimate geometry
separate from the primary intensity extraction. Save additional spatial/time
filtering as named variants with units; paper pixel-space settings do not transfer
unchanged to differently sampled grids.

Keep true measured zeros. Tissue/FOV absence is missing data, represented by NaN
and an explicit or exactly reconstructible validity mask. Exclude movie text and
borders. Do not invent zero expression or bridge disconnected islands. Document
whether validity covers tissue, FOV only, or both. If a reviewed origin is outside
early growing tissue, keep its missing prefix rather than moving it onto signal.
The appropriate connected interval depends on the preparation. If selection
depends on a supported endpoint, check that anchor independently. Map reviewed
registered paths back to native source pixels for intensity sampling when
possible, avoiding an extra interpolation of the source images.

## Distance, averaging and per-frame smoothing

Keep these measurement choices separate when a request uses shorthand such as
“Distance / Averaging / Blurring or smoothing only on each frame”:

- **Distance:** state the origin, positive direction, reviewed endpoint and scale.
  Axial distance follows P→A; radial distance follows the supported origin toward
  the periphery. Image y or an uncalibrated pixel count is not automatically an
  anatomical or physical distance.
- **Averaging:** for a finite-width strip, average valid transverse samples at
  each fixed distance and time. Preserve the distance profile and frame sequence;
  averaging along the axis or over time is a different operation. An “unsmoothed”
  strip kymograph can therefore still include width averaging. A bare “averaging”
  note does not by itself specify which dimension to average.
- **Per-frame spatial smoothing:** filter x/y independently within each frame,
  then extract the strip. Record the filter, physical width and converted pixel
  width, boundary/mask handling and operation order. Do not mix neighboring times
  when following a per-frame-only instruction. Keep the unfiltered reference and
  use matched geometry, masks and display limits to inspect the effect.
- **Temporal processing:** temporal averaging, baseline estimation, detrending
  and time-axis filtering use measurements from other times. Subtracting a slow
  temporal baseline is still temporal processing, even if the input intensity
  was not temporally blurred. Label it as a separate derived variant with its
  time scale, edge support and sensitivity checks; it is not interchangeable
  with primary intensity or phase. Such analysis remains available when justified
  or requested, rather than being silently added to a spatial-only workflow.

For an ambiguous colleague note, distinguish the working interpretation from a
confirmed specification. These distinctions apply to both geometries; specimen
coordinates and filter widths still require case-specific evidence.

When an intensity filter excludes tissue-exterior or missing pixels, specify
how its weights are normalized. Video5's control uses per-frame normalized
masked convolution rather than treating excluded values as zero observations.
The filtered interpolation surface does not establish new tissue validity:
reapply and check the original measurement mask/counts, and retain the original
unfiltered reference and its color scale. A saved control at another origin is
not reusable merely because its array shape matches.

## Deliver an inspectable result

Use a consistent distance × time array orientation and save:

- Intensity matrix, physical time vector or explicit frame indices, and spatial
  distance vector with their actual units.
- Origin/direction trajectory or equivalent per-frame path coordinates, reference
  frame, strip width and valid-width counts/mask where available. A NaN mask is
  acceptable when it reconstructs validity exactly and the coverage rule is stated.
- Source identity/hashes, biological orientation evidence, acquisition/calibration
  audit, geometry and registration parameters, filtering, masking and limitations.
- Representative ROI overlays and a kymograph with matching axes; a separate
  controlled comparison when changing an existing method.

In current NPZ files, common keys are `intensity` (space × time), `time_h`,
`position_um`, `origins_xy` and `directions_xy`. Counts/masks and comparison
variants vary by adapter. Do not label an absent tissue mask as present or imply
that display values are isolated raw reporter fluorescence.

## Compare and accept

Begin paper-level reproduction with the
[source audit skill](../.agents/skills/kymograph-source-audit/SKILL.md): enumerate
main and supplementary panels, merge repeated views, and decide by available
**spatial** data. Reproduce a source-matched published panel; extract an available
gene movie that has no kymograph; skip missing inputs. A PDF of anterior time
traces and a rendered heatmap do not supply distance-by-time measurements.
The same reporter or preparation does not establish the same specimen/condition.

Keep each author's filtering/width parameters attached to the analysis they
describe. A spatial sigma in micrometres does not specify a temporal sigma in
hours, and a width specified for one figure family does not fill an omission for
another. A spatial-only control on a compressed movie is useful but cannot claim
raw projection, exact author processing or ROI recovery. Smooth appearance does
not settle a sampling-coordinate disagreement.

Preserve the existing reference unless replacement is requested. For an ROI or
filter comparison, hold timestamps, physical units, width, registration, validity
rules and estimator constant where possible. Document unavoidable differences.
Use shared axes and explicit shared color limits over both complete arrays.
Distance zero belongs to each origin; equal distance does not identify the same
cells. Do not normalize time or length merely to force visual agreement.

Check meaningful behavior: units, transform direction, P→A/outward orientation,
frame/channel correspondence, zeros, missing values and exact identity of a
promised preserved reference. Use synthetic signal/motion controls to exercise
changed sampling logic and original inputs to confirm an adapter still reproduces
its saved matrix. Inspect overlays as well as the heatmap. Appearance alone does
not validate geometry.

For candidate ROI comparisons, distinguish geometry changes from changes in
retained support. A rotated band needs a new full-width coverage review: the
original ray's distance cap can put its corners outside the visible culture.
Report a sector-specific conservative cap as an image-envelope proxy, and use a
matched-support control to isolate direction dependence when the candidate also
changes coverage. Keep dim interior values measured; a fluorescence threshold
does not establish an anatomical tissue mask.

Assess whether an alternative fit is itself well constrained before interpreting
its disagreement. An unstable registration window is a failed control, not a
calibrated anatomical error bar. Radial fits that change substantially between
angular sectors can be driven by the tissue envelope or persistent segment
boundaries; record that lack of center identifiability. A reproducible candidate
can remain a diagnostic while the current measurement is retained.

Freeze the numerical and geometry artifacts before the final independent check.
Bind its verdict to those file hashes; regenerating an archive or its provenance
requires updating that binding even when sampled arrays are unchanged.
State the scope of preservation checks: a before/after snapshot establishes
what a run left unchanged, while another candidate may later receive an
authorized revision. Keep the snapshot historical and recheck the revised
candidate, rather than making a peer's old artifact hashes a permanent test
requirement.

Use `CLOCK_ASSET_ROOT` with an isolated review directory when re-running adapters.
Confirm their input needs first: some adapters read earlier numeric/geometry
artifacts from that same root. Examples and limitations are in each worked case.
Never regenerate the working scientific assets just to validate a skill edit.

## Lessons from the five-card review

- Match anatomical identity to the measured specimen and interval. Lauschke
  Video 5 segmentation-stage polarity does not establish anterior identity in
  early Video 2. Approximate culture age is not a measured marker-onset time.
- Separate exact extraction with saved geometry from regeneration of geometry.
  In Video 2, regenerated masks differ at 0.00245% of pixels while both sampled
  matrices/counts match exactly. Report both results; retain reviewed masks
  rather than claiming bitwise mask reproduction.
- An exported movie's scale bar and clock take precedence over blindly applying
  camera metadata. Retain reading precision, approximate/axis-specific scale,
  irregular timestamps and source dimensions separately from playback padding.
- A structural feature, ROI start, wavefront-fitted center and anatomical
  landmark are different objects. FOV-valid samples are not proof of tissue
  validity. Sonnen S2 reproduces its exploratory strip but does not validate its
  center or supply an absent tissue mask.

## Repository responsibilities

Analysis stays in `analysis/`; numerical tests stay in `tests/`. The two skills
route to these implementations and method guides, without duplicate numerical
code in skill folders. Case-specific coordinates and thresholds belong in worked
references and extraction records. New inputs need fresh geometry review.

Supply the UI workflow with reviewed values, units, coverage, source,
coordinate meaning, uncertainties and artifact links. Include supported
regional polarity and the direction in which numeric distance increases.
The [UI guide](ui-card-guidelines.md#anatomical-direction-beside-the-vertical-axis)
defines the A-above-P display convention and source-frame orientation.
Use the saved geometry and validity for the [sampling overlays](ui-card-guidelines.md#sampling-roi-overlay-in-the-video).

## Regional-direction reassessment

Assess three questions independently: anatomical direction, time-resolved
molecular identity and exact sampling-landmark registration. S2's Fig1D match
supports regional P→A despite an unvalidated center; its late segment-posterior
stripe does not reverse the whole culture. Video2's geometric fit, meanwhile,
does not identify anterior tissue at its FOV-limited end. A culture-stage marker
time from other specimens is not a movie-specific onset threshold. New evidence
should revise an earlier blanket AP omission when justified, while preserving
remaining limitations and original numeric measurements.

## Paired gene channels and published display colors

A reporter's fluorophore name does not determine the RGB channel in a published
movie. Lauschke Video 6 is Mesp2-GFP, but its released movie displays Mesp2 in red.
Select the observed red display channel explicitly, not green by the GFP name.
Preserve the distinction between a fluorescence reporter, its target gene and
compressed/pseudo-colored display values.

For matched reporters from one specimen, a center estimated in an oscillatory
channel can define a shared spatial reference for a nonoscillatory marker.
Check frame dimensions, timestamps and same-frame features in the merged movie
before transferring geometry. Do not fit an artificial oscillation center to a
differentiation marker. Check peripheral coverage before inheriting a
reporter-informed tissue mask, and retain its limitations. Shared geometry does
not establish comparable brightness, a shared normalization or cell tracking.

The Video 6 adapter is `analysis/extract_lauschke_mesp2.py`; its source hashes,
red-channel correspondence, inherited geometry and full-frame ROI evidence are
saved with the matrix. It adds no temporal filtering, phase or cell tracking.

For the Mesp2 detail-only control, reuse the normalized masked per-frame Gaussian
with **explicit red channel index 0**. The shared function keeps green index 1
as its Video 5 default. `analysis/compare_lauschke_mesp2_spatial.py` reproduces
the raw Video 6 primary before computing the control. Both panels use the
original full Mesp2 min/max, not the LuVeLu limits or a new contrast stretch.
The working sigma is 9.66 µm (10.143 source px), matching the paired LuVeLu
control; it is not an optimized Mesp2 bandwidth. Preserve all 61 times and
1,321 missing values. The standalone comparison already puts zero below, so
its UI annotation must not apply the gallery primary's y reversal again.

## Final-frame reference for a growth view

**Identify the changing end.** Establish A/P from anatomy. In early, middle and
late frames, compare both tissue boundaries against a recognizable interior
landmark after correcting for specimen pose. If the posterior boundary advances
relative to the landmark, inspect P-side coverage. If the anterior boundary
advances, inspect A-side coverage. If both move, retain both measured boundaries.
If bending, field clipping or landmark loss prevents a clear assignment, report
the change in coverage and leave the growth side unresolved. Keep the display
convention (A above P) independent of this decision.

**For a fixed-length axial growth view**, choose a reviewed frame showing the
completed span, usually the last frame. Save its A and P coordinates, full curve
and calibrated arc length L. Use the same physical grid from 0 to L in every
kymograph column. Map the reference into each native frame using the saved
registration, preserving longitudinal distances. A constant image height, a
fixed plot limit or two fixed endpoints alone cannot establish constant curved
length.

**Verify the overlay against the matrix.** Draw the full-width supported interval
as a solid strip and each unsupported reference interval as a dashed guide. Keep
the corresponding bins missing, including gaps or loss at either end. From the
exported geometry, check that the solid and dashed centerline segments meet at
the mask boundaries, reach the saved A/P endpoints and sum to L within the
recorded discretization tolerance in every frame. Check the same frames in the
video player with the ROI enabled. An off-screen endpoint retains its reference
coordinate.

For example, the Rohde 2024 Position 2 axial card uses the last traced axis
(518.8 µm). Its P-side guide occupies about 226 µm in frame 0 and 11 µm in
frame 299, including the posterior sampling inset. Those lengths describe
sampling coverage. The PSM4 cell-track card from the same embryo uses a separate
measurement.

A moving contour or midline can still guide the interior sampling path. Taper
endpoint corrections over a reviewed distance and check the full-width strip for
local folds. Recompute physical arc length after geometry changes. Abruptly
adding or removing curve control points at a fixed endpoint can introduce jumps.
P and A reference selection, valid endpoints and display orientation need their
own saved fields and labels.

An inner radial reference may already be fixed by saved translation correction.
Express that point in the final frame and verify its registered trajectory.
Spreading can then appear at the outer edge while the center remains covered.
Missing coverage also depends on finite-width/FOV support and mask assumptions,
so its boundary needs a geometry review before interpretation as growth.

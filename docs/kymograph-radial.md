# Radial kymograph extraction

This method extracts K(r,t): signal along a finite-width center-to-periphery
strip, measured over time. It is intended for a preparation whose observed
wavefronts support radial sampling. This guide is shared by collaborators and
the repository's `kymograph-radial` skill. Apply the common
[measurement and review requirements](kymograph-extraction.md), shared with
[axial extraction](kymograph-axial.md).

## Geometry and anatomical meaning

Identify specimen, preparation, reporter/channel, imaging projection and the
source sequence from methods, captions and frames. Camera orientation is a clue,
not the sampling coordinate. In Lauschke 2013, the embryo-fragment AP view and
spreading mPSM culture are different preparations, not simply camera rotations.

Use center→periphery coordinates for supported radial geometry. Translate these
to posterior→anterior only when the study or anatomical markers establish that
relationship. Image vertical, a round silhouette and a bright central patch do
not establish an anatomical axis. If the preparation instead requires a straight
AP axis or a curved centerline, use the corresponding extraction method.

This workflow samples one radial strip. Averaging an entire ring, comparing
sectors or unwrapping a polar image changes the measurement and requires a
separate choice and implementation. An apparently circular wave does not imply
a specialized pacemaker population or physical transport from its center.

## Establish the origin and direction

Choose according to the scientific question and available evidence:

| Origin evidence           | Appropriate use                                      | Required distinction                                                                                |
| ------------------------- | ---------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Deposited author ROI      | Reproduce a documented sampling path                 | Respect its coordinates and temporal trajectory                                                     |
| Illustrated author line   | Reconstruct a depicted path in the matching movie    | Approximate drawing, not exact deposited ROI                                                        |
| Multi-frame wavefront fit | Independently estimate a radial center               | Curvature model and temporal support, not biological source validation                              |
| Tissue centroid / COM     | Structural proxy when justified for that preparation | Binary-area versus intensity-weighted centroid; neither automatically equals the oscillation center |

For an illustrated line, find the matching movie frame and register the actual
image content. Mask annotations, arrow, inset images and scale bars out of feature
matching. SIFT/ORB plus robust affine fitting are possible choices; use the
simplest transform supported by the images. Save matched features, inlier spatial
coverage, transform direction, residuals and checks against other thumbnails.
Map both endpoints. Small registration residuals do not remove uncertainty in
reading the drawn endpoints or establish anatomical identity.

For an inferred center, review extended curved fronts across multiple distinct
times. Fit the appropriate geometric model, inspect the observed arcs, and check
stability across disjoint times and nearby parameters. Several contours in one
frame are not independent temporal evidence. A low residual on a short arc can
still leave its center poorly constrained. If support is insufficient, report
that limitation or obtain a reviewed manual origin; do not silently fall back
to tissue COM. Use a radial direction approximately normal to supported fronts,
and document where the fronts actually intersect the selected ray.

A reviewer-identified dark core is a candidate region for this fit, not a
confirmed center by itself. Compare the candidate with continuous wavefronts
from separate times, reporting fit stability and alternative-origin sensitivity.
The tissue centroid, a dark-core seed, a geometric wavefront center and a
biological pacemaker remain distinct even when some lie close together.

## Register motion separately

Prefer a matched structural/brightfield channel when available. Verify sample,
channel alignment and time correspondence. Estimate translation or a more complex
transform according to observed motion and check first, anchor, intermediate
and last frames, plus any abrupt change. Oscillating brightness alone is not a
stable motion reference.

An origin estimate, a figure-to-movie transform and an inter-frame motion model
answer different questions. A single illustrated arrow does not reveal its full
time trajectory. If a path is continued by structural translation, record that
assumption. Translation is not rotation/deformation correction or cell tracking.
A fixed-image path can be a useful sensitivity comparison without claiming it
is the author's trajectory.

## Radial sampling and comparison

Apply the common guide for source/channel identity, calibration, strip sampling,
filter separation, output arrays and controlled comparisons. Review center and
outward direction together. A geometric circle fit needs physical coordinates
that account for any unequal x/y pixel dimensions.

An origin outside early growing tissue stays at its reviewed location: allow a
missing prefix and do not move it onto signal. Inspect disconnected tissue and
document which continuous segment is retained; first-exit and longest-run rules
are case choices. Neither the last finite distance nor the FOV boundary is
automatically the biological rim or the oscillation-arrest front.

Each radial origin defines its own distance zero. A common r does not identify
the same cells across paths. Compare reviewed overlays and numeric masks as well
as the apparent waves, preserving a promised reference matrix exactly.

## Lessons from the Lauschke reconstruction

| Observed problem                                                                       | Lesson for future radial extraction                                                                          |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Tissue COM and an independent wavefront-fit center differed from the illustrated start | Label all three origins separately and inspect their overlays before choosing one                            |
| Fig. 1d's red square was near the independent fit                                      | The square is a local-trace ROI; use the dashed line's tail when transferring the illustrated kymograph path |
| The panel labeled “0 min” matched video overlay 18.07 h                                | Register the image content and preserve the source clock; inset-relative time need not be movie time         |
| Accurate feature matching coexisted with approximately read arrow endpoints            | Report registration residual, drawing precision and biological uncertainty separately                        |
| The mapped line lay outside early tissue                                               | Keep missing coverage; moving it onto signal would change the requested method                               |
| A new origin rule could change masking behavior                                        | Apply common rules to both paths and check the old matrix remains identical before interpreting differences  |

Case coordinates and numerical results are in the skill's
[worked reference](../.agents/skills/kymograph-radial/references/lauschke-2013.md).
They are not presets for future samples.

## Code and handoff

- `analysis/extract_lauschke_author_line.py`: illustrated-line reconstruction,
  shared-rule comparison and preservation check.
- `analysis/lauschke_wavefront_center.py`: independent multi-frame center fit.
- `analysis/reproduce_lauschke_views.py`: reference sampling and spatial controls.
- `analysis/extract_lauschke_radial.py`: earlier centroid-proxy reconstruction;
  inspect its scope before reuse.
- `tests/test_lauschke_author_line.py` and `tests/test_radial_geometry.py`:
  numerical checks for geometry, drift, missing data and sampling.
- [Reproduction guide](reproducing.md): source files, environments and commands.

Reuse or improve analysis modules rather than duplicating them inside a skill.
For a card/UI handoff, supply the reviewed matrix and previews, origin evidence,
coordinate meaning, source/channel identity, calibration, uncertainty and links
to the extraction record. Styling can evolve without changing those measurements.
Maintain this guide with evidence from new cases rather than adding a universal
rule for every historical parameter choice.

Primary references: [Lauschke et al.](https://www.nature.com/articles/nature11804),
[ImageJ line-strip extraction](https://imagej.net/plugins/kymoreslicewide),
and [OpenCV feature-registration example](https://docs.opencv.org/4.x/d1/de0/tutorial_py_feature_homography.html).

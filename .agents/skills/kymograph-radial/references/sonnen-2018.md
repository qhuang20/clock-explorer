# Sonnen 2018 · Radial sampling in Movies S2 and S3

## Current selections

| Movie and dataset | Selected measurement | Implementation and limits |
| --- | --- | --- |
| Movie S2 · `sonnen-2018` | [Fixed final-frame inner reference](#movie-s2--explicit-final-frame-inner-reference). The saved ray has full-width envelope support evaluated each frame. | Extract with `analysis/extract_sonnen_fixed_reference.py --only s2` and render with `analysis/render_sonnen_half_and_extent.py --fixed --only s2`. The inner landmark and approximate scale remain under review. |
| Movie S3 · `sonnen-2018-microfluidic` | [Tracked geometric center](#movie-s3--moving-geometric-center) and an image-up strip, with a frame-specific supported endpoint. | Review with `analysis/review_sonnen_s3_moving_center.py` and render with `analysis/render_sonnen_s3_primary.py`. The fitted envelope is a geometric proxy with unresolved inner tissue occupancy and wave-source identity. |

Earlier candidate measurements and comparisons are documented below. S2 and S3
have different preparations, origin rules and distance limits.

## Movie S2 · Source and biological identity

[Movie S2 / paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC5847172/) is
Axin2T2A Venus-PEST fluorescence in ex vivo mPSM, associated with Fig. 1D–F.
Its grayscale appearance does not make it brightfield. Movie S3 is a different
LuVeLu microfluidic experiment; Fig. 1G and Fig. 2 dual-reporter experiments are
also distinct. S2 temperature, exact embryonic stage and export projection are
unverified; do not inherit 37°C from the microfluidic protocol.

The ray starts near a persistent inner structure. The documented evidence
supports regional inner-posteriorward to outer-anteriorward direction and plain
A above P in plots. Exact landmarks and the oscillation center remain unresolved.
Regional central-posterior/peripheral-anterior identity and the posterior half
of a later segment are different concepts, not interchangeable endpoints.

## Historical S2 fixed-strip baseline

- `mmc3.mp4`: 155 frames, 990×984; SHA-256
  `02b0f439d976b0a3cecb38ef89cab2c92fea1188242aceef40d11a7cf1594ec1`.
- Overlay time 0–25.69 h has 0.16/0.17/0.18 h increments, precision 0.01 h.
  Playback 10 fps/15.5 s is unrelated; movie zero is not proven culture zero.
- Horizontal scale 100 µm ≈ 139 source pixels (reading about ±1 px), retained as
  approximate isotropic conversion. Vertical scale is not independently known;
  the paper's raw-camera 1.38 µm/px does not apply to the enlarged export.
- Saved strip [520,480]→[260,240], continued by fluorescence-texture translation;
  width 40 px, 41 transverse samples; bilinear green-display mean. No added
  spatial/time smoothing, detrending, phase or deformation/cell tracking.
- Every original 354×155 value, timestamp, distance and translation reproduces
  exactly. All transverse samples are in the FOV, but no tissue mask exists.
  Do not invent missing prefixes, NaNs or zeros to make the plot look cleaner.

## Historical baseline audit

`analysis/audit_sonnen_movie_s2.py` and `tests/test_sonnen_review.py` check source
identity, exact baseline reproduction, timestamp gaps, endpoint translation,
strip geometry and FOV-only semantics. Review exports are under
`figures/sonnen-2018/s2-review/` and `data/derived/sonnen-2018/s2-review/`.
The original primary `movie-s2-kymograph.npz` is unchanged; the review NPZ adds
source-pixel coordinates and geometry without replacing it.

The standalone reviewed plot already has zero below/outward above, with
`axes_1` as data and `axes_2` as colorbar. Use the common compact card axis box,
no extra y flip; the generated UI adds regional A-above-P letters. Pair the ROI-only contact sheet with a separate
primary plot in the four-stage detail walkthrough. Keep approximate scale and
unresolved origin visible; put provenance, trajectories and origin/scale review
images in Data & sources. Future center fitting needs new reviewed evidence
and a controlled comparison, rather than silently replacing this baseline.

## Reassessment with same-specimen published evidence

The earlier omission of all AP labels was too broad: unregistered O/E and an
unfitted center do not by themselves negate a supported regional direction.
Results explicitly define posterior mPSM centrally and anterior mPSM at the
periphery. MovieS2 caption and Fig1D–F identify this same specimen and the
forming-segment stripe; posterior segment halves are segment-internal polarity.

Fresh consecutive-frame review covers0–154 with the unchanged strip overlays.
Fig1D matches frame89/14.85h with152 feature inliers, median residual0.994 source
pixels and broad spatial coverage. The mapped arrow identifies an anteriorward
segmenting sector; O→E points toward it (cosine≈0.900). These are geometric
correspondence checks, not confidence intervals for anatomy. Arrow reading is
approximately±3 published pixels; it is not a deposited author kymograph ROI.

As tissue spreads, the endpoint becomes interior but the strip still points
from the inner region toward that outer sector. Label regional direction in
card and detail, retaining distance-from-ROI-start and approximateµm units.
Movie zero is not verified culture zero; do not import a20h onset rule from
another paper or treat the14.85h snapshot match as first segmentation onset.
Exact center, P/A boundaries, tissue validity and per-cell molecular identity
at every time remain unresolved. New evidence is under `ap-review/` in the
Sonnen derived-data and figure directories. `analysis/review_radial_ap.py`
checks the recorded correspondence and regenerates the keyframe evidence.

## Published-panel comparison and data-first scope (2026-11-17)

The author sampling arrow for the **Figure 2A** intensity kymograph is in
**Figure S2A**; S2B repeats 2A, while S2C is a phase calculation from that
measurement. Figure S2D/E/F is the corresponding LuVeLu reference experiment.
The white arrowhead in Figure1D marks a forming-segment stripe, not that sampling
line. These arrows must not be exchanged.

`catalog/source-audits/sonnen-2018.json` now inventories all 14 published
kymograph panel groups and their conditions. None has an identified exact-sample
spatial input among the checked public attachments. The available single-reporter
Movies S1/S2/S3 already have local kymographs; no additional source-backed card is
missing. Document S1 contains plotted anterior time traces, not spatial matrices.
Skip unavailable measurements, including Mesp2 and treatment-specific panels,
rather than substituting a related movie or reconstructing raw data from a JPEG.

`analysis/compare_sonnen_published.py` searches all155 S2 frames with the same
masked SIFT/RANSAC procedure. Positive-control Figure1D matches frame89 with168
inliers spanning approximately167×168 published pixels and median1.00 source-pixel
residual. S2A yields at most2 inliers and no supported transform. The latter is
not evidence of a different specimen, especially across imaging modalities;
it prevents transferring the author's exact line. Two-point zero residuals are
degenerate fits, not validation. The thresholds are this case's geometric guard.

Keep author method scopes separate. Figures1C/G use5µm filtering and a50 original
camera-pixel (~70µm) averaging width. The oscillation-dynamics paragraph specifies
10µm filtering but no averaging width or independent temporal-filter scale.
Do not silently inherit70µm for Figure2 or translate a spatial sigma into a time
kernel. Public movies may already include undocumented display processing.

The new S2 control adds only a per-frame x/y Gaussian σ=10µm, using100µm/139px
approximate export calibration, the original40px strip, saved motion and all
irregular timestamps. Both complete arrays share color limits and retained FOV
support; no center refit, temporal filter or post-kymograph filter is applied.
It is a method-guided spatial sensitivity control, not Figure2A reproduction.
Smoothing does not resolve the origin or late interior endpoint. Files are under
`data/derived/sonnen-2018/paper-comparison/` and matching figure directories;
the primary remains byte-for-byte unchanged. S1/S3 retain their existing
spatial-only controls, without claiming the author exact ROI or pulse condition.

## Movie S3 · moving geometric center

The LuVeLu microfluidic culture has an open contour early and a more rounded
envelope later. `analysis/review_sonnen_s3_moving_center.py` fits ellipses to
outer envelopes across all 111 native frames and stabilizes the median center
from three contour thresholds. Center coordinates move about 18 source pixels
right and 31 pixels up between the first and last frames. Threshold sensitivity
is recorded with the trajectory. Crop boundaries can bias the fit when the
culture spreads. Check the full usable image and exclude annotations before
filtering for the envelope.

The fitted envelope bridges dark gaps and establishes an outer-extent proxy.
Inner tissue occupancy and the biological wave source still require independent
evidence. Within the recorded envelope, keep low display values in the finite
strip. Only the geometry estimator uses smoothing. The old and new strips
share the image-up direction, approximate 70 µm width, source timestamps and
color limits. Compare their common radial support before interpreting the
additional extent of the moving strip. Save the track, valid coverage and
overlay with the matrix. Parameters are specific to this movie.

The Movie S3 card now uses the saved moving-center matrix. Render the selected
plot with `analysis/render_sonnen_s3_primary.py` and export its frame-aligned
footprint with `analysis/export_video_rois.py --only sonnen-2018-microfluidic`.
The fixed-origin extraction remains available in the comparison.

The [shared overlay rule](../../../../docs/ui-card-guidelines.md#radial-extent-and-missing-coverage)
uses the saved path and validity for the sampling board, kymograph and video.
In S3 the orange origin is O, the band is solid through E, and the dashed guide
runs from E to this dataset's **300 µm** cap. The kymograph leaves that extension
missing. Frames 0, 55 and 110 have approximately 139, 254 and 260 µm of sampled
extent. Check the endpoints against the saved paths and confirm the browser
loads the revised overlay and maps it to the corresponding native frames.

S3's ROI-only refresh uses `analysis/render_sonnen_s3_primary.py --roi-only`.
Chrome retained a cached overlay during review. The refreshed board and
overlay use new asset paths (`roi-with-extent.png` and
`sonnen-2018-microfluidic-video-roi-with-extent.json`). The intensity matrix
and its hash stayed the same, so the matrix hash alone could not detect the
older overlay.

## Movie S2 · extending the original ray

The earlier extended-ray comparison came from
`analysis/review_sonnen_s2_extended.py`. The inner reference, direction,
translations, original grid spacing and 40 px width remain the basis of the
measurement. All 354 original rows are copied exactly after independent pixel
resampling confirms them. New outer rows require every transverse sample to
lie inside contiguous outer-envelope support, with a 5 px margin. The shortest
extent across three display thresholds supplies the conservative extension.
These geometry estimates use an 8 px Gaussian, while intensities come directly
from the original decoded green channel.

The initial retained extent is approximately 255 µm. It reaches approximately
361 µm at 12.85 h and 337 µm in the last frame. The envelope can expand and
contract. Its validity applies to new rows, while the historical prefix retains
its earlier FOV-only validity. Record this mixed coverage policy explicitly.
The origin's biological interpretation remains unresolved. Extending the ray
supplies additional peripheral coverage, with center validation a separate task.

Review the full finite-width band at the outer edge. Preserve source distances
and missing extensions through time, and compare the previous/extended matrices
with one scale. Changing the endpoint alone preserves all shared measured
values. A new zero or direction would require a different controlled comparison.

## Movie S2 · explicit final-frame inner reference

The requested fixed-P convention is now expressed explicitly in
`analysis/extract_sonnen_fixed_reference.py --only s2`. The saved translation
trajectory already defined one registered inner origin. Set the reference once
at its final-frame xy and recover native coordinates through inverse transforms.
The geometry remains the same outward ray. The current matrix applies full-width
three-threshold envelope support throughout the ray, including the historical
prefix. The former FOV-only prefix remains in the previous comparison.

The center is covered throughout this specimen. Spreading appears at the outer
edge of the radial coordinate. Save and display P-reference markers separately
from the moving last supported endpoint E. The fixed-reference case gives a
specific origin convention while the biological center remains under review.

In the sampling board and video, the solid band ends at E, the last supported
sample of each frame. The dashed guide follows the saved ray to the end of
S2's distance grid, and that extension stays missing in the kymograph. The
fixed P reference follows the saved source-frame translations, while E can
move independently as coverage changes. Export playback with
`analysis/export_video_rois.py --only sonnen-2018`.

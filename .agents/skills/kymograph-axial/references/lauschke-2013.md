# Lauschke 2013: axial Video 1 reconstruction

This case supports `kymograph-axial` for the posterior embryo fragment in
[Figure 1b/c and Supplementary Video 1](https://www.nature.com/articles/nature11804).
Figure 1d/f is a different spreading mPSM preparation and belongs to the radial
workflow. These are not merely two rotations of one specimen.

## Current selection

Video 1 · `lauschke-2013-embryo` uses the [fixed A/P curve shifted inward by 30 px](#selected-video-1-primary--fixed-references-inward30)
across all 126 frames (0–20.92 h). Extract with
`analysis/extract_video1_inward30.py` and render with
`analysis/render_video1_primary.py`. The reviewed registration is sensitive to
the structural window, and the foreground mask is a display-texture proxy.
The earlier straight and moving-reference curves are documented below as history.

## Earlier straight-strip input and coordinates

- Source: `41586_2013_BFnature11804_MOESM292_ESM.mov`.
- SHA-256: `ead90ea0a22ae683f8bcfc3b804cbc37144274b8635e2206a0a6d985f9b94b04`.
- Full source has 126 decoded frames. The reviewed extraction uses the first 61,
  whose burned-in timestamps span 0–10 h. Later bent geometry is not validated.
- Spatial scale: 100 µm spans 103 decoded video pixels, reviewed endpoints
  x=23,126 at y=691; scale-bar reading precision approximately one pixel.
- Coordinates: x right, y down; frame indices below are zero-based.

| Frame | Posterior-side point x,y | Anterior-direction point x,y |
| ----- | ------------------------ | ---------------------------- |
| 0     | 405,350                  | 170,140                      |
| 20    | 365,385                  | 150,230                      |
| 40    | 375,415                  | 155,280                      |
| 60    | 420,460                  | 190,325                      |

The adapter interpolates both points over the reviewed interval, sets the
posterior-side point as origin and normalizes the vector toward the anterior
point. These are manually reviewed approximate landmarks, not the author's
saved ROI or tracked cells. The second point establishes direction only.

It samples 20 px-wide strips with bilinear signal sampling and a mean of decoded
RGB display values. The 451 × 61 primary grid has distances 0–450 µm and retains
actual source timestamps. It excludes FOV/text borders with a 75% width-validity
threshold and terminates at the first failed row. There is no anatomical tissue
mask; finite background beyond tissue can remain. A strip's last finite sample
is not necessarily an anterior tissue edge or arrest front.

The source blends reporter and brightfield. Display intensity is not raw LuVeLu
fluorescence. Primary extraction adds no filtering. A separate image-space
Gaussian σ=9.66 µm control does not filter time or infer phase. No detrending,
Hilbert phase or deformation correction is reproduced here.

## Reproduce in an isolated review directory

Obtain original Videos 1–3 and the audited timestamp JSONs described in the
[reproduction guide](../../../../docs/reproducing.md). The current adapter
verifies/decodes all three sources even with `--only 1`. With the scientific
Python environment active, run from the checkout root:

```sh
axial_review_root="$(mktemp -d)"
CLOCK_ASSET_ROOT="$axial_review_root" python analysis/reproduce_lauschke_views.py \
  --source-dir assets/data/source-archive/lauschke-2013 \
  --time-dir assets/data/derived/lauschke-2013 \
  --only 1
```

Outputs under the isolated asset root are:

- `data/derived/lauschke-2013/video1-kymograph.npz`: primary/control matrices,
  timestamps, physical distances and per-frame origins/directions.
- `data/derived/lauschke-2013/video1-provenance.json`: source hash, reviewed
  landmarks, width, scale, filtering and limitations.
- `figures/lauschke-2013/video1-sampling.*` and `video1-spatial-filter.*`:
  path overlays, kymograph and spatial-control pair.

Compare numerical arrays, masks, time/space coordinates and geometry against the
saved reference before replacing any assets. New PNG metadata/font rendering or
provenance script hashes need not match an older run; do not use image hashes as
the sole numerical reproduction criterion.

## Maintenance

Implementation: `analysis/reproduce_lauschke_views.py`, especially `ap_geometry`,
`read_times` and `sample`. Reviewed arrays/records live in ignored `assets/`,
with fetch sources and checksums in `catalog/assets.json`.

A new specimen needs its own landmark evidence, endpoint, motion review, clock,
scale and validity rules. Do not reuse the coordinates above as automatic AP
estimates. If a tissue mask or later curved interval is introduced, compare it
as a new method rather than silently changing the existing reconstruction.

## Video 1 review: reproduction versus author correspondence

`analysis/audit_lauschke_video1.py` independently decodes Video 1, verifies its
source hash and timestamp audit, and reproduces every saved primary and
spatial-control value across all 61 reviewed frames. It writes separate ROI
panels, an all-frame contact sheet, a paper-orientation comparison and a JSON
review record without replacing the original NPZ or provenance. The website
uses the reviewed first-card four-step layout for this dataset.

The Fig. 1b/c caption and Supplementary Video 1 description support posterior-to-
anterior polarity. They do not establish that Video 1 is the exact embryo shown
in Fig. 1b. A local image-registration probe did not supply a corroborated,
non-degenerate panel-to-video transform; no illustrated author line is claimed.
Keep the manual coordinates explicitly approximate. This is a reconstruction of
the paper's axial sampling geometry, not a pixel-identical reproduction of Fig. 1c.

The ROI overlays show the full FOV-valid strip, including its declared endpoint.
Only FOV/annotation validity is applied: finite background may remain, and the
endpoint is not an anatomical anterior boundary or arrest front. Do not describe
this adapter as masking all tissue-exterior pixels.

```sh
python analysis/audit_lauschke_video1.py \
  --source-dir assets/data/source-archive/lauschke-2013 \
  --output outputs/lauschke-video1-review
```

## Controlled Video 1 processing comparison

The user-confirmed default range is **0–450 µm** for the card, representative
ROI, all61 audit, three-panel comparison, downloads and processing provenance.
The old0–350 µm comparison remains archived, not the default. This is specific
to Video1; it does not impose450 or common numerical limits on other datasets.

Preserve the original451×61 raw and spatial-control matrices and 1,342 NaNs.
Only14/61 frames reach450; the other47 end at FOV-valid distances407–449µm.
450 is a sampling/display cap, not a fixed PSM length or verified A boundary.
Full-width overlays at every selected frame show the visible embryo/PSM-side
corridor without a clear exterior section justifying a new mask at contact-sheet
scale. This is visual review, not anatomical segmentation: finite display values
may still include BF/background or adjacent tissue. Do not claim an FOV mask is
a tissue mask or fill unseen extension to reach the chosen limit.

The first two panels retain the full reference's intensity limits and compare
unsmoothed values with per-frame image-space Gaussian σ=9.66µm. The third is a
separate derived diagnostic: filtered values minus a slow Gaussian baseline
σt=1.5h using actual hours and trapezoidal weights. All panels share space,
time and validity; signed residuals and missing data remain intact. Time support
is evaluated per spatial position; hatch low support rather than whole columns
when later FOV coverage changes with distance. The established residual display
range stays±55; two positive values (55.3270/55.5708 at t0, r431/432µm) exceed
it and get a colorbar extension, without clipping saved values or renormalizing.

All five arrays on the archived0–350 segment remain exact. Reproduce with
`analysis/compare_lauschke_video1_450.py --source-dir assets/data/source-archive/lauschke-2013 --output outputs/lauschke-video1-450-review`
using the scientific environment. Its `tests/test_video1_450.py` checks the full
grid, old-segment identity, missingness and per-position temporal support. New outputs live
under `figures/lauschke-2013/video1-450-review/` and
`data/derived/lauschke-2013/video1-450-review/`. The new three-panel SVG already
puts zero below, data axes1–3 and colorbars4–5. Set its method `flip_y:false`;
the unchanged original card still uses its own reviewed reversal. Source ROI
frames keep their movie orientation.

## Interpreting the per-frame processing note

The user relayed Victoria's shorthand: “Distance / Averaging / Blurring or
smoothing on the video only on each frame.” In this review, the working
interpretation is calibrated P→A distance, transverse strip-width averaging and
independent image-space filtering for each frame. The fragment does not confirm
Victoria's intended averaging dimension or any numerical filter setting; it is
not an additional method statement from the paper.

Under that per-frame-only interpretation, the spatial Gaussian panel is the
processed-intensity comparison; the unsmoothed panel already includes width
averaging. The third panel's σt=1.5 h baseline subtraction uses neighboring times
and remains an auxiliary derived-contrast diagnostic, outside the spatial-only
recommendation. Do not relabel it as temporally unprocessed intensity, isolated
fluorescence or phase. The case's σ=9.66 µm and σt=1.5 h are not universal defaults.

## Reviewed A-above-P display convention

Video 1's rounded posterior end and the paper's Fig. 1b/c support the existing
posterior-side-to-anterior sampling direction. The user prefers kymographs with
A above P. The reviewed UI now reverses the gallery plot and all three panels
of the processing comparison together: distance zero is below, increasing
anteriorward above. The time axis, colorbar direction and upright labels remain
unchanged. Original numeric arrays and source figures retain their stored
orientation; source ROI frames are not flipped. Keep the approximate landmarks
and analysis cutoff distinct from exact anatomical endpoints.

## Full Video 1 · earlier moving curved-strip analysis

The same original MOV has126 frames and reaches20.92h. The new adapter
`analysis/extract_lauschke_video1_curved.py` uses12 structural keyframes, with
separate keys at100/101 for the visible source-pose jump (16.67→16.92h).
It interpolates control points in actual time, samples a natural cubic by
physical arc length and takes a20px-wide normal mean. The full451×126 matrix
uses0–450µm without rescaling growth, retaining10 FOV/text-missing values.
The width-normal mapping has minimum local Jacobian0.862, without a local fold.
A40px sensitivity profile is saved separately; it does not choose the primary
width by how clean its waves look.

The full sequence is re-extracted, so early values differ from the earlier
straight method. The original451×61 NPZ remains unchanged, and a matched0–10h
comparison holds width and color scale together while showing the geometry and
coverage difference. Both current raw and per-frame σ=9.66µm panels use the new
raw matrix's complete limits. No temporal filter is added. Original frames stay
upright; the gallery and comparison show A above P.

Reproduce in a separate root (the original timestamp audit and old reference
must be available under the normal `CLOCK_ASSET_ROOT`):

```sh
python analysis/extract_lauschke_video1_curved.py \
  --output-root outputs/video1-full-curve-review
```

Outputs use `data/derived/lauschke-2013/video1-full-curve/` and
`figures/lauschke-2013/video1-full-curve/`. Save the full per-frame paths,
normals, controls, counts, masks and all126 overlays. The curve follows an
approximate visible PSM-side corridor; it is not author-deposited anatomy,
an exact posterior endpoint, segmentation or cell tracking. The mixed
LuVeLu/brightfield display cannot supply isolated fluorescence. Curve placement
and source-pose correction do not make stripe slopes material wave speeds.

## Selected Video 1 primary · fixed references, inward30

The user selected the inward30 candidate on2026-11-16. This is still the axial
workflow: a curved P→A sampling corridor with a different reference convention,
not a new extraction skill. Update this case and the shared guide as calibration
evolves;30px is this specimen's choice, not a default for other movies.

The reference frame is125. Approximate sampling endpoints P=(540,430),
A=(100,300) stay fixed in that stabilized coordinate system. The interior path
follows the visible lower contour, shifted inward30px with a spatially smoothed
normal field and tapered endpoint transitions. Fixed xy endpoints do not freeze
arc length, tissue tips or cells. Do not replace them with the first/last valid
measurement positions when drawing labels.

The exact reviewed geometry is inverse-mapped into native Video1 pixels;
intensities are not read from a warped stabilization movie. The current primary
has596×126 samples,1µm distance spacing, all0–20.92h timestamps and a20px width
mean. Every exact A endpoint has21/21 width samples supported. At least16/21
points are required; keep the final connected supported run toward that checked
A anchor. Early P-side extensions and separated islands remain missing, never
zero-filled or bridged. There are16,433 missing values. Path length varies about
516.10–594.67µm; this is physical arc length, not a normalized tissue length.

`analysis/extract_video1_inward30.py` saves the native/reference paths, normals,
counts, masks and source/geometry hashes. `analysis/render_video1_primary.py`
copies the reviewed NPZ unchanged to
`data/derived/lauschke-2013/video1-fixed-reference/kymograph.npz` and renders the
matching figures. Catalogue selection, range payload and playback overlay must
all reference that file's hash. The active UI no longer offers the earlier
moving/straight comparisons; historical source files are not the selected method.

Solid video bands use the measurement-valid interval. A separate dashed guide
shows the full finite reference path, with A/P labels attached to saved reference
points rather than the moving valid interval. Source-video coordinates can move
because they include the inverse camera-pose transform. The kymograph displays
A above P without flipping the source video.

The original registration remains sensitive to structural-window selection
(up to about73px disagreement in the tested cumulative registrations). Low
feature residuals and a user-selected path do not independently validate anatomy.
The foreground is a display-texture proxy, not verified PSM segmentation; the
LuVeLu/brightfield composite is not isolated reporter fluorescence. Keep these
limits visible and preserve the source clock gap at100/101.

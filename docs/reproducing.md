# Reproducing research views

Website builds and numerical analysis are separate. `npm run build` never runs
an extraction or changes scientific arrays.

Start with the [shared extraction guide](kymograph-extraction.md), then choose
the [axial](kymograph-axial.md) or [radial](kymograph-radial.md) method according
to the preparation and reviewed geometry.

## Environment

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r analysis/requirements.txt
npm run data:fetch
```

The pinned scientific environment was validated with Python 3.12. The website
requires only Python 3.10+ standard library. Install scientific packages only if
you need to extract or redraw data.

## Render saved matrices

```sh
python analysis/render_kymograph.py
python analysis/render_comparison.py
python analysis/render_method_cards.py
python analysis/build_range_payloads.py
npm run check
npm run build
```

These commands write local research artifacts under `assets/`; comparison metadata
is updated under `catalog/`. The comparison renderer preserves card context and
model labels when rebuilding scientific ranges and figures. Review numerical and
metadata differences before committing. Set `CLOCK_ASSET_ROOT` and
`CLOCK_CATALOG_ROOT` to temporary directories to compare a rerun without replacing
working outputs.

Some exact pixels/font metrics may differ across operating systems. Validate
matrix values, axes, masks and input hashes rather than assuming a PNG hash is a
portable scientific test.

## Extraction adapters

| Script                                          | Inputs and scope                                                                  |
| ----------------------------------------------- | --------------------------------------------------------------------------------- |
| `extract_delaune_video.py --source-dir PATH`    | Original S1 movie and Figure 1 reference; fixed strip                             |
| `extract_video_kymographs.py --source-dir PATH` | Lauschke/Sonnen source tree; Lauschke delegates to the radial adapter             |
| `extract_lauschke_radial.py --source-dir PATH`  | Original Video 5 and matching Video 4 in a source-archive directory               |
| `extract_rohde_tracks.py --no-previews`         | Published CSV, calibration XML and ROI files in `assets/data/samples/rohde-2024/` |
| `extract_yaman_example.py`                      | Author-provided example TIFF                                                      |
| `extract_miao_video.py`                         | Movie 2 and matching LUT in `assets/data/derived/miao-2023/`                      |
| `extract_sanaki_video.py`                       | Movie 4 and Fire LUT in `assets/data/derived/sanaki-2022/`                        |

Original movies are intentionally not bundled in Git. Use their provenance
records to obtain the exact input file and verify the expected hash. File names
and required layouts are stated in each script. The current Somitoid color-index
and video ROI reconstructions are qualitative display measurements, not raw
fluorescence. Saved full-range reconstructions are provided as optional assets;
not every historical one-off acquisition script is a supported pipeline.

For Python contributions, install `.github/requirements.txt` and run
`ruff check analysis scripts tests` and `ruff format --check analysis scripts tests`.

## Lauschke radial re-extraction

`extract_lauschke_radial.py` checks the two original MOV hashes, estimates structural
translation using Video 4, and computes uniform-area centroids from brightfield
texture masks constrained by one time-median LuVeLu support region. Filtering is
used for geometry only. It samples unchanged decoded green values along a 20 px
wide, 45° radius from that centroid toward the outer rim. A radius ends at the
first loss of 75% valid width; background remains NaN. All 61 source frames remain.

The geometric center is a center-side posterior **proxy**, not a verified fate
marker or a fitted oscillation source. The original paper uses an oscillation
center-to-periphery line; this independent extraction does not claim the exact
published ROI or reproduce its filtered phase analysis. No new physical tail cut,
cell tracking, rotation correction or tissue deformation correction is inferred.
The saved geometry masks/trajectory, 35°/55° alternatives, and support-threshold
sensitivity record make the choices inspectable. Run the optional geometry tests
with the scientific environment: `python -m unittest discover -s tests -p test_radial_geometry.py`.

## Choose geometry before choosing an ROI

[Lauschke Fig. 1 and its supplementary videos](https://www.nature.com/articles/nature11804)
compare different preparations, not just camera rotations:

| Reference             | Preparation                                                    | Sampling geometry                              |
| --------------------- | -------------------------------------------------------------- | ---------------------------------------------- |
| Fig. 1b/c, Video 1    | Posterior embryo fragment, side view                           | Posterior-side landmark toward anterior PSM    |
| Fig. 1d/f, Videos 2/3 | Isolated tailbud-derived spreading mPSM; culture-plane imaging | Core/oscillation-center side toward periphery  |
| Videos 4–7            | Separate later segmentation-stage mPSM culture                 | Radial geometry; not the Fig. 1f source sample |

Image vertical is not an anatomical AP axis. A round-looking tissue does not by
itself justify radial sampling. Identify the preparation and anatomical direction
from captions/methods, then review the source frames. Whole-tissue COM during
asymmetric spreading can drift away from the oscillation source. Keep any COM
proxy, structural registration, and inferred posterior identity distinct.

`reproduce_lauschke_views.py --source-dir PATH --time-dir PATH` reconstructs the
two Fig. 1 sampling geometries from the original display movies. The time directory
contains audited `video1-timestamps.json` and `video2-timestamps.json` files. It uses
the first 61/126 Video 1 frames (0–10 h), reviewed AP landmark pairs, and all 160
Video 2 frames (0–33.80 h). Video 2 now estimates a shared center from continuous
early wavefront arcs, then follows matching Video 3 translation; COM is not used
as a center prior or fallback. Preserve the measured video scale bars and actual timestamp overlays;
these need not match a nominal acquisition interval. Video 1 is a composite display,
so its intensity cannot be treated as isolated fluorescence.

Primary comparison arrays are unsmoothed. Separate spatial-filter figures convert
the paper's raw-image sigma (7 × 1.38 µm) to 9.66 µm on each display frame. They use
the same paths, masks, timestamps and color limits as their unsmoothed controls.
The original second kymograph blur has unverified time-pixel scaling here; it is
not applied to the reduced video time grid. No detrending or Hilbert phase is
inferred. Tissue can leave the FOV, so an ROI endpoint is not automatically the
biological periphery or the oscillation-arrest front. The sampling figures use the
paper's ascending-space orientation; gallery cards retain the common 0-at-top view.

## Video 2 wavefront-center estimation

`lauschke_wavefront_center.py` fits long curved contours of dynamic wavefronts,
then selects a temporally supported consensus and jointly fits a shared curvature
center with one radius per observed frame. Every frame has equal total weight;
multiple contours from one frame cannot count as independent temporal evidence.
No tissue COM initializes the fit, and insufficient evidence raises an error.

The fit scans 0.75–16 h. Its coherent consensus contains six distinct frames over
1.28–5.10 h. The reference-frame estimate is approximately (412.7, 399.0) decoded
video pixels; the median arc residual is 7.5 µm. Disjoint temporal halves differ
by 14.6 µm and geometry-filter scales of 14/20 µm shift the center by 3–5 µm.
These are sensitivity diagnostics, not confidence intervals or biological validation.
The center-estimation filters (spatial sigma 16.61 µm and a temporal Gaussian
difference with sigmas 0.2/1.2 h, converted using the median overlay interval)
serve geometry only. The primary sampled intensities and source timestamps are
not filtered. Saved observed contours permit direct inspection of the fit.

The reviewed upper-tissue radius at −72° avoids scattered bright spots near the
bottom edge. Its perpendicularity follows the approximate circular-front model;
only a subset of the fitted contours crosses this ray directly. The direction is
not selected to improve kymograph contrast and is not the author's exact ROI.
Late-stage source positions are not independently validated: the early center is
continued using brightfield translation, without deformation or cell tracking.
The former COM reconstruction is retained only as an audit file. Use `--only 2`
with the adapter command to update this dataset without regenerating Video 1.

## Video 2 illustrated-line comparison

To reconstruct the start and direction drawn in Fig. 1d without replacing the
current wavefront-fit matrix, run after obtaining the original source movie and
existing Video 2 geometry:

```sh
python analysis/extract_lauschke_author_line.py \
  --source-dir assets/data/source-archive/lauschke-2013 \
  --registration assets/data/derived/lauschke-2013/video2-author-line-registration.json
```

The registration input records the publisher image hash, panel crop, reviewed
arrow endpoints, affine transform and matched image features. The illustrated
“0 min” panel matches Video 2 frame 85 (zero-based), whose overlay reads 18.07 h;
four other thumbnails independently confirm the sequence. The reference fit has
142 inliers and a median residual of 0.31 video pixels. Feature accuracy does not
make the drawn endpoints exact: their reading precision is about two panel
pixels, and the authors did not deposit a full time-dependent ROI.

Both paths use the existing brightfield translation, actual movie timestamps,
100 µm / 111 video-pixel scale, 20 px strip width and tissue/FOV rules. A missing
leading segment is permitted, and only the longest continuous valid tissue
interval is retained per frame. The current matrix is re-sampled under that rule
and must match exactly before figures are generated. Neither origin is moved to
make early tissue visible. Both complete arrays share one finite-value min–max
color scale. Distances start at each path's own origin and do not identify the
same cells.

The new `video2-author-line.npz` stores the illustrated-line matrix, unchanged
current reference, geometry, valid-width counts, shared color limits and separate
spatial-filter controls. A fixed-image line is also saved as a sensitivity check
on the assumed motion. JSON provenance records source and script hashes. The
main gallery keeps its existing matrix; the Video 2 detail view adds the paired
kymographs and line overlays. This reconstruction does not claim to reproduce
all processing or the exact temporal ROI of published Fig. 1f.

## Video 5 dark-core center comparison

With the scientific environment active, the original Video 5 and saved Video 5
centroid geometry/matrix available, run:

```sh
python analysis/fit_lauschke_video5.py \
  --source-dir assets/data/source-archive/lauschke-2013 \
  --output-root work/video5-wavefront-comparison
```

This writes new comparison arrays, paired ROI/kymograph figures and a center-fit
record into the specified output root. It does not replace the centroid matrix.
The [worked radial case](../.agents/skills/kymograph-radial/references/lauschke-2013.md#video-5-dark-core-guided-wavefront-comparison)
explains the candidate region, temporal/filter checks and remaining limitations.

The reviewed Video 5 primary now uses the fitted `intensity` in
`video5-wavefront-comparison.npz`; the original centroid file remains unchanged.
To render that saved selection without refitting the center:

```sh
python analysis/render_video5_primary.py \
  --source-dir assets/data/source-archive/lauschke-2013 --output-root assets
python analysis/render_comparison.py --only lauschke-2013
python analysis/build_range_payloads.py --only lauschke-2013
```

The first command creates the primary ROI preview. The standard renderer honors
the reviewed input and coordinate in `catalog/comparison.json`; it also updates
combined exports. The scoped range command preserves other dataset payloads.
Keep optional-asset sizes/checksums synchronized after regenerating figures,
then run the repository checks and site build.

## Mesp2 paired-channel spatial control

The gallery keeps the original Video 6 Mesp2 extraction. Add or reproduce its
detail-only Unsmoothed / Spatial filter comparison into an isolated root:

```sh
python analysis/compare_lauschke_mesp2_spatial.py \
  --source-dir assets/data/source-archive/lauschke-2013 \
  --output-root outputs/video6-mesp2-spatial/assets
```

It requires the saved Video 6 primary and Video 5 geometry under the asset root.
The command verifies the source hash and reproduces the raw primary exactly,
then filters the red display channel per frame with a normalized masked
Gaussian before sampling the same strip. NPZ/JSON and SVG/PNG/PDF comparison
files preserve the original geometry, mask and primary color limits.

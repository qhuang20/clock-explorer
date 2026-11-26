# Masamizu 2006: axial route, registration not yet established

## Current selection

Movie 2 · `masamizu-2006` uses the fixed 35 px image strip across 45 frames,
saved in `data/derived/masamizu-2006/kymograph.npz`. Overall polarity was
confirmed in review. The camera angle, physical calibration and framewise
anatomical registration remain unresolved. Use
`analysis/audit_masamizu_geometry.py` to reproduce the saved strip and check
the source and sampling coordinates.

## Choose the skill from the preparation and evidence

[Masamizu et al., PNAS 103, 1313–1318 (2006), DOI 10.1073/pnas.0508658103](https://pmc.ncbi.nlm.nih.gov/articles/PMC1345707/)
reports E10.5 caudal embryo/PSM explant imaging with Hes1-Ub1-Luc. The Results and
Figure 3 caption identify Movie 2 and describe progression from the caudal end
toward S0. The caption identifies S0 with an asterisk in Figure 3a.

Select **`kymograph-axial`** as the appropriate analysis route. The inspected movie
does not provide a reviewed center-to-periphery preparation or concentric-front
geometry supporting **`kymograph-radial`**. A source image looking round at one
moment is insufficient evidence for radial sampling.

This decision does not verify a dorsal, ventral or lateral camera view. The
reviewed card now says “Embryo imaging · angle unverified”: the broad imaging
class is supported while the precise angle remains unresolved in the reviewed
Fig.3/Movie2 caption and methods (catalog evidence M9). Keep that qualification
until specific orientation evidence is found. Likewise, the
article's biological direction does not itself map P/A landmarks into every
movie frame.

## What the current card actually measures

- Exact input: `pnas_0508658103_08658Movie2.mov`, 2,952,078 bytes;
  SHA-256 `455cdd3e3049351a064879e09ebcfa8ebd8be73d3d357eeb12bd42490465ce92`.
- All 45 frames decode to 256 × 256 grayscale. RGB decoding yields identical
  channel values. The `rawvideo` codec does not make this a raw microscopy stack.
- Fixed image ROI: x=[60,95), y=[50,210), a 35 px-wide strip.
- The matrix averages source grayscale values across x and stacks them as
  160 image-y positions × 45 frame indices. This is not an AP-registered distance.
- The reference has no tissue mask, background subtraction or structural motion
  correction. Signal positions and shapes change over the sequence, while the
  sampling frame remains fixed. Do not separate drift, growth, deformation and
  expression-wave movement from brightness changes alone.
- The 45-frame audit reproduces every stored display-intensity value exactly;
  frame and image-y coordinates agree, and the saved global normalization agrees
  to floating-point precision. The reference NPZ remains unchanged.

The upper-right “Video extraction” source badge remains accurate. An axial route
is an analysis method choice, not another source category or calibration status.
The existing simple card layout does not need a redesign for this decision.

## Calibration and readiness

| Question                              | Review outcome                                    | Consequence                                                            |
| ------------------------------------- | ------------------------------------------------- | ---------------------------------------------------------------------- |
| Appropriate biological coordinate     | Axial route supported by preparation and Fig. 3   | Use the axial workflow for the next anatomical review                  |
| P/A landmarks mapped to source frames | Not established in this audit                     | Do not label the fixed strip an anatomically registered P→A extraction |
| Camera view                           | Embryo imaging supported; angle unverified         | Keep the qualified broad view rather than inferring dorsal/ventral     |
| Exposure duration                     | Article reports 20 min                            | Do not substitute exposure for verified acquisition interval           |
| Exact experimental frame interval     | Unverified                                        | Retain frame-index axis                                                |
| Micrometers per decoded pixel         | Unverified                                        | Retain pixel coordinates                                               |
| Quantitative wave velocity            | Not supported by current calibration/registration | Do not infer it from diagonal-band slope                               |

Qualitative review in frame/pixel units is still valid. Missing physical units
do not prevent source inspection, but they limit the biological measurements.
The diagonal trace may combine tissue displacement, growth and oscillatory signal;
its visual smoothness does not validate an anatomical kymograph.

## Reproduce the baseline audit

With the optional scientific Python environment active, run from the checkout:

```sh
python analysis/audit_masamizu_geometry.py
```

The script verifies the exact source hash, decodes every frame, reconstructs the
saved fixed-strip matrix, checks normalization and ensures the original matrix
hash is preserved. It writes an all-frame ROI contact sheet and `review.json`
under ignored `outputs/masamizu-geometry-review/`; `--output` changes that location.
The reported method choice is a reviewed case conclusion, not an automatic
geometry-classification result.

Current direct PMC/legacy university PDF fetches did not yield readable figure
files. Primary-source indexed text supplied the article/caption evidence above.
No pixel-wise registration of labeled Figure 3 to the movie, exact author ROI,
or new anatomical extraction is claimed.

## Image polarity confirmed in review

The reviewer confirmed **upper image y = anterior side, lower image y = posterior
side** on 2026-11-15. They identify the lower pale triangular region as the growth
zone associated with posterior tail elongation. This supersedes the earlier
provisional upper/lower interpretation; the UI now shows plain `A` / `P`.
The presentation record identifies this as user review, rather than a newly
recovered author annotation or deposited ROI.

Overall anatomical polarity is now supported for this movie. This confirmation
does not change the fixed ROI, image-y coordinates, matrix, unresolved camera
view, physical calibration or framewise anatomical registration. The persistent
bright band's displacement can mix tissue/segmentation-front motion with signal
dynamics; do not use it alone to estimate wave velocity. Do not apply this
movie's upper/lower ordering automatically to another specimen.

## Next review before a new axial extraction

Review a readable labeled Figure 3 or matched structural views, map S0/anterior
and posterior-side landmarks across representative source frames, choose one
PSM-side path and its valid tissue extent, and state how motion is handled.
A bright expression maximum or intensity COM is not a silently acceptable
posterior landmark. Do not mix a second PSM side into the strip just to increase
signal.

Then compare the reviewed axial ROI with the existing fixed-strip reference,
using the same frames, estimator and declared display limits wherever possible.
Keep unknown time/length units explicit. Preserve the old matrix and distinguish
qualitative image-coordinate extraction from anatomically registered sampling.

This case adds a readiness gate to method routing; it does not prescribe its
fixed ROI coordinates for new movies.

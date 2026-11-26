---
name: kymograph-axial
description: >-
  Extract kymographs along a supported posterior-to-anterior anatomical axis
  in Clock Explorer microscopy movies or stacks. Choose a straight or curved
  finite-width corridor, including one-sided dorsal or fixed-reference sampling.
  For center-to-periphery waves, use kymograph-radial.
---

# Axial kymograph extraction

Read the project's `AGENTS.md`, the [shared extraction guide](../../../docs/kymograph-extraction.md)
and the relevant sections of the [axial guide](../../../docs/kymograph-axial.md).
The shared guide covers calibration, sampling, filtering, masks, comparisons
and the measurement handoff. Both methods are under active calibration.

## Choose the axial corridor

- Establish P/A from anatomy or documented labels for the measured interval.
  Image orientation and wave direction alone are insufficient. A supported
  regional P→A direction can coexist with approximate endpoints. If polarity
  remains unresolved, use neutral image coordinates.
- Review origin, direction and endpoint separately. Use a straight strip
  where its full width stays in the intended corridor. If the tissue bends,
  follow a reviewed curve, sample by physical arc length and check its
  transverse normals for folds and adjacent tissue.
- For one-sided dorsal footage, use the clearer corridor in native image
  coordinates. A reviewed seam can guide structural tracking. Constrain
  motion with keyframes, inspect forward/backward disagreement and check
  that the full strip stays on the chosen side.
- For a [growth view](../../../docs/kymograph-extraction.md#final-frame-reference-for-a-growth-view),
  compare both tissue ends against an independent structural landmark after
  registration. Record where coverage changes (A, P, both, or unresolved).
- For a growth view with a fixed P origin (Aulehla 2008 Movies 1 and 2),
  set zero at the visible final-frame tail tip in registered coordinates.
  Sample each frame through its own traced A endpoint. Measure arc length
  from the fixed P, including any unsampled P-side gap. Size the matrix and
  the vertical axis to the largest valid distance across all frames. Leave
  unsupported bins missing. Check that each solid video ROI and the last
  valid bin in its column reach the traced A end within the sampling resolution.
  Capping the matrix at the final-frame length can truncate earlier wave peaks.
- For fixed-length sampling, set both reference endpoints and the calibrated
  arc length once. Only the supported part of the strip changes by frame.

## Worked cases

- [Masamizu Movie 2](references/masamizu-2006.md) uses a fixed image strip
  with reviewed overall polarity and unresolved framewise registration.
- [Lauschke Video 1](references/lauschke-2013.md) follows a curved, inward
  corridor with fixed A/P references.
- [Sonnen Movie S1](../../../docs/kymograph-axial.md#dorsal-right-side-sampling-sonnen-movie-s1)
  follows the image-right half with final-frame A/P references.

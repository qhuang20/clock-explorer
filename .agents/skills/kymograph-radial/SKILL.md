---
name: kymograph-radial
description: >-
  Extract center-to-periphery kymographs along a finite-width ray in Clock
  Explorer microscopy movies or stacks. Review wavefront or geometric origin
  evidence, outward direction, and per-frame supported extent. For a straight
  or curved anatomical AP corridor, use kymograph-axial.
---

# Radial kymograph extraction

Read the project's `AGENTS.md`, the [shared extraction guide](../../../docs/kymograph-extraction.md)
and the relevant sections of the [radial guide](../../../docs/kymograph-radial.md).
The shared guide covers calibration, sampling, filtering, masks, comparisons
and the measurement handoff. Both methods are under active calibration.

## Choose the origin and ray

- Check the preparation and observed fronts before choosing an outward ray.
  A round silhouette or top view alone is insufficient. Record the origin as
  a deposited ROI, mapped illustrated line, multi-frame wavefront estimate,
  reviewed inner reference or geometric proxy.
- A dark core can seed a hypothesis. Confirm a wavefront center using arcs
  at distinct times, and review sensitivity to the time window and angular
  sector. For a moving geometric proxy, check the outer envelope and center
  trajectory for crop effects and changing notches. An envelope can bridge
  gaps with unresolved inner occupancy.
- Select the ray direction and review the full-width support independently
  of the origin. During spreading, an early endpoint can become interior.
  Reassess support when extending or rotating the ray and record any change
  in coverage policy. Use the dataset's distance grid and keep missing
  positions explicit. The last supported sample can move along the ray.
- Use center/periphery labels unless the measured interval supports regional
  P/A. Keep the origin's geometry, anatomical identity and interpretation as
  a wave source distinct. This method samples one strip. Annular averages
  define a different measurement.

## Worked cases

- [Lauschke Videos 2, 5 and 6](references/lauschke-2013.md) distinguish an
  illustrated line, wavefront-fitted origins and a paired reporter.
- [Sonnen Movies S2 and S3](references/sonnen-2018.md#current-selections)
  illustrate a fixed inner reference and a moving geometric origin. Both
  use frame-specific supported endpoints in the ROI display.

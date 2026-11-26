# SPDX-License-Identifier: MIT
"""Mask boundaries, channel identity and absence of time mixing in the control."""

import importlib.util
from pathlib import Path
import sys
import unittest

AVAILABLE = all(
    importlib.util.find_spec(m) for m in ("numpy", "scipy", "av", "matplotlib")
)
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    from compare_lauschke_video5_spatial import masked_gaussian_frame, spatial_control
    from extract_lauschke_radial import sample_radial


@unittest.skipUnless(AVAILABLE, "requires optional scientific analysis environment")
class Video5SpatialTests(unittest.TestCase):
    def test_excluded_bright_background_does_not_bleed_and_constant_tissue_is_not_diluted(
        self,
    ):
        mask = np.zeros((70, 80), bool)
        mask[20:50, 20:60] = True
        signal = np.where(mask, 7.0, 1e9)
        smooth = masked_gaussian_frame(signal, mask, 4.0)
        np.testing.assert_allclose(smooth[mask], 7.0, rtol=0, atol=4e-15)
        self.assertTrue(np.isnan(smooth[0, 0]))
        self.assertTrue(
            np.isnan(masked_gaussian_frame(signal, np.zeros_like(mask), 4.0)).all()
        )

    def test_green_only_per_frame_filter_preserves_zeros_missingness_and_width_counts(
        self,
    ):
        frames = np.zeros((3, 130, 140, 3), float)
        frames[..., 0] = 1e6
        frames[..., 2] = 2e6
        frames[1, 50, 50, 1] = 255
        masks = np.zeros((3, 130, 140), bool)
        masks[:, 25:105, 25:110] = True
        origins = np.tile([40.0, 40.0], (3, 1))
        before = frames.copy()
        raw, counts = sample_radial(frames, origins, masks)
        smooth, smooth_counts = spatial_control(
            frames, origins, masks, sigma_um=3.0, um_per_px=1.0
        )
        np.testing.assert_array_equal(counts, smooth_counts)
        np.testing.assert_array_equal(np.isfinite(raw), np.isfinite(smooth))
        self.assertGreater(np.nanmax(smooth[:, 1]), 0.0)
        np.testing.assert_array_equal(smooth[np.isfinite(smooth[:, 0]), 0], 0.0)
        np.testing.assert_array_equal(smooth[np.isfinite(smooth[:, 2]), 2], 0.0)
        np.testing.assert_array_equal(frames, before)
        self.assertTrue(np.isnan(smooth[-1]).all())

    def test_missing_pixels_inside_mask_are_ignored_instead_of_zero_filled(self):
        signal = np.full((50, 50), 9.0)
        signal[24:27, 24:27] = np.nan
        smooth = masked_gaussian_frame(signal, np.ones_like(signal, bool), 2.0)
        np.testing.assert_allclose(smooth, 9.0, rtol=0, atol=1e-12)
        with self.assertRaises(ValueError):
            masked_gaussian_frame(signal, np.ones((2, 2)), 2.0)
        with self.assertRaises(ValueError):
            masked_gaussian_frame(signal, np.ones_like(signal), 0.0)


if __name__ == "__main__":
    unittest.main()

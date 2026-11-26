# SPDX-License-Identifier: MIT
"""A GFP construct can be red in a published movie; retain channel and masking."""

import importlib.util
from pathlib import Path
import sys
import unittest

AVAILABLE = all(importlib.util.find_spec(m) for m in ("numpy", "scipy", "av"))
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    from extract_lauschke_mesp2 import extract_red
    from compare_lauschke_video5_spatial import spatial_control


@unittest.skipUnless(AVAILABLE, "requires optional scientific analysis environment")
class Mesp2ChannelTests(unittest.TestCase):
    def test_red_signal_is_not_replaced_by_gfp_named_green_or_temporal_mixing(self):
        frames = np.zeros((3, 130, 140, 3), float)
        frames[..., 1] = 170.0
        frames[..., 2] = 220.0
        frames[1, ..., 0] = 37.0
        masks = np.zeros((3, 130, 140), bool)
        masks[:, 25:105, 25:110] = True
        origins = np.tile([40.0, 40.0], (3, 1))
        before = frames.copy()
        values, counts = extract_red(frames, origins, masks)
        self.assertTrue(np.isfinite(values[0]).all())
        for i, expected in enumerate([0.0, 37.0, 0.0]):
            np.testing.assert_allclose(
                values[np.isfinite(values[:, i]), i], expected, rtol=0, atol=1e-12
            )
        self.assertTrue(np.isnan(values[-1]).all())
        self.assertTrue((counts[-1] == 0).all())
        np.testing.assert_array_equal(frames, before)

    def test_red_spatial_control_retains_missingness_and_never_mixes_time_or_green(
        self,
    ):
        frames = np.zeros((3, 130, 140, 3), float)
        frames[..., 1] = 1e6
        frames[..., 2] = 2e6
        frames[1, 50, 50, 0] = 255.0
        masks = np.zeros((3, 130, 140), bool)
        masks[:, 25:105, 25:110] = True
        origins = np.tile([40.0, 40.0], (3, 1))
        raw, counts = extract_red(frames, origins, masks)
        smooth, new_counts = spatial_control(
            frames, origins, masks, sigma_um=3.0, um_per_px=1.0, channel_index=0
        )
        np.testing.assert_array_equal(counts, new_counts)
        np.testing.assert_array_equal(np.isfinite(raw), np.isfinite(smooth))
        self.assertGreater(np.nanmax(smooth[:, 1]), 0.0)
        self.assertLess(np.nanmax(smooth[:, 1]), np.nanmax(raw[:, 1]))
        for i in [0, 2]:
            np.testing.assert_array_equal(smooth[np.isfinite(smooth[:, i]), i], 0.0)
        with self.assertRaises(ValueError):
            spatial_control(frames, origins, masks, channel_index=3)

    def test_a_bright_disconnected_island_does_not_extend_the_shared_strip(self):
        frames = np.zeros((1, 220, 220, 3))
        frames[..., 0] = 11.0
        mask = np.zeros((1, 220, 220), bool)
        mask[:, 20:100, 20:100] = True
        mask[:, 140:210, 140:210] = True
        frames[:, 140:210, 140:210, 0] = 255.0
        values, counts = extract_red(frames, np.array([[40.0, 40.0]]), mask)
        self.assertLess(np.flatnonzero(np.isfinite(values[:, 0]))[-1], 100)
        self.assertLess(np.nanmax(values), 12.0)
        self.assertTrue((counts[150:] == 0).all())


if __name__ == "__main__":
    unittest.main()

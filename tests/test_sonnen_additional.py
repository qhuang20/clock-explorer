# SPDX-License-Identifier: MIT
"""Scientific invariants of the two source-specific additional adapters."""

import importlib.util
from pathlib import Path
import sys
import unittest

AVAILABLE = all(importlib.util.find_spec(m) for m in ["numpy", "scipy", "av", "PIL"])
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    from extract_sonnen_additional import (
        experiment_clock,
        geometry,
        image_validity,
        sample_image,
    )


@unittest.skipUnless(AVAILABLE, "requires the optional scientific environment")
class AdditionalSonnenTests(unittest.TestCase):
    def test_source_clock_retains_decimal_offsets_not_playback_fps(self):
        clock = experiment_clock("s1", 88)
        self.assertEqual(clock[77], 12.84)
        self.assertEqual(clock[86], 14.34)
        self.assertEqual(clock[-1], 14.5)
        self.assertTrue(np.all(np.diff(clock) > 0))
        self.assertAlmostEqual(experiment_clock("s3", 111)[-1], 18 + 20 / 60)
        with self.assertRaises(ValueError):
            experiment_clock("s1", 87)

    def test_sampling_keeps_real_zeros_and_rejects_partial_width(self):
        image = np.zeros((30, 30))
        valid = np.ones_like(image, dtype=bool)
        path = np.array([[10.0, 10.0], [10.0, 1.0]])
        values, counts = sample_image(image, path, np.array([0.0, 1.0]), 6, valid)
        self.assertEqual(values[0], 0)
        self.assertTrue(np.isnan(values[1]))
        self.assertEqual(counts[0], 7)
        self.assertLess(counts[1], 7)

    def test_image_filter_is_mask_aware_and_has_no_cross_frame_input(self):
        valid = np.ones((30, 30), dtype=bool)
        valid[:5] = False
        image = np.full((30, 30), 7.0)
        image[:5] = 255
        value, _ = sample_image(
            image, np.array([[15.0, 8.0]]), np.array([1.0, 0.0]), 4, valid, 3
        )
        self.assertAlmostEqual(value[0], 7)

    def test_source_annotations_are_excluded_without_dark_pixel_threshold(self):
        mask = image_validity("s3", (512, 512))
        self.assertFalse(mask[20, 20])  # dye inset
        self.assertFalse(mask[470, 450])  # scale bar
        self.assertTrue(mask[285, 235])  # includes low/zero reporter values

    def test_manual_and_fixed_origins_remain_distinct(self):
        p, u, _ = geometry("s1", 88)
        self.assertTrue(np.all(u[:, 1] < 0))  # source anteriorward direction
        self.assertGreater(np.linalg.norm(p[-1] - p[0]), 100)
        np.testing.assert_allclose(np.linalg.norm(u, axis=1), 1)
        p, u, extent = geometry("s3", 111)
        np.testing.assert_array_equal(p, np.tile([235.0, 290.0], (111, 1)))
        self.assertLess(extent[0], extent[-1])


if __name__ == "__main__":
    unittest.main()

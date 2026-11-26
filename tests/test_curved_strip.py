# SPDX-License-Identifier: MIT
"""Geometry, physical distance, averaging and missingness of a moving curve."""

import importlib.util
from pathlib import Path
import sys
import unittest

AVAILABLE = all(importlib.util.find_spec(m) for m in ("numpy", "scipy"))
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    from curved_strip import arc_length_path, sample_strip


@unittest.skipUnless(AVAILABLE, "requires optional scientific analysis environment")
class CurvedStripTests(unittest.TestCase):
    def test_straight_limit_has_physical_distance_and_width_mean(self):
        xy, normal, length = arc_length_path(
            [[30, 70], [130, 70]], np.arange(21.0), 0.5
        )
        frame = np.tile(np.arange(180.0)[None, :], (160, 1))
        values, counts, valid = sample_strip(frame, xy, normal, 20)
        np.testing.assert_allclose(values, 30 + 2 * np.arange(21.0), atol=1e-12)
        np.testing.assert_array_equal(counts, 21)
        self.assertTrue(valid.all())
        self.assertAlmostEqual(length, 50)

    def test_arc_length_is_not_chord_or_length_normalization(self):
        angles = np.linspace(0, np.pi / 2, 13)
        points = np.stack([80 + 40 * np.cos(angles), 80 + 40 * np.sin(angles)], axis=-1)
        distances = np.arange(31.0)
        xy, normal, length = arc_length_path(points, distances, 0.5)
        self.assertAlmostEqual(length, 10 * np.pi, delta=0.01)
        expected = 80 + 40 * np.stack(
            [np.cos(distances / 20), np.sin(distances / 20)], axis=-1
        )
        # Natural cubic endpoints approximate a circle; error <0.04 source px.
        np.testing.assert_allclose(xy, expected, atol=0.04)
        np.testing.assert_allclose(np.linalg.norm(normal, axis=1), 1, atol=1e-12)

    def test_rigid_rotation_and_translation_preserve_sampling(self):
        points = np.array([[30, 80], [55, 65], [80, 70], [110, 100]], float)
        xy, normal, _ = arc_length_path(points, np.arange(61.0), 1)
        y, x = np.indices((180, 180))
        frame = 2 * x + y
        values, _, _ = sample_strip(frame, xy, normal, 12)
        rotated = np.rot90(frame)
        rotated_points = np.stack([points[:, 1], 179 - points[:, 0]], axis=-1)
        rxy, rn, _ = arc_length_path(rotated_points, np.arange(61.0), 1)
        result, _, _ = sample_strip(rotated, rxy, rn, 12)
        np.testing.assert_allclose(result, values, atol=2e-12)
        moved = np.roll(np.roll(frame, 7, axis=0), 4, axis=1)
        mxy, mn, _ = arc_length_path(points + [4, 7], np.arange(61.0), 1)
        result, _, _ = sample_strip(moved, mxy, mn, 12)
        np.testing.assert_allclose(result, values, atol=2e-12)

    def test_curve_follows_bent_signal_corridor_while_chord_leaves_it(self):
        angles = np.linspace(0, np.pi / 2, 17)
        points = np.stack([30 + 60 * np.cos(angles), 30 + 60 * np.sin(angles)], axis=-1)
        xy, normal, length = arc_length_path(points, np.linspace(0, 90, 91), 1)
        yy, xx = np.indices((140, 140))
        frame = (np.abs(np.hypot(xx - 30, yy - 30) - 60) < 5) * 100.0
        curved, _, _ = sample_strip(frame, xy, normal, 4)
        straight, sn, _ = arc_length_path(
            [points[0], points[-1]], np.linspace(0, 80, 81), 1
        )
        chord, _, _ = sample_strip(frame, straight, sn, 4)
        self.assertGreater(curved.min(), 99)
        self.assertLess(chord[40], 1)
        self.assertGreater(length, np.linalg.norm(points[-1] - points[0]))

    def test_true_zeros_and_masked_tail_remain_distinct(self):
        xy, norm, _ = arc_length_path([[20, 40], [100, 40]], np.arange(81.0), 1)
        region = np.ones((120, 120), bool)
        region[:, 70:] = False
        values, counts, valid = sample_strip(
            np.zeros((120, 120)), xy, norm, 8, valid_region=region
        )
        self.assertTrue(np.all(values[:50] == 0))
        self.assertTrue(np.isnan(values[50:]).all())
        self.assertTrue(np.all(counts[50:] == 0))
        self.assertFalse(valid[50:].any())

    def test_requested_distance_beyond_reviewed_curve_is_missing(self):
        xy, norm, length = arc_length_path([[20, 40], [40, 40]], np.arange(31.0), 1)
        values, _, _ = sample_strip(np.ones((100, 100)), xy, norm, 4)
        self.assertEqual(length, 20)
        self.assertTrue(np.isnan(xy[21:]).all())
        self.assertTrue(np.isnan(values[21:]).all())


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: MIT
"""Protect coordinate registration and missing-data behavior of ROI comparisons."""

import importlib.util
from pathlib import Path
import sys
import unittest

AVAILABLE = all(importlib.util.find_spec(m) for m in ("numpy", "scipy", "av"))
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    from extract_lauschke_author_line import (
        mapped_line,
        sample_line,
        validate_registration,
    )


@unittest.skipUnless(AVAILABLE, "requires optional scientific analysis environment")
class IllustratedLineTests(unittest.TestCase):
    def test_registered_anchor_and_direction_follow_common_motion(self):
        registration = {
            "reference_transform_panel_to_video": [[2, 0, 10], [0, 2, -4]],
            "reference_frame_index_0_based": 1,
            "arrow_tail_panel_xy": [20, 30],
            "arrow_tip_panel_xy": [20, 10],
        }
        shifts = np.array([[3, 8], [5, 12], [-2, 13]], float)
        origins, directions, start, tip = mapped_line(registration, shifts)
        np.testing.assert_allclose(start, [50, 56])
        np.testing.assert_allclose(tip, [50, 16])
        np.testing.assert_allclose(origins[1], start)
        np.testing.assert_allclose(origins - origins[1], shifts - shifts[1])
        np.testing.assert_allclose(directions, [[0, -1]] * 3)

    def test_origin_outside_tissue_preserves_missing_prefix_and_true_zero(self):
        # A growing tissue reaches the fixed line later; its origin never moves.
        frames = np.zeros((2, 180, 160), dtype=np.uint8)
        masks = np.zeros_like(frames, dtype=bool)
        masks[1, 30:80, 50:111] = True
        matrix, counts = sample_line(
            frames,
            np.tile([20.0, 50.0], (2, 1)),
            np.tile([1.0, 0.0], (2, 1)),
            np.arange(121.0),
            masks,
            um_per_px=1,
        )
        self.assertTrue(np.isnan(matrix[:, 0]).all())
        self.assertTrue(np.isnan(matrix[:30, 1]).all())
        np.testing.assert_array_equal(matrix[30:91, 1], 0)
        np.testing.assert_array_equal(counts[30:91, 1], 21)
        self.assertTrue(np.isnan(matrix[91:, 1]).all())

    def test_disconnected_islands_do_not_become_one_continuous_profile(self):
        frame = np.full((180, 170), 40, dtype=np.uint8)
        mask = np.zeros(frame.shape, bool)
        mask[30:80, 50:111] = True
        mask[30:80, 125:135] = True
        matrix, _ = sample_line(
            [frame],
            np.array([[20, 50]]),
            np.array([[1, 0]]),
            np.arange(131.0),
            [mask],
            um_per_px=1,
        )
        np.testing.assert_array_equal(matrix[30:91, 0], 40)
        self.assertTrue(np.isnan(matrix[91:, 0]).all())

    def test_registration_uses_correspondences_and_rejects_tampered_transform(self):
        points = np.column_stack([np.arange(120), np.arange(120) % 9])
        registration = {
            "reference_frame_index_0_based": 85,
            "reference_transform_panel_to_video": [[2, 0, 10], [0, 2, -4]],
            "independent_thumbnail_matches": [
                {
                    "frame": 85,
                    "inliers": 120,
                    "median_error_source_px": 0,
                    "panel_inliers": points.tolist(),
                    "video_inliers": (points * 2 + [10, -4]).tolist(),
                }
            ],
        }
        np.testing.assert_array_equal(validate_registration(registration), 0)
        registration["reference_transform_panel_to_video"][0][2] += 10
        with self.assertRaises(ValueError):
            validate_registration(registration)
        registration["reference_transform_panel_to_video"][0][2] -= 10
        registration["independent_thumbnail_matches"][0]["inliers"] = 3
        with self.assertRaises(ValueError):
            validate_registration(registration)


if __name__ == "__main__":
    unittest.main()

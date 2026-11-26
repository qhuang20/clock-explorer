# SPDX-License-Identifier: MIT
"""Check geometry/registration evidence mechanics, not biological identity."""

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
    from review_radial_ap import endpoint_table, checked_mapping, direction_check


@unittest.skipUnless(AVAILABLE, "requires optional scientific analysis environment")
class APReviewTests(unittest.TestCase):
    def test_last_measured_point_does_not_invent_tissue_rim_or_fill_missing_extension(
        self,
    ):
        matrix = np.array([[1.0, 1.0], [2.0, np.nan], [np.nan, np.nan]])
        rows = endpoint_table(
            matrix,
            np.array([0.0, 1.0]),
            np.array([0.0, 10.0, 20.0]),
            np.tile([100.0, 100.0], (2, 1)),
            np.tile([0.0, -1.0], (2, 1)),
            1.0,
        )
        self.assertEqual(rows[0]["last_valid_um"], 10.0)
        self.assertEqual(rows[0]["endpoint_xy"], [100.0, 90.0])
        self.assertEqual(rows[1]["last_valid_um"], 0.0)
        self.assertTrue(np.isnan(matrix[-1]).all())

    def test_correspondence_checks_reject_reflection_degeneracy_or_changed_mapping(
        self,
    ):
        yy, xx = np.mgrid[:6, :6]
        a = np.c_[xx.ravel() * 25.0, yy.ravel() * 25.0]
        mat = np.array([[5.26, 0, 9.0], [0, 5.26, -3.0]])
        record = {
            "crop_points": a,
            "frame_points": a @ mat[:, :2].T + mat[:, 2],
            "affine_crop_to_frame": mat,
        }
        _, errors = checked_mapping(record)
        np.testing.assert_allclose(errors, 0.0)
        for bad in [
            np.array([[-5.26, 0, 9.0], [0, 5.26, -3.0]]),
            mat * 0,
            mat + np.array([[0, 0, 50], [0, 0, 0]]),
        ]:
            with self.assertRaises(ValueError):
                checked_mapping({**record, "affine_crop_to_frame": bad})

    def test_direction_can_target_a_regional_sector_without_coinciding_with_its_landmark(
        self,
    ):
        p = direction_check(
            np.array([0.0, 0.0]), np.array([-2.0, -2.0]), np.array([-3.0, -4.0])
        )
        self.assertGreater(p["cosine_toward_documented_anterior_region"], 0.9)
        self.assertGreater(p["target_projection_source_px"], 0.0)
        with self.assertRaises(ValueError):
            direction_check(
                np.array([0.0, 0.0]), np.array([0.0, 0.0]), np.array([-3.0, -4.0])
            )

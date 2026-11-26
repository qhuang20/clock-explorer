# SPDX-License-Identifier: MIT
"""Scientific failure cases in the paper-comparison adapter."""

import importlib.util
from pathlib import Path
import sys
import unittest

AVAILABLE = all(
    importlib.util.find_spec(m) for m in ["numpy", "scipy", "av", "cv2", "PIL"]
)
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    from compare_sonnen_published import filtered_s2_profile, supported_match


@unittest.skipUnless(AVAILABLE, "requires optional scientific environment")
class SonnenPaperComparisonTests(unittest.TestCase):
    def test_zero_residual_from_two_correspondences_is_not_a_registration(self):
        row = {
            "inliers": 2,
            "median_source_px": 0,
            "span_crop_xy": [130, 75],
            "scale_crop_to_native": 5.2,
        }
        self.assertFalse(supported_match(row))
        row["inliers"] = 168
        self.assertTrue(supported_match(row))
        row["span_crop_xy"] = [3, 7]
        self.assertFalse(supported_match(row))

    def test_spatial_control_preserves_constant_signal_and_true_zeros(self):
        path = np.array([[180.0, 180.0], [200.0, 200.0]])
        normal = np.array([1.0, 0.0])
        for level in [0, 37]:
            frame = np.full((400, 400, 3), level, np.uint8)
            frame[:75] = 255  # Excluded annotation; not a signal observation.
            values, counts = filtered_s2_profile(frame, path, normal)
            np.testing.assert_allclose(values, level, atol=1e-10)
            np.testing.assert_array_equal(counts, [41, 41])
        with self.assertRaises(ValueError):
            filtered_s2_profile(frame, path, normal, sigma_um=-1)


if __name__ == "__main__":
    unittest.main()

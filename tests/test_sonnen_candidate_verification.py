# SPDX-License-Identifier: MIT
"""Independent sampler verification, separate from producer implementations."""

import importlib.util
from pathlib import Path
import sys
import unittest

AVAILABLE = all(importlib.util.find_spec(m) for m in ["numpy", "av"])
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    from verify_sonnen_candidates import cap_profile, interpolate, strip_profile


@unittest.skipUnless(AVAILABLE, "requires optional scientific environment")
class IndependentSamplerTests(unittest.TestCase):
    def test_bilinear_reproduces_linear_field_and_preserves_zero(self):
        y, x = np.indices((8, 9))
        image = 2 * x + 3 * y
        xy = np.array([[0, 0], [1.25, 2.5], [5.75, 6.1]])
        np.testing.assert_allclose(interpolate(image, xy), 2 * xy[:, 0] + 3 * xy[:, 1])
        self.assertEqual(interpolate(image, xy)[0], 0)

    def test_unsupported_coordinates_are_missing_including_nonfinite(self):
        xy = np.array([[-0.1, 0], [4, 2], [2, 4], [np.nan, 2]])
        self.assertTrue(np.isnan(interpolate(np.ones((5, 5)), xy)).all())

    def test_cross_strip_mean_and_partial_support_are_explicit(self):
        y, x = np.indices((9, 9))
        image = 10 * x + y
        path = np.array([[3.0, 4.0], [4.0, 4.0]])
        normal = np.array([0.0, 1.0])
        offsets = np.arange(-2, 3)
        support = np.ones_like(image, bool)
        support[:4] = False
        strict, counts = strip_profile(image, path, normal, offsets, support)
        partial, _ = strip_profile(image, path, normal, offsets, support, minimum=3)
        np.testing.assert_array_equal(counts, [3, 3])
        self.assertTrue(np.isnan(strict).all())
        np.testing.assert_allclose(partial, [35, 45])

    def test_physical_cap_preserves_origin_zero_and_valid_zero_measurement(self):
        profile = np.array([0.0, 5.0, 3.0, 9.0])
        distances = np.array([0.0, 2.0, 4.0, 6.0])
        result = cap_profile(profile, distances, 2, 2)
        np.testing.assert_array_equal(result[:3], profile[:3])
        self.assertTrue(np.isnan(result[3]))
        np.testing.assert_array_equal(profile, [0.0, 5.0, 3.0, 9.0])
        with self.assertRaises(ValueError):
            cap_profile(profile, distances, 0, 2)


if __name__ == "__main__":
    unittest.main()

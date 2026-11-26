# SPDX-License-Identifier: MIT
"""Safeguards for the review-only fixed-reference geometry pilot."""

import importlib.util
from pathlib import Path
import sys
import unittest

AVAILABLE = all(importlib.util.find_spec(m) for m in ("numpy", "scipy"))
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    from review_video1_stable_roi import rigid_fit, transform, coverage
    from review_video1_inward_roi import inward_candidate, minimum_jacobian


@unittest.skipUnless(AVAILABLE, "requires optional scientific analysis environment")
class StableRoiTests(unittest.TestCase):
    def test_camera_jump_is_recovered_without_scaling_distances(self):
        source = np.array([[10, 20], [30, 80], [100, 25], [70, 120], [120, 140]], float)
        angle = np.deg2rad(13)
        rotation = np.array(
            [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
        )
        target = source @ rotation.T + [4, 115]
        matrix = rigid_fit(source, target)
        np.testing.assert_allclose(transform(source, matrix), target, atol=1e-12)
        np.testing.assert_allclose(
            matrix[:2, :2].T @ matrix[:2, :2], np.eye(2), atol=1e-12
        )
        self.assertAlmostEqual(np.linalg.det(matrix[:2, :2]), 1)
        np.testing.assert_allclose(
            transform(target, np.linalg.inv(matrix)), source, atol=1e-12
        )

    def test_growth_cannot_be_absorbed_as_scale_or_reflection(self):
        points = np.array([[10, 20], [30, 80], [100, 25], [70, 120], [120, 140]], float)
        for target in [1.3 * points, points * [-1, 1]]:
            matrix = rigid_fit(points, target)
            np.testing.assert_allclose(
                np.linalg.svd(matrix[:2, :2])[1], [1, 1], atol=1e-12
            )
            self.assertAlmostEqual(np.linalg.det(matrix[:2, :2]), 1)
            self.assertGreater(np.linalg.norm(transform(points, matrix) - target), 1)

    def test_prospective_reference_extension_is_not_supported_tissue(self):
        mask = np.zeros((100, 120), bool)
        mask[20:80, 30:90] = True
        path = np.column_stack([np.arange(10, 111), np.full(101, 50.0)])
        normals = np.tile([0.0, 1.0], (101, 1))
        supported = coverage(path, normals, mask)
        np.testing.assert_array_equal(supported, (path[:, 0] >= 30) & (path[:, 0] < 90))
        self.assertFalse(supported[0])
        self.assertFalse(supported[-1])

    def test_inward_adjustment_keeps_reference_ends_and_measurement_scale(self):
        path = np.column_stack([np.linspace(400, 40, 181), np.full(181, 200.0)])
        normals = np.tile([0.0, -1.0], (181, 1))
        before = path.copy()
        shifted, norm, distance = inward_candidate(path, normals, 20)
        np.testing.assert_allclose(shifted[[0, -1]], path[[0, -1]], atol=1e-10)
        np.testing.assert_array_equal(path, before)
        # Cubic reparameterization can overshoot the nominal offset slightly.
        self.assertAlmostEqual(shifted[:, 1].min(), 180, delta=0.05)
        # Endpoints stay put; the new curved path is measured, not stretched
        # onto the original length or forced to a [0,1] measurement axis.
        self.assertGreater(distance[-1], 360 * 100 / 103)
        np.testing.assert_allclose(np.linalg.norm(norm, axis=1), 1, atol=1e-12)
        self.assertGreater(minimum_jacobian(shifted, norm), 0)


if __name__ == "__main__":
    unittest.main()

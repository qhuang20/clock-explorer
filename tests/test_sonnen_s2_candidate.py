# SPDX-License-Identifier: MIT
"""S2 diagnostic geometry, native signal and review-artifact invariants."""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

AVAILABLE = all(importlib.util.find_spec(m) for m in ["numpy", "scipy", "av", "PIL"])
ROOT = Path(__file__).resolve().parents[1]
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(ROOT / "analysis"))
    from review_sonnen_s2_candidate import (
        fit_normal_center,
        sample_green_strip,
        strip_geometry,
    )


@unittest.skipUnless(AVAILABLE, "requires optional scientific environment")
class DiagnosticGeometryTests(unittest.TestCase):
    def test_radial_gradient_lines_recover_synthetic_center(self):
        rng = np.random.default_rng(83)
        center = np.array([4.5, -2.25])
        theta = np.linspace(-np.pi, np.pi, 200, endpoint=False)
        radius = rng.uniform(10, 30, len(theta))
        vectors = np.c_[np.cos(theta), np.sin(theta)]
        points = center + radius[:, None] * vectors
        gradients = vectors * rng.uniform(0.5, 4, len(theta))[:, None]
        result, metrics = fit_normal_center(points, gradients)
        np.testing.assert_allclose(result, center, atol=1e-12)
        self.assertLess(metrics["weighted_line_rms_px"], 1e-12)

    def test_parallel_gradient_lines_do_not_claim_two_dimensional_center(self):
        points = np.c_[np.arange(10), np.arange(10)]
        with self.assertRaises(ValueError):
            fit_normal_center(points, np.tile([1, 0], (10, 1)))
        with self.assertRaises(ValueError):
            fit_normal_center(points, np.zeros_like(points))

    def test_native_green_and_transverse_mean_are_not_rgb_or_axis_averages(self):
        y, x = np.indices((12, 14))
        frame = np.stack(
            [np.full_like(x, 200), 2 * x + 3 * y, np.full_like(x, 250)], axis=-1
        )
        path = np.array([[4.5, 2.25], [4.5, 5.5]])
        mean, count, retained, valid = sample_green_strip(
            frame, path, np.tile([1, 0], (2, 1)), [-1, 0, 1], 3
        )
        np.testing.assert_allclose(mean, 2 * path[:, 0] + 3 * path[:, 1], atol=1e-12)
        np.testing.assert_array_equal(count, [3, 3])
        self.assertTrue(retained.all() and valid.all())

    def test_measured_zero_and_partial_fov_absence_remain_distinct(self):
        path = np.array([[0, 2], [-0.5, 2], [-2, 2]])
        mean, count, retained, valid = sample_green_strip(
            np.zeros((6, 6, 3)), path, np.tile([1, 0], (3, 1)), [-1, 0, 1], 2
        )
        np.testing.assert_array_equal(count, [2, 1, 0])
        np.testing.assert_array_equal(retained, [True, False, False])
        self.assertEqual(mean[0], 0)
        self.assertTrue(np.isnan(mean[1:]).all())
        np.testing.assert_array_equal(valid.sum(axis=1), count)

    def test_retained_motion_changes_both_endpoints_without_scaling_path(self):
        shifts = np.array([[0, 0], [-11.25, 4.5]])
        path, normals, origins, directions = strip_geometry(
            [530, 450], shifts, [0, 3.2, 7.5]
        )
        np.testing.assert_allclose(path[1] - path[0], np.tile(shifts[1], (3, 1)))
        np.testing.assert_allclose(path[:, -1] - origins, directions * 7.5)
        np.testing.assert_allclose(np.linalg.norm(normals, axis=-1), 1)
        np.testing.assert_allclose(
            np.sum(normals * directions[:, None, :], axis=-1), 0, atol=1e-14
        )


DATA = ROOT / "assets/data/derived/sonnen-2018/s2-candidate-review"


@unittest.skipUnless(
    AVAILABLE and (DATA / "review-provenance.json").is_file(),
    "requires optional local S2 review output",
)
class CandidateArtifactTests(unittest.TestCase):
    def test_candidate_retains_source_clock_distances_and_width_validity(self):
        with (
            np.load(DATA / "candidate-kymograph.npz") as new,
            np.load(
                ROOT / "assets/data/derived/sonnen-2018/movie-s2-kymograph.npz"
            ) as old,
        ):
            self.assertEqual(new["intensity"].shape, (354, 155))
            np.testing.assert_array_equal(new["time_h"], old["time_h"])
            np.testing.assert_array_equal(new["position_um"], old["position_um"])
            np.testing.assert_array_equal(new["shifts_xy"], old["shifts_xy"])
            np.testing.assert_array_equal(
                new["valid_width_counts"], new["sample_fov_valid_mask"].sum(axis=-1).T
            )
            np.testing.assert_array_equal(
                np.isfinite(new["intensity"]), new["measurement_valid_mask"]
            )
            np.testing.assert_allclose(new["path_xy"][:, 0], new["origins_xy"])
            np.testing.assert_allclose(
                np.linalg.norm(new["path_xy"][:, -1] - new["path_xy"][:, 0], axis=-1),
                new["position_px"][-1],
            )
            self.assertEqual(new["minimum_valid_count"].item(), 33)
            self.assertEqual(len(new["width_offsets_px"]), 41)

    def test_control_does_not_promote_diagnostic_fit_or_change_baseline(self):
        report = json.loads((DATA / "review-provenance.json").read_text())
        baseline = ROOT / "assets" / report["baseline_matrix"]["path"]
        self.assertEqual(
            hashlib.sha256(baseline.read_bytes()).hexdigest(),
            report["baseline_matrix"]["sha256"],
        )
        self.assertIn("adoption deferred", report["status"])
        self.assertFalse(
            report["geometry_diagnostic"]["variation_ranges_are_confidence_intervals"]
        )
        self.assertGreater(
            report["geometry_diagnostic"]["upper_sector_shift_from_default_px"], 100
        )
        self.assertEqual(report["measurement"]["valid_width_count_min_max"], [41, 41])
        self.assertIn("FOV only", report["measurement"]["validity"])

    def test_overlay_is_bound_to_candidate_matrix_and_preserves_full_clock(self):
        overlay = json.loads((DATA / "video-roi.json").read_text())
        self.assertEqual(overlay["dataset_id"], "sonnen-2018")
        self.assertEqual(overlay["video_id"], "movie-s2")
        self.assertEqual(
            overlay["geometry_input_sha256"],
            hashlib.sha256((DATA / "candidate-kymograph.npz").read_bytes()).hexdigest(),
        )
        self.assertEqual(len(overlay["frames"]), 155)
        self.assertEqual(overlay["frame_starts_s"][-1], 15.4)
        self.assertEqual(overlay["frames"][-1]["experiment_h"], 25.69)
        self.assertEqual(overlay["direction_labels"], ["C*", "outward"])


if __name__ == "__main__":
    unittest.main()

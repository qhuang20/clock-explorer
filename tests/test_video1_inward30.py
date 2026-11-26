# SPDX-License-Identifier: MIT
"""Fixed-reference extraction: missing prefixes, gaps and native sampling."""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/video1-inward30-kymograph"
AVAILABLE = all(importlib.util.find_spec(m) for m in ("numpy", "scipy"))
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(ROOT / "analysis"))
    from curved_strip import sample_strip
    from extract_video1_inward30 import resample_saved_curve, to_source_geometry
    from review_video1_stable_roi import SCALE, transform


@unittest.skipUnless(AVAILABLE, "requires optional scientific environment")
class InwardExtractionTests(unittest.TestCase):
    def test_last_supported_run_retains_missing_prefix_and_true_zeros_without_bridging(
        self,
    ):
        frame = np.zeros((100, 120))
        region = np.zeros_like(frame, bool)
        region[20:80, 25:30] = True
        region[20:80, 60:90] = True
        path = np.column_stack([np.arange(20.0, 101.0), np.full(81, 50.0)])
        normal = np.tile([0.0, 1.0], (81, 1))
        old, _, _ = sample_strip(frame, path, normal, 20, valid_region=region)
        self.assertTrue(np.isnan(old).all())  # Existing origin-connected default.
        values, counts, valid = sample_strip(
            frame,
            path,
            normal,
            20,
            valid_region=region,
            coverage_policy="last_supported_run",
        )
        expected = (path[:, 0] >= 60) & (path[:, 0] < 90)
        np.testing.assert_array_equal(valid, expected)
        np.testing.assert_array_equal(values[expected], 0)
        self.assertTrue(np.isnan(values[~expected]).all())
        self.assertTrue(
            (counts[5:10] >= 16).all()
        )  # Earlier island excluded, not bridged.
        absent, _, _ = sample_strip(
            frame,
            path,
            normal,
            20,
            valid_region=np.zeros_like(region),
            coverage_policy="last_supported_run",
        )
        self.assertTrue(np.isnan(absent).all())

    def test_inverse_maps_normals_without_translation_and_preserves_native_values(self):
        source = np.array([[40.0, 50.0], [39, 50], [38, 50], [37, 50]])
        normals = np.tile([0.0, -1.0], (4, 1))
        angle = 0.4
        matrix = np.eye(3)
        matrix[:2, :2] = [
            [np.cos(angle), -np.sin(angle)],
            [np.sin(angle), np.cos(angle)],
        ]
        matrix[:2, 2] = [20, 115]
        ref = transform(source, matrix)
        rn = normals @ matrix[:2, :2].T
        restored, nn = to_source_geometry(ref, rn, matrix)
        np.testing.assert_allclose(restored, source, atol=1e-12)
        np.testing.assert_allclose(nn, normals, atol=1e-12)
        y, x = np.indices((120, 120))
        frame = 2 * x + y
        values, _, _ = sample_strip(frame, restored, nn, 20)
        np.testing.assert_allclose(values, 2 * source[:, 0] + source[:, 1], atol=1e-10)

    def test_saved_path_keeps_physical_scale_and_does_not_extrapolate(self):
        path = np.array([[100, 80], [80, 80], [60, 80]], float)
        normals = np.tile([0.0, -1.0], (3, 1))
        d = np.array([0.0, 10 * SCALE, 20 * SCALE, 40 * SCALE, 41 * SCALE])
        xy, nn, length = resample_saved_curve(path, normals, d)
        np.testing.assert_allclose(xy[:4, 0], [100, 90, 80, 60], atol=1e-12)
        np.testing.assert_allclose(xy[:4, 1], 80, atol=1e-12)
        self.assertAlmostEqual(length, 40 * SCALE)
        self.assertTrue(np.isnan(xy[-1]).all())
        self.assertTrue(np.isnan(nn[-1]).all())


@unittest.skipUnless(
    AVAILABLE and (OUTPUT / "provenance.json").is_file(),
    "requires optional local inward30 review output",
)
class SavedInwardReviewTests(unittest.TestCase):
    def test_time_reference_points_current_primary_and_missingness(self):
        r = json.loads((OUTPUT / "provenance.json").read_text())
        primary = Path(r["current_reference"]["file"])
        self.assertEqual(
            hashlib.sha256(primary.read_bytes()).hexdigest(),
            r["current_reference"]["sha256"],
        )
        with np.load(OUTPUT / "video1-inward30-kymograph.npz") as z:
            self.assertEqual(z["intensity"].shape[1], 126)
            np.testing.assert_array_equal(
                z["measurement_valid_mask"], np.isfinite(z["intensity"])
            )
            np.testing.assert_array_equal(z["time_h"], r["clock"]["time_h"])
            self.assertAlmostEqual(z["time_h"][101] - z["time_h"][100], 0.25)
            self.assertAlmostEqual(z["time_h"][-1], 20.92)
            self.assertTrue(np.isnan(z["intensity"][:140, 0]).all())
            for i, m in enumerate(z["source_to_reference"]):
                np.testing.assert_allclose(
                    transform(z["A_reference_source_xy"][i], m),
                    z["A_ref_xy"],
                    atol=1e-9,
                )
                np.testing.assert_allclose(
                    transform(z["P_reference_source_xy"][i], m),
                    z["P_ref_xy"],
                    atol=1e-9,
                )
                indices = np.flatnonzero(z["measurement_valid_mask"][:, i])
                self.assertTrue((np.diff(indices) == 1).all())
            self.assertTrue((z["A_endpoint_valid_width_counts"] >= 16).all())

    def test_saved_values_reproduce_from_native_pixels_including_split_and_jump(self):
        cache = ROOT / "work/lauschke-paper-method/video1-frames.npy"
        baseline = ROOT / "outputs/video1-stabilized-roi-review/geometry-review.npz"
        if not cache.is_file() or not baseline.is_file():
            self.skipTest("optional source geometry/cache unavailable")
        frames = np.load(cache, mmap_mode="r")
        with (
            np.load(baseline) as b,
            np.load(OUTPUT / "video1-inward30-kymograph.npz") as z,
        ):
            for i in [0, 27, 60, 100, 101, 125]:
                region = b["foreground_masks_original"][i].copy()
                region[:15] = False
                region[-60:] = False
                region[:, :15] = False
                values, counts, valid = sample_strip(
                    frames[i],
                    z["path_xy"][i],
                    z["normals_xy"][i],
                    20,
                    valid_region=region,
                    coverage_policy="last_supported_run",
                )
                np.testing.assert_array_equal(values, z["intensity"][:, i])
                np.testing.assert_array_equal(counts, z["valid_width_counts"][:, i])
                np.testing.assert_array_equal(valid, z["measurement_valid_mask"][:, i])


if __name__ == "__main__":
    unittest.main()

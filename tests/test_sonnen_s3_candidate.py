# SPDX-License-Identifier: MIT
"""Independent invariants for the local S3 angular and coverage controls."""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
AVAILABLE = all(importlib.util.find_spec(m) for m in ["numpy", "scipy", "av", "PIL"])
DATA = ROOT / "assets/data/derived/sonnen-2018/s3-candidate-review"
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(ROOT / "analysis"))
    from review_sonnen_s3_candidate import ORIGIN, apply_extent, sector_geometry


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


@unittest.skipUnless(AVAILABLE, "requires optional scientific environment")
class SectorNumericalTests(unittest.TestCase):
    def test_sector_rotation_preserves_origin_and_physical_distance(self):
        positions = np.arange(0.0, 301.0)
        scale = 100 / 72
        for angle in [-15, 0, 15]:
            path, normal = sector_geometry(positions, scale, angle)
            np.testing.assert_array_equal(path[0], ORIGIN)
            np.testing.assert_allclose(
                np.linalg.norm(np.diff(path, axis=0), axis=1) * scale, 1.0, atol=1e-12
            )
            self.assertAlmostEqual(np.linalg.norm(normal), 1.0)
            self.assertAlmostEqual(
                float(np.dot(path[-1] - path[0], normal)), 0.0, places=10
            )
        left, _ = sector_geometry(positions, scale, -15)
        right, _ = sector_geometry(positions, scale, 15)
        np.testing.assert_allclose(left[:, 0] + right[:, 0], 2 * ORIGIN[0])
        np.testing.assert_allclose(left[:, 1], right[:, 1])

    def test_extent_is_separate_from_values_and_preserves_true_zero(self):
        values = np.array([[0.0, 4.0], [5.0, 0.0], [7.0, 8.0]])
        before = values.copy()
        out = apply_extent(values, np.array([0.0, 1.0, 2.0]), 1.0, np.array([0.5, 1.0]))
        self.assertEqual(out[0, 0], 0.0)
        self.assertEqual(out[1, 1], 0.0)
        self.assertTrue(np.isnan(out[1, 0]))
        self.assertTrue(np.isnan(out[2]).all())
        np.testing.assert_array_equal(values, before)


@unittest.skipUnless(
    AVAILABLE and (DATA / "s3-sector-candidate.npz").is_file(),
    "requires optional local S3 candidate artifacts",
)
class SectorArtifactTests(unittest.TestCase):
    def test_original_values_and_clocks_survive_separate_candidate(self):
        with np.load(DATA / "s3-sector-candidate.npz") as z:
            with np.load(
                ROOT / "assets/data/derived/sonnen-2018/movie-s3/kymograph.npz"
            ) as base:
                for key in ["time_h", "position_um"]:
                    np.testing.assert_array_equal(z[key], base[key])
                np.testing.assert_array_equal(
                    z["baseline_intensity"], base["intensity"]
                )
            self.assertEqual(z["intensity"].shape, (301, 111))
            self.assertEqual(int(np.isnan(z["baseline_intensity"]).sum()), 9609)
            self.assertEqual(float(z["time_h"][-1]), 18 + 20 / 60)
            np.testing.assert_allclose(z["path_xy"][:, 0], np.tile(ORIGIN, (111, 1)))
            self.assertEqual(len(z["width_offsets_px"]), 52)
            np.testing.assert_allclose(z["width_offsets_px"][[0, -1]], [-25.2, 25.2])
            self.assertFalse(z["image_validity_mask"][20, 20])
            self.assertFalse(z["image_validity_mask"][470, 450])
            self.assertTrue(z["image_validity_mask"][290, 235])

    def test_matched_support_is_shared_and_candidate_caps_are_explicit(self):
        with np.load(DATA / "s3-sector-candidate.npz") as z:
            common = np.minimum.reduce(
                [
                    z["coverage_extent_px"],
                    z["current_coverage_extent_px"],
                    z["right_coverage_extent_px"],
                ]
            )
            np.testing.assert_array_equal(common, z["matched_coverage_extent_px"])
            masks = [
                np.isfinite(z[k])
                for k in [
                    "matched_current_intensity",
                    "matched_left_intensity",
                    "matched_right_intensity",
                ]
            ]
            np.testing.assert_array_equal(masks[0], masks[1])
            np.testing.assert_array_equal(masks[0], masks[2])
            expected = (
                z["position_um"][:, None] / z["um_per_px"]
                <= z["coverage_extent_px"][None, :]
            ) & (z["fov_width_counts"] == 52)
            np.testing.assert_array_equal(expected, np.isfinite(z["intensity"]))
            self.assertTrue(
                np.all(z["coverage_extent_px"] <= z["current_coverage_extent_px"])
            )

    def test_hashes_baselines_and_frozen_s1_preserved(self):
        p = json.loads((DATA / "s3-review-provenance.json").read_text())
        self.assertEqual(p["baseline_hashes_before"], p["baseline_hashes_after"])
        for name, h in p["baseline_hashes_before"].items():
            self.assertEqual(sha(ROOT / name), h)
        # S1 hashes describe the peer package at S3 generation time. A later
        # deliberate S1 font-portability revision may change rendered metadata;
        # it must not invalidate the unchanged S3 package or its own baseline.
        snapshot = ROOT / "outputs/sonnen-s3-candidate/s1-frozen-before.json"
        if snapshot.is_file():
            self.assertEqual(
                p["frozen_s1_hashes_preserved"], json.loads(snapshot.read_text())
            )
        self.assertEqual(
            p["script_sha256"], sha(ROOT / "analysis/review_sonnen_s3_candidate.py")
        )
        self.assertFalse(p["origin"]["AP_assigned"])
        self.assertFalse(p["origin"]["COM_used"])
        self.assertFalse(p["origin"]["center_fit_performed"])
        self.assertFalse(p["sampling"]["temporal_filter"])
        self.assertEqual(p["recommendation"], "defer_primary_replacement")

    def test_overlay_and_manifest_bound_to_candidate(self):
        r = json.loads((DATA / "s3-candidate-video-roi.json").read_text())
        self.assertEqual(
            r["geometry_input_sha256"], sha(DATA / "s3-sector-candidate.npz")
        )
        self.assertEqual(r["direction_labels"], ["O", "E"])
        self.assertEqual(len(r["frames"]), 111)
        self.assertEqual([f["index"] for f in r["frames"]], list(range(111)))
        self.assertEqual([r["width"], r["height"]], [512, 512])
        registry = json.loads((ROOT / "catalog/assets.json").read_text())["files"]
        candidate = Path("sonnen-2018/s3-candidate-review")
        manifest = [
            entry
            for entry in registry
            if Path(entry["path"]).parent.parts[-2:] == candidate.parts
        ]
        self.assertGreater(len(manifest), 10)
        for a in manifest:
            f = ROOT / "assets" / a["path"]
            self.assertEqual(f.stat().st_size, a["bytes"])
            self.assertEqual(sha(f), a["sha256"])


if __name__ == "__main__":
    unittest.main()

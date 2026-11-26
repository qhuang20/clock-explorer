# SPDX-License-Identifier: MIT
"""Scientific invariants of the detail-only S1 registration candidate."""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
AVAILABLE = all(
    importlib.util.find_spec(m)
    for m in ["numpy", "scipy", "av", "cv2", "PIL", "matplotlib"]
)
DATA = ROOT / "assets/data/derived/sonnen-2018/s1-candidate-review"
if AVAILABLE:
    import numpy as np
    from PIL import ImageFont

    sys.path.insert(0, str(ROOT / "analysis"))
    from review_sonnen_s1_candidate import (
        font_path,
        mapped_paths,
        rigid_initial,
        sample_native,
    )


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


@unittest.skipUnless(AVAILABLE, "requires the optional scientific environment")
class S1CandidateNumericalTests(unittest.TestCase):
    def test_font_falls_back_to_bundled_portable_font(self):
        missing = ROOT / "outputs/sonnen-s1-candidate/font-not-installed/Arial.ttf"
        self.assertFalse(missing.is_file())
        selected = font_path(missing)
        self.assertTrue(selected.is_file())
        self.assertEqual(selected.name, "DejaVuSans.ttf")
        self.assertEqual(font_path(selected), selected)
        loaded = ImageFont.truetype(str(selected), 18)
        self.assertGreater(loaded.getbbox("S1 · 70 µm")[2], 0)

    def test_euclidean_mapping_preserves_lengths_without_scale(self):
        p = np.array([10.0, 15.0])
        d = np.array([0.0, -1.0])
        m = rigid_initial(p, d, np.array([30.0, 40.0]), np.array([1.0, 0.0]))
        path = p + np.arange(8)[:, None] * d
        paths, normals = mapped_paths(
            path, np.array([1.0, 0.0]), np.array([np.vstack([m, [0, 0, 1]])])
        )
        np.testing.assert_allclose(paths[0, 0], [30, 40])
        np.testing.assert_allclose(np.linalg.norm(np.diff(paths[0], axis=0), axis=1), 1)
        self.assertAlmostEqual(np.linalg.det(m[:, :2]), 1.0)
        np.testing.assert_allclose(np.linalg.norm(normals, axis=1), 1)

    def test_native_affine_field_mean_and_real_zero_support(self):
        yy, xx = np.indices((40, 40))
        path = np.array([[12.25, 15.5], [16.0, 20.0]])
        offsets = np.linspace(-3.4, 3.4, 12)
        normal = np.array([1.0, 0.0])
        mask = np.ones((40, 40), bool)
        values, counts = sample_native(2 * xx + 3 * yy + 4, path, normal, offsets, mask)
        np.testing.assert_allclose(
            values, 2 * path[:, 0] + 3 * path[:, 1] + 4, rtol=0, atol=1e-12
        )
        self.assertTrue(np.all(counts == len(offsets)))
        zeros, _ = sample_native(np.zeros_like(xx), path, normal, offsets, mask)
        np.testing.assert_array_equal(zeros, [0, 0])
        mask[:, 9] = False
        values, counts = sample_native(xx, path, normal, offsets, mask)
        self.assertTrue(np.isnan(values[0]))
        self.assertLess(counts[0], len(offsets))


@unittest.skipUnless(
    AVAILABLE and (DATA / "s1-rigid-candidate.npz").is_file(),
    "requires optional local S1 review artifacts",
)
class S1CandidateArtifactTests(unittest.TestCase):
    def test_native_geometry_and_original_time_coordinate(self):
        with np.load(DATA / "s1-rigid-candidate.npz") as z:
            self.assertEqual(z["intensity"].shape, (301, 88))
            self.assertEqual(z["path_xy"].shape, (88, 301, 2))
            self.assertEqual(float(z["time_h"][-1]), 14.5)
            self.assertEqual(float(z["time_h"][77]), 12.84)
            np.testing.assert_allclose(
                np.linalg.det(z["reference_to_source"][:, :2, :2]), 1.0, atol=2e-7
            )
            lengths = (
                np.linalg.norm(np.diff(z["path_xy"], axis=1), axis=-1) * z["um_per_px"]
            )
            np.testing.assert_allclose(lengths, 1.0, atol=2e-6)
            np.testing.assert_array_equal(z["valid"], np.isfinite(z["intensity"]))
            self.assertEqual(len(z["width_offsets_px"]), 116)
            np.testing.assert_allclose(z["width_offsets_px"][[0, -1]], [-57.4, 57.4])
        with np.load(
            ROOT / "assets/data/derived/sonnen-2018/movie-s1/kymograph.npz"
        ) as base:
            with np.load(DATA / "s1-rigid-candidate.npz") as candidate:
                for key in ["time_h", "position_um"]:
                    np.testing.assert_array_equal(candidate[key], base[key])
                np.testing.assert_array_equal(
                    candidate["baseline_intensity"], base["intensity"]
                )

    def test_baseline_and_source_script_hashes_preserved(self):
        record = json.loads((DATA / "s1-review-provenance.json").read_text())
        self.assertEqual(
            record["baseline_hashes_before"], record["baseline_hashes_after"]
        )
        for name, value in record["baseline_hashes_before"].items():
            self.assertEqual(sha(ROOT / name), value)
        self.assertEqual(
            record["script_sha256"],
            sha(ROOT / "analysis/review_sonnen_s1_candidate.py"),
        )
        self.assertEqual(record["recommendation"], "defer_primary_replacement")
        self.assertFalse(
            record["registration"]["posterior_outline_holdout"]["used_in_fit"]
        )
        self.assertFalse(record["sampling"]["temporal_filter"])

    def test_candidate_overlay_is_bound_to_new_matrix_and_native_frames(self):
        r = json.loads((DATA / "s1-candidate-video-roi.json").read_text())
        self.assertEqual(r["dataset_id"], "sonnen-2018-embryo")
        self.assertEqual(r["video_id"], "movie-s1")
        self.assertEqual(
            r["geometry_input_sha256"], sha(DATA / "s1-rigid-candidate.npz")
        )
        self.assertEqual([r["width"], r["height"]], [988, 982])
        self.assertEqual(len(r["frame_starts_s"]), 88)
        self.assertEqual([f["index"] for f in r["frames"]], list(range(88)))
        self.assertEqual(r["direction_labels"], ["P", "A"])

    def test_registered_manifest_resolves_exact_artifacts(self):
        registry = json.loads((ROOT / "catalog/assets.json").read_text())["files"]
        candidate = Path("sonnen-2018/s1-candidate-review")
        manifest = [
            entry
            for entry in registry
            if Path(entry["path"]).parent.parts[-2:] == candidate.parts
        ]
        self.assertGreater(len(manifest), 10)
        for r in manifest:
            p = ROOT / "assets" / r["path"]
            self.assertEqual(p.stat().st_size, r["bytes"])
            self.assertEqual(sha(p), r["sha256"])


if __name__ == "__main__":
    unittest.main()

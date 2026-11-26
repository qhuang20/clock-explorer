# SPDX-License-Identifier: MIT
"""Full-sequence handoff and source checks, including the source pose jump."""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
REL = "data/derived/lauschke-2013/video1-full-curve/"
AVAILABLE = all(importlib.util.find_spec(m) for m in ("numpy", "scipy", "av"))
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(ROOT / "analysis"))
    from curved_strip import sample_strip
    from reproduce_lauschke_views import read_times
    from extract_video_kymographs import decode


class FullCurveHandoffTests(unittest.TestCase):
    def test_catalog_selects_fixed_reference_primary_without_old_ui(self):
        coverage = json.loads((ROOT / "catalog/temporal-coverage.json").read_text())[
            "lauschke-2013-embryo"
        ]
        self.assertEqual(
            (coverage["mode"], coverage["used"], coverage["total"]), ("all", 126, 126)
        )
        self.assertEqual(coverage["ranges_inclusive"], [[0, 125]])
        for name in ["additional-datasets.json", "comparison.json"]:
            records = json.loads((ROOT / "catalog" / name).read_text())
            if isinstance(records, dict):
                records = records["datasets"]
            c = next(c for c in records if c["id"] == "lauschke-2013-embryo")
            self.assertEqual(
                c["input"],
                "data/derived/lauschke-2013/video1-fixed-reference/kymograph.npz",
            )
            self.assertEqual(
                c["geometry_version"], "video1-fixed-reference-inward30-v1"
            )
        p = json.loads((ROOT / "catalog/card-presentation.json").read_text())[
            "lauschke-2013-embryo"
        ]
        self.assertTrue(p["flip_y"])
        self.assertFalse(p["method_figure"]["comparison"])
        self.assertNotIn("reference_comparison", p["method_figure"])
        self.assertNotIn("result_preview", p["method_figure"])
        self.assertNotIn(
            "data/derived/lauschke-2013/video1-kymograph.npz", p["detail_asset_paths"]
        )


@unittest.skipUnless(
    AVAILABLE and (ASSETS / REL / "video1-curved-kymograph.npz").is_file(),
    "requires optional scientific environment and local Video 1 extraction",
)
class FullCurveSourceTests(unittest.TestCase):
    def test_saved_geometry_time_validity_and_preserved_reference(self):
        report = json.loads(
            (ASSETS / REL / "video1-curved-provenance.json").read_text()
        )
        old = ASSETS / report["reference"]["input"]
        self.assertEqual(
            hashlib.sha256(old.read_bytes()).hexdigest(), report["reference"]["sha256"]
        )
        with np.load(ASSETS / REL / "video1-curved-kymograph.npz") as z:
            self.assertEqual(z["intensity"].shape, (451, 126))
            expected = read_times(
                ASSETS / "data/derived/lauschke-2013/video1-timestamps.json", 126
            )
            np.testing.assert_array_equal(z["time_h"], expected)
            self.assertAlmostEqual(expected[-1], 20.92)
            self.assertAlmostEqual(expected[101] - expected[100], 0.25)
            np.testing.assert_array_equal(
                z["measurement_valid_mask"], np.isfinite(z["intensity"])
            )
            np.testing.assert_array_equal(
                np.isfinite(z["intensity"]),
                np.isfinite(z["spatial_smoothed_intensity"]),
            )
            # The curve advances by physical arc length without per-frame length scaling.
            steps = np.linalg.norm(np.diff(z["path_xy"], axis=1), axis=-1) * 100 / 103
            np.testing.assert_allclose(steps, 1, atol=0.0002)
            np.testing.assert_allclose(
                np.linalg.norm(z["normals_xy"], axis=-1), 1, atol=1e-12
            )
            self.assertGreater(report["geometry"]["minimum_normal_jacobian"], 0.8)
            # Both sides of the sudden source-pose change have exact reviewed anchors.
            for i in [100, 101]:
                np.testing.assert_array_equal(
                    z["path_xy"][i, 0],
                    report["geometry"]["key_paths_original_xy"][str(i)][0],
                )

    def test_native_values_reproduce_at_early_late_and_jump_frames(self):
        source = (
            ASSETS
            / "data/source-archive/lauschke-2013/41586_2013_BFnature11804_MOESM292_ESM.mov"
        )
        if not source.is_file():
            self.skipTest("original Video 1 unavailable")
        frames = decode(source)
        valid = np.zeros((730, 737), bool)
        valid[15:-60, 15:] = True
        with np.load(ASSETS / REL / "video1-curved-kymograph.npz") as z:
            for i in [0, 60, 100, 101, 125]:
                values, counts, _ = sample_strip(
                    frames[i],
                    z["path_xy"][i],
                    z["normals_xy"][i],
                    20,
                    valid_region=valid,
                )
                np.testing.assert_array_equal(values, z["intensity"][:, i])
                np.testing.assert_array_equal(counts, z["valid_width_counts"][:, i])


if __name__ == "__main__":
    unittest.main()

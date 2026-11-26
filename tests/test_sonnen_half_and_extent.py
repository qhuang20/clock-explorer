# SPDX-License-Identifier: MIT
"""Seam-side, optical-flow and preserved-prefix regression checks."""

import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
AVAILABLE = all(
    importlib.util.find_spec(m) for m in ["numpy", "scipy", "av", "cv2", "PIL"]
)
if AVAILABLE:
    import av
    import cv2
    import numpy as np
    from scipy import ndimage as ndi

    sys.path.insert(0, str(ROOT / "analysis"))
    from review_sonnen_s1_half import advect

DATA = ROOT / "assets/data/derived/sonnen-2018"


@unittest.skipUnless(AVAILABLE, "requires the scientific environment")
class HalfTrackingTests(unittest.TestCase):
    def test_one_sided_patch_tracker_recovers_known_translation(self):
        rng = np.random.default_rng(20)
        image = cv2.GaussianBlur(
            rng.integers(0, 255, (512, 512), dtype=np.uint8), (0, 0), 1
        )
        moved = cv2.warpAffine(image, np.array([[1.0, 0, 3], [0, 1.0, 2]]), (512, 512))
        seam = np.column_stack([np.linspace(220, 140, 20), np.linspace(410, 90, 20)])
        result, count, error = advect(image, moved, seam)
        np.testing.assert_allclose(result - seam, np.tile([3, 2], (20, 1)), atol=0.1)
        self.assertGreater(count, 45)
        self.assertLess(error, 0.1)


@unittest.skipUnless(
    AVAILABLE and (DATA / "s1-midline-half-review/kymograph.npz").is_file(),
    "requires local S1 review",
)
class HalfArtifactTests(unittest.TestCase):
    def test_every_retained_band_stays_on_selected_side_and_matches_source(self):
        with np.load(DATA / "s1-midline-half-review/kymograph.npz") as z:
            signal, valid, paths, normals, seams = [
                z[k] for k in ["intensity", "valid", "path_xy", "normals_xy", "seam_xy"]
            ]
            np.testing.assert_array_equal(valid, np.isfinite(signal))
            self.assertEqual(signal.shape[1], 88)
            self.assertEqual(z["time_h"][-1], 14.5)
            self.assertTrue(np.all(z["width_counts"][valid] == 61))
            with av.open(
                str(ROOT / "assets/data/source-archive/sonnen-2018/mmc2.mp4")
            ) as c:
                for i, f in enumerate(c.decode(video=0)):
                    path, normal = paths[i][valid[:, i]], normals[i][valid[:, i]]
                    xy = (
                        path[:, None, :]
                        + normal[:, None, :] * np.arange(-30, 31)[None, :, None]
                    )
                    boundary = np.interp(
                        xy[..., 1], seams[i, ::-1, 1], seams[i, ::-1, 0]
                    )
                    self.assertTrue(np.all(xy[..., 0] > boundary + 8))
                    raw = ndi.map_coordinates(
                        f.to_ndarray(format="rgb24")[:, :, 1].astype(float),
                        [xy[..., 1], xy[..., 0]],
                        order=1,
                    ).mean(axis=1)
                    np.testing.assert_allclose(
                        raw, signal[valid[:, i], i], rtol=0, atol=1e-10
                    )
                    ids = np.flatnonzero(valid[:, i])
                    self.assertTrue(np.all(np.diff(ids) == 1))


@unittest.skipUnless(
    AVAILABLE and (DATA / "s2-extended-ray-review/kymograph.npz").is_file(),
    "requires local S2 review",
)
class ExtentArtifactTests(unittest.TestCase):
    def test_existing_values_times_and_translations_are_exact(self):
        with (
            np.load(DATA / "movie-s2-kymograph.npz") as old,
            np.load(DATA / "s2-extended-ray-review/kymograph.npz") as new,
        ):
            for key in ["time_h", "shifts_xy"]:
                np.testing.assert_array_equal(new[key], old[key])
            np.testing.assert_array_equal(new["intensity"][:354], old["intensity"])
            np.testing.assert_array_equal(new["position_um"][:354], old["position_um"])
            np.testing.assert_array_equal(new["valid"], np.isfinite(new["intensity"]))
            self.assertGreater(new["valid"].sum(), old["intensity"].size)
            for column in new["valid"].T:
                self.assertFalse(np.any(np.diff(column.astype(int)) > 0))
            self.assertTrue(np.all(new["fov_width_counts"][new["valid"]] == 41))

    def test_new_outer_values_match_native_source_pixels(self):
        with np.load(DATA / "s2-extended-ray-review/kymograph.npz") as z:
            values, paths = z["intensity"], z["path_xy"]
            dx, dy = z["direction_xy"]
            normal = np.array([-dy, dx])
            with av.open(
                str(ROOT / "assets/data/source-archive/sonnen-2018/mmc3.mp4")
            ) as source:
                for i, frame in enumerate(source.decode(video=0)):
                    rows = np.flatnonzero(
                        np.isfinite(values[:, i]) & (np.arange(len(values)) >= 354)
                    )
                    xy = (
                        paths[i, rows, None, :]
                        + normal * np.arange(-20, 21)[None, :, None]
                    )
                    raw = ndi.map_coordinates(
                        frame.to_ndarray(format="rgb24")[:, :, 1].astype(float),
                        [xy[..., 1], xy[..., 0]],
                        order=1,
                    ).mean(axis=1)
                    np.testing.assert_allclose(raw, values[rows, i], rtol=0, atol=1e-10)

    def test_overlay_is_bound_to_selected_numeric_input(self):
        catalog = json.loads((ROOT / "catalog/comparison.json").read_text())
        for did, count in [("sonnen-2018", 155), ("sonnen-2018-embryo", 88)]:
            selected = next(d for d in catalog["datasets"] if d["id"] == did)
            overlay = json.loads((DATA / f"{did}-video-roi.json").read_text())
            self.assertEqual(overlay["geometry_input_sha256"], selected["input_sha256"])
            self.assertEqual(
                [f["index"] for f in overlay["frames"]], list(range(count))
            )
            self.assertTrue(all(f["bands"] for f in overlay["frames"]))


if __name__ == "__main__":
    unittest.main()

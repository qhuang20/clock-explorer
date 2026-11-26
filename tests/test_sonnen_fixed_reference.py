# SPDX-License-Identifier: MIT
"""Fixed-reference geometry and native-pixel regression checks for Sonnen."""

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "assets/data/derived/sonnen-2018"
AVAILABLE = all(importlib.util.find_spec(name) for name in ["numpy", "scipy", "av"])
if AVAILABLE:
    import av
    import numpy as np
    from scipy import ndimage as ndi


@unittest.skipUnless(
    AVAILABLE
    and all(
        (DATA / f"{name}-final-reference/kymograph.npz").is_file()
        for name in ["s1", "s2"]
    ),
    "requires optional local fixed-reference data",
)
class FixedReferenceTests(unittest.TestCase):
    def test_reference_is_fixed_after_unit_scale_pose_registration(self):
        for name in ["s1", "s2"]:
            with (
                self.subTest(movie=name),
                np.load(DATA / f"{name}-final-reference/kymograph.npz") as z,
            ):
                pose, source = z["source_to_reference"], z["P_reference_source_xy"]
                mapped = (
                    np.einsum("nij,nj->ni", pose[:, :2, :2], source) + pose[:, :2, 2]
                )
                np.testing.assert_allclose(
                    mapped,
                    np.tile(z["P_reference_xy"], (len(pose), 1)),
                    atol=1e-9,
                    rtol=0,
                )
                np.testing.assert_allclose(
                    z["path_xy"][:, 0], source, atol=1e-9, rtol=0
                )
                rotation = pose[:, :2, :2]
                self.assertLess(
                    np.max(abs(rotation @ np.swapaxes(rotation, 1, 2) - np.eye(2))),
                    1e-9,
                )
                np.testing.assert_allclose(np.linalg.det(rotation), 1, atol=1e-9)
                np.testing.assert_allclose(pose[-1], np.eye(3), atol=1e-9)
                if "A_reference_source_xy" in z:
                    mapped_a = (
                        np.einsum("nij,nj->ni", rotation, z["A_reference_source_xy"])
                        + pose[:, :2, 2]
                    )
                    np.testing.assert_allclose(
                        mapped_a,
                        np.tile(z["A_reference_xy"], (len(pose), 1)),
                        atol=1e-9,
                        rtol=0,
                    )

    def test_missing_prefix_keeps_physical_zero_at_the_reference(self):
        with np.load(DATA / "s1-final-reference/kymograph.npz") as z:
            self.assertGreater(
                z["first_valid_distance_um"][0], z["first_valid_distance_um"][-1]
            )
            first = np.flatnonzero(z["valid"][:, 0])[0]
            self.assertGreater(first, 0)
            self.assertTrue(np.isnan(z["intensity"][:first, 0]).all())
            self.assertGreater(
                np.linalg.norm(z["path_xy"][0, first] - z["P_reference_source_xy"][0]),
                10,
            )
            self.assertEqual(z["position_um"][0], 0)
            for path, normals, valid in zip(
                z["path_xy"], z["normals_xy"], z["valid"].T
            ):
                p, n = path[valid], normals[valid]
                tangent = np.gradient(p, axis=0)
                tangent /= np.linalg.norm(tangent, axis=1, keepdims=True)
                derivative = np.gradient(n, axis=0) * float(z["um_per_px"])
                jacobian = 1 - float(z["strip_width_px"]) / 2 * abs(
                    np.sum(derivative * tangent, axis=1)
                )
                self.assertGreater(np.min(jacobian), 0)

    def test_all_retained_samples_reproduce_original_video_pixels(self):
        for name, filename, previous in [
            ("s1", "mmc2.mp4", "s1-midline-half-review"),
            ("s2", "mmc3.mp4", "s2-extended-ray-review"),
        ]:
            with (
                self.subTest(movie=name),
                np.load(DATA / f"{name}-final-reference/kymograph.npz") as z,
                np.load(DATA / previous / "kymograph.npz") as old,
            ):
                np.testing.assert_array_equal(z["time_h"], old["time_h"])
                np.testing.assert_array_equal(z["valid"], np.isfinite(z["intensity"]))
                width = float(z["strip_width_px"])
                offsets = np.linspace(-width / 2, width / 2, int(np.ceil(width)) + 1)
                self.assertTrue(np.all(z["width_counts"][z["valid"]] == len(offsets)))
                with av.open(
                    str(ROOT / "assets/data/source-archive/sonnen-2018" / filename)
                ) as source:
                    for i, frame in enumerate(source.decode(video=0)):
                        valid = z["valid"][:, i]
                        path = z["path_xy"][i, valid]
                        normal = z["normals_xy"][i, valid]
                        xy = (
                            path[:, None, :]
                            + normal[:, None, :] * offsets[None, :, None]
                        )
                        if name == "s1":
                            seam = z["seam_xy"][i]
                            seam_x = np.interp(xy[..., 1], seam[::-1, 1], seam[::-1, 0])
                            self.assertTrue(np.all(xy[..., 0] > seam_x + 8))
                        values = ndi.map_coordinates(
                            frame.to_ndarray(format="rgb24")[:, :, 1].astype(float),
                            [xy[..., 1], xy[..., 0]],
                            order=1,
                        ).mean(axis=1)
                        np.testing.assert_allclose(
                            values, z["intensity"][valid, i], atol=1e-10, rtol=0
                        )

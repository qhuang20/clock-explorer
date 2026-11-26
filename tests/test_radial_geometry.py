# SPDX-License-Identifier: MIT
"""Numerical geometry checks; optional analysis dependencies are not CI runtime deps."""

import importlib.util
from pathlib import Path
import sys
import unittest
import json
import tempfile

AVAILABLE = all(importlib.util.find_spec(m) for m in ("numpy", "scipy", "av"))
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    from extract_lauschke_radial import mask_centroid, sample_radial
    from reproduce_lauschke_views import read_times, sample


@unittest.skipUnless(AVAILABLE, "requires optional scientific analysis environment")
class RadialGeometryTests(unittest.TestCase):
    def test_centroid_is_uniform_area_and_translation_equivariant(self):
        mask = np.zeros((90, 100), bool)
        mask[20:50, 30:70] = True
        np.testing.assert_allclose(mask_centroid(mask), [49.5, 34.5])
        moved = np.roll(np.roll(mask, 4, axis=0), -7, axis=1)
        np.testing.assert_allclose(mask_centroid(moved), mask_centroid(mask) + [-7, 4])

    def test_p_to_a_radius_preserves_true_zero_and_masks_after_first_exit(self):
        image = np.zeros((80, 110, 3), dtype=np.uint8)
        image[..., 1] = np.arange(110, dtype=np.uint8)[None, :]
        mask = np.zeros((80, 110), bool)
        mask[20:60, :55] = True
        mask[20:60, 70:100] = True  # A disconnected island must not re-enter.
        matrix, counts = sample_radial([image], np.array([[0.0, 40.0]]), [mask], 0)
        np.testing.assert_allclose(matrix[:55, 0], np.arange(55))
        self.assertTrue(np.isnan(matrix[55:, 0]).all())
        self.assertTrue((counts[55:, 0] == 0).all())

    def test_strip_translation_changes_neither_sampled_signal_nor_mask(self):
        image = np.zeros((90, 120, 3), dtype=np.uint8)
        image[..., 1] = np.arange(120, dtype=np.uint8)[None, :]
        mask = np.zeros((90, 120), bool)
        mask[15:70, 10:80] = True
        a, _ = sample_radial([image], np.array([[30.0, 40.0]]), [mask], 45)
        shifted_image = np.roll(np.roll(image, 4, axis=0), 5, axis=1)
        shifted_mask = np.roll(np.roll(mask, 4, axis=0), 5, axis=1)
        b, _ = sample_radial(
            [shifted_image], np.array([[35.0, 44.0]]), [shifted_mask], 45
        )
        np.testing.assert_allclose(a, b, equal_nan=True)


@unittest.skipUnless(AVAILABLE, "requires optional scientific analysis environment")
class PaperGeometryTests(unittest.TestCase):
    def test_time_audit_preserves_an_irregular_gap_and_manual_correction(self):
        rows = [
            {"frame": i, "text": x}
            for i, x in enumerate(["0.00 h", "0.17 h", "0.33 h", "0.58 h"])
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "times.json"
            path.write_text(
                json.dumps({"ocr": rows, "manual_corrections_h": {"1": 0.16}})
            )
            np.testing.assert_allclose(read_times(path, 4), [0, 0.16, 0.33, 0.58])

    def test_image_space_gaussian_never_blurs_between_frames(self):
        frames = np.zeros((3, 140, 140, 3), dtype=np.uint8)
        frames[1, :, 65] = 255
        origins = np.tile([60.0, 55.0], (3, 1))
        directions = np.tile([1.0, 0.0], (3, 1))
        positions = np.arange(11, dtype=float)
        raw = sample(frames, origins, directions, positions, 1)
        smooth = sample(frames, origins, directions, positions, 1, sigma_um=9.66)
        np.testing.assert_array_equal(raw[:, [0, 2]], 0)
        np.testing.assert_array_equal(smooth[:, [0, 2]], 0)
        self.assertGreater(np.max(smooth[:, 1]), 0)
        self.assertLess(np.max(smooth[:, 1]), np.max(raw[:, 1]))


@unittest.skipUnless(AVAILABLE, "requires optional scientific analysis environment")
class WavefrontCenterTests(unittest.TestCase):
    def make_fronts(self):
        from lauschke_wavefront_center import fit_circle

        rng = np.random.default_rng(20261115)
        truth = np.array([420.0, 390.0])
        fronts = []
        for frame, radius in enumerate([120.0, 155.0, 190.0, 130.0, 165.0, 200.0]):
            angles = np.linspace(0.1, 3.0, 65)
            points = (
                truth
                + radius * np.c_[np.cos(angles), np.sin(angles)]
                + rng.normal(0, 0.5, (65, 2))
            )
            center, _, residual, _ = fit_circle(points)
            fronts.append(
                {
                    "frame": frame,
                    "time_h": float(frame),
                    "center": center.tolist(),
                    "residual_px": residual,
                    "points": points.tolist(),
                }
            )
        return truth, fronts

    def test_shared_arc_center_recovered_despite_competing_fronts(self):
        from lauschke_wavefront_center import select_consensus

        truth, fronts = self.make_fronts()
        distractors = []
        for front in fronts[:4]:
            shifted = dict(front)
            shifted["center"] = (np.asarray(front["center"]) + [-200, -180]).tolist()
            shifted["points"] = (np.asarray(front["points"]) + [-200, -180]).tolist()
            distractors.append(shifted)
        center, _, selected = select_consensus(fronts + distractors)
        np.testing.assert_allclose(center, truth, atol=2)
        self.assertEqual(len(selected), 6)

    def test_center_follows_registration_translation(self):
        from lauschke_wavefront_center import select_consensus

        _, fronts = self.make_fronts()
        before, _, _ = select_consensus(fronts)
        shift = np.array([37.0, -22.0])
        for front in fronts:
            front["center"] = (np.asarray(front["center"]) + shift).tolist()
            front["points"] = (np.asarray(front["points"]) + shift).tolist()
        after, _, _ = select_consensus(fronts)
        np.testing.assert_allclose(after, before + shift, atol=1e-4)

    def test_duplicate_contours_do_not_replace_distinct_times(self):
        from lauschke_wavefront_center import select_consensus

        _, fronts = self.make_fronts()
        with self.assertRaises(ValueError):
            select_consensus(fronts[:2] * 20)

    def test_straight_front_has_no_identifiable_curvature_center(self):
        from lauschke_wavefront_center import fit_circle

        x = np.arange(30, dtype=float)
        with self.assertRaises(ValueError):
            fit_circle(np.c_[x, 2 * x])

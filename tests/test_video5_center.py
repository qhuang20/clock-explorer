# SPDX-License-Identifier: MIT
"""Behavioral checks for candidate-guided fitting, without a COM fallback."""

import importlib.util
from pathlib import Path
import sys
import unittest

AVAILABLE = all(
    importlib.util.find_spec(m) for m in ("numpy", "scipy", "av", "matplotlib")
)
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    from lauschke_wavefront_center import fit_circle, find_fronts
    from fit_lauschke_video5 import select_candidate_fronts


@unittest.skipUnless(AVAILABLE, "requires optional scientific analysis environment")
class Video5CenterTests(unittest.TestCase):
    def fronts(self):
        rng = np.random.default_rng(20261116)
        center = np.array([380.0, 290.0])
        rows = []
        for i in range(8):
            theta = np.linspace(-0.7, 2.7, 90)
            points = center + (90 + 8 * i) * np.c_[np.cos(theta), np.sin(theta)]
            points += rng.normal(0, 0.5, points.shape)
            fitted, radius, residual, span = fit_circle(points)
            rows.append(
                {
                    "frame": i,
                    "time_h": i / 2,
                    "center": fitted.tolist(),
                    "points": points.tolist(),
                    "radius_px": radius,
                    "residual_px": residual,
                    "span_rad": span,
                }
            )
        return center, rows

    def test_shared_fit_is_not_locked_to_manual_candidate(self):
        truth, fronts = self.fronts()
        candidate = truth + [-20, 15]
        center, _, selected = select_candidate_fronts(fronts, candidate)
        np.testing.assert_allclose(center, truth, atol=2)
        self.assertGreater(np.linalg.norm(center - candidate), 20)
        self.assertEqual(len(selected), 8)

    def test_other_lobe_and_duplicate_levels_cannot_change_time_weight(self):
        truth, fronts = self.fronts()
        false_lobe = []
        for front in fronts:
            f = dict(front)
            f["center"] = (np.array(f["center"]) + [180, 100]).tolist()
            f["points"] = (np.array(f["points"]) + [180, 100]).tolist()
            f["residual_px"] = 0.0
            false_lobe.append(f)
        center, _, selected = select_candidate_fronts(fronts * 3 + false_lobe, truth)
        np.testing.assert_allclose(center, truth, atol=2)
        self.assertEqual(len(selected), len({f["frame"] for f in selected}))
        with self.assertRaises(ValueError):
            select_candidate_fronts(fronts[:2] * 20, truth)
        with self.assertRaises(ValueError):
            select_candidate_fronts(false_lobe, truth)

    def test_green_channel_search_recovers_expanding_ring_center(self):
        size = 260
        yy, xx = np.mgrid[:size, :size]
        truth = np.array([130.0, 130.0])
        rad = np.hypot(xx - truth[0], yy - truth[1])
        other = np.hypot(xx - 75, yy - 140)
        times = np.arange(25) / 5
        movie = []
        for time in times:
            r = 80 + 18 * np.sin(2 * np.pi * time / 2.4)
            green = 15 + 180 * np.exp(-0.5 * ((rad - r) / 6) ** 2)
            red = 15 + 220 * np.exp(
                -0.5 * ((other - (75 + 10 * np.cos(2 * np.pi * time / 2))) / 6) ** 2
            )
            movie.append(np.stack([red, green, red], axis=-1))
        frames = np.asarray(movie).astype("uint8")
        masks = np.tile(rad < 125, (len(times), 1, 1))
        fronts = find_fronts(
            frames,
            masks,
            np.zeros((len(times), 2)),
            times,
            1.0,
            frame_stride=1,
            fit_time_h=(0.5, 4.3),
            channel=1,
        )
        center, _, selected = select_candidate_fronts(fronts, truth, radius_px=35)
        np.testing.assert_allclose(center, truth, atol=3)
        self.assertGreaterEqual(len(selected), 5)


if __name__ == "__main__":
    unittest.main()

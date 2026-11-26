# SPDX-License-Identifier: MIT
"""Movie S2 review checks: preserve the clock and distinguish FOV from tissue."""

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

AVAILABLE = all(importlib.util.find_spec(m) for m in ["numpy", "av", "PIL"])
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    from audit_sonnen_movie_s2 import (
        START,
        END,
        sampling_geometry,
        fov_width_counts,
        read_burned_times,
    )


@unittest.skipUnless(AVAILABLE, "requires optional scientific analysis environment")
class SonnenReviewTests(unittest.TestCase):
    def test_translation_moves_both_endpoints_without_changing_direction(self):
        shifts = np.array([[0.0, 0.0], [-20.0, 8.0]])
        origins, ends, direction, distance, xy = sampling_geometry(shifts)
        np.testing.assert_array_equal(origins, START + shifts)
        np.testing.assert_array_equal(ends, END + shifts)
        np.testing.assert_allclose(xy[:, 0, 20], origins)
        np.testing.assert_allclose(xy[:, -1, 20], ends)
        self.assertEqual(xy.shape, (2, 354, 41, 2))
        self.assertTrue(np.all(direction < 0))
        self.assertGreater(distance[-1], 350)
        np.testing.assert_allclose(
            np.linalg.norm(xy[0, :, 40] - xy[0, :, 0], axis=1), 40
        )

    def test_fov_mask_does_not_turn_dark_pixels_into_missing_tissue(self):
        _, _, _, _, xy = sampling_geometry(np.zeros((2, 2)))
        counts = fov_width_counts(xy, (984, 990, 3))
        np.testing.assert_array_equal(counts, np.full((354, 2), 41))
        moved = xy - [510, 0]
        partial = fov_width_counts(moved, (984, 990, 3))
        self.assertTrue(np.any(partial == 0))
        self.assertTrue(np.any((partial > 0) & (partial < 41)))

    def test_burned_clock_retains_irregular_intervals_and_rejects_gaps(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "time.csv"
            path.write_text("frame,time_hours\n0,0.00\n1,0.17\n2,0.35\n")
            np.testing.assert_array_equal(read_burned_times(path, 3), [0.0, 0.17, 0.35])
            path.write_text("frame,time_hours\n0,0.00\n2,0.35\n")
            with self.assertRaises(ValueError):
                read_burned_times(path, 2)


if __name__ == "__main__":
    unittest.main()

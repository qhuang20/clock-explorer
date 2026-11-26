# SPDX-License-Identifier: MIT
"""Guards for the longer Video 1 grid, FOV-only validity and fixed scales."""

import importlib.util
from pathlib import Path
import sys
import unittest

AVAILABLE = all(importlib.util.find_spec(m) for m in ("numpy", "scipy", "av"))
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    from compare_lauschke_video1_450 import fov_counts, display_tail, SCALE
    from compare_lauschke_video1 import processing_arrays
    from reproduce_lauschke_views import sample


@unittest.skipUnless(AVAILABLE, "requires optional scientific analysis environment")
class Video1450Tests(unittest.TestCase):
    def test_fov_counts_match_original_sampler_without_inventing_tissue_mask(self):
        frames = np.zeros((2, 100, 160, 3), dtype=np.uint8)
        origins = np.array([[100.0, 30.0], [100.0, 36.0]])
        directions = np.array([[-1.0, 0.0], [-1.0, 0.0]])
        positions = np.arange(101.0)
        values = sample(frames, origins, directions, positions, SCALE)
        counts = fov_counts(frames.shape[1:], origins, directions, positions)
        np.testing.assert_array_equal(counts >= 16, np.isfinite(values))
        self.assertEqual(values[0, 0], 0)
        self.assertTrue(np.isnan(values[83:, 0]).all())
        self.assertTrue(np.isnan(values[:, 1]).all())
        # Zero-valued background can be FOV-valid: this function deliberately
        # makes no anatomical tissue claim from intensity or finite counts.
        self.assertTrue(np.isfinite(values[:83, 0]).all())

    def test_added_missing_distances_do_not_change_old_rows_or_fill_residual(self):
        times = np.linspace(0, 10, 61)
        spatial = np.tile(100 + 10 * np.sin(2 * np.pi * times / 2.3), (451, 1))
        spatial[407:, 12:59] = np.nan
        full = processing_arrays(spatial, spatial, times)
        cropped = processing_arrays(spatial[:351], spatial[:351], times)
        for new, old in zip(full, cropped):
            np.testing.assert_array_equal(new[:351], old)
        np.testing.assert_array_equal(np.isfinite(full[1]), np.isfinite(spatial))
        self.assertTrue(np.all(full[2][450, 12:59] < 0.8))

    def test_scale_extension_reports_tail_without_clipping_signed_values(self):
        residual = np.array([[-55.57, np.nan, 0, 54.9]])
        before = residual.copy()
        tail = display_tail(residual)
        np.testing.assert_array_equal(residual, before)
        self.assertEqual(tail["limits"], [-55, 55])
        self.assertEqual(tail["below_scale_count"], 1)
        self.assertEqual(tail["above_scale_count"], 0)
        self.assertEqual(tail["colorbar_extend"], "min")
        self.assertFalse(tail["numeric_values_clipped"])


if __name__ == "__main__":
    unittest.main()

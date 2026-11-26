# SPDX-License-Identifier: MIT
"""Scientific invariants of the time-domain baseline used in Video 1 comparison."""

import importlib.util
from pathlib import Path
import sys
import unittest

AVAILABLE = all(importlib.util.find_spec(m) for m in ("numpy", "scipy", "av"))
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    from compare_lauschke_video1 import processing_arrays, time_background


@unittest.skipUnless(AVAILABLE, "requires optional scientific analysis environment")
class Video1ProcessingTests(unittest.TestCase):
    def test_constant_signal_stays_zero_after_subtraction_and_missing_stays_missing(
        self,
    ):
        times = np.array([0.0, 0.2, 0.55, 1.0, 2.0, 3.0])
        values = np.full((3, len(times)), 17.0)
        values[0, 2] = np.nan
        values[1] = np.nan
        values[2] = 0
        baseline, residual, support = processing_arrays(values, values, times)
        np.testing.assert_allclose(baseline[0], 17, atol=1e-13)
        self.assertTrue(np.isnan(residual[0, 2]))
        self.assertTrue(np.isnan(residual[1]).all())
        np.testing.assert_allclose(residual[2], 0, atol=0)
        self.assertTrue(np.isfinite(residual[2]).all())
        self.assertTrue((support[1] == 0).all())

    def test_physical_time_units_and_irregular_sampling_are_respected(self):
        times = np.array([0.0, 0.1, 0.7, 1.4, 2.8, 3.5, 5.0])
        values = (10 + np.sin(times))[None, :]
        hours, support = time_background(values, times, 1.5)
        minutes, minute_support = time_background(values, times * 60, 90)
        np.testing.assert_allclose(hours, minutes, atol=1e-13)
        np.testing.assert_allclose(support, minute_support, atol=1e-13)
        by_index, _ = time_background(values, np.arange(len(times)), 1.5)
        self.assertFalse(np.allclose(hours, by_index))

    def test_known_oscillation_survives_slow_baseline_and_signed_values_are_retained(
        self,
    ):
        times = np.linspace(0, 20, 401)
        signal = 20 * np.sin(2 * np.pi * times / 2.3)
        values = (100 + 3 * times + signal)[None, :]
        background, residual, support = processing_arrays(values, values, times)
        middle = (times >= 4.5) & (times <= 15.5)
        self.assertGreater(
            np.corrcoef(signal[middle], residual[0, middle])[0, 1], 0.999
        )
        self.assertLess(
            np.sqrt(np.mean((signal[middle] - residual[0, middle]) ** 2)), 0.2
        )
        self.assertLess(residual.min(), 0)
        self.assertGreater(residual.max(), 0)
        np.testing.assert_allclose(background + residual, values, atol=1e-12)
        self.assertLess(support[0, 0], 0.6)
        self.assertGreater(support[0, 200], 0.99)

    def test_invalid_times_and_changed_measurement_masks_are_rejected(self):
        values = np.ones((2, 3))
        for times in [[0, 0, 1], [0, 2, 1], [0, float("nan"), 2]]:
            with self.assertRaises(ValueError):
                time_background(values, times)
        with self.assertRaises(ValueError):
            time_background(values, [0, 1, 2], 0)
        spatial = values.copy()
        spatial[0, 1] = np.nan
        with self.assertRaises(ValueError):
            processing_arrays(values, spatial, [0, 1, 2])


if __name__ == "__main__":
    unittest.main()

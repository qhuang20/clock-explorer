# SPDX-License-Identifier: MIT
"""Audit guards for zero values, missing coverage, clock overrides and SVG axes."""

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

AVAILABLE = all(importlib.util.find_spec(m) for m in ("numpy", "scipy", "av"))
if AVAILABLE:
    import json
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    from audit_lauschke_video2 import coverage, require_identical, svg_axes
    from reproduce_lauschke_views import read_times


@unittest.skipUnless(AVAILABLE, "requires optional scientific analysis environment")
class Video2ReviewTests(unittest.TestCase):
    def test_exact_audit_preserves_true_zero_and_nan_location(self):
        original = np.array([[0.0, np.nan], [10.0, 3.0]])
        require_identical(original.copy(), original, "reference")
        changed = original.copy()
        changed[0, 1] = 0
        with self.assertRaises(ValueError):
            require_identical(changed, original, "missing value")
        changed = original.copy()
        changed[0, 0] = np.nan
        with self.assertRaises(ValueError):
            require_identical(changed, original, "true zero")
        changed = original.copy()
        changed[1, 1] = np.nextafter(3.0, 4.0)
        with self.assertRaises(ValueError):
            require_identical(changed, original, "one-ULP change")

    def test_coverage_distinguishes_empty_prefix_and_internal_gap(self):
        matrix = np.array(
            [
                [np.nan, np.nan, 0],
                [np.nan, 2, np.nan],
                [np.nan, 3, 4],
                [np.nan, np.nan, np.nan],
            ]
        )
        rows = coverage(matrix, np.arange(4.0) * 2)
        self.assertIsNone(rows[0]["first_valid_um"])
        self.assertEqual(rows[1]["first_valid_um"], 2)
        self.assertEqual(rows[1]["internal_gaps"], 0)
        self.assertEqual(rows[2]["first_valid_um"], 0)
        self.assertEqual(rows[2]["last_valid_um"], 4)
        self.assertEqual(rows[2]["internal_gaps"], 1)
        self.assertEqual(rows[2]["finite_distances"], 2)

    def test_burned_in_clock_override_is_not_uniformly_resampled(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "timestamps.json"
            p.write_text(
                json.dumps(
                    {
                        "ocr": [
                            {"frame": 0, "text": "0.00 h"},
                            {"frame": 1, "text": "0.24 h"},
                            {"frame": 2, "text": "0.43 h"},
                        ],
                        "manual_corrections_h": {"1": 0.21},
                    }
                )
            )
            times = read_times(p, 3)
        np.testing.assert_array_equal(times, [0, 0.21, 0.43])
        self.assertFalse(np.diff(times)[0] == np.diff(times)[1])

    def test_svg_audit_keeps_data_axes_and_colorbar_separate(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg"><g id="axes_1"><g id="matplotlib.axis_2"><g><text x="20" y="300">0</text><text x="20" y="100">400</text></g></g></g><g id="axes_2"><g id="matplotlib.axis_4"><text x="500" y="300">0.0</text></g></g></svg>"""
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "figure.svg"
            p.write_text(svg)
            axes = svg_axes(p)
        self.assertEqual([a["id"] for a in axes], ["axes_1", "axes_2"])
        labels = axes[0]["labels"][0]["text"]
        self.assertGreater(labels[0]["y"], labels[1]["y"])
        self.assertEqual(axes[1]["labels"][0]["text"][0]["text"], "0.0")


if __name__ == "__main__":
    unittest.main()

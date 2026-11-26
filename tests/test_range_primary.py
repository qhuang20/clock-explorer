# SPDX-License-Identifier: MIT
"""Selected exports must use fitted intensity and preserve other payloads."""

import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

AVAILABLE = all(
    importlib.util.find_spec(m) for m in ("numpy", "tifffile", "matplotlib")
)
if AVAILABLE:
    import numpy as np


@unittest.skipUnless(AVAILABLE, "requires optional scientific analysis environment")
class SelectedRangeTests(unittest.TestCase):
    def test_primary_array_and_unselected_payloads_survive_scoped_rebuild(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            assets = root / "assets"
            catalog = root / "catalog"
            output = assets / "data/range-explorer"
            output.mkdir(parents=True)
            catalog.mkdir()
            path = assets / "data/derived/lauschke-2013/comparison.npz"
            path.parent.mkdir(parents=True)
            primary = np.array([[0.0, np.nan], [2.0, 5.0]])
            np.savez(
                path,
                intensity=primary,
                centroid_intensity=np.full((2, 2), 99.0),
                time_h=[0.0, 1.0],
                position_um=[0.0, 1.0],
            )
            record = {
                "id": "lauschke-2013",
                "input": str(path.relative_to(assets)),
                "reporter": "LuVeLu",
                "short": "Lauschke",
                "position_unit": "µm",
                "roi": "fitted-roi.png",
                "axis_label": "Distance from fitted center (µm)",
            }
            (catalog / "comparison.json").write_text(
                json.dumps({"datasets": [record, {"id": "unrelated"}]})
            )
            (catalog / "temporal-coverage.json").write_text(
                json.dumps({"lauschke-2013": {"unit": "frames"}})
            )
            sentinel = b"Original other data; do not regenerate.\n"
            (output / "unrelated.js").write_bytes(sentinel)
            previous = {
                "unrelated": {
                    "paper": "unrelated",
                    "script": "data/range-explorer/unrelated.js",
                    "title": "Retained",
                }
            }
            (output / "index.json").write_text(json.dumps(previous))
            env = {
                **os.environ,
                "CLOCK_ASSET_ROOT": str(assets),
                "CLOCK_CATALOG_ROOT": str(catalog),
                "MPLCONFIGDIR": str(root / "mpl-cache"),
            }
            script = (
                Path(__file__).resolve().parents[1] / "analysis/build_range_payloads.py"
            )
            subprocess.run(
                [sys.executable, str(script), "--only", "lauschke-2013"],
                env=env,
                check=True,
                capture_output=True,
            )
            self.assertEqual((output / "unrelated.js").read_bytes(), sentinel)
            self.assertEqual(
                json.loads((output / "index.json").read_text())["unrelated"],
                previous["unrelated"],
            )
            text = (output / "lauschke-2013.js").read_text()
            payload = json.loads(text[len("window.ClockRangeExplorer.receive(") : -3])
            full = payload["variants"][0]
            restored = np.frombuffer(
                base64.b64decode(full["array_f32_le"]), dtype="<f4"
            ).reshape(full["shape"])
            np.testing.assert_array_equal(restored, primary.astype("float32"))
            self.assertEqual(
                full["source_sha256"], hashlib.sha256(path.read_bytes()).hexdigest()
            )
            self.assertEqual(full["roi"], "fitted-roi.png")


if __name__ == "__main__":
    unittest.main()

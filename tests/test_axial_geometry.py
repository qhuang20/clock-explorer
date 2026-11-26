# SPDX-License-Identifier: MIT
"""Physical orientation and motion checks for the existing axial strip sampler."""

import importlib.util
from pathlib import Path
import sys
import unittest

AVAILABLE = all(importlib.util.find_spec(m) for m in ("numpy", "scipy", "av"))
if AVAILABLE:
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    from reproduce_lauschke_views import sample


@unittest.skipUnless(AVAILABLE, "requires optional scientific analysis environment")
class AxialGeometryTests(unittest.TestCase):
    def setUp(self):
        # Known signal gradient: zero at P, increasing toward A.
        signal = np.maximum(np.arange(200) - 80, 0).astype(np.uint8)
        self.frame = np.broadcast_to(signal[None, :, None], (200, 200, 3)).copy()
        self.position_um = np.arange(11, dtype=float)

    def profile(self, frame, origin, direction):
        return sample(
            [frame],
            np.asarray([origin], float),
            np.asarray([direction], float),
            self.position_um,
            0.5,
        )[:, 0]

    def test_physical_scale_preserves_zero_and_correct_axis_direction(self):
        forward = self.profile(self.frame, [80, 80], [1, 0])
        reverse = self.profile(self.frame, [100, 80], [-1, 0])
        np.testing.assert_allclose(forward, 2 * self.position_um, atol=1e-12)
        np.testing.assert_allclose(reverse, forward[::-1], atol=1e-12)
        self.assertEqual(forward[0], 0)

    def test_rotating_movie_and_landmarks_preserves_physical_profile(self):
        original = self.profile(self.frame, [80, 80], [1, 0])
        # np.rot90 maps (x,y) to (y,width-1-x) and (dx,dy) to (dy,-dx).
        rotated = self.profile(np.rot90(self.frame), [80, 119], [0, -1])
        np.testing.assert_allclose(rotated, original, atol=1e-12)

    def test_motion_correction_preserves_profile_when_landmarks_follow_tissue(self):
        original = self.profile(self.frame, [80, 80], [1, 0])
        moved = np.roll(np.roll(self.frame, 7, axis=0), -4, axis=1)
        corrected = self.profile(moved, [76, 87], [1, 0])
        fixed = self.profile(moved, [80, 80], [1, 0])
        np.testing.assert_allclose(corrected, original, atol=1e-12)
        self.assertFalse(np.allclose(fixed, original))


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: MIT
"""Lossless export of the author-supplied Yaman/Ramanathan example.

The archive does not identify the sample, channel, treatment, physical spatial
scale or absolute differentiation time. Retain stored rows; do not infer these.
"""

from paths import ASSET_ROOT
import numpy as np
import tifffile

ROOT = ASSET_ROOT
source = ROOT / "data/samples/yaman-2023/Kymograph.tif"
a = tifffile.imread(source)
assert a.ndim == 2 and a.dtype == np.uint16
# Author phase_Calculation.m uses t=(1:size(I,2))*0.25 hours.
t = np.arange(a.shape[1], dtype=float) * 0.25
p = np.arange(a.shape[0], dtype=float)
dest = ROOT / "data/derived/yaman-2023/kymograph.npz"
dest.parent.mkdir(parents=True, exist_ok=True)
np.savez_compressed(
    dest,
    intensity=a,
    time_h=t,
    position=p,
    position_row=p,
    author_script_time_h=t + 0.25,
    position_unit=np.array("stored row"),
    intensity_unit=np.array("source TIFF integer value"),
    time_origin=np.array("relative to first stored sample"),
)
print(f"Exported unchanged author example: {a.shape[0]} rows × {a.shape[1]} times")

# SPDX-License-Identifier: MIT
"""Render the promoted Video 5 fitted ROI from saved, source-verified arrays."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from paths import ASSET_ROOT
from extract_video_kymographs import decode
from extract_lauschke_radial import MOVIE_SHA
from audit_lauschke_video5 import overlay


def render(source_dir, output_root):
    movie = source_dir / "41586_2013_BFnature11804_MOESM296_ESM.mov"
    if hashlib.sha256(movie.read_bytes()).hexdigest() != MOVIE_SHA:
        raise ValueError("Unexpected Video 5 source")
    data = ASSET_ROOT / "data/derived/lauschke-2013"
    with np.load(data / "video5-wavefront-comparison.npz") as saved:
        matrix = saved["intensity"].copy()
        origins = saved["origins_xy"].copy()
        times = saved["time_h"].copy()
    with np.load(data / "video5-geometry.npz") as saved:
        masks = saved["tissue_masks"].copy()
        shifts = saved["shifts_xy"].copy()
    report = json.loads((data / "video5-wavefront-center.json").read_text())
    np.testing.assert_allclose(
        origins - shifts,
        np.tile(report["center_xy_reference_px"], (61, 1)),
        rtol=0,
        atol=1e-10,
    )
    frames = np.asarray(decode(movie))
    if len(frames) != 61 or matrix.shape != (401, 61):
        raise ValueError("Unexpected primary-data dimensions")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "sans-serif", "font.size": 10})
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 4.1))
    for ax, i in zip(axes, [0, 30, 60]):
        last = np.flatnonzero(np.isfinite(matrix[:, i]))[-1]
        overlay(
            ax, frames[i], masks[i], origins[i], last, f"{times[i]:g} h · Frame {i}"
        )
        ax.plot(*origins[i], "o", mfc="none", mec="#d6b7ff", ms=11, mew=1.4)
    fig.text(
        0.02,
        0.025,
        "Purple ring: fitted geometric center    Orange: 20 px radial strip at 45°    Cyan: analysis mask",
        fontsize=9,
        color="#535d6b",
    )
    fig.subplots_adjust(left=0.01, right=0.99, bottom=0.08, top=0.91, wspace=0.045)
    output = output_root / "figures/lauschke-2013"
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output / "video5-wavefront-roi.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    render(args.source_dir, args.output_root)

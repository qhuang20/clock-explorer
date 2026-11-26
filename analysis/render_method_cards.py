# SPDX-License-Identifier: MIT
"""Render compact previews of existing experimental extraction matrices.

Masamizu Movie 2 retains frame / image-pixel coordinates: its exposure time
must not be substituted for the unverified biological acquisition interval.
The original two-panel sampling-method figure is left untouched.
"""

from paths import ASSET_ROOT
from pathlib import Path
import os
import json
import hashlib

ROOT = ASSET_ROOT
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".plot-cache"))
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 11,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "axes.edgecolor": "#9198a6",
        "axes.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "text.color": "#252936",
        "axes.labelcolor": "#525b6b",
        "xtick.color": "#697386",
        "ytick.color": "#697386",
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
        "axes.facecolor": "#f1f3f6",
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    }
)


def edge(x):
    x = np.asarray(x)
    assert len(x) > 1 and np.all(np.diff(x) > 0)
    return np.r_[
        x[0] - (x[1] - x[0]) / 2, (x[1:] + x[:-1]) / 2, x[-1] + (x[-1] - x[-2]) / 2
    ]


def main():
    source = ROOT / "data/derived/masamizu-2006/kymograph.npz"
    z = np.load(source, allow_pickle=False)
    values = z["intensity_8bit"]
    time, position = z["frame_index"], z["image_y_px"]
    normalized = (values - np.nanmin(values)) / (np.nanmax(values) - np.nanmin(values))
    assert values.shape == (len(position), len(time)) == (160, 45)
    np.testing.assert_allclose(normalized, z["relative_intensity"])
    fig, ax = plt.subplots(figsize=(4.4, 3.35))
    fig.subplots_adjust(left=0.16, right=0.89, bottom=0.16, top=0.96)
    cmap = plt.get_cmap("OrRd").copy()
    cmap.set_bad("#f1f3f6")
    mesh = ax.pcolormesh(
        edge(time),
        edge(position),
        np.ma.masked_invalid(normalized),
        cmap=cmap,
        vmin=0,
        vmax=1,
        shading="flat",
        rasterized=True,
    )
    ax.set(
        xlim=(edge(time)[0], edge(time)[-1]),
        ylim=(edge(position)[-1], edge(position)[0]),
        xlabel="Frame index",
        ylabel="Image position y (px)",
    )
    ax.set_xticks([0, 10, 20, 30, 44])
    ax.set_yticks([50, 100, 150, 200])
    bar = fig.colorbar(mesh, ax=ax, pad=0.045, fraction=0.045, aspect=25)
    bar.outline.set_visible(False)
    bar.set_ticks([0, 0.5, 1])
    bar.set_label("Relative display intensity")
    output = ROOT / "figures/masamizu-2006/masamizu-movie2-card-compact"
    for fmt in ["svg", "png", "pdf"]:
        fig.savefig(str(output) + "." + fmt, dpi=300)
    plt.close(fig)
    trace = {
        "source_data": str(source.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "transformation": "Global finite-value min-max normalization, flat pcolormesh; no resampling or smoothing.",
        "caption_claim": "Display intensity extracted from 45 frames of Masamizu Movie 2, in stored frame and image-pixel coordinates.",
        "limits": [
            "Acquisition interval and micrometers per pixel are unverified.",
            "Supplemental video display intensity, not raw camera measurements.",
            "Fixed ROI; tissue deformation and image drift remain uncorrected.",
        ],
    }
    (source.parent / "card-render.json").write_text(json.dumps(trace, indent=2) + "\n")
    print("Rendered Masamizu card: 160 × 45, frame / pixel axes, OrRd [0,1].")


if __name__ == "__main__":
    main()

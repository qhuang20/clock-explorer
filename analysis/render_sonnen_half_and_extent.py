# SPDX-License-Identifier: MIT
"""Render the saved Movie S1 half-strip and S2 ray extension for local cards."""

import argparse
import json

import av
import numpy as np

from export_video_rois import bands_from_path
from extract_sonnen_additional import digest
from paths import ASSET_ROOT
from render_method_cards import edge, plt

CASES = {
    "s1": (
        "s1-midline-half-review",
        "mmc2.mp4",
        "Distance from P-side reference (approx. µm)",
    ),
    "s2": (
        "s2-extended-ray-review",
        "mmc3.mp4",
        "Distance from ROI origin (approx. µm)",
    ),
}


def render(name, fixed=False, output_folder=None):
    folder, movie, ylabel = CASES[name]
    if fixed:
        folder = f"{name}-final-reference"
        ylabel = "Distance from fixed P reference (approx. µm)"
    folder = output_folder or folder
    data = ASSET_ROOT / "data/derived/sonnen-2018" / folder
    figures = ASSET_ROOT / "figures/sonnen-2018" / folder
    figures.mkdir(parents=True, exist_ok=True)
    source = ASSET_ROOT / "data/source-archive/sonnen-2018" / movie
    numeric = data / "kymograph.npz"
    record = json.loads((data / "provenance.json").read_text())
    if (
        digest(numeric) != record["matrix_sha256"]
        or digest(source) != record["source_sha256"]
    ):
        raise ValueError("Reviewed extraction files changed")
    with np.load(numeric) as z:
        values, times, distance, valid, paths = [
            z[k] for k in ["intensity", "time_h", "position_um", "valid", "path_xy"]
        ]
        width = float(z["strip_width_px"])
        references = {
            k: z[k]
            for k in ["P_reference_source_xy", "A_reference_source_xy"]
            if k in z
        }
        if "normals_xy" in z:
            normals = z["normals_xy"]
            seams = z["seam_xy"] if "seam_xy" in z else None
        else:
            dx, dy = z["direction_xy"]
            normals = np.broadcast_to([-dy, dx], paths.shape)
            seams = None
    low, high = record.get("display_limits", (np.nanmin(values), np.nanmax(values)))
    for stem, end in [("kymograph", times[-1]), ("kymograph-common", 10)]:
        fig, ax = plt.subplots(figsize=(4.4, 3.8))
        fig.subplots_adjust(left=0.16, right=0.89, bottom=0.18, top=0.88)
        heat = ax.pcolormesh(
            edge(times),
            edge(distance),
            np.ma.masked_invalid((values - low) / (high - low)),
            cmap=plt.get_cmap("OrRd").with_extremes(bad="#f1f3f6"),
            vmin=0,
            vmax=1,
            rasterized=True,
        )
        ax.set(xlim=(0, end), ylim=(0, distance[-1]), xlabel="Time (h)", ylabel=ylabel)
        ax.set_title("Axin2T2A", loc="left", pad=9)
        bar = fig.colorbar(heat, ax=ax, pad=0.045, fraction=0.045, aspect=25)
        bar.set_ticks([0, 0.5, 1])
        bar.set_label("Relative display intensity")
        bar.outline.set_visible(False)
        for ext in ["svg", "png", "pdf"]:
            fig.savefig(figures / f"{stem}.{ext}", dpi=200)
        plt.close(fig)
    indices = [0, len(times) // 2, len(times) - 1]
    with av.open(str(source)) as c:
        frames = {
            i: f.to_ndarray(format="rgb24")
            for i, f in enumerate(c.decode(video=0))
            if i in indices
        }
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.7), layout="constrained")
    for ax, i in zip(axes, indices):
        ax.imshow(frames[i], interpolation="nearest")
        if seams is not None:
            ax.plot(*seams[i].T, color="#ed6a5a", lw=1)
        bands, lines = bands_from_path(paths[i], normals[i], valid[:, i], width)
        for band in bands:
            ax.fill(*np.array(band).T, facecolor="#ffb45c33", edgecolor="#ffb45c", lw=1)
        for line in lines:
            ax.plot(*np.array(line).T, color="#ffb45c", lw=1)
        ids = np.flatnonzero(valid[:, i])
        p = paths[i, ids]
        if fixed:
            finite = np.isfinite(paths[i]).all(axis=1)
            ax.plot(*paths[i, finite].T, color="#ffb45c", lw=0.8, ls="--")
        posterior = references.get("P_reference_source_xy", paths[:, 0])[i]
        anterior = (
            references["A_reference_source_xy"][i]
            if "A_reference_source_xy" in references
            else p[-1]
        )
        for point, label in [
            (posterior, "P ref" if fixed else "P-side" if name == "s1" else "O"),
            (
                anterior,
                "A ref"
                if fixed and name == "s1"
                else "toward A"
                if name == "s1"
                else "E",
            ),
        ]:
            ax.plot(*point, "o", ms=3, mfc="none", mec="white")
            ax.text(
                *(point + [12, -10]),
                label,
                color="#ffb45c",
                fontsize=8,
                bbox={"facecolor": "#17191e", "edgecolor": "none", "pad": 1},
            )
        ax.set_title(f"Frame {i} · {times[i]:.2f} h")
        ax.set_axis_off()
    fig.savefig(figures / "roi.png", dpi=175)
    plt.close(fig)
    print(name, values.shape, "missing", np.isnan(values).sum())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=CASES, action="append")
    parser.add_argument("--fixed", action="store_true")
    args = parser.parse_args()
    for name in args.only or CASES:
        render(name, fixed=args.fixed)

# SPDX-License-Identifier: MIT
"""Render the selected Movie S3 results from its saved moving-center matrix."""

import argparse
import json
from pathlib import Path

import av
import numpy as np

from export_video_rois import bands_from_path, radial_extent_guides
from extract_sonnen_additional import digest
from paths import ASSET_ROOT
from render_method_cards import edge, plt

DATA = Path("data/derived/sonnen-2018/s3-moving-center-review")
FIGURES = Path("figures/sonnen-2018/s3-moving-center")


def render_kymographs(plot_dir, values, times, radius, low, high):
    color = plt.get_cmap("OrRd").with_extremes(bad="#f1f3f6")
    for stem, upper_time in [("kymograph", times[-1]), ("kymograph-common", 10)]:
        fig, ax = plt.subplots(figsize=(4.4, 3.8))
        fig.subplots_adjust(left=0.16, right=0.89, bottom=0.18, top=0.88)
        mesh = ax.pcolormesh(
            edge(times),
            edge(radius),
            np.ma.masked_invalid((values - low) / (high - low)),
            cmap=color,
            vmin=0,
            vmax=1,
            shading="flat",
            rasterized=True,
        )
        ax.set(
            xlim=(times[0], upper_time),
            ylim=(0, radius[-1]),
            xlabel="Time (h)",
            ylabel="Distance from tracked center (approx. µm)",
        )
        ax.set_title("LuVeLu", loc="left", pad=9)
        bar = fig.colorbar(mesh, ax=ax, pad=0.045, fraction=0.045, aspect=25)
        bar.set_ticks([0, 0.5, 1])
        bar.set_label("Relative display intensity")
        bar.outline.set_visible(False)
        for extension in ("svg", "png", "pdf"):
            fig.savefig(plot_dir / f"{stem}.{extension}", dpi=240)
        plt.close(fig)


def render(roi_only=False):
    data = ASSET_ROOT / DATA
    plot_dir = ASSET_ROOT / FIGURES
    plot_dir.mkdir(parents=True, exist_ok=True)
    source = ASSET_ROOT / "data/source-archive/sonnen-2018/mmc4.mp4"
    numeric = data / "kymograph.npz"
    review = json.loads((data / "provenance.json").read_text())
    if (
        digest(numeric) != review["matrix_sha256"]
        or digest(source) != review["source_sha256"]
    ):
        raise ValueError("Input files differ from the reviewed Movie S3 extraction")

    with np.load(numeric) as arrays:
        values, times, radius, valid, paths, centers = (
            arrays[key]
            for key in [
                "intensity",
                "time_h",
                "position_um",
                "valid",
                "path_xy",
                "origins_xy",
            ]
        )
        width_px = float(arrays["strip_width_px"])
        direction = arrays["direction_xy"]
    np.testing.assert_array_equal(valid, np.isfinite(values))
    normal = np.array([-direction[1], direction[0]])
    normals = np.broadcast_to(normal, paths.shape[1:])
    low, high = float(np.nanmin(values)), float(np.nanmax(values))
    if not roi_only:
        render_kymographs(plot_dir, values, times, radius, low, high)

    selected = [0, len(times) // 2, len(times) - 1]
    with av.open(str(source)) as video:
        frames = {
            index: frame.to_ndarray(format="rgb24")
            for index, frame in enumerate(video.decode(video=0))
            if index in selected
        }
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.7), layout="constrained")
    for ax, index in zip(axes, selected):
        ax.imshow(frames[index], interpolation="nearest")
        bands, lines = bands_from_path(paths[index], normals, valid[:, index], width_px)
        for guide in radial_extent_guides(paths[index], lines):
            ax.plot(*np.asarray(guide).T, color="#ffb45c", lw=1.1, ls="--")
        for band in bands:
            ax.fill(
                *np.asarray(band).T,
                facecolor="#ffb45c44",
                edgecolor="#ffb45c",
                linewidth=1.2,
            )
        for line in lines:
            ax.plot(*np.asarray(line).T, color="#ffb45c", linewidth=1.1)
        ax.scatter(
            *centers[index],
            s=23,
            facecolor="#ffb45c",
            edgecolor="#17191e",
            linewidth=0.8,
        )
        if lines:
            ax.annotate(
                "E",
                lines[-1][-1],
                xytext=(5, 1),
                textcoords="offset points",
                color="#ffb45c",
                fontsize=8,
                bbox={"facecolor": "#17191e", "edgecolor": "none", "pad": 1},
            )
        ax.set_title(f"Frame {index} · {times[index]:.2f} h")
        ax.set_axis_off()
    fig.savefig(plot_dir / "roi-with-extent.png", dpi=175)
    plt.close(fig)
    print(
        json.dumps(
            {
                "input_sha256": review["matrix_sha256"],
                "normalization": [low, high],
                "missing_values": int(np.count_nonzero(~valid)),
                "files": str(plot_dir),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roi-only", action="store_true")
    render(roi_only=parser.parse_args().roi_only)

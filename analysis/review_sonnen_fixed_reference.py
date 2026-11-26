# SPDX-License-Identifier: MIT
"""Show fixed references in native and stabilized source frames."""

import argparse
import json

import av
import cv2
import numpy as np

from export_video_rois import bands_from_path
from paths import ASSET_ROOT
from render_method_cards import plt

PREVIOUS = {"s1": "s1-midline-half-review", "s2": "s2-extended-ray-review"}


def draw(
    ax, image, path, normals, valid, width, p_reference, a_reference=None, pose=None
):
    from review_video1_stable_roi import transform

    if pose is not None:
        image = cv2.warpAffine(image, pose[:2], (image.shape[1], image.shape[0]))
        path = transform(path, pose)
        normals = normals @ pose[:2, :2].T
        p_reference = transform(p_reference, pose)
        if a_reference is not None:
            a_reference = transform(a_reference, pose)
    ax.imshow(image, interpolation="nearest")
    finite = np.isfinite(path).all(axis=1)
    ax.plot(*path[finite].T, color="#ffb45c", ls="--", lw=0.9)
    bands, lines = bands_from_path(path, normals, valid, width)
    for band in bands:
        ax.fill(*np.array(band).T, facecolor="#ffb45c33", edgecolor="#ffb45c", lw=1)
    for line in lines:
        ax.plot(*np.array(line).T, color="#ffb45c", lw=1)
    for point, label in [(p_reference, "P ref"), (a_reference, "A ref")]:
        if point is None:
            continue
        ax.plot(*point, "o", ms=4, mfc="none", mec="white", mew=1)
        ax.text(
            *(point + [12, -12]),
            label,
            color="white",
            fontsize=8,
            bbox={"facecolor": "#17191e", "edgecolor": "none", "pad": 1},
        )
    ax.set(xlim=(-0.5, image.shape[1] - 0.5), ylim=(image.shape[0] - 0.5, -0.5))
    ax.set_axis_off()


def render(name):
    data = ASSET_ROOT / f"data/derived/sonnen-2018/{name}-final-reference"
    output = ASSET_ROOT / f"figures/sonnen-2018/{name}-final-reference"
    output.mkdir(parents=True, exist_ok=True)
    record = json.loads((data / "provenance.json").read_text())
    with np.load(data / "kymograph.npz") as z:
        values, times, distances, paths, normals, valid, pose, p_source = [
            z[k]
            for k in [
                "intensity",
                "time_h",
                "position_um",
                "path_xy",
                "normals_xy",
                "valid",
                "source_to_reference",
                "P_reference_source_xy",
            ]
        ]
        a_source = z["A_reference_source_xy"] if "A_reference_source_xy" in z else None
        width = float(z["strip_width_px"])
    with np.load(
        ASSET_ROOT / f"data/derived/sonnen-2018/{PREVIOUS[name]}/kymograph.npz"
    ) as z:
        previous, previous_distance = z["intensity"], z["position_um"]
    with av.open(str(ASSET_ROOT / record["source_file"])) as source:
        images = [f.to_ndarray(format="rgb24") for f in source.decode(video=0)]
    indices = [0, len(images) // 2, len(images) - 1]
    fig, axes = plt.subplots(2, 3, figsize=(11, 8.1), layout="constrained")
    for row in range(2):
        for ax, i in zip(axes[row], indices):
            draw(
                ax,
                images[i],
                paths[i],
                normals[i],
                valid[:, i],
                width,
                p_source[i],
                a_source[i] if a_source is not None else None,
                pose=pose[i] if row else None,
            )
            ax.set_title(
                f"{'Final-frame coordinates' if row else 'Original movie'} · {times[i]:.2f} h"
            )
    fig.supxlabel(
        "P ref is fixed in final-frame coordinates · Solid band: measured tissue · Dashed line: reference extension",
        fontsize=10,
    )
    fig.savefig(output / "reference-review.jpg", dpi=160)
    plt.close(fig)
    from matplotlib.backends.backend_pdf import PdfPages

    with PdfPages(output / "all-frames.pdf") as pdf:
        for start in range(0, len(images), 6):
            fig, axes = plt.subplots(2, 3, figsize=(10, 7.5), layout="constrained")
            for ax, i in zip(axes.flat, range(start, min(start + 6, len(images)))):
                draw(
                    ax,
                    images[i],
                    paths[i],
                    normals[i],
                    valid[:, i],
                    width,
                    p_source[i],
                    a_source[i] if a_source is not None else None,
                )
                ax.set_title(f"Frame {i} · {times[i]:.2f} h")
            for ax in list(axes.flat)[min(6, len(images) - start) :]:
                ax.set_axis_off()
            pdf.savefig(fig, dpi=65)
            plt.close(fig)
    low = min(np.nanmin(previous), np.nanmin(values))
    high = max(np.nanmax(previous), np.nanmax(values))
    fig, axes = plt.subplots(1, 2, sharey=True, figsize=(11, 4.7), layout="constrained")
    for ax, v, d, label in zip(
        axes,
        [previous, values],
        [previous_distance, distances],
        [
            "Previous P-side origin"
            if name == "s1"
            else "Earlier translated radial ray",
            "Fixed final-frame P reference",
        ],
    ):
        heat = ax.pcolormesh(
            times,
            d,
            (v - low) / (high - low),
            shading="nearest",
            cmap=plt.get_cmap("OrRd").with_extremes(bad="#f1f3f6"),
            vmin=0,
            vmax=1,
            rasterized=True,
        )
        ax.set(
            xlim=(0, times[-1]),
            ylim=(0, max(distances[-1], previous_distance[-1])),
            xlabel="Movie time (h)",
            title=label,
        )
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Distance from each reference (approx. µm)")
    fig.colorbar(heat, ax=axes, label="Relative display intensity", ticks=[0, 0.5, 1])
    for ext in ["svg", "png"]:
        fig.savefig(output / f"reference-comparison.{ext}", dpi=160)
    plt.close(fig)
    print(name, "fixed-reference review", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=PREVIOUS, action="append")
    for name in parser.parse_args().only or PREVIOUS:
        render(name)

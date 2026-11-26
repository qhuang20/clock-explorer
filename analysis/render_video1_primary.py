# SPDX-License-Identifier: MIT
"""Install/render the selected Video 1 fixed-reference primary locally.

Copies the reviewed numeric file unchanged; never re-estimates its geometry or
intensities. Catalogue and playback overlays are updated separately.
"""

import argparse
import json
import shutil
from pathlib import Path

import numpy as np

from paths import ASSET_ROOT
from review_video1_stable_roi import digest
from export_video_rois import bands_from_path
from extract_lauschke_video1_curved import style

DATA_DIR = Path("data/derived/lauschke-2013/video1-fixed-reference")
FIGURE_DIR = Path("figures/lauschke-2013/video1-fixed-reference")
VERSION = "video1-fixed-reference-inward30-v1"


def overlay(ax, frame, path, normal, valid, p_ref, a_ref, time, index, small=False):
    ax.imshow(frame)
    finite = np.isfinite(path).all(1)
    guide = np.r_[path[finite], a_ref[None]]
    ax.plot(
        guide[:, 0],
        guide[:, 1],
        color="#ffb45c",
        lw=0.65 if small else 1.0,
        ls=(0, (4, 3)),
        alpha=0.8,
    )
    bands, lines = bands_from_path(path, normal, valid, 20)
    for band in bands:
        band = np.asarray(band)
        ax.fill(band[:, 0], band[:, 1], color="#ffb45c", alpha=0.16)
        ax.plot(*np.r_[band, band[:1]].T, color="#ffb45c", lw=0.6 if small else 1.0)
    for line in lines:
        line = np.array(line)
        ax.plot(*line.T, color="#ffb45c", lw=0.7 if small else 1.1)
    for point, label in [(p_ref, "P ref"), (a_ref, "A ref")]:
        ax.plot(
            *point,
            "o",
            ms=2 if small else 4,
            mfc="none",
            mec="white",
            mew=0.6 if small else 1.0,
        )
        if not small:
            ax.text(
                point[0] + 12,
                point[1] - 10,
                label,
                color="white",
                fontsize=8,
                bbox={"facecolor": "black", "alpha": 0.65, "pad": 1.5},
            )
    ax.set_title(f"Frame {index} · {time:.2f} h", fontsize=6 if small else 11, pad=5)
    ax.set_xlim(0, frame.shape[1])
    ax.set_ylim(frame.shape[0], 0)
    ax.axis("off")


def run(review, output_root, cache):
    source = review / "video1-inward30-kymograph.npz"
    record = json.loads((review / "provenance.json").read_text())
    before = digest(source)
    data = output_root / DATA_DIR
    figures = output_root / FIGURE_DIR
    data.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    target = data / "kymograph.npz"
    shutil.copyfile(source, target)
    if digest(target) != before:
        raise ValueError("Selected primary copy changed")
    frames = np.load(cache, mmap_mode="r")
    plt = style()
    with np.load(target) as z:
        raw = z["intensity"]
        times = z["time_h"]
        position = z["position_um"]
        paths = z["path_xy"]
        normals = z["normals_xy"]
        valid = z["measurement_valid_mask"]
        for name, ids, cols, size in [
            ("roi", [0, 60, 125], 3, (11.4, 4.7)),
            ("keyframes", [0, 27, 60, 84, 100, 101, 108, 116, 125], 3, (11.4, 12.0)),
            ("all126", list(range(126)), 9, (18, 30)),
        ]:
            rows = (len(ids) + cols - 1) // cols
            fig, axs = plt.subplots(rows, cols, figsize=size, squeeze=False)
            for ax, i in zip(axs.flat, ids):
                overlay(
                    ax,
                    frames[i],
                    paths[i],
                    normals[i],
                    valid[:, i],
                    z["P_reference_source_xy"][i],
                    z["A_reference_source_xy"][i],
                    times[i],
                    i,
                    len(ids) > 10,
                )
            for ax in list(axs.flat)[len(ids) :]:
                ax.axis("off")
            fig.subplots_adjust(
                left=0.01,
                right=0.99,
                top=0.94 if rows < 3 else 0.985,
                bottom=0.14 if rows < 3 else 0.025,
                wspace=0.03,
                hspace=0.13,
            )
            if rows < 3:
                fig.text(
                    0.02,
                    0.07,
                    "Fixed A/P reference coordinates after rigid stabilization · inward 30 px · 20 px-wide mean",
                    fontsize=9,
                    color="#535d6b",
                )
                fig.text(
                    0.02,
                    0.025,
                    "Solid: retained sampling region · dashed: reference path · no reporter values assigned to unsupported extensions",
                    fontsize=8,
                    color="#535d6b",
                )
            fig.savefig(figures / (name + ".png"), dpi=160 if rows > 3 else 200)
            plt.close(fig)
        from extract_video1_inward30 import heat

        fig, ax = plt.subplots(figsize=(4.4, 3.8))
        fig.subplots_adjust(left=0.16, right=0.87, bottom=0.19, top=0.87)
        limits = [float(np.nanmin(raw)), float(np.nanmax(raw))]
        # Standalone download already follows A above P. Gallery previews have
        # their own SVG reversal, supplied by the existing comparison renderer.
        mesh = heat(ax, raw, position, times, limits, "LuVeLu", float(position[-1]))
        ax.set_ylabel("Arc length from fixed P reference (µm)")
        cb = fig.colorbar(mesh, ax=ax, pad=0.045, fraction=0.045, aspect=25)
        cb.set_ticks([0, 0.5, 1])
        cb.set_label("Relative display intensity")
        cb.outline.set_visible(False)
        for ext in ["svg", "png", "pdf"]:
            fig.savefig(figures / ("kymograph." + ext), dpi=240)
        plt.close(fig)
    record["status"] = (
        "User-selected local gallery primary; fixed-reference inward30 geometry remains under calibration"
    )
    record["dataset"] = "lauschke-2013-embryo"
    record["method_version"] = VERSION
    record["numeric_file"] = str(DATA_DIR / "kymograph.npz")
    record["numeric_sha256"] = before
    record["primary_normalization"] = {
        "min": limits[0],
        "max": limits[1],
        "method": "finite min/max of complete selected sample before windowing",
    }
    record["local_primary_renderer_sha256"] = digest(__file__)
    record.pop("current_reference", None)
    (data / "provenance.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {"numeric_sha256": before, "data": str(data), "figures": str(figures)}
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--review", type=Path, default=Path("outputs/video1-inward30-kymograph")
    )
    parser.add_argument("--output-root", type=Path, default=ASSET_ROOT)
    parser.add_argument(
        "--cached-frames",
        type=Path,
        default=Path("work/lauschke-paper-method/video1-frames.npy"),
    )
    args = parser.parse_args()
    run(args.review, args.output_root, args.cached_frames)

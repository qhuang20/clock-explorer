# SPDX-License-Identifier: MIT
"""Review the saved Video 5 radial ROI without replacing its measured matrix.

The saved area-centroid trajectory is a proxy. An optional exploratory contour
probe is reported separately and never silently promoted to a new origin.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

from paths import ASSET_ROOT
from extract_video_kymographs import decode
from extract_lauschke_radial import MOVIE_SHA, UM_PER_PX, sample_radial


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def overlay(ax, image, mask, center, last, title, shift=None, fronts=()):
    ax.imshow(image)
    ax.contour(mask, levels=[0.5], colors=["#75d7ed"], linewidths=0.65)
    direction = np.array([1.0, 1.0]) / np.sqrt(2)
    normal = np.array([-direction[1], direction[0]])
    end = center + last * direction
    corners = np.array(
        [
            center + 10 * normal,
            end + 10 * normal,
            end - 10 * normal,
            center - 10 * normal,
        ]
    )
    ax.fill(corners[:, 0], corners[:, 1], color="#ffad43", alpha=0.3)
    ax.annotate(
        "",
        xy=end,
        xytext=center,
        arrowprops={"arrowstyle": "->", "color": "#ffad43", "lw": 1.8},
    )
    ax.plot(*center, "+", color="white", ms=11, mew=1.5)
    ax.text(
        center[0] - 10,
        center[1] + 20,
        "r = 0",
        color="white",
        fontsize=8,
        ha="right",
        bbox={"facecolor": "black", "alpha": 0.65, "pad": 2},
    )
    for front in fronts:
        points = np.array(front["points"]) + shift
        candidate = np.array(front["center"]) + shift
        ax.plot(points[:, 0], points[:, 1], color="#e1b5ff", lw=1.1)
        ax.plot(*candidate, "x", color="#e1b5ff", ms=8, mew=1.4)
    ax.set_title(title, fontsize=11, color="#242833", pad=8)
    ax.set_xlim(0, image.shape[1])
    ax.set_ylim(image.shape[0], 0)
    ax.axis("off")


def run(source_dir, output_root, probe_path=None, probe_wavefronts=False):
    movie = source_dir / "41586_2013_BFnature11804_MOESM296_ESM.mov"
    data = ASSET_ROOT / "data/derived/lauschke-2013"
    input_paths = [
        data / name
        for name in (
            "video5-kymograph.npz",
            "video5-geometry.npz",
            "extraction-provenance.json",
        )
    ]
    before = {p.name: digest(p) for p in input_paths}
    if digest(movie) != MOVIE_SHA:
        raise ValueError("Video 5 source hash differs")
    frames = np.asarray(decode(movie))
    with np.load(input_paths[0]) as saved:
        matrix = saved["intensity"].copy()
        times = saved["time_h"].copy()
        centers = saved["centers_xy"].copy()
        saved_counts = saved["valid_width_counts"].copy()
    with np.load(input_paths[1]) as geometry:
        masks = geometry["tissue_masks"].copy()
        shifts = geometry["shifts_xy"].copy()
        np.testing.assert_array_equal(centers, geometry["centers_xy"])
    if frames.shape != (61, 742, 749, 3) or masks.shape != frames.shape[:3]:
        raise ValueError("Unexpected source or mask dimensions")
    rebuilt, counts = sample_radial(frames, centers, masks)
    np.testing.assert_allclose(rebuilt, matrix, atol=0, rtol=0, equal_nan=True)
    np.testing.assert_array_equal(counts, saved_counts)
    mask_centers = np.array([ndi.center_of_mass(m)[::-1] for m in masks])
    center_rounding = np.linalg.norm(mask_centers - centers, axis=1)
    if center_rounding.max() > 1:
        raise ValueError("Saved origin differs from raster-mask centroid by >1 px")
    lengths = np.array(
        [np.flatnonzero(np.isfinite(matrix[:, i]))[-1] for i in range(matrix.shape[1])]
    )
    probe = json.loads(probe_path.read_text()) if probe_path else None
    if probe_wavefronts:
        from lauschke_wavefront_center import find_fronts, select_consensus

        fronts = find_fronts(frames, masks, shifts, times, UM_PER_PX)
        probe = {
            "purpose": "Exploratory Video 2 contour finder applied to Video 5; not an accepted center estimate.",
            "candidate_count": len(fronts),
            "candidate_frames": sorted(set(f["frame"] for f in fronts)),
            "fronts": fronts,
        }
        try:
            center, _, selected = select_consensus(fronts)
            probe["candidate_common_center"] = center.tolist()
            probe["selected_frames"] = [f["frame"] for f in selected]
        except ValueError as error:
            probe["consensus_failure"] = str(error)
    report = {
        "dataset": "lauschke-2013",
        "source_video": "Supplementary Video 5",
        "source_sha256": MOVIE_SHA,
        "review_version": "video5-roi-review-v1",
        "matrix_preserved": before,
        "all_61_profiles_reproduced_exactly": True,
        "center_type": "Uniform binary-mask area centroid; not intensity COM.",
        "center_status": "Provisional structural proxy, not a verified oscillation center.",
        "author_roi_status": "No exact author-deposited ROI mapped for this Video 5 review.",
        "angle_deg_image_x_right_y_down": 45,
        "strip_width_px": 20,
        "transverse_samples": 21,
        "minimum_valid_samples": 16,
        "mask_rule": "Stop at first radial row with <75% valid width; no re-entry.",
        "scale_um_per_px": UM_PER_PX,
        "maximum_raster_centroid_difference_px": float(center_rounding.max()),
        "finite_radius_range_um": [
            float(lengths.min() * UM_PER_PX),
            float(lengths.max() * UM_PER_PX),
        ],
        "center_registered_range_px": np.ptp(centers - shifts, axis=0).tolist(),
        "trajectory": [
            {
                "frame": i,
                "time_h": float(times[i]),
                "origin_xy_px": centers[i].tolist(),
                "last_valid_radius_px": int(lengths[i]),
                "end_xy_px": (centers[i] + lengths[i] / np.sqrt(2)).tolist(),
            }
            for i in range(len(times))
        ],
        "probe": None
        if not probe
        else {
            "purpose": probe["purpose"],
            "implementation": "lauschke_wavefront_center.find_fronts/select_consensus",
            "scope": "Unretuned Video 2 contour protocol used as a diagnostic only; no replacement fit accepted.",
            "candidate_count": probe["candidate_count"],
            "candidate_frames": probe["candidate_frames"],
            "consensus_failure": probe.get("consensus_failure"),
            "accepted_as_center": False,
            "fronts": probe["fronts"],
        },
        "conclusion": "Keep the existing centroid-proxy matrix for review. Current evidence does not validate its origin as a wavefront center or the 45-degree ray as an author line.",
        "limitations": [
            "The exploratory contour protocol is not independently validated for Video 5; failure does not show that no radial center exists.",
            "The tissue mask depends on reporter-informed support and threshold choice; its boundary is not a molecularly defined anterior edge.",
            "Nearby-angle extractions at 35/55 degrees already exist as sensitivity controls, not an optimized direction.",
            "Do not label centroid/periphery as verified P/A or claim cell, rotation or deformation tracking.",
        ],
        "caption_source": "https://www.nature.com/articles/nature11804#Sec12",
        "script_sha256": digest(__file__),
    }
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "sans-serif", "font.size": 10})
    figures = output_root / "figures/lauschke-2013"
    records = output_root / "data/derived/lauschke-2013"
    figures.mkdir(parents=True, exist_ok=True)
    records.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 4.1))
    for ax, i in zip(axes, [0, 30, 60]):
        overlay(
            ax,
            frames[i],
            masks[i],
            centers[i],
            lengths[i],
            f"{times[i]:g} h · Frame {i}",
        )
    fig.text(
        0.02,
        0.025,
        "+ Area centroid (proxy)    Orange: sampled radial strip    Cyan: analysis mask",
        color="#535d6b",
        fontsize=9,
    )
    fig.subplots_adjust(left=0.01, right=0.99, bottom=0.08, top=0.91, wspace=0.045)
    fig.savefig(figures / "video5-roi-review.png", dpi=180)
    plt.close(fig)
    if probe:
        fig, axes = plt.subplots(2, 3, figsize=(11.4, 8.2))
        for ax, i in zip(axes.flat, [0] + probe["candidate_frames"]):
            fs = [f for f in probe["fronts"] if f["frame"] == i]
            overlay(
                ax,
                frames[i],
                masks[i],
                centers[i],
                lengths[i],
                f"{times[i]:.2f} h · Frame {i}",
                shifts[i],
                fs,
            )
        fig.text(
            0.02,
            0.028,
            "White +: existing centroid    Purple curves/x: exploratory contours/centers (not accepted)",
            color="#535d6b",
            fontsize=9,
        )
        fig.subplots_adjust(
            left=0.01, right=0.99, bottom=0.06, top=0.95, wspace=0.045, hspace=0.12
        )
        fig.savefig(figures / "video5-front-review.png", dpi=180)
        plt.close(fig)
    for path in input_paths:
        if digest(path) != before[path.name]:
            raise ValueError("An existing scientific input changed during review")
    (records / "video5-roi-review.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "all_61_profiles_reproduced_exactly",
                    "maximum_raster_centroid_difference_px",
                    "finite_radius_range_um",
                    "conclusion",
                )
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--probe", type=Path)
    parser.add_argument("--probe-wavefronts", action="store_true")
    args = parser.parse_args()
    run(args.source_dir, args.output_root, args.probe, args.probe_wavefronts)


if __name__ == "__main__":
    main()

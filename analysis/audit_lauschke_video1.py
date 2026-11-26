# SPDX-License-Identifier: MIT
"""Reproduce and inspect the Video 1 axial reference without replacing it.

The P/A polarity follows the paper and reviewed specimen morphology. Landmark
coordinates remain an independent approximation, not a recovered author ROI.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from paths import ASSET_ROOT
from extract_video_kymographs import decode
from reproduce_lauschke_views import (
    AP_KEYS,
    SOURCE_HASHES,
    SIGMA_UM,
    WIDTH_PX,
    ap_geometry,
    read_times,
    sample,
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def overlay(ax, frame, origin, direction, end_um, scale, title):
    ax.imshow(frame)
    normal = np.array([-direction[1], direction[0]])
    end = origin + end_um / scale * direction
    corners = np.array(
        [
            origin + 10 * normal,
            end + 10 * normal,
            end - 10 * normal,
            origin - 10 * normal,
        ]
    )
    ax.fill(corners[:, 0], corners[:, 1], color="#ffad43", alpha=0.27)
    ax.annotate(
        "",
        xy=end,
        xytext=origin,
        arrowprops={"arrowstyle": "->", "color": "#ffad43", "lw": 1.8},
    )
    ax.plot(*origin, "+", color="white", ms=11, mew=1.5)
    ax.text(
        origin[0] + 12,
        origin[1] + 16,
        "P-side*",
        color="white",
        fontsize=8,
        bbox={"facecolor": "black", "alpha": 0.7, "pad": 2},
    )
    midway = origin + min(250.0, end_um * 0.65) / scale * direction
    ax.text(
        midway[0] - 12,
        midway[1] + 24,
        "toward A",
        color="#ffcb80",
        fontsize=8,
        ha="right",
        bbox={"facecolor": "black", "alpha": 0.7, "pad": 2},
    )
    ax.set_title(title, fontsize=11, color="#242833", pad=8)
    ax.set_xlim(0, frame.shape[1])
    ax.set_ylim(frame.shape[0], 0)
    ax.axis("off")


def heat(ax, matrix, times, positions, norm, cmap, title):
    xedges = np.r_[
        times[0] - (times[1] - times[0]) / 2,
        (times[1:] + times[:-1]) / 2,
        times[-1] + (times[-1] - times[-2]) / 2,
    ]
    yedges = np.r_[
        positions[0] - 0.5, (positions[1:] + positions[:-1]) / 2, positions[-1] + 0.5
    ]
    mesh = ax.pcolormesh(
        xedges,
        yedges,
        np.ma.masked_invalid(matrix),
        cmap=cmap,
        norm=norm,
        shading="flat",
        rasterized=True,
    )
    ax.set_xlim(times[0], times[-1])
    ax.set_ylim(0, positions[-1])
    ax.set_xlabel("Time (h)")
    ax.set_ylabel("Distance from P-side reference (µm)")
    ax.set_title(title, fontsize=11, loc="left")
    return mesh


def run(source_dir, output_root):
    data = ASSET_ROOT / "data/derived/lauschke-2013"
    paths = [
        data / name
        for name in (
            "video1-kymograph.npz",
            "video1-provenance.json",
            "video1-timestamps.json",
        )
    ]
    before = {p.name: digest(p) for p in paths}
    movie = source_dir / "41586_2013_BFnature11804_MOESM292_ESM.mov"
    if digest(movie) != SOURCE_HASHES[1]:
        raise ValueError("Unexpected Video 1 source hash")
    source = np.asarray(decode(movie))
    if len(source) != 126:
        raise ValueError("Unexpected Video 1 frame count")
    frames = source[:61]
    times = read_times(paths[2], len(source))[:61]
    scale = 100 / 103
    positions = np.arange(451, dtype=float)
    origins, directions = ap_geometry(len(frames))
    raw = sample(frames, origins, directions, positions, scale)
    smooth = sample(frames, origins, directions, positions, scale, sigma_um=SIGMA_UM)
    expected = dict(
        intensity=raw,
        spatial_smoothed_intensity=smooth,
        time_h=times,
        position_um=positions,
        origins_xy=origins,
        directions_xy=directions,
    )
    with np.load(paths[0]) as saved:
        for key, values in expected.items():
            np.testing.assert_allclose(
                values, saved[key], rtol=0, atol=0, equal_nan=True, err_msg=key
            )
    np.testing.assert_allclose(np.linalg.norm(directions, axis=1), 1, atol=1e-14)
    if not ((directions[:, 0] < 0) & (directions[:, 1] < 0)).all():
        raise ValueError("Reviewed P-to-A direction changed")
    final_rows = np.array(
        [np.flatnonzero(np.isfinite(raw[:, i]))[-1] for i in range(len(times))]
    )
    figures = output_root / "figures/lauschke-2013"
    records = output_root / "data/derived/lauschke-2013"
    figures.mkdir(parents=True, exist_ok=True)
    records.mkdir(parents=True, exist_ok=True)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 10,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 4.8))
    for ax, i in zip(axes, [0, 30, 60]):
        overlay(
            ax,
            frames[i],
            origins[i],
            directions[i],
            positions[final_rows[i]],
            scale,
            f"Frame {i} · {times[i]:.2f} h",
        )
    fig.text(
        0.025,
        0.12,
        "White +: approximate P-side origin    Orange: 20 px axial strip toward A",
        fontsize=10,
        color="#535d6b",
    )
    fig.text(
        0.025,
        0.065,
        "*Independent anatomical landmarks. The end is limited by FOV/text, not a verified anterior tissue edge.",
        fontsize=9,
        color="#535d6b",
    )
    fig.subplots_adjust(left=0.015, right=0.985, top=0.96, bottom=0.19, wspace=0.04)
    fig.savefig(figures / "video1-roi-review.png", dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(8, 8, figsize=(15, 15))
    for i, ax in enumerate(axes.flat):
        if i < len(frames):
            overlay(
                ax,
                frames[i],
                origins[i],
                directions[i],
                positions[final_rows[i]],
                scale,
                f"{i} · {times[i]:.2f} h",
            )
        else:
            ax.axis("off")
    fig.subplots_adjust(
        left=0.01, right=0.99, top=0.98, bottom=0.01, wspace=0.08, hspace=0.20
    )
    fig.savefig(figures / "video1-roi-all-frames.png", dpi=120)
    plt.close(fig)
    cmap = matplotlib.colormaps["OrRd"].copy()
    cmap.set_bad("#f1f3f6")
    norm = Normalize(float(np.nanmin(raw)), float(np.nanmax(raw)))
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.9), constrained_layout=True)
    for ax, array, title in zip(
        axes,
        [raw, smooth],
        ["Primary display values", "Spatial-only control · σ = 9.66 µm"],
    ):
        mesh = heat(ax, array, times, positions, norm, cmap, title)
    fig.colorbar(mesh, ax=axes, label="Video display value", shrink=0.78)
    fig.suptitle("Video 1 · paper orientation: P at bottom, A upward", fontsize=13)
    for fmt in ["png", "svg", "pdf"]:
        fig.savefig(figures / ("video1-axial-review." + fmt), dpi=180)
    plt.close(fig)
    report = {
        "dataset": "lauschke-2013-embryo",
        "review_version": "video1-axial-review-v1",
        "source_video": "Supplementary Video 1",
        "source_sha256": SOURCE_HASHES[1],
        "all_61_profiles_reproduced_exactly": True,
        "spatial_control_reproduced_exactly": True,
        "reference_files_preserved": before,
        "used_source_frames": [0, 60],
        "total_source_frames": len(source),
        "shape_space_time": list(raw.shape),
        "time_range_h": [float(times[0]), float(times[-1])],
        "time_basis": "Audited burned-in timestamps; movie playback is not experiment time.",
        "scale_bar": {
            "length_um": 100,
            "video_endpoints_xy": [[23, 691], [126, 691]],
            "um_per_px": scale,
            "reading_precision_px": 1,
        },
        "polarity": "Posterior rounded end toward anterior PSM; image direction is upper-left in this movie.",
        "polarity_evidence": "Paper Fig. 1b/c caption, Supplementary Video 1 description and reviewed movie morphology.",
        "landmark_status": "Independent approximate manual P-side and A-direction landmarks; no molecular markers or cell tracking.",
        "author_roi_status": "No exact deposited author ROI. Fig. 1b-to-movie image correspondence has not been established.",
        "landmark_keyframes": AP_KEYS.tolist(),
        "strip_width_px": WIDTH_PX,
        "transverse_samples": WIDTH_PX + 1,
        "minimum_valid_samples": 16,
        "mask": "FOV and annotation exclusion only; NOT an anatomical tissue mask. Finite background may remain.",
        "endpoint": "First width-validity failure or 450 µm grid limit; not an anterior tissue edge or arrest front.",
        "channel": "Mean RGB of merged reporter/brightfield display movie, not isolated fluorescence.",
        "sampling": "Bilinear finite-width mean; no primary filtering or time smoothing.",
        "spatial_control_sigma_um": SIGMA_UM,
        "figure_orientation": "Review comparison has P at bottom as in Fig. 1c; gallery retains shared zero-at-top convention.",
        "trajectory": [
            {
                "frame": i,
                "time_h": float(times[i]),
                "p_side_xy_px": origins[i].tolist(),
                "direction_xy": directions[i].tolist(),
                "last_fov_valid_distance_um": float(positions[final_rows[i]]),
            }
            for i in range(len(times))
        ],
        "limitations": [
            "Same biological preparation does not establish same embryo as Fig. 1b.",
            "Later frames 61–125 are not validated with this straight-path adapter.",
            "No recovery of raw reporter counts, author phase analysis or material cell coordinates.",
        ],
        "evidence_urls": [
            "https://www.nature.com/articles/nature11804/figures/1",
            "https://www.nature.com/articles/nature11804#supplementary-information",
        ],
        "script_sha256": digest(__file__),
    }
    for p in paths:
        if digest(p) != before[p.name]:
            raise ValueError("Reference changed during audit")
    (records / "video1-roi-review.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in [
                    "dataset",
                    "all_61_profiles_reproduced_exactly",
                    "spatial_control_reproduced_exactly",
                    "shape_space_time",
                    "time_range_h",
                    "author_roi_status",
                ]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/lauschke-video1-review")
    )
    args = parser.parse_args()
    run(args.source_dir, args.output)

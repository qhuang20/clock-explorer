# SPDX-License-Identifier: MIT
"""Full Video 1 reconstruction with a reviewed moving P-to-A curved strip.

The original 61-frame straight-strip assets are retained for comparison. This
is a new whole-sequence geometry, not a splice after hour 10 or an exact author
ROI. The original source is an inseparable LuVeLu/brightfield display composite.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator

from paths import ASSET_ROOT
from extract_video_kymographs import decode
from reproduce_lauschke_views import SOURCE_HASHES, SIGMA_UM, read_times
from curved_strip import arc_length_path, strip_coordinates, sample_strip

SCALE = 100 / 103
WIDTH_PX = 20
DISTANCE_UM = np.arange(451, dtype=float)
DATA_SUBDIR = Path("data/derived/lauschke-2013/video1-full-curve")
FIGURE_SUBDIR = Path("figures/lauschke-2013/video1-full-curve")
# Original decoded xy pixels; first point is the approximate posterior-side
# reference. Subsequent points follow the visible PSM-side corridor toward A.
# The last guide point supplies direction beyond the 450 µm sampling cap; it is
# not a measured anterior boundary. No control point is selected by fluorescence.
KEY_PATHS = {
    0: [
        [405, 350],
        [340, 330],
        [275, 280],
        [220, 215],
        [172, 135],
        [133, 40],
        [105, -60],
    ],
    20: [
        [365, 385],
        [300, 375],
        [225, 330],
        [165, 260],
        [110, 175],
        [70, 65],
        [40, -60],
    ],
    40: [
        [375, 415],
        [310, 420],
        [235, 370],
        [170, 300],
        [120, 210],
        [80, 65],
        [50, -60],
    ],
    60: [
        [420, 460],
        [345, 450],
        [260, 410],
        [185, 345],
        [130, 250],
        [85, 65],
        [60, -60],
    ],
    72: [
        [445, 490],
        [370, 495],
        [285, 455],
        [205, 385],
        [145, 290],
        [90, 65],
        [65, -60],
    ],
    84: [
        [475, 505],
        [395, 535],
        [305, 510],
        [225, 455],
        [165, 365],
        [105, 205],
        [65, -60],
    ],
    96: [
        [500, 500],
        [425, 550],
        [335, 555],
        [250, 510],
        [185, 435],
        [125, 335],
        [65, -30],
    ],
    # The source changes pose abruptly between these adjacent frames. Bracket
    # the jump, rather than drifting a pre-jump ROI through post-jump background.
    100: [
        [500, 540],
        [440, 585],
        [350, 595],
        [260, 555],
        [190, 475],
        [125, 360],
        [65, -30],
    ],
    101: [
        [500, 430],
        [445, 470],
        [360, 480],
        [275, 450],
        [205, 390],
        [145, 300],
        [70, -20],
    ],
    108: [
        [505, 455],
        [450, 505],
        [365, 520],
        [275, 490],
        [200, 420],
        [140, 325],
        [70, -20],
    ],
    116: [
        [500, 450],
        [450, 515],
        [365, 535],
        [275, 500],
        [195, 430],
        [135, 330],
        [70, -20],
    ],
    125: [
        [500, 440],
        [455, 515],
        [370, 550],
        [275, 520],
        [195, 455],
        [135, 360],
        [75, -15],
    ],
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def geometry(times):
    keys = np.array(sorted(KEY_PATHS))
    points = np.array([KEY_PATHS[int(k)] for k in keys], float)
    controls = PchipInterpolator(times[keys], points, axis=0, extrapolate=False)(times)
    paths, normals, lengths = [], [], []
    for control in controls:
        xy, normal, length = arc_length_path(control, DISTANCE_UM, SCALE)
        paths.append(xy)
        normals.append(normal)
        lengths.append(length)
    return controls, np.array(paths), np.array(normals), np.array(lengths)


def style():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "axes.labelcolor": "#525b6b",
            "xtick.color": "#697386",
            "ytick.color": "#697386",
            "axes.edgecolor": "#9198a6",
            "savefig.dpi": 200,
        }
    )
    return plt


def overlay(ax, frame, path, normal, time_h, index, small=False):
    ax.imshow(frame)
    edges = strip_coordinates(path, normal, WIDTH_PX)
    band = np.concatenate([edges[:, 0], edges[::-1, -1]])
    ax.fill(band[:, 0], band[:, 1], color="#ffb547", alpha=0.28)
    ax.plot(path[:, 0], path[:, 1], color="#ffb547", lw=0.9 if small else 1.4)
    for edge in [edges[:, 0], edges[:, -1]]:
        ax.plot(edge[:, 0], edge[:, 1], color="#ffce7b", lw=0.4 if small else 0.7)
    # Arrowhead follows the final local tangent of the curve, never a P–A chord.
    ax.annotate(
        "",
        xy=path[-1],
        xytext=path[-24],
        arrowprops={"arrowstyle": "->", "color": "#ffb547", "lw": 1 if small else 1.6},
    )
    ax.plot(*path[0], "+", color="white", ms=5 if small else 9, mew=1.2)
    if not small:
        box = {"facecolor": "black", "alpha": 0.65, "pad": 1.8}
        ax.text(
            path[0, 0] + 10,
            path[0, 1] + 15,
            "P-side · s=0",
            color="white",
            fontsize=8,
            bbox=box,
        )
        ax.text(
            path[-1, 0] + 12,
            path[-1, 1] + 12,
            "toward A",
            color="#ffce7b",
            fontsize=8,
            bbox=box,
        )
    ax.set_title(f"Frame {index} · {time_h:.2f} h", fontsize=7 if small else 11, pad=5)
    ax.set_xlim(0, frame.shape[1])
    ax.set_ylim(frame.shape[0], 0)
    ax.axis("off")


def heat(ax, matrix, times, limits, title):
    import matplotlib
    from matplotlib.colors import Normalize

    cmap = matplotlib.colormaps["OrRd"].copy()
    cmap.set_bad("#f1f3f6")
    times = np.asarray(times)
    x = np.r_[
        times[0] - (times[1] - times[0]) / 2,
        (times[:-1] + times[1:]) / 2,
        times[-1] + (times[-1] - times[-2]) / 2,
    ]
    y = np.arange(-0.5, 451.0, 1.0)
    mesh = ax.pcolormesh(
        x,
        y,
        np.ma.masked_invalid((matrix - limits[0]) / (limits[1] - limits[0])),
        cmap=cmap,
        norm=Normalize(0, 1),
        shading="flat",
        rasterized=True,
    )
    ax.set_xlim(times[0], times[-1])
    ax.set_ylim(0, 450)
    ax.set_xlabel("Time (h)")
    ax.set_ylabel("Arc length from P-side reference (µm)")
    ax.set_title(title, loc="left", fontsize=11)
    return mesh


def render(frames, paths, normals, times, raw, smooth, limits, output):
    plt = style()
    for name, ids, cols, size in [
        ("video1-curved-roi", [0, 60, 125], 3, (11.4, 4.7)),
        (
            "video1-curved-keyframes",
            [0, 40, 60, 84, 100, 101, 108, 116, 125],
            3,
            (11.4, 11.0),
        ),
        ("video1-curved-all126", list(range(126)), 9, (18, 30)),
    ]:
        rows = (len(ids) + cols - 1) // cols
        fig, axs = plt.subplots(rows, cols, figsize=size, squeeze=False)
        for ax, i in zip(axs.flat, ids):
            overlay(ax, frames[i], paths[i], normals[i], times[i], i, len(ids) > 10)
        for ax in list(axs.flat)[len(ids) :]:
            ax.axis("off")
        fig.subplots_adjust(
            left=0.01,
            right=0.99,
            top=0.94 if rows < 3 else 0.985,
            bottom=0.13 if rows < 3 else 0.025,
            wspace=0.03,
            hspace=0.13,
        )
        if rows < 3:
            fig.text(
                0.02,
                0.065,
                "Moving 20 px strip · cross-strip mean · distance follows the curve from P toward A",
                fontsize=9,
                color="#535d6b",
            )
            fig.text(
                0.02,
                0.025,
                "P-side reference and path are approximate manual anatomy; 450 µm is a sampling cap, not an anterior boundary.",
                fontsize=8,
                color="#535d6b",
            )
        fig.savefig(output / (name + ".png"), dpi=160 if rows > 3 else 200)
        plt.close(fig)
    fig, axs = plt.subplots(1, 2, figsize=(10.8, 4.8))
    for ax, matrix, title in zip(
        axs, [raw, smooth], ["Unsmoothed · width average", "Per-frame spatial Gaussian"]
    ):
        mesh = heat(ax, matrix, times, limits, title)
    axs[1].set_ylabel("")
    fig.subplots_adjust(left=0.08, right=0.87, bottom=0.2, top=0.9, wspace=0.28)
    cb = fig.add_axes([0.89, 0.2, 0.015, 0.7])
    fig.colorbar(mesh, cax=cb, ticks=[0, 0.5, 1], label="Relative display intensity")
    fig.text(
        0.08,
        0.04,
        "All 126 frames · 0–20.92 h · identical curved ROI and color scale · no time filtering",
        fontsize=9,
        color="#535d6b",
    )
    for ext in ["png", "svg", "pdf"]:
        fig.savefig(output / ("video1-curved-spatial." + ext))
    plt.close(fig)
    with np.load(
        ASSET_ROOT / "data/derived/lauschke-2013/video1-kymograph.npz"
    ) as reference:
        old = reference["intensity"]
        old_times = reference["time_h"]
    shared = [
        float(min(np.nanmin(old), np.nanmin(raw[:, :61]))),
        float(max(np.nanmax(old), np.nanmax(raw[:, :61]))),
    ]
    fig, axs = plt.subplots(1, 2, figsize=(10.8, 4.8))
    for ax, matrix, title in zip(
        axs, [old, raw[:, :61]], ["Earlier straight reference", "Moving curved strip"]
    ):
        mesh = heat(ax, matrix, old_times, shared, title)
    axs[1].set_ylabel("")
    fig.subplots_adjust(left=0.08, right=0.87, bottom=0.2, top=0.9, wspace=0.28)
    cb = fig.add_axes([0.89, 0.2, 0.015, 0.7])
    fig.colorbar(
        mesh, cax=cb, ticks=[0, 0.5, 1], label="Shared relative display intensity"
    )
    fig.text(
        0.08,
        0.04,
        "Same 0–10 h / 20 px width · different geometry and FOV coverage · old numeric reference unchanged",
        fontsize=9,
        color="#535d6b",
    )
    for ext in ["png", "svg", "pdf"]:
        fig.savefig(output / ("video1-curved-vs-straight." + ext))
    plt.close(fig)


def run(source_dir, output_root):
    source = source_dir / "41586_2013_BFnature11804_MOESM292_ESM.mov"
    if digest(source) != SOURCE_HASHES[1]:
        raise ValueError("Video 1 source changed")
    frames = np.asarray(decode(source))
    if frames.shape != (126, 730, 737, 3):
        raise ValueError(f"Unexpected source shape {frames.shape}")
    timestamp = ASSET_ROOT / "data/derived/lauschke-2013/video1-timestamps.json"
    times = read_times(timestamp, 126)
    controls, paths, normals, lengths = geometry(times)
    if not np.isfinite(paths).all():
        raise ValueError("Control path is shorter than 450 µm")
    valid = np.zeros(frames.shape[1:3], bool)
    valid[15:-60, 15:] = True
    raw = []
    smooth = []
    counts = []
    width_control = []
    for frame, path, normal in zip(frames, paths, normals):
        value, count, _ = sample_strip(
            frame, path, normal, WIDTH_PX, valid_region=valid
        )
        filtered, _, _ = sample_strip(
            frame, path, normal, WIDTH_PX, sigma_px=SIGMA_UM / SCALE, valid_region=valid
        )
        wide, _, _ = sample_strip(frame, path, normal, 40, valid_region=valid)
        raw.append(value)
        smooth.append(filtered)
        counts.append(count)
        width_control.append(wide)
    raw = np.array(raw).T
    smooth = np.array(smooth).T
    counts = np.array(counts).T
    np.testing.assert_array_equal(np.isfinite(raw), np.isfinite(smooth))
    data = output_root / DATA_SUBDIR
    figures = output_root / FIGURE_SUBDIR
    data.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    limits = [float(np.nanmin(raw)), float(np.nanmax(raw))]
    curvature = np.linalg.norm(np.gradient(normals, axis=1), axis=-1) * SCALE
    minimum_normal_jacobian = float(np.min(1 - curvature * WIDTH_PX / 2))
    if minimum_normal_jacobian <= 0:
        raise ValueError("Finite-width normals fold at this curvature")
    broad = np.array(width_control).T
    paired = np.isfinite(raw) & np.isfinite(broad)
    width_r = float(np.corrcoef(raw[paired], broad[paired])[0, 1])
    np.savez_compressed(
        data / "video1-curved-kymograph.npz",
        intensity=raw,
        spatial_smoothed_intensity=smooth,
        time_h=times,
        position_um=DISTANCE_UM,
        origins_xy=paths[:, 0],
        path_xy=paths,
        normals_xy=normals,
        control_points_xy=controls,
        valid_width_counts=counts,
        measurement_valid_mask=np.isfinite(raw),
        width40_intensity=broad,
        original_display_limits=limits,
    )
    render(frames, paths, normals, times, raw, smooth, limits, figures)
    report = {
        "dataset": "lauschke-2013-embryo",
        "method_version": "video1-moving-curved-strip-v1",
        "source": {
            "file": source.name,
            "sha256": digest(source),
            "shape": list(frames.shape),
        },
        "clock": {
            "source": "original burned-in timestamps",
            "audit_sha256": digest(timestamp),
            "time_h": times.tolist(),
            "range_h": [float(times[0]), float(times[-1])],
            "irregular_step_retained": {
                "from_frame": 100,
                "to_frame": 101,
                "delta_h": float(times[101] - times[100]),
            },
        },
        "geometry": {
            "kind": "manually reviewed moving P-to-A curved strip",
            "key_paths_original_xy": KEY_PATHS,
            "temporal_interpolation": "PCHIP in actual hours; no extrapolation",
            "spatial_interpolation": "natural cubic in control-point chord coordinate; dense arc-length resampling",
            "scale_um_per_px": SCALE,
            "scale_basis": "100 µm / 103 source pixels; ±1 px scale-bar reading",
            "position_range_um": [0, 450],
            "distance": "physical arc length from approximate posterior-side reference",
            "width_px": WIDTH_PX,
            "width_um": WIDTH_PX * SCALE,
            "normal_samples": WIDTH_PX + 1,
            "valid_width_fraction": 0.75,
            "path_length_um": lengths.tolist(),
            "minimum_normal_jacobian": minimum_normal_jacobian,
            "validity": "source FOV/text only; no anatomical segmentation; first insufficient-width row ends profile",
            "polarity": "P-side origin toward anterior PSM; UI A above P; source frames unrotated",
        },
        "signal": {
            "estimator": "mean decoded RGB display values; bilinear transverse interpolation and arithmetic width mean",
            "channel": "inseparable LuVeLu / brightfield composite; not raw fluorescence",
            "primary_filter": "none; cross-strip averaging only",
            "spatial_control": {
                "sigma_um": SIGMA_UM,
                "sigma_source_px": SIGMA_UM / SCALE,
                "operation": "per-frame image Gaussian, then identical strip; same limits and measurement mask",
            },
            "temporal_filter": "none",
            "normalization_limits": limits,
        },
        "coverage": {
            "used": 126,
            "total": 126,
            "shape_space_time": list(raw.shape),
            "missing_values": int(np.isnan(raw).sum()),
            "finite_rows_per_frame": np.isfinite(raw).sum(axis=0).tolist(),
        },
        "reference": {
            "input": "data/derived/lauschke-2013/video1-kymograph.npz",
            "sha256": digest(
                ASSET_ROOT / "data/derived/lauschke-2013/video1-kymograph.npz"
            ),
            "range_h": [0, 10],
            "unchanged": True,
            "comparison": "Full sequence re-extracted with the curved method; no early/late method splice. Early values differ from straight reference.",
        },
        "limitations": [
            "Independent approximate manual path, not a deposited author ROI, molecular landmark, automated anatomical segmentation or cell tracking.",
            "P-to-A regional polarity does not identify exact tissue endpoints; the 450 µm cap is not PSM length.",
            "Compressed mixed display intensities retain brightfield/background contributions. Moving curves do not remove tissue deformation or give material wave speed.",
        ],
        "review": {
            "representative_frames": [0, 40, 60, 84, 100, 101, 108, 116, 125],
            "pose_change": {
                "frames": [100, 101],
                "time_h": [float(times[100]), float(times[101])],
                "action": "independent adjacent-frame manual key paths; no interpolation across an unbracketed source jump",
            },
            "all_frame_overlay": str(FIGURE_SUBDIR / "video1-curved-all126.png"),
            "width_sensitivity": {
                "width_control_px": 40,
                "pooled_20_40_correlation": width_r,
                "note": "40 px profile stored separately; primary retains prior 20 px width, not chosen to optimize wave appearance",
            },
        },
        "script_sha256": digest(__file__),
        "sampler_sha256": digest(Path(__file__).with_name("curved_strip.py")),
    }
    (data / "video1-curved-provenance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "data": str(data),
                "figures": str(figures),
                "coverage": report["coverage"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=ASSET_ROOT / "data/source-archive/lauschke-2013",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    run(args.source_dir, args.output_root)

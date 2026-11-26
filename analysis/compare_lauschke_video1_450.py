# SPDX-License-Identifier: MIT
"""Extend Video 1's processing comparison to its unchanged 450 µm grid.

No original asset is overwritten. Validity remains the preserved FOV/annotation
mask; visual corridor review does not create an anatomical tissue segmentation.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from paths import ASSET_ROOT
from extract_video_kymographs import decode
from reproduce_lauschke_views import (
    SOURCE_HASHES,
    SIGMA_UM,
    WIDTH_PX,
    ap_geometry,
    read_times,
    sample,
)
from compare_lauschke_video1 import processing_arrays, time_background

SCALE = 100 / 103
CAP_UM = 450
RESIDUAL_LIMIT = 55.0


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fov_counts(shape, origins, directions, positions):
    """Reconstruct FOV/annotation coverage without claiming tissue identity."""
    height, width = shape[:2]
    counts = []
    offsets = np.linspace(-WIDTH_PX / 2, WIDTH_PX / 2, WIDTH_PX + 1)
    for origin, direction in zip(origins, directions):
        normal = np.array([-direction[1], direction[0]])
        xy = (
            origin
            + positions[:, None, None] / SCALE * direction
            + offsets[None, :, None] * normal
        )
        valid = (
            (xy[..., 0] >= 15)
            & (xy[..., 0] <= width - 1)
            & (xy[..., 1] >= 15)
            & (xy[..., 1] < height - 60)
        )
        count = valid.sum(axis=1)
        inside = np.logical_and.accumulate(count >= 16)
        counts.append(np.where(inside, count, 0))
    return np.stack(counts, axis=1)


def display_tail(residual, limit=RESIDUAL_LIMIT):
    below = int(np.count_nonzero(residual < -limit))
    above = int(np.count_nonzero(residual > limit))
    extension = (
        "both" if below and above else "min" if below else "max" if above else "neither"
    )
    return {
        "limits": [-limit, limit],
        "below_scale_count": below,
        "above_scale_count": above,
        "finite_min": float(np.nanmin(residual)),
        "finite_max": float(np.nanmax(residual)),
        "colorbar_extend": extension,
        "numeric_values_clipped": False,
    }


def style():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 10,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "savefig.dpi": 300,
        }
    )
    return plt


def draw_roi(ax, frame, origin, direction, end_um, title, small=False):
    from matplotlib.patches import Polygon

    ax.imshow(frame)
    end = origin + end_um / SCALE * direction
    requested = origin + CAP_UM / SCALE * direction
    normal = np.array([-direction[1], direction[0]])
    corners = np.array(
        [
            origin + 10 * normal,
            end + 10 * normal,
            end - 10 * normal,
            origin - 10 * normal,
        ]
    )
    ax.add_patch(Polygon(corners, facecolor="#ffad43", alpha=0.23))
    ax.annotate(
        "",
        xy=end,
        xytext=origin,
        arrowprops={"arrowstyle": "->", "color": "#ffad43", "lw": 1.5},
    )
    ax.plot([end[0], requested[0]], [end[1], requested[1]], "--", color="#c9ced8", lw=1)
    ax.plot(*origin, "+", color="white", ms=8 if small else 11, mew=1.5)
    ax.plot(*end, "o", mfc="none", mec="#c9b1ff", ms=5 if small else 8, mew=1.2)
    if not small:
        ax.text(
            origin[0] + 10,
            origin[1] + 18,
            "P-side*",
            color="white",
            fontsize=8,
            bbox={"facecolor": "black", "alpha": 0.65, "pad": 2},
        )
        middle = origin + 250 / SCALE * direction
        ax.text(
            middle[0] - 12,
            middle[1] + 22,
            "toward A",
            color="#ffd59e",
            fontsize=8,
            ha="right",
            bbox={"facecolor": "black", "alpha": 0.65, "pad": 2},
        )
    ax.set_title(title, fontsize=8 if small else 11, pad=5)
    ax.set_xlim(0, frame.shape[1])
    ax.set_ylim(frame.shape[0], 0)
    ax.axis("off")


def edges(values):
    return np.r_[
        values[0] - (values[1] - values[0]) / 2,
        (values[1:] + values[:-1]) / 2,
        values[-1] + (values[-1] - values[-2]) / 2,
    ]


def render(
    raw,
    spatial,
    residual,
    support,
    positions,
    times,
    limits,
    frames,
    origins,
    directions,
    output,
):
    import matplotlib
    from matplotlib.colors import LinearSegmentedColormap, Normalize

    plt = style()
    last = np.array(
        [np.flatnonzero(np.isfinite(raw[:, i]))[-1] for i in range(len(times))]
    )
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 4.7))
    for ax, i in zip(axes, [0, 30, 60]):
        draw_roi(
            ax,
            frames[i],
            origins[i],
            directions[i],
            positions[last[i]],
            f"Frame {i} · {times[i]:.2f} h · FOV end {positions[last[i]]:.0f} µm",
        )
    fig.text(
        0.02,
        0.09,
        "Orange: unchanged 20 px strip toward A    Violet circle: last FOV-valid sample    Dashed: missing extension to 450 µm cap",
        fontsize=9,
        color="#535d6b",
    )
    fig.text(
        0.02,
        0.035,
        "*Approximate P-side landmark. A 450 µm cap is not tissue length or an anterior boundary; FOV validity is not tissue segmentation.",
        fontsize=9,
        color="#535d6b",
    )
    fig.subplots_adjust(left=0.01, right=0.99, top=0.95, bottom=0.16, wspace=0.04)
    fig.savefig(output / "video1-processing-roi-450.png", dpi=300)
    plt.close(fig)
    fig, axes = plt.subplots(8, 8, figsize=(16, 16))
    for i, ax in enumerate(axes.flat):
        if i < len(frames):
            draw_roi(
                ax,
                frames[i],
                origins[i],
                directions[i],
                positions[last[i]],
                f"{i} · {times[i]:.2f} h · {positions[last[i]]:.0f} µm",
                small=True,
            )
        else:
            ax.axis("off")
    fig.subplots_adjust(
        left=0.005, right=0.995, top=0.985, bottom=0.005, wspace=0.05, hspace=0.16
    )
    fig.savefig(output / "video1-processing-roi-all-frames-450.png", dpi=180)
    plt.close(fig)
    cmap = matplotlib.colormaps["OrRd"].copy()
    cmap.set_bad("#f1f3f6")
    signed = LinearSegmentedColormap.from_list(
        "signed_component", ["#6755b8", "#f8f8fb", "#c63d1d"]
    )
    signed.set_bad("#f1f3f6")
    fig, axes = plt.subplots(1, 3, figsize=(13.3, 5.0))
    lo, hi = limits
    meshes = []
    for i, (ax, array, title) in enumerate(
        zip(
            axes,
            [(raw - lo) / (hi - lo), (spatial - lo) / (hi - lo), residual],
            ["1  Unsmoothed", "2  Spatial filter", "3  Temporal-baseline residual"],
        )
    ):
        mesh = ax.pcolormesh(
            edges(times),
            edges(positions),
            np.ma.masked_invalid(array),
            cmap=cmap if i < 2 else signed,
            norm=Normalize(0, 1)
            if i < 2
            else Normalize(-RESIDUAL_LIMIT, RESIDUAL_LIMIT),
            shading="flat",
            rasterized=True,
        )
        meshes.append(mesh)
        ax.set_xlim(times[0], times[-1])
        ax.set_ylim(0, CAP_UM)
        ax.set_title(title, loc="left", fontsize=11, weight="bold")
        ax.set_xlabel("Time (h)")
        ax.set_yticks(np.arange(0, 451, 50))
        if i == 0:
            ax.set_ylabel("Distance from P-side reference (µm)")
        else:
            ax.tick_params(labelleft=False)
    fig.subplots_adjust(left=0.055, right=0.89, bottom=0.20, top=0.88, wspace=0.32)
    # All data axes are created first: axes_1..3. These are axes_4 and axes_5.
    box = axes[1].get_position()
    intensity_bar = fig.add_axes(
        [box.x1 + 0.012, box.y0 + 0.03, 0.009, box.height - 0.06]
    )
    fig.colorbar(
        meshes[1],
        cax=intensity_bar,
        ticks=[0, 0.5, 1],
        label="Relative display intensity",
    )
    box = axes[2].get_position()
    residual_bar = fig.add_axes(
        [box.x1 + 0.012, box.y0 + 0.03, 0.009, box.height - 0.06]
    )
    fig.colorbar(
        meshes[2],
        cax=residual_bar,
        label="Signed residual (display units)",
        extend=display_tail(residual)["colorbar_extend"],
    )
    caution = (support < 0.8) & np.isfinite(residual)
    # Draw only the true reduced-support region. Clearing a PolyQuadMesh's
    # color array can also clear its measurement mask in recent Matplotlib.
    hatches = axes[2].contourf(
        times,
        positions,
        caution.astype(float),
        levels=[0.5, 1.5],
        colors="none",
        hatches=["///"],
    )
    hatches.set_edgecolor("#8b91a0")
    hatches.set_linewidth(0)
    fig.text(
        0.025,
        0.085,
        "Same 0–450 µm grid · 61 frames · Original measurement mask and intensity scale retained; gray = missing FOV/annotation coverage.",
        fontsize=9,
        color="#535d6b",
    )
    fig.text(
        0.025,
        0.035,
        "Residual = spatially filtered display − Gaussian time baseline (σt = 1.5 h). Hatching: <80% baseline support at that distance and time.",
        fontsize=9,
        color="#535d6b",
    )
    for ext in ["png", "svg", "pdf"]:
        fig.savefig(output / f"video1-processing-comparison-450.{ext}", dpi=300)
    plt.close(fig)


def run(source_dir, output):
    base = ASSET_ROOT / "data/derived/lauschke-2013"
    originals = sorted(p for p in base.glob("video1-*") if p.is_file())
    originals += sorted(
        p
        for p in (ASSET_ROOT / "figures/lauschke-2013").glob("video1-*")
        if p.is_file()
    )
    before = {str(p.relative_to(ASSET_ROOT)): digest(p) for p in originals}
    movie = source_dir / "41586_2013_BFnature11804_MOESM292_ESM.mov"
    if digest(movie) != SOURCE_HASHES[1]:
        raise ValueError("Source Video 1 hash changed")
    all_frames = np.array(decode(movie))
    frames = all_frames[:61]
    if len(all_frames) != 126:
        raise ValueError("Unexpected source frame count")
    current = dict(np.load(base / "video1-kymograph.npz"))
    old = dict(np.load(base / "video1-processing-comparison.npz"))
    positions = current["position_um"]
    times = current["time_h"]
    origins, directions = ap_geometry(61)
    np.testing.assert_array_equal(positions, np.arange(451.0))
    for actual, expected in [
        (origins, current["origins_xy"]),
        (directions, current["directions_xy"]),
        (times, read_times(base / "video1-timestamps.json", 126)[:61]),
    ]:
        np.testing.assert_array_equal(actual, expected)
    raw = sample(frames, origins, directions, positions, SCALE)
    spatial = sample(frames, origins, directions, positions, SCALE, sigma_um=SIGMA_UM)
    for label, array in [("intensity", raw), ("spatial_smoothed_intensity", spatial)]:
        np.testing.assert_array_equal(array, current[label], err_msg=label)
    counts = fov_counts(frames.shape[1:], origins, directions, positions)
    np.testing.assert_array_equal(counts >= 16, np.isfinite(raw))
    baseline, residual, support = processing_arrays(raw, spatial, times, 1.5)
    np.testing.assert_array_equal(np.isfinite(raw), np.isfinite(residual))
    np.testing.assert_allclose(
        (baseline + residual)[np.isfinite(spatial)],
        spatial[np.isfinite(spatial)],
        rtol=0,
        atol=3e-14,
    )
    for label, array in [
        ("unsmoothed", raw),
        ("spatial_filtered", spatial),
        ("slow_background", baseline),
        ("oscillatory_component", residual),
        ("baseline_support_fraction", support),
    ]:
        np.testing.assert_array_equal(
            array[:351], old[label], err_msg="archived 350 " + label
        )
    lo, hi = float(np.nanmin(raw)), float(np.nanmax(raw))
    np.testing.assert_array_equal([lo, hi], old["original_display_limits"])
    figures = output / "figures"
    data = output / "data"
    figures.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    render(
        raw,
        spatial,
        residual,
        support,
        positions,
        times,
        (lo, hi),
        frames,
        origins,
        directions,
        figures,
    )
    alternatives = {}
    for sigma in [1.0, 2.0]:
        alternative, _ = time_background(spatial, times, sigma)
        alternatives[f"component_sigma_{sigma:g}h"] = np.where(
            np.isfinite(spatial), spatial - alternative, np.nan
        )
    np.savez_compressed(
        data / "video1-processing-comparison-450.npz",
        unsmoothed=raw,
        spatial_filtered=spatial,
        slow_background=baseline,
        oscillatory_component=residual,
        baseline_support_fraction=support,
        time_h=times,
        position_um=positions,
        origins_xy=origins,
        directions_xy=directions,
        original_display_limits=[lo, hi],
        baseline_sigma_h=1.5,
        measurement_valid_mask=np.isfinite(raw),
        fov_valid_width_counts=counts,
        baseline_reduced_support=(support < 0.8) & np.isfinite(raw),
        residual_display_limits=[-RESIDUAL_LIMIT, RESIDUAL_LIMIT],
        **alternatives,
    )
    coverage = []
    for i in range(61):
        end = float(positions[np.flatnonzero(np.isfinite(raw[:, i]))[-1]])
        coverage.append(
            {
                "frame": i,
                "time_h": float(times[i]),
                "last_fov_valid_distance_um": end,
                "requested_cap_um": CAP_UM,
                "cap_xy_px": (origins[i] + CAP_UM / SCALE * directions[i]).tolist(),
                "last_valid_xy_px": (origins[i] + end / SCALE * directions[i]).tolist(),
                "missing_distance_rows": int(np.isnan(raw[:, i]).sum()),
                "tissue_status": "visual corridor reviewed; not anatomically segmented",
            }
        )
    report = {
        "dataset": "lauschke-2013-embryo",
        "method_version": "video1-processing-comparison-450-v1",
        "source": {
            "filename": movie.name,
            "sha256": digest(movie),
            "bytes": movie.stat().st_size,
            "decoded_shape": list(all_frames.shape),
        },
        "source_url": "https://static-content.springer.com/esm/art%3A10.1038%2Fnature11804/MediaObjects/41586_2013_BFnature11804_MOESM292_ESM.mov",
        "reviewed_analysis_range_um": [0, CAP_UM],
        "shape_space_time": list(raw.shape),
        "time_range_h": [float(times[0]), float(times[-1])],
        "full_450_primary_and_spatial_control_reproduced_exactly": True,
        "original_primary_measurement_mask_preserved_exactly": True,
        "archived_350_all_five_arrays_preserved_exactly": True,
        "reference_files_preserved": before,
        "original_files_preserved_exactly": True,
        "sampling": {
            "scale_um_per_px": SCALE,
            "width_px": WIDTH_PX,
            "samples_across_width": 21,
            "minimum_valid_samples": 16,
            "mask": "FOV/annotation exclusion ONLY; no anatomical target-tissue mask",
            "estimator": "bilinear mean RGB display sampling, transverse mean, first failed width-valid row terminates profile",
            "channel": "LuVeLu/brightfield merged display; not isolated reporter or raw fluorescence",
        },
        "coverage": {
            "last_valid_distance_range_um": [
                min(x["last_fov_valid_distance_um"] for x in coverage),
                max(x["last_fov_valid_distance_um"] for x in coverage),
            ],
            "frames_reaching_450_cap": int(np.isfinite(raw[-1]).sum()),
            "frames_with_missing_distances": int(np.isnan(raw).any(axis=0).sum()),
            "missing_space_time_samples": int(np.isnan(raw).sum()),
            "per_frame": coverage,
        },
        "tissue_review": {
            "method": "Inspect all 61 original-orientation finite-width ROI overlays; representative views at 0,5,10 h.",
            "finding": "The reviewed strip follows a visible embryo/PSM-side corridor toward the image edge. No clear tissue-exterior segment is identified before the FOV-valid end at contact-sheet resolution.",
            "qualification": "Visual corridor support is not a pixelwise anatomical segmentation and does not identify an exact anterior PSM boundary. Finite FOV-valid samples may include BF/background or adjacent tissue; these are not certified tissue expression.",
            "cap_meaning": "450 µm is the sampling/display cap, not fixed PSM length, an exact A endpoint or oscillation-arrest front.",
        },
        "spatial_filter": {
            "sigma_um": SIGMA_UM,
            "sigma_video_px": SIGMA_UM / SCALE,
            "operation": "Gaussian each full source image independently, then same strip and mask",
            "temporal_filter": False,
        },
        "temporal_baseline": {
            "sigma_h": 1.5,
            "method": "existing finite-value Gaussian physical-time/trapezoidal quadrature from compare_lauschke_video1.py",
            "residual": "spatial_filtered - slow_background, retaining signed values and measurement NaNs",
            "role": "auxiliary temporal diagnostic, not spatial-only processing, isolated fluorescence or phase",
            "support_hatching": "only finite residual samples where baseline_support_fraction <0.8; support is position/time specific",
            "baseline_estimates_at_missing_times": "slow_background may be estimated across missing times; residual and displayed matrices never fill those missing measurements",
        },
        "display": {
            "first_two_limits_from_original_full_reference": [lo, hi],
            "first_two_palette": "OrRd",
            "residual": display_tail(residual),
            "residual_palette": ["#6755b8", "#f8f8fb", "#c63d1d"],
            "orientation": "P-side zero bottom; increasing anteriorward above; source frames unchanged",
            "data_axes": ["axes_1", "axes_2", "axes_3"],
            "intensity_colorbar_axes": ["axes_4"],
            "residual_colorbar_axes": ["axes_5"],
            "flip_y": False,
        },
        "limitations": [
            "Approximate manual P-side origin/direction, not a recovered author ROI or cell tracking.",
            "No anatomical tissue segmentation; full strip identity remains qualified as a visual corridor review.",
            "Later bent frames61–125 are not covered by this straight-strip adapter.",
            "The residual scale remains ±55; its extension triangle marks values beyond that display range. No signed numeric value is clipped.",
        ],
        "script": "analysis/compare_lauschke_video1_450.py",
        "script_sha256": digest(__file__),
        "dependencies": {
            name: digest(Path(__file__).with_name(name))
            for name in [
                "compare_lauschke_video1.py",
                "reproduce_lauschke_views.py",
                "extract_video_kymographs.py",
            ]
        },
        "environment": {
            name: __import__(name).__version__
            for name in ["numpy", "scipy", "av", "matplotlib"]
        },
    }
    for relative, sha in before.items():
        if digest(ASSET_ROOT / relative) != sha:
            raise ValueError("Original asset changed during 450 review")
    (data / "video1-processing-comparison-450.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in [
                    "shape_space_time",
                    "full_450_primary_and_spatial_control_reproduced_exactly",
                    "archived_350_all_five_arrays_preserved_exactly",
                ]
            },
            indent=2,
        )
    )
    print(
        json.dumps(
            {
                "coverage": {
                    k: v for k, v in report["coverage"].items() if k != "per_frame"
                },
                "residual_display": report["display"]["residual"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/lauschke-video1-450-review")
    )
    args = parser.parse_args()
    run(args.source_dir, args.output)

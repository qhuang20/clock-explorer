# SPDX-License-Identifier: MIT
"""Controlled processing comparison on a conservative Video 1 axial segment.

Preserves the full 0–450 µm reference. The new 0–350 µm endpoint is an analysis
cutoff, not an inferred anatomical anterior boundary or oscillation-arrest front.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from paths import ASSET_ROOT
from extract_video_kymographs import decode
from reproduce_lauschke_views import SOURCE_HASHES, SIGMA_UM, ap_geometry, sample


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def time_background(values, times_h, sigma_h=1.5):
    """Gaussian low-pass in physical time, with finite-value quadrature weights.

    Returns a slow baseline and the fraction of full Gaussian support available
    at each space/time point. This never fills a missing measurement in residuals.
    """
    values = np.asarray(values, dtype=float)
    times = np.asarray(times_h, dtype=float)
    if (
        values.ndim != 2
        or times.ndim != 1
        or len(times) < 2
        or values.shape[1] != len(times)
        or not np.isfinite(times).all()
        or not (np.diff(times) > 0).all()
        or not np.isfinite(sigma_h)
        or sigma_h <= 0
    ):
        raise ValueError(
            "Expected a space × time matrix, increasing hours and positive sigma"
        )
    dt = np.diff(times)
    widths = np.r_[dt[0] / 2, (dt[:-1] + dt[1:]) / 2, dt[-1] / 2]
    kernel = np.exp(-0.5 * ((times[:, None] - times[None, :]) / sigma_h) ** 2) * widths
    finite = np.isfinite(values)
    denominator = finite.astype(float) @ kernel.T
    numerator = np.where(finite, values, 0) @ kernel.T
    baseline = np.divide(
        numerator, denominator, out=np.full_like(values, np.nan), where=denominator > 0
    )
    support = denominator / (np.sqrt(2 * np.pi) * sigma_h)
    return baseline, support


def processing_arrays(raw, spatial, times, sigma_h=1.5):
    raw, spatial = np.asarray(raw, float), np.asarray(spatial, float)
    if raw.shape != spatial.shape or not np.array_equal(
        np.isfinite(raw), np.isfinite(spatial)
    ):
        raise ValueError("Processing variants must retain the same measurement mask")
    baseline, support = time_background(spatial, times, sigma_h)
    residual = np.where(np.isfinite(spatial), spatial - baseline, np.nan)
    return baseline, residual, support


def draw_roi(ax, frame, origin, direction, old_end_um, title):
    ax.imshow(frame)
    scale = 100 / 103
    end = origin + 350 / scale * direction
    old_end = origin + old_end_um / scale * direction
    normal = np.array([-direction[1], direction[0]])
    corners = np.array(
        [
            origin + 10 * normal,
            end + 10 * normal,
            end - 10 * normal,
            origin - 10 * normal,
        ]
    )
    ax.plot([end[0], old_end[0]], [end[1], old_end[1]], "--", color="#c9ced8", lw=1.2)
    ax.fill(corners[:, 0], corners[:, 1], color="#ffad43", alpha=0.25)
    ax.annotate(
        "",
        xy=end,
        xytext=origin,
        arrowprops={"arrowstyle": "->", "color": "#ffad43", "lw": 1.7},
    )
    ax.plot(*origin, "+", color="white", ms=10, mew=1.4)
    ax.plot(*end, "o", mfc="none", mec="#c9b1ff", mew=1.6, ms=8)
    ax.text(
        origin[0] + 10,
        origin[1] + 20,
        "P-side*",
        color="white",
        fontsize=8,
        bbox={"facecolor": "black", "alpha": 0.65, "pad": 2},
    )
    ax.text(
        end[0] + 15,
        end[1] - 8,
        "350 µm*",
        color="#dfceff",
        fontsize=8,
        bbox={"facecolor": "black", "alpha": 0.65, "pad": 2},
    )
    ax.set_title(title, fontsize=11, color="#252a35", pad=7)
    ax.set_xlim(0, frame.shape[1])
    ax.set_ylim(frame.shape[0], 0)
    ax.axis("off")


def plot_comparison(
    raw, spatial, residual, support, positions, times, limits, destination
):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, Normalize

    cmap = matplotlib.colormaps["OrRd"].copy()
    cmap.set_bad("#f1f3f6")
    signed = LinearSegmentedColormap.from_list(
        "signed_component", ["#6755b8", "#f8f8fb", "#c63d1d"]
    )
    signed.set_bad("#f1f3f6")
    lo, hi = limits
    normalized = [(a - lo) / (hi - lo) for a in (raw, spatial)]
    amplitude = max(5.0, float(np.ceil(np.nanmax(np.abs(residual)) / 5) * 5))
    xedges = np.r_[
        times[0] - (times[1] - times[0]) / 2,
        (times[1:] + times[:-1]) / 2,
        times[-1] + (times[-1] - times[-2]) / 2,
    ]
    yedges = np.r_[
        positions[0] - 0.5, (positions[1:] + positions[:-1]) / 2, positions[-1] + 0.5
    ]
    fig, axes = plt.subplots(1, 3, figsize=(13.3, 4.9), layout="constrained")
    for i, (ax, array, title) in enumerate(
        zip(
            axes,
            normalized + [residual],
            ["1  Unsmoothed", "2  Spatial filter", "3  Oscillatory component"],
        )
    ):
        mesh = ax.pcolormesh(
            xedges,
            yedges,
            np.ma.masked_invalid(array),
            cmap=cmap if i < 2 else signed,
            norm=Normalize(0, 1) if i < 2 else Normalize(-amplitude, amplitude),
            shading="flat",
            rasterized=True,
        )
        ax.set_xlim(times[0], times[-1])
        ax.set_ylim(positions[-1], 0)
        ax.set_title(title, loc="left", fontsize=11, weight="bold")
        ax.set_xlabel("Time (h)")
        if i == 0:
            ax.set_ylabel("Distance from P-side reference (µm)")
        else:
            ax.tick_params(labelleft=False)
        if i == 1:
            fig.colorbar(
                mesh,
                ax=list(axes[:2]),
                shrink=0.82,
                pad=0.02,
                label="Relative display intensity",
                ticks=[0, 0.5, 1],
            )
        if i == 2:
            fig.colorbar(
                mesh,
                ax=ax,
                shrink=0.82,
                pad=0.02,
                label="Signed residual (display units)",
            )
            good = np.all(support >= 0.8, axis=0)
            if good.any():
                left, right = times[np.flatnonzero(good)[[0, -1]]]
                for a, b in [(times[0], left), (right, times[-1])]:
                    ax.axvspan(
                        a,
                        b,
                        facecolor="#d9dce5",
                        alpha=0.32,
                        hatch="//",
                        edgecolor="#8b91a0",
                        linewidth=0,
                    )
    fig.get_layout_engine().set(rect=(0, 0.14, 1, 0.83))
    fig.text(
        0.03,
        0.065,
        "Same 0–350 µm ROI · 61 frames · First two panels share the unchanged original intensity scale.",
        fontsize=10,
        color="#535d6b",
    )
    fig.text(
        0.03,
        0.017,
        "Component = spatially filtered display − slow baseline (Gaussian σt = 1.5 h). Hatched time ends: reduced baseline support.",
        fontsize=9,
        color="#535d6b",
    )
    for fmt in ["png", "svg", "pdf"]:
        fig.savefig(destination / f"video1-processing-comparison.{fmt}", dpi=180)
    plt.close(fig)


def run(source_dir, output_root, sigma_h=1.5):
    data = ASSET_ROOT / "data/derived/lauschke-2013"
    references = [
        data / name
        for name in [
            "video1-kymograph.npz",
            "video1-provenance.json",
            "video1-timestamps.json",
        ]
    ]
    before = {p.name: digest(p) for p in references}
    movie = source_dir / "41586_2013_BFnature11804_MOESM292_ESM.mov"
    if digest(movie) != SOURCE_HASHES[1]:
        raise ValueError("Unexpected source movie")
    frames = np.asarray(decode(movie))[:61]
    with np.load(references[0]) as saved:
        full = saved["intensity"].copy()
        full_spatial = saved["spatial_smoothed_intensity"].copy()
        times = saved["time_h"].copy()
        positions = saved["position_um"].copy()
        origins = saved["origins_xy"].copy()
        directions = saved["directions_xy"].copy()
    reviewed_origins, reviewed_directions = ap_geometry(len(frames))
    np.testing.assert_array_equal(origins, reviewed_origins)
    np.testing.assert_array_equal(directions, reviewed_directions)
    selected = positions <= 350
    positions = positions[selected]
    raw = sample(frames, origins, directions, positions, 100 / 103)
    spatial = sample(
        frames, origins, directions, positions, 100 / 103, sigma_um=SIGMA_UM
    )
    np.testing.assert_allclose(raw, full[selected], atol=0, rtol=0, equal_nan=True)
    np.testing.assert_allclose(
        spatial, full_spatial[selected], atol=0, rtol=0, equal_nan=True
    )
    if not np.isfinite(raw).all():
        raise ValueError("The proposed common ROI has missing FOV coverage")
    baseline, component, support = processing_arrays(raw, spatial, times, sigma_h)
    np.testing.assert_allclose(baseline + component, spatial, rtol=0, atol=3e-14)
    sensitivity = {}
    alternatives = {}
    common = (times >= 2) & (times <= 8)
    for sigma in [1.0, 2.0]:
        alternative, _ = time_background(spatial, times, sigma)
        alternative = spatial - alternative
        alternatives[f"component_sigma_{sigma:g}h"] = alternative
        sensitivity[str(sigma)] = {
            "correlation_central_2_to_8h": float(
                np.corrcoef(
                    component[:, common].ravel(), alternative[:, common].ravel()
                )[0, 1]
            ),
            "median_absolute_difference_display_units": float(
                np.median(np.abs(component[:, common] - alternative[:, common]))
            ),
        }
    lo, hi = float(np.nanmin(full)), float(np.nanmax(full))
    figures = output_root / "figures/lauschke-2013"
    records = output_root / "data/derived/lauschke-2013"
    figures.mkdir(parents=True, exist_ok=True)
    records.mkdir(parents=True, exist_ok=True)
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
        }
    )
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 4.7))
    for ax, i in zip(axes, [0, 30, 60]):
        last = np.flatnonzero(np.isfinite(full[:, i]))[-1]
        draw_roi(
            ax,
            frames[i],
            origins[i],
            directions[i],
            float(last),
            f"{times[i]:.2f} h · frame {i}",
        )
    fig.text(
        0.02,
        0.105,
        "Orange: retained 0–350 µm strip    Violet circle: analysis endpoint    Dashed gray: original extension",
        fontsize=9,
        color="#535d6b",
    )
    fig.text(
        0.02,
        0.045,
        "*Independent P-side reference and conservative cutoff; neither endpoint is an author-deposited anatomical landmark.",
        fontsize=9,
        color="#535d6b",
    )
    fig.subplots_adjust(left=0.01, right=0.99, top=0.96, bottom=0.18, wspace=0.04)
    fig.savefig(figures / "video1-processing-roi.png", dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(8, 8, figsize=(15, 15))
    for i, ax in enumerate(axes.flat):
        if i < len(frames):
            last = np.flatnonzero(np.isfinite(full[:, i]))[-1]
            draw_roi(
                ax,
                frames[i],
                origins[i],
                directions[i],
                float(last),
                f"{i} · {times[i]:.2f} h",
            )
        else:
            ax.axis("off")
    fig.subplots_adjust(
        left=0.01, right=0.99, top=0.98, bottom=0.01, wspace=0.07, hspace=0.18
    )
    fig.savefig(figures / "video1-processing-roi-all-frames.png", dpi=120)
    plt.close(fig)
    plot_comparison(
        raw, spatial, component, support, positions, times, (lo, hi), figures
    )
    np.savez_compressed(
        records / "video1-processing-comparison.npz",
        unsmoothed=raw,
        spatial_filtered=spatial,
        slow_background=baseline,
        oscillatory_component=component,
        baseline_support_fraction=support,
        time_h=times,
        position_um=positions,
        origins_xy=origins,
        directions_xy=directions,
        original_display_limits=[lo, hi],
        baseline_sigma_h=sigma_h,
        **alternatives,
    )
    report = {
        "dataset": "lauschke-2013-embryo",
        "method_version": "video1-processing-comparison-v1",
        "source_sha256": SOURCE_HASHES[1],
        "reference_files_preserved": before,
        "original_reference_range_um": [0, 450],
        "reviewed_analysis_range_um": [0, 350],
        "endpoint_status": "Conservative common visible-tissue analysis cutoff, not anatomical anterior edge or arrest front.",
        "endpoint_review": "Five-time review at 0,2.5,5,7.5,10 h plus all-frame ROI contact sheet. The 400–450 µm extension approaches the FOV edge; 350 µm stays within the visible PSM-side strip.",
        "roi_origin_direction": "Unchanged approximate manual P-side landmarks and P→A directions from the preserved reference.",
        "strip_width_px": 20,
        "transverse_samples": 21,
        "um_per_video_px": 100 / 103,
        "full_61_frame_cropped_reference_match": True,
        "shape_space_time": list(raw.shape),
        "time_range_h": [float(times[0]), float(times[-1])],
        "timestamps": "Unchanged audited burned-in times, not playback times.",
        "spatial_filter": {
            "sigma_um": SIGMA_UM,
            "sigma_video_px": SIGMA_UM / (100 / 103),
            "operation": "Gaussian each full display image, then unchanged finite-width sampler; no added temporal smoothing of primary signal.",
        },
        "background": {
            "input": "Spatially filtered display matrix",
            "method": "Gaussian low-pass at each physical distance using actual hours and trapezoidal quadrature; finite-value normalized.",
            "sigma_h": sigma_h,
            "component": "spatial_filtered - slow_background",
            "support_caution_threshold": 0.8,
            "edge_caution_times_h": times[np.any(support < 0.8, axis=0)].tolist(),
            "interpretation": "Signed oscillatory display contrast, not recovered fluorescence, phase, or proof of a biological oscillator at every pixel.",
        },
        "display": {
            "intensity_limits_from_full_reference": [lo, hi],
            "intensity_palette": "OrRd",
            "component_palette": "violet–white–orange, symmetric about zero; independent signed display-unit scale",
            "orientation": "Shared gallery convention: zero at top; time increases right.",
        },
        "sensitivity": sensitivity,
        "limitations": [
            "Merged 8-bit display movie; in-tissue RGB channels are identical in reviewed frames, so YFP cannot be separated by channel selection.",
            "No exact author ROI or confirmed Fig. 1b specimen identity; manual anatomical approximation.",
            "The new cutoff removes the unreviewed anterior extension, not all in-tissue BF/background contributions.",
            "Temporal baseline uses reduced support at record ends; hatched regions mark this and are not absent expression.",
            "No per-position amplitude normalization, negative-value clipping, Hilbert phase, or reconstruction of missing frames.",
        ],
        "roi_endpoints_xy": (origins + 350 / (100 / 103) * directions).tolist(),
        "script_sha256": digest(__file__),
    }
    for p in references:
        if digest(p) != before[p.name]:
            raise ValueError("Preserved reference changed")
    (records / "video1-processing-comparison.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in [
                    "shape_space_time",
                    "reviewed_analysis_range_um",
                    "full_61_frame_cropped_reference_match",
                    "sensitivity",
                ]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/lauschke-video1-processing")
    )
    parser.add_argument("--background-sigma-h", type=float, default=1.5)
    args = parser.parse_args()
    run(args.source_dir, args.output, args.background_sigma_h)

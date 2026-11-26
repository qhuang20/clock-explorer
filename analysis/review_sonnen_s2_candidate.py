# SPDX-License-Identifier: MIT
"""Review a Sonnen S2 origin-sensitivity control without replacing the primary.

The gradient-normal diagnostic is deliberately not a validated wavefront-center
detector. Temporal background subtraction and spatial smoothing are used only
to inspect geometry; all kymograph values are sampled from unfiltered native
decoded green display pixels. Large sector dependence defers center adoption.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import zipfile

import av
import numpy as np
from scipy import ndimage as ndi

from audit_sonnen_movie_s2 import END, MOVIE_SHA, SOURCE_URL, START, UM_PER_PX, WIDTH
from export_video_rois import bands_from_path
from paths import ASSET_ROOT, REPO_ROOT


KEYFRAMES = [0, 20, 40, 60, 89, 110, 132, 154]
FIT_FRAMES = np.arange(10, 145, 5)
REDUCTION = 3
ORANGE = "#ee9b36"
CYAN = "#61c4da"
VIOLET = "#7163d5"
INK = "#252936"
MUTED = "#596375"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def fit_normal_center(points_xy, gradients_xy, weights=None):
    """Weighted intersection of image-gradient normal lines, not anatomy.

    For radial intensity, each gradient line passes through the geometric
    center. Arbitrary tissue or segment edges need not satisfy that model.
    Return the algebraic line-fit residual and angular misalignment separately.
    """
    points = np.asarray(points_xy, float)
    gradients = np.asarray(gradients_xy, float)
    if (
        points.shape != gradients.shape
        or points.ndim != 2
        or points.shape[1] != 2
        or len(points) < 3
        or not np.isfinite(points).all()
        or not np.isfinite(gradients).all()
    ):
        raise ValueError("Paired finite xy points/gradients required")
    magnitude = np.linalg.norm(gradients, axis=1)
    if np.any(magnitude <= 0):
        raise ValueError("Nonzero gradients required")
    w = magnitude if weights is None else np.asarray(weights, float)
    if w.shape != (len(points),) or np.any(w <= 0) or not np.isfinite(w).all():
        raise ValueError("Finite positive weights required")
    normals = np.c_[-gradients[:, 1], gradients[:, 0]] / magnitude[:, None]
    root_w = np.sqrt(w / w.max())
    design = normals * root_w[:, None]
    target = np.sum(normals * points, axis=1) * root_w
    center, _, rank, singular = np.linalg.lstsq(design, target, rcond=None)
    if rank != 2:
        raise ValueError("Gradient lines do not constrain a two-dimensional center")
    residual = np.sum(normals * (points - center), axis=1)
    distance = np.linalg.norm(points - center, axis=1)
    angle = np.degrees(
        np.arcsin(np.clip(np.abs(residual) / np.maximum(distance, 1e-9), 0, 1))
    )
    return center, {
        "weighted_line_rms_px": float(np.sqrt(np.average(residual**2, weights=w))),
        "median_normal_misalignment_deg": float(np.median(angle)),
        "design_condition_number": float(singular[0] / singular[-1]),
        "points": len(points),
    }


def geometry_region(shape, sector="whole", outer_radius=420):
    """Predeclared image window around the old ROI start; not a tissue mask."""
    y, x = np.indices(shape)
    points = np.stack([x * REDUCTION, y * REDUCTION], axis=-1).astype(float)
    dx, dy = points[..., 0] - START[0], points[..., 1] - START[1]
    radius, angle = np.hypot(dx, dy), np.arctan2(dy, dx)
    mask = (
        (radius > 90)
        & (radius < outer_radius)
        & (points[..., 0] > 50)
        & (points[..., 0] < 900)
        & (points[..., 1] > 80)
        & (points[..., 1] < 850)
    )
    if sector == "upper":
        mask &= (angle < -0.25) & (angle > -3.0)
    elif sector == "lower":
        mask &= (angle > 0.25) & (angle < 3.0)
    elif sector != "whole":
        raise ValueError("Unknown angular sector")
    return points, mask


def geometry_stack(frames, shifts):
    """Reduced, translation-stabilized display data for geometry only."""
    return np.array(
        [
            ndi.shift(
                f[::REDUCTION, ::REDUCTION, 1].astype(np.float32),
                (-shift[1] / REDUCTION, -shift[0] / REDUCTION),
                order=1,
                mode="constant",
                cval=0,
            )
            for f, shift in zip(frames, shifts)
        ]
    )


def analyze_geometry(stack, times):
    variants = [
        ("default", 3, 5, "whole", 420, 70),
        ("blur_6px", 2, 5, "whole", 420, 70),
        ("blur_12px", 4, 5, "whole", 420, 70),
        ("time_sigma_3f", 3, 3, "whole", 420, 70),
        ("time_sigma_8f", 3, 8, "whole", 420, 70),
        ("upper_sector", 3, 5, "upper", 420, 70),
        ("lower_sector", 3, 5, "lower", 420, 70),
        ("shorter_annulus", 3, 5, "whole", 350, 70),
        ("gradient_p60", 3, 5, "whole", 420, 60),
        ("gradient_p80", 3, 5, "whole", 420, 80),
    ]
    reports, centers_all = [], []
    smooth_cache, residual_cache = {}, {}
    for name, blur, temporal, sector, radius, percentile in variants:
        if blur not in smooth_cache:
            smooth_cache[blur] = ndi.gaussian_filter(stack, [0, blur, blur])
        pair = (blur, temporal)
        if pair not in residual_cache:
            smooth = smooth_cache[blur]
            residual_cache[pair] = smooth - ndi.gaussian_filter1d(
                smooth, temporal, axis=0
            )
        residual = residual_cache[pair]
        points, region = geometry_region(stack.shape[1:], sector, radius)
        centers, rows = [], []
        for frame in FIT_FRAMES:
            gy, gx = np.gradient(residual[frame])
            amplitude = np.hypot(gx, gy)
            selected = region & (
                amplitude > np.percentile(amplitude[region], percentile)
            )
            gradient = np.c_[gx[selected], gy[selected]]
            center, metrics = fit_normal_center(points[selected], gradient)
            centers.append(center)
            rows.append(
                {
                    "frame": int(frame),
                    "time_h": float(times[frame]),
                    "center_reference_xy": center.tolist(),
                    **metrics,
                }
            )
        centers = np.array(centers)
        groups = [
            FIT_FRAMES < 55,
            (FIT_FRAMES >= 55) & (FIT_FRAMES < 100),
            FIT_FRAMES >= 100,
        ]
        reports.append(
            {
                "id": name,
                "sigma_source_px": blur * REDUCTION,
                "temporal_sigma_frames": temporal,
                "sector": sector,
                "annulus_reference_center_xy": START.tolist(),
                "inner_radius_source_px": 90,
                "outer_radius_source_px": radius,
                "gradient_percentile": percentile,
                "median_reference_xy": np.median(centers, axis=0).tolist(),
                "temporal_p10_p90_reference_xy": np.percentile(
                    centers, [10, 90], axis=0
                ).tolist(),
                "disjoint_time_group_medians_reference_xy": [
                    np.median(centers[group], axis=0).tolist() for group in groups
                ],
                "per_frame": rows,
            }
        )
        centers_all.append(centers)
    return reports, np.array(centers_all), residual_cache[(3, 5)]


def strip_geometry(origin, shifts, position_px):
    origin, shifts, positions = (
        np.asarray(origin, float),
        np.asarray(shifts, float),
        np.asarray(position_px, float),
    )
    if (
        origin.shape != (2,)
        or shifts.ndim != 2
        or shifts.shape[1] != 2
        or positions.ndim != 1
        or not np.isfinite(np.r_[origin, shifts.ravel(), positions]).all()
        or np.any(positions < 0)
        or np.any(np.diff(positions) <= 0)
    ):
        raise ValueError("Finite origin, shifts and increasing distances required")
    direction = (END - START) / np.linalg.norm(END - START)
    normal = np.array([-direction[1], direction[0]])
    origins = origin + shifts
    paths = origins[:, None, :] + positions[None, :, None] * direction
    normals = np.broadcast_to(normal, paths.shape).copy()
    return paths, normals, origins, np.tile(direction, (len(shifts), 1))


def sample_green_strip(frame, path, normals, offsets, minimum_count):
    """Bilinear native green display samples, with explicit FOV-only coverage."""
    path, normals, offsets = (
        np.asarray(path, float),
        np.asarray(normals, float),
        np.asarray(offsets, float),
    )
    if (
        path.shape != normals.shape
        or path.ndim != 2
        or path.shape[1] != 2
        or offsets.ndim != 1
        or not np.isfinite(np.r_[path.ravel(), normals.ravel(), offsets]).all()
        or not np.allclose(np.linalg.norm(normals, axis=1), 1)
        or not 1 <= minimum_count <= len(offsets)
    ):
        raise ValueError("Finite paths, unit normals and valid offset count required")
    xy = path[:, None, :] + offsets[None, :, None] * normals[:, None, :]
    x, y = xy[..., 0], xy[..., 1]
    height, width = frame.shape[:2]
    valid = (x >= 0) & (x < width - 1) & (y >= 0) & (y < height - 1)
    x0, y0 = (
        np.clip(np.floor(x).astype(int), 0, width - 2),
        np.clip(np.floor(y).astype(int), 0, height - 2),
    )
    u, v = x - x0, y - y0
    g = frame[..., 1].astype(float)
    values = (
        (1 - u) * (1 - v) * g[y0, x0]
        + u * (1 - v) * g[y0, x0 + 1]
        + (1 - u) * v * g[y0 + 1, x0]
        + u * v * g[y0 + 1, x0 + 1]
    )
    counts = valid.sum(axis=1)
    retained = counts >= minimum_count
    mean = np.divide(
        np.where(valid, values, 0).sum(axis=1),
        counts,
        out=np.full(len(path), np.nan),
        where=retained,
    )
    return mean, counts, retained, valid


def init_plot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": MUTED,
            "axes.edgecolor": "#a2a8b3",
            "xtick.color": MUTED,
            "ytick.color": MUTED,
        }
    )
    return plt


def save_versions(fig, figures, stem):
    for ext in ["svg", "png", "pdf"]:
        fig.savefig(figures / f"{stem}.{ext}", dpi=180)


def draw_roi(ax, image, old_path, candidate_path, normal, frame, time, title=True):
    ax.imshow(image)
    half = WIDTH / 2 * normal
    for path, color, line in [(old_path, CYAN, "--"), (candidate_path, ORANGE, "-")]:
        polygon = np.array(
            [
                path[0] - half,
                path[-1] - half,
                path[-1] + half,
                path[0] + half,
                path[0] - half,
            ]
        )
        ax.plot(polygon[:, 0], polygon[:, 1], color=color, lw=0.9, ls=line)
        ax.annotate(
            "",
            xy=path[-1],
            xytext=path[0],
            arrowprops={
                "arrowstyle": "->",
                "color": color,
                "lw": 1.3,
                "linestyle": line,
            },
        )
        ax.plot(*path[0], "o", ms=4, mfc="none", mec=color, mew=1.0)
    ax.set_xlim(0, image.shape[1])
    ax.set_ylim(image.shape[0], 0)
    ax.axis("off")
    if title:
        ax.set_title(f"Frame {frame} · {time:.2f} h", fontsize=10, color=INK, pad=5)


def render_rois(frames, times, old_paths, paths, normals, figures):
    plt = init_plot()
    fig, axes = plt.subplots(2, 4, figsize=(15.2, 8.5))
    for ax, i in zip(axes.flat, KEYFRAMES):
        draw_roi(ax, frames[i], old_paths[i], paths[i], normals[i, 0], i, times[i])
    fig.suptitle(
        "Sonnen 2018 · Movie S2 · ROI origin-sensitivity review",
        fontsize=15,
        fontweight="bold",
        color=INK,
        y=0.98,
    )
    fig.text(
        0.04,
        0.075,
        "Cyan dashed: retained exploratory strip. Orange: origin-sensitivity control. Both average a 40 px-wide strip.",
        fontsize=10,
        color=MUTED,
    )
    fig.text(
        0.04,
        0.038,
        "Same ray, extent and retained translation; no tissue mask. The control does not validate a center or solve late peripheral coverage.",
        fontsize=9,
        color=MUTED,
    )
    fig.subplots_adjust(
        left=0.02, right=0.99, bottom=0.12, top=0.91, hspace=0.12, wspace=0.06
    )
    fig.savefig(figures / "roi-comparison.jpg", dpi=180)
    fig.savefig(figures / "roi-comparison.pdf")
    plt.close(fig)
    with zipfile.ZipFile(
        figures / "all-frame-roi-contacts.zip", "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for first in range(0, len(frames), 36):
            fig, axes = plt.subplots(6, 6, figsize=(16, 16.6))
            for ax in axes.flat:
                ax.axis("off")
            for ax, i in zip(axes.flat, range(first, min(first + 36, len(frames)))):
                draw_roi(
                    ax, frames[i], old_paths[i], paths[i], normals[i, 0], i, times[i]
                )
            fig.suptitle(
                f"Movie S2 · frames {first}–{min(first + 35, len(frames) - 1)} · cyan baseline / orange control",
                fontsize=14,
                y=0.995,
            )
            fig.subplots_adjust(
                left=0.015,
                right=0.985,
                bottom=0.015,
                top=0.965,
                hspace=0.15,
                wspace=0.04,
            )
            target = (
                figures
                / f"contacts-{first:03d}-{min(first + 35, len(frames) - 1):03d}.jpg"
            )
            fig.savefig(target, dpi=115)
            archive.write(target, target.name)
            plt.close(fig)


def render_kymographs(baseline, candidate, times, positions, figures):
    plt = init_plot()
    limits = [
        float(min(baseline.min(), np.nanmin(candidate))),
        float(max(baseline.max(), np.nanmax(candidate))),
    ]
    cmap = plt.get_cmap("OrRd").copy()
    cmap.set_bad("#e8ecf1")
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 5.5), sharey=True)
    for ax, matrix, title in zip(
        axes,
        [baseline, candidate],
        ["Retained exploratory strip", "Origin-sensitivity control"],
    ):
        mesh = ax.pcolormesh(
            times,
            positions,
            np.ma.masked_invalid((matrix - limits[0]) / (limits[1] - limits[0])),
            cmap=cmap,
            vmin=0,
            vmax=1,
            shading="nearest",
            rasterized=True,
        )
        ax.set_xlim(times[0], times[-1])
        ax.set_ylim(positions[0], positions[-1])
        ax.set_xlabel("Time (h)")
        ax.set_title(title, loc="left", fontsize=12, pad=12, color=INK)
    axes[0].set_ylabel("Distance from each ROI origin (approx. µm)")
    axes[0].text(
        -0.15, 1.01, "A", transform=axes[0].transAxes, color=VIOLET, fontweight="bold"
    )
    axes[0].text(
        -0.15, -0.01, "P", transform=axes[0].transAxes, color=VIOLET, fontweight="bold"
    )
    fig.subplots_adjust(left=0.09, right=0.865, bottom=0.24, top=0.83, wspace=0.13)
    bar = fig.add_axes([0.895, 0.24, 0.014, 0.59])
    fig.colorbar(
        mesh, cax=bar, label="Shared relative display intensity", ticks=[0, 0.5, 1]
    )
    fig.suptitle(
        "Sonnen 2018 · Movie S2 · raw display-intensity comparison",
        x=0.09,
        ha="left",
        y=0.97,
        fontsize=15,
        fontweight="bold",
        color=INK,
    )
    fig.text(
        0.09,
        0.13,
        "All 155 frames · 0–25.69 h · same 40 px width, ray, extent and retained motion · no intensity smoothing",
        fontsize=9,
        color=MUTED,
    )
    fig.text(
        0.09,
        0.065,
        "Only the sampling origin changes. Distance zero is different in each panel; A/P indicates regional direction.\nThe control is not a validated center, author ROI or improved reconstruction; adoption is deferred.",
        fontsize=9,
        color=MUTED,
        linespacing=1.6,
    )
    save_versions(fig, figures, "kymograph-comparison")
    plt.close(fig)
    return limits


def render_sensitivity(reports, centers, stack, residual, times, figures):
    plt = init_plot()
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.8))
    sectors = {
        "default": (ORANGE, "Whole field"),
        "upper_sector": ("#d1794a", "Upper sector"),
        "lower_sector": ("#9d4c75", "Lower sector"),
    }
    controls = np.array(
        [r["median_reference_xy"] for r in reports if r["id"] not in sectors]
    )
    axes[0].scatter(
        *controls.T, color="#9ba4b3", s=22, label="Nearby filter/window controls"
    )
    for i, report in enumerate(reports):
        med = np.array(report["median_reference_xy"])
        if report["id"] in sectors:
            color, label = sectors[report["id"]]
            axes[0].scatter(*med, color=color, s=34, zorder=3)
            axes[0].annotate(label, med + [8, -1], fontsize=8, color=color)
            axes[1].plot(
                times[FIT_FRAMES],
                centers[i, :, 1],
                color=color,
                lw=1.3,
                marker=".",
                label=label,
            )
    axes[0].plot(*START, "+", color=CYAN, ms=12, mew=2, label="Retained origin")
    axes[0].invert_yaxis()
    axes[0].set_aspect("equal", adjustable="datalim")
    axes[0].set_xlabel("Reference-frame x (source px)")
    axes[0].set_ylabel("Reference-frame y (source px)")
    axes[0].set_title(
        "Diagnostic medians depend on angular sector", loc="left", fontsize=11
    )
    axes[0].legend(loc="upper left", fontsize=8)
    axes[1].set_xlabel("Movie overlay time (h)")
    axes[1].set_ylabel("Diagnostic center y (source px)")
    axes[1].set_title("Time-separated estimates disagree", loc="left", fontsize=11)
    axes[1].legend(fontsize=8, frameon=False)
    fig.suptitle(
        "S2 center identifiability · geometry diagnostic only",
        fontsize=15,
        fontweight="bold",
        color=INK,
        y=0.98,
    )
    fig.text(
        0.07,
        0.09,
        "Spatial Gaussian and frame-index temporal residuals are used only here; raw intensity is sampled for the kymographs.\nSector-dependent centers and moving boundary/segment edges prevent validating a unique wavefront origin.",
        fontsize=9,
        color=MUTED,
        linespacing=1.6,
    )
    fig.subplots_adjust(left=0.08, right=0.97, bottom=0.23, top=0.85, wspace=0.35)
    save_versions(fig, figures, "center-sensitivity")
    plt.close(fig)

    fig, axes = plt.subplots(2, 6, figsize=(16, 6.8))
    for col, i in enumerate([10, 25, 40, 65, 89, 130]):
        axes[0, col].imshow(stack[i], cmap="gray", vmin=0, vmax=210)
        axes[1, col].imshow(residual[i], cmap="coolwarm", vmin=-18, vmax=18)
        for row in [0, 1]:
            axes[row, col].plot(
                START[0] / REDUCTION, START[1] / REDUCTION, "+", color=CYAN, ms=7
            )
            axes[row, col].axis("off")
        axes[0, col].set_title(f"Frame {i} · {times[i]:.2f} h", fontsize=9)
    fig.suptitle(
        "S2 raw stabilized views and geometry-only residuals",
        fontsize=14,
        fontweight="bold",
        color=INK,
        y=0.99,
    )
    fig.text(
        0.025,
        0.075,
        "Top: reduced display images in retained translation coordinates. Bottom: Gaussian 9 source px minus a 5-frame-sigma temporal baseline.\nResiduals contain tissue-boundary and persistent-segment changes; they do not isolate repeated interior wavefronts. Cyan + is the retained origin.",
        fontsize=9,
        color=MUTED,
        linespacing=1.6,
    )
    fig.subplots_adjust(
        left=0.01, right=0.99, top=0.9, bottom=0.16, hspace=0.06, wspace=0.04
    )
    fig.savefig(figures / "geometry-diagnostics.jpg", dpi=180)
    plt.close(fig)


def export_overlay(paths, normals, validity, source_clock, candidate_path, times, data):
    frames = []
    for i, (path, normal, valid) in enumerate(zip(paths, normals, validity.T)):
        bands, lines = bands_from_path(path, normal, valid, WIDTH)
        frames.append(
            {
                "index": i,
                "experiment_h": float(times[i]),
                "bands": bands,
                "lines": lines,
            }
        )
    document = {
        "schema_version": 1,
        "dataset_id": "sonnen-2018",
        "video_id": "movie-s2",
        "source_sha256": MOVIE_SHA,
        "playback_sha256": MOVIE_SHA,
        "width": 990,
        "height": 984,
        "frame_starts_s": source_clock,
        "direction_labels": ["C*", "outward"],
        "geometry_input": str(candidate_path.relative_to(data.parents[3])),
        "geometry_input_sha256": digest(candidate_path),
        "drawing": "Native source xy; 0.01 px rounded outline of 40 px strip. No display y reversal.",
        "scope": "Review-only origin-sensitivity control, not active primary geometry. C* is a diagnostic estimate, not a validated center. FOV-only validity; no tissue segmentation.",
        "frames": frames,
    }
    dump(data / "video-roi.json", document)


def protected_assets(asset_root):
    manifest = json.loads((REPO_ROOT / "catalog/assets.json").read_text())["files"]
    return {
        row["path"]: digest(asset_root / row["path"])
        for row in manifest
        if row.get("paper") == "sonnen-2018"
        and (asset_root / row["path"]).is_file()
        and "/s2-candidate-review/" not in row["path"]
    }


def run(movie, asset_root, output, cache):
    output.mkdir(parents=True, exist_ok=True)
    data = asset_root / "data/derived/sonnen-2018/s2-candidate-review"
    figures = asset_root / "figures/sonnen-2018/s2-candidate-review"
    data.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    before = protected_assets(asset_root)
    if digest(movie) != MOVIE_SHA:
        raise ValueError("Movie S2 source does not match baseline")
    baseline_path = asset_root / "data/derived/sonnen-2018/movie-s2-kymograph.npz"
    baseline_sha = digest(baseline_path)
    with np.load(baseline_path, allow_pickle=False) as z:
        baseline = {key: z[key].copy() for key in z.files}
    if not cache.is_file():
        with av.open(str(movie)) as container:
            frames = np.array(
                [f.to_ndarray(format="rgb24") for f in container.decode(video=0)]
            )
    else:
        frames = np.load(cache, mmap_mode="r", allow_pickle=False)
    if frames.shape != (155, 984, 990, 3):
        raise ValueError("Unexpected cached source frames")
    clock, decoded = [], 0
    with av.open(str(movie)) as container:
        for i, frame in enumerate(container.decode(video=0)):
            np.testing.assert_array_equal(frame.to_ndarray(format="rgb24"), frames[i])
            clock.append(float(frame.pts * frame.time_base))
            decoded += 1
    if decoded != 155:
        raise ValueError("Unexpected source frame count")
    clock = [round(t - clock[0], 9) for t in clock]
    shifts, times, positions = (
        baseline["shifts_xy"],
        baseline["time_h"],
        baseline["position_um"],
    )
    np.testing.assert_array_equal(
        times,
        np.genfromtxt(
            asset_root / "data/derived/sonnen-2018/burned-frame-times.csv",
            delimiter=",",
            names=True,
        )["time_hours"],
    )
    stack = geometry_stack(frames, shifts)
    reports, fit_centers, residual = analyze_geometry(stack, times)
    origin = np.array(reports[0]["median_reference_xy"])
    position_px = positions / UM_PER_PX
    paths, normals, origins, directions = strip_geometry(origin, shifts, position_px)
    old_paths, old_normals, _, _ = strip_geometry(START, shifts, position_px)
    offsets = np.arange(-WIDTH / 2, WIDTH / 2 + 1)
    minimum_count = int(np.ceil(len(offsets) * 0.8))
    matrix, counts, retained, sample_valid = [], [], [], []
    maximum_baseline_error = 0.0
    for i, frame in enumerate(frames):
        old_profile, _, _, _ = sample_green_strip(
            frame, old_paths[i], old_normals[i], offsets, minimum_count
        )
        maximum_baseline_error = max(
            maximum_baseline_error,
            float(np.max(np.abs(old_profile - baseline["intensity"][:, i]))),
        )
        np.testing.assert_allclose(
            old_profile, baseline["intensity"][:, i], atol=1e-10, rtol=0
        )
        values, n, valid, width_valid = sample_green_strip(
            frame, paths[i], normals[i], offsets, minimum_count
        )
        matrix.append(values)
        counts.append(n)
        retained.append(valid)
        sample_valid.append(width_valid)
    matrix, counts, retained = (
        np.array(matrix).T,
        np.array(counts).T,
        np.array(retained).T,
    )
    candidate_path = data / "candidate-kymograph.npz"
    np.savez_compressed(
        candidate_path,
        intensity=matrix,
        time_h=times,
        position_um=positions,
        position_px=position_px,
        path_xy=paths,
        normals_xy=normals,
        origins_xy=origins,
        directions_xy=directions,
        reference_origin_xy=origin,
        baseline_reference_origin_xy=START,
        shifts_xy=shifts,
        width_offsets_px=offsets,
        minimum_valid_count=minimum_count,
        valid_width_counts=counts,
        measurement_valid_mask=retained,
        sample_fov_valid_mask=np.array(sample_valid),
        source_sha256=MOVIE_SHA,
        source_frame_index=np.arange(len(frames)),
        source_frame_starts_s=clock,
        fit_frame_index=FIT_FRAMES,
        fit_centers_reference_xy=fit_centers[0],
        um_per_source_pixel=UM_PER_PX,
    )
    np.savez_compressed(
        data / "center-sensitivity.npz",
        centers_reference_xy=fit_centers,
        frame_index=FIT_FRAMES,
        time_h=times[FIT_FRAMES],
        run_ids=np.array([r["id"] for r in reports]),
    )
    limits = render_kymographs(baseline["intensity"], matrix, times, positions, figures)
    np.savez_compressed(
        data / "comparison.npz",
        baseline_intensity=baseline["intensity"],
        candidate_intensity=matrix,
        time_h=times,
        position_um=positions,
        shared_display_limits=limits,
        baseline_reference_origin_xy=START,
        candidate_reference_origin_xy=origin,
    )
    export_overlay(paths, normals, retained, clock, candidate_path, times, data)
    trajectory = [
        {
            "frame": i,
            "time_h": float(times[i]),
            "baseline_origin_xy": (START + shifts[i]).tolist(),
            "candidate_origin_xy": origins[i].tolist(),
            "candidate_endpoint_xy": paths[i, -1].tolist(),
            "fov_valid_width_min": int(counts[:, i].min()),
            "retained_positions": int(retained[:, i].sum()),
        }
        for i in range(len(times))
    ]
    dump(data / "trajectory.json", trajectory)
    with (data / "frame-geometry.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "frame",
                "time_h",
                "origin_x_px",
                "origin_y_px",
                "end_x_px",
                "end_y_px",
                "retained_positions",
            ]
        )
        for row in trajectory:
            writer.writerow(
                [
                    row["frame"],
                    row["time_h"],
                    *row["candidate_origin_xy"],
                    *row["candidate_endpoint_xy"],
                    row["retained_positions"],
                ]
            )
    medians = {r["id"]: np.array(r["median_reference_xy"]) for r in reports}
    report = {
        "paper_id": "sonnen-2018",
        "dataset_id": "sonnen-2018",
        "source_movie": "Movie S2",
        "status": "origin-sensitivity control; center adoption deferred",
        "source": {
            "url": SOURCE_URL,
            "sha256": MOVIE_SHA,
            "frames": decoded,
            "shape_yx": [984, 990],
            "cache_all_frames_match_decode": True,
            "channel": "Unfiltered native decoded green display values; compressed grayscale fluorescence export, not raw camera data.",
        },
        "source_evidence": {
            "article_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC5847172/",
            "cached_primary": "work/mammal-sources/PMC5847172.xml",
            "sample_match": "Movie S2 caption links this specimen to Fig.1D–F. Existing independent Fig1D registration matches source frame89 at14.85h.",
            "author_method_scope": "Fig.1G 70µm/50px dual-reporter ROI is a different recording. No exact S2 author kymograph ROI is supplied.",
            "view": "Culture-plane imaging; ex vivo mPSM",
            "AP_scope": "Supported regional inner-posteriorward to outer-anteriorward direction; exact center, tissue boundaries and cell identities remain unregistered.",
        },
        "geometry_diagnostic": {
            "method": "Weighted intersections of spatial intensity-gradient lines in a frame-index temporal residual. Not an identified interior-wavefront detector.",
            "purpose": "Origin sensitivity only; no validation of oscillation center or biological pacemaker.",
            "translation": "Inherited original fluorescence-derived cumulative translation; no new independent structural registration.",
            "reference_coordinates": "Source frame0 pixel coordinates after subtracting retained per-frame shifts.",
            "downsample": REDUCTION,
            "diagnostic_window_xyxy": [50, 80, 900, 850],
            "fit_frames": FIT_FRAMES.tolist(),
            "fit_time_h": times[FIT_FRAMES].tolist(),
            "default_origin_xy": origin.tolist(),
            "baseline_origin_xy": START.tolist(),
            "origin_offset_px": (origin - START).tolist(),
            "origin_offset_norm_px": float(np.linalg.norm(origin - START)),
            "upper_sector_shift_from_default_px": float(
                np.linalg.norm(medians["upper_sector"] - origin)
            ),
            "lower_sector_shift_from_default_px": float(
                np.linalg.norm(medians["lower_sector"] - origin)
            ),
            "interpretation": "Default and nearby blur controls can agree while angular-sector/time-window fits disagree substantially. Residuals include moving tissue boundaries and stable segment stripes; a unique wavefront center is not identifiable by this diagnostic.",
            "variation_ranges_are_confidence_intervals": False,
            "runs": reports,
        },
        "measurement": {
            "shape_space_time": list(matrix.shape),
            "time_range_h": [float(times[0]), float(times[-1])],
            "timestamps": "All155 original burned labels retained, precision0.01h; movie zero is not verified culture zero.",
            "coordinate": "Distance from each distinct ROI origin, same extent as retained strip; origins do not identify the same cells.",
            "position_um_approx": [float(positions[0]), float(positions[-1])],
            "scale_um_per_px_approx": UM_PER_PX,
            "scale_basis": "100µm over139 decoded horizontal pixels; isotropic approximation; not the raw1.38µm/pixel protocol.",
            "direction_xy": directions[0].tolist(),
            "width_px": WIDTH,
            "width_samples": len(offsets),
            "width_offsets_px": offsets.tolist(),
            "minimum_valid_count": minimum_count,
            "interpolation": "Bilinear native green display values; transverse arithmetic mean.",
            "signal_smoothing": "None. Spatial/temporal filters occur only in origin diagnostic, not primary sampling.",
            "validity": "FOV only. No anatomical or intensity-derived tissue mask. True dark pixels and measured zero remain values.",
            "valid_width_count_min_max": [int(counts.min()), int(counts.max())],
            "missing_values": int(np.isnan(matrix).sum()),
            "mean_absolute_difference_from_baseline_display_units": float(
                np.nanmean(np.abs(matrix - baseline["intensity"]))
            ),
            "baseline_recomputed_max_absolute_error": maximum_baseline_error,
            "shared_display_limits": limits,
        },
        "limitations": [
            "Candidate is an origin-sensitivity control, not a validated wavefront center or better primary.",
            "Diagnostic gradients include growing envelope and persistent segment boundaries; sector dependence is substantial.",
            "The same approximate scale and fluorescence-derived translation are inherited; motion/tissue identity are not independently validated.",
            "An endpoint within the FOV is not necessarily the anatomical rim; it becomes interior as tissue spreads.",
            "Compressed display intensities are not raw fluorescence; no cross-sample absolute expression comparison.",
        ],
        "script": {
            "path": "analysis/review_sonnen_s2_candidate.py",
            "sha256": digest(__file__),
        },
        "baseline_matrix": {
            "path": str(baseline_path.relative_to(asset_root)),
            "sha256": baseline_sha,
        },
        "protected_asset_sha256_before": before,
    }
    dump(data / "review-provenance.json", report)
    dump(output / "review.json", report)
    render_rois(frames, times, old_paths, paths, normals, figures)
    render_sensitivity(reports, fit_centers, stack, residual, times, figures)
    after = {path: digest(asset_root / path) for path in before}
    if before != after or digest(baseline_path) != baseline_sha:
        raise ValueError("A protected pre-existing asset changed")
    preservation = {
        "baseline_matrix_sha256": baseline_sha,
        "protected_assets": len(before),
        "all_unchanged": True,
        "sha256_before": before,
        "sha256_after": after,
    }
    dump(output / "preservation.json", preservation)
    manifest = [
        {
            "path": str(p.relative_to(asset_root)),
            "bytes": p.stat().st_size,
            "sha256": digest(p),
            "paper": "sonnen-2018",
            "source_url": SOURCE_URL,
            "rights": "Third-party research derivation; CC BY-NC-ND4.0 source; local review only.",
        }
        for folder in [data, figures]
        for p in sorted(folder.iterdir())
        if p.is_file()
    ]
    dump(output / "asset-manifest.json", manifest)
    handoff = {
        "paper_id": "sonnen-2018",
        "dataset_id": "sonnen-2018",
        "movie": "Movie S2",
        "status": report["status"],
        "primary_replacement_recommended": False,
        "candidate_origin_reference_xy": origin.tolist(),
        "origin_offset_from_old_px": float(np.linalg.norm(origin - START)),
        "candidate_matrix": str(candidate_path.relative_to(asset_root)),
        "provenance": str((data / "review-provenance.json").relative_to(asset_root)),
        "roi": str((figures / "roi-comparison.jpg").relative_to(asset_root)),
        "comparison": str(
            (figures / "kymograph-comparison.svg").relative_to(asset_root)
        ),
        "diagnostic": str((figures / "center-sensitivity.svg").relative_to(asset_root)),
        "geometry_diagnostic": str(
            (figures / "geometry-diagnostics.jpg").relative_to(asset_root)
        ),
        "all_frames_contacts": str(
            (figures / "all-frame-roi-contacts.zip").relative_to(asset_root)
        ),
        "overlay": str((data / "video-roi.json").relative_to(asset_root)),
        "display": {
            "zero_at": "bottom",
            "data_axes": ["axes_1", "axes_2"],
            "colorbar_axes": ["axes_3"],
            "flip_y": False,
            "axis_polarity": {
                "top": "A",
                "bottom": "P",
                "scope": "regional direction only; candidate origin not center-validated",
            },
        },
        "ui": {
            "label": "Origin-sensitivity review",
            "note": "The retained strip is compared with a nearby diagnostic origin. Direction, width, spatial extent, original times and retained translations are held fixed. All values are unfiltered display intensities, shown with one color scale. Sector-dependent estimates prevent validating a unique wavefront center; the current primary remains unchanged. This control does not solve late peripheral coverage.",
            "steps": [
                "Inspect multiple times using geometry-only spatial/temporal filtering and gradient-line diagnostics.",
                "Keep the diagnostic median origin as an explicitly unvalidated sensitivity control; compare angular sectors, time groups and nearby filter settings.",
                "Sample 155 native source frames with the same 40 px width, outward ray, distance extent and retained translation as the current strip.",
                "Display both raw matrices with common intensity limits and preserve the original primary byte-for-byte.",
            ],
            "limits": report["limitations"],
        },
        "preservation": preservation,
        "manifest": str(output / "asset-manifest.json"),
        "tests": "tests/test_sonnen_s2_candidate.py; pending independent review",
        "figure_table_trace": [
            {
                "artifact_id": "sonnen-s2-origin-control",
                "source_data": {
                    "dataset_id": "sonnen-2018",
                    "file": str((data / "comparison.npz").relative_to(asset_root)),
                },
                "transformation": {
                    "script": "analysis/review_sonnen_s2_candidate.py",
                    "sha256": digest(__file__),
                },
                "caption_claim": "Controlled display-intensity comparison of distinct ROI origins; center adoption deferred.",
                "limitations": report["limitations"],
            }
        ],
    }
    dump(output / "handoff.json", handoff)
    return handoff


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--movie",
        type=Path,
        default=REPO_ROOT / "work/additional-data/mammal/sonnen-mmc3.mp4",
    )
    parser.add_argument("--asset-root", type=Path, default=ASSET_ROOT)
    parser.add_argument(
        "--cache",
        type=Path,
        default=REPO_ROOT / "work/radial-ap-review/sonnen-s2-frames.npy",
    )
    parser.add_argument(
        "--output", type=Path, default=REPO_ROOT / "outputs/sonnen-s2-candidate"
    )
    args = parser.parse_args()
    result = run(args.movie, args.asset_root, args.output, args.cache)
    print(
        json.dumps(
            {
                key: result[key]
                for key in [
                    "status",
                    "candidate_origin_reference_xy",
                    "origin_offset_from_old_px",
                    "candidate_matrix",
                    "roi",
                    "comparison",
                ]
            }
        )
    )


if __name__ == "__main__":
    main()

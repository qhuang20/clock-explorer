# SPDX-License-Identifier: MIT
"""Fit a dark-core-guided Video 5 wavefront center and preserve the COM reference.

The candidate screens observed contour centers; it does not constrain the shared
fit to the clicked location. Geometry filtering never changes primary samples.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from paths import ASSET_ROOT
from extract_video_kymographs import decode
from extract_lauschke_radial import MOVIE_SHA, UM_PER_PX, sample_radial
from lauschke_wavefront_center import find_fronts, fit_common_center
from audit_lauschke_video5 import overlay

CANDIDATE_XY = (369.7781558576528, 270.23314452116745)
CANDIDATE_RADIUS_PX = 65.0
FIT_TIME_H = (0.5, 9.5)
GEOMETRY_SIGMA_UM = 16.61


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def select_candidate_fronts(fronts, candidate_xy, radius_px=CANDIDATE_RADIUS_PX):
    """One observed contour per time, with no COM or nearest-dark-pixel fallback."""
    prior = np.asarray(candidate_xy, float)
    if prior.shape != (2,) or not np.isfinite(prior).all() or radius_px <= 0:
        raise ValueError("Invalid reviewed candidate region")
    by_frame = {}
    for front in fronts:
        if np.linalg.norm(np.asarray(front["center"]) - prior) > radius_px:
            continue
        if (
            front["frame"] not in by_frame
            or front["residual_px"] < by_frame[front["frame"]]["residual_px"]
        ):
            by_frame[front["frame"]] = front
    selected = sorted(by_frame.values(), key=lambda f: f["frame"])
    if len(selected) < 5 or np.ptp([f["time_h"] for f in selected]) < 2:
        raise ValueError("Candidate lacks five distinct times spanning two hours")
    center, radii = fit_common_center(selected)
    if np.linalg.norm(center - prior) > radius_px:
        raise ValueError("Unconstrained shared fit contradicts candidate region")
    return center, radii, selected


def temporal_blocks(fronts, radii):
    blocks = []
    for front, radius in zip(fronts, radii):
        if (
            not blocks
            or front["time_h"] - blocks[-1][-1][0]["time_h"] > 0.5 + 1e-8
            or radius < blocks[-1][-1][1] - 30
        ):
            blocks.append([])
        blocks[-1].append((front, float(radius)))
    return blocks


def normal_errors(center, fronts, ray_deg=45):
    rows = []
    for front in fronts:
        q = np.asarray(front["points"])
        v = q - center
        theta = np.degrees(np.arctan2(v[:, 1], v[:, 0]))
        near = abs((theta - ray_deg + 180) % 360 - 180) < 7
        if near.sum() < 3:
            continue
        tangent = np.gradient(q, axis=0)
        normal = np.c_[-tangent[:, 1], tangent[:, 0]]
        cosine = abs((normal * v).sum(axis=1)) / np.maximum(
            np.linalg.norm(normal, axis=1) * np.linalg.norm(v, axis=1), 1e-9
        )
        error = np.degrees(np.arccos(np.clip(cosine[near], 0, 1)))
        rows.append(
            {
                "frame": front["frame"],
                "median_normal_error_deg": float(np.median(error)),
            }
        )
    return rows


def edges(values):
    return np.r_[
        values[0] - (values[1] - values[0]) / 2,
        (values[:-1] + values[1:]) / 2,
        values[-1] + (values[-1] - values[-2]) / 2,
    ]


def render(
    frames,
    masks,
    old_origins,
    origins,
    old,
    new,
    times,
    positions,
    shifts,
    selected,
    center,
    radii,
    limits,
    output,
):
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
            "text.color": "#252936",
            "axes.labelcolor": "#535d6b",
            "xtick.color": "#677285",
            "ytick.color": "#677285",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axes = plt.subplots(2, 3, figsize=(11.4, 8.2))
    for row, (matrix, path, name) in enumerate(
        [
            (old, old_origins, "Area-centroid reference"),
            (new, origins, "Dark-core wavefront fit"),
        ]
    ):
        for ax, i in zip(axes[row], [0, 30, 60]):
            last = np.flatnonzero(np.isfinite(matrix[:, i]))[-1]
            overlay(ax, frames[i], masks[i], path[i], last, f"{name} · {times[i]:g} h")
            if row:
                ax.plot(*path[i], "o", mfc="none", mec="#d6b7ff", ms=11, mew=1.4)
    fig.text(
        0.02,
        0.025,
        "Same green display channel, masks, 45° direction and 20 px width; origins differ.",
        fontsize=9,
        color="#535d6b",
    )
    fig.subplots_adjust(
        left=0.01, right=0.99, bottom=0.06, top=0.95, wspace=0.045, hspace=0.12
    )
    fig.savefig(output / "video5-center-rois.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11.4, 5.2))
    cmap = matplotlib.colormaps["OrRd"].copy()
    cmap.set_bad("#f1f3f6")
    norm = Normalize(0, 1)
    low, high = limits
    for ax, array, title in zip(
        axes, [old, new], ["Area-centroid reference", "Dark-core wavefront fit"]
    ):
        mesh = ax.pcolormesh(
            edges(times),
            edges(positions),
            np.ma.masked_invalid((array - low) / (high - low)),
            cmap=cmap,
            norm=norm,
            shading="flat",
            rasterized=True,
        )
        ax.set_xlim(times[0], times[-1])
        ax.set_ylim(positions[-1], positions[0])
        ax.set_title(title, fontsize=12, loc="left", pad=12)
        ax.set_xlabel("Time (h)")
        ax.set_ylabel("Distance from own origin (µm)")
    cax = fig.add_axes([0.93, 0.22, 0.016, 0.61])
    bar = fig.colorbar(mesh, cax=cax, ticks=[0, 0.5, 1])
    bar.set_label("Relative display intensity · shared scale")
    bar.outline.set_visible(False)
    fig.text(
        0.065,
        0.085,
        "Same 61 frames, scale, 20 px width, masks and 45° ray; no additional intensity filtering.",
        color="#677285",
        fontsize=9,
    )
    fig.text(
        0.065,
        0.035,
        "Gray = missing samples. Equal distance does not identify the same cells. The original reference file is unchanged.",
        color="#677285",
        fontsize=9,
    )
    fig.subplots_adjust(left=0.065, right=0.885, top=0.87, bottom=0.22, wspace=0.28)
    for ext in ["png", "svg", "pdf"]:
        fig.savefig(output / ("video5-center-kymographs." + ext), dpi=200)
    plt.close(fig)

    fig, axes = plt.subplots(4, 4, figsize=(12.5, 13))
    for ax, front, radius in zip(axes.flat, selected, radii):
        i = front["frame"]
        ax.imshow(frames[i])
        q = np.array(front["points"]) + shifts[i]
        ax.plot(q[:, 0], q[:, 1], color="#d6b7ff", lw=1.1)
        theta = np.linspace(0, 2 * np.pi, 200)
        circle = origins[i] + radius * np.c_[np.cos(theta), np.sin(theta)]
        ax.plot(circle[:, 0], circle[:, 1], color="white", lw=0.7, ls="--", alpha=0.8)
        ax.plot(*origins[i], "+", color="white", ms=8, mew=1.2)
        ax.plot(*old_origins[i], "x", color="#ffad43", ms=6)
        ax.set_title(f"Frame {i} · {times[i]:.2f} h", fontsize=9)
        ax.set_xlim(120, 670)
        ax.set_ylim(630, 50)
        ax.axis("off")
    for ax in axes.flat[len(selected) :]:
        ax.axis("off")
    fig.text(
        0.02,
        0.027,
        "Purple: observed contrast contour   Dashed white: shared-center circle   +: fitted center   Orange x: old centroid",
        color="#535d6b",
        fontsize=9,
    )
    fig.subplots_adjust(
        left=0.01, right=0.99, bottom=0.05, top=0.96, wspace=0.04, hspace=0.1
    )
    fig.savefig(output / "video5-center-fronts.png", dpi=160)
    plt.close(fig)


def run(source_dir, output_root, candidate_xy=CANDIDATE_XY):
    data = ASSET_ROOT / "data/derived/lauschke-2013"
    reference = data / "video5-kymograph.npz"
    geometry = data / "video5-geometry.npz"
    provenance = data / "extraction-provenance.json"
    protected = {p.name: digest(p) for p in [reference, geometry, provenance]}
    movie = source_dir / "41586_2013_BFnature11804_MOESM296_ESM.mov"
    if digest(movie) != MOVIE_SHA:
        raise ValueError("Unexpected Video 5 source hash")
    frames = np.asarray(decode(movie))
    with np.load(reference) as source:
        old = source["intensity"].copy()
        old_origins = source["centers_xy"].copy()
        times = source["time_h"].copy()
        positions = source["position_um"].copy()
        old_counts = source["valid_width_counts"].copy()
    with np.load(geometry) as source:
        masks = source["tissue_masks"].copy()
        shifts = source["shifts_xy"].copy()
        np.testing.assert_array_equal(old_origins, source["centers_xy"])
    if frames.shape != (61, 742, 749, 3):
        raise ValueError("Unexpected Video 5 shape")
    rebuilt, counts = sample_radial(frames, old_origins, masks)
    np.testing.assert_allclose(rebuilt, old, rtol=0, atol=0, equal_nan=True)
    np.testing.assert_array_equal(counts, old_counts)

    def detect(sigma):
        return find_fronts(
            frames,
            masks,
            shifts,
            times,
            UM_PER_PX,
            sigma_um=sigma,
            frame_stride=1,
            fit_time_h=FIT_TIME_H,
            channel=1,
        )

    candidates = detect(GEOMETRY_SIGMA_UM)
    center, radii, selected = select_candidate_fronts(candidates, candidate_xy)
    origins = center + shifts
    matrix, valid_counts = sample_radial(frames, origins, masks)
    if not np.isfinite(matrix[0]).all():
        raise ValueError("Fitted origin lacks sampling support in at least one frame")
    if np.isinf(matrix).any():
        raise ValueError("Infinite signal values")
    halves = [
        [f for f in selected if f["time_h"] < 4.5],
        [f for f in selected if f["time_h"] >= 4.5],
    ]
    time_centers = [fit_common_center(fs, center)[0] for fs in halves]
    blocks = temporal_blocks(selected, radii)
    leave_out = []
    held_out_fitted = []
    held_out_centroid = []
    for j, block in enumerate(blocks):
        training = [f for n, b in enumerate(blocks) if n != j for f, _ in b]
        other, _ = fit_common_center(training, center)
        fitted_errors, centroid_errors = [], []
        for front, _ in block:
            points = np.asarray(front["points"])
            index = front["frame"]
            old_center = old_origins[index] - shifts[index]
            for target, origin in [
                (fitted_errors, other),
                (centroid_errors, old_center),
            ]:
                distances = np.linalg.norm(points - origin, axis=1)
                target.extend(abs(distances - np.median(distances)))
        held_out_fitted.extend(fitted_errors)
        held_out_centroid.extend(centroid_errors)
        leave_out.append(
            {
                "omitted_frames": [f["frame"] for f, _ in block],
                "center_xy_reference_px": other.tolist(),
                "offset_um": float(np.linalg.norm(other - center) * UM_PER_PX),
                "held_out_fitted_radial_mad_um": float(
                    np.median(fitted_errors) * UM_PER_PX
                ),
                "held_out_centroid_radial_mad_um": float(
                    np.median(centroid_errors) * UM_PER_PX
                ),
            }
        )
    sensitivity = []
    for sigma in [14.0, 20.0]:
        other, _, fs = select_candidate_fronts(detect(sigma), candidate_xy)
        sensitivity.append(
            {
                "sigma_um": sigma,
                "distinct_frames": len(fs),
                "center_xy_reference_px": other.tolist(),
                "offset_um": float(np.linalg.norm(other - center) * UM_PER_PX),
            }
        )
    prior_sensitivity = []
    for delta in [(-20, 0), (20, 0), (0, -20), (0, 20)]:
        prior = np.array(candidate_xy) + delta
        other, _, fs = select_candidate_fronts(candidates, prior)
        prior_sensitivity.append(
            {
                "candidate_offset_px": list(delta),
                "selected_frames": [f["frame"] for f in fs],
                "center_xy_reference_px": other.tolist(),
                "offset_um": float(np.linalg.norm(other - center) * UM_PER_PX),
            }
        )
    residuals = np.concatenate(
        [
            abs(np.linalg.norm(np.array(f["points"]) - center, axis=1) - radius)
            for f, radius in zip(selected, radii)
        ]
    )
    normal = normal_errors(center, selected)
    finite = np.r_[old[np.isfinite(old)], matrix[np.isfinite(matrix)]]
    limits = np.array([finite.min(), finite.max()])
    records = output_root / "data/derived/lauschke-2013"
    figures = output_root / "figures/lauschke-2013"
    records.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    directions = np.tile(np.array([1.0, 1.0]) / np.sqrt(2), (len(times), 1))
    alternatives = {
        f"angle_{angle}": sample_radial(frames, origins, masks, angle)[0]
        for angle in [35, 55]
    }
    np.savez_compressed(
        records / "video5-wavefront-comparison.npz",
        intensity=matrix,
        centroid_intensity=old,
        time_h=times,
        position_um=positions,
        origins_xy=origins,
        centroid_origins_xy=old_origins,
        directions_xy=directions,
        valid_width_counts=valid_counts,
        centroid_valid_width_counts=old_counts,
        shared_color_limits=limits,
        **alternatives,
    )
    np.savetxt(
        records / "video5-wavefront-origins.csv",
        np.c_[np.arange(len(times)), times, origins, old_origins, shifts],
        delimiter=",",
        comments="",
        fmt="%.9g",
        header="frame,time_h,fitted_x_px,fitted_y_px,centroid_x_px,centroid_y_px,bf_dx_px,bf_dy_px",
    )
    report = {
        "method_version": "video5-dark-core-wavefront-v1",
        "source_filename": movie.name,
        "source_sha256": MOVIE_SHA,
        "protected_reference_hashes": protected,
        "centroid_reference_reproduced_exactly": True,
        "candidate_origin": "User-reviewed dark core in source frame 0; approximate region, not an author ROI.",
        "candidate_xy_reference_px": list(candidate_xy),
        "candidate_search_radius_px": CANDIDATE_RADIUS_PX,
        "candidate_role": "Screens individual contour centers only; shared fit is unconstrained by the manual point or COM.",
        "center_xy_reference_px": center.tolist(),
        "center_status": "Supported shared geometric center of observed oscillatory-contrast contours; not a verified biological pacemaker.",
        "candidate_arc_count": len(candidates),
        "selected_distinct_frames": [f["frame"] for f in selected],
        "supported_time_range_h": [selected[0]["time_h"], selected[-1]["time_h"]],
        "fit_radii_px": radii.tolist(),
        "median_joint_radial_residual_um": float(np.median(residuals) * UM_PER_PX),
        "p90_joint_radial_residual_um": float(np.percentile(residuals, 90) * UM_PER_PX),
        "disjoint_time_centers_xy_reference_px": [c.tolist() for c in time_centers],
        "disjoint_time_center_separation_um": float(
            np.linalg.norm(time_centers[0] - time_centers[1]) * UM_PER_PX
        ),
        "time_split_h": 4.5,
        "leave_temporal_block_out": leave_out,
        "held_out_same_contour_radial_mad_um": {
            "centroid_reference": float(np.median(held_out_centroid) * UM_PER_PX),
            "wavefront_fit": float(np.median(held_out_fitted) * UM_PER_PX),
            "meaning": "Median absolute radial deviation with each held-out contour radius optimized by its median; same contour set for both origins. Temporal filtering remains correlated; this is a geometry diagnostic.",
        },
        "geometry_filter_sensitivity": sensitivity,
        "manual_candidate_sensitivity": prior_sensitivity,
        "ray_angle_deg": 45,
        "ray_choice": "Retained from centroid reference to isolate origin choice; not optimized for kymograph appearance.",
        "observed_front_normal_errors": normal,
        "median_front_normal_error_deg": float(
            np.median([r["median_normal_error_deg"] for r in normal])
        ),
        "motion": "Fitted center in BF-registered frame continued by the existing Video 4 translations; centroid baseline retains its original per-frame mask trajectory.",
        "sampling": {
            "source_channel": "Original decoded green display channel",
            "frames": 61,
            "time_range_h": times[[0, -1]].tolist(),
            "um_per_px": UM_PER_PX,
            "strip_width_px": 20,
            "transverse_samples": 21,
            "minimum_valid_samples": 16,
            "radius_grid_um": positions[[0, -1]].tolist(),
            "mask_rule": "Same saved tissue masks; stop at first row with <75% valid width; no re-entry.",
            "intensity_filtering_added": False,
            "shared_display_limits_raw": limits.tolist(),
        },
        "geometry_filters_only": {
            "spatial_sigma_um": GEOMETRY_SIGMA_UM,
            "temporal_difference_of_gaussians_sigma_h": [0.2, 1.2],
            "fit_window_h": list(FIT_TIME_H),
            "frame_stride": 1,
            "levels": "0 and ±0.4 SD of the masked dynamic contrast field",
            "detector": "Same circle-contour criteria as existing Lauschke finder; Video 5 green channel and all consecutive frames.",
        },
        "limitations": [
            "Circular level-set model is approximate; spatial residuals and filter/block differences are diagnostics, not a confidence interval.",
            "Consecutive contours share temporally filtered input and are not independent biological replicates.",
            "45° ray is only approximately normal to observed fronts; 35/55° signal controls are included.",
            "Frames outside the supported contour times use the BF-continued center; no independent source-center claim at every frame.",
            "Area centroid and shared wavefront center have distinct trajectories; same radius does not identify the same cells.",
            "No P/A fate marker, author-deposited ROI, cell tracking or tissue-deformation correction is inferred.",
            "Compressed source movie is already author-processed display data, not raw fluorescence.",
        ],
        "selected_fronts": selected,
        "all_candidate_fronts": candidates,
        "script_sha256": digest(__file__),
        "wavefront_module_sha256": digest(
            Path(__file__).with_name("lauschke_wavefront_center.py")
        ),
    }
    (records / "video5-wavefront-center.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    render(
        frames,
        masks,
        old_origins,
        origins,
        old,
        matrix,
        times,
        positions,
        shifts,
        selected,
        center,
        radii,
        limits,
        figures,
    )
    for name, expected in protected.items():
        if digest(data / name) != expected:
            raise ValueError("Protected centroid reference changed")
    print(
        json.dumps(
            {
                k: report[k]
                for k in [
                    "center_xy_reference_px",
                    "selected_distinct_frames",
                    "supported_time_range_h",
                    "median_joint_radial_residual_um",
                    "disjoint_time_center_separation_um",
                    "geometry_filter_sensitivity",
                    "median_front_normal_error_deg",
                ]
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--candidate-x", type=float, default=CANDIDATE_XY[0])
    parser.add_argument("--candidate-y", type=float, default=CANDIDATE_XY[1])
    args = parser.parse_args()
    run(args.source_dir, args.output_root, (args.candidate_x, args.candidate_y))


if __name__ == "__main__":
    main()

# SPDX-License-Identifier: MIT
"""Map the Fig. 1d illustrated line onto Video 2 and compare the current ROI.

This reconstructs a drawn sampling path, not an author-deposited ROI or biological
center. Both main panels use the same existing BF translation and video scale.
"""

from pathlib import Path
import argparse
import hashlib
import json

import numpy as np
from scipy import ndimage as ndi

from paths import ASSET_ROOT
from extract_video_kymographs import decode
from reproduce_lauschke_views import SOURCE_HASHES, WIDTH_PX, SIGMA_UM

UM_PER_PX = 100 / 111


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def transform_points(matrix, points):
    matrix = np.asarray(matrix, float)
    points = np.asarray(points, float)
    if matrix.shape != (2, 3) or points.shape[-1] != 2 or not np.isfinite(matrix).all():
        raise ValueError("Invalid image registration geometry")
    return points @ matrix[:, :2].T + matrix[:, 2]


def mapped_line(registration, shifts):
    matrix = np.asarray(registration["reference_transform_panel_to_video"])
    index = registration["reference_frame_index_0_based"]
    if not isinstance(index, int) or not 0 <= index < len(shifts):
        raise ValueError("Invalid reference frame")
    start = transform_points(matrix, registration["arrow_tail_panel_xy"])
    tip = transform_points(matrix, registration["arrow_tip_panel_xy"])
    vector = tip - start
    if np.linalg.norm(vector) < 10:
        raise ValueError("Illustrated line is degenerate")
    direction = vector / np.linalg.norm(vector)
    return (
        start + shifts - shifts[index],
        np.tile(direction, (len(shifts), 1)),
        start,
        tip,
    )


def longest_interval(valid):
    """Retain one continuous tissue segment without requiring tissue at r=0."""
    valid = np.asarray(valid, bool)
    edges = np.diff(np.r_[False, valid, False].astype(int))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    kept = np.zeros(valid.shape, bool)
    if len(starts):
        j = np.argmax(ends - starts)
        kept[starts[j] : ends[j]] = True
    return kept


def sample_line(
    frames, origins, directions, position_um, masks, um_per_px=UM_PER_PX, sigma_um=0
):
    columns = []
    counts = []
    for i, (frame, origin, direction) in enumerate(zip(frames, origins, directions)):
        normal = np.array([-direction[1], direction[0]])
        offsets = np.linspace(-WIDTH_PX / 2, WIDTH_PX / 2, WIDTH_PX + 1)
        xy = (
            origin
            + position_um[:, None, None] / um_per_px * direction
            + offsets[None, :, None] * normal
        )
        coords = [xy[..., 1], xy[..., 0]]
        gray = (
            frame[..., :3].astype(float).mean(axis=-1)
            if frame.ndim == 3
            else frame.astype(float)
        )
        if sigma_um:
            gray = ndi.gaussian_filter(gray, sigma_um / um_per_px)
        values = ndi.map_coordinates(
            gray, coords, order=1, mode="constant", cval=np.nan
        )
        valid = (
            np.isfinite(values)
            & (xy[..., 0] >= 15)
            & (xy[..., 1] >= 15)
            & (xy[..., 1] < frame.shape[0] - 60)
        )
        valid &= (
            ndi.map_coordinates(
                masks[i].astype(float), coords, order=0, mode="constant", cval=0
            )
            > 0.5
        )
        count = valid.sum(axis=1)
        inside = longest_interval(count >= np.ceil(0.75 * len(offsets)))
        profile = np.divide(
            np.where(valid, values, 0).sum(axis=1),
            count,
            out=np.full(len(count), np.nan),
            where=inside,
        )
        columns.append(profile)
        counts.append(np.where(inside, count, 0))
    return np.stack(columns, axis=1), np.stack(counts, axis=1)


def validate_registration(registration):
    first = registration["independent_thumbnail_matches"][0]
    if (
        first["frame"] != registration["reference_frame_index_0_based"]
        or first["inliers"] < 100
        or first["median_error_source_px"] > 0.5
    ):
        raise ValueError("Registration lacks reviewed feature support")
    points = np.asarray(first["panel_inliers"])
    target = np.asarray(first["video_inliers"])
    matrix = np.asarray(registration["reference_transform_panel_to_video"])
    errors = np.linalg.norm(transform_points(matrix, points) - target, axis=1)
    if np.median(errors) > 0.5 or np.percentile(errors, 95) > 2:
        raise ValueError("Saved registration is inconsistent with matched features")
    return errors


def edge(values):
    return np.r_[
        values[0] - (values[1] - values[0]) / 2,
        (values[1:] + values[:-1]) / 2,
        values[-1] + (values[-1] - values[-2]) / 2,
    ]


def render_pair(
    author, current, times, position, limits, reference_h, out, stem, filtered=False
):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "text.color": "#252936",
            "axes.labelcolor": "#535d6b",
            "xtick.color": "#677285",
            "ytick.color": "#677285",
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )
    fig, axs = plt.subplots(1, 2, figsize=(11.4, 5.5), sharex=True, sharey=True)
    cmap = matplotlib.colormaps["OrRd"].copy()
    cmap.set_bad("#f1f3f6")
    low, high = limits
    for ax, array, title in zip(
        axs,
        [author, current],
        ["Published-line reconstruction", "Current wavefront-fit reconstruction"],
    ):
        values = (array - low) / (high - low)
        mesh = ax.pcolormesh(
            edge(times),
            edge(position),
            np.ma.masked_invalid(values),
            cmap=cmap,
            vmin=0,
            vmax=1,
            shading="flat",
            rasterized=True,
        )
        ax.set_xlim(times[0], times[-1])
        ax.set_ylim(0, position[-1])
        ax.set_title(title, loc="left", fontsize=12, pad=12)
        ax.set_xlabel("Video overlay time (h)")
        ax.axvline(reference_h, color="#8b8599", lw=0.8, ls="--", alpha=0.65)
    axs[0].set_ylabel("Distance from own ROI start (µm)")
    cax = fig.add_axes([0.92, 0.24, 0.015, 0.59])
    bar = fig.colorbar(mesh, cax=cax, ticks=[0, 0.5, 1])
    bar.set_label("Relative display intensity · shared scale")
    bar.outline.set_visible(False)
    label = (
        f"Spatial Gaussian σ = {SIGMA_UM:.2f} µm"
        if filtered
        else "Unsmoothed display values"
    )
    fig.suptitle(
        "Video 2 · illustrated line versus current ROI",
        x=0.04,
        ha="left",
        fontsize=16,
        weight="bold",
        y=0.98,
    )
    fig.text(
        0.04,
        0.115,
        f"{label} · same 160 frames, 20 px width, BF translation, tissue/FOV rules and color limits",
        fontsize=9,
        color="#677285",
    )
    fig.text(
        0.04,
        0.065,
        "Gray = no tissue/FOV samples. Each vertical origin belongs to its own line; no missing values are filled.",
        fontsize=9,
        color="#677285",
    )
    fig.text(
        0.04,
        0.022,
        "Dashed time: matched Fig. 1d “0 min” panel (18.07 h video overlay). Drawing-based ROI, not exact author coordinates.",
        fontsize=9,
        color="#677285",
    )
    fig.subplots_adjust(left=0.075, right=0.88, top=0.83, bottom=0.24, wspace=0.16)
    for ext in ["png", "svg", "pdf"]:
        fig.savefig(out / (stem + "." + ext), dpi=220)
    plt.close(fig)


def render_rois(
    frames,
    author_origins,
    author_directions,
    current_origins,
    current_directions,
    positions,
    times,
    out,
    reference_index,
):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axs = plt.subplots(1, 3, figsize=(11.4, 5.2))
    colors = ["#e17a26", "#7151cf"]

    def endpoint(origin, direction, frame):
        length = positions[-1] / UM_PER_PX
        for dim, bound in [(0, frame.shape[1] - 5), (1, frame.shape[0] - 5)]:
            if direction[dim] > 0:
                length = min(length, (bound - origin[dim]) / direction[dim])
            elif direction[dim] < 0:
                length = min(length, (5 - origin[dim]) / direction[dim])
        return origin + max(0, length) * direction

    for ax, i in zip(axs, [0, reference_index, len(frames) - 1]):
        ax.imshow(frames[i])
        for origins, directions, color, marker in [
            (author_origins, author_directions, colors[0], "o"),
            (current_origins, current_directions, colors[1], "x"),
        ]:
            origin = origins[i]
            end = endpoint(origin, directions[i], frames[i])
            ax.annotate(
                "",
                xy=end,
                xytext=origin,
                arrowprops={"arrowstyle": "->", "color": color, "lw": 1.8},
            )
            ax.plot(*origin, marker=marker, color=color, mfc="none", ms=10, mew=1.8)
        ax.axis("off")
        ax.set_title(
            f"{times[i]:.2f} h"
            + (" · registration anchor" if i == reference_index else ""),
            loc="left",
            fontsize=11,
        )
    fig.suptitle(
        "Video 2 · mapped illustrated line and current fitted line",
        x=0.035,
        ha="left",
        fontsize=15,
        weight="bold",
    )
    fig.text(
        0.035,
        0.145,
        "Orange ○: published drawing mapped at frame 85     Purple ×: current wavefront fit",
        fontsize=10,
        color="#535d6b",
    )
    fig.text(
        0.035,
        0.085,
        "Both use the same BF translation. No origin is moved onto signal when the selected line is outside early tissue.",
        fontsize=9,
        color="#677285",
    )
    fig.text(
        0.035,
        0.03,
        "The drawn arrow is a reviewed approximation, not an author-deposited center/ROI trajectory.",
        fontsize=9,
        color="#677285",
    )
    fig.subplots_adjust(left=0.025, right=0.985, top=0.88, bottom=0.22, wspace=0.06)
    for ext in ["png", "svg", "pdf"]:
        fig.savefig(out / ("video2-author-line-roi." + ext), dpi=200)
    plt.close(fig)


def run(source_dir, registration_path):
    base = ASSET_ROOT / "data/derived/lauschke-2013"
    figures = ASSET_ROOT / "figures/lauschke-2013"
    movie = source_dir / "41586_2013_BFnature11804_MOESM293_ESM.mov"
    registration = json.loads(registration_path.read_text())
    errors = validate_registration(registration)
    if (
        digest(movie) != SOURCE_HASHES[2]
        or digest(movie) != registration["source_movie_sha256"]
    ):
        raise ValueError("Source movie hash changed")
    frames = np.array(decode(movie))
    reference_path = base / "video2-kymograph.npz"
    reference_hash = digest(reference_path)
    current = np.load(reference_path)
    geometry = np.load(base / "video2-geometry.npz")
    times = current["time_h"]
    positions = current["position_um"]
    shifts = geometry["shifts_xy"]
    masks = geometry["masks"]
    assert len(frames) == len(times) == len(shifts) == 160
    origins, directions, start, tip = mapped_line(registration, shifts)
    index = registration["reference_frame_index_0_based"]
    assert abs(times[index] - registration["reference_video_overlay_h"]) < 0.005
    author, counts = sample_line(frames, origins, directions, positions, masks)
    control, _ = sample_line(
        frames, current["origins_xy"], current["directions_xy"], positions, masks
    )
    # Verify the common interval rule leaves the existing current matrix intact.
    if not np.array_equal(control, current["intensity"], equal_nan=True):
        raise ValueError(
            "Shared sampling mask changed the current reference; inspect before comparison"
        )
    smoothed, _ = sample_line(
        frames, origins, directions, positions, masks, sigma_um=SIGMA_UM
    )
    fixed, _ = sample_line(
        frames, np.tile(start, (160, 1)), directions, positions, masks
    )
    finite = np.r_[author[np.isfinite(author)], control[np.isfinite(control)]]
    limits = np.array([finite.min(), finite.max()])
    assert limits[1] > limits[0] and not np.isinf(author).any()
    np.savez_compressed(
        base / "video2-author-line.npz",
        intensity=author,
        current_intensity=current["intensity"],
        spatial_smoothed_intensity=smoothed,
        current_spatial_smoothed_intensity=current["spatial_smoothed_intensity"],
        fixed_image_intensity=fixed,
        time_h=times,
        position_um=positions,
        origins_xy=origins,
        directions_xy=directions,
        current_origins_xy=current["origins_xy"],
        current_directions_xy=current["directions_xy"],
        valid_width_counts=counts,
        shared_color_limits=limits,
    )
    render_pair(
        author,
        control,
        times,
        positions,
        limits,
        times[index],
        figures,
        "video2-author-line-comparison",
    )
    render_pair(
        smoothed,
        current["spatial_smoothed_intensity"],
        times,
        positions,
        limits,
        times[index],
        figures,
        "video2-author-line-spatial-comparison",
        True,
    )
    render_rois(
        frames,
        origins,
        directions,
        current["origins_xy"],
        current["directions_xy"],
        positions,
        times,
        figures,
        index,
    )
    valid_columns = np.isfinite(author).any(axis=0)
    indices = np.flatnonzero(valid_columns)
    trace = {
        "method_version": "illustrated-roi-compare-v1",
        "paper_id": "lauschke-2013",
        "source_movie": movie.name,
        "source_sha256": digest(movie),
        "reference_matrix": "video2-kymograph.npz",
        "reference_matrix_sha256": reference_hash,
        "reference_matrix_preserved_exactly": digest(reference_path) == reference_hash,
        "registration": registration_path.name,
        "registration_sha256": digest(registration_path),
        "reference_frame_index_0_based": index,
        "reference_overlay_h": float(times[index]),
        "mapped_start_xy_at_reference": start.tolist(),
        "mapped_tip_xy_at_reference": tip.tolist(),
        "angle_deg_image_x_right_y_down": float(
            np.degrees(np.arctan2(directions[0, 1], directions[0, 0]))
        ),
        "graphic_endpoint_precision_panel_px": registration[
            "graphic_precision_panel_px"
        ],
        "median_registration_residual_video_px": float(np.median(errors)),
        "sampling_motion_rule": "mapped start at frame 85 + the same BF displacement relative to frame 85 used in the current reconstruction; direction fixed",
        "shape_space_time": list(author.shape),
        "sampled_frame_count": 160,
        "columns_with_tissue_samples": int(valid_columns.sum()),
        "first_column_with_tissue_samples": int(indices[0]),
        "first_tissue_overlay_h": float(times[indices[0]]),
        "time_basis": "unchanged burned-in video timestamps, not re-zeroed at the Figure 1d inset label",
        "time_range_h": [float(times[0]), float(times[-1])],
        "um_per_video_pixel": UM_PER_PX,
        "strip_width_px": WIDTH_PX,
        "sampling": "original decoded mean RGB; bilinear width samples; no added filtering in main comparison",
        "missing": "require >=75% valid strip width; retain longest continuous tissue/FOV run; allow a missing leading segment when the origin lies outside tissue; never fill missing values",
        "comparison_color_limits_raw": limits.tolist(),
        "normalization": "one finite-value min-max over the union of both complete matrices, shared between panels; no percentile clipping",
        "spatial_control_sigma_um": SIGMA_UM,
        "extra_variant": "fixed_image_intensity uses the literal line in unchanged image coordinates; saved as a registration-assumption sensitivity check",
        "limitations": [
            "The starting point and direction come from a drawn arrow, not an author-deposited ROI or verified biological source.",
            "The paper does not specify the full time-dependent ROI; shared BF motion is a controlled reconstruction assumption.",
            "Initial no-tissue intervals remain missing, even when this differs from the appearance of published Fig. 1f.",
            "Comparison distances are measured from different ROI origins and do not identify matched cells.",
            "Both methods retain the same video scale and time labels; paper inset minute labels are not used to recalibrate either axis.",
            "Compressed video display values are not raw fluorescence/photon counts.",
        ],
        "source_terms": "Nature copyright; no open reuse license verified.",
        "script": "analysis/extract_lauschke_author_line.py",
        "script_sha256": digest(__file__),
        "dependency_hashes": {
            name: digest(Path(__file__).with_name(name))
            for name in ["reproduce_lauschke_views.py", "extract_video_kymographs.py"]
        },
    }
    (base / "video2-author-line-provenance.json").write_text(
        json.dumps(trace, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                k: trace[k]
                for k in [
                    "mapped_start_xy_at_reference",
                    "angle_deg_image_x_right_y_down",
                    "shape_space_time",
                    "columns_with_tissue_samples",
                    "first_tissue_overlay_h",
                    "comparison_color_limits_raw",
                    "reference_matrix_preserved_exactly",
                ]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--registration", type=Path, required=True)
    args = parser.parse_args()
    run(args.source_dir, args.registration)

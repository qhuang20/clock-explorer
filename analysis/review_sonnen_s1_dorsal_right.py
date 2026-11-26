# SPDX-License-Identifier: MIT
"""Measure the reviewer-marked dorsal corridor in Sonnen Movie S1."""

import json
from pathlib import Path

import av
import numpy as np

from extract_sonnen_additional import SETTINGS, digest, image_validity, sample_image
from paths import ASSET_ROOT
from verify_sonnen_candidates import strip_profile

STUDY = Path("sonnen-2018")
REVIEW = Path("s1-dorsal-right-review")
CFG = SETTINGS["s1"]
# Native image coordinates. Frame, P-side sampling start and anteriorward
# direction point. The latter defines a direction, while arc extent is fixed
# by the original distance grid. The points follow the reviewed visible corridor.
KEYS = np.array(
    [
        [0, 540, 580, 386, 100],
        [7, 522, 568, 397, 96],
        [15, 543, 569, 392, 92],
        [23, 535, 584, 385, 115],
        [31, 515, 596, 374, 123],
        [39, 522, 608, 360, 133],
        [44, 522, 616, 353, 158],
        [47, 534, 620, 362, 156],
        [55, 533, 638, 357, 178],
        [63, 558, 650, 359, 204],
        [71, 586, 673, 349, 235],
        [79, 622, 704, 362, 281],
        [87, 660, 702, 374, 274],
    ],
    dtype=float,
)


def paths_for_frames(indices, positions_um, scale):
    points = np.column_stack(
        [np.interp(indices, KEYS[:, 0], KEYS[:, k]) for k in range(1, 5)]
    )
    origins = points[:, :2]
    directions = points[:, 2:] - origins
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    paths = (
        origins[:, None, :]
        + positions_um[None, :, None] * directions[:, None, :] / scale
    )
    normals = np.column_stack([-directions[:, 1], directions[:, 0]])
    return paths, normals, origins, directions


def draw_band(ax, path, normal, width, color):
    half = width * normal / 2
    outline = np.array(
        [
            path[0] + half,
            path[-1] + half,
            path[-1] - half,
            path[0] - half,
            path[0] + half,
        ]
    )
    ax.plot(*outline.T, color=color, lw=1.15)
    ax.annotate(
        "",
        xy=path[-1],
        xytext=path[0],
        arrowprops={"arrowstyle": "->", "color": color, "linewidth": 1.15},
    )


def render(
    frames,
    times,
    positions,
    baseline,
    old_paths,
    old_normals,
    candidate,
    paths,
    normals,
    width,
    destination,
):
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    plt.rcParams.update(
        {"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none"}
    )
    old_color, new_color = "#76d7ee", "#ffbb56"

    def board(indices, rows, cols):
        fig, axes = plt.subplots(
            rows, cols, figsize=(3.45 * cols, 3.23 * rows + 0.5), layout="constrained"
        )
        fig.suptitle("Sonnen 2018 · Movie S1 · dorsal sampling ROIs", fontsize=16)
        for ax, i in zip(axes.flat, indices):
            ax.imshow(frames[i], interpolation="nearest")
            draw_band(ax, old_paths[i], old_normals[i], width, old_color)
            draw_band(ax, paths[i], normals[i], width, new_color)
            ax.text(
                *(paths[i, 0] + [18, 13]),
                "s = 0",
                color=new_color,
                fontsize=8,
                bbox={"facecolor": "#17171a", "edgecolor": "none", "pad": 1.5},
            )
            ax.text(
                *(paths[i, -1] + [18, -12]),
                "toward A",
                color=new_color,
                fontsize=8,
                bbox={"facecolor": "#17171a", "edgecolor": "none", "pad": 1.5},
            )
            ax.set_title(f"Frame {i} · {times[i]:.2f} h", fontsize=10)
            ax.set_axis_off()
        for ax in list(axes.flat)[len(indices) :]:
            ax.set_axis_off()
        fig.supxlabel(
            "Cyan: current ROI    Orange: right-side ROI    Both strips: approx. 70 µm × 300 µm",
            fontsize=11,
        )
        return fig

    fig = board([0, 15, 31, 44, 63, 87], 2, 3)
    fig.savefig(destination / "roi-comparison.jpg", dpi=160, pil_kwargs={"quality": 94})
    plt.close(fig)
    with PdfPages(destination / "all-frames.pdf") as review:
        for start in range(0, len(frames), 12):
            fig = board(range(start, min(start + 12, len(frames))), 3, 4)
            review.savefig(fig, dpi=115)
            plt.close(fig)

    def edges(values):
        return np.r_[
            values[0] - (values[1] - values[0]) / 2,
            (values[:-1] + values[1:]) / 2,
            values[-1] + (values[-1] - values[-2]) / 2,
        ]

    low = float(min(np.nanmin(baseline), np.nanmin(candidate)))
    high = float(max(np.nanmax(baseline), np.nanmax(candidate)))
    palette = plt.get_cmap("OrRd").with_extremes(bad="#eff1f4")
    fig, axes = plt.subplots(
        1, 2, sharey=True, figsize=(11.4, 4.5), layout="constrained"
    )
    for ax, values, title in zip(
        axes, [baseline, candidate], ["Current ROI", "Right-side dorsal ROI"]
    ):
        image = ax.pcolormesh(
            edges(times),
            edges(positions),
            (values - low) / (high - low),
            cmap=palette,
            vmin=0,
            vmax=1,
            rasterized=True,
        )
        ax.set(
            xlim=(times[0], times[-1]),
            ylim=(positions[0], positions[-1]),
            xlabel="Movie time (h)",
            title=title,
        )
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Distance from each ROI start (approx. µm)")
    fig.colorbar(image, ax=axes, label="Relative display intensity", ticks=[0, 0.5, 1])
    for ext in ["svg", "png"]:
        fig.savefig(destination / f"kymograph-comparison.{ext}", dpi=160)
    plt.close(fig)
    return [low, high]


def run():
    movie = ASSET_ROOT / "data/source-archive" / STUDY / "mmc2.mp4"
    reference = ASSET_ROOT / "data/derived" / STUDY / "movie-s1/kymograph.npz"
    movie_hash, reference_hash = digest(movie), digest(reference)
    if movie_hash != CFG["sha256"]:
        raise ValueError("Unexpected Movie S1 source hash")
    with av.open(str(movie)) as container:
        frames = [
            frame.to_ndarray(format="rgb24") for frame in container.decode(video=0)
        ]
    if len(frames) != CFG["count"] or list(frames[0].shape[:2]) != CFG["shape"]:
        raise ValueError("Unexpected Movie S1 frame count or shape")
    with np.load(reference) as archive:
        baseline, times, positions, old_paths, old_normals = (
            archive[k]
            for k in ["intensity", "time_h", "position_um", "path_xy", "normals_xy"]
        )
        width, scale = float(archive["strip_width_px"]), float(archive["um_per_px"])
    path, normals, origins, directions = paths_for_frames(
        np.arange(len(frames)), positions, scale
    )
    offsets = np.linspace(-width / 2, width / 2, int(np.ceil(width)) + 1)
    support = image_validity("s1", frames[0].shape[:2])
    matrix = np.empty_like(baseline)
    counts = np.empty(matrix.shape, dtype=int)
    for i, frame in enumerate(frames):
        image = frame[:, :, 1]
        matrix[:, i], counts[:, i] = sample_image(
            image, path[i], normals[i], width, support
        )
        control, control_counts = strip_profile(
            image, path[i], normals[i], offsets, support
        )
        np.testing.assert_allclose(matrix[:, i], control, atol=1e-10, rtol=0)
        np.testing.assert_array_equal(counts[:, i], control_counts)
    if np.any(directions[:, 1] >= 0) or np.any(counts != len(offsets)):
        raise ValueError(
            "Candidate leaves the supported image area or changes direction"
        )

    data = ASSET_ROOT / "data/derived" / STUDY / REVIEW
    figures = ASSET_ROOT / "figures" / STUDY / REVIEW
    for dest in [data, figures]:
        dest.mkdir(parents=True, exist_ok=True)
    matrix_file = data / "kymograph.npz"
    np.savez_compressed(
        matrix_file,
        intensity=matrix,
        baseline_intensity=baseline,
        time_h=times,
        position_um=positions,
        frame_index=np.arange(len(frames)),
        path_xy=path,
        normals_xy=normals,
        origins_xy=origins,
        directions_xy=directions,
        strip_width_px=width,
        um_per_px=scale,
        valid=np.isfinite(matrix),
        fov_width_counts=counts,
    )
    limits = render(
        frames,
        times,
        positions,
        baseline,
        old_paths,
        old_normals,
        matrix,
        path,
        normals,
        width,
        figures,
    )
    if digest(reference) != reference_hash:
        raise ValueError("Reference matrix changed during review")
    record = {
        "dataset_id": CFG["dataset"],
        "source_movie": "Movie S1 · dorsal view",
        "source_sha256": movie_hash,
        "reference_sha256": reference_hash,
        "matrix_sha256": digest(matrix_file),
        "geometry": "Reviewer-selected right-side, anteriorward corridor. Straight strips interpolate 13 manual keyframes in native coordinates.",
        "landmark_columns": [
            "frame",
            "start_x",
            "start_y",
            "anteriorward_x",
            "anteriorward_y",
        ],
        "keyframes": KEYS.tolist(),
        "coordinate_reference": "Distance from the candidate strip start, increasing anteriorward. The two strips have different zero positions.",
        "width_source_px": width,
        "width_samples": len(offsets),
        "approx_um_per_px": scale,
        "signal": "Mean of bilinear samples in the original decoded green display channel, without added smoothing.",
        "validity": "Full-width image and annotation checks, with visual corridor review. Tissue segmentation was unavailable.",
        "shared_display_limits": limits,
        "frame_count": len(frames),
        "time_range_h": [float(times[0]), float(times[-1])],
        "distance_range_um": [float(positions[0]), float(positions[-1])],
        "verified_by_independent_sampler_frames": len(frames),
    }
    (data / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"Saved the dorsal ROI comparison across {len(frames)} frames in {figures}")


if __name__ == "__main__":
    run()

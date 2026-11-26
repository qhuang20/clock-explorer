# SPDX-License-Identifier: MIT
"""Track the visible outer envelope of Sonnen Movie S3 and review radial scans."""

import csv
import json
from pathlib import Path

import av
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

from extract_sonnen_additional import SETTINGS, digest, image_validity, sample_image
from paths import ASSET_ROOT
from verify_sonnen_candidates import strip_profile

STUDY = Path("sonnen-2018")
REVIEW = Path("s3-moving-center-review")
CFG = SETTINGS["s3"]
THRESHOLDS = (18, 24, 30)
EDGE_MARGIN_PX = 5
OLD_COLOR = "#7cd8ee"
NEW_COLOR = "#ffb651"


def measure_envelope(smooth, support, threshold):
    """Fit a geometric center to the hull of the main visible component."""
    binary = ((smooth >= threshold) & support).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary)
    if count < 2:
        raise ValueError("No visible component above the envelope threshold")
    largest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    component = (labels == largest).astype(np.uint8)
    contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    hull = cv2.convexHull(max(contours, key=cv2.contourArea))
    envelope = np.zeros(binary.shape, np.uint8)
    cv2.fillConvexPoly(envelope, hull, 1)
    polygon, _ = cv2.findContours(envelope, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    outline = max(polygon, key=cv2.contourArea)
    if len(outline) < 5:
        raise ValueError("Insufficient outer envelope support for ellipse fit")
    center, diameters, _ = cv2.fitEllipseDirect(outline)
    if min(diameters) < 90 or max(diameters) > 460:
        raise ValueError("Unexpected envelope size for this specimen")
    return center, hull[:, 0, :], envelope.astype(bool)


def track_centers(frames, support):
    alternatives, envelopes, hulls = [], [], []
    weights = ndi.gaussian_filter(support.astype(np.float32), 3)
    for frame in frames:
        signal = np.where(support, frame[:, :, 1], 0).astype(np.float32)
        smooth = np.divide(
            ndi.gaussian_filter(signal, 3),
            weights,
            out=np.zeros_like(signal),
            where=weights > 1e-6,
        )
        fits = [measure_envelope(smooth, support, value) for value in THRESHOLDS]
        alternatives.append([fit[0] for fit in fits])
        _, hull, envelope = fits[1]
        hulls.append(hull)
        envelopes.append(ndi.distance_transform_edt(envelope) > EDGE_MARGIN_PX)
    alternatives = np.array(alternatives)
    nominal = np.median(alternatives, axis=1)
    centers = ndi.gaussian_filter1d(
        ndi.median_filter(nominal, size=(3, 1), mode="nearest"),
        1,
        axis=0,
        mode="nearest",
    )
    return centers, alternatives, np.array(envelopes), hulls


def sample(frames, paths, width_px, support, envelopes):
    """Average original display pixels, with a conservative outer extent."""
    offsets = np.linspace(-width_px / 2, width_px / 2, int(np.ceil(width_px)) + 1)
    normal = np.array([1.0, 0.0])
    profiles, fov_counts, envelope_counts = [], [], []
    for frame, path, envelope in zip(frames, paths, envelopes):
        raw, counts = sample_image(frame[:, :, 1], path, normal, width_px, support)
        check, check_counts = strip_profile(
            frame[:, :, 1], path, normal, offsets, support
        )
        np.testing.assert_allclose(raw, check, atol=1e-10, rtol=0, equal_nan=True)
        np.testing.assert_array_equal(counts, check_counts)
        xy = path[:, None, :] + offsets[None, :, None] * normal
        inside = ndi.map_coordinates(
            envelope,
            [xy[..., 1], xy[..., 0]],
            order=0,
            mode="constant",
            cval=False,
        ).sum(axis=1)
        valid = np.logical_and.accumulate((inside == len(offsets)) & np.isfinite(raw))
        if not valid[0]:
            raise ValueError("Tracked center has no contiguous full-width support")
        profiles.append(np.where(valid, raw, np.nan))
        fov_counts.append(counts)
        envelope_counts.append(inside)
    return np.array(profiles).T, np.array(fov_counts).T, np.array(envelope_counts).T


def roi_frame(frame, old_path, new_path, hull, width, history):
    im = Image.fromarray(frame).convert("RGB")
    draw = ImageDraw.Draw(im)
    draw.line([tuple(p) for p in np.r_[hull, hull[:1]]], fill="#c7c5da", width=1)
    if len(history) > 1:
        draw.line([tuple(p) for p in history], fill=NEW_COLOR, width=2)
    for path, color in [(old_path, OLD_COLOR), (new_path, NEW_COLOR)]:
        x, y = path[0]
        end_y = path[-1, 1]
        draw.rectangle((x - width / 2, end_y, x + width / 2, y), outline=color, width=2)
        draw.line((x, y, x, end_y), fill=color, width=2)
        draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color, outline="#222", width=1)
    return im


def render(
    figures, video, times, positions, old, moving, centers, alternatives, make_overlay
):
    import matplotlib.pyplot as plt
    from matplotlib import get_data_path

    plt.rcParams.update(
        {"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none"}
    )
    fig = plt.figure(figsize=(10.7, 9.1), layout="constrained")
    grid = fig.add_gridspec(3, 3, height_ratios=[1, 1, 0.48])
    fig.suptitle("Sonnen 2018 · Movie S3 · tracking the culture center", fontsize=16)
    for j, i in enumerate([0, 15, 35, 55, 80, 110]):
        ax = fig.add_subplot(grid[j // 3, j % 3])
        ax.imshow(make_overlay(i))
        ax.set_title(f"Frame {i} · {times[i]:.2f} h")
        ax.set_axis_off()
    traj = fig.add_subplot(grid[2, :])
    colors = ["#6356b3", "#ba602a"]
    for axis, label, color in zip(range(2), ["x · rightward", "y · downward"], colors):
        fit_values = alternatives[:, :, axis] - centers[0, axis]
        traj.fill_between(
            times,
            fit_values.min(axis=1),
            fit_values.max(axis=1),
            color=color,
            alpha=0.16,
        )
        traj.plot(times, centers[:, axis] - centers[0, axis], color=color, label=label)
    traj.set(
        xlim=(times[0], times[-1]),
        xlabel="Movie time (h)",
        ylabel="Shift from first frame\n(source pixels)",
    )
    traj.spines[["top", "right"]].set_visible(False)
    traj.legend(loc="upper left", ncols=2, frameon=False)
    fig.supxlabel(
        "Cyan: fixed ROI   ·   Orange: moving geometric center and ROI   ·   Gray: outer envelope",
        fontsize=10,
    )
    fig.savefig(figures / "roi-comparison.jpg", dpi=160, pil_kwargs={"quality": 93})
    plt.close(fig)

    def edges(a):
        return np.r_[
            a[0] - (a[1] - a[0]) / 2, (a[:-1] + a[1:]) / 2, a[-1] + (a[-1] - a[-2]) / 2
        ]

    common = np.isfinite(old) & np.isfinite(moving)
    limits = [
        float(min(np.nanmin(old), np.nanmin(moving))),
        float(max(np.nanmax(old), np.nanmax(moving))),
    ]
    fig, axes = plt.subplots(
        1, 3, sharey=True, figsize=(13.5, 4.35), layout="constrained"
    )
    palette = plt.get_cmap("OrRd").with_extremes(bad="#eff1f4")
    for ax, title, image in zip(
        axes,
        [
            "Fixed origin · common coverage",
            "Moving center · common coverage",
            "Moving center · full reviewed extent",
        ],
        [np.where(common, old, np.nan), np.where(common, moving, np.nan), moving],
    ):
        normalized = (image - limits[0]) / (limits[1] - limits[0])
        heat = ax.pcolormesh(
            edges(times),
            edges(positions),
            normalized,
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
    fig.colorbar(heat, ax=axes, label="Relative display intensity", ticks=[0, 0.5, 1])
    for ext in ["svg", "png"]:
        fig.savefig(figures / f"kymograph-comparison.{ext}", dpi=160)
    plt.close(fig)

    font = ImageFont.truetype(
        str(Path(get_data_path()) / "fonts/ttf/DejaVuSans.ttf"), 15
    )
    with av.open(str(video), "w", options={"movflags": "+faststart"}) as movie:
        stream = movie.add_stream("libx264", rate=8, options={"crf": "20"})
        stream.width, stream.height, stream.pix_fmt = 512, 564, "yuv420p"
        for i, time in enumerate(times):
            still = Image.new("RGB", (512, 564), "#17191e")
            still.paste(make_overlay(i), (0, 0))
            caption = ImageDraw.Draw(still)
            caption.text(
                (12, 515),
                f"Movie S3 · frame {i} · {time:.2f} h",
                fill="white",
                font=font,
            )
            caption.text((12, 539), "Cyan: fixed ROI", fill=OLD_COLOR, font=font)
            caption.text(
                (168, 539), "Orange: moving center & ROI", fill=NEW_COLOR, font=font
            )
            movie.mux(stream.encode(av.VideoFrame.from_image(still)))
        movie.mux(stream.encode())
    return limits


def run():
    movie = ASSET_ROOT / "data/source-archive" / STUDY / "mmc4.mp4"
    baseline = ASSET_ROOT / "data/derived" / STUDY / "movie-s3/kymograph.npz"
    movie_hash, baseline_hash = digest(movie), digest(baseline)
    if movie_hash != CFG["sha256"]:
        raise ValueError("Unexpected Movie S3 source hash")
    with av.open(str(movie)) as container:
        frames = [f.to_ndarray(format="rgb24") for f in container.decode(video=0)]
    shape = frames[0].shape[:2]
    if len(frames) != CFG["count"] or list(shape) != CFG["shape"]:
        raise ValueError("Unexpected Movie S3 frame count or shape")
    with np.load(baseline) as src:
        old, times, positions, old_paths = (
            src[k] for k in ["intensity", "time_h", "position_um", "path_xy"]
        )
        width, scale = float(src["strip_width_px"]), float(src["um_per_px"])
    support = image_validity("s3", shape)
    centers, alternatives, envelopes, hulls = track_centers(frames, support)
    if any(
        np.any(
            (hull[:, 0] <= 8)
            | (hull[:, 0] >= shape[1] - 5)
            | (hull[:, 1] <= 4)
            | (hull[:, 1] >= shape[0] - 5)
        )
        for hull in hulls
    ):
        raise ValueError("Review envelope fit against the acquisition boundary")
    direction = np.array([0.0, -1.0])
    paths = centers[:, None, :] + positions[None, :, None] / scale * direction
    matrix, fov_counts, envelope_counts = sample(
        frames, paths, width, support, envelopes
    )
    valid = np.isfinite(matrix)

    data = ASSET_ROOT / "data/derived" / STUDY / REVIEW
    figures = ASSET_ROOT / "figures" / STUDY / REVIEW
    data.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    numeric = data / "kymograph.npz"
    np.savez_compressed(
        numeric,
        intensity=matrix,
        baseline_intensity=old,
        time_h=times,
        position_um=positions,
        origins_xy=centers,
        threshold_centers_xy=alternatives,
        envelope_thresholds=THRESHOLDS,
        path_xy=paths,
        direction_xy=direction,
        frame_index=np.arange(len(frames)),
        valid=valid,
        common_valid=np.isfinite(old) & valid,
        fov_width_counts=fov_counts,
        envelope_width_counts=envelope_counts,
        outer_envelope_support=envelopes,
        strip_width_px=width,
        um_per_px=scale,
    )
    with (data / "center-trajectory.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "frame",
                "time_h",
                "center_x_source_px",
                "center_y_source_px",
                "last_valid_distance_um",
            ]
        )
        writer.writerows(
            (i, t, *centers[i], positions[valid[:, i]][-1]) for i, t in enumerate(times)
        )

    def overlay(i):
        return roi_frame(
            frames[i],
            old_paths[i, np.isfinite(old[:, i])],
            paths[i, valid[:, i]],
            hulls[i],
            width,
            centers[: i + 1],
        )

    video = data / "roi-review.mp4"
    limits = render(
        figures, video, times, positions, old, matrix, centers, alternatives, overlay
    )
    if digest(baseline) != baseline_hash:
        raise ValueError("Reference matrix changed during review")
    with av.open(str(video)) as container:
        if sum(1 for _ in container.decode(video=0)) != len(frames):
            raise ValueError("Review playback does not cover all source frames")
    record = {
        "dataset_id": CFG["dataset"],
        "source": "Movie S3 · microfluidic LuVeLu",
        "source_sha256": movie_hash,
        "baseline_sha256": baseline_hash,
        "matrix_sha256": digest(numeric),
        "review_playback_sha256": digest(video),
        "method": "Largest connected foreground component after mask-normalized Gaussian filtering of the display image, convex outer hull, ellipse fit to its rasterized contour. Median center across thresholds. Three-frame median and one-frame Gaussian stabilize the center trajectory only.",
        "geometry_sigma_px": 3,
        "geometry_thresholds_in_display_units": THRESHOLDS,
        "envelope_margin_px": EDGE_MARGIN_PX,
        "origin_meaning": "Geometric outer-envelope center. This track does not identify a wave source or an anatomical landmark.",
        "support": "Full-width contiguous support within the eroded outer hull and valid image. The envelope describes outer extent and may bridge dark gaps. It does not establish inner tissue occupancy.",
        "intensity": "Mean of native green display pixels sampled bilinearly across the same 70 µm-wide, image-up strip. Source timestamps and approximate calibration retained. No added intensity filtering.",
        "experimental_time_range_h": [float(times[0]), float(times[-1])],
        "frame_count": len(frames),
        "rechecked_profiles": len(frames),
        "center_first_xy": centers[0].tolist(),
        "center_last_xy": centers[-1].tolist(),
        "max_distance_from_first_px": float(
            np.linalg.norm(centers - centers[0], axis=1).max()
        ),
        "max_threshold_disagreement_px": float(
            np.linalg.norm(
                alternatives - np.median(alternatives, axis=1, keepdims=True), axis=-1
            ).max()
        ),
        "max_frame_step_px": float(
            np.linalg.norm(np.diff(centers, axis=0), axis=1).max()
        ),
        "shared_display_limits": limits,
        "review_playback_fps": 8,
    }
    (data / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    run()

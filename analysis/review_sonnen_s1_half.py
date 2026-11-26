# SPDX-License-Identifier: MIT
"""Keyframe-constrained, one-sided optical-flow ROI for dorsal Movie S1."""

import json

import av
import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

from curved_strip import arc_length_path
from extract_sonnen_additional import SETTINGS, digest, image_validity
from paths import ASSET_ROOT
from verify_sonnen_candidates import strip_profile

REVIEW = "s1-midline-half-review"
# P-side to anteriorward, in native pixels. Reviewed seam approximations.
ANCHORS = {
    0: [[460, 700], [400, 560], [325, 400], [240, 215], [145, 45]],
    11: [[455, 690], [400, 550], [325, 380], [240, 210], [135, 40]],
    22: [[435, 700], [390, 550], [310, 365], [235, 200], [125, 40]],
    33: [[430, 710], [385, 555], [300, 380], [210, 205], [95, 35]],
    44: [[440, 725], [400, 565], [300, 385], [210, 200], [100, 35]],
    55: [[470, 740], [420, 580], [330, 410], [225, 215], [100, 45]],
    66: [[500, 770], [425, 600], [335, 420], [225, 240], [90, 60]],
    77: [[550, 830], [475, 670], [350, 475], [205, 300], [75, 110]],
    87: [[590, 925], [510, 745], [380, 525], [215, 325], [75, 140]],
}
WIDTH_PX = 60
OFFSET_PX = 85


def normals_for(path):
    tangent = np.gradient(path, axis=0)
    tangent /= np.linalg.norm(tangent, axis=1, keepdims=True)
    return np.column_stack([-tangent[:, 1], tangent[:, 0]])


def dense_anchor(points):
    points = np.asarray(points, float)
    length = np.linalg.norm(np.diff(points, axis=0), axis=1).sum()
    return arc_length_path(points, np.linspace(0, length * 0.995, 25), 1)[0]


def advect(image, next_image, seam):
    """Track texture patches exclusively on the selected side of the seam."""
    normal = normals_for(seam)
    patches = (
        seam[:, None, :] + normal[:, None, :] * np.array([55, 85, 115])[None, :, None]
    )
    points = patches.reshape(-1, 1, 2).astype(np.float32)
    moved, status, _ = cv2.calcOpticalFlowPyrLK(
        image,
        next_image,
        points,
        None,
        winSize=(41, 41),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, 0.01),
    )
    returned, reverse_status, _ = cv2.calcOpticalFlowPyrLK(
        next_image,
        image,
        moved,
        None,
        winSize=(41, 41),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, 0.01),
    )
    error = np.linalg.norm(returned[:, 0] - points[:, 0], axis=1)
    valid = (status[:, 0] > 0) & (reverse_status[:, 0] > 0) & (error < 1.5)
    valid &= np.linalg.norm(moved[:, 0] - points[:, 0], axis=1) < 25
    displacement = (moved[:, 0] - points[:, 0]).reshape(-1, 3, 2)
    supported = valid.reshape(-1, 3)
    delta = np.full_like(seam, np.nan)
    for j in range(len(seam)):
        if supported[j].any():
            delta[j] = np.median(displacement[j, supported[j]], axis=0)
    accepted = np.flatnonzero(np.isfinite(delta).all(axis=1))
    if not len(accepted):
        return seam.copy(), 0, None
    for axis in range(2):
        delta[:, axis] = np.interp(
            np.arange(len(seam)), accepted, delta[accepted, axis]
        )
    # Smooth geometry only, limiting independent patch jitter along the seam.
    delta = ndi.gaussian_filter1d(delta, 2, axis=0, mode="nearest")
    return (
        seam + delta,
        int(valid.sum()),
        float(np.median(error[valid])) if valid.any() else None,
    )


def track(frames):
    clahe = cv2.createCLAHE(clipLimit=2, tileGridSize=(8, 8))
    images = [clahe.apply(cv2.GaussianBlur(f[:, :, 1], (0, 0), 1)) for f in frames]
    seams = np.empty((len(frames), 25, 2))
    disagreements = np.zeros(len(frames))
    quality = []
    keys = list(ANCHORS)
    for a, b in zip(keys[:-1], keys[1:]):
        forward = {a: dense_anchor(ANCHORS[a])}
        backward = {b: dense_anchor(ANCHORS[b])}
        for i in range(a, b):
            forward[i + 1], count, error = advect(images[i], images[i + 1], forward[i])
            quality.append(
                {
                    "from": i,
                    "to": i + 1,
                    "accepted_patches": count,
                    "median_fb_error_px": error,
                }
            )
        for i in range(b, a, -1):
            backward[i - 1], count, error = advect(
                images[i], images[i - 1], backward[i]
            )
            quality.append(
                {
                    "from": i,
                    "to": i - 1,
                    "accepted_patches": count,
                    "median_fb_error_px": error,
                }
            )
        # Endpoint-correct both tracks so each reviewed keyframe remains exact.
        f_correction = backward[b] - forward[b]
        b_correction = forward[a] - backward[a]
        for i in range(a, b + 1):
            w = (i - a) / (b - a)
            f = forward[i] + w * f_correction
            r = backward[i] + (1 - w) * b_correction
            disagreements[i] = np.max(np.linalg.norm(f - r, axis=1))
            seams[i] = (1 - w) * f + w * r
    if np.any(np.diff(seams[:, :, 1], axis=1) >= 0):
        raise ValueError("Tracked seam must remain ordered toward the anterior")
    return seams, disagreements, quality


def half_support(image, seam, fov):
    y, x = np.indices(image.shape)
    boundary = np.interp(np.arange(image.shape[0]), seam[::-1, 1], seam[::-1, 0])
    side = x > boundary[:, None] + 8
    # Display-derived foreground proxy. The seam-side rule is independent of brightness.
    foreground = ndi.gaussian_filter(image.astype(float), 8) > 65
    labels, _ = ndi.label(foreground)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    component = labels == sizes.argmax()
    right_edge = np.max(np.where(component, x, -1), axis=1).astype(float)
    right_edge = ndi.median_filter(right_edge, size=15, mode="nearest")
    envelope = x < right_edge[:, None] - 8
    return side & envelope & fov


def run():
    cfg = SETTINGS["s1"]
    movie = ASSET_ROOT / "data/source-archive/sonnen-2018/mmc2.mp4"
    if digest(movie) != cfg["sha256"]:
        raise ValueError("Unexpected Movie S1 source")
    with av.open(str(movie)) as c:
        frames = [f.to_ndarray(format="rgb24") for f in c.decode(video=0)]
    reference = ASSET_ROOT / "data/derived/sonnen-2018/movie-s1/kymograph.npz"
    with np.load(reference) as old:
        baseline, times = old["intensity"], old["time_h"]
        old_paths, old_normals = old["path_xy"], old["normals_xy"]
        old_width, scale = float(old["strip_width_px"]), float(old["um_per_px"])
    seams, disagreements, quality = track(frames)
    distance = np.arange(0, 501, dtype=float)
    fov = image_validity("s1", frames[0].shape[:2])
    paths, normals, values, counts, valid = [], [], [], [], []
    offsets = np.linspace(-WIDTH_PX / 2, WIDTH_PX / 2, WIDTH_PX + 1)
    for frame, seam in zip(frames, seams):
        corridor = seam + OFFSET_PX * normals_for(seam)
        path, normal, _ = arc_length_path(corridor, distance, scale)
        support = half_support(frame[:, :, 1], seam, fov)
        raw, count = strip_profile(frame[:, :, 1], path, normal, offsets, support)
        good = np.isfinite(raw)
        # Keep the longest contiguous supported run, preserving its physical distance.
        starts = np.flatnonzero(good & ~np.r_[False, good[:-1]])
        stops = np.flatnonzero(good & ~np.r_[good[1:], False]) + 1
        keep = np.zeros(len(good), bool)
        if len(starts):
            j = np.argmax(stops - starts)
            keep[starts[j] : stops[j]] = True
        values.append(np.where(keep, raw, np.nan))
        counts.append(count)
        valid.append(keep)
        paths.append(path)
        normals.append(normal)
    matrix, valid = np.array(values).T, np.array(valid).T
    paths, normals = np.array(paths), np.array(normals)
    data = ASSET_ROOT / "data/derived/sonnen-2018" / REVIEW
    figures = ASSET_ROOT / "figures/sonnen-2018" / REVIEW
    data.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        data / "kymograph.npz",
        intensity=matrix,
        time_h=times,
        position_um=distance,
        frame_index=np.arange(len(frames)),
        path_xy=paths,
        normals_xy=normals,
        seam_xy=seams,
        strip_width_px=WIDTH_PX,
        um_per_px=scale,
        valid=valid,
        width_counts=np.array(counts).T,
        tracking_disagreement_px=disagreements,
    )
    record = {
        "analysis_script": "analysis/review_sonnen_s1_half.py",
        "analysis_script_sha256": digest(__file__),
        "source_file": "data/source-archive/sonnen-2018/mmc2.mp4",
        "dataset_id": cfg["dataset"],
        "source_sha256": digest(movie),
        "reference_sha256": digest(reference),
        "matrix_sha256": digest(data / "kymograph.npz"),
        "method": "Reviewed seam keyframes constrain forward/backward Lucas-Kanade texture tracking on the image-right side. A curved strip follows the tracked seam with a fixed normal offset.",
        "seam_keyframes_xy": ANCHORS,
        "seam_keyframe_count": len(ANCHORS),
        "tracking_parameters": {
            "lk_window_px": [41, 41],
            "lk_max_level": 3,
            "lk_iterations": 40,
            "lk_epsilon": 0.01,
            "forward_backward_rejection_px": 1.5,
            "maximum_pair_displacement_px": 25,
            "geometry_station_sigma": 2,
            "patch_side_offsets_px": [55, 85, 115],
        },
        "strip_width_px": WIDTH_PX,
        "seam_offset_px": OFFSET_PX,
        "approx_um_per_px": scale,
        "frame_count": len(frames),
        "time_range_h": times[[0, -1]].tolist(),
        "distance_range_um": distance[[0, -1]].tolist(),
        "signal": "Unfiltered original decoded green display values, bilinear resampling and transverse mean.",
        "validity": "Every transverse sample must lie on the image-right side of the reviewed seam, inside the FOV/text mask and the row-filled outer-envelope proxy from Gaussian 8 px threshold 65 largest component, with an 8 px edge margin. Longest connected supported run retained with missing prefixes unchanged.",
        "registration": "Semi-automatic geometry tracking. Nine reviewed keyframes constrain drift and growth. Individual-cell identity remains unresolved.",
        "comparison": "Both geometry/coverage and width change. Shared intensity limits and physical axes. Each path has its own P-side reference and sampled cells.",
        "max_forward_backward_geometry_disagreement_px": float(disagreements.max()),
        "tracking_quality": quality,
    }
    (data / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")
    render_review(
        frames,
        times,
        matrix,
        distance,
        baseline,
        old_paths,
        old_normals,
        old_width,
        paths,
        normals,
        WIDTH_PX,
        seams,
        valid,
        figures,
    )
    print(
        json.dumps(
            {
                "output": str(figures),
                "valid_samples": int(valid.sum()),
                "max_tracking_disagreement_px": float(disagreements.max()),
            }
        )
    )


def render_review(
    frames,
    times,
    matrix,
    distance,
    baseline,
    old_paths,
    old_normals,
    old_width,
    paths,
    normals,
    width,
    seams,
    valid,
    figures,
):
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    plt.rcParams.update(
        {"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none"}
    )

    def overlay(i, previous=False):
        im = Image.fromarray(frames[i])
        d = ImageDraw.Draw(im)
        seam = seams[i]
        # Shade the unselected side, keeping the original source view orientation.
        shape = im.size
        shade = Image.new("RGBA", shape, (0, 0, 0, 0))
        painter = ImageDraw.Draw(shade)
        polygon = (
            [(0, 0), (float(seam[-1, 0]), 0)]
            + [tuple(p) for p in seam[::-1]]
            + [(float(seam[0, 0]), shape[1]), (0, shape[1])]
        )
        painter.polygon(polygon, fill=(25, 20, 45, 95))
        im = Image.alpha_composite(im.convert("RGBA"), shade).convert("RGB")
        d = ImageDraw.Draw(im)
        d.line([tuple(p) for p in seam], fill="#ff7060", width=3)
        p, n = paths[i][valid[:, i]], normals[i][valid[:, i]]
        if previous:
            old = old_paths[i]
            half = old_normals[i] * old_width / 2
            d.line(
                [
                    tuple(p)
                    for p in np.r_[old + half, (old - half)[::-1], (old + half)[:1]]
                ],
                fill="#76d7ee",
                width=2,
            )
        for edge in [p + n * width / 2, p - n * width / 2, p]:
            d.line([tuple(v) for v in edge], fill="#ffbb56", width=3)
        for point, label in [(p[0], "P-side"), (p[-1], "toward A")]:
            xy = tuple(point + [12, -15])
            d.text(xy, label, fill="#ffbb56", stroke_width=1, stroke_fill="black")
        return im

    def board(indices):
        fig, axes = plt.subplots(2, 3, figsize=(11, 7.8), layout="constrained")
        for ax, i in zip(axes.flat, indices):
            ax.imshow(overlay(i, previous=True))
            ax.set_axis_off()
            ax.set_title(f"Frame {i} · {times[i]:.2f} h")
        for ax in list(axes.flat)[len(indices) :]:
            ax.set_axis_off()
        fig.supxlabel(
            "Red: tracked seam · Orange: selected half-strip · Cyan: previous ROI",
            fontsize=11,
        )
        return fig

    fig = board([0, 22, 44, 60, 75, 87])
    fig.savefig(figures / "roi-comparison.jpg", dpi=160)
    plt.close(fig)
    with PdfPages(figures / "all-frames.pdf") as pdf:
        for start in range(0, len(frames), 6):
            fig = board(range(start, min(start + 6, len(frames))))
            pdf.savefig(fig, dpi=80)
            plt.close(fig)
    with av.open(str(figures / "roi-review.mp4"), "w") as out:
        stream = out.add_stream("libx264", rate=10)
        stream.width = 988
        stream.height = 982
        stream.pix_fmt = "yuv420p"
        for i in range(len(frames)):
            for packet in stream.encode(av.VideoFrame.from_image(overlay(i))):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    low = min(np.nanmin(baseline), np.nanmin(matrix))
    high = max(np.nanmax(baseline), np.nanmax(matrix))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7), sharey=True, layout="constrained")
    for ax, values, positions, title in zip(
        axes,
        [baseline, matrix],
        [np.arange(baseline.shape[0]), distance],
        ["Previous ROI · 70 µm-wide", "Tracked half-strip · 37 µm-wide"],
    ):
        heat = ax.pcolormesh(
            times,
            positions,
            (values - low) / (high - low),
            shading="nearest",
            cmap=plt.get_cmap("OrRd").with_extremes(bad="#eff1f4"),
            vmin=0,
            vmax=1,
            rasterized=True,
        )
        ax.set(
            xlim=(times[0], times[-1]),
            ylim=(0, distance[-1]),
            xlabel="Movie time (h)",
            title=title,
        )
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Distance from each strip start (approx. µm)")
    fig.colorbar(heat, ax=axes, label="Relative display intensity", ticks=[0, 0.5, 1])
    for ext in ["svg", "png"]:
        fig.savefig(figures / f"kymograph-comparison.{ext}", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    run()

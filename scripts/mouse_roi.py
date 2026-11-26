"""Extract native-frame strip profiles for the two curated mouse movies."""

import av
import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates, median_filter
from scipy.interpolate import PchipInterpolator
from PIL import Image
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def signal(rgb, role, channel=None):
    r, g, b = np.moveaxis(rgb.astype(np.float32), -1, 0)
    if channel == "magenta":
        return (r + b) / 2
    if role == "axial":
        return np.maximum(0, g - (r + b) / 2)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def radial_centers(stack):
    # Compare simultaneous rings after removing stationary texture and frame-wide changes.
    small = gaussian_filter(stack, (0, 3, 3))[:, ::4, ::4]
    angle = np.arange(24) * (2 * np.pi / 24)
    radii = np.arange(4, 23)
    dx = np.cos(angle)[:, None] * radii
    dy = np.sin(angle)[:, None] * radii
    indices = list(range(0, len(stack), 10)) + [len(stack) - 1]
    centers = []
    for t in indices:
        block = small[max(0, t - 10) : min(len(stack), t + 11) : 2]
        block = block - block.mean(axis=0)
        block -= block.mean(axis=(1, 2), keepdims=True)
        best = (-np.inf, None)
        for x in range(19, 52):
            for y in range(21, 52):
                vals = block[
                    :, np.rint(y + dy).astype(int), np.rint(x + dx).astype(int)
                ]
                score = np.mean(vals.mean(axis=1) ** 2) / max(np.mean(vals**2), 1e-8)
                if score > best[0]:
                    best = score, [x * 4, y * 4]
        centers.append(best[1])
    centers = median_filter(np.array(centers), size=(3, 1), mode="nearest")
    return np.column_stack(
        [np.interp(np.arange(len(stack)), indices, centers[:, d]) for d in (0, 1)]
    )


def geometry(job, stack):
    curves = []
    if job["role"] == "axial":
        controls = PchipInterpolator(job["keyframes"], job["path_xy"], axis=0)(
            np.arange(len(stack))
        )
        u = np.linspace(0, 1, 1000)[:, None]
        for p, q, r, s in controls:
            pts = (
                (1 - u) ** 3 * p
                + 3 * u * (1 - u) ** 2 * q
                + 3 * u**2 * (1 - u) * r
                + u**3 * s
            )
            arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
            curves.append(
                np.column_stack(
                    [np.interp(np.arange(int(arc[-1]) + 1), arc, col) for col in pts.T]
                )
            )
    else:
        centers = radial_centers(stack)
        direction = np.array(job["direction_xy"], dtype=float)
        direction /= np.linalg.norm(direction)
        normal = np.array([-direction[1], direction[0]])
        for im, center in zip(stack, centers):
            # A neighborhood mean recognizes the envelope rather than individual dark cells.
            support = gaussian_filter(im, 5)
            height, width = im.shape
            ray = center + np.arange(int(np.hypot(width, height)))[:, None] * direction
            xy = ray[:, None, :] + np.arange(-6, 7)[None, :, None] * normal
            valid = (
                (xy[:, :, 0] >= 1)
                & (xy[:, :, 0] < width - 1)
                & (xy[:, :, 1] > 12)
                & (xy[:, :, 1] < height - 1)
            ).all(axis=1)
            ray, xy = ray[valid], xy[valid]
            scores = map_coordinates(support, [xy[:, :, 1], xy[:, :, 0]], order=1).min(
                axis=1
            )
            stop = np.flatnonzero(
                np.convolve((scores < 9).astype(int), np.ones(4, dtype=int), "valid")
                == 4
            )
            if stop.size:
                ray = ray[: stop[0]]
            if len(ray) < 2:
                raise ValueError("No contiguous support at radial origin")
            curves.append(ray)
    return curves


def extract(job, src, out):
    with av.open(str(src)) as video:
        frames = [f.to_ndarray(format="rgb24") for f in video.decode(video=0)]
    source_w, source_h = job["dimensions"]
    w, h = source_w, source_h
    if len(frames) != job["frames"] or frames[0].shape[:2] != (h, w):
        raise ValueError("Unexpected source format")
    if "crop_xywh" in job:
        x, y, w, h = job["crop_xywh"]
        assert 0 <= x < x + w <= source_w and 0 <= y < y + h <= source_h
        frames = [f[y : y + h, x : x + w].copy() for f in frames]
    stack = np.stack([signal(f, job["role"], job.get("channel")) for f in frames])
    curves = geometry(job, stack)
    n = max(map(len, curves))
    references = None
    if "final_tail_reference" in job:
        from aulehla_reference import registered_strips

        references, n = registered_strips(job, frames, curves)
        curves = [record["line"] for record in references]
    values = np.full((n, len(frames)), np.nan)
    overlays = []
    for i, (im, line) in enumerate(zip(stack, curves)):
        tangent = np.gradient(line, axis=0)
        normal = tangent[:, ::-1] * [-1, 1] / np.linalg.norm(tangent, axis=1)[:, None]
        coords = line[:, None, :] + normal[:, None, :] * np.arange(-6, 7)[None, :, None]
        start = references[i]["start"] if references else 0
        values[start : start + len(line), i] = map_coordinates(
            im,
            [coords[:, :, 1], coords[:, :, 0]],
            order=1,
            mode="constant",
            cval=np.nan,
        ).mean(axis=1)
        edge = np.concatenate([coords[:, 0], coords[::-1, -1]])
        overlays.append(
            dict(
                index=i, lines=[line.round(4).tolist()], bands=[edge.round(4).tolist()]
            )
        )
        if references:
            overlays[-1].update(
                {key: value for key, value in references[i].items() if key != "line"}
            )
    np.savez_compressed(
        out / "kymograph.npz",
        intensity=values,
        time_h=job["time_h"],
        space_um=np.arange(n) * job.get("bar_um", 200) / job["bar_pixels"],
    )
    video_path = out / "playback.mp4"
    if job["role"] == "radial":
        import shutil

        shutil.copyfile(src, video_path)
    else:
        with av.open(str(video_path), "w", options={"movflags": "faststart"}) as dst:
            stream = dst.add_stream("libx264", rate=10)
            stream.width = w + (w % 2)
            stream.height = h
            stream.pix_fmt = "yuv420p"
            for rgb in frames:
                arr = np.pad(rgb, ((0, 0), (0, w % 2), (0, 0)), mode="edge")
                for packet in stream.encode(
                    av.VideoFrame.from_ndarray(arr, format="rgb24")
                ):
                    dst.mux(packet)
            for packet in stream.encode():
                dst.mux(packet)
    with av.open(str(video_path)) as video:
        starts = [float(f.time) for f in video.decode(video=0)]
    Image.fromarray(frames[0]).save(out / "poster.jpg", quality=90)
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.5))
    for ax, i in zip(axes, [0, len(frames) // 2, len(frames) - 1]):
        ax.imshow(frames[i])
        ax.axis("off")
        band = np.array(overlays[i]["bands"][0])
        ax.plot(*np.vstack([band, band[:1]]).T, c="#ffa943", lw=1)
        line = curves[i]
        ax.plot(*line.T, c="#ffa943", lw=0.75)
        labels = ("P", "A") if job["role"] == "axial" else ("O", "E")
        for guide in overlays[i].get("guide_lines", []):
            ax.plot(*np.asarray(guide).T, color="#ffa943", lw=1.2, linestyle="--")
        endpoints = overlays[i].get("reference_points", [line[0], line[-1]])
        for pt, label in zip(endpoints, labels):
            if references:
                ax.plot(*pt, "o", ms=3, color="white")
            ax.text(*pt, label, color="white", size=9, backgroundcolor="#443628")
        ax.set_title(f"Frame {i} · {job['time_h'][i]:.2f} h", fontsize=11)
    fig.tight_layout()
    fig.savefig(out / "roi.png", dpi=140)
    plt.close(fig)
    times = np.array(job["time_h"])
    mids = (times[:-1] + times[1:]) / 2
    edges = np.r_[
        times[0] - (mids[0] - times[0]), mids, times[-1] + (times[-1] - mids[-1])
    ]
    vmin, vmax = np.nanmin(values), np.nanmax(values)
    normalized = (values - vmin) / (vmax - vmin)
    fig, ax = plt.subplots(figsize=(5.8, 4.3))
    cmap = plt.get_cmap("OrRd").copy()
    cmap.set_bad("#eff1f4")
    mesh = ax.pcolormesh(
        edges,
        (np.arange(n + 1) - 0.5) * job.get("bar_um", 200) / job["bar_pixels"],
        normalized,
        cmap=cmap,
        vmin=0,
        vmax=1,
        rasterized=True,
    )
    ax.set(
        xlim=(times[0], times[-1]),
        ylim=(0, (n - 1) * job.get("bar_um", 200) / job["bar_pixels"]),
        xlabel="Time (h)",
        ylabel="Distance from "
        + (
            "final-frame P tip"
            if references
            else "P-side ROI"
            if job["role"] == "axial"
            else "fitted center"
        )
        + " (approx. µm)",
    )
    fig.colorbar(mesh, ax=ax, label="Relative display intensity")
    fig.tight_layout()
    fig.savefig(out / "plot.png", dpi=165)
    fig.savefig(out / "plot.svg")
    plt.close(fig)
    return overlays, starts

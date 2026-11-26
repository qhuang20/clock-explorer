# SPDX-License-Identifier: MIT
"""Miao Movie 2 early Somitoid. Use the geometric centroid and image-right ray."""

import hashlib
import json
from pathlib import Path

import av
import contourpy
import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter

from extract_miao_video import invert
from paths import ASSET_ROOT

DATA = ASSET_ROOT / "data/derived/miao-2023-radius"
FIG = ASSET_ROOT / "figures/miao-2023"
MOVIE = ASSET_ROOT / "videos/miao-2023/movie-2.mp4"
LUT = ASSET_ROOT / "data/derived/miao-2023/green-fire-blue.lut"
N = 52
SCALE = 200 / 115
SIGMA = 3
SAMPLE_FRAMES = (0, 26, 51)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(rgb, palette):
    blurred_outline = cv2.GaussianBlur(rgb.max(2), (0, 0), 4)
    contours, _ = cv2.findContours(
        (blurred_outline >= 22).astype("uint8"),
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    mask = np.zeros(rgb.shape[:2], np.uint8)
    cv2.drawContours(mask, [max(contours, key=cv2.contourArea)], 0, 1, -1)
    m = cv2.moments(mask, binaryImage=True)
    cx, cy = np.rint([m["m10"] / m["m00"], m["m01"] / m["m00"]]).astype(int)
    assert mask[cy, cx]
    outside = np.flatnonzero(mask[cy, cx:] == 0)
    end = cx + outside[0] - 1 if outside.size else mask.shape[1] - 1

    # Decode a halo at least as large as the truncated Gaussian kernel.
    halo = 3 * SIGMA
    x0, x1 = max(0, cx - halo), min(mask.shape[1], end + halo + 1)
    y0, y1 = max(0, cy - 20 - halo), min(mask.shape[0], cy + 20 + halo)
    idx, err = invert(rgb[y0:y1, x0:x1], palette)
    inside = mask[y0:y1, x0:x1].astype(bool)
    valid = inside & (err <= 30)
    weights = gaussian_filter(valid.astype(np.float32), SIGMA, truncate=3)
    sums = gaussian_filter(
        np.where(valid, idx, 0).astype(np.float32), SIGMA, truncate=3
    )
    filtered = np.divide(sums, weights, out=np.zeros_like(sums), where=weights > 0)

    sl = np.s_[cy - 20 - y0 : cy + 20 - y0, cx - x0 : end + 1 - x0]
    footprint = inside[sl]
    accepted = valid[sl]
    counts = accepted.sum(0)
    profiles = [
        np.divide(
            np.where(accepted, data[sl], 0).sum(0, dtype=float),
            counts,
            out=np.full(len(counts), np.nan),
            where=counts >= 20,
        )
        for data in (idx, filtered)
    ]
    outlines = contourpy.contour_generator(
        x=np.arange(cx - 1, end + 2),
        y=np.arange(cy - 21, cy + 21),
        z=np.pad(footprint, 1),
    ).lines(0.5)
    assert len(outlines) == 1
    return (cx, cy), (end, cy), outlines[0], counts, profiles


def run():
    DATA.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    assert (
        digest(MOVIE)
        == "6689c3c9d6ffc22b935d4046d19d7b26e832c9b267b3a6ea96f90e7530f342d3"
    )
    assert (
        digest(LUT)
        == "01f17d9e55cd3bf2f2e8af1bf4261ea392d88ed0316a5acb9375a44c21ea0f3e"
    )
    palette = (
        np.frombuffer(LUT.read_bytes(), np.uint8).reshape(3, 256).T.astype(np.float32)
    )
    time = 50.5 + np.arange(N) * 15.78 / 60
    records = []
    fig, axes = plt.subplots(1, 3, figsize=(10.8, 3.7), layout="constrained")
    with av.open(str(MOVIE)) as movie:
        for i, frame in zip(range(N), movie.decode(video=0)):
            rgb = frame.to_ndarray(format="rgb24")
            record = measure(rgb, palette)
            records.append(record)
            if i in SAMPLE_FRAMES:
                ax = axes[SAMPLE_FRAMES.index(i)]
                origin, edge, outline = record[:3]
                ax.imshow(rgb)
                ax.plot(*outline.T, color="#ffad46", lw=1.4)
                ax.plot(*np.array([origin, edge]).T, "o-", color="#ffad46", ms=3, lw=1)
                for pt, label in [(origin, "O"), (edge, "E")]:
                    ax.annotate(
                        label,
                        pt,
                        xytext=(0, 6),
                        textcoords="offset points",
                        ha="center",
                        color="white",
                        bbox=dict(facecolor="#161922", edgecolor="none", pad=1),
                    )
                ax.set(
                    xlim=(323, 958),
                    ylim=(647, 36),
                    title=f"Frame {i} · {time[i]:.2f} h",
                )
                ax.axis("off")
    assert len(records) == N
    fig.savefig(FIG / "right-radius-roi.png", dpi=150)
    plt.close(fig)
    bins = max(len(row[3]) for row in records)
    matrix = np.full((bins, N), np.nan)
    smooth = matrix.copy()
    counts = np.zeros((bins, N), np.uint8)
    for i, (_, _, _, count, (raw, flt)) in enumerate(records):
        n = len(count)
        matrix[:n, i], smooth[:n, i], counts[:n, i] = raw, flt, count
    assert np.array_equal(np.isfinite(matrix), counts >= 20)
    assert np.array_equal(np.isfinite(matrix), np.isfinite(smooth))
    positions = np.arange(bins) * SCALE
    lines = [row[2] for row in records]
    path = DATA / "kymograph.npz"
    np.savez_compressed(
        path,
        intensity=matrix,
        frame_smoothed=smooth,
        time_h=time,
        position_um=positions,
        frame_index=np.arange(N),
        origin_xy=[r[0] for r in records],
        edge_xy=[r[1] for r in records],
        outline_xy=np.concatenate(lines),
        outline_offsets=np.r_[0, np.cumsum([len(l) for l in lines])],
        accepted_pixel_count=counts,
        strip_width_px=40,
        sigma_xy_px=SIGMA,
    )
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True, layout="constrained")
    cmap = plt.get_cmap("OrRd").copy()
    cmap.set_bad("#f1f3f6")
    low, high = np.nanmin(matrix), np.nanmax(matrix)
    for ax, data, title in zip(
        axes,
        (matrix, smooth),
        ("Unsmoothed radius", "Frame-smoothed radius · σ = 3 px"),
    ):
        mesh = ax.pcolormesh(
            time - time[0],
            positions,
            (data - low) / (high - low),
            shading="nearest",
            cmap=cmap,
            vmin=0,
            vmax=1,
            rasterized=True,
        )
        ax.set(
            xlabel="Time from first sampled frame (h)",
            title=title,
            ylim=(0, positions[-1]),
        )
    axes[0].set_ylabel("Radius from geometric center (approx. µm)")
    fig.colorbar(mesh, ax=axes, label="Relative color index", fraction=0.025)
    fig.savefig(FIG / "right-radius-frame-comparison.png", dpi=160)
    plt.close(fig)
    record = dict(
        dataset="miao-2023",
        video="Movie 2",
        movie_sha256=digest(MOVIE),
        lut_sha256=digest(LUT),
        input_sha256=digest(path),
        source="https://doi.org/10.1038/s41586-022-05655-4",
        interval_minutes=15.78,
        differentiation_hours=[time[0], time[-1]],
        frames_used=[0, 51],
        scale_um_per_px=SCALE,
        origin="Centroid of the filled largest visible composite outline. Outline from maximum RGB, Gaussian sigma 4 px, threshold 22/255.",
        path="Horizontal image-right ray from that frame's centroid to its first tissue exit. O and E indicate geometry. Independent one-sided reconstruction of the center scan.",
        intensity="Nearest Green Fire Blue display-color index. Mean of valid pixels across 40 rows within the tissue outline, RGB residual at most 30; at least 20 accepted pixels per bin.",
        control="Per-frame mask-normalized two-dimensional Gaussian, sigma 3 px, truncated at 3 sigma, before averaging. Same acceptance mask and geometry. No temporal filtering.",
        limit="HES7-dominant early pseudocolor, possible MESP2 admixture and selective loss of bright pixels. Optical and anatomical wave origins are unresolved.",
        script="analysis/extract_miao_radius.py",
        script_sha256=digest(Path(__file__)),
    )
    (DATA / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    run()

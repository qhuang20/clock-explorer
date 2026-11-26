# SPDX-License-Identifier: MIT
"""Measure the whole somitoid in every Sanaki Movie 4 frame in centroid-based axial bins."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial import cKDTree
from paths import ASSET_ROOT
from comparison_plot import plt, panel, save

DATA = Path("data/derived/sanaki-2022-whole")
FIG = Path("figures/sanaki-2022")
SOURCE = "data/source-archive/sanaki-2022/41467_2022_29967_MOESM9_ESM.mp4"
CHECK = [0, 103, 104, 249, 250, 361]


def structure(frame):
    bf = cv2.cvtColor(frame[:, :486], cv2.COLOR_BGR2GRAY)
    # Linked panels are aligned. Above the old crop recover BF contrast from
    # the red plane of the merged image, where no green reporter is added.
    bf[:75] = frame[:75, 486:972, 2]
    # Decimated background blur avoids broad lamp gradients at the left edge.
    small = cv2.resize(bf, (122, 122), interpolation=cv2.INTER_AREA)
    bg = cv2.resize(cv2.GaussianBlur(small, (0, 0), 10), (486, 486)).astype(float)
    mask = ((bg - bf) > 0.12 * np.maximum(bg, 1)).astype("uint8")
    mask[:, :38] = 0
    mask = cv2.morphologyEx(
        mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour = max(contours, key=cv2.contourArea)
    mask[:] = 0
    cv2.drawContours(mask, [contour], 0, 1, -1)
    # Faint anterior somites have less relative contrast than the posterior
    # body. Grow the connected anterior envelope locally from the strong mask.
    ys = np.where(mask)[0]
    near = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (39, 39)))
    low = (near.astype(bool) & ((bg - bf) > 0.055 * np.maximum(bg, 1))).astype("uint8")
    low[int(np.percentile(ys, 45)) :] = 0
    joined = cv2.morphologyEx(
        mask | low,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
    )
    contours, _ = cv2.findContours(joined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour = max(contours, key=cv2.contourArea)
    mask[:] = 0
    cv2.drawContours(mask, [contour], 0, 1, -1)
    return bf, mask, contour


def run(output):
    target = output / DATA
    target.mkdir(parents=True, exist_ok=True)
    (output / FIG).mkdir(parents=True, exist_ok=True)
    source = ASSET_ROOT / SOURCE
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest == "852915ad75bb83a1504914932f0467dd53a0f5fdfd4e50baeafa297961599add"
    with (
        ASSET_ROOT / "data/derived/sanaki-2022-full/frame-times.csv"
    ).open() as stream:
        times = np.array([float(row["time_h"]) for row in csv.DictReader(stream)])
    lut = (
        np.frombuffer(
            (ASSET_ROOT / "data/derived/sanaki-2022/fire.lut").read_bytes(), np.uint8
        )
        .reshape(3, 256)
        .T
    )
    colors, first_indices = np.unique(lut, axis=0, return_index=True)
    tree = cKDTree(colors)
    cap = cv2.VideoCapture(str(source))
    profiles, counts, centers, axes, polys, qc = [], [], [], [], [], []
    shots = []
    for i, t in enumerate(times):
        ok, frame = cap.read()
        assert ok
        bf, mask, contour = structure(frame)
        y, x = np.where(mask)
        xy = np.c_[x, y]
        center = xy.mean(0)
        axis = np.linalg.eigh(np.cov(xy.T))[1][:, -1]
        if axis[1] > 0:
            axis = -axis
        bins = np.floor(((xy - center) @ axis) / 2).astype(int)
        err, nearest = tree.query(frame[y, x + 972, ::-1])
        good = err <= 30
        start = bins.min()
        n = np.bincount(bins[good] - start, minlength=np.ptp(bins) + 1)
        sums = np.bincount(
            bins[good] - start, weights=first_indices[nearest[good]], minlength=len(n)
        )
        mean = np.divide(sums, n, out=np.full(len(n), np.nan), where=n >= 3)
        profiles.append((start, mean))
        counts.append(n)
        centers.append(center)
        axes.append(axis)
        polys.append(contour[:, 0, :])
        recovered = y < 65
        qc.append(
            dict(
                frame=i,
                time_h=float(t),
                area=len(y),
                accepted=int(good.sum()),
                top_y=int(y.min()),
                above_old_crop=int(recovered.sum()),
                included_above_old_crop=int(
                    (recovered & good & (n[bins - start] >= 3)).sum()
                ),
            )
        )
        if i in CHECK:
            shots.append((i, bf, mask, frame[:, 972:, ::-1], contour))
    assert len(times) == 362 and not cap.read()[0]
    cap.release()
    low = min(start for start, _ in profiles)
    high = max(start + len(p) for start, p in profiles)
    matrix = np.full((high - low, len(times)), np.nan, dtype=np.float32)
    count = np.zeros(matrix.shape, dtype=np.uint32)
    for i, (start, p) in enumerate(profiles):
        sl = slice(start - low, start - low + len(p))
        matrix[sl, i] = p
        count[sl, i] = counts[i]
    pos = 2 * np.arange(low, high) + 1
    np.savez_compressed(
        target / "kymograph.npz",
        intensity=matrix,
        valid_counts=count,
        time_h=times,
        frame_index=np.arange(len(times)),
        position_px=pos,
        centers_xy=centers,
        axis_vectors_xy=axes,
        contour_xy=np.concatenate(polys),
        contour_offsets=np.r_[0, np.cumsum(list(map(len, polys)))],
    )
    info = dict(
        source=SOURCE,
        source_sha256=digest,
        source_frames=len(times),
        used_frames=len(times),
        time_range_h=times[[0, -1]].tolist(),
        time_basis="Movie clock labels, including 5 and 3 minute steps at frame 104 and 250.",
        method="Brightfield relative dark contrast >0.12 on a 486 px panel. Above y=75 use the aligned red plane of the merged panel to avoid the printed clock. Recover adjacent anterior tissue at >0.055 relative dark contrast within 19 px of the strong envelope. Fill largest connected outline. Per-frame centroid and upward-oriented principal axis, signed 2 px projection bins across the whole silhouette.",
        intensity="Mean nearest inferred Fire LUT index in each bin for RGB residual <=30 and at least three accepted pixels. Complete matrix finite min/max for display. No time interpolation.",
        geometry="Source contour pixels, panel-local x/y. Reporter x-offset 972 px. A positive projection points toward the anterior region; zero is the frame's centroid.",
        limitations="Rendered HES7 promoter-luciferase color index, approximate silhouette, uncalibrated spatial pixels; centroid shifts and curvature affect slopes.",
        frames=qc,
    )
    (target / "provenance.json").write_text(json.dumps(info, indent=2) + "\n")
    item = dict(
        matrix=matrix,
        time=times,
        position=pos,
        position_unit="video px",
        position_increases_up=True,
        native_space_only=True,
        axis_label="Projection from tissue centroid (px)",
        signal_label="Relative color index",
    )
    for window in ["full", "common"]:
        fig, ax = plt.subplots(figsize=(5.2, 4.3), layout="constrained")
        panel(fig, ax, item, window)
        save(fig, output / "figures/comparison" / ("sanaki-2022-" + window))
    fig, axs = plt.subplots(2, 3, figsize=(12, 6.4), layout="constrained")
    for ax, (i, bf, mask, rep, contour) in zip(axs.flat, shots):
        ys, xs = np.where(mask)
        x0, x1 = xs.min() - 15, xs.max() + 16
        y0, y1 = ys.min() - 12, ys.max() + 13
        left = bf[y0:y1, x0:x1]
        right = rep[y0:y1, x0:x1].copy()
        bg = np.repeat(left[:, :, None], 3, axis=2)
        pts = contour - [x0, y0]
        for im in [bg, right]:
            cv2.polylines(
                im, [pts.astype("int32")], True, (255, 170, 65), 1, cv2.LINE_AA
            )
        ax.imshow(np.concatenate([bg, right], axis=1))
        ax.axis("off")
        ax.set_title(f"Frame {i} · {times[i]:.2f} h")
    fig.suptitle(
        "Whole-tissue sampling ROI · structural image and HES7 reporter", fontsize=14
    )
    fig.savefig(output / FIG / "whole-roi.png", dpi=145)
    plt.close(fig)
    print("All frames", matrix.shape, "last frame", qc[-1])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ASSET_ROOT)
    run(parser.parse_args().output)

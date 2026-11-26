# SPDX-License-Identifier: MIT
"""Extend the saved Movie S2 ray to a reviewed full-width outer envelope."""

import json

import av
import cv2
import numpy as np
from scipy import ndimage as ndi

from audit_sonnen_movie_s2 import MOVIE_SHA, START, END, WIDTH, UM_PER_PX
from extract_sonnen_additional import digest
from paths import ASSET_ROOT
from verify_sonnen_candidates import strip_profile

REVIEW = "s2-extended-ray-review"
THRESHOLDS = [25, 35, 45]


def envelope(image, threshold):
    binary = (ndi.gaussian_filter(image.astype(float), 8) > threshold).astype(np.uint8)
    binary[:70] = 0
    binary[-45:] = 0
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary)
    if n < 2:
        raise ValueError("No supported culture envelope")
    component = (labels == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    filled = np.zeros_like(binary)
    cv2.drawContours(filled, [max(contours, key=cv2.contourArea)], -1, 1, cv2.FILLED)
    return ndi.distance_transform_edt(filled) > 5


def run():
    movie = ASSET_ROOT / "data/source-archive/sonnen-2018/mmc3.mp4"
    reference = ASSET_ROOT / "data/derived/sonnen-2018/movie-s2-kymograph.npz"
    if digest(movie) != MOVIE_SHA:
        raise ValueError("Unexpected Movie S2 source")
    with av.open(str(movie)) as c:
        frames = [f.to_ndarray(format="rgb24") for f in c.decode(video=0)]
    with np.load(reference) as old:
        baseline, times, previous_distances, shifts = [
            old[k] for k in ["intensity", "time_h", "position_um", "shifts_xy"]
        ]
    # Preserve the original grid spacing, origin, direction and 41 width samples.
    step = previous_distances[1] - previous_distances[0]
    distance = np.arange(int(np.ceil(500 / step)) + 1) * step
    direction = (END - START) / np.linalg.norm(END - START)
    normal = np.array([-direction[1], direction[0]])
    paths = START + shifts[:, None, :] + distance[None, :, None] / UM_PER_PX * direction
    offsets = np.arange(-WIDTH // 2, WIDTH // 2 + 1)
    matrix = np.full((len(distance), len(frames)), np.nan)
    width_counts, alternatives = [], []
    for i, (frame, path) in enumerate(zip(frames, paths)):
        raw, count = strip_profile(frame[:, :, 1], path, normal, offsets)
        np.testing.assert_allclose(
            raw[: len(previous_distances)], baseline[:, i], atol=2e-10, rtol=0
        )
        xy = path[:, None, :] + normal * offsets[None, :, None]
        extents = []
        for threshold in THRESHOLDS:
            support = envelope(frame[:, :, 1], threshold)
            inside = (
                ndi.map_coordinates(
                    support.astype(float),
                    [xy[..., 1], xy[..., 0]],
                    order=1,
                    mode="constant",
                    cval=0,
                )
                >= 1 - 1e-8
            )
            good = inside.all(axis=1) & np.isfinite(raw)
            # Preserve the original measured interval, then require contiguous new support.
            good[: len(previous_distances)] = True
            keep = np.logical_and.accumulate(good)
            extents.append(int(keep.sum()))
        # The highest threshold supplies the conservative new extension.
        stop = min(extents)
        matrix[:stop, i] = raw[:stop]
        width_counts.append(count)
        alternatives.append(extents)
    np.testing.assert_allclose(
        matrix[: len(previous_distances)], baseline, atol=2e-10, rtol=0
    )
    matrix[: len(previous_distances)] = baseline
    stop = np.flatnonzero(np.isfinite(matrix).any(axis=1))[-1] + 1
    matrix, distance, paths = matrix[:stop], distance[:stop], paths[:, :stop]
    width_counts = np.array(width_counts)[:, :stop]
    valid = np.isfinite(matrix)
    data = ASSET_ROOT / "data/derived/sonnen-2018" / REVIEW
    figures = ASSET_ROOT / "figures/sonnen-2018" / REVIEW
    data.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        data / "kymograph.npz",
        intensity=matrix,
        time_h=times,
        position_um=distance,
        shifts_xy=shifts,
        frame_index=np.arange(len(frames)),
        path_xy=paths,
        direction_xy=direction,
        strip_width_px=WIDTH,
        um_per_px=UM_PER_PX,
        valid=valid,
        fov_width_counts=width_counts.T,
        envelope_extent_samples=np.array(alternatives),
        baseline_intensity=baseline,
    )
    record = {
        "analysis_script": "analysis/review_sonnen_s2_extended.py",
        "analysis_script_sha256": digest(__file__),
        "source_file": "data/source-archive/sonnen-2018/mmc3.mp4",
        "frame_count": len(frames),
        "time_range_h": times[[0, -1]].tolist(),
        "distance_range_um": distance[[0, -1]].tolist(),
        "dataset_id": "sonnen-2018",
        "source_sha256": digest(movie),
        "reference_sha256": digest(reference),
        "matrix_sha256": digest(data / "kymograph.npz"),
        "method": "Extend the original translated ray, preserving its origin, direction, width, timestamps and existing354 rows. Newly measured rows require all 41 transverse samples within the contiguous outer envelope with a 5 px margin.",
        "thresholds_display_units": THRESHOLDS,
        "geometry_gaussian_sigma_px": 8,
        "extension_threshold_rule": "Use the shortest fully supported extent across all three thresholds.",
        "approx_um_per_px": UM_PER_PX,
        "strip_width_px": WIDTH,
        "width_samples": 41,
        "old_extent_um": float(previous_distances[-1]),
        "last_valid_distance_um": [
            float(distance[np.flatnonzero(valid[:, i])[-1]]) for i in range(len(frames))
        ],
        "threshold_extent_range_um": ((np.array(alternatives) - 1) * step).tolist(),
        "signal": "Original unfiltered decoded green display channel, bilinear interpolation and cross-strip mean.",
        "limits": "The original 354-row interval retains its FOV-only validity. The new extent uses a display-derived outer-envelope proxy. Existing origin and radial-center uncertainty remain. PSM segmentation and anatomical arrest-boundary validation remain unresolved.",
        "verified_unchanged_prefix_max_error": float(
            np.max(abs(matrix[: len(previous_distances)] - baseline))
        ),
    }
    (data / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")
    render(
        frames,
        times,
        matrix,
        distance,
        baseline,
        previous_distances,
        paths,
        normal,
        valid,
        figures,
    )
    print(
        json.dumps(
            {
                "output": str(figures),
                "first_last_valid_um": [
                    record["last_valid_distance_um"][i] for i in [0, 77, 154]
                ],
                "prefix_max_error": record["verified_unchanged_prefix_max_error"],
            }
        )
    )


def render(
    frames,
    times,
    matrix,
    distance,
    baseline,
    old_distance,
    paths,
    normal,
    valid,
    figures,
):
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    plt.rcParams.update(
        {"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none"}
    )

    def board(indices):
        fig, axes = plt.subplots(2, 3, figsize=(11, 7.8), layout="constrained")
        for ax, i in zip(axes.flat, indices):
            ax.imshow(frames[i])
            ax.set_axis_off()
            ax.set_title(f"Frame {i} · {times[i]:.2f} h")
            for path, color in [
                (paths[i, : len(old_distance)], "#76d7ee"),
                (paths[i, valid[:, i]], "#ffbb56"),
            ]:
                band = np.r_[
                    path + WIDTH / 2 * normal,
                    (path - WIDTH / 2 * normal)[::-1],
                    (path + WIDTH / 2 * normal)[:1],
                ]
                ax.plot(*band.T, color=color, lw=1)
            p = paths[i, valid[:, i]]
            ax.plot(*p.T, color="#ffbb56", lw=1)
            ax.plot(*p[0], "o", color="#ffbb56", ms=3)
        for ax in list(axes.flat)[len(indices) :]:
            ax.set_axis_off()
        fig.supxlabel(
            "Orange: extended ROI · Cyan: previous endpoint · Origin, direction and width retained",
            fontsize=11,
        )
        return fig

    fig = board([0, 30, 77, 110, 132, 154])
    fig.savefig(figures / "roi-comparison.jpg", dpi=160)
    plt.close(fig)
    with PdfPages(figures / "all-frames.pdf") as pdf:
        for start in range(0, len(frames), 6):
            fig = board(range(start, min(start + 6, len(frames))))
            pdf.savefig(fig, dpi=65)
            plt.close(fig)
    low = min(np.nanmin(baseline), np.nanmin(matrix))
    high = max(np.nanmax(baseline), np.nanmax(matrix))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7), sharey=True, layout="constrained")
    for ax, values, positions, title in zip(
        axes,
        [baseline, matrix],
        [old_distance, distance],
        ["Previous ray", "Extended ray"],
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
            xlim=(0, times[-1]),
            ylim=(0, distance[-1]),
            xlabel="Movie time (h)",
            title=title,
        )
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Distance from unchanged ROI origin (approx. µm)")
    fig.colorbar(heat, ax=axes, label="Relative display intensity", ticks=[0, 0.5, 1])
    for ext in ["svg", "png"]:
        fig.savefig(figures / f"kymograph-comparison.{ext}", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    run()

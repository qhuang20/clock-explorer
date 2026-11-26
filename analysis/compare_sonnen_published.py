# SPDX-License-Identifier: MIT
"""Compare available Sonnen sources with paper panels, preserving primaries.

This is a study adapter. A negative fluorescence/brightfield feature match does
not prove different specimens. The spatial-only filter control is not a raw-stack
or author-kymograph reproduction, and it makes no assumption about time blurring.
"""

import hashlib
import json
from pathlib import Path

import av
import cv2
import numpy as np

from audit_sonnen_movie_s2 import MOVIE_SHA, UM_PER_PX, WIDTH, sampling_geometry
from extract_sonnen_additional import sample_image
from paths import ASSET_ROOT

DATA = Path("data/derived/sonnen-2018/paper-comparison")
FIGURES = Path("figures/sonnen-2018/paper-comparison")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def supported_match(row):
    """Case-specific geometric guard, not a universal specimen-identity test."""
    return (
        row["inliers"] >= 30
        and min(row.get("span_crop_xy", [0, 0])) >= 70
        and 2 < row.get("scale_crop_to_native", 0) < 10
        and row.get("median_source_px", float("inf")) < 3
    )


def match_published_crops(frames, figure1, figure_s2):
    """Search all frames, with a known same-specimen Figure 1D positive control.

    Templates are doubled and movie frames halved for SIFT. Transform matrices
    explicitly map that doubled template into half-resolution movie coordinates.
    Red arrows, crop borders and lower scale-bar/text areas are excluded.
    """
    cv2.setNumThreads(2)
    cv2.setRNGSeed(0)
    sift = cv2.SIFT_create(nfeatures=2500, contrastThreshold=0.008, edgeThreshold=14)
    clahe = cv2.createCLAHE(clipLimit=2, tileGridSize=(8, 8))
    queries = {}
    for label, crop in [
        ("figure1d_positive_control", figure1[193:382, :187]),
        ("figure_s2a", figure_s2[50:227, 109:286]),
    ]:
        mask = np.full(crop.shape[:2], 255, np.uint8)
        b, g, r = cv2.split(crop)
        arrow = (r.astype(float) > g.astype(float) * 1.4 + 20) & (r > 120)
        mask[cv2.dilate(arrow.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0] = 0
        mask[:5] = mask[-12:] = 0
        mask[:, :5] = mask[:, -5:] = 0
        mask[-28:, -55:] = 0
        gray = clahe.apply(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))
        queries[label] = sift.detectAndCompute(
            cv2.resize(gray, None, fx=2, fy=2),
            cv2.resize(mask, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST),
        )
    matcher = cv2.BFMatcher()
    rows = {key: [] for key in queries}
    for index, frame in enumerate(frames):
        gray = cv2.resize(frame[:, :, 1], None, fx=0.5, fy=0.5)
        keys, descriptors = sift.detectAndCompute(clahe.apply(gray), None)
        for label, (qkeys, qdesc) in queries.items():
            good = (
                []
                if descriptors is None or qdesc is None
                else [
                    m
                    for m, n in matcher.knnMatch(qdesc, descriptors, k=2)
                    if m.distance < 0.72 * n.distance
                ]
            )
            row = {"frame": index, "matches": len(good), "inliers": 0}
            if len(good) >= 4:
                a = np.float32([qkeys[m.queryIdx].pt for m in good])
                b = np.float32([keys[m.trainIdx].pt for m in good])
                matrix, keep = cv2.estimateAffinePartial2D(
                    a,
                    b,
                    method=cv2.RANSAC,
                    ransacReprojThreshold=2,
                    maxIters=3000,
                    confidence=0.995,
                )
                if matrix is not None:
                    selected = keep.ravel().astype(bool)
                    errors = np.linalg.norm(
                        a @ matrix[:, :2].T + matrix[:, 2] - b, axis=1
                    )
                    row.update(
                        inliers=int(selected.sum()),
                        span_crop_xy=(np.ptp(a[selected], axis=0) / 2).tolist(),
                        median_source_px=float(np.median(errors[selected]) * 2),
                        scale_crop_to_native=float(np.linalg.norm(matrix[:, 0]) * 4),
                        matrix_template2x_to_moviehalf=matrix.tolist(),
                    )
            row["supported_geometric_match"] = supported_match(row)
            rows[label].append(row)
    best = {
        label: max(group, key=lambda row: row["inliers"])
        for label, group in rows.items()
    }
    if not best["figure1d_positive_control"]["supported_geometric_match"]:
        raise ValueError(
            "Positive control failed; no source-identity conclusion allowed"
        )
    return {
        "best": best,
        "all_frames": rows,
        "author_roi_transferred": False,
        "scope": "Feature correspondence only. A failed cross-modal match is not proof of different specimens.",
    }


def filtered_s2_profile(frame, path, normal, sigma_um=10):
    """One frame in, one profile out; no temporal inputs or tissue segmentation."""
    if not np.isfinite(sigma_um) or sigma_um <= 0:
        raise ValueError("Positive finite spatial sigma required")
    validity = np.ones(frame.shape[:2], bool)
    validity[:75] = False  # Clock and scale-bar rows, far from this saved strip.
    validity[-4:] = False
    validity[:, :4] = validity[:, -4:] = False
    return sample_image(
        frame[:, :, 1], path, normal, WIDTH, validity, sigma_um / UM_PER_PX
    )


def plot_filter_control(raw, smooth, times, positions, output):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {"font.family": "DejaVu Sans", "font.size": 9, "svg.fonttype": "none"}
    )
    low, high = (
        float(min(np.nanmin(raw), np.nanmin(smooth))),
        float(max(np.nanmax(raw), np.nanmax(smooth))),
    )
    te = np.r_[
        times[0] - np.diff(times)[0] / 2,
        (times[:-1] + times[1:]) / 2,
        times[-1] + np.diff(times)[-1] / 2,
    ]
    pe = np.r_[
        positions[0] - np.diff(positions)[0] / 2,
        (positions[:-1] + positions[1:]) / 2,
        positions[-1] + np.diff(positions)[-1] / 2,
    ]
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.9), layout="constrained")
    for ax, values, title in zip(
        axes,
        [raw, smooth],
        [
            "Retained primary · no added smoothing",
            "Same ROI · per-frame spatial Gaussian σ = 10 µm",
        ],
    ):
        im = ax.pcolormesh(
            te,
            pe,
            (values - low) / (high - low),
            cmap="OrRd",
            vmin=0,
            vmax=1,
            rasterized=True,
        )
        ax.set(
            xlim=(times[0], times[-1]),
            ylim=(positions[0], positions[-1]),
            xlabel="Movie-overlay time (h)",
            ylabel="Distance from ROI start (approx. µm)",
            title=title,
        )
        ax.spines[["top", "right"]].set_visible(False)
    fig.colorbar(
        im,
        ax=axes,
        label="Relative display intensity · shared scale",
        ticks=[0, 0.5, 1],
        shrink=0.9,
    )
    for ext in ["svg", "png", "pdf"]:
        fig.savefig(output / f"s2-spatial-control.{ext}", dpi=160)
    plt.close(fig)
    return [low, high]


def run():
    source = ASSET_ROOT / "data/source-archive/sonnen-2018"
    movie = source / "mmc3.mp4"
    primary = ASSET_ROOT / "data/derived/sonnen-2018/movie-s2-kymograph.npz"
    hashes = {
        str(p.relative_to(ASSET_ROOT)): sha(p)
        for p in [movie, primary, source / "gr1.jpg", source / "figs2.jpg"]
    }
    if sha(movie) != MOVIE_SHA:
        raise ValueError("Movie S2 source hash mismatch")
    with av.open(str(movie)) as container:
        frames = [f.to_ndarray(format="rgb24") for f in container.decode(video=0)]
    with np.load(primary) as z:
        raw, times, positions, shifts = [
            z[k].copy() for k in ["intensity", "time_h", "position_um", "shifts_xy"]
        ]
    if len(frames) != raw.shape[1] or len(frames) != 155:
        raise ValueError("Unexpected frame count")
    origins, ends, direction, distances, _ = sampling_geometry(shifts)
    paths = origins[:, None, :] + distances[None, :, None] * direction
    normal = np.array([-direction[1], direction[0]])
    smooth, counts = zip(
        *[
            filtered_s2_profile(frame, path, normal)
            for frame, path in zip(frames, paths)
        ]
    )
    smooth, counts = np.stack(smooth, axis=1), np.stack(counts, axis=1)
    if not np.all(counts == WIDTH + 1) or not np.array_equal(
        np.isfinite(raw), np.isfinite(smooth)
    ):
        raise ValueError("Filtering changed retained support")
    data, figures = ASSET_ROOT / DATA, ASSET_ROOT / FIGURES
    data.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        data / "s2-spatial-control.npz",
        intensity_baseline=raw,
        spatial_filtered=smooth,
        time_h=times,
        position_um=positions,
        path_xy=paths,
        origins_xy=origins,
        endpoints_xy=ends,
        fov_width_counts=counts,
        valid_fov_only=np.isfinite(raw),
        strip_width_px=WIDTH,
        sigma_um=10,
        sigma_px=10 / UM_PER_PX,
    )
    limits = plot_filter_control(raw, smooth, times, positions, figures)
    match = match_published_crops(
        frames,
        cv2.imread(str(source / "gr1.jpg")),
        cv2.imread(str(source / "figs2.jpg")),
    )
    (data / "figure-frame-search.json").write_text(json.dumps(match, indent=2) + "\n")
    record = {
        "dataset_id": "sonnen-2018",
        "source_movie": "Movie S2",
        "input_sha256": hashes,
        "producer_sha256": sha(__file__),
        "processing": {
            "per_frame_xy_gaussian_sigma_um": 10,
            "sigma_source_px": 10 / UM_PER_PX,
            "strip_width_source_px": WIDTH,
            "width_sample_count": 41,
            "temporal_smoothing": False,
            "post_kymograph_smoothing": False,
            "validity": "FOV/annotation-only; no tissue mask",
            "scale": "Approximate isotropic export conversion, 100 µm / 139 px",
        },
        "baseline_arrays_preserved": True,
        "time_distance_and_missingness_preserved": True,
        "normalization": {
            "shared_original_display_limits": limits,
            "scope": "Both complete arrays; no per-column scaling",
        },
        "paper_scope": "Spatial-only method control inspired by oscillation-dynamics filtering, not reproduction of Figure 2A. No raw z-stacks, exact author ROI, or specified temporal filter kernel are available.",
        "geometry_match_best": match["best"],
        "author_roi_transferred": False,
        "primary_unchanged": all(
            sha(ASSET_ROOT / rel) == digest for rel, digest in hashes.items()
        ),
    }
    if not record["primary_unchanged"]:
        raise ValueError("Primary or movie changed")
    (data / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")
    print(
        json.dumps(
            {
                "data": str(data),
                "primary_unchanged": True,
                "geometry_match_best": match["best"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run()

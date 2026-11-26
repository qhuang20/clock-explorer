# SPDX-License-Identifier: MIT
"""Compare inward ROI adjustments with the same Video 1 reference endpoints.

Review-only geometry. Reuses the saved registration and foreground proxy;
does not extract intensities, replace gallery assets, or infer PSM identity.
"""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d

from paths import ASSET_ROOT
from review_video1_stable_roi import (
    A_REF,
    P_REF,
    SCALE,
    SOURCE_HASH,
    WIDTH,
    coverage,
    digest,
    draw_panel,
    resample_path,
)


def inward_candidate(path, normals, shift_px, taper_um=120.0, direction_sigma_um=40.0):
    """Move this reviewed P→A path inward, smoothly tapering at fixed ends.

    In this specimen's path convention the left normal points into the tail.
    Smooth only the geometry's direction field to avoid offsetting tiny local
    bends into cusps. This is neither a fluorescence filter nor a medial axis.
    The requested shift is maximal in the interior and zero at both endpoints.
    """
    path = np.asarray(path, float)
    normals = np.asarray(normals, float)
    if (
        path.shape != normals.shape
        or path.ndim != 2
        or path.shape[1] != 2
        or len(path) < 5
        or not np.isfinite(path).all()
        or not np.isfinite(normals).all()
        or shift_px <= 0
        or taper_um <= 0
        or direction_sigma_um <= 0
    ):
        raise ValueError(
            "Finite paired paths and positive adjustment parameters required"
        )
    distance = (
        np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))] * SCALE
    )
    step = float(np.median(np.diff(distance)))
    if step <= 0:
        raise ValueError("Degenerate path")
    direction = gaussian_filter1d(
        normals, direction_sigma_um / step, axis=0, mode="nearest"
    )
    direction /= np.linalg.norm(direction, axis=1, keepdims=True)
    # Physical transition length; no temporal or measurement-length normalization.
    ramp = np.sin(np.pi / 2 * np.minimum(distance / taper_um, 1)) ** 2
    ramp *= np.sin(np.pi / 2 * np.minimum((distance[-1] - distance) / taper_um, 1)) ** 2
    shifted = path + shift_px * ramp[:, None] * direction
    shifted[0] = path[0]
    shifted[-1] = path[-1]
    ids = np.unique(np.r_[np.arange(0, len(path), 5), len(path) - 1])
    xy, normal, new_distance = resample_path(shifted[ids])
    return xy, normal, new_distance


def minimum_jacobian(path, normals):
    tangent = np.column_stack([normals[:, 1], -normals[:, 0]])
    angle = np.unwrap(np.arctan2(tangent[:, 1], tangent[:, 0]))
    curvature = np.diff(angle) / np.linalg.norm(np.diff(path, axis=0), axis=1)
    return float((1 - WIDTH / 2 * np.abs(curvature)).min())


def registered_image(frame, source_to_reference):
    """Pillow needs destination-to-source affine coefficients (pixel xy)."""
    from PIL import Image

    inverse = np.linalg.inv(source_to_reference)
    coefficients = tuple(inverse[:2].ravel())
    return np.array(
        Image.fromarray(np.asarray(frame)).transform(
            (737, 730),
            Image.Transform.AFFINE,
            coefficients,
            resample=Image.Resampling.BILINEAR,
            fillcolor=(0, 0, 0),
        )
    )


def run(output, baseline, cached_frames):
    import av
    from PIL import Image, ImageDraw, ImageFont

    geometry = baseline / "geometry-review.npz"
    baseline_report = baseline / "review.json"
    baseline_hash = digest(geometry)
    report = json.loads(baseline_report.read_text())
    source = (
        ASSET_ROOT / "data/source-archive/lauschke-2013" / report["source"]["filename"]
    )
    if digest(source) != SOURCE_HASH:
        raise ValueError("Unexpected original source")
    frames = np.load(cached_frames, mmap_mode="r")
    if frames.shape != (126, 730, 737, 3):
        raise ValueError("Unexpected frame cache")
    with av.open(str(source)) as container:
        for i, frame in enumerate(container.decode(video=0)):
            if i in [0, 60, 100, 101, 125]:
                np.testing.assert_array_equal(
                    frames[i], frame.to_ndarray(format="rgb24")
                )
    with np.load(geometry) as z:
        paths = z["paths_xy"]
        normals = z["normals_xy"]
        counts = z["path_counts"]
        matrices = z["source_to_reference"]
        masks = z["foreground_masks_registered"]
        times = z["time_h"]
    variants = [[], [], []]
    jacobians = [[], [], []]
    for p, n, count in zip(paths, normals, counts):
        p = p[:count]
        n = n[:count]
        distance = (
            np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))] * SCALE
        )
        for j, candidate in enumerate(
            [(p, n, distance), inward_candidate(p, n, 20), inward_candidate(p, n, 30)]
        ):
            variants[j].append(candidate)
            jacobians[j].append(minimum_jacobian(candidate[0], candidate[1]))
            np.testing.assert_allclose(candidate[0][0], P_REF, atol=1e-8)
            np.testing.assert_allclose(candidate[0][-1], A_REF, atol=1e-8)
    if min(map(min, jacobians)) <= 0:
        raise ValueError("Finite-width curve folds; reject this candidate")
    old_primary = ASSET_ROOT / report["preserved_primary"]["path"]
    primary_hash = digest(old_primary)
    output.mkdir(parents=True, exist_ok=True)
    titles = [
        "Current contour-guided ROI",
        "Inward +20 px (candidate)",
        "Inward +30 px (candidate)",
    ]
    title_font = ImageFont.load_default(size=22)
    caption_font = ImageFont.load_default(size=18)
    sheet_font = ImageFont.load_default(size=16)
    frame_ids = [0, 60, 84, 100, 101, 125]
    sheet = Image.new("RGB", (1440, 3000), "white")
    sd = ImageDraw.Draw(sheet)
    compact = Image.new("RGB", (1440, 1500), "white")
    cd = ImageDraw.Draw(compact)
    supported = [[], [], []]
    with av.open(
        str(output / "inward-roi-comparison.mp4"),
        "w",
        options={"movflags": "+faststart"},
    ) as movie:
        stream = movie.add_stream("libx264", rate=10)
        stream.width = 1920
        stream.height = 700
        stream.pix_fmt = "yuv420p"
        stream.options = {"crf": "18", "preset": "medium"}
        for i, frame in enumerate(frames):
            registered = registered_image(frame, matrices[i])
            panels = []
            for j in range(3):
                p, n, _ = variants[j][i]
                valid = coverage(p, n, masks[i])
                supported[j].append(int(valid.sum()))
                panels.append(draw_panel(registered, p, n, valid, masks[i]))
            canvas = Image.new("RGB", (1920, 700), "white")
            d = ImageDraw.Draw(canvas)
            for j, panel in enumerate(panels):
                canvas.paste(panel.resize((640, 634)), (j * 640, 38))
                d.text((j * 640 + 12, 9), titles[j], font=title_font, fill="#242833")
                d.text(
                    (j * 640 + 12, 678),
                    f"{times[i]:.2f} h | frame {i} | same fixed A/P refs",
                    font=caption_font,
                    fill="#525b6b",
                )
            for packet in stream.encode(av.VideoFrame.from_image(canvas)):
                movie.mux(packet)
            if i in frame_ids:
                row = frame_ids.index(i)
                for j, panel in enumerate(panels):
                    sheet.paste(panel.resize((480, 475)), (j * 480, row * 500 + 25))
                    sd.text(
                        (j * 480 + 8, row * 500 + 4),
                        f"{titles[j]} | {times[i]:.2f} h",
                        font=sheet_font,
                        fill="#242833",
                    )
            if i in [0, 60, 125]:
                row = [0, 60, 125].index(i)
                for j, panel in enumerate(panels):
                    compact.paste(panel.resize((480, 475)), (j * 480, row * 500 + 25))
                    cd.text(
                        (j * 480 + 8, row * 500 + 4),
                        f"{titles[j]} | {times[i]:.2f} h",
                        font=sheet_font,
                        fill="#242833",
                    )
                    panel.save(output / f"variant-{[0, 20, 30][j]}px-frame-{i}.png")
            if i == 125:
                canvas.save(output / "last-frame-comparison.jpg", quality=95)
        for packet in stream.encode():
            movie.mux(packet)
    sheet.save(output / "keyframes.jpg", quality=94)
    compact.save(output / "summary.jpg", quality=94)
    max_n = max(len(p) for variant in variants for p, _, _ in variant)
    stored_paths = np.full((3, 126, max_n, 2), np.nan)
    stored_normals = stored_paths.copy()
    path_counts = np.zeros((3, 126), int)
    for j, variant in enumerate(variants):
        for i, (p, n, _) in enumerate(variant):
            path_counts[j, i] = len(p)
            stored_paths[j, i, : len(p)] = p
            stored_normals[j, i, : len(p)] = n
    np.savez_compressed(
        output / "geometry-review.npz",
        paths_xy=stored_paths,
        normals_xy=stored_normals,
        path_counts=path_counts,
        source_to_reference=matrices,
        time_h=times,
        shifts_px=[0, 20, 30],
    )
    if digest(geometry) != baseline_hash or digest(old_primary) != primary_hash:
        raise ValueError("A preserved input changed during this review")
    record = {
        "status": "ROI placement review only; no accepted replacement or new intensity matrix",
        "source": report["source"],
        "baseline_geometry": {
            "path": str(geometry),
            "sha256": baseline_hash,
            "report_sha256": digest(baseline_report),
        },
        "reference_frame": 125,
        "A_ref_xy": A_REF.tolist(),
        "P_ref_xy": P_REF.tolist(),
        "width_px": WIDTH,
        "um_per_px": SCALE,
        "maximum_interior_shifts_px": [0, 20, 30],
        "maximum_interior_shifts_um": [0, 20 * SCALE, 30 * SCALE],
        "construction": "move along spatially smoothed inward normals; taper to zero over120um at each fixed endpoint; reparameterize by actual arc length",
        "direction_geometry_sigma_um": 40,
        "endpoint_taper_um": 120,
        "intensity_filtering": False,
        "intensity_extraction_performed": False,
        "same_registration_and_foreground_proxy_for_all_variants": True,
        "minimum_local_width_jacobians": list(map(min, jacobians)),
        "foreground_supported_rows": supported,
        "preserved_primary": {"path": str(old_primary), "sha256": primary_hash},
        "limitations": [
            "Fixed reference points are prospective sampling endpoints, not stationary anatomical tips or the same cells.",
            "Contour foreground is not validated PSM identity; moving inward can cross into a neighboring structure.",
            "Inward shifts are specimen-specific geometric review choices, not optimized for wave contrast.",
            "The original registration remains sensitive to structural-window choice (maximum disagreement about73px).",
            "Unsupported extensions remain dashed; no zero expression is assigned.",
            "Fixed endpoints do not fix the physical arc length of an evolving curved path.",
        ],
        "script_sha256": digest(__file__),
    }
    (output / "review.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "frames": 126,
                "shifts_px": [0, 20, 30],
                "minimum_width_jacobians": list(map(min, jacobians)),
                "primary_unchanged": True,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/video1-inward-roi-review")
    )
    parser.add_argument(
        "--baseline", type=Path, default=Path("outputs/video1-stabilized-roi-review")
    )
    parser.add_argument(
        "--cached-frames",
        type=Path,
        default=Path("work/lauschke-paper-method/video1-frames.npy"),
    )
    args = parser.parse_args()
    run(args.output, args.baseline, args.cached_frames)

# SPDX-License-Identifier: MIT
"""Review-only: stabilize Video 1, then compare fixed-reference ROI choices.

No gallery primary, extraction matrix or catalog is replaced. Reference P/A
points are prospective sampling endpoints, not verified anatomical endpoints.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.signal import savgol_filter

from paths import ASSET_ROOT
from curved_strip import arc_length_path, strip_coordinates

SCALE = 100 / 103
WIDTH = 20
A_REF = np.array([100.0, 300.0])
P_REF = np.array([540.0, 430.0])
SOURCE_HASH = "ead90ea0a22ae683f8bcfc3b804cbc37144274b8635e2206a0a6d985f9b94b04"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def transform(points, matrix):
    return np.asarray(points) @ matrix[:2, :2].T + matrix[:2, 2]


def rigid_fit(source, target):
    """Least-squares SE(2), excluding scaling, reflection and shear."""
    p = np.asarray(source, float)
    q = np.asarray(target, float)
    if (
        p.shape != q.shape
        or len(p) < 3
        or not np.isfinite(p).all()
        or not np.isfinite(q).all()
    ):
        raise ValueError("At least three finite paired points required")
    pc = p.mean(0)
    qc = q.mean(0)
    if np.sum((p - pc) ** 2) < 1:
        raise ValueError("Degenerate feature constellation")
    u, _, vt = np.linalg.svd((p - pc).T @ (q - qc))
    if np.linalg.det(vt.T @ u.T) < 0:
        vt[-1] *= -1
    rotation = vt.T @ u.T
    matrix = np.eye(3)
    matrix[:2, :2] = rotation
    matrix[:2, 2] = qc - rotation @ pc
    return matrix


def feature_pairs(frames, bounds):
    import cv2

    sift = cv2.SIFT_create(nfeatures=2500, contrastThreshold=0.009, edgeThreshold=14)
    mask = np.zeros(frames.shape[1:3], np.uint8)
    x0, y0, x1, y1 = bounds
    mask[y0:y1, x0:x1] = 255
    features = []
    for frame in frames:
        features.append(
            sift.detectAndCompute(frame.mean(axis=-1).astype(np.uint8), mask)
        )
    matcher = cv2.BFMatcher()
    pairs = []
    for i in range(1, len(frames)):
        k0, d0 = features[i]
        k1, d1 = features[i - 1]
        good = [
            m
            for m, n in matcher.knnMatch(d0, d1, k=2)
            if m.distance < 0.72 * n.distance
        ]
        p = np.array([k0[m.queryIdx].pt for m in good], float)
        q = np.array([k1[m.trainIdx].pt for m in good], float)
        if len(p) < 6:
            raise ValueError(f"Too few feature matches at frame {i}")
        _, keep = cv2.estimateAffinePartial2D(
            p,
            q,
            method=cv2.RANSAC,
            ransacReprojThreshold=2.5,
            maxIters=4000,
            confidence=0.999,
        )
        if keep is None:
            raise ValueError(f"RANSAC failed at frame {i}")
        keep = keep.ravel() > 0
        rigid = rigid_fit(p[keep], q[keep])
        residual = np.linalg.norm(transform(p, rigid) - q, axis=1)
        keep = residual < 3
        rigid = rigid_fit(p[keep], q[keep])
        error = np.linalg.norm(transform(p[keep], rigid) - q[keep], axis=1)
        pairs.append(
            (
                rigid,
                {
                    "frame": i,
                    "matches": len(good),
                    "inliers": int(keep.sum()),
                    "fit_rmse_px": float(np.sqrt(np.mean(error**2))),
                    "inlier_bbox_span_px": np.ptp(p[keep], axis=0).tolist(),
                    "rotation_deg": float(
                        np.rad2deg(np.arctan2(rigid[1, 0], rigid[0, 0]))
                    ),
                    "translation_xy_px": rigid[:2, 2].tolist(),
                },
            )
        )
    return pairs


def registration(frames):
    import cv2

    cv2.setNumThreads(2)
    cv2.setRNGSeed(13)
    proximal = feature_pairs(frames, [20, 20, 290, 390])
    broad = feature_pairs(frames, [20, 20, 350, 600])
    matrices = [np.eye(3)]
    broad_matrices = [np.eye(3)]
    rows = []
    for (m, row), (bm, brow) in zip(proximal, broad):
        fallback = row["inliers"] < 12
        if fallback:
            m = bm
            row = dict(brow)
        if row["inliers"] < 12 or row["fit_rmse_px"] > 3:
            raise ValueError(
                f"Registration needs manual review at frame {row['frame']}"
            )
        row = {
            **row,
            "region": "broader structural window"
            if fallback
            else "proximal structural window",
            "used_fallback": fallback,
        }
        rows.append(row)
        matrices.append(matrices[-1] @ m)
        broad_matrices.append(broad_matrices[-1] @ bm)
    matrices = np.array(matrices)
    broad_matrices = np.array(broad_matrices)
    # Each transform maps original source pixels into frame 125 coordinates.
    to_ref = np.linalg.inv(matrices[-1])[None] @ matrices
    alternative = np.linalg.inv(broad_matrices[-1])[None] @ broad_matrices
    return to_ref, alternative, rows


def foreground(frame, threshold=4.5):
    """Conservative display-foreground proxy; not a PSM segmentation."""
    gray = frame.mean(axis=-1).astype(float)
    variance = ndi.uniform_filter(gray * gray, 11) - ndi.uniform_filter(gray, 11) ** 2
    texture = ndi.gaussian_filter(np.sqrt(np.maximum(variance, 0)), 3)
    mask = texture > threshold
    mask[:12] = False
    mask[-65:] = False
    mask[:, :12] = False
    mask[:, 660:] = False
    mask = ndi.binary_closing(mask, iterations=5)
    labels, _ = ndi.label(mask)
    counts = np.bincount(labels.ravel())
    counts[0] = 0
    return ndi.binary_fill_holes(labels == counts.argmax())


def contour_controls(mask, a_ref=A_REF, p_ref=P_REF, offset=45.0):
    """PSM-side path follows the inward lower flank; endpoints stay fixed.

    This is a contour-guided candidate, not the whole-tail medial axis. A fixed
    nominal inward offset is chosen geometrically, not by wave contrast.
    """
    columns = []
    lower = []
    for x in range(55, min(mask.shape[1] - 1, 610)):
        y = np.flatnonzero(mask[:, x])
        if len(y) >= 30 and y[-1] - y[0] >= 40:
            columns.append(x)
            lower.append(y[-1])
    x = np.array(columns, float)
    y = np.array(lower, float)
    if len(x) < 70:
        raise ValueError("Insufficient lower-flank coverage")
    # Exclude the sharp distal silhouette turn from the offset construction.
    keep = x <= x.max() - 30
    x = x[keep]
    y = y[keep]
    y = savgol_filter(y, 51, 3)
    slope = np.gradient(y, x)
    normal = np.column_stack([slope, -np.ones(len(x))])
    normal /= np.linalg.norm(normal, axis=1, keepdims=True)
    inner = np.column_stack([x, y]) + offset * normal
    keep = (inner[:, 0] > a_ref[0] + 25) & (inner[:, 0] < p_ref[0] - 20)
    inner = inner[keep][::12]
    if len(inner) < 5:
        raise ValueError("Insufficient PSM-side candidate path")
    points = [p_ref]
    for point in inner[::-1]:
        if np.linalg.norm(point - points[-1]) >= 6:
            points.append(point)
    points.append(a_ref)
    return np.array(points)


def resample_path(controls):
    _, _, length = arc_length_path(controls, np.array([0.0]), SCALE)
    distance = np.r_[np.arange(0, length, 2.0), length]
    path, normal, _ = arc_length_path(controls, distance, SCALE)
    return path, normal, distance


def coverage(path, normal, mask):
    coords = strip_coordinates(path, normal, WIDTH)
    counts = ndi.map_coordinates(
        mask.astype(np.uint8),
        [coords[..., 1], coords[..., 0]],
        order=0,
        mode="constant",
        cval=0,
    ).sum(axis=1)
    return counts >= 16


def segments(mask):
    delta = np.diff(np.r_[False, mask, False].astype(int))
    return zip(np.flatnonzero(delta == 1), np.flatnonzero(delta == -1))


def draw_panel(frame, path, normals, valid, mask=None, labels=("P_ref", "A_ref")):
    """Draw only the candidate measurement region as solid; outside is dashed."""
    from PIL import Image, ImageDraw, ImageFont

    im = Image.fromarray(np.asarray(frame, np.uint8))
    draw = ImageDraw.Draw(im)
    if mask is not None:
        edge = mask ^ ndi.binary_erosion(mask)
        canvas = np.array(im)
        canvas[edge] = [75, 196, 208]
        im = Image.fromarray(canvas)
        draw = ImageDraw.Draw(im)
    xy = strip_coordinates(path, normals, WIDTH)
    for start, stop in segments(valid):
        if stop - start < 2:
            continue
        band = np.vstack([xy[start:stop, 0], xy[start:stop, -1][::-1]])
        fill = Image.new("RGBA", im.size, (0, 0, 0, 0))
        fd = ImageDraw.Draw(fill)
        fd.polygon([tuple(p) for p in band], fill=(255, 180, 92, 38))
        im = Image.alpha_composite(im.convert("RGBA"), fill).convert("RGB")
        draw = ImageDraw.Draw(im)
        for side in [0, -1]:
            draw.line([tuple(p) for p in xy[start:stop, side]], fill="#ffb45c", width=2)
        draw.line([tuple(p) for p in path[start:stop]], fill="#ffb45c", width=2)
    for j in range(0, len(path) - 2, 5):
        if not valid[j]:
            draw.line(
                [tuple(path[j]), tuple(path[min(j + 2, len(path) - 1)])],
                fill="#a9a2ca",
                width=2,
            )
    for point, label in [(path[0], labels[0]), (path[-1], labels[1])]:
        x, y = point
        draw.ellipse((x - 4, y - 4, x + 4, y + 4), outline="white", width=2)
        font = ImageFont.load_default(size=18)
        xytext = (x + 10, y - 24)
        box = draw.textbbox(xytext, label, font=font)
        draw.rectangle((box[0] - 3, box[1] - 3, box[2] + 3, box[3] + 3), fill="black")
        draw.text(xytext, label, font=font, fill="white")
    return im


def run(output, source, cached_frames=None):
    if digest(source) != SOURCE_HASH:
        raise ValueError("Unexpected original Video 1")
    if cached_frames is None:
        import av

        with av.open(str(source)) as container:
            frames = np.array(
                [f.to_ndarray(format="rgb24") for f in container.decode(video=0)]
            )
    else:
        frames = np.load(cached_frames, mmap_mode="r")
        # A cache is only a decoding convenience, never a substitute source.
        import av

        with av.open(str(source)) as container:
            for i, f in enumerate(container.decode(video=0)):
                if i in [0, 60, 100, 101, 125]:
                    np.testing.assert_array_equal(
                        frames[i], f.to_ndarray(format="rgb24")
                    )
    if frames.shape != (126, 730, 737, 3):
        raise ValueError("Unexpected source dimensions")
    import cv2

    to_ref, alternative, quality = registration(frames)
    original_masks = np.array([foreground(frame) for frame in frames])
    registered_masks = np.array(
        [
            cv2.warpAffine(
                mask.astype(np.uint8), m[:2], (737, 730), flags=cv2.INTER_NEAREST
            ).astype(bool)
            for mask, m in zip(original_masks, to_ref)
        ]
    )
    controls = [contour_controls(mask) for mask in registered_masks]
    candidates = [resample_path(c) for c in controls]
    fixed = candidates[-1]
    old_path = (
        ASSET_ROOT
        / "data/derived/lauschke-2013/video1-full-curve/video1-curved-kymograph.npz"
    )
    old_hash = digest(old_path)
    with np.load(old_path) as z:
        old = z["path_xy"]
        old_normals = z["normals_xy"]
        times = z["time_h"]
    output.mkdir(parents=True, exist_ok=True)
    from PIL import Image, ImageDraw, ImageFont

    title_font = ImageFont.load_default(size=22)
    caption_font = ImageFont.load_default(size=18)
    sheet_font = ImageFont.load_default(size=15)
    ids = [0, 60, 84, 100, 101, 125]
    sheet = Image.new("RGB", (3 * 480, len(ids) * 500), "white")
    sheet_draw = ImageDraw.Draw(sheet)
    valid_counts = []
    lengths = []
    # Encode each native frame once; avoid storing two full RGB movies in RAM.
    import av

    comparison = av.open(
        str(output / "roi-comparison.mp4"), "w", options={"movflags": "+faststart"}
    )
    stream = comparison.add_stream("libx264", rate=10)
    stream.width = 1920
    stream.height = 700
    stream.pix_fmt = "yuv420p"
    stream.options = {"crf": "19", "preset": "medium"}
    candidate_movie = av.open(
        str(output / "stabilized-roi.mp4"), "w", options={"movflags": "+faststart"}
    )
    candidate_stream = candidate_movie.add_stream("libx264", rate=10)
    candidate_stream.width = 738
    candidate_stream.height = 798
    candidate_stream.pix_fmt = "yuv420p"
    candidate_stream.options = {"crf": "18", "preset": "medium"}
    for i, (frame, m, mask, (path, norm, distance)) in enumerate(
        zip(frames, to_ref, registered_masks, candidates)
    ):
        registered = cv2.warpAffine(np.asarray(frame), m[:2], (737, 730))
        valid = coverage(path, norm, mask)
        fixed_valid = coverage(fixed[0], fixed[1], mask)
        valid_counts.append(int(valid.sum()))
        lengths.append(float(distance[-1]))
        panels = [
            draw_panel(
                frame,
                old[i],
                old_normals[i],
                np.ones(len(old[i]), bool),
                labels=("P", "toward A"),
            ),
            draw_panel(registered, fixed[0], fixed[1], fixed_valid, mask),
            draw_panel(registered, path, norm, valid, mask),
        ]
        titles = [
            "Current moving-P ROI",
            "Stabilized + fixed curve",
            "Stabilized + contour-guided ROI",
        ]
        canvas = Image.new("RGB", (3 * 640, 700), "#ffffff")
        d = ImageDraw.Draw(canvas)
        for j, (panel, title) in enumerate(zip(panels, titles)):
            resized = panel.resize((640, 634))
            canvas.paste(resized, (j * 640, 38))
            d.text((j * 640 + 14, 9), title, font=title_font, fill="#242833")
            d.text(
                (j * 640 + 14, 678),
                f"Frame {i} | experiment {times[i]:.2f} h",
                font=caption_font,
                fill="#525b6b",
            )
        for packet in stream.encode(av.VideoFrame.from_image(canvas)):
            comparison.mux(packet)
        single = Image.new("RGB", (738, 798), "white")
        single.paste(panels[2], (0, 38))
        sd = ImageDraw.Draw(single)
        sd.text(
            (12, 8),
            f"Fixed-reference candidate | {times[i]:.2f} h | frame {i}",
            font=title_font,
            fill="#242833",
        )
        sd.text(
            (12, 775),
            "Orange: supported strip | Dashed: outside foreground proxy",
            font=caption_font,
            fill="#525b6b",
        )
        for packet in candidate_stream.encode(av.VideoFrame.from_image(single)):
            candidate_movie.mux(packet)
        if i in ids:
            row = ids.index(i)
            for j, (panel, title) in enumerate(zip(panels, titles)):
                sheet.paste(panel.resize((480, 475)), (j * 480, row * 500 + 25))
                sheet_draw.text(
                    (j * 480 + 8, row * 500 + 4),
                    f"{title} | {times[i]:.2f}h",
                    font=sheet_font,
                    fill="black",
                )
        if i in [0, 60, 125]:
            panels[2].save(output / f"candidate-registered-{i}.png")
    sheet.save(output / "roi-comparison-keyframes.jpg", quality=93)
    for packet in stream.encode():
        comparison.mux(packet)
    comparison.close()
    for packet in candidate_stream.encode():
        candidate_movie.mux(packet)
    candidate_movie.close()
    stored_paths = np.full((126, max(len(p) for p, _, _ in candidates), 2), np.nan)
    stored_normals = stored_paths.copy()
    stored_controls = np.full((126, max(map(len, controls)), 2), np.nan)
    for i, (path, norm, _) in enumerate(candidates):
        stored_paths[i, : len(path)] = path
        stored_normals[i, : len(path)] = norm
    for i, c in enumerate(controls):
        stored_controls[i, : len(c)] = c
    np.savez_compressed(
        output / "geometry-review.npz",
        source_to_reference=to_ref,
        alternative_source_to_reference=alternative,
        controls_xy=stored_controls,
        control_counts=np.array(list(map(len, controls))),
        path_counts=np.array([len(p) for p, _, _ in candidates]),
        paths_xy=stored_paths,
        normals_xy=stored_normals,
        time_h=times,
        foreground_masks_original=original_masks,
        foreground_masks_registered=registered_masks,
    )
    displacement = []
    for m, n in zip(to_ref, alternative):
        displacement.append(
            float(
                np.linalg.norm(
                    transform(P_REF, np.linalg.inv(m))
                    - transform(P_REF, np.linalg.inv(n))
                )
            )
        )
    report = {
        "status": "geometry review candidate; not a new accepted kymograph",
        "source": {
            "filename": source.name,
            "sha256": SOURCE_HASH,
            "frames": 126,
            "range_h": [0, 20.92],
        },
        "method": "proximal feature registration (SE2 only) + fixed reference endpoints + contour-guided PSM-side strip",
        "reference_frame": 125,
        "A_ref_xy": A_REF.tolist(),
        "P_ref_xy": P_REF.tolist(),
        "width_px": WIDTH,
        "scale_um_per_px": SCALE,
        "inward_offset_nominal_px": 45,
        "contour": "11px local SD, Gaussian sigma3, threshold4.5, closing5, largest filled component; lower flank smoothed spatially; not anatomical PSM segmentation",
        "registration": {
            "primary_window_xyxy": [20, 20, 290, 390],
            "fallback_window_xyxy": [20, 20, 350, 600],
            "fallback_rule": "fewer than12 rigid inliers in proximal window",
            "scaling_or_shear": False,
            "reference": "last source frame; source-to-reference xy convention",
            "quality": quality,
            "minimum_inliers": min(r["inliers"] for r in quality),
            "median_fit_rmse_px": float(np.median([r["fit_rmse_px"] for r in quality])),
            "broader_window_P_ref_source_disagreement_px": displacement,
            "region_sensitivity_max_px": max(displacement),
            "anatomically_validated": False,
            "note": "Fit residuals are internal consistency checks, not independent anatomical validation. Cumulative registration depends on the chosen structural region.",
        },
        "curve_lengths_um": lengths,
        "foreground_supported_rows": valid_counts,
        "coordinate": "physical arc length along each candidate; endpoint positions fixed in reference xy; no length normalization",
        "preserved_primary": {
            "path": str(old_path.relative_to(ASSET_ROOT)),
            "sha256": old_hash,
        },
        "limitations": [
            "Reference endpoints are prospective analyst choices, not exact anatomical P/A boundaries or the same cells.",
            "Whole-tail foreground and its inward flank are not verified PSM identity. Review the strip location before extraction.",
            "Rigid stabilization removes an estimated global component; real growth/bending and nonrigid motion remain.",
            "No intensity kymograph is accepted or substituted by this geometry pilot. Body-exterior intervals must be missing, not zero, in a later extraction.",
        ],
        "libraries": {"opencv": cv2.__version__, "numpy": np.__version__},
        "api_documentation": [
            "https://docs.opencv.org/5.0/main_modules/d_projection.html"
        ],
        "script_sha256": digest(__file__),
    }
    jacobians = []
    for path, norm, _ in candidates:
        tangent = np.column_stack([norm[:, 1], -norm[:, 0]])
        angle = np.unwrap(np.arctan2(tangent[:, 1], tangent[:, 0]))
        curvature = np.diff(angle) / np.linalg.norm(np.diff(path, axis=0), axis=1)
        jacobians.append(float((1 - WIDTH / 2 * np.abs(curvature)).min()))
    report["geometry_checks"] = {
        "minimum_local_width_jacobian": min(jacobians),
        "local_fold_frames": np.flatnonzero(np.array(jacobians) <= 0).tolist(),
        "endpoints_fixed_in_reference": True,
        "foreground_is_anatomical_mask": False,
        "intensity_extraction_performed": False,
    }
    if min(jacobians) <= 0:
        raise ValueError("Candidate strip folds; needs geometry revision")
    if digest(old_path) != old_hash:
        raise ValueError("Existing primary changed")
    (output / "review.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "minimum_inliers": report["registration"]["minimum_inliers"],
                "fit_rmse_px": report["registration"]["median_fit_rmse_px"],
                "length_range_um": [min(lengths), max(lengths)],
                "mask_rows_range": [min(valid_counts), max(valid_counts)],
                "region_sensitivity_max_px": max(displacement),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/video1-stabilized-roi-review")
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=ASSET_ROOT
        / "data/source-archive/lauschke-2013/41586_2013_BFnature11804_MOESM292_ESM.mov",
    )
    parser.add_argument("--cached-frames", type=Path)
    args = parser.parse_args()
    run(args.output, args.source, args.cached_frames)

# SPDX-License-Identifier: MIT
"""Final-frame reference coordinates for Sonnen S1 axial and S2 radial strips."""

import argparse
import json

import av
import cv2
import numpy as np

from curved_strip import arc_length_path
from extract_sonnen_additional import digest, image_validity
from paths import ASSET_ROOT
from review_sonnen_s1_half import half_support, normals_for
from review_sonnen_s2_extended import envelope, THRESHOLDS
from review_video1_stable_roi import rigid_fit, transform
from verify_sonnen_candidates import strip_profile

STUDY = ASSET_ROOT / "data/derived/sonnen-2018"
CASES = {
    "s1": ("s1-midline-half-review", "s1-final-reference", "mmc2.mp4"),
    "s2": ("s2-extended-ray-review", "s2-final-reference", "mmc3.mp4"),
}


def anterior_pose(frames, seams, max_y=425):
    """Unit-scale rigid motion from texture in the selected anterior hemibody."""
    cv2.setNumThreads(2)
    cv2.setRNGSeed(13)
    clahe = cv2.createCLAHE(clipLimit=2, tileGridSize=(8, 8))
    images = [clahe.apply(cv2.GaussianBlur(f[:, :, 1], (0, 0), 1)) for f in frames]
    fov = image_validity("s1", frames[0].shape[:2])
    cumulative = [np.eye(3)]
    quality = []
    for i in range(len(frames) - 1):
        support = half_support(frames[i][:, :, 1], seams[i], fov)
        support[:40] = False
        support[max_y:] = False
        points = cv2.goodFeaturesToTrack(
            images[i],
            maxCorners=800,
            qualityLevel=0.006,
            minDistance=7,
            mask=support.astype(np.uint8) * 255,
            blockSize=7,
        )
        if points is None or len(points) < 6:
            raise ValueError(f"Insufficient anterior texture at frame {i}")
        target, forward_status, _ = cv2.calcOpticalFlowPyrLK(
            images[i],
            images[i + 1],
            points,
            None,
            winSize=(41, 41),
            maxLevel=3,
        )
        returned, reverse_status, _ = cv2.calcOpticalFlowPyrLK(
            images[i + 1],
            images[i],
            target,
            None,
            winSize=(41, 41),
            maxLevel=3,
        )
        good = (forward_status[:, 0] > 0) & (reverse_status[:, 0] > 0)
        good &= np.linalg.norm(returned[:, 0] - points[:, 0], axis=1) < 1.5
        good &= np.linalg.norm(target[:, 0] - points[:, 0], axis=1) < 25
        source, target = points[:, 0][good], target[:, 0][good]
        if len(source) < 6:
            raise ValueError(f"Insufficient consistent texture at frame {i}")
        _, keep = cv2.estimateAffinePartial2D(
            source,
            target,
            method=cv2.RANSAC,
            ransacReprojThreshold=2.5,
            maxIters=4000,
            confidence=0.999,
        )
        if keep is None:
            raise ValueError(f"Anterior pose fit failed at frame {i}")
        keep = keep[:, 0] > 0
        matrix = rigid_fit(source[keep], target[keep])
        keep = np.linalg.norm(transform(source, matrix) - target, axis=1) < 3
        matrix = rigid_fit(source[keep], target[keep])
        residual = np.linalg.norm(
            transform(source[keep], matrix) - target[keep], axis=1
        )
        quality.append(
            {
                "frame": i + 1,
                "inliers": int(keep.sum()),
                "rmse_px": float(np.sqrt(np.mean(residual**2))),
                "feature_span_xy_px": np.ptp(source[keep], axis=0).tolist(),
            }
        )
        cumulative.append(matrix @ cumulative[-1])
    cumulative = np.array(cumulative)
    return cumulative[-1][None] @ np.linalg.inv(cumulative), quality


def longest_run(good):
    starts = np.flatnonzero(good & ~np.r_[False, good[:-1]])
    stops = np.flatnonzero(good & ~np.r_[good[1:], False]) + 1
    valid = np.zeros(len(good), bool)
    if len(starts):
        selected = np.argmax(stops - starts)
        valid[starts[selected] : stops[selected]] = True
    return valid


def s1_geometry(frames, old):
    seams = old["seam_xy"]
    to_reference, quality = anterior_pose(frames, seams)
    alternative, alternative_quality = anterior_pose(frames, seams, max_y=325)
    scale, width = float(old["um_per_px"]), float(old["strip_width_px"])
    corridors = [seam + 85 * normals_for(seam) for seam in seams]
    # Keep the approved final-frame P-side endpoint as the prospective reference.
    p_ref = old["path_xy"][-1, 0].copy()
    a_ref = corridors[-1][-1].copy()
    controls, lengths = [], []
    for corridor, pose in zip(corridors, to_reference):
        registered = transform(corridor, pose)
        u = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(registered, axis=0), axis=1))]
        p_fraction = np.clip(u / 300, 0, 1)
        a_fraction = np.clip((u[-1] - u) / 200, 0, 1)
        p_weight = 1 - p_fraction**2 * (3 - 2 * p_fraction)
        a_weight = 1 - a_fraction**2 * (3 - 2 * a_fraction)
        points = registered + p_weight[:, None] * (p_ref - registered[0])
        points += a_weight[:, None] * (a_ref - registered[-1])
        points[0], points[-1] = p_ref, a_ref
        controls.append(points)
        lengths.append(arc_length_path(points, np.array([0.0]), scale)[2])
    distance = np.arange(0, np.ceil(max(lengths)) + 1)
    paths, normals, reference_paths = [], [], []
    for points, pose in zip(controls, to_reference):
        path, normal, _ = arc_length_path(points, distance, scale)
        inverse = np.linalg.inv(pose)
        paths.append(transform(path, inverse))
        normals.append(normal @ inverse[:2, :2].T)
        reference_paths.append(path)
    p_source = np.array(
        [transform(p_ref, np.linalg.inv(pose)) for pose in to_reference]
    )
    a_source = np.array(
        [transform(a_ref, np.linalg.inv(pose)) for pose in to_reference]
    )
    alternative_p = np.array(
        [transform(p_ref, np.linalg.inv(pose)) for pose in alternative]
    )
    sensitivity = np.linalg.norm(p_source - alternative_p, axis=1)
    arrays = {
        "path_xy": np.array(paths),
        "normals_xy": np.array(normals),
        "reference_path_xy": np.array(reference_paths),
        "source_to_reference": to_reference,
        "alternative_source_to_reference": alternative,
        "P_reference_xy": p_ref,
        "A_reference_xy": a_ref,
        "P_reference_source_xy": p_source,
        "A_reference_source_xy": a_source,
        "seam_xy": seams,
        "registration_sensitivity_px": sensitivity,
    }
    record = {
        "registration": "Anterior image-right texture, forward/backward KLT correspondences and RANSAC, followed by unit-scale rigid fits composed into the final frame. The posterior tip is excluded from the pose fit.",
        "registration_quality": quality,
        "alternative_registration_quality": alternative_quality,
        "structural_window_y_max_px": [425, 325],
        "max_reference_point_window_sensitivity_px": float(sensitivity.max()),
        "P_reference_xy_final_frame": p_ref.tolist(),
        "A_reference_xy_final_frame": a_ref.tolist(),
        "reference_evidence": "P is the posterior-side endpoint of the approved half-strip in the last source frame. A is the last frame's anterior endpoint of the approved full corridor. Both are fixed geometric references in final-frame coordinates.",
        "strip": "Approved image-right corridor, 85 px seam offset and 60 px width. The interior follows the saved seam track with endpoint corrections tapered over 300 source pixels from P and 200 pixels from A. Physical arc length is recomputed independently in every frame.",
        "coverage": "Every width sample must pass the saved half-side/FOV rules and the row-filled outer-envelope proxy. Keep the longest connected supported interval, preserving its missing P-side prefix and any missing A-side suffix.",
        "limitations": "Cumulative registration depends on the anterior structural window. The final posterior contour and selected-half geometry remain approximate. Empty positions record missing coverage relative to a fixed reference, with growth interpretation dependent on registration and coverage quality.",
    }
    return arrays, distance, scale, width, record


def s2_geometry(old):
    shifts = old["shifts_xy"]
    count = len(shifts)
    pose = np.repeat(np.eye(3)[None], count, axis=0)
    pose[:, :2, 2] = shifts[-1] - shifts
    p_ref = old["path_xy"][-1, 0]
    origins = np.array([transform(p_ref, np.linalg.inv(t)) for t in pose])
    direction = old["direction_xy"]
    scale, width = float(old["um_per_px"]), float(old["strip_width_px"])
    distance = old["position_um"]
    paths = origins[:, None, :] + distance[None, :, None] / scale * direction
    normal = np.array([-direction[1], direction[0]])
    arrays = {
        "path_xy": paths,
        "normals_xy": np.broadcast_to(normal, paths.shape).copy(),
        "P_reference_xy": p_ref,
        "P_reference_source_xy": origins,
        "source_to_reference": pose,
        "shifts_xy": shifts,
        "direction_xy": direction,
    }
    np.testing.assert_allclose(paths, old["path_xy"], atol=1e-10, rtol=0)
    record = {
        "registration": "Existing saved translations expressed in final-frame coordinates. The single P-side reference is fixed at the last-frame inner origin and inverse-mapped into each source frame.",
        "P_reference_xy_final_frame": p_ref.tolist(),
        "reference_evidence": "Existing reviewed inner P-side origin, expressed once in the final frame. Its anatomical center identity remains under calibration.",
        "strip": "Same physical distance grid, direction and 40 px transverse width. The outer extent follows full-width coverage while the inner reference stays fixed.",
        "coverage": "All 41 width samples must lie inside each of the three outer-envelope estimates at display thresholds 25, 35 and 45, using an 8 px geometry Gaussian and 5 px margin. Keep the connected interval containing the inner reference. Coverage applies to the entire ray.",
        "limitations": "A central reference can be inside the tissue throughout the acquisition. Spreading appears at the outer end of this radial coordinate. The inner reference, spatial scale and display-derived envelope remain approximate.",
    }
    return arrays, distance, scale, width, record


def run(name):
    previous, folder, movie_file = CASES[name]
    source = ASSET_ROOT / "data/source-archive/sonnen-2018" / movie_file
    old_file = STUDY / previous / "kymograph.npz"
    prior = json.loads((STUDY / previous / "provenance.json").read_text())
    if (
        digest(source) != prior["source_sha256"]
        or digest(old_file) != prior["matrix_sha256"]
    ):
        raise ValueError("Source or approved reference changed")
    with av.open(str(source)) as c:
        frames = [f.to_ndarray(format="rgb24") for f in c.decode(video=0)]
    with np.load(old_file) as z:
        old = {k: z[k] for k in z.files}
    arrays, distance, scale, width, record = (
        s1_geometry(frames, old) if name == "s1" else s2_geometry(old)
    )
    offsets = np.linspace(-width / 2, width / 2, int(np.ceil(width)) + 1)
    fov = image_validity("s1", frames[0].shape[:2]) if name == "s1" else None
    matrix = np.full((len(distance), len(frames)), np.nan)
    counts = np.zeros(matrix.shape, np.int16)
    minimum_jacobians = []
    for i, frame in enumerate(frames):
        support = (
            half_support(frame[:, :, 1], old["seam_xy"][i], fov)
            if name == "s1"
            else np.logical_and.reduce(
                [envelope(frame[:, :, 1], v) for v in THRESHOLDS]
            )
        )
        raw, counts[:, i] = strip_profile(
            frame[:, :, 1],
            arrays["path_xy"][i],
            arrays["normals_xy"][i],
            offsets,
            support,
        )
        good = np.isfinite(raw)
        keep = longest_run(good) if name == "s1" else np.logical_and.accumulate(good)
        matrix[:, i] = np.where(keep, raw, np.nan)
        path = arrays["path_xy"][i, keep]
        normal = arrays["normals_xy"][i, keep]
        angle = np.unwrap(np.arctan2(normal[:, 1], normal[:, 0]))
        curvature = np.diff(angle) / np.linalg.norm(np.diff(path, axis=0), axis=1)
        minimum = float(np.min(1 - width / 2 * abs(curvature)))
        if minimum <= 0:
            raise ValueError(f"Finite-width strip folds at frame {i}")
        minimum_jacobians.append(minimum)
    valid = np.isfinite(matrix)
    first = np.array(
        [distance[np.flatnonzero(v)[0]] if v.any() else np.nan for v in valid.T]
    )
    last = np.array(
        [distance[np.flatnonzero(v)[-1]] if v.any() else np.nan for v in valid.T]
    )
    arrays.update(
        intensity=matrix,
        time_h=old["time_h"],
        position_um=distance,
        frame_index=np.arange(len(frames)),
        valid=valid,
        width_counts=counts,
        strip_width_px=width,
        um_per_px=scale,
        first_valid_distance_um=first,
        last_valid_distance_um=last,
    )
    output = STUDY / folder
    output.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output / "kymograph.npz", **arrays)
    record.update(
        dataset_id="sonnen-2018-embryo" if name == "s1" else "sonnen-2018",
        analysis_script="analysis/extract_sonnen_fixed_reference.py",
        analysis_script_sha256=digest(__file__),
        source_file=str(source.relative_to(ASSET_ROOT)),
        source_sha256=digest(source),
        previous_input=str(old_file.relative_to(ASSET_ROOT)),
        previous_sha256=digest(old_file),
        matrix_sha256=digest(output / "kymograph.npz"),
        frame_count=len(frames),
        time_range_h=old["time_h"][[0, -1]].tolist(),
        distance_range_um=distance[[0, -1]].tolist(),
        strip_width_px=width,
        approx_um_per_px=scale,
        first_valid_distance_um=first.tolist(),
        last_valid_distance_um=last.tolist(),
        minimum_retained_width_jacobian=min(minimum_jacobians),
        signal="Bilinear transverse mean of original decoded green display values.",
    )
    (output / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")
    print(
        name,
        "P",
        record["P_reference_xy_final_frame"],
        "first valid",
        first[[0, -1]],
        "max registration sensitivity",
        record.get("max_reference_point_window_sensitivity_px"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=CASES, action="append")
    for case in parser.parse_args().only or CASES:
        run(case)

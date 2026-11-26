"""Register each movie's final caudal silhouette to its anterior structural landmarks."""

import cv2
import numpy as np
from scipy.interpolate import CubicHermiteSpline, PchipInterpolator


def structural_poses(frames, window):
    """Use the same track IDs in every rigid fit; ignore the green reporter channel."""
    cv2.setRNGSeed(271)
    structure = [
        np.rint((rgb[..., 0].astype(float) + rgb[..., 2]) / 2).astype("uint8")
        for rgb in frames
    ]
    x, y, right, bottom = window
    mask = np.zeros_like(structure[0])
    mask[y:bottom, x:right] = 255
    points = cv2.goodFeaturesToTrack(structure[0], 150, 0.012, 4, mask=mask)
    tracks = [points[:, 0]]
    keep = np.ones(len(points), dtype=bool)
    options = dict(
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 30, 0.01),
    )
    for a, b in zip(structure, structure[1:]):
        forward, ok, _ = cv2.calcOpticalFlowPyrLK(a, b, points, None, **options)
        backward, back_ok, _ = cv2.calcOpticalFlowPyrLK(b, a, forward, None, **options)
        keep &= (ok.ravel() == 1) & (back_ok.ravel() == 1)
        keep &= np.linalg.norm(backward[:, 0] - points[:, 0], axis=1) < 0.75
        tracks.append(forward[:, 0])
        points = forward
    tracks = np.ascontiguousarray(np.array(tracks)[:, keep])
    _, inliers = cv2.estimateAffinePartial2D(
        tracks[0], tracks[-1], method=cv2.RANSAC, ransacReprojThreshold=2.5
    )
    if inliers is None or inliers.sum() < 6:
        raise ValueError("Too few consistent anterior landmarks")
    tracks = tracks[:, inliers.ravel().astype(bool)].astype(np.float64)
    final = tracks[-1]
    poses = []
    for current in tracks:
        cross = (final - final.mean(0)).T @ (current - current.mean(0))
        left, _, right = np.linalg.svd(cross)
        rotation = left @ right
        if np.linalg.det(rotation) < 0:
            raise ValueError("Reflected structural pose")
        offset = current.mean(0) - final.mean(0) @ rotation
        residual = np.linalg.norm(final @ rotation + offset - current, axis=1)
        poses.append((rotation, offset, np.median(residual)))
    return poses, tracks.shape[1]


def posterior_curve(rim, medial):
    """Join the caudal outline smoothly to the reviewed medial PSM corridor."""
    join = 35
    tangent = medial[join + 1] - medial[join - 1]
    distance = np.linalg.norm(medial[join] - rim)
    bridge = CubicHermiteSpline(
        [0, 1],
        [rim, medial[join]],
        [[0, -distance], distance * tangent / np.linalg.norm(tangent)],
    )
    return np.vstack([bridge(np.linspace(0, 1, 120, endpoint=False)), medial[join:]])


def registered_strips(job, frames, medial):
    config = job["final_tail_reference"]
    tips = PchipInterpolator(config["rim_frames"], config["rim_xy"], axis=0)(
        np.arange(len(frames))
    )
    poses, count = structural_poses(frames, config["anterior_feature_window"])
    paths = [posterior_curve(tip, line) for tip, line in zip(tips, medial)]
    result = []
    for tip, path, (rotation, offset, residual) in zip(tips, paths, poses):
        reference = tips[-1] @ rotation + offset
        gap = np.linalg.norm(reference - tip)
        if gap < 1e-8:
            reference = tip.copy()
            gap = 0.0
        arc = gap + np.r_[0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
        # The whole finite-width strip must clear the blurred silhouette. Its first
        # few pixels remain unmeasured even when the final P marker is on the rim.
        start = int(np.ceil(gap + config["posterior_inset_px"]))
        stop = int(np.floor(arc[-1]))
        if stop <= start:
            raise ValueError("No supported medial corridor")
        valid = np.arange(start, stop + 1)
        line = np.column_stack([np.interp(valid, arc, coord) for coord in path.T])
        lead = np.vstack([reference, tip, path[(arc > gap) & (arc < start)], line[0]])
        guides = [lead.round(4).tolist()]
        anterior = line[-1]
        result.append(
            dict(
                line=line,
                start=start,
                guide_lines=guides,
                reference_points=np.array([reference, anterior]).round(4).tolist(),
                rim_xy=tip.round(4).tolist(),
                pose_rotation=rotation.tolist(),
                pose_offset=offset.tolist(),
                pose_residual_px=float(residual),
                pose_inliers=count,
            )
        )
    return result, max(strip["start"] + len(strip["line"]) for strip in result)

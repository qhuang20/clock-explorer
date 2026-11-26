# SPDX-License-Identifier: MIT
"""Estimate a Video 2 wavefront curvature center without a tissue-COM prior.

This independent estimator implements a checkable center choice for the paper's
center-to-periphery sampling geometry; it is not the authors' unpublished ROI
algorithm. A coherent early-wave center is not proof of a stationary biological
source throughout later deformation/arrest.
"""

import numpy as np
from scipy import ndimage as ndi, optimize

STEP = 3
FIT_TIME_H = (0.75, 16.0)
GEOMETRY_SIGMA_UM = 16.61
CONSENSUS_PX = 35.0


def fit_circle(points):
    q = np.asarray(points, float)
    if len(q) < 4 or np.linalg.matrix_rank(q - q.mean(axis=0)) < 2:
        raise ValueError("A straight/insufficient contour does not identify a center")
    coef = np.linalg.lstsq(
        np.c_[2 * q, np.ones(len(q))], (q * q).sum(axis=1), rcond=None
    )[0]
    center = coef[:2]
    radius = np.sqrt(max(0, coef[2] + center @ center))
    result = optimize.least_squares(
        lambda v: np.linalg.norm(q - v[:2], axis=1) - v[2],
        np.r_[center, radius],
        loss="soft_l1",
        f_scale=6,
        max_nfev=150,
    )
    center = result.x[:2]
    radius = float(result.x[2])
    residual = float(np.median(abs(np.linalg.norm(q - center, axis=1) - radius)))
    angles = np.unwrap(np.arctan2(q[:, 1] - center[1], q[:, 0] - center[0]))
    return center, radius, residual, float(np.ptp(angles))


def fit_common_center(fronts, initial=None):
    if len(fronts) < 3:
        raise ValueError("Need multiple independently observed wavefront frames")
    points = [np.asarray(f["points"], float) for f in fronts]
    initial = (
        np.median([f["center"] for f in fronts], axis=0)
        if initial is None
        else np.asarray(initial)
    )
    start = np.r_[
        initial, [np.median(np.linalg.norm(q - initial, axis=1)) for q in points]
    ]

    # Each frame contributes equal total weight, regardless of contour length.
    def residuals(v):
        return np.concatenate(
            [
                (np.linalg.norm(q - v[:2], axis=1) - v[2 + j]) / np.sqrt(len(q))
                for j, q in enumerate(points)
            ]
        )

    result = optimize.least_squares(
        residuals, start, loss="soft_l1", f_scale=1, max_nfev=300
    )
    if not result.success or not np.isfinite(result.x).all():
        raise ValueError("Wavefront-center fit did not converge")
    return result.x[:2], result.x[2:]


def select_consensus(fronts):
    if not fronts:
        raise ValueError("No well-curved wavefronts; there is no COM fallback")

    def select(center):
        by_frame = {}
        for f in fronts:
            if np.linalg.norm(np.asarray(f["center"]) - center) > CONSENSUS_PX:
                continue
            if (
                f["frame"] not in by_frame
                or f["residual_px"] < by_frame[f["frame"]]["residual_px"]
            ):
                by_frame[f["frame"]] = f
        return sorted(by_frame.values(), key=lambda f: f["frame"])

    choices = []
    for hypothesis in fronts:
        fs = select(np.asarray(hypothesis["center"]))
        score = (
            len(fs),
            np.ptp([f["time_h"] for f in fs]),
            -np.median([f["residual_px"] for f in fs]),
        )
        choices.append((score, fs))
    selected = max(choices, key=lambda item: item[0])[1]
    if len(selected) < 5 or np.ptp([f["time_h"] for f in selected]) < 2:
        raise ValueError("Wavefront evidence does not span enough distinct frames/time")
    center, _ = fit_common_center(selected)
    for _ in range(3):
        selected = select(center)
        center, radii = fit_common_center(selected, center)
    if len(selected) < 5 or np.ptp([f["time_h"] for f in selected]) < 2:
        raise ValueError("Refined consensus lost temporal support")
    return center, radii, selected


def find_fronts(
    frames,
    masks,
    shifts,
    times,
    um_per_px,
    sigma_um=GEOMETRY_SIGMA_UM,
    *,
    frame_stride=2,
    fit_time_h=FIT_TIME_H,
    channel=None,
):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not isinstance(frame_stride, int) or frame_stride < 1:
        raise ValueError("Frame stride must be a positive integer")
    if channel is not None and channel not in range(frames.shape[-1]):
        raise ValueError("Requested display channel is unavailable")
    # First retain the paper's spatial scale, then suppress cell texture only in
    # the center estimator. The final intensity sampler does not use these data.
    movie = []
    support = []
    for f, m, s in zip(frames, masks, shifts):
        signal = f.mean(axis=-1) if channel is None else f[..., channel]
        gray = ndi.gaussian_filter(signal.astype(np.float32), 9.66 / um_per_px)
        movie.append(ndi.shift(gray, [-s[1], -s[0]], order=1, cval=0)[::STEP, ::STEP])
        support.append(
            ndi.shift(m.astype(float), [-s[1], -s[0]], order=0)[::STEP, ::STEP] > 0.5
        )
    movie = np.asarray(movie)
    support = np.asarray(support)
    dt = float(np.median(np.diff(times)))
    dynamic = ndi.gaussian_filter1d(movie, 0.20 / dt, axis=0) - ndi.gaussian_filter1d(
        movie, 1.2 / dt, axis=0
    )
    extra = np.sqrt(max(0, sigma_um**2 - 9.66**2)) / (um_per_px * STEP)
    dynamic = ndi.gaussian_filter(dynamic, (0, extra, extra))
    x = np.arange(dynamic.shape[2]) * STEP
    y = np.arange(dynamic.shape[1]) * STEP
    fig, ax = plt.subplots()
    fronts = []
    try:
        for i in np.flatnonzero((times >= fit_time_h[0]) & (times <= fit_time_h[1]))[
            ::frame_stride
        ]:
            valid = ndi.binary_erosion(support[i], iterations=7)
            field = np.ma.masked_where(~valid, dynamic[i])
            if field.count() < 100:
                continue
            scale = float(np.std(field.compressed()))
            for level in [0, -0.4 * scale, 0.4 * scale]:
                contours = ax.contour(x, y, field, levels=[level])
                for contour in contours.allsegs[0]:
                    if len(contour) < 20:
                        continue
                    arclength = np.r_[
                        0, np.linalg.norm(np.diff(contour, axis=0), axis=1).cumsum()
                    ]
                    if arclength[-1] < 200:
                        continue
                    loc = np.arange(0, arclength[-1], 6)
                    q = np.c_[
                        np.interp(loc, arclength, contour[:, 0]),
                        np.interp(loc, arclength, contour[:, 1]),
                    ]
                    try:
                        center, radius, error, span = fit_circle(q)
                    except ValueError:
                        continue
                    if (
                        75 < radius < 450
                        and span > 2.4
                        and error < 12
                        and error / radius < 0.08
                        and 0 < center[0] < frames.shape[2]
                        and 0 < center[1] < 680
                    ):
                        fronts.append(
                            {
                                "frame": int(i),
                                "time_h": float(times[i]),
                                "level": float(level),
                                "center": center.tolist(),
                                "radius_px": radius,
                                "residual_px": error,
                                "span_rad": span,
                                "points": q.tolist(),
                            }
                        )
                ax.clear()
    finally:
        plt.close(fig)
    return fronts


def ray_direction(center, fronts):
    # The article's upper peripheral sector avoids the detached bright spots at
    # the bottom of this movie. Sector choice is a reviewed tissue/FOV choice,
    # separate from the COM-independent center fit and from kymograph contrast.
    scores = []
    for deg in np.arange(-100, -39, 2):
        errors = []
        for front in fronts:
            q = np.asarray(front["points"])
            v = q - center
            angle = np.degrees(np.arctan2(v[:, 1], v[:, 0]))
            near = abs((angle - deg + 180) % 360 - 180) < 6
            if near.sum() < 2:
                continue
            tangent = np.gradient(q, axis=0)
            normal = np.c_[-tangent[:, 1], tangent[:, 0]]
            cosine = abs((normal * v).sum(axis=1)) / np.maximum(
                np.linalg.norm(normal, axis=1) * np.linalg.norm(v, axis=1), 1e-9
            )
            errors.append(
                float(np.median(np.degrees(np.arccos(np.clip(cosine[near], 0, 1)))))
            )
        if errors:
            scores.append(
                {
                    "angle_deg": int(deg),
                    "directly_crossed_fit_frames": len(errors),
                    "median_normal_error_deg": float(np.median(errors)),
                }
            )
    if not scores:
        raise ValueError("The reviewed upper sector has no observed front support")
    selected = min(scores, key=lambda row: abs(row["angle_deg"] + 72))
    selected["selection"] = (
        "Reviewed upper contiguous-tissue sector, approximately matching the published arrow; not optimized for kymograph contrast"
    )
    selected["caution"] = (
        "Only a subset of accepted arcs crosses this ray directly; perpendicularity elsewhere relies on the approximate circular-wavefront model"
    )
    rad = np.deg2rad(selected["angle_deg"])
    return np.array([np.cos(rad), np.sin(rad)]), selected, scores


def estimate_center(frames, masks, shifts, times, um_per_px, with_sensitivity=True):
    fronts = find_fronts(frames, masks, shifts, times, um_per_px)
    center, radii, selected = select_consensus(fronts)
    direction, ray, scores = ray_direction(center, selected)
    midpoint = float(np.median([f["time_h"] for f in selected]))
    halves = [
        [f for f in selected if f["time_h"] <= midpoint],
        [f for f in selected if f["time_h"] > midpoint],
    ]
    half_centers = [fit_common_center(fs, center)[0] for fs in halves]
    residuals = [
        abs(np.linalg.norm(np.asarray(f["points"]) - center, axis=1) - r)
        for f, r in zip(selected, radii)
    ]
    sensitivity = []
    if with_sensitivity:
        for sigma in [14.0, 20.0]:
            try:
                candidates = find_fronts(frames, masks, shifts, times, um_per_px, sigma)
                other, _, used = select_consensus(candidates)
                sensitivity.append(
                    {
                        "geometry_sigma_um": sigma,
                        "center_xy_reference_px": other.tolist(),
                        "offset_um": float(np.linalg.norm(other - center) * um_per_px),
                        "accepted_frames": len(used),
                    }
                )
            except ValueError as error:
                sensitivity.append(
                    {"geometry_sigma_um": sigma, "unidentified": str(error)}
                )
    audit = {
        "method_version": "wavefront-arcs-v1",
        "center_xy_reference_px": center.tolist(),
        "no_com_prior_or_fallback": True,
        "scanned_time_h": list(FIT_TIME_H),
        "supported_time_h": [
            min(f["time_h"] for f in selected),
            max(f["time_h"] for f in selected),
        ],
        "candidate_arc_count": len(fronts),
        "accepted_distinct_frames": len(selected),
        "accepted_frames": [f["frame"] for f in selected],
        "median_joint_arc_residual_um": float(
            np.median(np.concatenate(residuals)) * um_per_px
        ),
        "disjoint_time_centers_xy_px": [c.tolist() for c in half_centers],
        "disjoint_time_center_separation_um": float(
            np.linalg.norm(half_centers[1] - half_centers[0]) * um_per_px
        ),
        "max_disjoint_time_offset_um": float(
            max(np.linalg.norm(c - center) for c in half_centers) * um_per_px
        ),
        "ray": ray,
        "ray_angle_candidates": scores,
        "geometry_filter_sensitivity": sensitivity,
        "filters_geometry_only": {
            "spatial_sigma_um": GEOMETRY_SIGMA_UM,
            "temporal_difference_of_gaussians_sigma_h": [0.2, 1.2],
            "time_grid": "sigma converted using median overlay interval; no final data timestamps or intensities are filtered",
            "stride_pixels": STEP,
        },
        "arc_rules": {
            "minimum_length_px": 200,
            "radius_range_px": [75, 450],
            "minimum_angular_span_rad": 2.4,
            "maximum_median_residual_px": 12,
            "maximum_relative_residual": 0.08,
            "consensus_distance_px": CONSENSUS_PX,
            "equal_weight_per_frame": True,
        },
        "limitations": [
            "A curvature-center estimate from coherent early wavefronts is not a verified molecular posterior marker or the authors' exact ROI.",
            "A stationary center beyond the supported early interval is not independently validated; the early fitted anchor is continued only by matched brightfield translation.",
            "Disjoint-time and geometry-filter differences are sensitivity diagnostics, not statistical confidence intervals.",
        ],
    }
    return center, direction, audit, selected

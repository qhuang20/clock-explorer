# SPDX-License-Identifier: MIT
"""Physical arc-length sampling along a reviewed, finite-width curved path.

This module does not infer anatomy, track cells, or fit a path to brightness.
Callers supply the reviewed P-to-A geometry in original image coordinates.
"""

import numpy as np
from scipy.interpolate import CubicSpline
from scipy import ndimage as ndi


def arc_length_path(points_xy, distance_um, um_per_px):
    """Return centerline and unit normals at physical distances from point 0.

    A natural cubic interpolant follows chord-length-parameterized control
    points; a dense arc-length lookup avoids stretching a curved path onto a
    straight chord or normalizing different specimens to the same length.
    Positions beyond the supplied path are missing, never extrapolated.
    """
    points = np.asarray(points_xy, float)
    distance = np.asarray(distance_um, float)
    if (
        points.ndim != 2
        or points.shape[1] != 2
        or len(points) < 2
        or not np.isfinite(points).all()
        or um_per_px <= 0
        or not np.isfinite(um_per_px)
    ):
        raise ValueError("Finite xy points and positive isotropic calibration required")
    chords = np.linalg.norm(np.diff(points, axis=0), axis=1)
    if np.any(chords <= 0) or not np.isfinite(distance).all() or np.any(distance < 0):
        raise ValueError(
            "Distinct consecutive points and nonnegative distances required"
        )
    u = np.r_[0.0, np.cumsum(chords)]
    spline = CubicSpline(u, points, axis=0, bc_type="natural")
    dense_u = np.linspace(0, u[-1], max(4097, int(u[-1] * 10) + 1))
    dense_xy = spline(dense_u)
    arc_um = (
        np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(dense_xy, axis=0), axis=1))]
        * um_per_px
    )
    inside = distance <= arc_um[-1]
    sampled_u = np.interp(distance, arc_um, dense_u)
    xy = spline(sampled_u)
    tangent = spline(sampled_u, 1)
    tangent /= np.linalg.norm(tangent, axis=1, keepdims=True)
    normal = np.stack([-tangent[:, 1], tangent[:, 0]], axis=-1)
    xy[~inside] = np.nan
    normal[~inside] = np.nan
    return xy, normal, float(arc_um[-1])


def strip_coordinates(path_xy, normals_xy, width_px):
    if width_px <= 0 or int(width_px) != width_px:
        raise ValueError("Positive integer strip width required")
    offsets = np.linspace(-width_px / 2, width_px / 2, int(width_px) + 1)
    return path_xy[:, None, :] + offsets[None, :, None] * normals_xy[:, None, :]


def sample_strip(
    frame,
    path_xy,
    normals_xy,
    width_px=20,
    min_fraction=0.75,
    sigma_px=0.0,
    valid_region=None,
    coverage_policy="origin_connected",
):
    """Mean across normals at each distance; no spatial-axis/time averaging.

    valid_region, if supplied, is a categorical pixel mask. The caller must
    distinguish a FOV/text mask from an anatomical segmentation. After the first
    insufficient-width position, the remaining profile is missing by default.
    ``last_supported_run`` instead retains only the final contiguous supported
    interval, allowing a missing prefix from a fixed reference outside early
    tissue. The caller must independently check its intended endpoint/anchor;
    this policy does not infer anatomical connectivity or bridge missing gaps.
    """
    if not 0 < min_fraction <= 1:
        raise ValueError("Valid-width fraction must be in (0, 1]")
    xy = strip_coordinates(np.asarray(path_xy), np.asarray(normals_xy), width_px)
    h, w = frame.shape[:2]
    valid = (
        np.isfinite(xy).all(axis=-1)
        & (xy[..., 0] >= 0)
        & (xy[..., 0] <= w - 1)
        & (xy[..., 1] >= 0)
        & (xy[..., 1] <= h - 1)
    )
    coords = [np.nan_to_num(xy[..., 1], nan=-1), np.nan_to_num(xy[..., 0], nan=-1)]
    if valid_region is not None:
        valid &= (
            ndi.map_coordinates(
                np.asarray(valid_region, np.uint8),
                coords,
                order=0,
                mode="constant",
                cval=0,
            )
            > 0
        )
    gray = np.asarray(frame, float)
    if gray.ndim == 3:
        gray = gray[..., :3].mean(axis=-1)
    if sigma_px:
        gray = ndi.gaussian_filter(gray, sigma_px)
    values = ndi.map_coordinates(gray, coords, order=1, mode="constant", cval=np.nan)
    valid &= np.isfinite(values)
    counts = valid.sum(axis=1)
    enough = counts >= np.ceil(min_fraction * xy.shape[1])
    if coverage_policy == "origin_connected":
        inside = np.logical_and.accumulate(enough)
    elif coverage_policy == "last_supported_run":
        inside = np.zeros(len(enough), bool)
        supported = np.flatnonzero(enough)
        if len(supported):
            stop = supported[-1] + 1
            gaps = np.flatnonzero(~enough[:stop])
            start = gaps[-1] + 1 if len(gaps) else 0
            inside[start:stop] = True
    else:
        raise ValueError("Unknown strip coverage policy")
    mean = np.divide(
        np.where(valid, values, 0).sum(axis=1),
        counts,
        out=np.full(len(path_xy), np.nan),
        where=inside,
    )
    return mean, counts, inside

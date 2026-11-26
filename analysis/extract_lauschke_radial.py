# SPDX-License-Identifier: MIT
"""COM-anchored radial re-extraction of Lauschke 2013 Supplementary Video 5.

The geometry is a locally reviewed proxy, not an author-deposited AP coordinate.
Only geometry estimation is filtered; sampled video intensities are unchanged.
"""

from pathlib import Path
import argparse
import hashlib
import json

import av
import numpy as np
from scipy import ndimage as ndi
import scipy

from paths import ASSET_ROOT
from extract_video_kymographs import decode, feature, displacement

MOVIE_SHA = "04b7cad440c786080b2e50ec4ef041e5ebac0e66aea87dfa3c68961900ecbb2b"
REFERENCE_SHA = "d5f15bc642115155ec1eb641f3d199c7b7f41d0645bba46d9cb5eb1014925ab8"
UM_PER_PX = 100 / 105
ANGLE_DEG = 45.0  # Image coordinates: right=0 degrees, down=90 degrees.
WIDTH_PX = 20
RADIUS_PX = 400


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def largest_filled(mask):
    labels, _ = ndi.label(mask)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    if sizes.max() == 0:
        raise ValueError("No tissue component")
    return ndi.binary_fill_holes(labels == sizes.argmax())


def mask_centroid(mask):
    """Uniform-area centroid, never the reporter intensity-weighted centroid."""
    y, x = ndi.center_of_mass(mask.astype(bool))
    if not np.isfinite([x, y]).all():
        raise ValueError("Empty tissue mask")
    return np.array([x, y])


def estimate_geometry(frames, references, support_threshold=20, texture_threshold=18):
    features = [feature(f) for f in references]
    increments = np.array(
        [np.zeros(2)]
        + [displacement(a, b) for a, b in zip(features[:-1], features[1:])]
    )
    if np.max(np.abs(increments)) >= 11:
        raise ValueError("Structural registration reached search bound")
    shifts = increments.cumsum(axis=0)
    # A single time-independent support prevents a moving fluorescence peak
    # from becoming a per-frame tissue/COM measurement. It is still reporter-
    # informed, so weak tissue and support-threshold dependence are documented.
    registered = np.stack(
        [
            ndi.shift(f[..., 1].astype(float), [-s[1], -s[0]], order=1, cval=np.nan)
            for f, s in zip(frames, shifts)
        ]
    )
    support = ndi.gaussian_filter(np.nanmedian(registered, axis=0), 10)
    support = support > support_threshold
    support[:15] = False
    support[680:] = False  # Scale bar and burned-in timestamps are excluded.
    support[:, :15] = False
    support[:, 735:] = False
    support = largest_filled(support)
    centers, masks = [], []
    for f, shift in zip(references, shifts):
        g = ndi.shift(
            f[..., 0].astype(float), [-shift[1], -shift[0]], order=1, cval=100
        )
        variance = ndi.uniform_filter(g * g, 15) - ndi.uniform_filter(g, 15) ** 2
        texture = ndi.gaussian_filter(np.sqrt(np.maximum(variance, 0)), 5)
        body = largest_filled(texture > texture_threshold) & support
        body = largest_filled(body)
        centers.append(mask_centroid(body) + shift)
        masks.append(ndi.shift(body.astype(float), [shift[1], shift[0]], order=0) > 0.5)
    return np.array(centers), np.array(masks), shifts, support


def sample_radial(frames, centers, masks, angle_deg=ANGLE_DEG, width_px=WIDTH_PX):
    """A finite-width straight radius: valid tissue only, no background filling."""
    radius = np.arange(RADIUS_PX + 1, dtype=float)
    angle = np.deg2rad(angle_deg)
    direction = np.array([np.cos(angle), np.sin(angle)])
    normal = np.array([-direction[1], direction[0]])
    offsets = np.arange(-width_px // 2, width_px // 2 + 1)
    columns, counts = [], []
    for frame, center, mask in zip(frames, centers, masks):
        xy = (
            center + radius[:, None, None] * direction + offsets[None, :, None] * normal
        )
        coordinates = [xy[..., 1], xy[..., 0]]
        values = ndi.map_coordinates(
            frame[..., 1].astype(float),
            coordinates,
            order=1,
            mode="constant",
            cval=np.nan,
        )
        valid = (
            ndi.map_coordinates(
                mask.astype(float), coordinates, order=0, mode="constant", cval=0
            )
            > 0.5
        ) & np.isfinite(values)
        count = valid.sum(axis=1)
        # End the radius at its first tissue exit; do not jump across a gap
        # to an isolated cell or a second disconnected structure.
        inside = np.logical_and.accumulate(count >= np.ceil(0.75 * len(offsets)))
        profile = np.divide(
            np.where(valid, values, 0).sum(axis=1),
            count,
            out=np.full(len(radius), np.nan),
            where=inside,
        )
        columns.append(profile)
        counts.append(np.where(inside, count, 0))
    return np.stack(columns, axis=1), np.stack(counts, axis=1)


def audit_figure(frames, references, centers, masks, matrix, out):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "sans-serif", "font.size": 10})
    fig, axes = plt.subplots(2, 3, figsize=(11.4, 8.4))
    direction = np.array([np.cos(np.pi / 4), np.sin(np.pi / 4)])
    normal = np.array([-direction[1], direction[0]])
    for j, i in enumerate([0, 30, 60]):
        radius = np.flatnonzero(np.isfinite(matrix[:, i]))[-1]
        center, end = centers[i], centers[i] + radius * direction
        for row, image in enumerate([references[i], frames[i]]):
            ax = axes[row, j]
            ax.imshow(image)
            ax.contour(masks[i], levels=[0.5], colors=["#74cce0"], linewidths=0.8)
            a, b = center, end
            corners = np.array(
                [
                    a + WIDTH_PX / 2 * normal,
                    b + WIDTH_PX / 2 * normal,
                    b - WIDTH_PX / 2 * normal,
                    a - WIDTH_PX / 2 * normal,
                ]
            )
            ax.fill(corners[:, 0], corners[:, 1], facecolor="#ffae43", alpha=0.22)
            ax.annotate(
                "",
                xy=end,
                xytext=center,
                arrowprops={"arrowstyle": "->", "color": "#ffae43", "lw": 2},
            )
            ax.plot(*center, marker="+", color="white", ms=12, mew=1.8)
            ax.text(
                center[0] - 12,
                center[1] - 20,
                "COM / P*",
                color="white",
                ha="center",
                bbox={"facecolor": "black", "alpha": 0.6, "pad": 2},
            )
            ax.text(
                end[0] + 5,
                end[1] + 12,
                "A*",
                color="#ffcf77",
                bbox={"facecolor": "black", "alpha": 0.6, "pad": 2},
            )
            ax.set_title(f"{'Brightfield' if row == 0 else 'LuVeLu'} · {i / 6:g} h")
            ax.axis("off")
    fig.suptitle(
        "Lauschke 2013 · geometry and radial sampling",
        x=0.04,
        ha="left",
        fontsize=15,
        weight="bold",
    )
    fig.text(
        0.04,
        0.055,
        "Cyan: tissue mask   +: area centroid   Orange: radial strip toward the periphery",
        color="#535d6b",
    )
    fig.text(
        0.04,
        0.025,
        "P*: center-side proxy; A*: outward direction. No anatomical marker or cell tracking is inferred.",
        color="#535d6b",
    )
    fig.subplots_adjust(
        left=0.025, right=0.985, bottom=0.10, top=0.93, wspace=0.035, hspace=0.08
    )
    for fmt in ["png", "pdf"]:
        fig.savefig(out / ("video5-radial-roi." + fmt), dpi=200)
    fig.savefig(out / "video5-roi.jpg", dpi=180)
    plt.close(fig)


def run(movie, reference):
    if sha(movie) != MOVIE_SHA or sha(reference) != REFERENCE_SHA:
        raise ValueError("Source hash differs from reviewed Video 5 / matching Video 4")
    frames, references = np.array(decode(movie)), np.array(decode(reference))
    assert frames.shape == references.shape == (61, 742, 749, 3)
    centers, masks, shifts, support = estimate_geometry(frames, references)
    matrix, counts = sample_radial(frames, centers, masks)
    times = np.arange(61) / 6
    radius = np.arange(matrix.shape[0]) * UM_PER_PX
    assert np.isfinite(matrix[0]).all() and not np.isinf(matrix).any()
    assert np.nanmin(matrix) >= 0 and np.nanmax(matrix) <= 255
    out = ASSET_ROOT / "data/derived/lauschke-2013"
    figures = ASSET_ROOT / "figures/lauschke-2013"
    out.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out / "video5-kymograph.npz",
        intensity=matrix,
        time_h=times,
        position_um=radius,
        centers_xy=centers,
        shifts_xy=shifts,
        valid_width_counts=counts,
    )
    np.savez_compressed(
        out / "video5-geometry.npz",
        tissue_masks=masks,
        reference_support=support,
        centers_xy=centers,
        shifts_xy=shifts,
    )
    for name, array, header in [
        ("video5-intensity", matrix, ""),
        ("video5-time-h", times, "time_h"),
        ("video5-position-um", radius, "radial_distance_um"),
        (
            "video5-centers-xy",
            np.c_[times, centers, shifts],
            "time_h,center_x_px,center_y_px,drift_x_px,drift_y_px",
        ),
    ]:
        np.savetxt(
            out / (name + ".csv"),
            array,
            delimiter=",",
            header=header,
            comments="",
            fmt="%.9g",
        )
    alternatives = {
        f"angle_{a}": sample_radial(frames, centers, masks, a)[0] for a in [35, 55]
    }
    sensitivity = {}
    for threshold in [10, 30]:
        other_centers, _, _, _ = estimate_geometry(frames, references, threshold)
        sensitivity[str(threshold)] = {
            "max_center_offset_px": float(
                np.linalg.norm(other_centers - centers, axis=1).max()
            ),
            "median_center_offset_px": float(
                np.median(np.linalg.norm(other_centers - centers, axis=1))
            ),
        }
    np.savez_compressed(
        out / "video5-angle-sensitivity.npz",
        **alternatives,
        time_h=times,
        position_um=radius,
    )
    audit_figure(frames, references, centers, masks, matrix, figures)
    trace = {
        "paper_id": "lauschke-2013",
        "method_version": "radial-com-v1",
        "source_url": "https://static-content.springer.com/esm/art%3A10.1038%2Fnature11804/MediaObjects/41586_2013_BFnature11804_MOESM296_ESM.mov",
        "source_movie_sha256": MOVIE_SHA,
        "reference_movie_sha256": REFERENCE_SHA,
        "source_movie_filename": Path(movie).name,
        "reference_movie_filename": Path(reference).name,
        "channel": "LuVeLu / original decoded green video display channel",
        "shape_space_time": list(matrix.shape),
        "all_frames_used": 61,
        "time_basis": "10 min acquisition; source overlays 0–10 h; not movie playback time",
        "time_range_h": [0, 10],
        "pixel_scale_um": UM_PER_PX,
        "scale_bar": {
            "length_um": 100,
            "length_video_px": 105,
            "endpoints_xy": [[27, 694], [132, 694]],
            "measurement_precision_px": 1,
        },
        "spatial_reference": "r=0 at uniform-area COM of reviewed tissue support, increasing toward outer rim; center-side P proxy to outward A direction",
        "roi": {
            "angle_deg_image_x_right_y_down": ANGLE_DEG,
            "width_px": WIDTH_PX,
            "width_samples": WIDTH_PX + 1,
            "radius_max_px": RADIUS_PX,
            "edge_rule": "first radius with <75% valid width terminates profile; remainder NaN",
        },
        "geometry": {
            "support": "single Gaussian10-smoothed temporal median of BF-registered green-channel images, threshold20; largest filled component; remove labels/borders",
            "tissue_mask": "BF local SD window15, Gaussian5 for geometry only, threshold18; intersect fixed support; largest filled component",
            "center": "uniform binary-mask area centroid, NOT fluorescence intensity center of mass",
            "drift": "adjacent-frame phase correlation of matched BF texture; then per-frame mask centroid",
            "center_trajectory": "video5-centers-xy.csv",
            "masks": "video5-geometry.npz",
        },
        "sampling": "bilinear original video green values across a 20 px strip, tissue-only width mean; no temporal filtering, detrending, phase inference or intensity correction",
        "missing_values": int(np.isnan(matrix).sum()),
        "normalization": "full-record finite min-max for display only, grey outside mask",
        "sensitivity": {
            "support_threshold_display_units": sensitivity,
            "neighbor_angles_deg": [35, 55],
            "arrays": "video5-angle-sensitivity.npz",
        },
        "method_evidence": {
            "url": "https://www.mcgill.ca/francois-group/files/francois-group/nature_2013_lauschke.pdf",
            "section": "Image processing; Parameter measurements",
            "retrieval": "search-index text verified; direct author PDF currently returns 404",
            "summary": "Published kymographs follow a line from oscillation center to periphery, perpendicular to wavefront; original analysis additionally filtered/detrended and estimated phase. This is a new independent intensity extraction, not that phase analysis.",
        },
        "limitations": [
            "Geometric COM is a reviewed center-side proxy, not a measured posterior fate marker or a fitted oscillation source.",
            "A single temporal-median reporter support excludes sparse/outside pixels; mask threshold affects COM. It does not establish the complete tissue boundary.",
            "This explant is already isolated tailbud-derived tissue; no intact embryo AP axis or new physical tail cut is inferred.",
            "Radial angle is manually reviewed; nearby 35/55-degree extractions are supplied, not selected for best-looking waves.",
            "COM registration is translational, not rotation/deformation correction or material cell tracking.",
            "Compressed 8-bit projected/median-filtered display movie is not raw fluorescence; absolute amplitudes cannot be compared.",
        ],
        "license": "Nature copyright; no open derivative license verified.",
        "script": "analysis/extract_lauschke_radial.py",
        "script_sha256": sha(__file__),
        "libraries": {
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "av": av.__version__,
        },
    }
    (out / "extraction-provenance.json").write_text(json.dumps(trace, indent=2) + "\n")
    print(
        json.dumps(
            {
                "shape": matrix.shape,
                "center_first_xy": centers[0].tolist(),
                "center_last_xy": centers[-1].tolist(),
                "missing": int(np.isnan(matrix).sum()),
                "sensitivity": sensitivity,
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    args = parser.parse_args()
    run(
        args.source_dir / "41586_2013_BFnature11804_MOESM296_ESM.mov",
        args.source_dir / "41586_2013_BFnature11804_MOESM295_ESM.mov",
    )


if __name__ == "__main__":
    main()

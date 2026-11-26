# SPDX-License-Identifier: MIT
"""Detail-only per-frame spatial control at the saved Video 5 wavefront ROI.

Never refits the center or modifies primary/COM arrays. Gaussian convolution
uses normalized tissue weights, so excluded pixels are not zero observations.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import scipy
from scipy import ndimage as ndi

from paths import ASSET_ROOT
from extract_video_kymographs import decode
from extract_lauschke_radial import MOVIE_SHA, UM_PER_PX, sample_radial

SIGMA_UM = 9.66
DATA_DIR = Path("data/derived/lauschke-2013/video5-spatial-review")
FIGURE_DIR = Path("figures/lauschke-2013/video5-spatial-review")
STEM = "video5-wavefront-spatial-comparison"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def masked_gaussian_frame(signal, mask, sigma_px):
    """Independent x/y normalized convolution; no outside-mask signal leakage."""
    signal, mask = np.asarray(signal, float), np.asarray(mask, bool)
    if (
        signal.ndim != 2
        or signal.shape != mask.shape
        or not np.isfinite(sigma_px)
        or sigma_px <= 0
    ):
        raise ValueError("Expected matching 2D frame/mask and positive spatial sigma")
    valid = mask & np.isfinite(signal)
    denominator = ndi.gaussian_filter(
        valid.astype(float), sigma_px, mode="constant", cval=0.0, truncate=4.0
    )
    numerator = ndi.gaussian_filter(
        np.where(valid, signal, 0.0), sigma_px, mode="constant", cval=0.0, truncate=4.0
    )
    return np.divide(
        numerator, denominator, out=np.full_like(signal, np.nan), where=denominator > 0
    )


def spatial_control(
    frames, origins, masks, sigma_um=SIGMA_UM, um_per_px=UM_PER_PX, *, channel_index=1
):
    """Filter one explicitly selected display channel per source frame."""
    frames, origins, masks = np.asarray(frames), np.asarray(origins), np.asarray(masks)
    if (
        frames.ndim != 4
        or frames.shape[-1] != 3
        or masks.shape != frames.shape[:3]
        or origins.shape != (len(frames), 2)
        or not np.isfinite(origins).all()
        or not np.isfinite(um_per_px)
        or um_per_px <= 0
    ):
        raise ValueError(
            "Expected RGB frames, saved x/y origins and matched tissue masks"
        )
    if type(channel_index) is not int or channel_index not in (0, 1, 2):
        raise ValueError("RGB channel index must be 0, 1 or 2")
    columns, counts = [], []
    for frame, origin, mask in zip(frames, origins, masks):
        filtered = masked_gaussian_frame(
            frame[..., channel_index], mask, sigma_um / um_per_px
        )
        # sample_radial reads channel1; this is a view, not a new RGB estimator.
        green_view = np.broadcast_to(filtered[..., None], filtered.shape + (3,))
        matrix, width_counts = sample_radial([green_view], [origin], [mask])
        columns.append(matrix[:, 0])
        counts.append(width_counts[:, 0])
    return np.stack(columns, axis=1), np.stack(counts, axis=1)


def edges(values):
    return np.r_[
        values[0] - (values[1] - values[0]) / 2,
        (values[:-1] + values[1:]) / 2,
        values[-1] + (values[-1] - values[-2]) / 2,
    ]


def render(
    raw,
    smooth,
    times,
    positions,
    limits,
    destination,
    *,
    stem=STEM,
    distance_label="Distance from fitted center (µm)",
    geometry_note="Same fitted origins, 45° ray, 20 px strip, 61 frames and measurement mask; unchanged raw-primary color scale.",
):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans", "sans-serif"],
            "font.size": 10,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "text.color": "#252936",
            "axes.labelcolor": "#535d6b",
            "xtick.color": "#677285",
            "ytick.color": "#677285",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig = plt.figure(figsize=(11.4, 5.4))
    axes = [
        fig.add_axes([0.07, 0.22, 0.34, 0.65]),
        fig.add_axes([0.50, 0.22, 0.34, 0.65]),
    ]
    cmap = matplotlib.colormaps["OrRd"].copy()
    cmap.set_bad("#f1f3f6")
    low, high = limits
    for ax, matrix, title in zip(
        axes, [raw, smooth], ["1  Unsmoothed", "2  Spatial filter"]
    ):
        mesh = ax.pcolormesh(
            edges(times),
            edges(positions),
            np.ma.masked_invalid((matrix - low) / (high - low)),
            cmap=cmap,
            norm=Normalize(0, 1),
            shading="flat",
            rasterized=True,
        )
        ax.set_xlim(times[0], times[-1])
        ax.set_ylim(positions[0], positions[-1])
        ax.set_xlabel("Time (h)")
        ax.set_ylabel(distance_label)
        ax.set_title(title, loc="left", fontsize=12, weight="bold", pad=12)
    bar = fig.colorbar(
        mesh, cax=fig.add_axes([0.90, 0.22, 0.016, 0.65]), ticks=[0, 0.5, 1]
    )
    bar.set_label("Relative display intensity · shared primary scale")
    bar.outline.set_visible(False)
    fig.text(0.07, 0.105, geometry_note, fontsize=9, color="#677285")
    fig.text(
        0.07,
        0.063,
        "Spatial control: per-frame masked Gaussian σ = 9.66 µm (10.143 source px); no temporal filtering.",
        fontsize=9,
        color="#677285",
    )
    fig.text(
        0.07,
        0.021,
        "Gray = missing. Regional A/P direction does not identify an exact anatomical boundary or oscillator source.",
        fontsize=9,
        color="#677285",
    )
    destination.mkdir(parents=True, exist_ok=True)
    for fmt in ["svg", "png", "pdf"]:
        fig.savefig(destination / (stem + "." + fmt), dpi=180)
    plt.close(fig)


def run(source_dir, output_root):
    data = ASSET_ROOT / "data/derived/lauschke-2013"
    input_path = data / "video5-wavefront-comparison.npz"
    geometry = data / "video5-geometry.npz"
    movie = source_dir / "41586_2013_BFnature11804_MOESM296_ESM.mov"
    protected = [p for p in data.glob("video5*") if p.is_file()]
    protected += [
        p for p in (ASSET_ROOT / "figures/lauschke-2013").glob("video5*") if p.is_file()
    ]
    protected += [
        p
        for p in (ASSET_ROOT / "figures/comparison").glob("lauschke-2013-full.*")
        if p.is_file()
    ]
    before = {str(p): digest(p) for p in protected}
    if digest(movie) != MOVIE_SHA:
        raise ValueError("Unexpected Video5 source hash")
    frames = np.asarray(decode(movie))
    if frames.shape != (61, 742, 749, 3):
        raise ValueError("Unexpected Video5 frame shape")
    with np.load(input_path) as f:
        raw = f["intensity"].copy()
        origins = f["origins_xy"].copy()
        directions = f["directions_xy"].copy()
        times = f["time_h"].copy()
        positions = f["position_um"].copy()
        counts = f["valid_width_counts"].copy()
    with np.load(geometry) as f:
        masks = f["tissue_masks"].copy()
        shifts = f["shifts_xy"].copy()
    # Confirm this is the promoted geometric fit, not oldCOM or a new fit.
    center_report = json.loads((data / "video5-wavefront-center.json").read_text())
    np.testing.assert_allclose(
        origins - shifts,
        np.tile(center_report["center_xy_reference_px"], (61, 1)),
        rtol=0,
        atol=1e-10,
    )
    np.testing.assert_allclose(
        directions, np.tile(np.array([1.0, 1.0]) / np.sqrt(2), (61, 1)), rtol=0, atol=0
    )
    np.testing.assert_allclose(positions, np.arange(401) * UM_PER_PX, rtol=0, atol=0)
    rebuilt, rebuilt_counts = sample_radial(frames, origins, masks)
    np.testing.assert_allclose(rebuilt, raw, rtol=0, atol=0, equal_nan=True)
    np.testing.assert_array_equal(rebuilt_counts, counts)
    smooth, smooth_counts = spatial_control(frames, origins, masks)
    np.testing.assert_array_equal(smooth_counts, counts)
    np.testing.assert_array_equal(np.isfinite(smooth), np.isfinite(raw))
    limits = np.array([np.nanmin(raw), np.nanmax(raw)])
    recs = output_root / DATA_DIR
    figs = output_root / FIGURE_DIR
    recs.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        recs / (STEM + ".npz"),
        intensity=raw,
        spatial_smoothed_intensity=smooth,
        time_h=times,
        position_um=positions,
        origins_xy=origins,
        directions_xy=directions,
        shifts_xy=shifts,
        valid_width_counts=counts,
        spatial_valid_width_counts=smooth_counts,
        measurement_valid_mask=np.isfinite(raw),
        shared_color_limits=limits,
        sigma_um=SIGMA_UM,
        sigma_px=SIGMA_UM / UM_PER_PX,
    )
    render(raw, smooth, times, positions, limits, figs)
    finite = smooth[np.isfinite(smooth)]
    report = {
        "dataset": "lauschke-2013",
        "method_version": "video5-fitted-spatial-control-v1",
        "checked": "2026-11-15",
        "source": {
            "movie": movie.name,
            "sha256": MOVIE_SHA,
            "shape_t_y_x_c": list(frames.shape),
            "channel": "green display channel (index1); not raw fluorescence",
        },
        "saved_primary": {
            "path": str(input_path.relative_to(ASSET_ROOT)),
            "sha256": before[str(input_path)],
            "key": "intensity",
            "reproduced_exactly": True,
        },
        "geometry": {
            "record": "data/derived/lauschke-2013/video5-wavefront-center.json",
            "masks_path": str(geometry.relative_to(ASSET_ROOT)),
            "masks_sha256": before[str(geometry)],
            "center_refit": False,
            "origins_and_directions": "saved current wavefront-fit arrays, unchanged",
            "angle_image_deg": 45.0,
            "width_px": 20,
            "transverse_samples": 21,
            "minimum_valid_count": 16,
            "first_exit_rule": "unchanged sample_radial; terminate at first insufficient-width distance",
        },
        "filter": {
            "method": "normalized masked Gaussian convolution in each source frame x/y, then bilinear strip sampling",
            "sigma_um": SIGMA_UM,
            "um_per_source_px": UM_PER_PX,
            "sigma_px": SIGMA_UM / UM_PER_PX,
            "truncate_sigma": 4.0,
            "boundary_mode": "constant zero weight, not zero-valued observations",
            "normalization": "G(signal × valid)/G(valid), valid=tissue mask AND finite signal; pixels without support remainNaN",
            "post_filter_measurement_mask": "original tissue/FOV/width validity; filtering does not add measured positions",
            "temporal_filter": False,
            "temporal_baseline": False,
            "phase": False,
            "parameter_status": "first explicit working spatial control, not universal optimal sigma",
        },
        "coordinates": {
            "shape_space_time": list(raw.shape),
            "time_h": times.tolist(),
            "position_um": positions.tolist(),
            "time_range_h": [float(times[0]), float(times[-1])],
            "space_range_um": [float(positions[0]), float(positions[-1])],
        },
        "verification": {
            "raw_matrix_exact": True,
            "coordinates_and_geometry_copied_exactly": True,
            "same_width_counts": bool(np.array_equal(counts, smooth_counts)),
            "same_missing_mask": True,
            "missing_samples": int(np.isnan(raw).sum()),
            "original_files_unchanged": True,
            "no_COM_smooth_reuse": True,
        },
        "display": {
            "shared_raw_primary_limits": limits.tolist(),
            "smooth_finite_limits": [float(finite.min()), float(finite.max())],
            "below_raw_scale": int((finite < limits[0]).sum()),
            "above_raw_scale": int((finite > limits[1]).sum()),
            "normalization": "both panels use unchanged full raw-primary min/max, not COM-pair limits or separately rescaled smooth limits",
            "A_above_P": True,
            "zero": "bottom",
            "flip_y": False,
            "plot_axes": ["axes_1", "axes_2"],
            "colorbar_axes": ["axes_3"],
        },
        "limitations": [
            "Saved masks are existing analysis masks, not newly validated anatomy.",
            "A geometric center is not proven biological oscillator source.",
            "Spatial smoothing changes local contrast and can blur narrow fronts; no optimal bandwidth claim.",
            "Translation does not track cells or deformation.",
            "Source display compression and green display values are retained, not raw expression.",
        ],
        "script_sha256": digest(__file__),
        "versions": {"numpy": np.__version__, "scipy": scipy.__version__},
        "reproduce": "work/plot-env/bin/python analysis/compare_lauschke_video5_spatial.py --source-dir assets/data/source-archive/lauschke-2013 --output-root outputs/video5-spatial-review/assets",
    }
    assert all(digest(Path(path)) == value for path, value in before.items())
    (recs / (STEM + ".json")).write_text(json.dumps(report, indent=2) + "\n")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    (output_root.parent / "preservation.json").write_text(
        json.dumps(before, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "raw_exact": True,
                "same_mask": True,
                "missing": int(np.isnan(raw).sum()),
                "sigma_px": SIGMA_UM / UM_PER_PX,
                "primary_limits": limits.tolist(),
                "smooth_limits": [float(finite.min()), float(finite.max())],
                "originals_unchanged": len(before),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    run(args.source_dir, args.output_root)

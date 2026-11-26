# SPDX-License-Identifier: MIT
"""Detail-only Mesp2 per-frame spatial control with unchanged primary data."""

import argparse
import json
from pathlib import Path

import numpy as np
import scipy

from paths import ASSET_ROOT
from extract_video_kymographs import decode
from extract_lauschke_mesp2 import SOURCES, extract_red, sha
from extract_lauschke_radial import UM_PER_PX
from compare_lauschke_video5_spatial import SIGMA_UM, spatial_control, render

DATA_DIR = Path("data/derived/lauschke-2013/video6-mesp2-spatial")
FIGURE_DIR = Path("figures/lauschke-2013/video6-mesp2-spatial")
STEM = "video6-mesp2-spatial-comparison"


def run(source_dir, output_root):
    source = source_dir / "41586_2013_BFnature11804_MOESM297_ESM.mov"
    if sha(source) != SOURCES[6][1]:
        raise ValueError("Unexpected Video 6 source")
    input_path = (
        ASSET_ROOT
        / "data/derived/lauschke-2013/video6-mesp2/video6-mesp2-kymograph.npz"
    )
    geometry = ASSET_ROOT / "data/derived/lauschke-2013/video5-geometry.npz"
    protected = [input_path, geometry]
    protected.extend((ASSET_ROOT / "data/derived/lauschke-2013/video6-mesp2").glob("*"))
    protected.extend((ASSET_ROOT / "figures/lauschke-2013/video6-mesp2").glob("*"))
    before = {str(p): sha(p) for p in protected if p.is_file()}
    frames = np.asarray(decode(source))
    if frames.shape != (61, 742, 749, 3):
        raise ValueError("Unexpected Video 6 dimensions")
    with np.load(input_path) as f:
        raw = f["intensity"].copy()
        origins = f["origins_xy"].copy()
        directions = f["directions_xy"].copy()
        times = f["time_h"].copy()
        positions = f["position_um"].copy()
        counts = f["valid_width_counts"].copy()
    with np.load(geometry) as f:
        masks = f["tissue_masks"].copy()
    np.testing.assert_allclose(
        directions, np.tile(np.array([1.0, 1.0]) / np.sqrt(2), (61, 1)), rtol=0, atol=0
    )
    np.testing.assert_allclose(positions, np.arange(401) * UM_PER_PX, rtol=0, atol=0)
    np.testing.assert_allclose(times, np.arange(61) / 6, rtol=0, atol=0)
    rebuilt, rebuilt_counts = extract_red(frames, origins, masks)
    np.testing.assert_allclose(rebuilt, raw, rtol=0, atol=0, equal_nan=True)
    np.testing.assert_array_equal(rebuilt_counts, counts)
    smooth, smooth_counts = spatial_control(frames, origins, masks, channel_index=0)
    np.testing.assert_array_equal(counts, smooth_counts)
    np.testing.assert_array_equal(np.isfinite(raw), np.isfinite(smooth))
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
        valid_width_counts=counts,
        spatial_valid_width_counts=smooth_counts,
        measurement_valid_mask=np.isfinite(raw),
        shared_color_limits=limits,
        sigma_um=SIGMA_UM,
        sigma_px=SIGMA_UM / UM_PER_PX,
    )
    render(
        raw,
        smooth,
        times,
        positions,
        limits,
        figs,
        stem=STEM,
        distance_label="Distance from paired center (µm)",
        geometry_note="Same paired origins, 45° ray, 20 px strip, 61 frames and measurement mask; unchanged Mesp2-primary scale.",
    )
    finite = smooth[np.isfinite(smooth)]
    report = {
        "dataset": "lauschke-2013-mesp2",
        "method_version": "video6-mesp2-spatial-control-v1",
        "source": {
            "movie": source.name,
            "sha256": SOURCES[6][1],
            "channel_index": 0,
            "channel": "Mesp2-GFP red pseudo-colored display; not the green channel or raw GFP counts",
        },
        "saved_primary": {
            "path": str(input_path.relative_to(ASSET_ROOT)),
            "sha256": before[str(input_path)],
            "key": "intensity",
            "reproduced_exactly": True,
        },
        "geometry": {
            "path": str(geometry.relative_to(ASSET_ROOT)),
            "sha256": before[str(geometry)],
            "origins": "unchanged saved paired LuVeLu centers and BF translation",
            "angle_image_deg": 45.0,
            "width_px": 20,
            "transverse_samples": 21,
            "minimum_valid_count": 16,
            "center_refit": False,
            "same_first_exit_rule": True,
        },
        "filter": {
            "method": "normalized masked Gaussian in each source frame x/y, then same bilinear strip sampling",
            "sigma_um": SIGMA_UM,
            "sigma_px": SIGMA_UM / UM_PER_PX,
            "truncate_sigma": 4.0,
            "normalization": "G(red × valid)/G(valid); valid=existing tissue mask AND finite red display values",
            "boundary_mode": "constant zero weight, not zero-valued observations",
            "post_filter_measurement_mask": "original tissue/FOV/width counts; no new measured positions",
            "temporal_filter": False,
            "temporal_baseline": False,
            "phase": False,
            "parameter_basis": "same explicit physical spatial control as Video 5, not an optimized Mesp2 bandwidth",
        },
        "verification": {
            "raw_matrix_exact": True,
            "same_width_counts": True,
            "same_missing_mask": True,
            "missing_samples": int(np.isnan(raw).sum()),
            "frames": 61,
            "shape_space_time": list(raw.shape),
        },
        "display": {
            "shared_color_limits": limits.tolist(),
            "smooth_finite_limits": [float(finite.min()), float(finite.max())],
            "below_raw_scale": int((finite < limits[0]).sum()),
            "above_raw_scale": int((finite > limits[1]).sum()),
            "normalization": "both panels use the full original Mesp2-primary min/max, independently from LuVeLu",
            "A_above_P": True,
            "zero": "bottom",
            "flip_y": False,
            "plot_axes": ["axes_1", "axes_2"],
            "colorbar_axes": ["axes_3"],
        },
        "limitations": [
            "Mesp2 is a segmentation marker; smoothing does not establish sustained oscillation.",
            "Spatial smoothing may blur narrow stripes; this sigma is a working comparison, not a universal optimum.",
            "Existing reporter-informed masks, paired-center and translation limitations remain.",
            "Pseudo-colored compressed display levels are not raw expression or cross-gene calibrated intensity.",
        ],
        "scripts": {
            Path(__file__).name: sha(__file__),
            "compare_lauschke_video5_spatial.py": sha(
                Path(__file__).with_name("compare_lauschke_video5_spatial.py")
            ),
        },
        "versions": {"numpy": np.__version__, "scipy": scipy.__version__},
        "reproduce": "python analysis/compare_lauschke_mesp2_spatial.py --source-dir assets/data/source-archive/lauschke-2013 --output-root outputs/video6-mesp2-spatial/assets",
    }
    assert all(sha(path) == value for path, value in before.items())
    report["verification"]["original_files_unchanged"] = True
    (recs / (STEM + ".json")).write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "raw_exact": True,
                "same_mask": True,
                "missing": int(np.isnan(raw).sum()),
                "sigma_um": SIGMA_UM,
                "sigma_px": SIGMA_UM / UM_PER_PX,
                "raw_limits": limits.tolist(),
                "smooth_limits": report["display"]["smooth_finite_limits"],
                "protected_files": len(before),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    run(args.source_dir, args.output_root)

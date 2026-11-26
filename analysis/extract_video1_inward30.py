# SPDX-License-Identifier: MIT
"""Extract the selected fixed-reference, inward-30px Video 1 review kymograph.

Uses the exact saved candidate, inverse-mapped into original source pixels.
The gallery primary remains untouched. Foreground is a display-derived proxy,
not verified anatomical PSM segmentation; see the saved review limitations.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from curved_strip import sample_strip
from paths import ASSET_ROOT
from review_video1_stable_roi import (
    A_REF,
    P_REF,
    SCALE,
    SOURCE_HASH,
    WIDTH,
    digest,
    transform,
)


def resample_saved_curve(path, normal, position_um):
    """Interpolate the saved 2µm-spaced geometry, without a new curve fit.

    Arc length is the measured length of its saved polyline, not a normalized
    path coordinate. Reviewed unit normals are interpolated and renormalized.
    No extrapolation beyond the selected A endpoint is allowed.
    """
    path = np.asarray(path, float)
    normal = np.asarray(normal, float)
    position_um = np.asarray(position_um, float)
    if (
        path.shape != normal.shape
        or path.ndim != 2
        or path.shape[1] != 2
        or len(path) < 2
        or not np.isfinite(path).all()
        or not np.isfinite(normal).all()
        or np.any(position_um < 0)
        or not np.isfinite(position_um).all()
    ):
        raise ValueError("Finite paired xy geometry and nonnegative distances required")
    distance = (
        np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))] * SCALE
    )
    if np.any(np.diff(distance) <= 0):
        raise ValueError("Distinct saved vertices required")
    xy = np.column_stack([np.interp(position_um, distance, path[:, j]) for j in [0, 1]])
    nn = np.column_stack(
        [np.interp(position_um, distance, normal[:, j]) for j in [0, 1]]
    )
    nn /= np.linalg.norm(nn, axis=1, keepdims=True)
    outside = position_um > distance[-1]
    xy[outside] = np.nan
    nn[outside] = np.nan
    return xy, nn, float(distance[-1])


def to_source_geometry(path_ref, normal_ref, source_to_reference):
    inverse = np.linalg.inv(source_to_reference)
    return transform(path_ref, inverse), normal_ref @ inverse[:2, :2].T


def heat(ax, matrix, position, times, limits, title, ymax):
    import matplotlib
    from matplotlib.colors import Normalize

    cmap = matplotlib.colormaps["OrRd"].copy()
    cmap.set_bad("#edf0f4")
    edges_t = np.r_[
        times[0] - (times[1] - times[0]) / 2,
        (times[:-1] + times[1:]) / 2,
        times[-1] + (times[-1] - times[-2]) / 2,
    ]
    step = position[1] - position[0]
    edges_y = np.r_[
        position[0] - step / 2,
        (position[:-1] + position[1:]) / 2,
        position[-1] + step / 2,
    ]
    mesh = ax.pcolormesh(
        edges_t,
        edges_y,
        np.ma.masked_invalid((matrix - limits[0]) / (limits[1] - limits[0])),
        cmap=cmap,
        norm=Normalize(0, 1),
        shading="flat",
        rasterized=True,
    )
    ax.set_facecolor("#edf0f4")
    ax.set_ylim(0, ymax)
    ax.set_xlim(times[0], times[-1])
    ax.set_xlabel("Time (h)")
    ax.set_title(title, loc="left", fontsize=11, pad=13)
    ax.set_yticks(np.arange(0, ymax + 1, 100))
    ax.set_xticks([0, 5, 10, 15, 20])
    # Regional orientation, not an assertion that y=max is an exact A endpoint.
    ax.text(-0.13, 1.01, "A", transform=ax.transAxes, fontsize=10, color="#525b6b")
    ax.text(-0.13, -0.01, "P", transform=ax.transAxes, fontsize=10, color="#525b6b")
    return mesh


def render_comparison(output, name, arrays, positions, times, limits, titles, footnote):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 10,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": "#525b6b",
            "xtick.color": "#697386",
            "ytick.color": "#697386",
            "axes.edgecolor": "#9198a6",
        }
    )
    fig, axs = plt.subplots(1, 2, figsize=(12.3, 6.1))
    ymax = float(np.ceil(max(max(p) for p in positions) / 100) * 100)
    for ax, a, p, title in zip(axs, arrays, positions, titles):
        mesh = heat(ax, a, p, times, limits, title, ymax)
    axs[0].set_ylabel("Arc length from ROI reference (µm)")
    fig.subplots_adjust(left=0.085, right=0.86, bottom=0.25, top=0.83, wspace=0.32)
    cb = fig.add_axes([0.89, 0.25, 0.014, 0.58])
    fig.colorbar(
        mesh, cax=cb, ticks=[0, 0.5, 1], label="Shared relative display intensity"
    )
    fig.suptitle(
        "Lauschke 2013 · Video 1",
        x=0.085,
        y=0.96,
        ha="left",
        fontsize=15,
        fontweight="bold",
        color="#242833",
    )
    fig.text(
        0.085,
        0.905,
        "All 126 frames · 0–20.92 h · 20 px strip width · no intensity smoothing",
        fontsize=10,
        color="#525b6b",
    )
    fig.text(
        0.085,
        0.14,
        "LuVeLu / brightfield composite · shared color scale · A above P · gray = missing coverage",
        fontsize=9,
        color="#525b6b",
    )
    fig.text(0.085, 0.09, footnote, fontsize=8.5, color="#525b6b", linespacing=1.65)
    for ext in ["png", "svg", "pdf"]:
        fig.savefig(output / f"{name}.{ext}", dpi=190)
    plt.close(fig)


def run(output, selected, baseline, cached_frames):
    import av

    selected_npz = selected / "geometry-review.npz"
    selected_report_path = selected / "review.json"
    baseline_npz = baseline / "geometry-review.npz"
    selected_report = json.loads(selected_report_path.read_text())
    json.loads((baseline / "review.json").read_text())
    input_hashes = {
        str(p): digest(p) for p in [selected_npz, selected_report_path, baseline_npz]
    }
    if digest(baseline_npz) != selected_report["baseline_geometry"]["sha256"]:
        raise ValueError("Saved baseline differs from the chosen placement review")
    source = (
        ASSET_ROOT
        / "data/source-archive/lauschke-2013"
        / selected_report["source"]["filename"]
    )
    if digest(source) != SOURCE_HASH:
        raise ValueError("Original Video 1 changed")
    frames = np.load(cached_frames, mmap_mode="r")
    if frames.shape != (126, 730, 737, 3):
        raise ValueError("Unexpected decoded frame cache")
    with av.open(str(source)) as container:
        decoded_count = 0
        for i, frame in enumerate(container.decode(video=0)):
            if i in [0, 27, 60, 100, 101, 125]:
                np.testing.assert_array_equal(
                    frames[i], frame.to_ndarray(format="rgb24")
                )
            decoded_count += 1
    if decoded_count != 126:
        raise ValueError("Unexpected source frame count")
    with np.load(selected_npz) as z:
        selected_index = np.flatnonzero(z["shifts_px"] == 30).item()
        unshifted_index = np.flatnonzero(z["shifts_px"] == 0).item()
        saved_paths = z["paths_xy"]
        saved_normals = z["normals_xy"]
        saved_counts = z["path_counts"]
        matrices = z["source_to_reference"]
        times = z["time_h"]
    with np.load(baseline_npz) as z:
        masks_original = z["foreground_masks_original"]
        np.testing.assert_array_equal(matrices, z["source_to_reference"])
        np.testing.assert_array_equal(times, z["time_h"])
    timestamp_path = ASSET_ROOT / "data/derived/lauschke-2013/video1-timestamps.json"
    from reproduce_lauschke_views import read_times

    np.testing.assert_array_equal(times, read_times(timestamp_path, 126))
    current = (
        ASSET_ROOT
        / "data/derived/lauschke-2013/video1-full-curve/video1-curved-kymograph.npz"
    )
    current_hash = digest(current)
    with np.load(current) as z:
        current_intensity = z["intensity"]
        current_position = z["position_um"]
        np.testing.assert_array_equal(times, z["time_h"])
    variants = []
    for index in [unshifted_index, selected_index]:
        max_length = max(
            np.linalg.norm(np.diff(p[:n], axis=0), axis=1).sum() * SCALE
            for p, n in zip(saved_paths[index], saved_counts[index])
        )
        position = np.arange(np.ceil(max_length) + 1, dtype=float)
        raw = []
        fov_control = []
        counts = []
        validity = []
        ref_paths = []
        ref_normals = []
        source_paths = []
        source_normals = []
        lengths = []
        a_counts = []
        a_source = []
        p_source = []
        for i, (frame, m, mask, n) in enumerate(
            zip(frames, matrices, masks_original, saved_counts[index])
        ):
            p = saved_paths[index, i, :n]
            nn = saved_normals[index, i, :n]
            np.testing.assert_allclose(p[0], P_REF, atol=1e-8)
            np.testing.assert_allclose(p[-1], A_REF, atol=1e-8)
            rp, rn, length = resample_saved_curve(p, nn, position)
            sp, sn = to_source_geometry(rp, rn, m)
            endpoints, endpoint_normals = to_source_geometry(p[[0, -1]], nn[[0, -1]], m)
            fov = np.zeros(mask.shape, bool)
            fov[15:-60, 15:] = True
            foreground = mask & fov
            _, endpoint_count, endpoint_valid = sample_strip(
                frame,
                endpoints[-1:],
                endpoint_normals[-1:],
                WIDTH,
                valid_region=foreground,
            )
            if not endpoint_valid[0]:
                raise ValueError(f"A reference unsupported at frame {i}")
            value, count, valid = sample_strip(
                frame,
                sp,
                sn,
                WIDTH,
                valid_region=foreground,
                coverage_policy="last_supported_run",
            )
            control, _, _ = sample_strip(
                frame,
                sp,
                sn,
                WIDTH,
                valid_region=fov,
                coverage_policy="last_supported_run",
            )
            raw.append(value)
            fov_control.append(control)
            counts.append(count)
            validity.append(valid)
            ref_paths.append(rp)
            ref_normals.append(rn)
            source_paths.append(sp)
            source_normals.append(sn)
            lengths.append(length)
            a_counts.append(int(endpoint_count[0]))
            a_source.append(endpoints[-1])
            p_source.append(endpoints[0])
        variants.append(
            {
                "position_um": position,
                "intensity": np.array(raw).T,
                "fov_only_intensity": np.array(fov_control).T,
                "valid_width_counts": np.array(counts).T,
                "measurement_valid_mask": np.array(validity).T,
                "path_xy": np.array(source_paths),
                "normals_xy": np.array(source_normals),
                "path_reference_xy": np.array(ref_paths),
                "normals_reference_xy": np.array(ref_normals),
                "path_length_um": np.array(lengths),
                "A_reference_source_xy": np.array(a_source),
                "P_reference_source_xy": np.array(p_source),
                "A_endpoint_valid_width_counts": np.array(a_counts),
            }
        )
    unshifted, new = variants
    output.mkdir(parents=True, exist_ok=True)
    limits = [
        float(min(np.nanmin(current_intensity), np.nanmin(new["intensity"]))),
        float(max(np.nanmax(current_intensity), np.nanmax(new["intensity"]))),
    ]
    np.savez_compressed(
        output / "video1-inward30-kymograph.npz",
        **new,
        time_h=times,
        source_to_reference=matrices,
        reference_frame=125,
        A_ref_xy=A_REF,
        P_ref_xy=P_REF,
        shared_comparison_limits=limits,
    )
    np.savez_compressed(
        output / "comparison-controls.npz",
        time_h=times,
        current_intensity=current_intensity,
        current_position_um=current_position,
        inward0_intensity=unshifted["intensity"],
        inward0_position_um=unshifted["position_um"],
        inward30_fov_only_intensity=new["fov_only_intensity"],
        inward30_position_um=new["position_um"],
    )
    render_comparison(
        output,
        "current-vs-inward30",
        [current_intensity, new["intensity"]],
        [current_position, new["position_um"]],
        times,
        limits,
        ["Current · moving P reference", "Inward 30 px · fixed A/P references"],
        "Current: FOV/text validity only. New: foreground interval connected to checked A reference.\nOrigins differ; equal arc length does not identify the same cells. Original primary is preserved.",
    )
    matched_limits = [
        float(min(np.nanmin(unshifted["intensity"]), np.nanmin(new["intensity"]))),
        float(max(np.nanmax(unshifted["intensity"]), np.nanmax(new["intensity"]))),
    ]
    render_comparison(
        output,
        "inward0-vs30",
        [unshifted["intensity"], new["intensity"]],
        [unshifted["position_um"], new["position_um"]],
        times,
        matched_limits,
        [
            "Fixed A/P references · no inward shift",
            "Fixed A/P references · inward 30 px",
        ],
        "Same registration, reference endpoints, strip width and foreground-coverage rule.\nOnly the interior path placement differs. Foreground proxy does not verify anatomical PSM identity.",
    )
    fov_limits = [
        float(min(np.nanmin(current_intensity), np.nanmin(new["fov_only_intensity"]))),
        float(max(np.nanmax(current_intensity), np.nanmax(new["fov_only_intensity"]))),
    ]
    render_comparison(
        output,
        "fov-only-control",
        [current_intensity, new["fov_only_intensity"]],
        [current_position, new["position_um"]],
        times,
        fov_limits,
        ["Current · FOV-only reference", "Inward 30 px · FOV-only control"],
        "Coverage control: both use source FOV/text exclusion, without a tissue mask.\nBackground can remain finite in this diagnostic; it must not be interpreted as tissue expression.",
    )
    for p, h in input_hashes.items():
        if digest(p) != h:
            raise ValueError("A selected geometry input changed during extraction")
    if digest(current) != current_hash:
        raise ValueError("Existing primary changed during extraction")
    starts = []
    ends = []
    excluded_islands = []
    for counts, valid in zip(
        new["valid_width_counts"].T, new["measurement_valid_mask"].T
    ):
        retained = np.flatnonzero(valid)
        starts.append(float(new["position_um"][retained[0]]))
        ends.append(float(new["position_um"][retained[-1]]))
        excluded_islands.append(int(np.sum((counts >= 16) & ~valid)))
    record = {
        "status": "local comparison extraction; gallery primary not replaced",
        "source": {
            "file": source.name,
            "sha256": SOURCE_HASH,
            "shape": [126, 730, 737, 3],
        },
        "selected_geometry": {
            "file": str(selected_npz),
            "sha256": digest(selected_npz),
            "variant_inward_shift_px": 30,
            "width_px": WIDTH,
            "normal_samples": 21,
            "reference_frame": 125,
            "A_ref_xy": A_REF.tolist(),
            "P_ref_xy": P_REF.tolist(),
            "resampling": "linear interpolation of saved xy vertices and unit-normal field; physical polyline arc length; no new spline fit or length normalization",
            "source_mapping": "inverse saved SE(2); rotate normals without translation; sample original decoded RGB directly",
            "scale_um_per_px": SCALE,
            "direction": "P reference toward A reference; A displayed above P",
        },
        "clock": {
            "timestamp_audit_sha256": digest(timestamp_path),
            "time_h": times.tolist(),
            "range_h": [float(times[0]), float(times[-1])],
            "frame_100_101_gap_h": float(times[101] - times[100]),
        },
        "signal": {
            "estimator": "bilinear interpolation of mean decoded RGB, then arithmetic normal-width mean",
            "meaning": "inseparable LuVeLu / brightfield display composite; not isolated fluorescence",
            "smoothing": "none; width averaging only",
            "time_filtering": "none",
            "shared_comparison_limits": limits,
        },
        "coverage": {
            "min_valid_fraction": 0.75,
            "required_width_samples": 16,
            "source_fov_text": "source rows15:670, columns15:737",
            "foreground": "unchanged local-texture foreground proxy from the earlier ROI review; not anatomical PSM segmentation",
            "interval": "final contiguous supported run, with every exact A endpoint independently checked; missing P-side prefix retained; no gap bridging",
            "A_endpoint_counts": new["A_endpoint_valid_width_counts"].tolist(),
            "path_length_um": new["path_length_um"].tolist(),
            "retained_start_um": starts,
            "retained_end_um": ends,
            "excluded_disconnected_rows": excluded_islands,
            "matrix_shape": list(new["intensity"].shape),
            "missing_values": int(np.isnan(new["intensity"]).sum()),
        },
        "current_reference": {
            "file": str(current),
            "sha256": current_hash,
            "unchanged": True,
            "validity_difference": "current primary has FOV-only coverage; new selected extraction adds foreground/A-connected interval. Separate FOV-only and matched-ROI controls are supplied.",
        },
        "input_hashes": input_hashes,
        "limitations": selected_report["limitations"]
        + [
            "Selecting the inward path does not independently validate the original registration.",
            "Reference endpoints are fixed in xy; their connecting path length varies. Gray prefixes are absence of supported measurement, not zero expression.",
            "Retained paths can move across cells or neighboring tissue; slopes are not automatically material wave speeds.",
        ],
        "script_sha256": digest(__file__),
        "sampler_sha256": digest(Path(__file__).with_name("curved_strip.py")),
    }
    (output / "provenance.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "shape": list(new["intensity"].shape),
                "missing_values": record["coverage"]["missing_values"],
                "A_endpoint_min_counts": min(record["coverage"]["A_endpoint_counts"]),
                "length_range_um": [
                    min(new["path_length_um"]),
                    max(new["path_length_um"]),
                ],
                "retained_start_range_um": [min(starts), max(starts)],
                "current_unchanged": True,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/video1-inward30-kymograph")
    )
    parser.add_argument(
        "--selected", type=Path, default=Path("outputs/video1-inward-roi-review")
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
    run(args.output, args.selected, args.baseline, args.cached_frames)

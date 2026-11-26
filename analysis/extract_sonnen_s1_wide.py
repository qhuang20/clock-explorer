# SPDX-License-Identifier: MIT
"""Resample Sonnen Movie S1 on its approved fixed-reference path and render the anterior detail."""

import json

import av
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from scipy.ndimage import gaussian_filter, gaussian_filter1d

from comparison_plot import panel, plt
from extract_sonnen_additional import digest, image_validity
from extract_sonnen_fixed_reference import STUDY, longest_run
from paths import ASSET_ROOT
from render_sonnen_half_and_extent import render
from review_sonnen_fixed_reference import draw
from review_sonnen_s1_half import half_support
from verify_sonnen_candidates import strip_profile


def run():
    folder = "s1-fixed-70um"
    data = STUDY / folder
    figures = ASSET_ROOT / "figures/sonnen-2018" / folder
    for directory in (data, figures):
        directory.mkdir(exist_ok=True, parents=True)
    previous = STUDY / "s1-final-reference"
    matrix_file = previous / "kymograph.npz"
    prior = json.loads((previous / "provenance.json").read_text())
    movie = ASSET_ROOT / prior["source_file"]
    if (
        digest(matrix_file) != prior["matrix_sha256"]
        or digest(movie) != prior["source_sha256"]
    ):
        raise ValueError("Movie S1 or its reviewed geometry changed")
    with np.load(matrix_file) as old:
        z = dict(old)
    scale = float(z["um_per_px"])
    width = 70 / scale
    offsets = np.linspace(-width / 2, width / 2, int(np.ceil(width)) + 1)
    times, distances = z["time_h"], z["position_um"]
    pos = (distances >= 275) & (distances <= 540)
    filtered = np.full_like(z["intensity"], np.nan)
    raw = np.full_like(z["intensity"], np.nan)
    counts = np.zeros_like(z["width_counts"])
    jacobians = []
    with av.open(str(movie)) as reader, PdfPages(figures / "all-frames.pdf") as pdf:
        for i, frame in enumerate(reader.decode(video=0)):
            rgb = frame.to_ndarray(format="rgb24")
            image = rgb[:, :, 1]
            support = half_support(
                image, z["seam_xy"][i], image_validity("s1", image.shape)
            )
            path, normals = z["path_xy"][i], z["normals_xy"][i]
            profile, counts[:, i] = strip_profile(
                image, path, normals, offsets, support
            )
            keep = longest_run(np.isfinite(profile))
            raw[keep, i] = profile[keep]
            curve, normal = path[keep], normals[keep]
            angle = np.unwrap(np.arctan2(normal[:, 1], normal[:, 0]))
            curvature = np.diff(angle) / np.linalg.norm(np.diff(curve, axis=0), axis=1)
            jacobians.append(float(np.min(1 - width / 2 * np.abs(curvature))))
            weights = gaussian_filter(support.astype(float), 5 / scale)
            blurred = gaussian_filter(
                image.astype(float) * support, 5 / scale
            ) / np.maximum(weights, 1e-12)
            line, _ = strip_profile(blurred, path, normals, offsets, support)
            weights = gaussian_filter1d(keep.astype(float), 5 / np.diff(distances)[0])
            smoothed = gaussian_filter1d(
                np.where(keep, line, 0), 5 / np.diff(distances)[0]
            )
            filtered[:, i] = np.where(
                keep, smoothed / np.maximum(weights, 1e-12), np.nan
            )
            if i % 6 == 0:
                fig, axes = plt.subplots(2, 3, figsize=(10, 7.5), layout="constrained")
                for ax in axes.flat:
                    ax.set_axis_off()
            ax = axes.flat[i % 6]
            draw(
                ax,
                rgb,
                path,
                normals,
                keep,
                width,
                z["P_reference_source_xy"][i],
                z["A_reference_source_xy"][i],
            )
            ax.set_title(f"Frame {i} · {times[i]:.2f} h")
            if i % 6 == 5 or i == len(times) - 1:
                pdf.savefig(fig, dpi=65)
                plt.close(fig)
    if i + 1 != len(times) or min(jacobians) <= 0:
        raise ValueError("Invalid frame coverage or folded sampling band")
    valid = np.isfinite(raw)
    first, last = np.array(
        [distances[np.flatnonzero(col)[[0, -1]]] for col in valid.T]
    ).T
    z.update(
        intensity=filtered,
        unsmoothed_intensity=raw,
        valid=valid,
        width_counts=counts,
        strip_width_px=width,
        first_valid_distance_um=first,
        last_valid_distance_um=last,
    )
    np.savez_compressed(data / "kymograph.npz", **z)
    np.savez_compressed(
        data / "full-spatial-filter.npz",
        intensity=filtered,
        time_h=times,
        position_um=distances,
    )
    np.savez_compressed(
        data / "anterior-zoom.npz",
        intensity=filtered[pos],
        time_h=times,
        position_um=distances[pos],
    )
    note = "The 70 µm band on the registered image-right corridor spans 114.8 export pixels. The transverse mean uses all 116 sample positions."
    prior.update(
        strip=note,
        primary_processing="Masked 5 µm Gaussian within each source frame, transverse mean, then 5 µm Gaussian along arc length. Time is unfiltered. The NPZ also retains the unsmoothed_intensity array.",
        display_limits=[float(np.nanmin(raw)), float(np.nanmax(raw))],
        previous_input=str(matrix_file.relative_to(ASSET_ROOT)),
        previous_sha256=digest(matrix_file),
        analysis_script="analysis/extract_sonnen_s1_wide.py",
        analysis_script_sha256=digest(__file__),
        matrix_sha256=digest(data / "kymograph.npz"),
        strip_width_px=width,
        strip_width_um=70,
        first_valid_distance_um=first.tolist(),
        last_valid_distance_um=last.tolist(),
        minimum_retained_width_jacobian=min(jacobians),
        zoom=dict(
            matrix_sha256=digest(data / "anterior-zoom.npz"),
            time_h=[float(times[0]), float(times[-1])],
            full_filtered_matrix_sha256=digest(data / "full-spatial-filter.npz"),
            distance_um=[275, 540],
            spatial_sigma_um=5,
            processing="Masked Gaussian in each source frame followed by Gaussian smoothing along arc length. No temporal filter. Shared full-run display limits.",
        ),
    )
    (data / "provenance.json").write_text(json.dumps(prior, indent=2) + "\n")
    render("s1", fixed=True, output_folder=folder)
    for stem, selected, region in [
        ("full-filter-comparison", slice(None), "Full corridor"),
        ("anterior-zoom", pos, "Anterior region"),
    ]:
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.25), layout="constrained")
        for ax, values, title in zip(
            axes, (raw, filtered), ("Unsmoothed", "5 µm spatial smoothing")
        ):
            panel(
                fig,
                ax,
                dict(
                    matrix=values[selected],
                    time=times,
                    position=distances[selected],
                    position_unit="µm",
                    position_increases_up=True,
                    axis_label="Distance from fixed P (approx. µm)",
                    signal_label="Relative intensity",
                    display_limits=(np.nanmin(raw), np.nanmax(raw)),
                ),
                window="full",
            )
            ax.set_title(title, loc="left")
        fig.suptitle(f"Movie S1 · Axin2T2A · {region} · 0–{times[-1]:g} h", fontsize=13)
        for ext in ("svg", "png"):
            fig.savefig(figures / f"{stem}.{ext}", dpi=180)
        plt.close(fig)


if __name__ == "__main__":
    run()

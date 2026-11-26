# SPDX-License-Identifier: MIT
"""Filter Movie S2 within each source frame and along its fixed radial strip."""

import json
from pathlib import Path

import av
import numpy as np
from scipy.ndimage import gaussian_filter, gaussian_filter1d

from comparison_plot import panel, plt
from extract_sonnen_additional import digest
from paths import ASSET_ROOT
from render_sonnen_half_and_extent import render
from review_sonnen_s2_extended import envelope, THRESHOLDS
from verify_sonnen_candidates import strip_profile


def run():
    study = ASSET_ROOT / "data/derived/sonnen-2018"
    previous = study / "s2-final-reference"
    folder = "s2-smoothed"
    output = study / folder
    output.mkdir(exist_ok=True)
    record = json.loads((previous / "provenance.json").read_text())
    source = ASSET_ROOT / record["source_file"]
    original = previous / "kymograph.npz"
    if (
        digest(source) != record["source_sha256"]
        or digest(original) != record["matrix_sha256"]
    ):
        raise ValueError("Source movie or radial extraction changed")
    with np.load(original) as stored:
        z = dict(stored)
    raw = z["intensity"]
    distances = z["position_um"]
    width = float(z["strip_width_px"])
    offsets = np.linspace(-width / 2, width / 2, int(np.ceil(width)) + 1)
    sigma_px = 5 / float(z["um_per_px"])
    sigma_rows = 5 / np.diff(distances)[0]
    filtered = np.full_like(raw, np.nan)
    with av.open(str(source)) as video:
        for i, frame in enumerate(video.decode(video=0)):
            image = frame.to_ndarray(format="rgb24")[:, :, 1]
            support = np.logical_and.reduce([envelope(image, v) for v in THRESHOLDS])
            path, normals = z["path_xy"][i], z["normals_xy"][i]
            observed, _ = strip_profile(image, path, normals, offsets, support)
            keep = np.logical_and.accumulate(np.isfinite(observed))
            np.testing.assert_array_equal(keep, z["valid"][:, i])
            np.testing.assert_allclose(observed[keep], raw[keep, i])
            weights = gaussian_filter(support.astype(float), sigma_px)
            blurred = gaussian_filter(
                image.astype(float) * support, sigma_px
            ) / np.maximum(weights, 1e-12)
            line, _ = strip_profile(blurred, path, normals, offsets, support)
            weights = gaussian_filter1d(keep.astype(float), sigma_rows)
            profile = gaussian_filter1d(np.where(keep, line, 0), sigma_rows)
            filtered[keep, i] = profile[keep] / weights[keep]
    if i + 1 != raw.shape[1]:
        raise ValueError("Incomplete movie")
    np.testing.assert_array_equal(np.isfinite(filtered), z["valid"])
    z.update(intensity=filtered, unsmoothed_intensity=raw)
    matrix = output / "kymograph.npz"
    np.savez_compressed(matrix, **z)
    limits = [float(np.nanmin(raw)), float(np.nanmax(raw))]
    record.update(
        previous_input=str(original.relative_to(ASSET_ROOT)),
        previous_sha256=digest(original),
        analysis_script="analysis/" + Path(__file__).name,
        analysis_script_sha256=digest(__file__),
        matrix_sha256=digest(matrix),
        display_limits=limits,
        spatial_sigma_um=5,
        signal="Spatially filtered Axin2T2A green display values; unsmoothed transverse means retained in unsmoothed_intensity.",
        primary_processing="Masked Gaussian within each source frame, transverse mean, then masked Gaussian along the radial distance axis. Both Gaussian stages have sigma 5 µm. No temporal filtering.",
    )
    (output / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")
    render("s2", fixed=True, output_folder=folder)
    figures = ASSET_ROOT / "figures/sonnen-2018" / folder
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.25), layout="constrained")
    for ax, values, title in zip(
        axes, (raw, filtered), ("Unsmoothed", "5 µm spatial smoothing")
    ):
        panel(
            fig,
            ax,
            dict(
                matrix=values,
                time=z["time_h"],
                position=distances,
                position_unit="µm",
                position_increases_up=True,
                display_limits=limits,
                axis_label="Distance from fixed P (approx. µm)",
                signal_label="Relative intensity",
            ),
            window="full",
        )
        ax.set_title(title, loc="left")
    fig.suptitle("Movie S2 · Axin2T2A · Ex vivo mPSM · 0–25.69 h", fontsize=13)
    for ext in ("png", "svg"):
        fig.savefig(figures / f"smoothing-comparison.{ext}", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    run()

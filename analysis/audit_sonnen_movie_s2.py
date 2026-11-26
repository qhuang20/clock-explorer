# SPDX-License-Identifier: MIT
"""Audit the Movie S2 exploratory strip without replacing its scientific assets.

Run with the optional scientific environment:
  work/plot-env/bin/python analysis/audit_sonnen_movie_s2.py

The radial route is supported by the preparation. Its present line has no
independently validated wavefront center or deposited author ROI. This adapter
therefore reproduces the existing display-value matrix and records the remaining
geometry uncertainty instead of relabeling the start as an anatomical landmark.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw

from paths import ASSET_ROOT, REPO_ROOT
from extract_video_kymographs import decode, extract

MOVIE_SHA = "02b0f439d976b0a3cecb38ef89cab2c92fea1188242aceef40d11a7cf1594ec1"
SOURCE_URL = "https://pmc-oa-opendata.s3.amazonaws.com/PMC5847172.1/mmc3.mp4"
ARTICLE_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC5847172/"
AUTHOR_PDF = (
    "https://www.sonnenlab.org/wp-content/uploads/2020/04/Sonnen_Aulehla_Cell_2018.pdf"
)
START = np.array([520.0, 480.0])
END = np.array([260.0, 240.0])
WIDTH = 40
UM_PER_PX = 100 / 139
KEYFRAMES = [0, 30, 60, 77, 110, 154]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sampling_geometry(shifts):
    """Reconstruct the saved strip; width is the span of 41 offsets, not 40 samples."""
    shifts = np.asarray(shifts, dtype=float)
    vector = END - START
    length = float(np.linalg.norm(vector))
    direction = vector / length
    origins = START + shifts
    endpoints = END + shifts
    distances = np.linspace(0, length, int(length) + 1)
    normal = np.array([-direction[1], direction[0]])
    offsets = np.arange(-WIDTH // 2, WIDTH // 2 + 1)
    coordinates = (
        origins[:, None, None, :]
        + distances[None, :, None, None] * direction
        + offsets[None, None, :, None] * normal
    )
    return origins, endpoints, direction, distances, coordinates


def fov_width_counts(coordinates, shape):
    """Bilinear FOV validity only; deliberately does not claim a tissue mask."""
    height, width = shape[:2]
    x, y = coordinates[..., 0], coordinates[..., 1]
    return ((x >= 0) & (x < width - 1) & (y >= 0) & (y < height - 1)).sum(axis=2).T


def read_burned_times(path, expected_frames):
    with Path(path).open() as handle:
        rows = list(csv.DictReader(handle))
    indices = np.array([int(r["frame"]) for r in rows])
    times = np.array([float(r["time_hours"]) for r in rows])
    if not np.array_equal(indices, np.arange(expected_frames)):
        raise ValueError("Burned clock must index every source frame without gaps")
    if not np.isfinite(times).all() or not np.all(np.diff(times) > 0):
        raise ValueError("Burned clock must be finite and strictly increasing")
    return times


def original_svg_axes(path):
    ns = {"s": "http://www.w3.org/2000/svg"}
    root = ET.parse(path)
    axes = []
    for group in root.findall(".//s:g", ns):
        if not group.get("id", "").startswith("axes_"):
            continue
        texts = [
            {"text": "".join(t.itertext()), "x": t.get("x"), "y": t.get("y")}
            for t in group.findall(".//s:text", ns)
        ]
        axes.append({"id": group.get("id"), "texts": texts})
    return {
        "data_axis_ids": ["axes_1"],
        "colorbar_axis_ids": ["axes_2"],
        "original_zero_at": "top",
        "original_distance_increases": "down",
        "display_reversal_for_outward_above_inner": True,
        "axes": axes,
    }


def make_figures(frames, times, matrix, positions, shifts, figures, review):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "svg.fonttype": "none",
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "axes.labelsize": 9,
        }
    )
    origins, endpoints, direction, _, _ = sampling_geometry(shifts)
    normal = np.array([-direction[1], direction[0]]) * WIDTH / 2
    fig, axes = plt.subplots(2, 3, figsize=(14, 10.5))
    for ax, i in zip(axes.flat, KEYFRAMES):
        ax.imshow(frames[i])
        a, b = origins[i], endpoints[i]
        corners = np.array([a + normal, b + normal, b - normal, a - normal, a + normal])
        ax.plot(corners[:, 0], corners[:, 1], color="#ffad43", lw=1.1)
        ax.annotate(
            "",
            xy=b,
            xytext=a,
            arrowprops={"arrowstyle": "->", "color": "#ffad43", "lw": 1.8},
        )
        ax.plot(*a, "o", ms=5, mfc="none", mec="#fff07c", mew=1.5)
        ax.text(
            a[0] + 18,
            a[1] + 26,
            "O: inner start",
            color="#fff07c",
            fontsize=8,
            bbox={"facecolor": "black", "alpha": 0.72, "pad": 2},
        )
        ax.text(
            b[0] - 10,
            b[1] - 28,
            "E: outward endpoint",
            ha="center",
            color="#ffcf8d",
            fontsize=8,
            bbox={"facecolor": "black", "alpha": 0.72, "pad": 2},
        )
        ax.set_title(
            f"Frame {i} | {times[i]:.2f} h | shift {shifts[i].round(1)} px", fontsize=9
        )
        ax.set_xlim(0, frames[i].shape[1])
        ax.set_ylim(frames[i].shape[0], 0)
        ax.axis("off")
    fig.suptitle(
        "Movie S2 | preserved exploratory inner-to-outward strip", fontsize=15, y=0.98
    )
    fig.text(
        0.06,
        0.045,
        "O and E are analyst-selected sampling endpoints, not exact P/A landmarks or a fitted center.\n"
        "Regional polarity develops from central posterior toward peripheral anterior mPSM; early culture is posterior PSM.\n"
        "Orange: 40 px transverse span / 41 bilinear samples. Translation only; no tissue segmentation or cell tracking.",
        fontsize=10,
        va="bottom",
    )
    fig.subplots_adjust(
        left=0.03, right=0.99, bottom=0.13, top=0.93, hspace=0.13, wspace=0.04
    )
    fig.savefig(figures / "movie-s2-reviewed-roi.jpg", dpi=160)
    fig.savefig(figures / "movie-s2-reviewed-roi.pdf")
    plt.close(fig)

    # Same measured values, explicit outward-above-inner display only.
    fig, ax = plt.subplots(figsize=(8.6, 5.5))
    display = (matrix - matrix.min()) / (matrix.max() - matrix.min())
    cmap = plt.get_cmap("OrRd").copy()
    cmap.set_bad("#d7dce2")
    mesh = ax.pcolormesh(
        times,
        positions,
        display,
        shading="nearest",
        cmap=cmap,
        vmin=0,
        vmax=1,
        rasterized=True,
    )
    ax.set_xlim(times[0], times[-1])
    ax.set_ylim(positions[0], positions[-1])
    ax.set_xlabel("Time (h)")
    ax.set_ylabel("Distance from ROI start (approx. µm)")
    ax.set_title("Axin2T2A", loc="left", pad=14)
    cb = fig.colorbar(mesh, ax=ax, pad=0.04)
    cb.set_label("Relative display intensity")
    fig.subplots_adjust(left=0.13, right=0.89, top=0.87, bottom=0.15)
    for extension in ["png", "svg", "pdf"]:
        fig.savefig(figures / f"movie-s2-reviewed-baseline.{extension}", dpi=180)
    plt.close(fig)

    # Geometry closeups retain actual source pixels and the baseline start.
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.7))
    for ax, i in zip(axes, [0, 77, 154]):
        ax.imshow(frames[i])
        a = origins[i]
        ax.plot(*a, "+", color="#fff07c", ms=13, mew=1.8)
        ax.set_xlim(a[0] - 145, a[0] + 145)
        ax.set_ylim(a[1] + 145, a[1] - 145)
        ax.set_title(f"Frame {i} | {times[i]:.2f} h\nO = {a.round(1)} px", fontsize=10)
        ax.axis("off")
    fig.suptitle(
        "Inner sampling origin: visible structure does not establish an oscillation center",
        fontsize=13,
    )
    fig.text(
        0.05,
        0.04,
        "No exact posterior landmark, author-deposited line or multi-frame wavefront center was established.\n"
        "FOV coverage is complete; tissue membership at every transverse sample remains unsegmented.",
        fontsize=10,
    )
    fig.subplots_adjust(top=0.8, bottom=0.16, left=0.03, right=0.99, wspace=0.04)
    fig.savefig(figures / "movie-s2-origin-review.jpg", dpi=160)
    plt.close(fig)

    sheet = Image.new("RGB", (1000, 350), "white")
    draw = ImageDraw.Draw(sheet)
    for j, i in enumerate([0, 1, 2, 10, 50, 77, 100, 154]):
        crop = Image.fromarray(frames[i]).crop((0, 0, 310, 65))
        crop.thumbnail((242, 51))
        x, y = j % 4 * 250, j // 4 * 88
        draw.text((x + 4, y + 3), f"Frame {i}: {times[i]:.2f} h", fill="black")
        sheet.paste(crop, (x, y + 24))
    crop = Image.fromarray(frames[0]).crop((800, 0, 984, 90)).resize((368, 180))
    sheet.paste(crop, (0, 170))
    draw.text(
        (385, 200),
        "Scale: 100 um / 139 decoded px (approximately +/-1 px).",
        fill="black",
    )
    draw.text(
        (385, 226),
        "Time: 155 burned-in labels; display precision 0.01 h.",
        fill="black",
    )
    draw.text(
        (385, 252), "10 fps playback is not the experimental clock.", fill="black"
    )
    sheet.save(figures / "movie-s2-calibration-review.png")
    shutil.copy2(
        figures / "movie-s2-calibration-review.png", review / "calibration-review.png"
    )


def run(movie, asset_root, output):
    data = asset_root / "data/derived/sonnen-2018"
    figures_original = asset_root / "figures/sonnen-2018"
    protected = [
        p
        for folder in [data, figures_original]
        for p in folder.iterdir()
        if p.is_file()
    ]
    before = {str(p.relative_to(asset_root)): digest(p) for p in protected}
    if digest(movie) != MOVIE_SHA:
        raise ValueError("Movie S2 source hash differs from the reviewed source")
    output.mkdir(parents=True, exist_ok=True)
    outdata = data / "s2-review"
    outdata.mkdir(parents=True, exist_ok=True)
    figures = figures_original / "s2-review"
    figures.mkdir(parents=True, exist_ok=True)
    frames = decode(movie)
    if len(frames) != 155 or frames[0].shape != (984, 990, 3):
        raise ValueError("Unexpected Movie S2 source dimensions")
    with np.load(data / "movie-s2-kymograph.npz") as original:
        saved = {k: original[k].copy() for k in original.files}
    times = read_burned_times(data / "burned-frame-times.csv", len(frames))
    np.testing.assert_array_equal(times, saved["time_h"])
    rebuilt, shifts, increments, length = extract(frames, frames, START, END, WIDTH)
    # Exact equality is intentional: this audit is not a replacement extraction.
    for a, b in [
        (rebuilt, saved["intensity"]),
        (shifts, saved["shifts_xy"]),
        (increments, saved["increments_xy"]),
    ]:
        np.testing.assert_array_equal(a, b)
    origins, endpoints, direction, position_px, xy = sampling_geometry(shifts)
    position_um = np.linspace(0, length * UM_PER_PX, rebuilt.shape[0])
    np.testing.assert_array_equal(position_um, saved["position_um"])
    counts = fov_width_counts(xy, frames[0].shape)
    np.testing.assert_array_equal(counts, np.full(rebuilt.shape, 41))
    np.savez_compressed(
        outdata / "movie-s2-reviewed-baseline.npz",
        **saved,
        position_px=position_px,
        origins_xy=origins,
        endpoints_xy=endpoints,
        directions_xy=np.tile(direction, (len(frames), 1)),
        valid_width_counts_fov_only=counts,
        valid_fov_only=np.ones(rebuilt.shape, dtype=bool),
    )
    trajectory = [
        {
            "frame": i,
            "time_h": float(times[i]),
            "origin_xy_px": origins[i].tolist(),
            "endpoint_xy_px": endpoints[i].tolist(),
            "translation_xy_px": shifts[i].tolist(),
        }
        for i in range(len(times))
    ]
    (outdata / "trajectory.json").write_text(json.dumps(trajectory, indent=2) + "\n")
    make_figures(frames, times, rebuilt, position_um, shifts, figures, output)
    svg = original_svg_axes(figures_original / "video-intensity.svg")
    report = {
        "dataset": "sonnen-2018",
        "review": "movie-s2-preserved-baseline-v1",
        "source": {
            "movie": "Movie S2 (mmc3.mp4)",
            "url": SOURCE_URL,
            "sha256": digest(movie),
            "bytes": movie.stat().st_size,
            "decoded_shape_t_y_x_rgb": [155, 984, 990, 3],
            "playback_fps": 10,
            "playback_duration_s": 15.5,
            "signal": "Axin2-T2A-Venus-PEST fluorescence rendered in near-grayscale; decoded green display values",
            "identity_evidence": "Movie S2 caption and Figure 1D-F explicitly identify the same ex vivo sample.",
            "not_this_movie": [
                "Movie S1: embryo PSM",
                "Movie S3: LuVeLu with Cascade Blue microfluidic inset",
                "Figure 1G: dual Axin2T2A/Mesp2-GFP sample",
                "Figure 2A/B: distinct reporter experiments; no identity with S2 established",
                "Figure 2E/F: simultaneous Axin2T2A-Luci/LuVeLu experiments",
            ],
            "projection": "Laser-scanning ex vivo protocol records three z planes, 8 um apart; exact rendering operation of this exported movie is unverified.",
            "preparation": "Spreading ex vivo quasi-monolayer PSM (mPSM) culture from posterior PSM; not intact embryonic AP anatomy.",
            "stage": "Exact stage of this S2 specimen was not independently established: caption does not state it; E10.5 is explicit for S1 and the microfluidic protocol, while off-chip culture refers to Lauschke 2013.",
            "temperature": "Unverified for this off-chip Movie S2; 37 C is explicit only in the microfluidic protocol.",
            "treatment": "No drug/entrainment condition assigned to Movie S2 caption; do not inherit S3 microfluidic conditions.",
            "license": "CC BY-NC-ND 4.0; local research derivation, no publication license inferred.",
        },
        "method_selection": {
            "selected": "kymograph-radial",
            "reason": "Spreading mPSM culture, paper-supported center/periphery polarity and extended curved peripheral fronts in the actual sequence.",
            "axial_route_not_selected": "No approximately straight intact embryonic AP anatomy or paired P/A landmarks in this preparation.",
            "readiness": "Exploratory inner-to-outward strip reproduced; anatomical registration and wavefront-center validation remain unresolved.",
            "primary_recommendation": "Preserve existing primary matrix and label it as an exploratory radial-route strip; do not promote a new origin without multi-time front evidence.",
            "no_center_fit_claim": "Weak oscillatory signal and persistent segment stripes must be separated before fitting. No COM substitution or circular fit was accepted.",
        },
        "polarity": {
            "regional": "Paper identifies central mPSM as posterior and peripheral mPSM as anterior as the culture develops.",
            "early": "Only posterior PSM is used to initiate culture; early peripheral cells are not thereby verified anterior.",
            "late": "Peripheral anterior differentiation and segment formation develop. Axin2 expression in the posterior half of a formed segment is segment-internal polarity, not a reversal of the whole-culture coordinate.",
            "exact_landmarks": "No exact anatomical posterior landmark, anterior endpoint, oscillation source, or author-deposited sampling line established.",
            "ui": "Use neutral inner/outward labels for the full displayed interval; no AP gutter letters. Outward above inner is a display convention, not anatomical registration.",
            "numerical_positive_direction": "From [520,480] toward [260,240] before cumulative translation; upper-left/outward in source image.",
            "source_image_coordinates": "x right, y down",
        },
        "calibration": {
            "time_unit": "h",
            "time_range": [float(times[0]), float(times[-1])],
            "time_source": "Existing complete burned-in timestamp table, exact preserved vector; this review visually spot-checked frames 0,1,2,10,50,77,100,154.",
            "movie_zero_is_culture_zero": "Unverified: the movie label starts at 0.00 h; no exact relation to dissection, plating, attachment or culture initiation was established.",
            "burned_label_precision_h": 0.01,
            "interval_values_h": np.unique(np.round(np.diff(times), 2)).tolist(),
            "nominal_protocol_min": 10,
            "nominal_time_replacement_used": False,
            "max_difference_from_nominal_time_h": float(
                np.max(np.abs(times - np.arange(len(times)) / 6))
            ),
            "length_unit": "um (approximate rendered scale)",
            "bar_um": 100,
            "bar_px": 139,
            "bar_endpoints_xy": [[823, 20], [962, 20]],
            "bar_reading_precision_px": 1,
            "um_per_decoded_pixel": UM_PER_PX,
            "raw_protocol_um_per_pixel": 1.38,
            "raw_protocol_scale_applied_to_export": False,
            "unequal_xy_scale": "Export is 990x984 rather than square 512x512. Only a horizontal scale bar is present; no independently verified vertical pixel size. Isotropic rendered scaling is a retained approximation; a full-frame 512-to-video stretch would differ by about 0.61%.",
            "no_speed_or_phase_inference": True,
        },
        "measurement": {
            "matrix_shape_space_time": list(rebuilt.shape),
            "matrix_reproduced_exactly": True,
            "start_xy_px": START.tolist(),
            "end_xy_px": END.tolist(),
            "length_px": length,
            "length_um_approx": float(position_um[-1]),
            "strip_width_px": WIDTH,
            "transverse_samples": 41,
            "strip_width_um_approx": WIDTH * UM_PER_PX,
            "sampling": "Bilinear original decoded green display values; transverse mean; no additional signal filtering.",
            "motion": "Adjacent same-fluorescence-image phase correlation, cumulative translation only; not a matched structural channel or cell tracking.",
            "maximum_translation_step_px": float(np.max(np.abs(increments))),
            "validity": "FOV-only, all 41 transverse samples valid for all 354x155 rows. No tissue mask.",
            "tissue_missing_prefix_status": "Not established. All original entries are finite; this is not evidence of complete tissue coverage. No new NaNs/zeros were manufactured.",
            "origin_status": "Analyst-selected inner start; no validated wavefront center.",
            "endpoint_status": "Analyst-selected outward endpoint; near initial outer tissue, later interior as culture spreads; not the tracked biological rim.",
            "data_value_range": [float(rebuilt.min()), float(rebuilt.max())],
            "missing_values": int(np.isnan(rebuilt).sum()),
            "true_zero_values": int((rebuilt == 0).sum()),
        },
        "display": svg,
        "new_preview": {
            "path": "figures/sonnen-2018/s2-review/movie-s2-reviewed-baseline.svg",
            "data_axis_ids": ["axes_1"],
            "zero_at": "bottom",
            "increasing_distance": "up",
            "values": "Identical baseline; only coordinate display is outward-above-inner.",
            "normalization": "Display only: (value - full-sample minimum) / (full-sample maximum - minimum); 0-1 OrRd. Numeric NPZ retains original decoded values.",
            "not_primary_replacement": True,
        },
        "evidence_sources": [
            {
                "url": ARTICLE_URL,
                "sections": [
                    "Movie S2 caption",
                    "Figure 1D-F",
                    "Figure 2E/F",
                    "STAR Methods",
                ],
            },
            {
                "url": AUTHOR_PDF,
                "pages": [3, 4, 15, 16],
                "note": "One-based PDF page numbers; primary author-hosted copy browsed.",
            },
        ],
        "original_asset_sha256_before": before,
        "script_sha256": digest(__file__),
        "reused_sampler_sha256": digest(
            REPO_ROOT / "analysis/extract_video_kymographs.py"
        ),
    }
    report["source"]["local_correspondence"] = [
        {
            "path": str(p),
            "sha256": digest(p),
            "bytes": p.stat().st_size,
            "identical_to_audited_source": digest(p) == MOVIE_SHA,
        }
        for p in [
            movie,
            asset_root / "videos/sonnen-2018/movie-s2.mp4",
            asset_root / "data/source-archive/sonnen-2018/mmc3.mp4",
        ]
        if p.exists()
    ]
    after = {str(p.relative_to(asset_root)): digest(p) for p in protected}
    if before != after:
        raise AssertionError("An original scientific asset changed during review")
    report["original_assets_unchanged"] = True
    report["original_asset_sha256_after"] = after
    for path in [outdata / "review-provenance.json", output / "review-provenance.json"]:
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    manifest = [
        {
            "path": str(p.relative_to(asset_root)),
            "bytes": p.stat().st_size,
            "sha256": digest(p),
            "paper": "sonnen-2018",
            "source_url": SOURCE_URL,
            "rights": "Third-party research material; CC BY-NC-ND 4.0; local review only.",
        }
        for folder in [outdata, figures]
        for p in sorted(folder.iterdir())
        if p.is_file()
    ]
    (output / "asset-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "preservation-check.json").write_text(
        json.dumps(
            {
                "source_sha256": MOVIE_SHA,
                "matrix_reproduced_exactly": True,
                "original_assets_unchanged": True,
                "original_assets": before,
            },
            indent=2,
        )
        + "\n"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--movie",
        type=Path,
        default=REPO_ROOT / "work/additional-data/mammal/sonnen-mmc3.mp4",
    )
    parser.add_argument("--asset-root", type=Path, default=ASSET_ROOT)
    parser.add_argument(
        "--output", type=Path, default=REPO_ROOT / "outputs/sonnen-s2-review"
    )
    args = parser.parse_args()
    result = run(args.movie, args.asset_root, args.output)
    print(
        json.dumps(
            {
                "matrix_reproduced_exactly": result["measurement"][
                    "matrix_reproduced_exactly"
                ],
                "original_assets_unchanged": result["original_assets_unchanged"],
                "review": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()

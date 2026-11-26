# SPDX-License-Identifier: MIT
"""Read-only review of Video 2's saved radial extraction and its interpretation.

Writes an isolated review package. Original matrices, geometry, figure files and
the independent-fit primary selection remain unchanged. Run in the scientific
environment, optionally adding --refit-geometry to repeat BF/center estimation.
"""

from pathlib import Path
import argparse
import json
import xml.etree.ElementTree as ET

import numpy as np
from scipy import ndimage as ndi

from paths import ASSET_ROOT
from extract_video_kymographs import decode
from reproduce_lauschke_views import (
    SOURCE_HASHES,
    WIDTH_PX,
    SIGMA_UM,
    read_times,
    radial_geometry,
    sample,
)
from extract_lauschke_author_line import (
    UM_PER_PX,
    digest,
    mapped_line,
    sample_line,
    validate_registration,
    edge,
)
from lauschke_wavefront_center import fit_common_center


PAPER_URL = (
    "https://www.mcgill.ca/francois-group/files/francois-group/nature_2013_lauschke.pdf"
)
ARTICLE_URL = "https://www.nature.com/articles/nature11804"
EVIDENCE = [
    {
        "id": "V2-identity",
        "url": ARTICLE_URL + "#Sec12",
        "location": "Supplementary Videos 2 and 3 captions",
        "finding": "Video 2 is E10.5 tailbud-derived LuVeLu mPSM and supplies Fig. 1d/f; Video 3 is its matched brightfield channel.",
    },
    {
        "id": "V2-axis",
        "url": PAPER_URL,
        "location": "Fig. 1d/f and caption, p. 102",
        "finding": "Video 2 waves are described in central-to-peripheral coordinates; Fig. 1f labels Central at distance zero and Peripheral outward.",
    },
    {
        "id": "V2-early",
        "url": PAPER_URL,
        "location": "Main text p. 103, paragraph beginning 'In principle'; Supplementary Figs. 6/7 cited by authors",
        "finding": "Before approximately 20 h the incomplete mPSM is posterior-like throughout, without anterior Mesp2/Aldh1a2 or segment formation. This is preparation-level evidence, not marker measurements in each Video 2 frame.",
    },
    {
        "id": "V2-later",
        "url": PAPER_URL,
        "location": "Fig. 2a-f and caption, p. 102",
        "finding": "The 18-24 h culture analysis supports later regional AP organization: Wnt/FGF targets centrally and differentiation peripherally. Exact onset in this Video 2 specimen is unmeasured.",
    },
    {
        "id": "V2-processing",
        "url": PAPER_URL,
        "location": "Methods, Image processing and Two-photon microscopy",
        "finding": "Published analysis uses projection, spatial blurring, later kymograph/time processing and phase extraction; this review reproduces display-intensity matrices and preserves the movie clock and measured movie scale.",
    },
]


def require_identical(actual, expected, label):
    if actual.shape != expected.shape or not np.array_equal(
        actual, expected, equal_nan=True
    ):
        raise ValueError(f"Saved {label} was not reproduced exactly")


def coverage(matrix, positions):
    """Distinguish absent columns, missing prefixes and internal missing islands."""
    valid = np.isfinite(matrix)
    result = []
    for i in range(matrix.shape[1]):
        rows = np.flatnonzero(valid[:, i])
        result.append(
            {
                "frame": i,
                "finite_distances": int(len(rows)),
                "first_valid_um": float(positions[rows[0]]) if len(rows) else None,
                "last_valid_um": float(positions[rows[-1]]) if len(rows) else None,
                "internal_gaps": int((~valid[rows[0] : rows[-1] + 1, i]).sum())
                if len(rows)
                else 0,
            }
        )
    return result


def svg_axes(path):
    """Read tick order and group IDs without touching embedded scientific images."""
    root = ET.parse(path).getroot()
    ns = {"s": "http://www.w3.org/2000/svg"}
    axes = []
    for group in root.findall(".//s:g", ns):
        if not group.get("id", "").startswith("axes_"):
            continue
        labels = []
        for axis in group.findall("./s:g", ns):
            if axis.get("id", "").startswith("matplotlib.axis_"):
                texts = [
                    {
                        "text": "".join(t.itertext()),
                        "x": float(t.get("x", "nan")),
                        "y": float(t.get("y", "nan")),
                    }
                    for t in axis.findall(".//s:text", ns)
                ]
                labels.append({"id": axis.get("id"), "text": texts})
        axes.append({"id": group.get("id"), "labels": labels})
    return axes


def style():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "savefig.dpi": 300,
            "text.color": "#252936",
            "axes.labelcolor": "#535d6b",
        }
    )
    return plt


def save_formats(fig, folder, stem):
    for ext in ("png", "svg", "pdf"):
        fig.savefig(folder / f"{stem}.{ext}", dpi=300)


def roi(ax, frame, mask, origin, direction, valid_profile, positions, *, other=None):
    ax.imshow(frame)
    ax.contour(mask, levels=[0.5], colors=["#33BBEE"], linewidths=0.6, alpha=0.65)
    normal = np.array([-direction[1], direction[0]])
    end = origin + positions[-1] / UM_PER_PX * direction
    # Dashed lines explicitly show unmeasured extension; solid sections use only
    # finite primary sample distances. Full source orientation is preserved.
    ax.plot([origin[0], end[0]], [origin[1], end[1]], "--", color="#a28cdd", lw=1)
    rows = np.flatnonzero(valid_profile)
    if len(rows):
        a, b = origin + positions[[rows[0], rows[-1]], None] / UM_PER_PX * direction
        corners = np.array(
            [a - 10 * normal, a + 10 * normal, b + 10 * normal, b - 10 * normal]
        )
        from matplotlib.patches import Polygon

        ax.add_patch(Polygon(corners, color="#7151cf", alpha=0.18))
        ax.annotate(
            "",
            xy=b,
            xytext=a,
            arrowprops={"arrowstyle": "->", "color": "#bb9bff", "lw": 1.8},
        )
    ax.plot(*origin, "+", color="white", ms=11, mew=1.8)
    if other is not None:
        o, d = other
        e = o + positions[-1] / UM_PER_PX * d
        ax.plot([o[0], e[0]], [o[1], e[1]], "--", color="#EE7733", lw=1.4)
        ax.plot(*o, "o", mfc="none", mec="#EE7733", ms=8, mew=1.4)
    ax.set_xlim(-0.5, frame.shape[1] - 0.5)
    ax.set_ylim(frame.shape[0] - 0.5, -0.5)
    ax.axis("off")


def render_rois(frames, bf, masks, current, author, figures, times, positions):
    plt = style()
    origins, directions = current["origins_xy"], current["directions_xy"]
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 4.8))
    for ax, i in zip(axes, [0, 85, 159]):
        roi(
            ax,
            frames[i],
            masks[i],
            origins[i],
            directions[i],
            np.isfinite(current["intensity"][:, i]),
            positions,
        )
        ax.set_title(f"Frame {i} · {times[i]:.2f} h", loc="left")
    fig.suptitle(
        "Video 2 · fitted-center radial strip", x=0.025, ha="left", fontsize=15
    )
    fig.text(
        0.025,
        0.115,
        "White +: fitted origin    Purple: 20 px strip    Cyan: saved BF tissue mask",
        fontsize=10,
    )
    fig.text(
        0.025,
        0.065,
        "Solid = measured tissue interval; dashed = missing extension. Source frames keep their original orientation.",
        fontsize=9,
    )
    fig.text(
        0.025,
        0.02,
        "Center supported at 1.28–5.10 h; elsewhere continued by matched BF translation. Center → periphery, without fixed A/P labels.",
        fontsize=9,
    )
    fig.subplots_adjust(left=0.015, right=0.985, top=0.88, bottom=0.19, wspace=0.04)
    save_formats(fig, figures, "video2-roi-review")
    plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(11.4, 8.5))
    for ax, i in zip(axes.flat, [0, 6, 24, 85, 100, 159]):
        roi(
            ax,
            frames[i],
            masks[i],
            origins[i],
            directions[i],
            np.isfinite(current["intensity"][:, i]),
            positions,
            other=(author["origins_xy"][i], author["directions_xy"][i]),
        )
        ax.set_title(
            f"Frame {i} · {times[i]:.2f} h" + (" · Fig. 1d anchor" if i == 85 else ""),
            loc="left",
        )
    fig.suptitle(
        "Video 2 · independent fit and mapped illustrated line",
        x=0.025,
        ha="left",
        fontsize=15,
    )
    fig.text(
        0.025,
        0.035,
        "Purple +: fitted-center primary    Orange ○: mapped Fig. 1d line; dashed orange continuation is an assumption.",
        fontsize=10,
    )
    fig.subplots_adjust(
        left=0.015, right=0.985, top=0.93, bottom=0.075, wspace=0.04, hspace=0.13
    )
    save_formats(fig, figures, "video2-roi-comparison-review")
    plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(11.4, 8.3))
    for ax, i in zip(axes.flat, [0, 24, 85, 100, 130, 159]):
        roi(
            ax,
            bf[i],
            masks[i],
            origins[i],
            directions[i],
            np.isfinite(current["intensity"][:, i]),
            positions,
        )
        ax.set_title(f"Matched Video 3 · {times[i]:.2f} h", loc="left")
    fig.suptitle(
        "Video 2 geometry · matching BF structural review",
        x=0.025,
        ha="left",
        fontsize=15,
    )
    fig.subplots_adjust(
        left=0.015, right=0.985, top=0.93, bottom=0.035, wspace=0.04, hspace=0.12
    )
    fig.savefig(figures / "video2-bf-roi-review.png", dpi=300)
    plt.close(fig)


def render_heatmaps(current, author, times, positions, limits, figures):
    import matplotlib
    from matplotlib.colors import Normalize

    plt = style()
    cmap = matplotlib.colormaps["OrRd"].copy()
    cmap.set_bad("#f1f3f6")

    def panel(ax, matrix, title, color_limits):
        values = (matrix - color_limits[0]) / (color_limits[1] - color_limits[0])
        mesh = ax.pcolormesh(
            edge(times),
            edge(positions),
            np.ma.masked_invalid(values),
            cmap=cmap,
            norm=Normalize(0, 1),
            shading="flat",
            rasterized=True,
        )
        ax.set_xlim(times[0], times[-1])
        ax.set_ylim(0, positions[-1])
        ax.set_xlabel("Video overlay time (h)")
        ax.set_title(title, loc="left")
        return mesh

    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    primary_limits = np.array(
        [np.nanmin(current["intensity"]), np.nanmax(current["intensity"])]
    )
    mesh = panel(ax, current["intensity"], "LuVeLu", primary_limits)
    ax.set_ylabel("Distance from fitted center (µm)")
    fig.colorbar(
        mesh, ax=ax, label="Relative display intensity", ticks=[0, 0.5, 1], pad=0.025
    )
    fig.subplots_adjust(left=0.09, right=0.97, bottom=0.13, top=0.9)
    save_formats(fig, figures, "video2-radial-review")
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 5.1), sharex=True, sharey=True)
    for ax, matrix, title in zip(
        axes,
        [current["intensity"], author["intensity"]],
        [
            "Independent wavefront fit · primary",
            "Mapped Fig. 1d illustrated line · comparison",
        ],
    ):
        mesh = panel(ax, matrix, title, limits)
        ax.axvline(times[85], color="#777777", lw=0.7, ls="--")
    axes[0].set_ylabel("Distance from own ROI start (µm)")
    cax = fig.add_axes([0.91, 0.22, 0.015, 0.6])
    fig.colorbar(
        mesh,
        cax=cax,
        label="Relative display intensity · shared scale",
        ticks=[0, 0.5, 1],
    )
    fig.text(
        0.025,
        0.07,
        "Both: 160 frames; 20 px width; original mean RGB; same BF translation, tissue/FOV rules and color scale.",
        fontsize=9,
    )
    fig.text(
        0.025,
        0.025,
        "Dashed time = Fig. 1d “0 min” anchor at 18.07 h. Each line has its own origin. No extra filtering or missing-value filling.",
        fontsize=9,
    )
    fig.subplots_adjust(left=0.07, right=0.85, bottom=0.19, top=0.89, wspace=0.18)
    save_formats(fig, figures, "video2-kymograph-comparison-review")
    plt.close(fig)


def render_calibration(frames, times, figures):
    plt = style()
    fig, axes = plt.subplots(2, 4, figsize=(11.4, 3.5))
    for j, i in enumerate([0, 17, 85, 159]):
        axes[0, j].imshow(frames[i, 680:, 15:165])
        axes[0, j].axis("off")
        axes[1, j].imshow(frames[i, 680:, 610:])
        axes[1, j].axis("off")
        axes[0, j].set_title(f"Frame {i} · {times[i]:.2f} h")
    fig.suptitle(
        "Source pixels · 100 µm scale and burned-in experiment clock", fontsize=14
    )
    fig.text(
        0.025,
        0.025,
        "100 µm bar: x = 21–132 px (111 px); frame 17 reads 3.61 h, overriding OCR 3.64 h. Playback frame rate is not experiment time.",
        fontsize=9,
    )
    fig.subplots_adjust(left=0.02, right=0.98, top=0.81, bottom=0.15, hspace=0.3)
    fig.savefig(figures / "video2-calibration-review.png", dpi=300)
    plt.close(fig)


def render_correspondence(figure, registration, frames, figures):
    from PIL import Image

    plt = style()
    image = np.array(Image.open(figure).convert("RGB"))
    x, y, w, h = registration["panel_crop_xy_wh"]
    crop = image[y : y + h, x : x + w]
    yy, xx = np.mgrid[:h, :w]
    m = np.array(registration["reference_transform_panel_to_video"])
    xy = np.stack([xx, yy], axis=-1) @ m[:, :2].T + m[:, 2]
    matched = (
        np.stack(
            [
                ndi.map_coordinates(
                    frames[85, ..., c].astype(float),
                    [xy[..., 1], xy[..., 0]],
                    order=1,
                    mode="constant",
                )
                for c in range(3)
            ],
            axis=-1,
        )
        / 255
    )
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 4.7))
    for ax, a, title in zip(
        axes,
        [crop, matched, 0.5 * crop / 255 + 0.5 * matched],
        [
            "Fig. 1d · “0 min”",
            "Video 2 frame 85 · 18.07 h",
            "50% image blend · same panel coordinates",
        ],
    ):
        ax.imshow(np.clip(a, 0, 1) if np.issubdtype(a.dtype, np.floating) else a)
        ax.axis("off")
        ax.set_title(title, loc="left", fontsize=11)
    fig.text(
        0.025,
        0.08,
        "Image features establish correspondence; drawn arrow endpoints remain approximate. The red square is a local intensity ROI.",
        fontsize=9,
    )
    fig.text(
        0.025,
        0.03,
        "The panel-relative “0 min” does not reset Video 2’s source clock. This transfer does not recover a full author ROI trajectory.",
        fontsize=9,
    )
    fig.subplots_adjust(left=0.015, right=0.985, top=0.94, bottom=0.15, wspace=0.07)
    fig.savefig(figures / "video2-figure-correspondence-review.png", dpi=300)
    plt.close(fig)


def run(source_dir, output, refit_geometry=False, publisher_figure=None):
    base = ASSET_ROOT / "data/derived/lauschke-2013"
    figures = output / "figures"
    records = output / "data"
    figures.mkdir(parents=True, exist_ok=True)
    records.mkdir(parents=True, exist_ok=True)
    reference_paths = sorted(base.glob("video2-*")) + sorted(
        (ASSET_ROOT / "figures/lauschke-2013").glob("video2-*")
    )
    reference_paths = [p for p in reference_paths if p.is_file()]
    before = {str(p.relative_to(ASSET_ROOT)): digest(p) for p in reference_paths}
    movies = {
        n: source_dir / f"41586_2013_BFnature11804_MOESM{291 + n}_ESM.mov"
        for n in [2, 3]
    }
    for n, p in movies.items():
        if digest(p) != SOURCE_HASHES[n]:
            raise ValueError(f"Source Video {n} changed")
    frames, bf = [np.array(decode(movies[n])) for n in [2, 3]]
    if frames.shape != (160, 744, 751, 3) or bf.shape != frames.shape:
        raise ValueError(
            "Unexpected source frame count, dimensions or channel correspondence"
        )
    current = dict(np.load(base / "video2-kymograph.npz"))
    author = dict(np.load(base / "video2-author-line.npz"))
    geometry = dict(np.load(base / "video2-geometry.npz"))
    registration = json.loads(
        (base / "video2-author-line-registration.json").read_text()
    )
    fit = json.loads((base / "video2-center-fit.json").read_text())
    fronts = json.loads((base / "video2-center-fronts.json").read_text())
    times, positions = current["time_h"], current["position_um"]
    require_identical(
        read_times(base / "video2-timestamps.json", len(frames)), times, "timestamps"
    )
    require_identical(author["time_h"], times, "author-line timestamps")
    require_identical(author["position_um"], positions, "author-line distance grid")
    require_identical(
        current["origins_xy"], geometry["origins_xy"], "origin trajectory"
    )
    np.testing.assert_allclose(
        np.linalg.norm(current["directions_xy"], axis=1), 1, atol=1e-14
    )
    center, radii = fit_common_center(fronts)
    # Re-starting a nonlinear optimizer from the median need not land at the
    # identical stopping iterate used by consensus refinement. Keep this small
    # optimizer tolerance separate from bitwise intensity reproduction.
    np.testing.assert_allclose(center, fit["center_xy_reference_px"], rtol=0, atol=1e-3)
    np.testing.assert_allclose(
        current["origins_xy"],
        np.array(fit["center_xy_reference_px"]) + geometry["shifts_xy"],
        rtol=0,
        atol=1e-8,
    )
    geometry_refit = {"performed": refit_geometry}
    if refit_geometry:
        print("Rebuilding BF masks, translation and early-wavefront center", flush=True)
        o, d, m, s, refit, _ = radial_geometry(frames, bf, times)
        for a, e, label in [
            (d, current["directions_xy"], "refitted directions"),
            (s, geometry["shifts_xy"], "rebuilt BF shifts"),
        ]:
            require_identical(a, e, label)
        np.testing.assert_allclose(o, current["origins_xy"], rtol=0, atol=1e-3)
        differences = np.sum(m != geometry["masks"], axis=(1, 2))
        geometry_refit.update(
            {
                "masks_exactly": bool(np.array_equal(m, geometry["masks"])),
                "mask_difference_pixels": int(differences.sum()),
                "mask_difference_fraction": float(differences.sum() / m.size),
                "mask_difference_pixels_per_frame": differences.tolist(),
                "translation_exactly": True,
                "directions_exactly": True,
                "max_origin_difference_px": float(
                    np.max(abs(o - current["origins_xy"]))
                ),
                "origin_tolerance_px": 1e-3,
            }
        )
        rebuilt_masks = m
    origins, directions, start, tip = mapped_line(registration, geometry["shifts_xy"])
    errors = validate_registration(registration)
    require_identical(origins, author["origins_xy"], "mapped illustrated origins")
    require_identical(
        directions, author["directions_xy"], "mapped illustrated directions"
    )
    results = {}
    for label, o, d, sigma, saved in [
        (
            "primary",
            current["origins_xy"],
            current["directions_xy"],
            0,
            current["intensity"],
        ),
        (
            "primary_spatial_control",
            current["origins_xy"],
            current["directions_xy"],
            SIGMA_UM,
            current["spatial_smoothed_intensity"],
        ),
        ("illustrated", origins, directions, 0, author["intensity"]),
        (
            "illustrated_spatial_control",
            origins,
            directions,
            SIGMA_UM,
            author["spatial_smoothed_intensity"],
        ),
        (
            "illustrated_fixed_image",
            np.tile(start, (160, 1)),
            directions,
            0,
            author["fixed_image_intensity"],
        ),
    ]:
        matrix, counts = sample_line(
            frames, o, d, positions, geometry["masks"], sigma_um=sigma
        )
        require_identical(matrix, saved, label)
        results[label] = (matrix, counts)
        print(f"{label}: exact reproduction", flush=True)
    # Also audit the original first-exit sampler, separate from comparison's
    # longest-valid-run rule. Both happen to match the preserved primary here.
    require_identical(
        sample(
            frames,
            current["origins_xy"],
            current["directions_xy"],
            positions,
            UM_PER_PX,
            geometry["masks"],
        ),
        current["intensity"],
        "original first-exit primary",
    )
    require_identical(
        author["current_intensity"],
        current["intensity"],
        "reference embedded in comparison",
    )
    require_identical(
        author["valid_width_counts"],
        results["illustrated"][1],
        "illustrated valid-width counts",
    )
    if refit_geometry:
        # Preserve the reviewed masks even if a numerical threshold rebuild has
        # a few edge-pixel differences. Test the effect on both actual strips.
        geometry_refit["rebuilt_mask_sampling"] = {}
        for label, o, d, saved in [
            (
                "primary",
                current["origins_xy"],
                current["directions_xy"],
                current["intensity"],
            ),
            ("illustrated", origins, directions, author["intensity"]),
        ]:
            rebuilt, counts = sample_line(frames, o, d, positions, rebuilt_masks)
            same = np.array_equal(rebuilt, saved, equal_nan=True)
            same_counts = np.array_equal(counts, results[label][1])
            geometry_refit["rebuilt_mask_sampling"][label] = {
                "matrix_exactly": bool(same),
                "counts_exactly": bool(same_counts),
            }
            if not same or not same_counts:
                raise ValueError("Rebuilt mask affects reviewed radial samples")
    finite = np.r_[
        current["intensity"][np.isfinite(current["intensity"])],
        author["intensity"][np.isfinite(author["intensity"])],
    ]
    limits = np.array([finite.min(), finite.max()])
    require_identical(limits, author["shared_color_limits"], "shared color limits")
    render_rois(
        frames, bf, geometry["masks"], current, author, figures, times, positions
    )
    render_heatmaps(current, author, times, positions, limits, figures)
    render_calibration(frames, times, figures)
    correspondence = False
    if publisher_figure is not None:
        if digest(publisher_figure) != registration["publisher_image_sha256"]:
            raise ValueError("Publisher reference image changed")
        render_correspondence(publisher_figure, registration, frames, figures)
        correspondence = True
    np.savez_compressed(
        records / "video2-review.npz",
        intensity=current["intensity"],
        illustrated_intensity=author["intensity"],
        time_h=times,
        position_um=positions,
        origins_xy=current["origins_xy"],
        directions_xy=current["directions_xy"],
        valid_width_counts=results["primary"][1],
        valid_mask=np.isfinite(current["intensity"]),
        illustrated_valid_width_counts=results["illustrated"][1],
        illustrated_origins_xy=origins,
        illustrated_directions_xy=directions,
        shared_color_limits=limits,
    )
    paths = {
        "gallery_primary": ASSET_ROOT
        / "figures/comparison/lauschke-2013-mpsm-full.svg",
        "saved_sampling": ASSET_ROOT / "figures/lauschke-2013/video2-sampling.svg",
        "saved_author_comparison": ASSET_ROOT
        / "figures/lauschke-2013/video2-author-line-comparison.svg",
        "review_primary": figures / "video2-radial-review.svg",
        "review_comparison": figures / "video2-kymograph-comparison-review.svg",
    }
    primary_cov = coverage(current["intensity"], positions)
    author_cov = coverage(author["intensity"], positions)
    report = {
        "dataset": "lauschke-2013-mpsm",
        "review_version": "video2-radial-review-v1",
        "primary_selection": {
            "input": "data/derived/lauschke-2013/video2-kymograph.npz",
            "key": "intensity",
            "recommendation": "preserve independent wavefront-fit primary",
        },
        "source_files": {
            str(n): {"filename": p.name, "sha256": digest(p), "bytes": p.stat().st_size}
            for n, p in movies.items()
        },
        "source_shape_time_y_x_rgb": list(frames.shape),
        "playback_note": "H.264 playback is padded on the right from source width 751 to width 752; source coordinates remain 751-wide.",
        "all_variants_reproduced_exactly": list(results),
        "original_first_exit_sampler_reproduced_exactly": True,
        "embedded_reference_reproduced_exactly": True,
        "geometry_refit": geometry_refit,
        "saved_contour_common_center_refit": {
            "center_xy_px": center.tolist(),
            "max_difference_from_saved_px": float(
                np.max(abs(center - np.array(fit["center_xy_reference_px"])))
            ),
            "optimizer_tolerance_px": 1e-3,
        },
        "figure_correspondence_visually_available": correspondence,
        "time": {
            "range_h": [float(times[0]), float(times[-1])],
            "frames": len(times),
            "interval_min_range": (
                np.array([np.min(np.diff(times)), np.max(np.diff(times))]) * 60
            ).tolist(),
            "frame_17_correction_h": float(times[17]),
            "figure_1d_zero_min_source_frame": 85,
            "figure_1d_zero_min_overlay_h": float(times[85]),
            "interpretation": "Preserve audited burned-in clock; do not impose nominal Methods interval or re-zero using figure thumbnails.",
        },
        "scale": {
            "um_per_source_px": UM_PER_PX,
            "bar_um": 100,
            "bar_x_endpoints_px": [21, 132],
            "bar_y_px": 700,
            "reading_precision_px": 1,
        },
        "geometry": {
            "type": "independent early-wavefront curvature center + matched BF translation",
            "supported_time_h": fit["supported_time_h"],
            "accepted_frames": fit["accepted_frames"],
            "median_arc_residual_um": fit["median_joint_arc_residual_um"],
            "disjoint_time_center_separation_um": fit[
                "disjoint_time_center_separation_um"
            ],
            "direction_deg_image_x_right_y_down": -72,
            "direct_fit_contours_crossing_ray": fit["ray"][
                "directly_crossed_fit_frames"
            ],
            "later_motion_assumption": "Translation continuation only; no independent later center validation, tissue deformation correction or cell tracking.",
        },
        "measurement": {
            "shape_space_time": list(current["intensity"].shape),
            "distance_grid_um": [float(positions[0]), float(positions[-1])],
            "strip_width_px": WIDTH_PX,
            "width_um": WIDTH_PX * UM_PER_PX,
            "transverse_samples": 21,
            "minimum_valid_samples": 16,
            "channel": "decoded mean RGB display values of LuVeLu Venus-channel movie; not raw fluorescence counts",
            "interpolation": "bilinear signal; nearest-neighbor categorical BF tissue mask",
            "primary_filtering": "none; width averaging only",
            "spatial_control_sigma_um": SIGMA_UM,
            "temporal_processing_primary": "none",
            "missing": "NaN for absent tissue/FOV; >=75% valid width; original first-exit primary and longest-run pair agree exactly on this input",
            "shared_raw_color_limits": limits.tolist(),
        },
        "primary_coverage": primary_cov,
        "illustrated_coverage": author_cov,
        "polarity": {
            "display_labels": ["Center", "Periphery"],
            "fixed_AP_labels_supported": False,
            "reason": "The whole series includes early posterior-only incomplete mPSM; no matching anterior-marker movie establishes specimen-specific onset later.",
            "temporal_qualification": "Paper describes incomplete posterior-like mPSM before approximately 20 h, and later regional AP organization. Do not use 20 h as an exact onset threshold for this specimen.",
            "confidence": "high for central/peripheral coordinate and rejection of uniform AP labels; unresolved specimen-specific anterior onset",
            "recommended_display": "Center-side zero at bottom and increasing peripheral distance above, matching Fig. 1f. Keep source frames unchanged.",
        },
        "illustrated_line": {
            "mapped_start_xy_frame85": start.tolist(),
            "mapped_tip_xy_frame85": tip.tolist(),
            "median_registration_residual_video_px": float(np.median(errors)),
            "graphic_endpoint_precision_panel_px": registration[
                "graphic_precision_panel_px"
            ],
            "interpretation": "Approximate mapped author drawing; no deposited ROI or temporal trajectory. Red square is separate local-trace ROI.",
        },
        "evidence": EVIDENCE,
        "evidence_checked": "2026-11-15",
        "environment": {
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
            "av": __import__("av").__version__,
            "matplotlib": __import__("matplotlib").__version__,
        },
        "limitations": [
            "Compressed display movie only; no raw photon counts, exact author line, Hilbert phase or published phase-gradient reproduction.",
            "Last sampled distance is tissue/FOV limited and is not a verified biological rim or arrest front.",
            "A fitted curvature center is not a molecular posterior landmark, pacemaker or material cell coordinate.",
            "Only one accepted contour directly crosses the selected ray; other perpendicularity relies on the approximate circular model.",
        ],
        "svg_axis_audit": {
            k: {"path": str(p), "axes": svg_axes(p)}
            for k, p in paths.items()
            if p.exists()
        },
        "script": "analysis/audit_lauschke_video2.py",
        "script_sha256": digest(__file__),
        "dependency_hashes": {
            n: digest(Path(__file__).with_name(n))
            for n in [
                "reproduce_lauschke_views.py",
                "extract_lauschke_author_line.py",
                "lauschke_wavefront_center.py",
                "extract_video_kymographs.py",
            ]
        },
        "preserved_original_sha256": before,
    }
    for relative, sha in before.items():
        if digest(ASSET_ROOT / relative) != sha:
            raise ValueError("Original asset changed during review")
    report["original_assets_preserved_exactly"] = True
    (records / "video2-review.json").write_text(json.dumps(report, indent=2) + "\n")
    manifest = []
    for p in sorted(figures.glob("*")) + sorted(records.glob("*")):
        manifest.append(
            {
                "path": str(p.relative_to(output)),
                "bytes": p.stat().st_size,
                "sha256": digest(p),
                "source_url": ARTICLE_URL,
                "rights": "Derived from Nature copyrighted display movie; no open reuse license verified.",
            }
        )
    (output / "asset-registration.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "exact_variants": list(results),
                "full_geometry_refit": refit_geometry,
                "preserved_original_files": len(before),
                "fixed_AP_labels_supported": False,
                "output": str(output.resolve()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/lauschke-video2-review")
    )
    parser.add_argument("--refit-geometry", action="store_true")
    parser.add_argument("--publisher-figure", type=Path)
    args = parser.parse_args()
    run(args.source_dir, args.output, args.refit_geometry, args.publisher_figure)

# SPDX-License-Identifier: MIT
"""Detail-only Sonnen S3 sector/coverage sensitivity, preserving the primary.

No center fitting, AP inference, or intensity-derived tissue mask. The source
movie is an exported LuVeLu microfluidic assay with a separate dye inset.
"""

import argparse
import hashlib
import json
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from export_video_rois import bands_from_path
from extract_sonnen_additional import SETTINGS, image_validity, sample_image
from paths import ASSET_ROOT, REPO_ROOT

DATASET = "sonnen-2018-microfluidic"
VIDEO = "movie-s3"
ARTICLE = "https://pmc.ncbi.nlm.nih.gov/articles/PMC5847172/"
SOURCE = "https://pmc-oa-opendata.s3.amazonaws.com/PMC5847172.1/mmc4.mp4"
DATA_REL = Path("data/derived/sonnen-2018/s3-candidate-review")
FIG_REL = Path("figures/sonnen-2018/s3-candidate-review")
ORIGIN = np.array([235.0, 290.0])
# Case-specific visible outer-envelope guards, manually reviewed with full bands.
# They are not tissue segmentation, wavefronts, arrest fronts, or fitted radii.
LEFT_KEYS = np.array(
    [
        [0, 60],
        [10, 78],
        [25, 90],
        [40, 108],
        [55, 124],
        [75, 124],
        [95, 144],
        [110, 144],
    ],
    float,
)
RIGHT_KEYS = np.array(
    [
        [0, 80],
        [10, 103],
        [25, 130],
        [40, 144],
        [55, 162],
        [75, 174],
        [95, 178],
        [110, 178],
    ],
    float,
)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_json(p, x):
    p.write_text(json.dumps(x, indent=2, allow_nan=False) + "\n")


def sector_geometry(position_um, scale, angle_deg):
    """Signed angle from image-up; positive is toward native image-right."""
    theta = np.deg2rad(angle_deg)
    direction = np.array([np.sin(theta), -np.cos(theta)])
    normal = np.array([-direction[1], direction[0]])
    return ORIGIN + position_um[:, None] / scale * direction, normal


def apply_extent(values, position_um, scale, extent_px):
    out = values.copy()
    out[position_um[:, None] / scale > extent_px[None, :]] = np.nan
    return out


def font(size):
    import matplotlib

    path = Path(matplotlib.get_data_path()) / "fonts/ttf/DejaVuSans.ttf"
    return ImageFont.truetype(str(path), size)


def roi_thumb(
    frame,
    old_path,
    new_path,
    old_extent,
    new_extent,
    old_normal,
    new_normal,
    width,
    scale,
    positions,
    index,
    time_h,
    size=360,
):
    im = Image.fromarray(frame).convert("RGB")
    d = ImageDraw.Draw(im)
    for path, extent, normal, color, line_width in [
        (old_path, old_extent, old_normal, "#a8d4e8", 2),
        (new_path, new_extent, new_normal, "#ffb44a", 3),
    ]:
        valid = positions / scale <= extent
        p = path[valid]
        band = np.r_[p - width / 2 * normal, (p + width / 2 * normal)[::-1]]
        d.line([tuple(q) for q in np.r_[band, band[:1]]], fill=color, width=line_width)
        if color == "#a8d4e8":
            for j in range(0, len(p) - 1, 12):
                d.line([tuple(q) for q in p[j : j + 7]], fill=color, width=2)
        else:
            d.line([tuple(q) for q in p], fill=color, width=2)
            for label, point in [("O", p[0]), ("E", p[-1])]:
                x, y = point
                d.rectangle((x + 6, y - 10, x + 27, y + 15), fill="black")
                d.text((x + 8, y - 10), label, fill=color, font=font(22))
    # This box is an exclusion, not another gene signal or extraction ROI.
    d.rectangle((0, 0, 48, 48), outline="#ff7777", width=2)
    im.thumbnail((size, size))
    out = Image.new("RGB", (size, size + 34), "white")
    out.paste(im, (0, 34))
    ImageDraw.Draw(out).text(
        (6, 7), f"Frame {index} · {time_h:.2f} h", fill="#242833", font=font(17)
    )
    return out


def render(
    frames,
    baseline,
    left,
    right,
    matched,
    times,
    positions,
    paths,
    normals,
    widths,
    scale,
    extents,
    figs,
):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    from matplotlib.backends.backend_pdf import PdfPages

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 10,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    lo = float(min(np.nanmin(v) for v in [baseline, left, right]))
    hi = float(max(np.nanmax(v) for v in [baseline, left, right]))
    xe = np.r_[
        times[0] - (times[1] - times[0]) / 2,
        (times[:-1] + times[1:]) / 2,
        times[-1] + (times[-1] - times[-2]) / 2,
    ]
    ye = np.r_[
        positions[0] - 0.5, (positions[:-1] + positions[1:]) / 2, positions[-1] + 0.5
    ]
    cmap = plt.get_cmap("OrRd").copy()
    cmap.set_bad("#edf0f4")

    def heat(ax, m, title):
        q = ax.pcolormesh(
            xe,
            ye,
            np.ma.masked_invalid(m),
            cmap=cmap,
            norm=Normalize(lo, hi),
            shading="flat",
            rasterized=True,
        )
        ax.set(
            xlim=(times[0], times[-1]),
            ylim=(0, positions[-1]),
            xlabel="Time (h)",
            title=title,
        )
        return q

    fig, axs = plt.subplots(1, 2, figsize=(12.8, 6.4), sharey=True)
    heat(axs[0], baseline, "Current · image-up strip")
    m = heat(axs[1], left, "Candidate · 15° left + conservative coverage")
    axs[0].set_ylabel("Distance from common image origin (approx. µm)")
    fig.subplots_adjust(left=0.085, right=0.88, bottom=0.29, top=0.83, wspace=0.25)
    cb = fig.add_axes([0.91, 0.29, 0.014, 0.54])
    fig.colorbar(m, cax=cb, label="Shared raw display intensity (0–255)")
    fig.suptitle(
        "Sonnen 2018 · Movie S3 · sector and coverage review",
        x=0.085,
        y=0.96,
        ha="left",
        fontweight="bold",
        fontsize=15,
    )
    fig.text(
        0.085,
        0.905,
        "111 frames · 0–18.33 h · common O=(235,290) px · 70 µm strip · no signal/time filtering",
        fontsize=10,
    )
    fig.text(
        0.085,
        0.17,
        "Gray means outside retained image coverage. Candidate changes direction AND the conservative outer cap; neither is anatomical segmentation.",
        fontsize=8.6,
    )
    fig.text(
        0.085,
        0.12,
        "O is a manual image origin, not a validated wavefront center. E is a retained sampling endpoint. No fixed A/P is assigned.",
        fontsize=9,
    )
    fig.text(
        0.085,
        0.065,
        "LuVeLu microfluidic assay (Fig.3); Cascade Blue inset excluded. Exact drug/control pulse identity of this export remains unresolved.",
        fontsize=8.5,
    )
    for ext in ["svg", "png", "pdf"]:
        fig.savefig(figs / f"s3-current-vs-candidate.{ext}", dpi=190)
    plt.close(fig)
    fig, axs = plt.subplots(1, 3, figsize=(15, 5.7), sharey=True)
    for ax, m, title in zip(
        axs,
        matched,
        [
            "Matched support · current",
            "Matched support · 15° left",
            "Matched support · 15° right",
        ],
    ):
        q = heat(ax, m, title)
    axs[0].set_ylabel("Distance from common O (approx. µm)")
    fig.subplots_adjust(left=0.07, right=0.9, bottom=0.22, top=0.82, wspace=0.2)
    cb = fig.add_axes([0.93, 0.22, 0.012, 0.6])
    fig.colorbar(q, cax=cb, label="Shared raw display intensity")
    fig.suptitle(
        "Angular controls · identical distance/width/time support",
        fontsize=15,
        fontweight="bold",
    )
    fig.text(
        0.07,
        0.09,
        "All three use the intersection of current, left-sector and right-sector coverage caps. Case-specific ±15° controls are not optimized directions or defaults.",
        fontsize=9,
    )
    for ext in ["svg", "png"]:
        fig.savefig(figs / f"s3-matched-support-controls.{ext}", dpi=190)
    plt.close(fig)
    board = Image.new("RGB", (1080, 2 * 394 + 110), "white")
    d = ImageDraw.Draw(board)
    d.text(
        (12, 12),
        "S3 ROI review · cyan: current · orange: 15° left control",
        fill="#242833",
        font=font(25),
    )
    d.text(
        (12, 49),
        "O / outward only; shorter candidate caps guard the outer band. Red box excludes the dye inset.",
        fill="#606977",
        font=font(18),
    )
    for j, i in enumerate([0, 20, 40, 55, 80, 110]):
        im = roi_thumb(
            frames[i],
            paths[0],
            paths[1],
            extents[0][i],
            extents[1][i],
            normals[0],
            normals[1],
            widths,
            scale,
            positions,
            i,
            times[i],
        )
        board.paste(im, ((j % 3) * 360, 100 + (j // 3) * 394))
    board.save(figs / "s3-roi-board.jpg", quality=94)
    sheets = []
    for start in range(0, len(frames), 16):
        sheet = Image.new("RGB", (1280, 4 * 354), "white")
        for j, i in enumerate(range(start, min(start + 16, len(frames)))):
            im = roi_thumb(
                frames[i],
                paths[0],
                paths[1],
                extents[0][i],
                extents[1][i],
                normals[0],
                normals[1],
                widths,
                scale,
                positions,
                i,
                times[i],
                size=320,
            )
            sheet.paste(im, ((j % 4) * 320, (j // 4) * 354))
        sheet.save(
            figs
            / f"s3-roi-frames-{start:03d}-{min(start + 15, len(frames) - 1):03d}.jpg",
            quality=90,
        )
        sheets.append(sheet)
    with PdfPages(figs / "s3-all-frame-rois.pdf") as pdf:
        for im in sheets:
            fig, ax = plt.subplots(figsize=(12.8, 14.16))
            ax.imshow(im)
            ax.axis("off")
            fig.subplots_adjust(0, 0, 1, 1)
            pdf.savefig(fig, dpi=140)
            plt.close(fig)
    fig, axs = plt.subplots(3, 1, figsize=(10.5, 8.7), sharex=True)
    for e, label in zip(
        extents,
        [
            "current manual cap",
            "left full-band guard",
            "right full-band guard",
            "common matched support",
        ],
    ):
        axs[0].plot(times, e, label=label)
    axs[0].set_ylabel("Retained image extent (px)")
    axs[0].legend(fontsize=8, ncol=2)
    for m, label in zip(matched[1:], ["15° left vs current", "15° right vs current"]):
        diff = m - matched[0]
        rms = np.sqrt(np.nanmean(diff**2, axis=0))
        axs[1].plot(times, rms, label=label)
    axs[1].set_ylabel("Matched-support RMS (0–255)")
    axs[1].legend(fontsize=9)
    for m, label in zip(
        [baseline, left, right], ["current", "left candidate", "right control"]
    ):
        axs[2].plot(times, np.isfinite(m).sum(0), label=label)
    axs[2].set(ylabel="Retained distance bins", xlabel="Experiment time (h)")
    axs[2].legend(fontsize=9)
    fig.suptitle(
        "S3 direction and coverage sensitivity · no center / anatomical identity claim"
    )
    fig.tight_layout()
    fig.savefig(figs / "s3-geometry-diagnostics.png", dpi=180)
    plt.close(fig)
    return [lo, hi]


def run(asset_root=ASSET_ROOT, output=REPO_ROOT / "outputs/sonnen-s3-candidate"):
    output.mkdir(parents=True, exist_ok=True)
    source = asset_root / "videos/sonnen-2018/movie-s3.mp4"
    assert sha(source) == SETTINGS["s3"]["sha256"], "Wrong S3 export"
    baseline_file = asset_root / "data/derived/sonnen-2018/movie-s3/kymograph.npz"
    protected = [
        p
        for folder in [
            asset_root / "data/derived/sonnen-2018/movie-s3",
            asset_root / "figures/sonnen-2018/movie-s3",
        ]
        for p in folder.rglob("*")
        if p.is_file()
    ]
    protected += [source, asset_root / "videos/sonnen-2018/movie-s3.jpg"]
    before = {str(p.relative_to(REPO_ROOT)): sha(p) for p in protected}
    frozen_path = output / "s1-frozen-before.json"
    frozen = json.loads(frozen_path.read_text()) if frozen_path.is_file() else {}
    with av.open(str(source)) as c:
        decoded = [
            (f.to_ndarray(format="rgb24"), float(f.pts * f.time_base))
            for f in c.decode(video=0)
        ]
    frames = np.stack([x[0] for x in decoded])
    starts = np.array([x[1] for x in decoded])
    starts -= starts[0]
    assert frames.shape == (111, 512, 512, 3)
    with np.load(baseline_file) as z:
        baseline = z["intensity"].copy()
        times = z["time_h"].copy()
        positions = z["position_um"].copy()
        baseline_paths = z["path_xy"].copy()
        baseline_normal = z["normals_xy"][0].copy()
        current_extent = z["coverage_extent_px"].copy()
        scale = float(z["um_per_px"])
        width = float(z["strip_width_px"])
    left_path, left_normal = sector_geometry(positions, scale, -15)
    right_path, right_normal = sector_geometry(positions, scale, 15)
    paths = [baseline_paths[0], left_path, right_path]
    normals = [baseline_normal, left_normal, right_normal]
    mask = image_validity("s3", (512, 512))
    full = []
    counts = []
    for p, n in zip(paths, normals):
        raw = np.full(baseline.shape, np.nan)
        nc = np.zeros(baseline.shape, np.int16)
        for i, frame in enumerate(frames):
            raw[:, i], nc[:, i] = sample_image(frame[:, :, 1], p, n, width, mask)
        full.append(raw)
        counts.append(nc)
    reproduction = apply_extent(full[0], positions, scale, current_extent)
    np.testing.assert_array_equal(reproduction, baseline)
    left_extent = np.minimum(
        current_extent, np.interp(np.arange(111), LEFT_KEYS[:, 0], LEFT_KEYS[:, 1])
    )
    right_extent = np.minimum(
        current_extent, np.interp(np.arange(111), RIGHT_KEYS[:, 0], RIGHT_KEYS[:, 1])
    )
    common_extent = np.minimum.reduce([current_extent, left_extent, right_extent])
    extents = [current_extent, left_extent, right_extent, common_extent]
    left = apply_extent(full[1], positions, scale, left_extent)
    right = apply_extent(full[2], positions, scale, right_extent)
    matched = [apply_extent(m, positions, scale, common_extent) for m in full]
    data = asset_root / DATA_REL
    figs = asset_root / FIG_REL
    data.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)
    numeric = data / "s3-sector-candidate.npz"
    offsets = np.linspace(-width / 2, width / 2, int(np.ceil(width)) + 1)
    np.savez_compressed(
        numeric,
        intensity=left,
        baseline_intensity=baseline,
        right_intensity=right,
        matched_current_intensity=matched[0],
        matched_left_intensity=matched[1],
        matched_right_intensity=matched[2],
        left_fov_intensity=full[1],
        right_fov_intensity=full[2],
        time_h=times,
        position_um=positions,
        frame_index=np.arange(111),
        path_xy=np.tile(left_path, (111, 1, 1)),
        normals_xy=np.tile(left_normal, (111, 1)),
        right_path_xy=np.tile(right_path, (111, 1, 1)),
        right_normals_xy=np.tile(right_normal, (111, 1)),
        baseline_path_xy=baseline_paths,
        baseline_normals_xy=np.tile(baseline_normal, (111, 1)),
        image_validity_mask=mask,
        valid=np.isfinite(left),
        fov_width_counts=counts[1],
        right_fov_width_counts=counts[2],
        baseline_fov_width_counts=counts[0],
        coverage_extent_px=left_extent,
        current_coverage_extent_px=current_extent,
        right_coverage_extent_px=right_extent,
        matched_coverage_extent_px=common_extent,
        width_offsets_px=offsets,
        strip_width_px=width,
        um_per_px=scale,
        origin_xy=ORIGIN,
        angles_deg=np.array([-15.0, 0.0, 15.0]),
    )
    roi_frames = []
    for i in range(111):
        bands, lines = bands_from_path(
            left_path,
            np.tile(left_normal, (len(positions), 1)),
            np.isfinite(left[:, i]),
            width,
        )
        ids = np.flatnonzero(np.isfinite(left[:, i]))
        refs = left_path[[ids[0], ids[-1]]].round(2).tolist() if len(ids) else []
        roi_frames.append(
            dict(
                index=i,
                experiment_h=float(times[i]),
                bands=bands,
                lines=lines,
                reference_points=refs,
            )
        )
    overlay = {
        "schema_version": 1,
        "dataset_id": DATASET,
        "video_id": VIDEO,
        "source_sha256": sha(source),
        "playback_sha256": sha(source),
        "width": 512,
        "height": 512,
        "frame_starts_s": np.round(starts, 9).tolist(),
        "frames": roi_frames,
        "direction_labels": ["O", "E"],
        "geometry_input": str(DATA_REL / numeric.name),
        "geometry_input_sha256": sha(numeric),
        "scope": "Candidate angular/coverage control only. O is manual image origin; E is retained sampling endpoint, not a biological boundary. Current movie overlay remains unchanged.",
    }
    write_json(data / "s3-candidate-video-roi.json", overlay)
    limits = render(
        frames,
        baseline,
        left,
        right,
        matched,
        times,
        positions,
        paths,
        normals,
        width,
        scale,
        extents,
        figs,
    )
    after = {name: sha(REPO_ROOT / name) for name in before}
    assert before == after, "S3 baseline changed"
    assert all(sha(asset_root / name) == h for name, h in frozen.items()), (
        "Frozen S1 package changed"
    )
    coverage = {
        "policy": "Predefined sector-angle controls, with case-specific manually reviewed conservative outer-band guards and exact FOV/annotation exclusion. Not anatomical segmentation.",
        "left_keys_frame_radius_px": LEFT_KEYS.tolist(),
        "right_keys_frame_radius_px": RIGHT_KEYS.tolist(),
        "time_interpolation": "Linear between keys in source frame index; intersect each guard with original vertical manual cap.",
        "matched_support": "Minimum of current, left and right extent caps, plus each branch's full-width FOV/annotation support.",
        "scope": "Outer silhouette-envelope inspection does not resolve dark internal regions as absent tissue versus low reporter intensity. Retain measured dark values; do not threshold signal.",
        "inspected_frames": list(range(111)),
        "revision_reason": "Rotating the vertical path can move outer corners outside visible culture, so inherited caps alone were not accepted as sector support.",
    }
    write_json(data / "s3-coverage-review.json", coverage)
    stats = {
        "baseline_missing": int(np.isnan(baseline).sum()),
        "candidate_missing": int(np.isnan(left).sum()),
        "right_missing": int(np.isnan(right).sum()),
        "matched_missing": int(np.isnan(matched[0]).sum()),
        "left_vs_current_matched_rms": float(
            np.sqrt(np.nanmean((matched[1] - matched[0]) ** 2))
        ),
        "right_vs_current_matched_rms": float(
            np.sqrt(np.nanmean((matched[2] - matched[0]) ** 2))
        ),
    }
    limits_text = [
        "O=(235,290) is a retained manual image origin, not a fitted wavefront center or molecular posterior.",
        "±15° are explicit case-specific sensitivity controls, not optimized directions or reusable defaults.",
        "Outer caps are conservative visual image-envelope estimates, not anatomical masks, segmentation endpoints, or arrest fronts.",
        "Dark internal regions cannot be classified as absent tissue versus low expression from this fluorescence display alone; their measured values are retained.",
        "S3 is the Fig.3 microfluidic assay, not the Fig.2B reference; exact exported drug/control pulse identity is unresolved.",
        "100 µm/72px is approximate export calibration, assuming equal x/y scaling; no raw z-stack or raw-detector claim.",
    ]
    provenance = {
        "dataset": DATASET,
        "source_movie": "Movie S3",
        "article_url": ARTICLE,
        "source_url": SOURCE,
        "source_sha256": sha(source),
        "source_shape": list(frames.shape),
        "baseline_path": str(baseline_file.relative_to(asset_root)),
        "baseline_sha256": sha(baseline_file),
        "candidate_sha256": sha(numeric),
        "shape_space_time": list(left.shape),
        "time_range_h": [float(times[0]), float(times[-1])],
        "clock": "All 111 original h:mm labels, 10 min/frame 0:00–18:20, copied unchanged from baseline; playback 25 fps is separate.",
        "reporter": "LuVeLu",
        "target_gene": "Lfng",
        "preparation": "Microfluidic ex vivo mPSM",
        "condition": "Drug/control pulse identity of this exported specimen unresolved;37°C chip protocol is documented.",
        "channel": "Decoded green channel of grayscale rendered LuVeLu; Cascade Blue inset is a separate perfusion reference and excluded.",
        "scale": {
            "bar_um": 100,
            "bar_px": 72,
            "um_per_px": scale,
            "approximate": True,
            "assumption": "Equal x/y export scaling; raw-camera 1.38 µm/px not substituted.",
        },
        "origin": {
            "xy": ORIGIN.tolist(),
            "type": "manual fixed image ROI",
            "center_fit_performed": False,
            "COM_used": False,
            "AP_assigned": False,
        },
        "sampling": {
            "width_um": 70,
            "width_px": width,
            "offset_count": len(offsets),
            "width_scope": "Method-guided from separate Fig.1C/G averaging procedure, not a deposited S3 ROI.",
            "angles_deg": {"candidate_left": -15, "current": 0, "control_right": 15},
            "angle_convention": "0=image-up, positive rotates toward native image-right",
            "interpolation": "bilinear native source pixels",
            "geometry_filter": None,
            "signal_filter": None,
            "temporal_filter": False,
            "support_mask_array": "image_validity_mask in NPZ; exact native-source boolean FOV/annotation mask",
            "support_mask_policy": "x>=8,x<508,y>=4,y<508,excluding x<48 and y<48 (dye inset), and y>=450 with x<120 or x>395 (annotations).",
            "offsets_array": "width_offsets_px in NPZ; 52 equally spaced positions including ±25.2 px.",
            "full_width_rule": "All 52 samples inside FOV/annotation mask; apply saved radius cap separately. True zeros remain valid.",
        },
        "coverage": coverage,
        "normalization": {"shared_raw_limits": limits, "baseline_unmodified": True},
        "stats": stats,
        "recommendation": "defer_primary_replacement",
        "reason": "Sector and coverage controls expose sampling sensitivity; no unique wavefront center or full-interval anatomical AP was established. Keep current primary and use this detail comparison for review.",
        "limitations": limits_text,
        "baseline_hashes_before": before,
        "baseline_hashes_after": after,
        "frozen_s1_hashes_preserved": frozen,
        "script_sha256": sha(__file__),
    }
    write_json(data / "s3-review-provenance.json", provenance)
    write_json(
        data / "s3-source-evidence.json",
        {
            "article_url": ARTICLE,
            "primary_jats_sha256": sha(
                REPO_ROOT / "work/mammal-sources/PMC5847172.xml"
            ),
            "caption_scope": "Movie S3: LuVeLu ex vivo PSM on microfluidic chip, related Fig.3; CascadeBlue visualizes drug or control pulses.",
            "not_same_source": "Fig.2B unforced reference specimen",
            "condition_limit": "Caption does not identify which drug/control pulse experiment this export represents.",
            "method_scope": "Raw camera was 512×512 at 1.38 µm/px; source movie bar supplies approximate export scale. 70 µm is a method-guided comparison width, not deposited S3 line.",
            "gene_vs_dye": "LuVeLu reports Lfng regulatory dynamics; dye inset is not a gene channel and supplies no additional gene kymograph.",
        },
    )
    manifest = []
    for folder in [data, figs]:
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                manifest.append(
                    {
                        "path": str(p.relative_to(asset_root)),
                        "paper": "sonnen-2018",
                        "group": "core",
                        "url": "https://segmentation-clock-explorer.pages.dev/"
                        + str(p.relative_to(asset_root)),
                        "rights": "Source CC BY-NC-ND4.0; local independent display-video sampling sensitivity, not author ROI or raw data.",
                        "bytes": p.stat().st_size,
                        "sha256": sha(p),
                    }
                )
    write_json(output / "asset-registration.json", manifest)
    handoff = {
        "dataset_id": DATASET,
        "source_movie": "Movie S3",
        "status": "candidate_for_independent_review",
        "recommendation": provenance["recommendation"],
        "reason": provenance["reason"],
        "baseline_unchanged": before == after,
        "matrix": str(DATA_REL / numeric.name),
        "provenance": str(DATA_REL / "s3-review-provenance.json"),
        "video_overlay": str(DATA_REL / "s3-candidate-video-roi.json"),
        "roi_board": str(FIG_REL / "s3-roi-board.jpg"),
        "comparison": str(FIG_REL / "s3-current-vs-candidate.svg"),
        "matched_comparison": str(FIG_REL / "s3-matched-support-controls.svg"),
        "diagnostics": str(FIG_REL / "s3-geometry-diagnostics.png"),
        "all_frame_rois": str(FIG_REL / "s3-all-frame-rois.pdf"),
        "manifest": str((output / "asset-registration.json").relative_to(REPO_ROOT)),
        "stats": stats,
        "shared_limits": limits,
        "ui": {
            "label": "S3 · sector and coverage sensitivity",
            "note": "Current image-up strip versus a 15° left control with separately reviewed conservative coverage. Same manual image origin and 70 µm width; raw display values share one color scale. This comparison changes both direction and outer coverage; matched-support controls isolate angle.",
            "roi_alt": "All 111 source-frame overlays: cyan=current, orange=left-sector control. O is a manual image origin; E is a retained sampling endpoint. Dye inset excluded; no fixed anatomical A/P or fitted center.",
            "limit": provenance["reason"],
            "polarity": None,
            "coordinate_note": "Distance increases outward from common manual image O; neither O nor E is a validated anatomical boundary or wavefront center.",
        },
        "open_concerns": limits_text,
    }
    write_json(output / "handoff.json", handoff)
    print(
        json.dumps(
            {
                "shape": list(left.shape),
                "baseline_unchanged": before == after,
                "frozen_s1_preserved": True,
                "stats": stats,
                "artifacts": len(manifest),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--asset-root", type=Path, default=ASSET_ROOT)
    p.add_argument(
        "--output", type=Path, default=REPO_ROOT / "outputs/sonnen-s3-candidate"
    )
    a = p.parse_args()
    run(a.asset_root, a.output)

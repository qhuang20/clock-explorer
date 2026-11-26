# SPDX-License-Identifier: MIT
"""Sonnen S1 fixed-reference rigid-alignment candidate, kept separate from primary.

A controlled comparison to the existing manually moving strip. This is a
registration sensitivity experiment, not anatomical landmark validation.
"""

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import av
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import map_coordinates

from paths import ASSET_ROOT, REPO_ROOT
from export_video_rois import bands_from_path
from extract_sonnen_additional import SETTINGS, image_validity

DATASET = "sonnen-2018-embryo"
VIDEO = "movie-s1"
SOURCE_URL = "https://pmc-oa-opendata.s3.amazonaws.com/PMC5847172.1/mmc2.mp4"
ARTICLE_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC5847172/"
DATA_REL = Path("data/derived/sonnen-2018/s1-candidate-review")
FIG_REL = Path("figures/sonnen-2018/s1-candidate-review")
RIGHTS = "Source CC BY-NC-ND 4.0; local independent display-video reconstruction, not raw data or a deposited author ROI."
# Held out from registration: approximate visible posterior silhouette extrema.
# These visual points are not molecular P landmarks or material-cell tracks.
POSTERIOR_OUTLINE_CHECKS = np.array(
    [
        [0, 455, 744],
        [7, 438, 731],
        [31, 432, 750],
        [44, 452, 758],
        [63, 485, 809],
        [87, 548, 969],
    ],
    dtype=float,
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def finite_list(a):
    return np.where(np.isfinite(a), a, None).tolist()


def rigid_initial(origin0, direction0, origin, direction):
    theta = np.arctan2(direction[1], direction[0]) - np.arctan2(
        direction0[1], direction0[0]
    )
    rot = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    return np.c_[rot, origin - rot @ origin0].astype(np.float32)


def fit_rigid(frames, origins, directions, sigma_px, upper_only=False):
    """ECC estimates rotation+translation only. Blurred images are geometry inputs.

    The existing manual path supplies an initialization, not a fit target.
    A separate upper-PSM support window tests sensitivity to changing anatomy.
    No failed fit is silently interpolated or substituted.
    """
    template = (
        cv2.GaussianBlur(frames[0, :, :, 1], (0, 0), sigma_px).astype(np.float32) / 255
    )
    base = image_validity("s1", frames.shape[1:3])
    yy, xx = np.indices(base.shape)
    matrices = np.full((len(frames), 3, 3), np.nan)
    correlations = np.full(len(frames), np.nan)
    accepted = np.zeros(len(frames), bool)
    for i, frame in enumerate(frames):
        moving = (
            cv2.GaussianBlur(frame[:, :, 1], (0, 0), sigma_px).astype(np.float32) / 255
        )
        mask = base.copy()
        if upper_only:
            mask &= (yy < origins[i, 1] - 120) & (xx < origins[i, 0] + 180)
        initial = rigid_initial(origins[0], directions[0], origins[i], directions[i])
        try:
            cc, fitted = cv2.findTransformECC(
                template,
                moving,
                initial,
                cv2.MOTION_EUCLIDEAN,
                (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-5),
                mask.astype(np.uint8) * 255,
                7,
            )
        except cv2.error:
            continue
        # This is a numerical fit guard, not an anatomical confidence threshold.
        if not np.isfinite(fitted).all() or cc < 0.6:
            continue
        matrices[i] = np.vstack([fitted, [0, 0, 1]])
        correlations[i] = cc
        accepted[i] = True
    return matrices, correlations, accepted


def mapped_paths(reference_path, reference_normal, matrices):
    paths = (
        np.einsum("fij,sj->fsi", matrices[:, :2, :2], reference_path)
        + matrices[:, None, :2, 2]
    )
    normals = np.einsum("fij,j->fi", matrices[:, :2, :2], reference_normal)
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    return paths, normals


def sample_native(image, path, normal, offsets_px, support):
    """Mean original green display values; retain only full supported widths."""
    xy = path[:, None, :] + offsets_px[None, :, None] * normal
    values = map_coordinates(
        image.astype(float),
        [xy[..., 1], xy[..., 0]],
        order=1,
        mode="constant",
        cval=np.nan,
    )
    valid = (
        map_coordinates(
            support.astype(float),
            [xy[..., 1], xy[..., 0]],
            order=1,
            mode="constant",
            cval=0,
        )
        >= 1 - 1e-8
    )
    counts = (valid & np.isfinite(values)).sum(axis=1)
    result = np.full(len(path), np.nan)
    full = counts == len(offsets_px)
    result[full] = values[full].mean(axis=1)
    return result, counts


def font_path(preferred=Path("/System/Library/Fonts/Supplemental/Arial.ttf")):
    """Preserve the reviewed font locally; use a bundled portable fallback."""
    if preferred.is_file():
        return preferred
    import matplotlib

    return Path(matplotlib.get_data_path()) / "fonts/ttf/DejaVuSans.ttf"


def font(size):
    return ImageFont.truetype(str(font_path()), size)


def overlay(frame, current, candidate, normal, width, frame_index, time, size=420):
    im = Image.fromarray(frame).convert("RGB")
    d = ImageDraw.Draw(im)
    # Current manual corridor: muted dashed centerline, plus low-weight band.
    old_n = np.array([-(current[-1] - current[0])[1], (current[-1] - current[0])[0]])
    old_n /= np.linalg.norm(old_n)
    old_band = np.r_[current - width / 2 * old_n, (current + width / 2 * old_n)[::-1]]
    d.line([tuple(p) for p in np.r_[old_band, old_band[:1]]], fill="#a8d4e8", width=2)
    for j in range(0, len(current) - 1, 12):
        d.line([tuple(p) for p in current[j : j + 7]], fill="#a8d4e8", width=3)
    if np.isfinite(candidate).all():
        band = np.r_[
            candidate - width / 2 * normal, (candidate + width / 2 * normal)[::-1]
        ]
        d.line([tuple(p) for p in np.r_[band, band[:1]]], fill="#ffb44a", width=4)
        d.line([tuple(p) for p in candidate], fill="#ffb44a", width=3)
        for label, point in [("P", candidate[0]), ("A", candidate[-1])]:
            x, y = point
            d.rectangle([x + 8, y - 20, x + 47, y + 24], fill="black")
            d.text((x + 12, y - 20), label, fill="#ffb44a", font=font(38))
    else:
        d.text((30, 80), "Candidate fit unavailable", fill="#ffb44a", font=font(30))
    im.thumbnail((size, size))
    out = Image.new("RGB", (size, size + 40), "white")
    out.paste(im, (0, 40))
    ImageDraw.Draw(out).text(
        (8, 8), f"Frame {frame_index} · {time:.2f} h", fill="#242833", font=font(19)
    )
    return out


def render(
    frames,
    paths,
    normals,
    baseline_paths,
    old,
    new,
    times,
    positions,
    width,
    matrices,
    controls,
    cc,
    figures,
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
    lo = float(min(np.nanmin(old), np.nanmin(new)))
    hi = float(max(np.nanmax(old), np.nanmax(new)))
    xe = np.r_[
        times[0] - np.diff(times)[0] / 2,
        (times[:-1] + times[1:]) / 2,
        times[-1] + np.diff(times)[-1] / 2,
    ]
    ye = np.r_[
        positions[0] - 0.5, (positions[:-1] + positions[1:]) / 2, positions[-1] + 0.5
    ]
    cmap = plt.get_cmap("OrRd").copy()
    cmap.set_bad("#edf0f4")

    def heat(ax, values, title):
        m = ax.pcolormesh(
            xe,
            ye,
            np.ma.masked_invalid(values),
            cmap=cmap,
            norm=Normalize(lo, hi),
            rasterized=True,
            shading="flat",
        )
        ax.set(
            xlim=(times[0], times[-1]),
            ylim=(0, positions[-1]),
            xlabel="Time (h)",
            ylabel="Distance from sampling reference (approx. µm)",
            title=title,
        )
        ax.text(
            -0.16,
            1,
            "A",
            transform=ax.transAxes,
            color="#6255d6",
            va="top",
            fontweight="bold",
        )
        ax.text(
            -0.16,
            0,
            "P",
            transform=ax.transAxes,
            color="#6255d6",
            va="bottom",
            fontweight="bold",
        )
        return m

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 6.2), sharey=True)
    heat(axes[0], old, "Current · manually moving reference")
    m = heat(axes[1], new, "Candidate · fixed reference, rigid alignment")
    axes[1].set_ylabel("")
    fig.subplots_adjust(left=0.085, right=0.88, bottom=0.27, top=0.83, wspace=0.25)
    cb = fig.add_axes([0.91, 0.27, 0.014, 0.56])
    fig.colorbar(m, cax=cb, label="Shared raw display intensity (0–255)")
    fig.suptitle(
        "Sonnen 2018 · Movie S1 · source-display comparison",
        x=0.085,
        y=0.96,
        ha="left",
        fontweight="bold",
        fontsize=15,
    )
    fig.text(
        0.085,
        0.905,
        "88 frames · 0–14.50 h · same 70 µm width · original display values, no temporal filtering",
        fontsize=10,
    )
    fig.text(
        0.085,
        0.15,
        "Coordinates differ: current zero follows manually reviewed P-side points; candidate zero follows a frame-0 rigid reference.",
        fontsize=9,
    )
    fig.text(
        0.085,
        0.105,
        "Neither origin is a deposited author landmark. Global fit does not establish tailbud registration; gray = no full-width support.",
        fontsize=9,
    )
    fig.text(
        0.085,
        0.06,
        "70 µm is a method-guided width from the separate Fig. 1C double-reporter experiment; S1 is the Fig. 1A specimen.",
        fontsize=8.5,
    )
    for ext in ["svg", "png", "pdf"]:
        fig.savefig(figures / f"s1-current-vs-candidate.{ext}", dpi=200)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    m = heat(ax, new, "S1 · rigid-reference candidate")
    fig.colorbar(m, ax=ax, label="Raw display intensity (0–255)", pad=0.045)
    fig.tight_layout()
    for ext in ["svg", "png", "pdf"]:
        fig.savefig(figures / f"s1-candidate.{ext}", dpi=200)
    plt.close(fig)

    delta = np.linalg.norm(paths[:, 0] - baseline_paths[:, 0], axis=1)
    difficult = int(np.nanargmax(delta))
    selection = list(dict.fromkeys([0, 7, 31, 44, difficult, 87]))
    boards = []
    for i in selection:
        boards.append(
            overlay(
                frames[i], baseline_paths[i], paths[i], normals[i], width, i, times[i]
            )
        )
    board = Image.new("RGB", (3 * 420, 2 * 460 + 120), "white")
    d = ImageDraw.Draw(board)
    d.text(
        (15, 12),
        "S1 ROI review · cyan: current · orange: rigid candidate",
        fill="#242833",
        font=font(26),
    )
    d.text(
        (15, 50),
        "P/A mark regional direction; global alignment does not identify fixed cells or exact anatomical endpoints.",
        fill="#606977",
        font=font(18),
    )
    for j, im in enumerate(boards):
        board.paste(im, ((j % 3) * 420, 100 + (j // 3) * 460))
    board.save(figures / "s1-roi-board.jpg", quality=94)
    # Every source frame is included in a readable, paginated contact review.
    sheets = []
    for start in range(0, len(frames), 16):
        sheet = Image.new("RGB", (1280, 1440), "white")
        for j, i in enumerate(range(start, min(start + 16, len(frames)))):
            im = overlay(
                frames[i],
                baseline_paths[i],
                paths[i],
                normals[i],
                width,
                i,
                times[i],
                size=320,
            )
            sheet.paste(im, ((j % 4) * 320, (j // 4) * 360))
        sheet.save(
            figures
            / f"s1-roi-frames-{start:03d}-{min(start + 15, len(frames) - 1):03d}.jpg",
            quality=91,
        )
        sheets.append(sheet)
    with PdfPages(figures / "s1-all-frame-rois.pdf") as pdf:
        for sheet in sheets:
            fig, ax = plt.subplots(figsize=(12.8, 14.4))
            ax.imshow(sheet)
            ax.axis("off")
            fig.subplots_adjust(0, 0, 1, 1)
            pdf.savefig(fig, dpi=140)
            plt.close(fig)
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    axes[0].plot(
        times, delta, label="candidate vs current P-side reference", color="#6255d6"
    )
    axes[0].set_ylabel("Origin difference (px)")
    axes[0].legend(fontsize=9)
    for label, control in controls.items():
        control_paths, _ = mapped_paths(baseline_paths[0], normals[0], control)
        dist = np.linalg.norm(control_paths[:, 0] - paths[:, 0], axis=1)
        axes[1].plot(times, dist, label=label)
    axes[1].set_ylabel("Fit sensitivity at zero (px)")
    axes[1].legend(fontsize=9)
    axes[2].plot(times, cc, color="#6255d6")
    axes[2].set(
        ylabel="ECC correlation", xlabel="Experiment time (h)", ylim=(0.5, 1.01)
    )
    fig.suptitle(
        "Registration diagnostics · fit consistency is not anatomical accuracy"
    )
    fig.tight_layout()
    fig.savefig(figures / "s1-registration-diagnostics.png", dpi=180)
    plt.close(fig)
    return [lo, hi], difficult


def posterior_outline_check(frames, old_paths, paths, times, figures):
    """Visual holdout check independent of the image optimizer, not ground truth."""
    import matplotlib.pyplot as plt

    rows = []
    fig, axes = plt.subplots(2, 3, figsize=(11.7, 9.4))
    for ax, (frame, x, y) in zip(axes.ravel(), POSTERIOR_OUTLINE_CHECKS):
        i = int(frame)
        point = np.array([x, y])
        rows.append(
            {
                "frame": i,
                "time_h": float(times[i]),
                "posterior_outline_xy": point.tolist(),
                "current_reference_distance_px": float(
                    np.linalg.norm(point - old_paths[i, 0])
                ),
                "candidate_reference_distance_px": float(
                    np.linalg.norm(point - paths[i, 0])
                ),
            }
        )
        ax.imshow(frames[i])
        ax.plot(x, y, "+", color="white", ms=13, mew=2, label="outline check")
        ax.plot(*old_paths[i, 0], "o", color="#a8d4e8", ms=6, label="current zero")
        ax.plot(*paths[i, 0], "s", color="#ffb44a", ms=6, label="candidate zero")
        ax.set(xlim=(250, 750), ylim=(982, 500), title=f"Frame {i} · {times[i]:.2f} h")
        ax.set_xlabel("Native x (px)")
        ax.set_ylabel("Native y (px)")
    axes[0, 0].legend(fontsize=7, loc="upper right")
    fig.suptitle(
        "Held-out posterior silhouette checks · visual estimates, not anatomical ground truth",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.96))
    fig.text(
        0.04,
        0.025,
        "About ±10 px visual inspection tolerance; these points do not enter the fit. Distances alone do not establish registration accuracy.",
        fontsize=8,
    )
    fig.savefig(figures / "s1-posterior-outline-check.png", dpi=170)
    plt.close(fig)
    return {
        "points": rows,
        "visual_tolerance_px": 10,
        "tolerance_meaning": "Approximate visual inspection tolerance, not a statistical confidence interval.",
        "used_in_fit": False,
        "interpretation": "Both origins remain interior and their distance to a visible posterior contour varies. This checks plausibility only; a global fit does not track an exact posterior landmark.",
    }


def run(
    asset_root=ASSET_ROOT,
    output=REPO_ROOT / "outputs/sonnen-s1-candidate",
    reuse_geometry=False,
):
    output.mkdir(parents=True, exist_ok=True)
    source = asset_root / "videos/sonnen-2018/movie-s1.mp4"
    assert sha(source) == SETTINGS["s1"]["sha256"], (
        "S1 source differs from reviewed export"
    )
    protected = [
        p
        for folder in [
            asset_root / "data/derived/sonnen-2018/movie-s1",
            asset_root / "figures/sonnen-2018/movie-s1",
        ]
        for p in folder.rglob("*")
        if p.is_file()
    ]
    before = {str(p.relative_to(REPO_ROOT)): sha(p) for p in protected}
    cache = output / "frames.npy"
    starts = []
    with av.open(str(source)) as c:
        frames = []
        for f in c.decode(video=0):
            frames.append(f.to_ndarray(format="rgb24"))
            starts.append(float(f.pts * f.time_base))
    frames = np.asarray(frames)
    if not cache.is_file():
        np.save(cache, frames)
    assert frames.shape == (88, 982, 988, 3)
    baseline_path = asset_root / "data/derived/sonnen-2018/movie-s1/kymograph.npz"
    with np.load(baseline_path) as z:
        old = z["intensity"].copy()
        times = z["time_h"].copy()
        positions = z["position_um"].copy()
        old_paths = z["path_xy"].copy()
        old_origins = z["origins_xy"].copy()
        old_directions = z["directions_xy"].copy()
        scale = float(z["um_per_px"])
        width = float(z["strip_width_px"])
    mask = image_validity("s1", frames.shape[1:3])
    cached = None
    preservation = {"mode": "recomputed from source"}
    if reuse_geometry:
        candidate_file = asset_root / DATA_REL / "s1-rigid-candidate.npz"
        previous_file = asset_root / DATA_REL / "s1-review-provenance.json"
        previous = json.loads(previous_file.read_text())
        assert previous["source_sha256"] == sha(source), "Cached source changed"
        assert previous["baseline_sha256"] == sha(baseline_path), (
            "Cached baseline changed"
        )
        assert previous["candidate_sha256"] == sha(candidate_file), (
            "Cached candidate changed"
        )
        with np.load(candidate_file) as z:
            cached = {key: z[key].copy() for key in z.files}
        for key, expected in [
            ("baseline_intensity", old),
            ("time_h", times),
            ("position_um", positions),
            ("image_validity_mask", mask),
        ]:
            np.testing.assert_array_equal(cached[key], expected)
        assert float(cached["um_per_px"]) == scale
        assert float(cached["strip_width_px"]) == width
        matrices, cc, accepted = (
            cached[key]
            for key in ["reference_to_source", "ecc_correlation", "fit_accepted"]
        )
        paths, normals = cached["path_xy"], cached["normals_xy"]
        controls = {
            "Gaussian 6 px": cached["control_sigma6_to_source"],
            "Upper-PSM window": cached["control_upper_to_source"],
        }
        preservation = {
            "mode": "reuse verified source-bound candidate arrays for rendering-only revision",
            "prior_numeric_sha256": sha(candidate_file),
            "prior_provenance_sha256": sha(previous_file),
            "array_keys": sorted(cached),
            "arrays_exactly_unchanged": True,
        }
    else:
        matrices, cc, accepted = fit_rigid(frames, old_origins, old_directions, 12)
        paths, normals = mapped_paths(
            old_paths[0],
            np.array([-old_directions[0, 1], old_directions[0, 0]]),
            matrices,
        )
        controls = {}
        for label, sigma, upper in [
            ("Gaussian 6 px", 6, False),
            ("Upper-PSM window", 12, True),
        ]:
            m, _, _ = fit_rigid(frames, old_origins, old_directions, sigma, upper)
            controls[label] = m
    offsets = np.linspace(-width / 2, width / 2, int(np.ceil(width)) + 1)
    raw = np.full(old.shape, np.nan)
    counts = np.zeros(old.shape, np.int16)
    if cached is not None:
        raw, counts = cached["intensity"], cached["fov_width_counts"]
        np.testing.assert_array_equal(offsets, cached["width_offsets_px"])
    else:
        for i, f in enumerate(frames):
            if accepted[i]:
                raw[:, i], counts[:, i] = sample_native(
                    f[:, :, 1], paths[i], normals[i], offsets, mask
                )
    data = asset_root / DATA_REL
    figures = asset_root / FIG_REL
    data.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    numeric = data / "s1-rigid-candidate.npz"
    np.savez_compressed(
        numeric,
        intensity=raw,
        baseline_intensity=old,
        time_h=times,
        position_um=positions,
        frame_index=np.arange(88),
        path_xy=paths,
        normals_xy=normals,
        reference_path_xy=old_paths[0],
        reference_to_source=matrices,
        ecc_correlation=cc,
        fit_accepted=accepted,
        valid=np.isfinite(raw),
        fov_width_counts=counts,
        width_offsets_px=offsets,
        strip_width_px=width,
        um_per_px=scale,
        image_validity_mask=mask,
        control_sigma6_to_source=controls["Gaussian 6 px"],
        control_upper_to_source=controls["Upper-PSM window"],
    )
    if cached is not None:
        with np.load(numeric) as z:
            assert set(z.files) == set(cached)
            for key, expected in cached.items():
                np.testing.assert_array_equal(z[key], expected)
    roi_frames = []
    for i in range(88):
        bands, lines = bands_from_path(
            paths[i],
            np.tile(normals[i], (len(positions), 1)),
            np.isfinite(raw[:, i]),
            width,
        )
        row = dict(index=i, experiment_h=float(times[i]), bands=bands, lines=lines)
        if accepted[i]:
            row["reference_points"] = np.round(paths[i, [0, -1]], 2).tolist()
        roi_frames.append(row)
    roi = dict(
        schema_version=1,
        dataset_id=DATASET,
        video_id=VIDEO,
        source_sha256=sha(source),
        playback_sha256=sha(source),
        width=988,
        height=982,
        frame_starts_s=np.round(np.array(starts) - starts[0], 9).tolist(),
        frames=roi_frames,
        direction_labels=["P", "A"],
        geometry_input=str(DATA_REL / numeric.name),
        geometry_input_sha256=sha(numeric),
        scope="Candidate only: fixed frame-0 reference mapped by global rigid registration; not validated anatomical landmarks.",
    )
    dump(data / "s1-candidate-video-roi.json", roi)
    limits, difficult = render(
        frames,
        paths,
        normals,
        old_paths,
        old,
        raw,
        times,
        positions,
        width,
        matrices,
        controls,
        cc,
        figures,
    )
    control_deltas = {}
    for label, m in controls.items():
        pp, _ = mapped_paths(
            old_paths[0], np.array([-old_directions[0, 1], old_directions[0, 0]]), m
        )
        delta = np.linalg.norm(pp[:, 0] - paths[:, 0], axis=1)
        control_deltas[label] = {
            "max_px": float(np.nanmax(delta)),
            "median_px": float(np.nanmedian(delta)),
            "finite_frames": int(np.isfinite(delta).sum()),
            "interpretation": "Underconstrained/unstable alternative; rejected as independent confirmation, not an accuracy error bar."
            if label == "Upper-PSM window"
            else "Geometry-blur sensitivity, not anatomical accuracy.",
        }
    outline = posterior_outline_check(frames, old_paths, paths, times, figures)
    dump(data / "s1-posterior-outline-check.json", outline)
    delta = np.linalg.norm(paths[:, 0] - old_paths[:, 0], axis=1)
    after = {name: sha(REPO_ROOT / name) for name in before}
    assert before == after, "Baseline changed"
    provenance = {
        "dataset": DATASET,
        "source_movie": "Movie S1",
        "source_url": SOURCE_URL,
        "source_sha256": sha(source),
        "source_shape": list(frames.shape),
        "article_url": ARTICLE_URL,
        "baseline_path": str(baseline_path.relative_to(asset_root)),
        "baseline_sha256": sha(baseline_path),
        "candidate_sha256": sha(numeric),
        "numeric_preservation": preservation,
        "font": {
            "preferred": "Arial when locally available",
            "fallback": "Matplotlib bundled DejaVuSans.ttf",
            "rendered_path": str(font_path()),
        },
        "shape_space_time": list(raw.shape),
        "time_range_h": [float(times[0]), float(times[-1])],
        "time_basis": "Copied exact baseline transcriptions of all 88 source burned-in times, including late 0.01 h offsets. Playback seconds are a separate clock.",
        "scale": {
            "bar_um": 100,
            "bar_px": 164,
            "um_per_px": scale,
            "approximate": True,
            "assumption": "Equal x/y export scaling; raw-camera 1.38 µm/px not substituted.",
        },
        "channel": "Decoded green channel of grayscale rendered Axin2T2A fluorescence; no raw detector/z-stack claim.",
        "sampling": {
            "width_um": 70,
            "width_px": width,
            "offset_count": len(offsets),
            "width_scope": "Method-guided borrowing from separate Fig. 1C double-reporter procedure; not a deposited S1 ROI.",
            "interpolation": "bilinear native-source pixels",
            "support": "Full width inside FOV and outside annotation mask; no anatomical tissue mask.",
            "support_mask_array": "image_validity_mask in candidate NPZ; exact source-pixel boolean mask.",
            "support_mask_policy": "x>=8, x<984, y>=4, y<978, excluding (y>=895 and x<400) or (y>=875 and x>770).",
            "offsets_array": "width_offsets_px in candidate NPZ; 116 equally spaced offsets including ±width_px/2.",
            "primary_image_sigma_px": 0,
            "temporal_filter": False,
        },
        "registration": {
            "reference_frame": 0,
            "model": "Euclidean rotation and translation only; no scale or deformation",
            "geometry_image_gaussian_sigma_px": 12,
            "initialization": "Existing manual P-side origin and P-to-A direction; then image ECC refinement",
            "mask": "FOV/annotation support mask; alternate fit uses only upper-PSM window",
            "numerical_fit_guard": "finite matrix and ECC >=0.6; no interpolation of rejected fits",
            "optimizer": {
                "motion": "cv2.MOTION_EUCLIDEAN",
                "max_iterations": 100,
                "epsilon": 1e-5,
                "gauss_filter_size": 7,
                "image_divisor": 255,
            },
            "upper_window_policy": "base FOV/annotation mask AND y < current manual origin_y - 120 AND x < current manual origin_x + 180; control only.",
            "accepted_frames": int(accepted.sum()),
            "ecc_range": [float(np.nanmin(cc)), float(np.nanmax(cc))],
            "sensitivity": control_deltas,
            "posterior_outline_holdout": outline,
            "current_origin_difference_px": {
                "median": float(np.nanmedian(delta)),
                "max": float(np.nanmax(delta)),
                "worst_frame": difficult,
            },
        },
        "normalization": {
            "comparison_shared_raw_limits": limits,
            "baseline_primary_values_unchanged": True,
        },
        "recommendation": "defer_primary_replacement",
        "reason": "Global rigid alignment is a controlled alternative, but sensitivity to structural support and tissue deformation does not establish exact posterior registration. Retain current primary and show candidate comparison for review.",
        "limitations": [
            "Both origins are regional image references, not exact P/A boundaries or tracked cells.",
            "Blur is used only for geometry fitting; signal values are sampled from original frames without temporal smoothing.",
            "A high ECC value measures image similarity and does not independently validate tailbud registration.",
            "Support rejects annotations/FOV edges but does not segment PSM; inspect every ROI before anatomical interpretation.",
            "S1 is the Fig.1A single-reporter specimen, distinct from Fig.1C double-reporter acquisition.",
        ],
        "baseline_hashes_before": before,
        "baseline_hashes_after": after,
        "script_sha256": sha(__file__),
    }
    dump(data / "s1-review-provenance.json", provenance)
    trajectory = []
    for i in range(88):
        trajectory.append(
            {
                "frame": i,
                "time_h": float(times[i]),
                "current_origin_xy": old_paths[i, 0].tolist(),
                "candidate_origin_xy": finite_list(paths[i, 0]),
                "candidate_end_xy": finite_list(paths[i, -1]),
                "matrix": finite_list(matrices[i]),
                "ecc": float(cc[i]) if np.isfinite(cc[i]) else None,
                "origin_delta_px": float(delta[i]) if np.isfinite(delta[i]) else None,
                "accepted": bool(accepted[i]),
            }
        )
    dump(data / "s1-reference-trajectory.json", trajectory)
    article = REPO_ROOT / "work/mammal-sources/PMC5847172.xml"
    if article.is_file():
        ET.parse(
            article
        )  # Evidence is retained as metadata, not republished article prose.
        dump(
            data / "s1-source-evidence.json",
            {
                "article_url": ARTICLE_URL,
                "local_primary_jats_sha256": sha(article),
                "source_movie_url": SOURCE_URL,
                "same_specimen": {
                    "figure": "1A/B",
                    "movie": "S1",
                    "target_gene": "Axin2",
                    "reporter": "Axin2T2A",
                    "stage": "E10.5",
                    "view": "Dorsal",
                },
                "separate_experiment": "Fig.1C Axin2T2A/Mesp2-GFP double-reporter recording",
                "width_basis": "Fig.1C caption states 70 µm averaging width; local S1 width is an explicitly method-guided choice.",
                "camera_vs_export": "Methods describe 512×512 raw imaging at 1.38 µm/px; this exported movie is 988×982 and uses its own measured scale bar.",
            },
        )
    manifest = []
    for folder in [data, figures]:
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                manifest.append(
                    {
                        "path": str(p.relative_to(asset_root)),
                        "paper": "sonnen-2018",
                        "group": "core",
                        "url": "https://segmentation-clock-explorer.pages.dev/"
                        + str(p.relative_to(asset_root)),
                        "rights": RIGHTS,
                        "bytes": p.stat().st_size,
                        "sha256": sha(p),
                    }
                )
    dump(output / "asset-registration.json", manifest)
    handoff = {
        "dataset_id": DATASET,
        "source_movie": "Movie S1",
        "status": "candidate_for_independent_review",
        "recommendation": provenance["recommendation"],
        "reason": provenance["reason"],
        "baseline_unchanged": before == after,
        "matrix": str(DATA_REL / numeric.name),
        "provenance": str(DATA_REL / "s1-review-provenance.json"),
        "video_overlay": str(DATA_REL / "s1-candidate-video-roi.json"),
        "roi_board": str(FIG_REL / "s1-roi-board.jpg"),
        "comparison": str(FIG_REL / "s1-current-vs-candidate.svg"),
        "diagnostics": str(FIG_REL / "s1-registration-diagnostics.png"),
        "all_frame_rois": str(FIG_REL / "s1-all-frame-rois.pdf"),
        "manifest": str((output / "asset-registration.json").relative_to(REPO_ROOT)),
        "shared_limits": limits,
        "registration_sensitivity": control_deltas,
        "ui": {
            "label": "S1 · fixed-reference alignment candidate",
            "note": "Current manually moving ROI versus a fixed frame-0 strip mapped by rigid alignment. Original display intensities share one color scale; 70 µm is a method-guided width from the separate Fig.1C experiment.",
            "roi_alt": "All 88 S1 frames reviewed. Cyan marks the current manual strip; orange the rigid-reference candidate. P/A are regional directions, not exact anatomical boundaries.",
            "limit": provenance["reason"],
            "polarity": {
                "top": "A",
                "bottom": "P",
                "flip_y": False,
                "scope": "regional_direction",
            },
        },
        "open_concerns": provenance["limitations"],
    }
    dump(output / "handoff.json", handoff)
    print(
        json.dumps(
            {
                "shape": list(raw.shape),
                "baseline_unchanged": before == after,
                "accepted": int(accepted.sum()),
                "missing": int(np.isnan(raw).sum()),
                "sensitivity": control_deltas,
                "recommendation": handoff["recommendation"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--asset-root", type=Path, default=ASSET_ROOT)
    p.add_argument(
        "--output", type=Path, default=REPO_ROOT / "outputs/sonnen-s1-candidate"
    )
    p.add_argument(
        "--reuse-geometry",
        action="store_true",
        help="Reuse a hash-verified existing candidate for rendering-only revisions.",
    )
    a = p.parse_args()
    run(a.asset_root, a.output, a.reuse_geometry)

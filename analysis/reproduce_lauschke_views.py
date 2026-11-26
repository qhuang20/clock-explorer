# SPDX-License-Identifier: MIT
"""Independent display-video reconstruction of Lauschke Fig. 1 sampling geometries.

Video 1: posterior embryo fragment, side view, manually registered AP strip.
Video 2 (+ matching BF Video 3): spreading mPSM, wavefront-fitted radial strip.
These are not recovered raw photon counts or the authors' exact saved ROIs.
"""

from pathlib import Path
import argparse
import hashlib
import json
import re

import numpy as np
from scipy import ndimage as ndi

from paths import ASSET_ROOT
from extract_video_kymographs import decode, feature, displacement
from extract_lauschke_radial import largest_filled
from lauschke_wavefront_center import estimate_center

SOURCE_HASHES = {
    1: "ead90ea0a22ae683f8bcfc3b804cbc37144274b8635e2206a0a6d985f9b94b04",
    2: "dd20eea69e9b443d0b6b3f84977b4454e3691237db7ddcd52f7e1f1f60b451dd",
    3: "14290aeaaca1dfaeca24a795e019b3e9a0f5fc30da9c86fa19a63f6458b0f294",
}
# Reviewed posterior-side and anterior-side points in ORIGINAL decoded pixels.
AP_KEYS = np.array(
    [
        [0, 405, 350, 170, 140],
        [20, 365, 385, 150, 230],
        [40, 375, 415, 155, 280],
        [60, 420, 460, 190, 325],
    ],
    dtype=float,
)
WIDTH_PX = 20
SIGMA_UM = 7 * 1.38  # Published sigma on raw images; convert to display pixels.


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_times(path, count):
    audit = json.loads(Path(path).read_text())
    rows = sorted(audit["ocr"], key=lambda r: r["frame"])
    assert [r["frame"] for r in rows] == list(range(count))
    overrides = {int(k): v for k, v in audit.get("manual_corrections_h", {}).items()}
    values = []
    for row in rows:
        match = re.search(r"(\d{1,2}\.\d{2})", row["text"])
        if not match:
            raise ValueError(f"Unreadable timestamp: {row}")
        values.append(overrides.get(row["frame"], float(match[1])))
    values = np.array(values)
    assert np.isfinite(values).all() and (np.diff(values) > 0).all()
    return values


def ap_geometry(count):
    assert count == 61  # The paper's 0–10 h comparison; later bent tail unreviewed.
    x = np.arange(count)
    points = np.array(
        [np.interp(x, AP_KEYS[:, 0], AP_KEYS[:, j]) for j in range(1, 5)]
    ).T
    origins = points[:, :2]
    directions = points[:, 2:] - origins
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    return origins, directions


def tissue_masks(references):
    masks = []
    for frame in references:
        g = frame[..., 0].astype(float)
        variance = ndi.uniform_filter(g * g, 15) - ndi.uniform_filter(g, 15) ** 2
        texture = ndi.gaussian_filter(np.sqrt(np.maximum(variance, 0)), 5)
        mask = texture > 12
        mask[:15] = False
        mask[680:] = False
        mask[:, :15] = False
        mask[:, 735:] = False
        masks.append(largest_filled(ndi.binary_closing(mask, iterations=4)))
    return np.array(masks)


def radial_geometry(frames, references, times):
    masks = tissue_masks(references)
    features = [feature(f) for f in references]
    increments = np.array(
        [[0.0, 0.0]] + [displacement(a, b) for a, b in zip(features[:-1], features[1:])]
    )
    assert np.max(np.abs(increments)) < 11
    shifts = increments.cumsum(axis=0)
    center, direction, audit, fronts = estimate_center(
        frames, masks, shifts, times, 100 / 111
    )
    origins = center + shifts
    directions = np.tile(direction, (len(references), 1))
    return origins, directions, masks, shifts, audit, fronts


def sample(
    frames, origins, directions, positions_um, um_per_px, masks=None, sigma_um=0
):
    columns = []
    for i, (frame, origin, direction) in enumerate(zip(frames, origins, directions)):
        normal = np.array([-direction[1], direction[0]])
        offsets = np.linspace(-WIDTH_PX / 2, WIDTH_PX / 2, WIDTH_PX + 1)
        xy = (
            origin
            + positions_um[:, None, None] / um_per_px * direction
            + offsets[None, :, None] * normal
        )
        coords = [xy[..., 1], xy[..., 0]]
        gray = frame[..., :3].astype(float).mean(axis=-1)
        if sigma_um:
            gray = ndi.gaussian_filter(gray, sigma_um / um_per_px)
        values = ndi.map_coordinates(
            gray, coords, order=1, mode="constant", cval=np.nan
        )
        valid = (
            np.isfinite(values)
            & (xy[..., 0] >= 15)
            & (xy[..., 1] >= 15)
            & (xy[..., 1] < frame.shape[0] - 60)
        )
        if masks is not None:
            valid &= (
                ndi.map_coordinates(
                    masks[i].astype(float), coords, order=0, mode="constant", cval=0
                )
                > 0.5
            )
        count = valid.sum(axis=1)
        inside = np.logical_and.accumulate(count >= np.ceil(0.75 * len(offsets)))
        profile = np.divide(
            np.where(valid, values, 0).sum(axis=1),
            count,
            out=np.full(len(count), np.nan),
            where=inside,
        )
        columns.append(profile)
    return np.stack(columns, axis=1)


def plot_record(
    number,
    frames,
    origins,
    directions,
    raw,
    smooth,
    positions,
    times,
    scale,
    masks,
    out,
):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )
    cmap = matplotlib.colormaps["OrRd"].copy()
    cmap.set_bad("#f1f3f6")
    lo, hi = np.nanmin(raw), np.nanmax(raw)
    from matplotlib.colors import Normalize

    norm = Normalize(lo, hi)

    def heat(ax, array, title):
        # Ascending space is the publication's orientation (P/center at bottom).
        xedges = np.r_[
            times[0] - (times[1] - times[0]) / 2,
            (times[1:] + times[:-1]) / 2,
            times[-1] + (times[-1] - times[-2]) / 2,
        ]
        yedges = np.r_[
            positions[0] - 0.5,
            (positions[1:] + positions[:-1]) / 2,
            positions[-1] + 0.5,
        ]
        mesh = ax.pcolormesh(
            xedges,
            yedges,
            np.ma.masked_invalid(array),
            cmap=cmap,
            norm=norm,
            shading="flat",
            rasterized=True,
        )
        ax.set_xlim(times[0], times[-1])
        ax.set_ylim(0, positions[-1])
        ax.set_xlabel("Time (h)")
        ax.set_ylabel(
            "Distance from posterior landmark (µm)"
            if number == 1
            else "Distance from fitted wavefront center (µm)"
        )
        ax.set_title(title, loc="left", fontsize=11)
        return mesh

    title = (
        "Embryonic PSM · side view"
        if number == 1
        else "Spreading mPSM · culture-plane view"
    )
    fig = plt.figure(figsize=(10.8, 7.6))
    grid = fig.add_gridspec(3, 2, width_ratios=[1, 1.25], hspace=0.18, wspace=0.25)
    ids = [0, len(frames) // 2, len(frames) - 1]
    for j, i in enumerate(ids):
        ax = fig.add_subplot(grid[j, 0])
        ax.imshow(frames[i])
        if masks is not None:
            ax.contour(masks[i], levels=[0.5], colors=["#74cce0"], linewidths=0.55)
        n = np.isfinite(raw[:, i]).sum()
        end = origins[i] + positions[max(n - 1, 0)] / scale * directions[i]
        ax.annotate(
            "",
            xy=end,
            xytext=origins[i],
            arrowprops={"arrowstyle": "->", "color": "#ffae43", "lw": 2},
        )
        ax.plot(*origins[i], "+", color="white", ms=8)
        ax.text(
            origins[i, 0] + 10,
            origins[i, 1] + 8,
            "P*" if number == 1 else "Wavefront fit*",
            color="white",
            bbox={"facecolor": "black", "alpha": 0.55, "pad": 1},
        )
        ax.text(
            end[0] + 8,
            end[1] + 4,
            "A" if number == 1 else "ROI end",
            color="#ffcf77",
            bbox={"facecolor": "black", "alpha": 0.55, "pad": 1},
        )
        ax.set_title(f"{times[i]:.2f} h", loc="left", fontsize=10)
        ax.axis("off")
    right = fig.add_subplot(grid[:, 1])
    mesh = heat(right, raw, "Unsmoothed display-video extraction")
    bar = fig.colorbar(mesh, ax=right, fraction=0.04, pad=0.04)
    bar.set_label("Video display value")
    bar.outline.set_visible(False)
    fig.suptitle(
        "Lauschke 2013 · " + title, x=0.04, ha="left", fontsize=15, weight="bold"
    )
    note = (
        "Video 1 · first 61/126 frames · reviewed AP landmarks; LuVeLu / brightfield composite"
        if number == 1
        else "Video 2 · all 160 frames · early-wavefront center fit + matching brightfield translation"
    )
    fig.text(0.04, 0.065, note, color="#677285", fontsize=9)
    fig.text(
        0.04,
        0.027,
        "*Center/landmark estimates are approximate. No cell tracking, raw photon recovery or exact author ROI is claimed.",
        color="#677285",
        fontsize=9,
    )
    fig.subplots_adjust(left=0.05, right=0.94, top=0.91, bottom=0.13)
    for ext in ["png", "svg", "pdf"]:
        fig.savefig(out / f"video{number}-sampling.{ext}", dpi=180)
    plt.close(fig)
    fig, axs = plt.subplots(1, 2, figsize=(10.8, 5.2))
    heat(axs[0], raw, "Unsmoothed extraction")
    mesh = heat(axs[1], smooth, f"Spatial Gaussian σ = {SIGMA_UM:.2f} µm")
    fig.colorbar(
        mesh,
        ax=axs.ravel().tolist(),
        fraction=0.025,
        pad=0.035,
        label="Video display value",
    )
    fig.suptitle(title + " · spatial-filter comparison", x=0.04, ha="left", fontsize=14)
    fig.text(
        0.04,
        0.045,
        "Same ROI, timestamps, mask and color limits. Only image-space filtering differs; no temporal blur or phase inference.",
        fontsize=9,
        color="#677285",
    )
    fig.subplots_adjust(left=0.08, right=0.88, bottom=0.18, top=0.86, wspace=0.32)
    # Reposition the shared bar after subplot adjustment to keep all labels inside.
    fig.axes[-1].set_position([0.905, 0.18, 0.018, 0.68])
    for ext in ["png", "svg", "pdf"]:
        fig.savefig(out / f"video{number}-spatial-filter.{ext}", dpi=180)
    plt.close(fig)


def render_center_audit(
    frames,
    origins,
    directions,
    shifts,
    raw,
    positions,
    times,
    scale,
    audit,
    fronts,
    out,
):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(11.4, 5.0))
    selected = [fronts[0], fronts[len(fronts) // 2], fronts[-1]]
    for ax, front in zip(axes, selected):
        i = front["frame"]
        ax.imshow(frames[i])
        points = np.asarray(front["points"]) + shifts[i]
        ax.plot(
            points[:, 0], points[:, 1], color="#74cce0", lw=1.4, label="Observed arc"
        )
        radius = np.median(np.linalg.norm(points - origins[i], axis=1))
        theta = np.linspace(-np.pi, np.pi, 250)
        ax.plot(
            origins[i, 0] + radius * np.cos(theta),
            origins[i, 1] + radius * np.sin(theta),
            "--",
            color="#ed82c8",
            lw=0.7,
        )
        ax.plot(*origins[i], "+", color="white", ms=12, mew=1.6)
        end = origins[i] + positions[np.isfinite(raw[:, i])][-1] / scale * directions[i]
        ax.annotate(
            "",
            xy=end,
            xytext=origins[i],
            arrowprops={"arrowstyle": "->", "color": "#ffae43", "lw": 2},
        )
        ax.text(
            origins[i, 0] + 12,
            origins[i, 1] - 10,
            "Fitted center*",
            color="white",
            fontsize=9,
            bbox={"facecolor": "black", "alpha": 0.6, "pad": 2},
        )
        ax.set_xlim(0, frames.shape[2])
        ax.set_ylim(680, 0)
        ax.axis("off")
        ax.set_title(f"{times[i]:.2f} h", loc="left", fontsize=11)
    fig.suptitle(
        "Video 2 · center estimated from continuous wavefronts",
        x=0.035,
        ha="left",
        fontsize=15,
        weight="bold",
    )
    fig.text(
        0.035,
        0.14,
        "Cyan: observed dynamic-wave arc   Dashed: fitted circle   +: shared curvature center   Orange: sampling radius",
        fontsize=9,
        color="#535d6b",
    )
    fig.text(
        0.035,
        0.085,
        f"{audit['accepted_distinct_frames']} frames ({audit['supported_time_h'][0]:.2f}–{audit['supported_time_h'][1]:.2f} h) · median arc residual {audit['median_joint_arc_residual_um']:.1f} µm · disjoint-time center difference {audit['disjoint_time_center_separation_um']:.1f} µm",
        fontsize=9,
        color="#535d6b",
    )
    fig.text(
        0.035,
        0.035,
        "*Early-wave geometric estimate, not a verified molecular source. Later sampling follows brightfield translation only.",
        fontsize=9,
        color="#535d6b",
    )
    fig.subplots_adjust(left=0.025, right=0.985, bottom=0.21, top=0.88, wspace=0.06)
    for fmt in ["png", "svg", "pdf"]:
        fig.savefig(out / ("video2-wavefront-center." + fmt), dpi=200)
    plt.close(fig)


def run(source_dir, time_dir, only=None):
    frames = {}
    for number in [1, 2, 3]:
        path = source_dir / f"41586_2013_BFnature11804_MOESM{291 + number}_ESM.mov"
        assert digest(path) == SOURCE_HASHES[number], (
            f"Source hash changed: Video {number}"
        )
        frames[number] = np.array(decode(path))
    out = ASSET_ROOT / "data/derived/lauschke-2013"
    figures = ASSET_ROOT / "figures/lauschke-2013"
    out.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    for number in [only] if only else [1, 2]:
        audit = None
        time_path = time_dir / f"video{number}-timestamps.json"
        times = read_times(time_path, len(frames[number]))
        if number == 1:
            f = frames[1][:61]
            times = times[:61]
            origins, directions = ap_geometry(len(f))
            masks = None
            shifts = None
            scale = 100 / 103
            positions = np.arange(451, dtype=float)
        else:
            f = frames[2]
            origins, directions, masks, shifts, audit, fronts = radial_geometry(
                f, frames[3], times
            )
            scale = 100 / 111
            positions = np.arange(401, dtype=float)
        raw = sample(f, origins, directions, positions, scale, masks)
        smooth = sample(f, origins, directions, positions, scale, masks, SIGMA_UM)
        assert np.isfinite(raw).any() and raw.shape == (len(positions), len(times))
        np.savez_compressed(
            out / f"video{number}-kymograph.npz",
            intensity=raw,
            spatial_smoothed_intensity=smooth,
            time_h=times,
            position_um=positions,
            origins_xy=origins,
            directions_xy=directions,
        )
        if masks is not None:
            np.savez_compressed(
                out / "video2-geometry.npz",
                masks=masks,
                origins_xy=origins,
                shifts_xy=shifts,
            )
        plot_record(
            number,
            f,
            origins,
            directions,
            raw,
            smooth,
            positions,
            times,
            scale,
            masks,
            figures,
        )
        trace = {
            "paper_id": "lauschke-2013",
            "video": number,
            "method_version": "wavefront-arcs-v1"
            if number == 2
            else "paper-geometries-v1",
            "source_sha256": SOURCE_HASHES[number],
            "source_filename": f"41586_2013_BFnature11804_MOESM{291 + number}_ESM.mov",
            "shape_space_time": list(raw.shape),
            "used_frames": len(times),
            "total_source_frames": len(frames[number]),
            "time_range_h": [float(times[0]), float(times[-1])],
            "time_basis": "each burned-in experimental timestamp; 0.01 h display precision; not playback rate or imposed nominal 10 min",
            "timestamps_audit": time_path.name,
            "um_per_video_pixel": scale,
            "scale_bar": {
                "length_um": 100,
                "x_endpoints": [23, 126] if number == 1 else [21, 132],
                "y": 691 if number == 1 else 700,
                "precision_px": 1,
            },
            "geometry": "reviewed posterior/anterior landmark pairs, interpolated for 0–10 h"
            if number == 1
            else "consensus circular-arc fits to continuous early wavefronts; no COM prior; matching Video 3 translation; reviewed upper-tissue radius approximately perpendicular under the circular-wavefront model",
            "ap_landmark_keyframes": AP_KEYS.tolist() if number == 1 else None,
            "spatial_reference": "posterior-side landmark → anterior PSM"
            if number == 1
            else "early-wavefront curvature-center estimate → outward; later anchor continued by brightfield translation",
            "width_video_px": WIDTH_PX,
            "raw": "decoded mean RGB display values, bilinear sampling across width, no added filtering",
            "spatial_filter_comparison": {
                "sigma_um": SIGMA_UM,
                "sigma_display_px": SIGMA_UM / scale,
                "order": "Gaussian filter each full grayscale video image, then same sampling path and mask",
                "temporal_filter": False,
                "same_color_limits_as_raw": True,
            },
            "mask": "FOV / text exclusion"
            if number == 1
            else "BF local SD15; Gaussian5 geometry only; threshold12, closing4, largest filled component; first <75% valid strip width ends radius",
            "source_terms": "Nature copyright; no open reuse license verified.",
            "evidence_url": "https://www.nature.com/articles/nature11804",
            "evidence_sections": [
                "Figure 1 caption",
                "Supplementary Videos 1–3",
                "Image processing",
            ],
            "limitations": [
                "Independent display-video reconstruction, not exact author ROI or raw photon counts.",
                "Video 1 merges reporter and brightfield; its grayscale values cannot isolate fluorescence."
                if number == 1
                else "Center fitted only in the coherent early-wave interval; later center is not independently validated and is continued by BF translation; no cell/deformation tracking.",
                "The original second kymograph Gaussian has no verified time-pixel scaling here and is not blindly applied; no detrending or Hilbert phase.",
                "The explant can extend beyond the field of view; the sampled endpoint is not necessarily the biological rim or the oscillation-arrest front.",
                "The comparison gallery retains its shared 0-at-top convention; sampling documentation uses the paper orientation with 0 at bottom.",
            ],
            "script": "analysis/reproduce_lauschke_views.py",
            "script_sha256": digest(__file__),
            "dependency_hashes": {
                name: digest(Path(__file__).with_name(name))
                for name in [
                    "extract_video_kymographs.py",
                    "extract_lauschke_radial.py",
                    "lauschke_wavefront_center.py",
                ]
            },
        }
        if audit is not None:
            trace["wavefront_center"] = audit
            trace["center_fit_audit"] = "video2-center-fit.json"
            trace["center_fit_fronts"] = "video2-center-fronts.json"
            trace["geometry_filter_used_for_final_intensity"] = False
            (out / "video2-center-fit.json").write_text(
                json.dumps(audit, indent=2) + "\n"
            )
            (out / "video2-center-fronts.json").write_text(json.dumps(fronts) + "\n")
            render_center_audit(
                f,
                origins,
                directions,
                shifts,
                raw,
                positions,
                times,
                scale,
                audit,
                fronts,
                figures,
            )
            sensitivity = {}
            for j, center in enumerate(audit["disjoint_time_centers_xy_px"]):
                sensitivity[f"time_half_{j + 1}"] = sample(
                    f, np.asarray(center) + shifts, directions, positions, scale, masks
                )
            for offset in [-10, 10]:
                theta = np.deg2rad(audit["ray"]["angle_deg"] + offset)
                sensitivity[f"angle_{offset:+d}"] = sample(
                    f,
                    origins,
                    np.tile([np.cos(theta), np.sin(theta)], (len(f), 1)),
                    positions,
                    scale,
                    masks,
                )
            np.savez_compressed(
                out / "video2-center-sensitivity.npz",
                **sensitivity,
                time_h=times,
                position_um=positions,
            )
        (out / f"video{number}-provenance.json").write_text(
            json.dumps(trace, indent=2) + "\n"
        )
        print(
            json.dumps(
                {
                    "video": number,
                    "shape": raw.shape,
                    "times": [times[0], times[-1]],
                    "masked": int(np.isnan(raw).sum()),
                    "origin_first": origins[0].tolist(),
                    "origin_last": origins[-1].tolist(),
                }
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--time-dir", type=Path, required=True)
    parser.add_argument("--only", type=int, choices=[1, 2])
    args = parser.parse_args()
    run(args.source_dir, args.time_dir, args.only)

# SPDX-License-Identifier: MIT
"""Render inspectable AP-direction evidence without changing radial measurements.

Direction is a reviewed regional interpretation, not an automated AP detector.
A saved publisher-to-movie feature registration is checked independently before
use; source identity and every frame/time coordinate remain explicit.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from paths import ASSET_ROOT
from extract_video_kymographs import decode


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def endpoint_table(matrix, times, positions, origins, directions, um_per_px):
    """Last measured position, not an anatomical tissue rim or anterior end."""
    if (
        matrix.shape != (len(positions), len(times))
        or origins.shape != directions.shape
        or origins.shape != (len(times), 2)
        or not np.isfinite(um_per_px)
        or um_per_px <= 0
    ):
        raise ValueError("Inconsistent sampling geometry")
    rows = []
    for i in range(len(times)):
        valid = np.flatnonzero(np.isfinite(matrix[:, i]))
        if not len(valid):
            rows.append(
                {
                    "frame": i,
                    "time_h": float(times[i]),
                    "last_valid_um": None,
                    "endpoint_xy": None,
                }
            )
            continue
        j = int(valid[-1])
        end = origins[i] + positions[j] / um_per_px * directions[i]
        rows.append(
            {
                "frame": i,
                "time_h": float(times[i]),
                "last_valid_um": float(positions[j]),
                "endpoint_xy": end.tolist(),
                "near_top_exclusion": bool(end[1] <= 20),
            }
        )
    return rows


def checked_mapping(record):
    """Check correspondences, non-degeneracy and residuals; anatomy is separate."""
    a = np.asarray(record["crop_points"], float)
    b = np.asarray(record["frame_points"], float)
    mat = np.asarray(record["affine_crop_to_frame"], float)
    if (
        a.ndim != 2
        or a.shape != b.shape
        or a.shape[1] != 2
        or len(a) < 30
        or mat.shape != (2, 3)
        or not np.isfinite(mat).all()
    ):
        raise ValueError("Insufficient finite publisher-to-movie correspondences")
    scale = float(np.linalg.norm(mat[:, 0]))
    sv = np.linalg.svd(mat[:, :2], compute_uv=False)
    if (
        not 4.5 < scale < 6
        or np.linalg.det(mat[:, :2]) <= 0
        or sv.max() / sv.min() > 1.02
        or np.any(np.ptp(a, axis=0) < 80)
    ):
        raise ValueError("Degenerate or implausible Figure1D registration")
    errors = np.linalg.norm(a @ mat[:, :2].T + mat[:, 2] - b, axis=1)
    if np.median(errors) > 2 or np.max(errors) > 4:
        raise ValueError("Publisher registration residual contradicts saved evidence")
    return mat, errors


def direction_check(origin, endpoint, anterior_region):
    """Projection toward one documented region, not an exact anatomical axis."""
    vector = np.asarray(endpoint) - origin
    target = np.asarray(anterior_region) - origin
    if not np.isfinite(np.r_[origin, endpoint, anterior_region]).all():
        raise ValueError("Finite points required")
    lengths = np.linalg.norm(vector) * np.linalg.norm(target)
    if lengths <= 0:
        raise ValueError("Distinct finite points required")
    return {
        "cosine_toward_documented_anterior_region": float(
            np.dot(vector, target) / lengths
        ),
        "target_projection_source_px": float(
            np.dot(target, vector / np.linalg.norm(vector))
        ),
    }


def init_plot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans", "sans-serif"],
            "font.size": 9,
        }
    )
    return plt


def sonnen_figures(frames, times, origins, endpoints, record, figure, output):
    plt = init_plot()
    mat, errors = checked_mapping(record)
    i = record["frame"]
    anchor = np.array(record["arrow_tip_crop_xy_approx"]) @ mat[:, :2].T + mat[:, 2]
    regional = direction_check(origins[i], endpoints[i], anchor)
    fig, axs = plt.subplots(1, 2, figsize=(10, 5.1))
    crop = figure[193:382, :187]
    axs[0].imshow(crop)
    axs[0].plot(
        *record["arrow_tip_crop_xy_approx"],
        "o",
        mfc="none",
        mec="#b68aff",
        ms=12,
        mew=1.5,
    )
    axs[0].set_title("Published Fig.1D · arrow: forming-segment sector")
    axs[0].axis("off")
    axs[1].imshow(frames[i])
    a, b = origins[i], endpoints[i]
    axs[1].plot([a[0], b[0]], [a[1], b[1]], color="#ffad43", lw=2)
    axs[1].annotate(
        "", xy=b, xytext=a, arrowprops={"arrowstyle": "->", "color": "#ffad43", "lw": 2}
    )
    axs[1].plot(*anchor, "o", mfc="none", mec="#b68aff", ms=14, mew=2)
    axs[1].text(
        a[0] + 12,
        a[1] + 25,
        "O: inner start",
        color="#ffcf77",
        bbox={"facecolor": "black", "alpha": 0.7, "pad": 2},
    )
    axs[1].text(b[0] - 20, b[1] + 15, "E", color="#ffcf77", fontsize=11)
    axs[1].set_title(f"S2 frame{i} · {times[i]:.2f}h · same published specimen")
    axs[1].axis("off")
    fig.text(
        0.03,
        0.105,
        f"{len(errors)} inlier pairs; median residual {np.median(errors):.2f} source px. Purple circle: approximately read published arrow tip.",
        fontsize=9,
        color="#535d6b",
    )
    fig.text(
        0.03,
        0.055,
        "Orange O→E points toward the documented anterior/segmenting sector; O and E are not exact P/A landmarks.",
        fontsize=9,
        color="#535d6b",
    )
    fig.text(
        0.03,
        0.015,
        "This establishes coarse regional direction, not an oscillation center, cell trajectory or first segmentation time.",
        fontsize=9,
        color="#535d6b",
    )
    fig.subplots_adjust(left=0.02, right=0.98, top=0.9, bottom=0.17, wspace=0.12)
    fig.savefig(output / "sonnen-s2-published-direction.png", dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(12, 8.5))
    selected = [0, 50, 89, 110, 132, 154]
    for ax, j in zip(axes.flat, selected):
        ax.imshow(frames[j])
        a, b = origins[j], endpoints[j]
        ax.annotate(
            "",
            xy=b,
            xytext=a,
            arrowprops={"arrowstyle": "->", "color": "#ffad43", "lw": 1.6},
        )
        ax.plot(*a, "o", mfc="none", mec="#ffcf77", ms=7, mew=1.5)
        ax.text(a[0] + 12, a[1] + 25, "O", color="#ffcf77")
        ax.text(b[0] - 15, b[1] + 15, "E", color="#ffcf77")
        ax.set_title(f"Frame{j} · {times[j]:.2f}h")
        ax.axis("off")
    fig.text(
        0.03,
        0.075,
        "O→E: posteriorward inner region toward the anteriorward/segmenting sector. Source frames are not flipped.",
        fontsize=9,
        color="#535d6b",
    )
    fig.text(
        0.03,
        0.04,
        "The strip remains inward→outward as tissue spreads; its endpoint becomes interior, not a tracked anatomical rim.",
        fontsize=9,
        color="#535d6b",
    )
    fig.text(
        0.03,
        0.008,
        "AP letters describe regional direction only. Movie zero is not proven culture zero; first marker/segment onset is unmeasured.",
        fontsize=9,
        color="#535d6b",
    )
    fig.subplots_adjust(
        left=0.01, right=0.99, top=0.96, bottom=0.12, wspace=0.05, hspace=0.1
    )
    fig.savefig(output / "sonnen-s2-ap-keyframes.jpg", dpi=180)
    plt.close(fig)
    return regional, selected, anchor


def video2_figure(
    frames, bf, times, matrix, origins, directions, positions, rows, output
):
    plt = init_plot()
    fig, axes = plt.subplots(2, 3, figsize=(12, 8.8))
    selected = [28, 85, 159]
    for col, i in enumerate(selected):
        a = origins[i]
        b = np.array(rows[i]["endpoint_xy"])
        full = a + positions[-1] / (100 / 111) * directions[i]
        for row, data in enumerate([frames, bf]):
            ax = axes[row, col]
            ax.imshow(data[i])
            ax.axhspan(0, 15, color="#cf6250", alpha=0.5)
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#ffad43", lw=1.8)
            ax.plot([b[0], full[0]], [b[1], full[1]], "--", color="#cba5ff", lw=1)
            ax.plot(*a, "+", color="white", ms=8)
            ax.plot(*b, "x", color="#ffcf77", ms=7)
            ax.set_title(
                f"{'LuVeLu' if row == 0 else 'Matched Video3 BF'} · f{i} · {times[i]:.2f}h"
            )
            ax.set_xlim(0, frames[i].shape[1])
            ax.set_ylim(frames[i].shape[0], 0)
            ax.axis("off")
    fig.text(
        0.02,
        0.085,
        "Solid orange: measured radius; dashed: missing extension. Top red band: existing15px exclusion, not an anterior boundary.",
        fontsize=9,
        color="#535d6b",
    )
    fig.text(
        0.02,
        0.045,
        "Late sampled end is near y≈17px/FOV cutoff. Neither LuVeLu nor BF supplies a matched anterior-marker boundary here.",
        fontsize=9,
        color="#535d6b",
    )
    fig.text(
        0.02,
        0.009,
        "Supplementary Fig.6:6h posterior markers throughout;21h central-posterior/peripheral-Mesp2. Different cultures, not a Video2 onset clock.",
        fontsize=9,
        color="#535d6b",
    )
    fig.subplots_adjust(
        left=0.01, right=0.99, top=0.95, bottom=0.13, wspace=0.04, hspace=0.11
    )
    fig.savefig(output / "video2-ap-scope.png", dpi=180)
    plt.close(fig)
    return selected


def run(source_dir, figure_path, registration_path, output_root):
    from PIL import Image

    out = output_root / "figures"
    out.mkdir(parents=True, exist_ok=True)
    data = output_root / "data"
    data.mkdir(parents=True, exist_ok=True)
    record = json.loads(registration_path.read_text())
    if (
        digest(figure_path)
        != "49d1a7b3e378f210e376c8cc42a28fb5fe90d23cfcde0fd7178d6d9093a95d18"
    ):
        raise ValueError("Publisher figure differs from reviewed source")
    son = (
        ASSET_ROOT / "data/derived/sonnen-2018/s2-review/movie-s2-reviewed-baseline.npz"
    )
    with np.load(son) as a:
        st = a["time_h"].copy()
        so = a["origins_xy"].copy()
        se = a["endpoints_xy"].copy()
    smovie = source_dir / "sonnen-2018/mmc3.mp4"
    if (
        digest(smovie)
        != "02b0f439d976b0a3cecb38ef89cab2c92fea1188242aceef40d11a7cf1594ec1"
    ):
        raise ValueError("Unexpected S2 source")
    frames = np.asarray(decode(smovie))
    fig = np.asarray(Image.open(figure_path).convert("RGB"))
    regional, skeys, anchor = sonnen_figures(frames, st, so, se, record, fig, out)
    record.update(
        source_figure_sha256=digest(figure_path),
        source_movie_sha256=digest(smovie),
        movie_time_h=float(st[record["frame"]]),
        regional_check=regional,
        approx_published_anterior_sector_xy=anchor.tolist(),
    )
    (data / "sonnen-fig1d-registration.json").write_text(
        json.dumps(record, indent=2) + "\n"
    )
    sreport = {
        "dataset": "sonnen-2018",
        "decision": "supported regional P→A direction; exact origin/end/oscillation center remain unregistered",
        "display": "A aboveP; zero already below; no additional data flip",
        "basis": [
            "S2 caption explicitly links Fig1D–F to this specimen and identifies forming-segment stripes.",
            "Text:posterior mPSM=center;anterior mPSM=periphery. Segment-posterior-half identity is a separate spatial level.",
            "Fig1D matches source frame89,14.85h,152 inliers,median error0.994 sourcepx.",
            "Consecutive frames0–154 reviewed; line remains inner→upper-left outward as tissue spreads, not a rim tracker.",
        ],
        "scope": "coarse regional direction across the retained display, referenced to the identified later anteriorward sector; not time-resolved molecular identity of every sampled cell",
        "keyframes": [{"frame": i, "time_h": float(st[i])} for i in skeys],
        "registration": "sonnen-fig1d-registration.json",
        "regional_check": regional,
        "not_measured": [
            "exact posterior landmark",
            "exact anterior boundary",
            "biological oscillator center",
            "culture-start time or first-marker onset",
            "tissue validity at every sample",
        ],
        "line_shift_extent_xy": (so - so[0]).tolist(),
        "source_matrix_unchanged": True,
    }
    (data / "sonnen-ap-review.json").write_text(json.dumps(sreport, indent=2) + "\n")
    del frames
    with np.load(ASSET_ROOT / "data/derived/lauschke-2013/video2-kymograph.npz") as a:
        raw = a["intensity"].copy()
        t = a["time_h"].copy()
        p = a["position_um"].copy()
        o = a["origins_xy"].copy()
        u = a["directions_xy"].copy()
    rows = endpoint_table(raw, t, p, o, u, 100 / 111)
    v2 = source_dir / "lauschke-2013/41586_2013_BFnature11804_MOESM293_ESM.mov"
    v3 = source_dir / "lauschke-2013/41586_2013_BFnature11804_MOESM294_ESM.mov"
    if (
        digest(v2) != "dd20eea69e9b443d0b6b3f84977b4454e3691237db7ddcd52f7e1f1f60b451dd"
        or digest(v3)
        != "14290aeaaca1dfaeca24a795e019b3e9a0f5fc30da9c86fa19a63f6458b0f294"
    ):
        raise ValueError("Unexpected Video2/3 source")
    f = np.asarray(decode(v2))
    bf = np.asarray(decode(v3))
    keys = video2_figure(f, bf, t, raw, o, u, p, rows, out)
    near = [r for r in rows if r.get("near_top_exclusion")]
    report = {
        "dataset": "lauschke-2013-mpsm",
        "decision": "retain center→outward coordinate without uniform AP letters for full0–33.8h",
        "direction_vs_identity": "mature-culture center-posterior/periphery-anterior organization is supported; insufficient same-specimen evidence for when this radius reaches differentiated anterior tissue",
        "new_observations": [
            "All160 LuVeLu frames reviewed; matched BF consecutive late frames inspected.",
            "98/160 measured ends are at y16.56–17.59px near the existing15px exclusion; from frame64(13.60h) onward this persists.",
            "No clear segment boundary along this sampled late ray was independently established in matched BF.",
            "Supplementary Fig6:6h vs21h marker stains are different cultures, not a Video2-specific clock or20h switch.",
        ],
        "top_edge_proximity": {
            "count": len(near),
            "operational_threshold_y_px": 20,
            "first_frame": near[0]["frame"],
            "first_time_h": near[0]["time_h"],
            "continuous_from_frame": 64,
            "continuous_from_time_h": float(t[64]),
        },
        "keyframes": [{"frame": i, "time_h": float(t[i])} for i in keys],
        "endpoint_audit": rows,
        "unresolved": [
            "same-specimen anterior marker/onset",
            "biological outer rim beyond clipped ray/FOV",
            "exact anatomical P/A endpoints",
        ],
        "completed": [
            "source identity",
            "consecutive movie review",
            "matched structural channel review",
            "stage-specific marker source review",
            "numeric endpoint/FOV audit",
        ],
        "source_matrix_unchanged": True,
    }
    assert len(near) == 98 and all(r["near_top_exclusion"] for r in rows[64:])
    (data / "video2-ap-review.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        "Rendered fresh AP review; S2 coarse direction supported, Video2 full-interval AP remains unsupported."
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-dir", type=Path, required=True)
    p.add_argument("--figure", type=Path, required=True)
    p.add_argument("--registration", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    run(a.source_dir, a.figure, a.registration, a.output)

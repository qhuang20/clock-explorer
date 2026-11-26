# SPDX-License-Identifier: MIT
"""Extract Lauschke Video 6 Mesp2 using the reviewed same-specimen LuVeLu strip.

Mesp2-GFP is displayed RED in the published movie. Geometry is inherited from
Video 5 after a same-frame check against merged Video 7; no Mesp2 center fit,
COM, temporal filter, phase or raw-fluorescence inference is introduced.
"""

import argparse
import hashlib
import json
from pathlib import Path

import av
import numpy as np
from scipy import ndimage as ndi

from paths import ASSET_ROOT
from extract_video_kymographs import decode
from extract_lauschke_radial import sample_radial, UM_PER_PX

SOURCES = {
    5: ("296", "04b7cad440c786080b2e50ec4ef041e5ebac0e66aea87dfa3c68961900ecbb2b"),
    6: ("297", "c80a25b0774f681f3c061f544ea69f504a0839a1e90a92ae9089e086bba577ae"),
    7: ("298", "4a5ace8823b5d219751c0adad3afd01b0a21541f8dc943039ef9bb1835b971fc"),
}
DATA = Path("data/derived/lauschke-2013/video6-mesp2")
FIGURES = Path("figures/lauschke-2013/video6-mesp2")
GEOMETRY_SHA = "0b065769a0541758cacdbc82f37e67250c42c9b4aeb2c8074d30da0e16b83958"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def extract_red(frames, origins, masks):
    """Select published red display values explicitly, preserving strip validity."""
    frames = np.asarray(frames)
    if frames.ndim != 4 or frames.shape[-1] != 3:
        raise ValueError("Expected source RGB frames")
    # The shared sampler historically reads channel 1. A broadcast view supplies
    # only the explicitly selected red signal to all slots without RGB mixing.
    red_view = np.broadcast_to(frames[..., 0, None], frames.shape)
    return sample_radial(red_view, origins, masks)


def correspondence(frames, merged):
    """Same-frame red features; exclude burned-in labels and broad BF contrast."""
    shifts, correlations = [], []
    for frame, overlay in zip(frames, merged):
        x = frame[40:650, 40:710, 0].astype(float)
        y = overlay[40:650, 40:710, 0].astype(float)
        window = np.outer(np.hanning(x.shape[0]), np.hanning(x.shape[1]))
        x = (ndi.gaussian_filter(x, 1) - ndi.gaussian_filter(x, 8)) * window
        y = (ndi.gaussian_filter(y, 1) - ndi.gaussian_filter(y, 8)) * window
        cross = np.fft.fft2(y) * np.conj(np.fft.fft2(x))
        corr = np.fft.fftshift(np.fft.ifft2(cross / (abs(cross) + 1e-10)).real)
        cy, cx = np.array(corr.shape) // 2
        row, col = np.unravel_index(
            np.argmax(corr[cy - 8 : cy + 9, cx - 8 : cx + 9]), (17, 17)
        )
        shifts.append([int(col - 8), int(row - 8)])
        correlations.append(float(np.corrcoef(x.ravel(), y.ravel())[0, 1]))
    if any(x != [0, 0] for x in shifts) or min(correlations) < 0.8:
        raise ValueError("Paired-channel correspondence needs renewed visual review")
    return {
        "integer_xy_shift_to_merged": shifts,
        "highpass_correlations": correlations,
        "domain": "source x40:710, y40:650; Gaussian 1-8 px; Hanning; +/-8 px search",
        "scope": "integer-pixel correspondence, not subpixel chromatic registration",
    }


def edges(values):
    return np.r_[
        values[0] - (values[1] - values[0]) / 2,
        (values[1:] + values[:-1]) / 2,
        values[-1] + (values[-1] - values[-2]) / 2,
    ]


def render(matrix, times, positions, destination):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "font.size": 9,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "text.color": "#252936",
            "axes.labelcolor": "#525b6b",
            "xtick.color": "#697386",
            "ytick.color": "#697386",
            "axes.edgecolor": "#9198a6",
            "axes.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig = plt.figure(figsize=(4.4, 3.35))
    ax = fig.add_axes([0.16, 0.16, 0.6643, 0.8])
    cmap = matplotlib.colormaps["OrRd"].copy()
    cmap.set_bad("#f1f3f6")
    low, high = np.nanmin(matrix), np.nanmax(matrix)
    mesh = ax.pcolormesh(
        edges(times),
        edges(positions),
        np.ma.masked_invalid((matrix - low) / (high - low)),
        cmap=cmap,
        vmin=0,
        vmax=1,
        rasterized=True,
        shading="flat",
    )
    ax.set_xlim(times[0], times[-1])
    ax.set_ylim(positions[-1], positions[0])
    ax.set_xticks([0, 2, 4, 6, 8, 10])
    ax.set_yticks(np.arange(0, 351, 50))
    ax.set_xlabel("Time (h)")
    ax.set_ylabel("Distance from paired center (µm)")
    bar = fig.colorbar(
        mesh, cax=fig.add_axes([0.85715, 0.16, 0.02437, 0.8]), ticks=[0, 0.5, 1]
    )
    bar.set_label("Relative display intensity")
    bar.outline.set_visible(False)
    destination.mkdir(parents=True, exist_ok=True)
    for fmt in ["svg", "png", "pdf"]:
        fig.savefig(destination / ("video6-mesp2-kymograph." + fmt), dpi=200)
    plt.close(fig)


def render_roi(frames, origins, masks, matrix, times, destination):
    import matplotlib.pyplot as plt

    direction = np.array([1.0, 1.0]) / np.sqrt(2)
    normal = np.array([-direction[1], direction[0]])
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 4.1))
    for ax, i in zip(axes, [0, 30, 60]):
        ax.imshow(frames[i])
        ax.contour(masks[i], levels=[0.5], colors=["#74cce0"], linewidths=0.8)
        origin = origins[i]
        last = np.flatnonzero(np.isfinite(matrix[:, i]))[-1]
        end = origin + last * direction
        corners = np.array(
            [
                origin - 10 * normal,
                end - 10 * normal,
                end + 10 * normal,
                origin + 10 * normal,
            ]
        )
        ax.fill(corners[:, 0], corners[:, 1], facecolor="#ffae43", alpha=0.18)
        ax.annotate(
            "",
            xy=end,
            xytext=origin,
            arrowprops={"arrowstyle": "->", "color": "#ffae43", "lw": 1.8},
        )
        ax.plot(*origin, "+", color="white", ms=10, mew=1.5)
        ax.set_title(f"Mesp2 · {times[i]:g} h · Frame {i}", fontsize=11)
        ax.axis("off")
    fig.text(
        0.02,
        0.025,
        "White: paired LuVeLu fitted center   Orange: 20 px radial strip at 45°   Cyan: shared analysis mask",
        fontsize=9,
        color="#535d6b",
    )
    fig.subplots_adjust(left=0.01, right=0.99, bottom=0.08, top=0.91, wspace=0.045)
    fig.savefig(destination / "video6-mesp2-roi.png", dpi=180)
    plt.close(fig)


def run(source_dir, output_root):
    data = ASSET_ROOT / "data/derived/lauschke-2013"
    paired = data / "video5-wavefront-comparison.npz"
    geometry = data / "video5-geometry.npz"
    if sha(paired) != GEOMETRY_SHA:
        raise ValueError("Unexpected reviewed Video 5 geometry")
    before = {str(p): sha(p) for p in [paired, geometry]}
    paths = {
        n: source_dir / f"41586_2013_BFnature11804_MOESM{suffix}_ESM.mov"
        for n, (suffix, _) in SOURCES.items()
    }
    pts = {}
    for n, path in paths.items():
        if sha(path) != SOURCES[n][1]:
            raise ValueError(f"Unexpected Video {n} source")
        with av.open(str(path)) as stream:
            pts[n] = [float(f.pts * f.time_base) for f in stream.decode(video=0)]
    assert pts[5] == pts[6] == pts[7] and len(pts[6]) == 61
    frames = np.asarray(decode(paths[6]))
    merged = np.asarray(decode(paths[7]))
    if frames.shape != merged.shape or frames.shape != (61, 742, 749, 3):
        raise ValueError("Unexpected paired source frame dimensions")
    check = correspondence(frames, merged)
    with np.load(paired) as f:
        origins = f["origins_xy"].copy()
        directions = f["directions_xy"].copy()
        times = f["time_h"].copy()
        positions = f["position_um"].copy()
        old_counts = f["valid_width_counts"].copy()
    with np.load(geometry) as f:
        masks = f["tissue_masks"].copy()
    np.testing.assert_allclose(
        directions, np.tile(np.array([1.0, 1.0]) / np.sqrt(2), (61, 1)), rtol=0, atol=0
    )
    np.testing.assert_allclose(times, np.arange(61) / 6, rtol=0, atol=0)
    np.testing.assert_allclose(positions, np.arange(401) * UM_PER_PX, rtol=0, atol=0)
    matrix, counts = extract_red(frames, origins, masks)
    np.testing.assert_array_equal(counts, old_counts)
    fov, _ = extract_red(frames, origins, np.ones_like(masks))
    recs = output_root / DATA
    figs = output_root / FIGURES
    recs.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        recs / "video6-mesp2-kymograph.npz",
        intensity=matrix,
        time_h=times,
        position_um=positions,
        origins_xy=origins,
        directions_xy=directions,
        valid_width_counts=counts,
        measurement_valid_mask=np.isfinite(matrix),
        fov_only_diagnostic=fov,
    )
    np.savetxt(
        recs / "video6-mesp2-intensity.csv",
        matrix,
        delimiter=",",
        header="space x time; original red display levels; NaN=missing",
    )
    render(matrix, times, positions, figs)
    render_roi(frames, origins, masks, matrix, times, figs)
    # A consecutive-frame record retains original source orientation and clocks.
    from PIL import Image, ImageDraw

    sheet = Image.new("RGB", (8 * 180, 8 * 200), "white")
    draw = ImageDraw.Draw(sheet)
    for i, frame in enumerate(frames):
        image = Image.fromarray(frame).resize((180, 178))
        x = (i % 8) * 180
        y = (i // 8) * 200
        sheet.paste(image, (x, y + 21))
        draw.text((x + 3, y + 3), f"Frame {i} / {times[i]:.2f} h", fill="black")
        origin = origins[i] * [180 / 749, 178 / 742]
        end = (
            origins[i] + np.flatnonzero(np.isfinite(matrix[:, i]))[-1] * directions[i]
        ) * [180 / 749, 178 / 742]
        draw.line(
            (x + origin[0], y + 21 + origin[1], x + end[0], y + 21 + end[1]),
            fill="#ffae43",
            width=1,
        )
    sheet.save(figs / "video6-all-frames-roi.jpg", quality=93)
    report = {
        "dataset": "lauschke-2013-mesp2",
        "method_version": "video6-paired-radial-v1",
        "source": {
            "movie": paths[6].name,
            "sha256": SOURCES[6][1],
            "shape_t_y_x_c": list(frames.shape),
            "reporter": "Mesp2-GFP",
            "target_gene": "Mesp2",
            "sample": "same segmentation-stage specimen as Videos 4,5,7",
            "channel": "red pseudo-colored display channel (index 0); NOT green despite GFP construct name",
            "source_caption": "Maximum-intensity projection of a z-stack; display movie, not raw fluorescence",
        },
        "paired_geometry": {
            "matrix_path": str(paired.relative_to(ASSET_ROOT)),
            "matrix_sha256": before[str(paired)],
            "mask_path": str(geometry.relative_to(ASSET_ROOT)),
            "mask_sha256": before[str(geometry)],
            "origin": "saved Video 5 common wavefront-fit center + Video 4 BF translation; no Mesp2/COM center fit",
            "angle_image_deg": 45,
            "width_px": 20,
            "transverse_samples": 21,
            "minimum_valid_count": 16,
            "mask": "existing BF-texture/LuVeLu-support analysis mask; shared-ray coverage reviewed, not full Mesp2-domain segmentation",
            "um_per_source_px": UM_PER_PX,
            "scale_basis": "same-frame 100 µm / 105 source px bar",
            "regional_polarity": "central posteriorward -> peripheral anteriorward; exact endpoints not anatomical landmarks",
        },
        "temporal": {
            "used_frames": 61,
            "total_frames": 61,
            "time_h": times.tolist(),
            "interval_min": 10,
            "basis": "matching burned-in clocks in all 61 Video6 frames and identical PTS to Videos5/7; Video5 reviewed clock retained",
            "clock_zero": "movie zero, not established culture-start zero",
        },
        "registration": check,
        "measurement": {
            "shape_space_time": list(matrix.shape),
            "missing_values": int(np.isnan(matrix).sum()),
            "finite_min": float(np.nanmin(matrix)),
            "finite_max": float(np.nanmax(matrix)),
            "outside_shared_mask_fov_only_max": float(
                np.nanmax(np.where(np.isfinite(matrix), np.nan, fov))
            ),
            "normalization": "whole-record finite min-max, independently from LuVeLu; no percentile clipping",
            "temporal_filter": False,
            "spatial_filter_added": False,
            "phase": False,
            "same_width_counts_as_paired_LuVeLu": True,
        },
        "limitations": [
            "Mesp2 is a segmentation marker; no assumption of sustained oscillator behavior or phase extraction.",
            "Compressed pseudo-colored display levels are not raw GFP counts, transcript concentration or cross-gene calibrated values.",
            "Inherited geometric center is not a validated pacemaker. Translation does not track cells or correct deformation.",
            "Shared analysis mask is reporter-informed and may exclude peripheral signal; this is one reviewed ray, not the full Mesp2 domain.",
            "Regional AP direction is supported; strip endpoint is not an established anterior boundary.",
        ],
        "display": {
            "source_plot_zero": "top",
            "UI_flip_y": True,
            "UI_top": "A",
            "UI_bottom": "P",
        },
        "inputs_unchanged": all(sha(p) == h for p, h in before.items()),
        "script_sha256": sha(__file__),
    }
    assert report["inputs_unchanged"]
    (recs / "video6-mesp2-provenance.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "shape": list(matrix.shape),
                "missing": report["measurement"]["missing_values"],
                "range": [
                    report["measurement"]["finite_min"],
                    report["measurement"]["finite_max"],
                ],
                "same_frame_registration": "0 px all 61 frames",
                "input_preserved": True,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    run(args.source_dir, args.output_root)

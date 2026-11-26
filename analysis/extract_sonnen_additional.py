# SPDX-License-Identifier: MIT
"""Local, reviewed display-video adapters for Sonnen 2018 Movies S1 and S3.

These are independent reconstructions, not the author ROIs or raw image stacks.
Inputs are the unmodified official playback files; no network access is used.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter, map_coordinates

from paths import ASSET_ROOT
from export_video_rois import bands_from_path

SETTINGS = {
    "s1": {
        "dataset": "sonnen-2018-embryo",
        "video": "movie-s1",
        "count": 88,
        "sha256": "f69d385c7aad96dbbd82c0ee8ea16989c3bb07a06c8adcaf849d12efaf5500cc",
        "source_file": "mmc2.mp4",
        "reporter": "Axin2T2A",
        "gene": "Axin2",
        "scale_bar_px": 164,
        "sigma_um": 5,
        "shape": [982, 988],
        "route": "axial",
        "direction_labels": ["P", "A"],
        "geometry": "Reviewed approximate P-side/A-side points, linearly interpolated in source-frame coordinates; no material-cell tracking.",
        "limitation": "Manual axial ROI, not the author's Figure 1C double-reporter experiment. FOV/annotation validity is not anatomical segmentation; approximate scale and P-side origin.",
    },
    "s3": {
        "dataset": "sonnen-2018-microfluidic",
        "video": "movie-s3",
        "count": 111,
        "sha256": "4c48c94ab0a86ec3ebc51db9f5f5a21b438f6d0d57fcfb9c2632d340284035aa",
        "source_file": "mmc4.mp4",
        "reporter": "LuVeLu",
        "gene": "Lfng",
        "scale_bar_px": 72,
        "sigma_um": 10,
        "shape": [512, 512],
        "route": "radial-route exploratory strip",
        "direction_labels": ["O", "E"],
        "geometry": "Fixed reviewed inner-to-upper-periphery image strip; conservative outer extents interpolated from silhouette keyframes. No COM, fitted wave center, or anatomical AP inference.",
        "limitation": "Microfluidic Movie S3 (Figure 3), not Figure 2B. The exact pulse protocol for this exported specimen is not identified by its caption. The origin is a manual image ROI, not a validated oscillation center; radial extent is a conservative manual coverage estimate.",
    },
}

# Frame, posterior-side x/y, anteriorward x/y, all in native source pixels.
S1_KEYS = np.array(
    [
        [0, 440, 650, 270, 180],
        [7, 435, 625, 265, 170],
        [15, 455, 640, 290, 185],
        [23, 450, 650, 285, 225],
        [31, 430, 680, 270, 245],
        [39, 450, 705, 290, 290],
        [47, 455, 720, 295, 320],
        [55, 470, 740, 300, 335],
        [63, 480, 775, 315, 360],
        [71, 495, 805, 325, 380],
        [79, 515, 855, 345, 420],
        [87, 520, 880, 350, 440],
    ],
    dtype=float,
)
# Frame, conservative supported radius in source pixels. Does not move zero.
S3_EXTENT_KEYS = np.array(
    [
        [0, 90],
        [10, 113],
        [20, 130],
        [30, 143],
        [40, 150],
        [50, 160],
        [60, 164],
        [70, 172],
        [80, 176],
        [90, 175],
        [100, 178],
        [110, 180],
    ],
    dtype=float,
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def experiment_clock(name, count):
    """Preserve the displayed clock, including S1's late 0.01-hour offsets."""
    if count != SETTINGS[name]["count"]:
        raise ValueError("Unexpected source frame count")
    times = np.arange(count, dtype=float) / 6
    if name == "s1":
        times = np.round(times, 2)
        for i, value in {77: 12.84, 80: 13.34, 83: 13.84, 86: 14.34}.items():
            times[i] = value
    return times


def geometry(name, count):
    frame = np.arange(count)
    if name == "s1":
        points = np.array(
            [np.interp(frame, S1_KEYS[:, 0], S1_KEYS[:, j]) for j in range(1, 5)]
        ).T
        origins = points[:, :2]
        directions = points[:, 2:] - origins
        directions /= np.linalg.norm(directions, axis=1)[:, None]
        extent_px = np.full(count, np.inf)
    else:
        origins = np.tile([235.0, 290.0], (count, 1))
        directions = np.tile([0.0, -1.0], (count, 1))
        extent_px = np.interp(frame, S3_EXTENT_KEYS[:, 0], S3_EXTENT_KEYS[:, 1])
    return origins, directions, extent_px


def image_validity(name, shape):
    yy, xx = np.indices(shape)
    valid = (xx >= 8) & (xx < shape[1] - 4) & (yy >= 4) & (yy < shape[0] - 4)
    if name == "s1":
        valid &= ~(((yy >= 895) & (xx < 400)) | ((yy >= 875) & (xx > 770)))
    else:
        valid &= ~((xx < 48) & (yy < 48))  # Cascade Blue inset and frame.
        valid &= ~((yy >= 450) & ((xx < 120) | (xx > 395)))
    return valid


def sample_image(image, path, normal, width_px, validity, sigma_px=0):
    """Bilinear finite-width mean; all transverse samples must be supported.

    True zero intensities remain valid. A Gaussian is independently applied
    within this frame; it never smooths time or crosses masked annotations.
    """
    offsets = np.linspace(-width_px / 2, width_px / 2, int(np.ceil(width_px)) + 1)
    xy = path[:, None, :] + offsets[None, :, None] * normal
    coords = [xy[..., 1], xy[..., 0]]
    image = image.astype(float)
    if sigma_px:
        weight = gaussian_filter(validity.astype(float), sigma_px)
        image = np.divide(
            gaussian_filter(np.where(validity, image, 0), sigma_px),
            weight,
            out=np.zeros_like(image),
            where=weight > 1e-6,
        )
    values = map_coordinates(image, coords, order=1, mode="constant", cval=np.nan)
    support = (
        map_coordinates(
            validity.astype(float), coords, order=1, mode="constant", cval=0
        )
        >= 1 - 1e-8
    )
    counts = (support & np.isfinite(values)).sum(axis=1)
    profile = np.full(len(path), np.nan)
    full = counts == len(offsets)
    profile[full] = values[full].mean(axis=1)
    return profile, counts


def render(
    name,
    cfg,
    frames,
    paths,
    normals,
    width,
    raw,
    smooth,
    times,
    positions,
    figures,
    valid,
):
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
        }
    )
    lo, hi = float(np.nanmin(raw)), float(np.nanmax(raw))
    cmap = plt.get_cmap("OrRd").copy()
    cmap.set_bad("#f1f3f6")

    def panel(fig, ax, data):
        xe = np.r_[
            times[0] - (times[1] - times[0]) / 2,
            (times[:-1] + times[1:]) / 2,
            times[-1] + (times[-1] - times[-2]) / 2,
        ]
        ye = np.r_[
            positions[0] - 0.5,
            (positions[:-1] + positions[1:]) / 2,
            positions[-1] + 0.5,
        ]
        im = ax.pcolormesh(
            xe,
            ye,
            np.ma.masked_invalid((data - lo) / (hi - lo)),
            cmap=cmap,
            vmin=0,
            vmax=1,
            rasterized=True,
            shading="flat",
        )
        ax.set(
            xlim=(times[0], times[-1]),
            ylim=(0, positions[-1]),
            xlabel="Time (h)",
            ylabel="Distance from P-side ROI (approx. µm)"
            if name == "s1"
            else "Distance from inner ROI (approx. µm)",
        )
        fig.colorbar(
            im, ax=ax, label="Relative display intensity", ticks=[0, 0.5, 1], pad=0.045
        )

    for filename, matrix in [
        ("kymograph", raw),
        ("spatial-filter", smooth),
        ("kymograph-common", raw),
    ]:
        fig, ax = plt.subplots(figsize=(6.2, 5.1))
        panel(fig, ax, matrix)
        if filename == "kymograph-common":
            ax.set_xlim(0, 10)
            ax.set_xticks([0, 2, 4, 6, 8, 10])
        fig.tight_layout()
        for ext in ["svg", "png", "pdf"]:
            fig.savefig(figures / (filename + "." + ext), dpi=180)
        plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, matrix, title in zip(
        axes,
        [raw, smooth],
        [
            "Primary · no image smoothing",
            f"Per-frame Gaussian · σ={cfg['sigma_um']} µm",
        ],
    ):
        panel(fig, ax, matrix)
        ax.set_title(title)
    fig.tight_layout()
    fig.savefig(figures / "spatial-comparison.svg")
    plt.close(fig)

    def overlay(i, size):
        im = Image.fromarray(frames[i]).convert("RGB")
        draw = ImageDraw.Draw(im)
        font_size = 36 if name == "s1" else 20
        font = ImageFont.truetype(
            str(Path(matplotlib.get_data_path()) / "fonts/ttf/DejaVuSans.ttf"),
            font_size,
        )
        bands, lines = bands_from_path(
            paths[i], np.tile(normals[i], (len(positions), 1)), valid[:, i], width
        )
        for band in bands:
            draw.line(
                [tuple(p) for p in band] + [tuple(band[0])], fill="#ffb454", width=3
            )
        for line in lines:
            draw.line([tuple(p) for p in line], fill="#ffb454", width=3)
        # Show requested but unsupported extension separately, without values.
        rejected = np.flatnonzero(~valid[:, i])
        for k in rejected[::8]:
            p = paths[i, k]
            draw.ellipse([p[0] - 1, p[1] - 1, p[0] + 1, p[1] + 1], fill="#b8b8c3")
        for p, label in [
            (paths[i, 0], cfg["direction_labels"][0]),
            (paths[i, np.flatnonzero(valid[:, i])[-1]], cfg["direction_labels"][1]),
        ]:
            x, y = p
            draw.rectangle(
                [x + 7, y - font_size, x + font_size + 16, y + 10], fill="black"
            )
            draw.text((x + 11, y - font_size), label, fill="#ffb454", font=font)
        im.thumbnail((size, size))
        return im

    for filename, indices, cols, size in [
        ("roi.png", [0, len(frames) // 2, len(frames) - 1], 3, 500),
        (
            "roi-review.jpg",
            np.unique(np.linspace(0, len(frames) - 1, 12).astype(int)),
            4,
            350,
        ),
    ]:
        rows = int(np.ceil(len(indices) / cols))
        sheet = Image.new("RGB", (cols * size, rows * (size + 30)), "white")
        draw = ImageDraw.Draw(sheet)
        for j, i in enumerate(indices):
            x = (j % cols) * size
            y = (j // cols) * (size + 30)
            sheet.paste(overlay(i, size), (x, y + 30))
            draw.text((x + 8, y + 8), f"Frame {i} · {times[i]:.2f} h", fill="black")
        sheet.save(figures / filename)


def run(name, source, output):
    cfg = SETTINGS[name]
    if digest(source) != cfg["sha256"]:
        raise ValueError("Source checksum mismatch")
    with av.open(str(source)) as c:
        decoded = list(c.decode(video=0))
        starts = np.array([float(f.pts * f.time_base) for f in decoded])
        starts -= starts[0]
        frames = [f.to_ndarray(format="rgb24") for f in decoded]
    if len(frames) != cfg["count"] or list(frames[0].shape[:2]) != cfg["shape"]:
        raise ValueError("Unexpected decoded dimensions")
    times = experiment_clock(name, len(frames))
    scale = 100 / cfg["scale_bar_px"]
    width_px = 70 / scale
    positions = np.arange(301, dtype=float)
    origins, directions, extents = geometry(name, len(frames))
    normals = np.stack([-directions[:, 1], directions[:, 0]], axis=-1)
    paths = (
        origins[:, None, :] + positions[None, :, None] / scale * directions[:, None, :]
    )
    raw = np.full((len(positions), len(frames)), np.nan)
    smooth = raw.copy()
    counts = np.zeros(raw.shape, dtype=int)
    validity = image_validity(name, frames[0].shape[:2])
    for i, f in enumerate(frames):
        raw[:, i], counts[:, i] = sample_image(
            f[:, :, 1], paths[i], normals[i], width_px, validity
        )
        smooth[:, i], _ = sample_image(
            f[:, :, 1],
            paths[i],
            normals[i],
            width_px,
            validity,
            cfg["sigma_um"] / scale,
        )
        outside = positions / scale > extents[i]
        raw[outside, i] = np.nan
        smooth[outside, i] = np.nan
    data = output / "data/derived/sonnen-2018" / cfg["video"]
    figures = output / "figures/sonnen-2018" / cfg["video"]
    data.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    numeric = data / "kymograph.npz"
    np.savez_compressed(
        numeric,
        intensity=raw,
        spatial_filtered=smooth,
        time_h=times,
        position_um=positions,
        frame_index=np.arange(len(frames)),
        origins_xy=origins,
        directions_xy=directions,
        path_xy=paths,
        normals_xy=normals,
        valid=np.isfinite(raw),
        fov_width_counts=counts,
        coverage_extent_px=extents,
        strip_width_px=width_px,
        um_per_px=scale,
    )
    with (data / "frame-times.csv").open("w") as f:
        writer = csv.writer(f)
        writer.writerow(["frame", "time_h", "playback_s"])
        writer.writerows(zip(range(len(frames)), times, starts))
    roi_frames = []
    for i in range(len(frames)):
        bands, lines = bands_from_path(
            paths[i],
            np.tile(normals[i], (len(positions), 1)),
            np.isfinite(raw[:, i]),
            width_px,
        )
        roi_frames.append(
            dict(index=i, experiment_h=float(times[i]), bands=bands, lines=lines)
        )
    roi = dict(
        schema_version=1,
        dataset_id=cfg["dataset"],
        video_id=cfg["video"],
        source_sha256=cfg["sha256"],
        playback_sha256=cfg["sha256"],
        width=frames[0].shape[1],
        height=frames[0].shape[0],
        frame_starts_s=starts.tolist(),
        frames=roi_frames,
        direction_labels=cfg["direction_labels"],
        geometry_input=str(numeric.relative_to(output)),
        geometry_input_sha256=digest(numeric),
        scope=cfg["geometry"],
    )
    (data / "video-roi.json").write_text(json.dumps(roi, separators=(",", ":")) + "\n")
    provenance = dict(
        dataset=cfg["dataset"],
        paper_id="sonnen-2018",
        source_url="https://pmc-oa-opendata.s3.amazonaws.com/PMC5847172.1/"
        + cfg["source_file"],
        source_sha256=digest(source),
        reporter=cfg["reporter"],
        target_gene=cfg["gene"],
        shape_space_time=list(raw.shape),
        time_range_h=[float(times[0]), float(times[-1])],
        time_basis="S1: all 88 burned-in decimal-hour labels visually transcribed; late .01 h offsets preserved. S3: h:mm display, 10 min per frame (0:00–18:20), separate from 25 fps playback.",
        scale=dict(
            bar_um=100,
            bar_px=cfg["scale_bar_px"],
            um_per_px=scale,
            approximate=True,
            note="Measured from exported movie bar; acquisition 1.38 µm/px is not substituted. Equal x/y export scaling is assumed.",
        ),
        route=cfg["route"],
        geometry=cfg["geometry"],
        keyframes=(S1_KEYS if name == "s1" else S3_EXTENT_KEYS).tolist(),
        sampling=dict(
            width_um=70,
            width_px=width_px,
            offset_count=int(np.ceil(width_px)) + 1,
            channel="decoded green channel of grayscale rendered fluorescence",
            interpolation="bilinear",
            primary_image_sigma_um=0,
            temporal_smoothing=False,
            optional_image_sigma_um=cfg["sigma_um"],
            validity="Full width inside FOV and outside annotations; S3 additionally uses conservative manually reviewed outer extents. Not a full anatomical segmentation. True zeros retained.",
        ),
        limitation=cfg["limitation"],
        normalization=[float(np.nanmin(raw)), float(np.nanmax(raw))],
        input_sha256=digest(numeric),
        script_sha256=digest(__file__),
    )
    (data / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    render(
        name,
        cfg,
        frames,
        paths,
        normals,
        width_px,
        raw,
        smooth,
        times,
        positions,
        figures,
        np.isfinite(raw),
    )
    print(
        cfg["dataset"],
        list(raw.shape),
        "hours",
        times[-1],
        "missing",
        int(np.isnan(raw).sum()),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=["s1", "s3"], action="append")
    parser.add_argument("--asset-root", type=Path, default=ASSET_ROOT)
    parser.add_argument("--output-root", type=Path, default=ASSET_ROOT)
    args = parser.parse_args()
    for name in args.only or ["s1", "s3"]:
        run(
            name,
            args.asset_root / "videos/sonnen-2018" / (SETTINGS[name]["video"] + ".mp4"),
            args.output_root,
        )

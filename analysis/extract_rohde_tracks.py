# SPDX-License-Identifier: MIT
#!/usr/bin/env python3
"""Re-bin published Rohde/Bercowsky-Rama 2024 continuous Her1-YFP spot measurements.

No event maps, fluorescence-image inversion, intensity interpolation, smoothing,
normalization, gap filling, or mixing of independently exported spot sets.
Requires numpy; previews additionally require matplotlib and tifffile.
Numerical-only offline run: python extract_rohde_tracks.py --no-previews
This mode uses the four files bundled in data/samples/rohde-2024/.
Optional previews additionally need the author's Time150min.tif and
Time300min.tif in that directory; these large images are not bundled.
"""

from paths import ASSET_ROOT
from pathlib import Path
import argparse
import csv
import hashlib
import json
import os
import struct
import zipfile
import xml.etree.ElementTree as ET
import numpy as np

APP = ASSET_ROOT
ROOT = APP / "data/derived/rohde-2024"
ROOT.mkdir(parents=True, exist_ok=True)
SRC = APP / "data/samples/rohde-2024"

BIN_UM = 20.0  # analysis bin, not microscope resolution
DT_S = 90.0  # Methods + both author notebooks
NUMERICAL_SOURCE_SHA256 = {
    "vertices.csv": "f6c38cc5e6b6a7c3a5b62f5a9d8b83720c2f23bef7450da41dad541913d4e761",
    "psm4-vertices.csv": "0d6918adf6250759fd69db89fa9b11557438f2477d8661b486e89ead408dda3d",
    "acquisition.xml": "c2369585bba63cf8054cbee2fed5222850084f05e76f56fccc302dc38f0c542c",
    "RoiSet.zip": "3ed9355d5550e2999d744cbc5cd2a010005d94b4124a243fb7f0428131a5fff8",
}
PREVIEW_SOURCE_SHA256 = {
    "Time150min.tif": "8f45e17b5322308ab6a7adae9bc970f053b86899257673a2d9b10572f31dc228",
    "Time300min.tif": "9023016c07e573c703e37451ee28749c212ae85aeb99e0b4fb299cd6ac3805d0",
}


def read_rois(path):
    """Read ImageJ integer/subpixel polylines, verified against official RoiDecoder.java.

    ImageJ RoiDecoder: type byte offset 6; top/left 8/10; N 16; options 50;
    coordinates at 64. Fail rather than silently reinterpret unsupported variants.
    """
    rois = {}
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            b = z.read(name)
            assert b[:4] == b"Iout" and b[6] == 5, (name, "not polyline")
            top, left = struct.unpack(">hh", b[8:12])
            n = struct.unpack(">H", b[16:18])[0]
            options = struct.unpack(">H", b[50:52])[0]
            assert n == 32, (name, "unexpected ROI encoding")
            x = np.frombuffer(b[64 : 64 + 2 * n], ">i2").astype(float) + left
            y = np.frombuffer(b[64 + 2 * n : 64 + 4 * n], ">i2").astype(float) + top
            if options & 128:
                x = np.frombuffer(b[64 + 4 * n : 64 + 8 * n], ">f4").astype(float)
                y = np.frombuffer(b[64 + 8 * n : 64 + 12 * n], ">f4").astype(float)
            frame = int(Path(name).stem[:4]) - 1
            assert frame not in rois
            rois[frame] = np.column_stack([x, y])
    return rois


def read_spots(path):
    rows = list(csv.reader(path.open()))
    top, sub, units = rows[:3]

    def ix(a, b=None):
        matches = [
            i for i, name in enumerate(top) if name == a and (b is None or sub[i] == b)
        ]
        assert len(matches) == 1, (a, b, matches)
        return matches[0]

    columns = [
        ix("ID"),
        ix("Spot frame"),
        ix("Spot gaussian-filtered intensity", "Mean ch0"),
        ix("Spot position", "X"),
        ix("Spot position", "Y"),
        ix("Spot position", "Z"),
        ix("Spot track ID"),
    ]
    assert units[columns[2]] == "(Counts)"
    assert all(units[c] == "(micron)" for c in columns[3:6])
    a = np.array([[float(row[i]) for i in columns] for row in rows[3:]], dtype=float)
    assert np.isfinite(a).all() and len(np.unique(a[:, 0])) == len(a)
    return a


def reference_line(poly_um):
    # Same 20 subdivisions per original ROI segment as author notebook.
    return np.vstack(
        [
            p + (q - p) * np.arange(20)[:, None] / 20
            for p, q in zip(poly_um[:-1], poly_um[1:])
        ]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-previews",
        action="store_true",
        help="Write both NPZ files and statistics without plotting or reading TIFFs.",
    )
    args = parser.parse_args()
    required = dict(NUMERICAL_SOURCE_SHA256)
    if not args.no_previews:
        required.update(PREVIEW_SOURCE_SHA256)
        os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "mpl-cache"))
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import tifffile
    for filename, expected_sha256 in required.items():
        assert (
            hashlib.sha256((SRC / filename).read_bytes()).hexdigest() == expected_sha256
        ), filename
    xml = ET.parse(SRC / "acquisition.xml").getroot()
    voxel_um = np.array(
        list(map(float, xml.find(".//ViewSetup/voxelSize/size").text.split()))
    )
    first = int(xml.find(".//Timepoints/first").text)
    last = int(xml.find(".//Timepoints/last").text)
    nframes = last - first + 1
    assert first == 0 and last == 299
    time_h = np.arange(nframes) * DT_S / 3600
    rois_px = read_rois(SRC / "RoiSet.zip")
    assert set(rois_px) == set(range(nframes))
    rois_um = {t: p * voxel_um[:2] for t, p in rois_px.items()}
    transforms = {}
    for e in xml.findall(".//ViewRegistration"):
        if e.attrib["setup"] == "0":
            transforms[int(e.attrib["timepoint"])] = np.array(
                list(map(float, e.find("ViewTransform/affine").text.split()))
            ).reshape(3, 4)
    records = []
    raw_for_overlay = {}
    for name, filename in [
        ("tailbud_cohort", "vertices.csv"),
        ("psm4_cohort", "psm4-vertices.csv"),
    ]:
        spots = read_spots(SRC / filename)
        frames = spots[:, 1].astype(int)
        assert ((frames >= 0) & (frames < nframes)).all()
        raw_xyz = np.full((len(spots), 3), np.nan)
        distance_um = np.full(len(spots), np.nan)
        lateral_um = np.full(len(spots), np.nan)
        for t in np.unique(frames):
            take = frames == t
            affine = transforms[t]
            # Author notebook maps registered Mastodon coordinates into raw-image µm.
            raw_xyz[take] = np.linalg.solve(
                affine[:, :3], (spots[take, 3:6] - affine[:, 3]).T
            ).T
            line = reference_line(rois_um[t])
            squared = np.sum((raw_xyz[take, None, :2] - line[None, :, :]) ** 2, axis=2)
            k = np.argmin(squared, axis=1)
            # Authors use Euclidean distance to posterior ROI endpoint (NOT arclength).
            distance_um[take] = np.linalg.norm(line[k] - line[0], axis=1)
            lateral_um[take] = np.sqrt(squared[np.arange(len(k)), k])
        assert np.isfinite(raw_xyz).all() and np.isfinite(distance_um).all()
        upper = np.ceil(distance_um.max() / BIN_UM) * BIN_UM
        edges = np.arange(0, upper + BIN_UM, BIN_UM)
        centers = (edges[:-1] + edges[1:]) / 2
        sums = np.zeros((len(centers), nframes))
        counts = np.zeros_like(sums, dtype=np.int32)
        bins = np.minimum(np.floor(distance_um / BIN_UM).astype(int), len(centers) - 1)
        np.add.at(sums, (bins, frames), spots[:, 2])
        np.add.at(counts, (bins, frames), 1)
        intensity = np.full_like(sums, np.nan)
        np.divide(sums, counts, out=intensity, where=counts > 0)
        assert counts.sum() == len(spots)
        assert np.array_equal(np.isnan(intensity), counts == 0)
        target = ROOT / f"{name}.npz"
        np.savez_compressed(
            target,
            intensity=intensity,
            time_h=time_h,
            position_um=centers,
            position_edges_um=edges,
            cell_count=counts,
            missing_mask=counts == 0,
            frame_index=np.arange(nframes),
            spot_frame=frames,
            spot_id=spots[:, 0].astype(int),
            spot_track_id=spots[:, -1].astype(int),
            spot_intensity=spots[:, 2],
            spot_distance_um=distance_um,
            spot_raw_xyz_um=raw_xyz,
            spot_lateral_distance_um=lateral_um,
        )
        entry = {
            "id": name,
            "npz": str(target.relative_to(ROOT)),
            "csv": filename,
            "matrix_shape": list(intensity.shape),
            "spot_observations": len(spots),
            "track_ids": int(len(np.unique(spots[:, -1]))),
            "frame_range_with_spots": [int(frames.min()), int(frames.max())],
            "time_h_with_spots": [
                float(time_h[frames.min()]),
                float(time_h[frames.max()]),
            ],
            "observed_position_um": [
                float(distance_um.min()),
                float(distance_um.max()),
            ],
            "cell_count_nonempty_min_median_max": [
                int(counts[counts > 0].min()),
                float(np.median(counts[counts > 0])),
                int(counts.max()),
            ],
            "missing_fraction": float(np.mean(counts == 0)),
            "intensity_min_max": [float(spots[:, 2].min()), float(spots[:, 2].max())],
            "position_bin_width_um": BIN_UM,
            "lateral_distance_um_median_max": [
                float(np.median(lateral_um)),
                float(lateral_um.max()),
            ],
        }
        records.append(entry)
        if args.no_previews:
            continue
        raw_for_overlay[name] = (spots, raw_xyz)
        fig, axs = plt.subplots(
            2, 1, figsize=(11, 7), layout="constrained", sharex=True
        )
        im = axs[0].pcolormesh(
            np.arange(nframes + 1) * DT_S / 3600 - DT_S / 7200,
            edges,
            np.ma.masked_invalid(intensity),
            cmap="OrRd",
            shading="flat",
            vmin=0,
        )
        axs[0].set(
            ylabel="Distance from posterior ROI endpoint (µm)",
            title=f"{name}: measured Her1-YFP; 20 µm bins; empty bins masked",
        )
        fig.colorbar(im, ax=axs[0], label="Mean spot intensity (counts)")
        ic = axs[1].pcolormesh(
            np.arange(nframes + 1) * DT_S / 3600 - DT_S / 7200,
            edges,
            counts,
            cmap="Greys",
            shading="flat",
        )
        axs[1].set(xlabel="Time from acquisition frame 0 (h)", ylabel="Position (µm)")
        fig.colorbar(ic, ax=axs[1], label="Measured spots per bin")
        fig.savefig(ROOT / f"{name}-diagnostic.png", dpi=150)
        plt.close(fig)

    (ROOT / "extraction-statistics.json").write_text(json.dumps(records, indent=2))
    print(json.dumps(records, indent=2))
    if args.no_previews:
        return

    fig, axs = plt.subplots(1, 2, figsize=(13, 6), layout="constrained")
    for ax, t in zip(axs, [100, 200]):
        img = tifffile.imread(SRC / f"Time{int(t * DT_S / 60)}min.tif")
        ax.imshow(
            img,
            origin="upper",
            extent=[0, img.shape[1] * voxel_um[0], img.shape[0] * voxel_um[1], 0],
        )
        p = rois_um[t]
        ax.plot(p[:, 0], p[:, 1], color="cyan", lw=1.1, label="Published notochord ROI")
        ax.scatter(
            p[0, 0],
            p[0, 1],
            s=65,
            c="red",
            marker="x",
            label="Posterior reference (0 µm)",
        )
        for name, color in [("tailbud_cohort", "orange"), ("psm4_cohort", "magenta")]:
            a, xyz = raw_for_overlay[name]
            take = a[:, 1] == t
            ax.scatter(
                xyz[take, 0],
                xyz[take, 1],
                s=14,
                facecolors="none",
                edgecolors=color,
                lw=0.7,
                label=f"{name} spots",
            )
        ax.set(
            title=f"{t * DT_S / 60:g} min — frame {t}",
            xlabel="Raw image X (µm)",
            ylabel="Raw image Y (µm)",
        )
    axs[1].legend(loc="upper right", fontsize=7)
    fig.suptitle(
        "Published RGB projection + imported ROI + inverse-transformed measured spots\nRGB TIFFs used only for geometric validation; intensity comes from CSV",
        fontsize=11,
    )
    fig.savefig(ROOT / "roi-overlay.png", dpi=160)
    plt.close(fig)

    fig, axs = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    for ax, t in zip(axs[0], [100, 200]):
        img = tifffile.imread(SRC / f"Time{int(t * DT_S / 60)}min.tif")
        ax.imshow(img)
        ax.set_title(f"Published projection: {t * DT_S / 60:g} min")
        ax.axis("off")
    for ax, name in zip(axs[1], ["tailbud_cohort", "psm4_cohort"]):
        d = np.load(ROOT / f"{name}.npz")
        m = d["intensity"]
        edges = d["position_edges_um"]
        ax.pcolormesh(
            np.arange(nframes + 1) * DT_S / 3600 - DT_S / 7200,
            edges,
            np.ma.masked_invalid(m),
            cmap="OrRd",
            vmin=0,
            shading="flat",
        )
        ax.set(
            title=name + " — measured spots binned in space",
            xlabel="Acquisition time (h)",
            ylabel="Posterior-reference distance (µm)",
        )
    fig.savefig(ROOT / "contact-sheet.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()

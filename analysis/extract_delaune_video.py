# SPDX-License-Identifier: MIT
"""Reconstruct Delaune 2012 Movie S1 from the official rendered movie.

Usage: python extract_delaune_video.py --source-dir /path/to/delaune-2012-revisit
Offline inputs: NIHMS417414-supplement-04.mov and figure1.jpg.
Dependencies: numpy, Pillow, av. Run render_comparison.py after extraction.
"""

from paths import ASSET_ROOT
import argparse, hashlib, json
from pathlib import Path
import av
import numpy as np
from PIL import Image, ImageDraw

ROOT = ASSET_ROOT
URL = "https://pmc.ncbi.nlm.nih.gov/articles/instance/3500528/bin/NIHMS417414-supplement-04.mov"
FIG_URL = (
    "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/5ebe/3500528/23b3f391c9b3/nihms417414f1.jpg"
)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def window_sums(a, h, w):
    s = np.pad(a, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    return s[h:, w:] - s[:-h, w:] - s[h:, :-w] + s[:-h, :-w]


def template_match(a, b):
    h, w = b.shape
    b = b - b.mean()
    size = [1 << (a.shape[k] + b.shape[k] - 2).bit_length() for k in range(2)]
    conv = np.fft.irfft2(
        np.fft.rfft2(a, size) * np.fft.rfft2(b[::-1, ::-1], size), size
    )[h - 1 : a.shape[0], w - 1 : a.shape[1]]
    norm = np.sqrt(
        np.maximum(window_sums(a * a, h, w) - window_sums(a, h, w) ** 2 / (h * w), 1e-8)
        * np.sum(b * b)
    )
    corr = conv / norm
    y, x = np.unravel_index(np.argmax(corr), corr.shape)
    return float(corr[y, x]), int(x), int(y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-dir", type=Path, required=True)
    args = ap.parse_args()
    source = args.source_dir / "NIHMS417414-supplement-04.mov"
    fig = args.source_dir / "figure1.jpg"
    assert (
        sha(source)
        == "37765980a6e010723ffaf367cd691814a55cc065c8356a1bb3a135d427079a16"
    ), "Source changed; review before reconstruction"
    with av.open(str(source)) as c:
        stream = c.streams.video[0]
        fps = float(stream.average_rate)
        frames = [f.to_ndarray(format="rgb24") for f in c.decode(video=0)]
    assert len(frames) == 24 and frames[0].shape == (1024, 1024, 3)
    # RGB channels of this grayscale movie are identical. Preserve the decoded
    # display channel; do not infer photon counts or undo compression / gamma.
    assert all(
        np.array_equal(f[:, :, 0], f[:, :, 1])
        and np.array_equal(f[:, :, 1], f[:, :, 2])
        for f in frames
    )
    gray = [f[:, :, 1] for f in frames]
    out = ROOT / "data/derived/delaune-2012"
    out.mkdir(parents=True, exist_ok=True)
    pics = ROOT / "figures/delaune-2012"
    pics.mkdir(parents=True, exist_ok=True)
    # Verify time from primary figure panels, never from the playback FPS.
    published = np.array(Image.open(fig).convert("L"))
    matches = []
    qc = Image.new("RGB", (4 * 210, 340), "white")
    draw = ImageDraw.Draw(qc)
    for j, left in enumerate([30, 146, 263, 382]):
        target = published[323:439, left + 12 : left + 100].astype(float)
        rank = []
        for i, f in enumerate(gray):
            best = (-1, None, None, None)
            for size in range(150, 221, 2):
                a = np.array(Image.fromarray(f).resize((size, size)), dtype=float)
                score, x, y = template_match(a, target)
                if score > best[0]:
                    best = (score, size, x, y)
            rank.append(
                dict(frame=i, correlation=best[0], resize=best[1], x=best[2], y=best[3])
            )
        rank.sort(key=lambda r: -r["correlation"])
        best = rank[0]
        assert best["frame"] == 3 * (j + 1) and best["correlation"] > 0.92
        matches.append(
            dict(panel=f"F{j + 1}", published_time_min=j * 12, ranked_matches=rank)
        )
        x = j * 210
        draw.text((x + 5, 5), f"Fig.1 F{j + 1}: {j * 12} min", fill="black")
        qc.paste(Image.fromarray(target.astype("uint8")).convert("RGB"), (x + 5, 25))
        draw.text(
            (x + 5, 160),
            f"Movie frame {best['frame']} | r={best['correlation']:.3f}",
            fill="black",
        )
        a = Image.fromarray(gray[best["frame"]]).resize(
            (best["resize"], best["resize"])
        )
        qc.paste(
            a.crop((best["x"], best["y"], best["x"] + 88, best["y"] + 116)).convert(
                "RGB"
            ),
            (x + 5, 185),
        )
    qc.save(pics / "time-calibration.png")
    (out / "figure-frame-match.json").write_text(json.dumps(matches, indent=2) + "\n")
    # Fixed image strip entirely on the left side of the midline; x is
    # mediolateral, y anterior->posterior in the published dorsal view.
    # This is an Eulerian image-coordinate profile, not tracked tissue / cells.
    x0, x1, y0, y1 = 330, 450, 180, 850
    matrix = np.stack([f[y0 : y1 + 1, x0:x1].mean(axis=1) for f in gray], axis=1)
    frame_index = np.arange(24)
    time_h = frame_index * 4 / 60
    position_px = np.arange(y0, y1 + 1)
    assert matrix.shape == (671, 24) and np.isfinite(matrix).all()
    np.savez_compressed(
        out / "movie-s1-kymograph.npz",
        intensity=matrix,
        time_h=time_h,
        position_px=position_px,
        frame_index=frame_index,
    )
    np.savetxt(out / "movie-s1-intensity.csv", matrix, delimiter=",", fmt="%.7g")
    np.savetxt(
        out / "movie-s1-time-h.csv", time_h, delimiter=",", header="time_h", comments=""
    )
    np.savetxt(
        out / "movie-s1-position-px.csv",
        position_px,
        delimiter=",",
        header="image_y_video_px",
        comments="",
        fmt="%d",
    )
    sheet = Image.new("RGB", (3 * 512, 542), "white")
    draw = ImageDraw.Draw(sheet)
    for j, i in enumerate([0, 12, 23]):
        im = Image.fromarray(frames[i])
        di = ImageDraw.Draw(im)
        di.rectangle((x0, y0, x1 - 1, y1), outline="#ff8b3d", width=5)
        di.line(((x0 + x1) // 2, y0, (x0 + x1) // 2, y1), fill="#ff8b3d", width=2)
        sheet.paste(im.resize((512, 512)), (j * 512, 30))
        draw.text(
            (j * 512 + 8, 8),
            f"Frame {i} | {i * 4} min from movie start | fixed ROI",
            fill="black",
        )
    sheet.save(pics / "roi-overlay.jpg", quality=94)
    prov = dict(
        paper_id="delaune-2012",
        source_url=URL,
        source_filename=source.name,
        source_sha256=sha(source),
        source_bytes=source.stat().st_size,
        source_level="Compressed published grayscale movie, not raw fluorescence",
        movie_mapping={
            "04.mov": "Movie S1: single dorsal grayscale field; matches Fig.1F and supplemental caption",
            "02.avi": "Movie S2: four genotype panels, not Movie S1 despite JATS SD2 link",
        },
        reporter="Her1–Venus",
        genotype="Heterozygous Tg(her1:her1-Venus)bk15",
        temperature_C=23,
        temperature_basis="Methods temperature-ring setpoint; Results says 22–23°C. No per-movie thermometer record.",
        shape_space_time=list(matrix.shape),
        frame_count=len(frames),
        playback_fps=fps,
        time_interval_min=4,
        time_range_h=[0, float(time_h[-1])],
        time_origin="First decoded video frame; 12 min before Fig.1F1 zero",
        time_calibration={
            "basis": "Methods 4 min interval independently supported by Fig.1F1–F4 image matching",
            "figure_url": FIG_URL,
            "figure_sha256": sha(fig),
            "published_times_min": [0, 12, 24, 36],
            "matched_frames": [3, 6, 9, 12],
            "published_time_from_movie_start_min": 12,
            "matching_method": "Normalized cross-correlation after scalar resize; full frame ranking; see figure-frame-match.json",
        },
        spatial_unit="video px",
        spatial_axis="Absolute image y, downward, anterior toward posterior in this dorsal view",
        spatial_calibration="No rendered-video scale bar verified. Raw 2.092 px/µm NOT transferred.",
        roi={
            "x_start_inclusive": x0,
            "x_end_exclusive": x1,
            "y_start_inclusive": y0,
            "y_end_inclusive": y1,
            "width_px": x1 - x0,
            "registration": "none; fixed image coordinates",
        },
        extraction="Arithmetic mean of decoded green (identical grayscale RGB) values across each ROI row, independently at each frame. No temporal filtering, background subtraction, drift correction, interpolation, phase inference or tissue mask.",
        normalization="Complete matrix finite min-max to [0,1] in shared renderer; zero is sample minimum, not zero fluorescence.",
        limitations=[
            "Rendered values are affected by compression, display LUT, possible clipping and gamma.",
            "Growth, motion and out-of-plane loss are not corrected. Supplemental S1 caption explicitly describes PSM leaving the imaging plane.",
            "Low displayed signal cannot distinguish weak expression, missing tissue and defocus; no tissue mask inferred.",
            "Use for qualitative spatial waveform comparison, not absolute amplitude or physical wave-speed fitting.",
            "Biological time mapping between labeled figure frames assumes uniform export cadence consistent with Methods.",
        ],
        display_range=[float(matrix.min()), float(matrix.max())],
        roi_fraction_pixels_at_255=float(
            np.mean([np.mean(f[y0 : y1 + 1, x0:x1] == 255) for f in gray])
        ),
        license="© 2012 Elsevier. Local research derivation; no public redistribution license inferred.",
        script="extract_delaune_video.py",
        script_sha256=sha(Path(__file__)),
        libraries={"numpy": np.__version__, "av": av.__version__},
    )
    (out / "provenance.json").write_text(
        json.dumps(prov, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "shape": matrix.shape,
                "duration_h": float(time_h[-1]),
                "range": prov["display_range"],
                "matched_frames": [r["ranked_matches"][0]["frame"] for r in matches],
            }
        )
    )


if __name__ == "__main__":
    main()

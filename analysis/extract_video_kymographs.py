# SPDX-License-Identifier: MIT
# coding: utf-8
"""Extract exploratory kymographs from locally downloaded official movies.

python extract_video_kymographs.py --source-dir /path/to/additional-data
Input videos are not bundled. Exact source URLs and hashes accompany outputs.
No network access. Dependencies: av, numpy, Pillow.
"""

from paths import ASSET_ROOT
import argparse, hashlib, json
from pathlib import Path
import av
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

ROOT = ASSET_ROOT
SOURCE_METADATA = {
    "lauschke-2013": {
        "source_url": "https://static-content.springer.com/esm/art%3A10.1038%2Fnature11804/MediaObjects/41586_2013_BFnature11804_MOESM296_ESM.mov",
        "license": "Nature copyright; no open derivative license verified.",
    },
    "sonnen-2018": {
        "source_url": "https://pmc-oa-opendata.s3.amazonaws.com/PMC5847172.1/mmc3.mp4",
        "license": "CC BY-NC-ND 4.0 (article/source repository); local research derivation, no publication license inferred.",
    },
}


def decode(path):
    with av.open(str(path)) as container:
        return [frame.to_ndarray(format="rgb24") for frame in container.decode(video=0)]


def feature(rgb):
    # Exclude burned-in time/scale labels. The high-pass/windowed grayscale
    # texture is used ONLY for motion estimation; sampled values are unchanged.
    a = np.asarray(
        Image.fromarray(rgb)
        .convert("L")
        .filter(ImageFilter.GaussianBlur(2))
        .resize((rgb.shape[1] // 2, rgb.shape[0] // 2)),
        dtype=float,
    )
    a = a[30:-45, 30:-30]
    a = a - np.asarray(
        Image.fromarray(a.astype("uint8")).filter(ImageFilter.GaussianBlur(6))
    )
    return a * np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))


def displacement(a, b):
    cross = np.fft.fft2(b) * np.conj(np.fft.fft2(a))
    corr = np.fft.fftshift(np.fft.ifft2(cross / (np.abs(cross) + 1e-9)).real)
    cy, cx = np.array(corr.shape) // 2
    y, x = np.unravel_index(np.argmax(corr[cy - 6 : cy + 7, cx - 6 : cx + 7]), (13, 13))
    y += cy - 6
    x += cx - 6

    def sub(v0, v1, v2):
        den = v0 - 2 * v1 + v2
        return 0.5 * (v0 - v2) / den if den else 0

    return (
        np.array(
            [
                x - cx + sub(corr[y, x - 1], corr[y, x], corr[y, x + 1]),
                y - cy + sub(corr[y - 1, x], corr[y, x], corr[y + 1, x]),
            ]
        )
        * 2
    )


def extract(frames, refs, start, end, width):
    assert len(frames) == len(refs)
    features = [feature(f) for f in refs]
    increments = np.array(
        [np.zeros(2)]
        + [displacement(a, b) for a, b in zip(features[:-1], features[1:])]
    )
    assert np.max(abs(increments)) < 11, (
        "Registration hit search bound; review manually."
    )
    shifts = np.cumsum(increments, axis=0)
    vector = np.array(end) - start
    length = np.linalg.norm(vector)
    n = int(length) + 1
    base = np.linspace(start, end, n)
    normal = np.array([-vector[1], vector[0]]) / length
    coord = (
        base[:, None, :]
        + np.arange(-(width // 2), width // 2 + 1)[None, :, None] * normal
    )
    cols = []
    for f, shift in zip(frames, shifts):
        xy = coord + shift
        x, y = xy[..., 0], xy[..., 1]
        assert (
            x.min() >= 0
            and y.min() >= 0
            and x.max() < f.shape[1] - 1
            and y.max() < f.shape[0] - 1
        )
        x0 = x.astype(int)
        y0 = y.astype(int)
        u = x - x0
        v = y - y0
        # Lauschke green channel; Sonnen grayscale channels are equivalent up
        # to video encoding. Preserve decoded green display values in both.
        g = f[:, :, 1].astype(float)
        values = (
            (1 - u) * (1 - v) * g[y0, x0]
            + u * (1 - v) * g[y0, x0 + 1]
            + (1 - u) * v * g[y0 + 1, x0]
            + u * v * g[y0 + 1, x0 + 1]
        )
        cols.append(values.mean(axis=1))
    return np.stack(cols, axis=1), shifts, increments, length


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True, type=Path)
    args = parser.parse_args()
    src = args.source_dir
    settings = [
        dict(
            id="lauschke-2013",
            movie=src / "lauschke/video5.mov",
            reference=src / "lauschke/video4.mov",
            start=[420, 350],
            end=[420, 660],
            width=20,
            bar_px=105,
            bar_endpoints=[[27, 694], [132, 694]],
            bar_um=100,
            channel="LuVeLu / decoded green display channel",
            file_id="video5",
        ),
        dict(
            id="sonnen-2018",
            movie=src / "mammal/sonnen-mmc3.mp4",
            reference=None,
            start=[520, 480],
            end=[260, 240],
            width=40,
            bar_px=139,
            bar_endpoints=[[823, 20], [962, 20]],
            bar_um=100,
            channel="Axin2T2A / decoded grayscale display channel",
            file_id="movie-s2",
        ),
    ]
    # A numerical sign check prevents inverse registration coordinates.
    rng = np.random.default_rng(7)
    a = rng.normal(size=(64, 64))
    b = np.roll(np.roll(a, 2, 0), -3, 1)
    assert np.allclose(displacement(a, b), [-6, 4], atol=0.01)
    for s in settings:
        if s["id"] == "lauschke-2013":
            from extract_lauschke_radial import run

            run(s["movie"], s["reference"])
            continue
        frames = decode(s["movie"])
        refs = decode(s["reference"]) if s["reference"] else frames
        mat, shifts, inc, length = extract(
            frames, refs, s["start"], s["end"], s["width"]
        )
        assert np.isfinite(mat).all() and mat.min() >= 0 and mat.max() <= 255
        out = ROOT / "data/derived" / s["id"]
        out.mkdir(parents=True, exist_ok=True)
        figs = ROOT / "figures" / s["id"]
        figs.mkdir(parents=True, exist_ok=True)
        if s["id"] == "sonnen-2018":
            import csv

            entries = list(
                csv.DictReader((src / "mammal/sonnen-s2-frame-times.csv").open())
            )
            times = np.array([float(r["time_hours"]) for r in entries])
            basis = "All 155 burned-in timestamps read by local OCR and spot-checked visually; 0.01 h display precision."
            assert len(times) == len(frames) and np.all(np.diff(times) > 0)
        else:
            times = np.arange(len(frames)) / 6
            basis = "10 min acquisition interval, verified against burned-in timestamps at frames 0,1,2,15,30,45,60 (0 to 10 h); not playback FPS."
        position = np.linspace(0, length * s["bar_um"] / s["bar_px"], mat.shape[0])
        np.savez_compressed(
            out / (s["file_id"] + "-kymograph.npz"),
            intensity=mat,
            time_h=times,
            position_um=position,
            shifts_xy=shifts,
            increments_xy=inc,
        )
        np.savetxt(
            out / (s["file_id"] + "-intensity.csv"), mat, delimiter=",", fmt="%.7g"
        )
        np.savetxt(
            out / (s["file_id"] + "-time-h.csv"),
            times,
            delimiter=",",
            header="time_h",
            comments="",
        )
        np.savetxt(
            out / (s["file_id"] + "-position-um.csv"),
            position,
            delimiter=",",
            header="position_um",
            comments="",
        )
        sheet = Image.new(
            "RGB", (3 * frames[0].shape[1], frames[0].shape[0] + 30), "white"
        )
        for j, i in enumerate([0, len(frames) // 2, len(frames) - 1]):
            im = Image.fromarray(frames[i])
            draw = ImageDraw.Draw(im)
            a = np.array(s["start"]) + shifts[i]
            b = np.array(s["end"]) + shifts[i]
            vec = b - a
            normal = np.array([-vec[1], vec[0]]) / np.linalg.norm(vec) * s["width"] / 2
            draw.polygon(
                [
                    tuple(a + normal),
                    tuple(b + normal),
                    tuple(b - normal),
                    tuple(a - normal),
                ],
                outline=(255, 160, 0),
                width=2,
            )
            draw.line([tuple(a), tuple(b)], fill=(255, 80, 50), width=3)
            draw.ellipse(
                [a[0] - 7, a[1] - 7, a[0] + 7, a[1] + 7], outline=(255, 220, 0), width=3
            )
            sheet.paste(im, (j * im.width, 30))
            ImageDraw.Draw(sheet).text(
                (j * im.width + 10, 7),
                f"frame {i} | t={times[i]:.2f} h | translation={shifts[i].round(2)} px",
                fill="black",
            )
        sheet.save(figs / (s["file_id"] + "-roi.jpg"))
        trace = {
            "paper_id": s["id"],
            "channel": s["channel"],
            "source_movie_sha256": hashlib.sha256(s["movie"].read_bytes()).hexdigest(),
            "reference_movie_sha256": hashlib.sha256(
                s["reference"].read_bytes()
            ).hexdigest()
            if s["reference"]
            else None,
            "source_movie_filename": s["movie"].name,
            "shape_space_time": list(mat.shape),
            "time_basis": basis,
            "time_range_h": [float(times[0]), float(times[-1])],
            "time_array": "./" + s["file_id"] + "-time-h.csv",
            "scale_bar": {
                "length_um": s["bar_um"],
                "length_video_px": s["bar_px"],
                "endpoints_xy": s["bar_endpoints"],
                "measurement_precision_px": 1,
            },
            "pixel_scale_um": s["bar_um"] / s["bar_px"],
            "spatial_reference": "distance from ROI start, toward explant periphery; not anatomical AP registration",
            "roi": {
                "start_xy": s["start"],
                "end_xy": s["end"],
                "width_px": s["width"],
                "perpendicular_samples": s["width"] + 1,
            },
            "registration": {
                "method": "adjacent-frame phase correlation, cumulative translation only",
                "reference": "matched brightfield Movie4"
                if s["reference"]
                else "same grayscale movie",
                "max_step_px": float(np.max(abs(inc))),
                "max_cumulative_xy_px": shifts.min(axis=0).tolist()
                + shifts.max(axis=0).tolist(),
                "feature_preprocessing": "grayscale; Gaussian2; half-size; crop borders; subtract Gaussian6; Hanning window; search ±6 half-resolution px; quadratic subpixel peak",
            },
            "sampling": "bilinear samples of original decoded channel, mean over width; no temporal filtering, detrending, phase inference, or intensity correction",
            "display_value_range": [float(mat.min()), float(mat.max())],
            "data_level": "derived from compressed 8-bit rendered supplement; not raw fluorescence",
            "limitations": [
                "Translations reduce drift but do not correct rotation, growth or tissue deformation.",
                "ROI is an exploratory choice; it is not claimed to reproduce the published kymograph.",
                "Video LUT, clipping, gamma, compression and projection are not reversed.",
                "No valid-tissue mask; use for qualitative waveform comparison, not amplitude fitting.",
                "Spatial calibration is measured from rendered scale bar, not inherited from raw camera pixels.",
            ],
            "script": "extract_video_kymographs.py",
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "libraries": {"numpy": np.__version__, "av": av.__version__},
        }
        trace.update(SOURCE_METADATA[s["id"]])
        (out / "extraction-provenance.json").write_text(
            json.dumps(trace, ensure_ascii=False, indent=2) + "\n"
        )
        print(
            s["id"],
            mat.shape,
            "t=",
            times[-1],
            "position_um=",
            position[-1],
            flush=True,
        )


if __name__ == "__main__":
    main()

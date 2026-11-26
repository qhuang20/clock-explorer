# SPDX-License-Identifier: MIT
"""DISPLAY-COLOUR-INDEX approximation of early HES7-dominant Movie 2.

Not raw fluorescence. Fixed horizontal Eulerian strip; no tissue warping,
temporal smoothing, detrending or imputation. Frames 0..51 precede 64 h, when
the paper reports widespread MESP2 activation. Earlier MESP2 mixing cannot
be excluded. Residual masks remain auditable. Put movie2.mp4 and the LUT in
data/derived/miao-2023/; dependencies are in analysis/requirements.txt.
"""

from paths import ASSET_ROOT
import hashlib, json, os

os.environ.setdefault("MPLCONFIGDIR", str(ASSET_ROOT / "mpl-cache"))
import av
import numpy as np
from PIL import Image, ImageDraw
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

P = ASSET_ROOT / "data/derived/miao-2023"
N = 52
X0, Y0, X1, Y1 = 380, 320, 900, 360
THRESHOLD = 30.0


def invert(rgb, lut):
    a = rgb.reshape(-1, 3).astype(np.float32)
    index = np.empty(len(a), np.uint8)
    error = np.empty(len(a), np.float32)
    for start in range(0, len(a), 8192):
        z = a[start : start + 8192]
        d = ((z[:, None, :] - lut[None, :, :]) ** 2).sum(2)
        k = d.argmin(1)
        index[start : start + len(z)] = k
        error[start : start + len(z)] = np.sqrt(d[np.arange(len(z)), k])
    return index.reshape(rgb.shape[:2]), error.reshape(rgb.shape[:2])


def scale_bar_length(rgb):
    # Visible 200-um bar, excluding text below it. Bright contiguous pixels.
    patch = rgb[665:680, 880:1030].min(axis=2) > 240
    runs = []
    for row in patch:
        a = np.r_[False, row, False].astype(int)
        starts = np.where(np.diff(a) == 1)[0]
        ends = np.where(np.diff(a) == -1)[0]
        runs.extend((ends - starts).tolist())
    return max(runs)


def main():
    assert (
        hashlib.sha256((P / "movie2.mp4").read_bytes()).hexdigest()
        == "6689c3c9d6ffc22b935d4046d19d7b26e832c9b267b3a6ea96f90e7530f342d3"
    )
    assert (
        hashlib.sha256((P / "green-fire-blue.lut").read_bytes()).hexdigest()
        == "01f17d9e55cd3bf2f2e8af1bf4261ea392d88ed0316a5acb9375a44c21ea0f3e"
    )
    lut = (
        np.frombuffer((P / "green-fire-blue.lut").read_bytes(), np.uint8)
        .reshape(3, 256)
        .T.astype(np.float32)
    )
    raw = []
    residual = []
    badmasks = []
    counts = []
    bars = []
    sheets = []
    foreground_errors = []
    for i, f in enumerate(av.open(str(P / "movie2.mp4")).decode(video=0)):
        if i == N:
            break
        rgb = f.to_ndarray(format="rgb24")
        crop = rgb[Y0:Y1, X0:X1]
        index, error = invert(crop, lut)
        bad = error > THRESHOLD
        raw.append(index)
        residual.append(error.astype(np.float16))
        badmasks.append(bad)
        counts.append((~bad).sum(0))
        bars.append(scale_bar_length(rgb))
        foreground_errors.extend(error[crop.max(2) > 30].tolist())
        if i in [0, 10, 20, 30, 40, 51]:
            im = Image.fromarray(rgb)
            d = ImageDraw.Draw(im)
            d.rectangle((X0, Y0, X1 - 1, Y1 - 1), outline="cyan", width=3)
            d.line((640, Y0, 640, Y1 - 1), fill="white", width=2)
            d.rectangle((903, 671, 1017, 675), outline="yellow", width=1)
            ar = np.array(im)
            cc = ar[Y0:Y1, X0:X1]
            cc[bad] = [255, 60, 60]
            im = Image.fromarray(ar)
            im.thumbnail((768, 432))
            sheets.append((i, im))
    # Video compression moves thresholded endpoints by up to two pixels.
    assert len(raw) == N and np.median(bars) == 115 and min(bars) >= 113, bars
    raw = np.array(raw)
    badmasks = np.array(badmasks)
    counts = np.array(counts)
    values = np.where(badmasks, np.nan, raw.astype(np.float32))
    # A column must retain at least half of its 40 input pixels.
    with np.errstate(invalid="ignore"):
        intensity = np.nanmean(values, axis=1).T
    intensity[counts.T < 20] = np.nan
    unmasked = raw.mean(axis=1).T
    times = 50.5 + np.arange(N) * 15.78 / 60
    positions = (np.arange(X0, X1) - 640) * 200 / 115
    np.savez_compressed(
        P / "kymograph.npz",
        intensity=intensity,
        intensity_all_lut_pixels=unmasked,
        time_h=times,
        position_um=positions,
        accepted_pixel_count=counts.T,
        frame_index=np.arange(N),
        position_unit=np.array(
            "micrometre relative to video x=640; approximate bar calibration"
        ),
        intensity_unit=np.array(
            "approximate ImageJ Green Fire Blue display-colour index (0..255)"
        ),
    )
    np.savez_compressed(
        P / "pixel-quality.npz",
        residual_rgb=np.array(residual),
        high_residual_mask=badmasks,
        lut_index=raw,
        crop_xyxy=np.array([X0, Y0, X1, Y1]),
        threshold_rgb_euclidean=np.array(THRESHOLD),
        scale_bar_length_px=np.array(bars),
    )
    sheet = Image.new("RGB", (768, len(sheets) * 455), "white")
    d = ImageDraw.Draw(sheet)
    for j, (i, im) in enumerate(sheets):
        d.text(
            (8, j * 455 + 4),
            f"Frame {i}; {times[i]:.3f} h; cyan: fixed strip; red: rejected colour pixels",
            fill="black",
        )
        sheet.paste(im, (0, j * 455 + 23))
    sheet.save(P / "roi-overlay.png")
    err = np.array(foreground_errors)
    qc = {
        "n_frames": N,
        "shape_space_time": list(intensity.shape),
        "time_range_h": [float(times[0]), float(times[-1])],
        "scale_bar_px": 115,
        "observed_scale_bar_px_range": [min(bars), max(bars)],
        "scale_bar_um": 200,
        "um_per_video_px": 200 / 115,
        "foreground_lut_rgb_error_percentiles_50_90_95_99": np.percentile(
            err, [50, 90, 95, 99]
        ).tolist(),
        "fraction_foreground_pixels_rejected": float((err > THRESHOLD).mean()),
        "fraction_kymograph_cells_nan": float(np.isnan(intensity).mean()),
        "masked_vs_all_mean_absolute_index_difference": float(
            np.nanmean(abs(intensity - unmasked))
        ),
    }
    (P / "extraction-qc.json").write_text(json.dumps(qc, indent=2))
    fig, ax = plt.subplots(figsize=(8, 4.8), layout="constrained")
    im = ax.imshow(
        intensity,
        origin="lower",
        aspect="auto",
        interpolation="nearest",
        extent=[times[0], times[-1], positions[0], positions[-1]],
        cmap="OrRd",
        vmin=0,
        vmax=255,
    )
    ax.set(
        xlabel="Time after differentiation start (h)",
        ylabel="Horizontal image position (um)",
        title="Miao 2023 | early Movie 2 | display-colour approximation",
    )
    fig.colorbar(im, ax=ax, label="Relative colour index (not raw fluorescence)")
    fig.savefig(P / "kymograph-preview.png", dpi=160)
    plt.close(fig)
    print(json.dumps(qc, indent=2))


if __name__ == "__main__":
    main()

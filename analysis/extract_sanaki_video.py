# SPDX-License-Identifier: MIT
"""Reproduce a DISPLAY-COLOUR-INDEX kymograph, not raw luminescence.

Run with the dependencies in analysis/requirements.txt. Inputs are the public
Supplementary Movie 4 and ImageJ Fire LUT in data/derived/sanaki-2022/.
Only frames 0..98 (00:00..16:20 on day 4) are used. All operations are local.
No temporal smoothing, detrending, interpolation, or missing-value filling.
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

P = ASSET_ROOT / "data/derived/sanaki-2022"
N = 99
THRESHOLD = 30.0  # Euclidean error in 8-bit RGB; keep error/mask for auditing.
X0, Y0, X1, Y1 = 120, 90, 331, 331


def invert(rgb, lut):
    a = rgb.reshape(-1, 3).astype(np.float32)
    idx = np.empty(len(a), np.uint8)
    err = np.empty(len(a), np.float32)
    # Bounded chunks prevent a full-frame by 256 by RGB allocation.
    for start in range(0, len(a), 8192):
        chunk = a[start : start + 8192]
        d2 = ((chunk[:, None, :] - lut[None, :, :]) ** 2).sum(axis=2)
        k = d2.argmin(axis=1)
        idx[start : start + len(chunk)] = k
        err[start : start + len(chunk)] = np.sqrt(d2[np.arange(len(chunk)), k])
    return idx.reshape(rgb.shape[:2]), err.reshape(rgb.shape[:2])


def main():
    assert (
        hashlib.sha256((P / "movie4.mp4").read_bytes()).hexdigest()
        == "852915ad75bb83a1504914932f0467dd53a0f5fdfd4e50baeafa297961599add"
    )
    assert (
        hashlib.sha256((P / "fire.lut").read_bytes()).hexdigest()
        == "ecbe72a19eef021e68479107a74d629d88bee5b6a0253f9a29eed3324f17773f"
    )
    lut = (
        np.frombuffer((P / "fire.lut").read_bytes(), np.uint8)
        .reshape(3, 256)
        .T.astype(np.float32)
    )
    yy, xx = np.mgrid[Y0:Y1, X0:X1]
    intensity = np.full((120, N), np.nan, np.float32)
    unmasked = intensity.copy()
    counts = np.zeros((120, N), np.int32)
    residual, bad_masks, tissue_masks, centers, axes = [], [], [], [], []
    sheets = []
    lut_errors = []
    for i, f in enumerate(av.open(str(P / "movie4.mp4")).decode(video=0)):
        if i == N:
            break
        rgb = f.to_ndarray(format="rgb24")
        # Segmentation uses the simultaneous bright-field panel, independently
        # of oscillating reporter brightness. Excludes timestamp and borders.
        bf = rgb[Y0:Y1, X0:X1].astype(float).mean(axis=2)
        tissue = bf < 160
        pts = np.column_stack([xx[tissue], yy[tissue]])
        center = pts.mean(axis=0)
        axis = np.linalg.eigh(np.cov(pts.T))[1][:, -1]
        if axis[1] > 0:
            axis = -axis
        # Negative to positive goes bottom-left to top-right. This is an
        # approximate longitudinal projection, not a curved material midline.
        projected = (xx - center[0]) * axis[0] + (yy - center[1]) * axis[1]
        bins = np.floor((projected + 120) / 2).astype(int)
        rep = rgb[Y0:Y1, X0 + 972 : X1 + 972]  # third, reporter-only panel
        index, error = invert(rep, lut)
        bad = error > THRESHOLD
        for b in range(120):
            members = tissue & (bins == b)
            accepted = members & ~bad
            counts[b, i] = accepted.sum()
            if accepted.sum() >= 3:
                intensity[b, i] = index[accepted].mean()
            if members.sum() >= 3:
                unmasked[b, i] = index[members].mean()
        residual.append(error.astype(np.float16))
        bad_masks.append(bad)
        tissue_masks.append(tissue)
        centers.append(center)
        axes.append(axis)
        lut_errors.extend(error[tissue].tolist())
        if i in [0, 16, 32, 48, 65, 80, 98]:
            im = Image.fromarray(rgb).convert("RGB")
            draw = ImageDraw.Draw(im)
            draw.rectangle((X0, Y0, X1 - 1, Y1 - 1), outline="cyan", width=2)
            # Same registered axis shown in bright-field and reporter panels.
            for shift in [0, 972]:
                c = center + [shift, 0]
                draw.line(
                    [tuple(c - 105 * axis), tuple(c + 105 * axis)], fill="cyan", width=3
                )
                draw.ellipse((c[0] - 4, c[1] - 4, c[0] + 4, c[1] + 4), fill="white")
            # Red marks pixels outside the LUT tolerance, restricted to tissue.
            ar = np.array(im)
            crop = ar[Y0:Y1, X0 + 972 : X1 + 972]
            crop[tissue & bad] = [255, 60, 60]
            im = Image.fromarray(ar)
            im.thumbnail((972, 324))
            sheets.append((i, im))
    assert len(residual) == N
    times = np.arange(N, dtype=float) / 6
    positions = np.arange(120, dtype=float) * 2 - 119
    np.savez_compressed(
        P / "kymograph.npz",
        intensity=intensity,
        intensity_all_lut_pixels=unmasked,
        time_h=times,
        position_px=positions,
        accepted_pixel_count=counts,
        frame_index=np.arange(N),
        position_unit=np.array("video pixel along bright-field major axis"),
        intensity_unit=np.array(
            "approximate ImageJ Fire display-colour index (0..255)"
        ),
    )
    np.savez_compressed(
        P / "pixel-quality.npz",
        residual_rgb=np.array(residual),
        high_residual_mask=np.array(bad_masks),
        tissue_mask=np.array(tissue_masks),
        centers_xy=np.array(centers),
        axis_vectors_xy=np.array(axes),
        crop_xyxy=np.array([X0, Y0, X1, Y1]),
        reporter_panel_x_offset=np.array(972),
        threshold_rgb_euclidean=np.array(THRESHOLD),
    )
    sheet = Image.new("RGB", (972, len(sheets) * 350), "white")
    d = ImageDraw.Draw(sheet)
    for j, (i, im) in enumerate(sheets):
        d.text(
            (8, j * 350 + 5),
            f"Frame {i}; {i / 6:.3f} h after day-4 start; cyan: axis; red: rejected colour pixels",
            fill="black",
        )
        sheet.paste(im, (0, j * 350 + 26))
    sheet.save(P / "roi-overlay.png")
    err = np.array(lut_errors)
    qc = {
        "n_frames": N,
        "shape_space_time": list(intensity.shape),
        "time_range_h": [float(times[0]), float(times[-1])],
        "lut_rgb_error_percentiles_50_90_95_99": np.percentile(
            err, [50, 90, 95, 99]
        ).tolist(),
        "fraction_tissue_pixels_rejected": float((err > THRESHOLD).mean()),
        "fraction_kymograph_cells_nan": float(np.isnan(intensity).mean()),
        "centroid_first_last_xy": [centers[0].tolist(), centers[-1].tolist()],
        "axis_first_last_xy": [axes[0].tolist(), axes[-1].tolist()],
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
        xlabel="Time after day-4 imaging start (h)",
        ylabel="Registered longitudinal position (video px)",
        title="Sanaki-Matsumiya 2022 | Movie 4 | display-colour approximation",
    )
    fig.colorbar(im, ax=ax, label="Relative colour index (not raw luminescence)")
    fig.savefig(P / "kymograph-preview.png", dpi=160)
    plt.close(fig)
    print(json.dumps(qc, indent=2))


if __name__ == "__main__":
    main()

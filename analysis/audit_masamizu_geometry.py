# SPDX-License-Identifier: MIT
"""Audit the first card's existing fixed ROI without changing scientific assets.

The axial route is an evidence-reviewed case decision, not an automated classifier.
This script verifies the source, reproduces the old image-coordinate measurement,
and renders every source frame for anatomical/registration review.
"""

import argparse
import hashlib
import json
from pathlib import Path

import av
import numpy as np

from paths import ASSET_ROOT, REPO_ROOT

EXPECTED_SOURCE = "455cdd3e3049351a064879e09ebcfa8ebd8be73d3d357eeb12bd42490465ce92"
ARTICLE = "https://pmc.ncbi.nlm.nih.gov/articles/PMC1345707/"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(source, matrix, provenance_path, output):
    source_hash = digest(source)
    if source_hash != EXPECTED_SOURCE:
        raise ValueError("This reviewed case requires the exact Masamizu Movie 2")
    original_hash = digest(matrix)
    provenance = json.loads(provenance_path.read_text())
    with av.open(str(source)) as container:
        frames = np.stack(
            [f.to_ndarray(format="rgb24") for f in container.decode(video=0)]
        )
    if frames.shape != (45, 256, 256, 3):
        raise ValueError(f"Unexpected source dimensions: {frames.shape}")
    if not (
        np.array_equal(frames[..., 0], frames[..., 1])
        and np.array_equal(frames[..., 0], frames[..., 2])
    ):
        raise ValueError(
            "The reviewed grayscale measurement does not cover a mixed RGB source"
        )
    gray = frames[..., 0]
    roi = provenance["roi"]
    x0, x1 = roi["x_start"], roi["x_stop_exclusive"]
    y0, y1 = roi["y_start"], roi["y_stop_exclusive"]
    raw = gray[:, y0:y1, x0:x1].mean(axis=2).T
    with np.load(matrix, allow_pickle=False) as saved:
        np.testing.assert_array_equal(raw, saved["intensity_8bit"])
        np.testing.assert_array_equal(np.arange(45), saved["frame_index"])
        np.testing.assert_array_equal(np.arange(y0, y1), saved["image_y_px"])
        relative = (raw - raw.min()) / (raw.max() - raw.min())
        np.testing.assert_allclose(
            relative, saved["relative_intensity"], rtol=0, atol=1e-15
        )
    assert provenance["source_movie_sha256"] == source_hash
    assert digest(matrix) == original_hash
    output.mkdir(parents=True, exist_ok=True)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    fig, axes = plt.subplots(5, 9, figsize=(13.5, 8.3))
    for i, ax in enumerate(axes.flat):
        ax.imshow(gray[i], cmap="gray", vmin=0, vmax=255)
        ax.add_patch(
            Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, color="#f59b42", lw=0.7)
        )
        ax.set_title(f"Frame {i}", fontsize=8, pad=3)
        ax.set_axis_off()
    fig.suptitle(
        "Masamizu 2006 · all 45 frames of Movie 2",
        x=0.035,
        ha="left",
        fontsize=15,
        weight="bold",
        y=0.985,
    )
    fig.text(
        0.035,
        0.055,
        "Orange: existing fixed strip, x=[60,95), y=[50,210) px · original 8-bit grayscale display",
        fontsize=9,
        color="#535d6b",
    )
    fig.text(
        0.035,
        0.025,
        "Axial workflow selected from the preparation and paper; no P/A landmarks or anatomical registration inferred here.",
        fontsize=9,
        color="#535d6b",
    )
    fig.subplots_adjust(
        left=0.025, right=0.985, top=0.925, bottom=0.105, hspace=0.26, wspace=0.10
    )
    fig.savefig(output / "movie2-all-frames.png", dpi=180)
    plt.close(fig)
    report = {
        "paper_id": "masamizu-2006",
        "review_date": "2026-11-15",
        "scope": "first-card method selection and reference audit; no new AP-registered extraction",
        "source_sha256": source_hash,
        "source_shape_time_y_x_rgb": list(frames.shape),
        "grayscale_channels_identical": True,
        "reference_matrix_sha256": original_hash,
        "reference_reproduced_from_all_source_frames": True,
        "reference_matrix_preserved": digest(matrix) == original_hash,
        "reference_shape_space_time": list(raw.shape),
        "reference_roi_image_px": roi,
        "reference_intensity_range": [float(raw.min()), float(raw.max())],
        "method_selection": {
            "selected_skill": "kymograph-axial",
            "basis": "E10.5 caudal embryo/PSM explant; article and Fig. 3 describe caudal-to-S0 progression",
            "radial_not_selected": "No supporting center-to-periphery preparation or reviewed concentric-front geometry in this movie",
            "biological_route_confidence": "supported by article preparation and Fig. 3 caption",
            "anatomical_view": "unverified; do not equate the axial route with dorsal/lateral/ventral view",
            "existing_extraction": "fixed image-coordinate strip, not anatomically registered",
            "execution_readiness": "qualitative fixed-strip reference verified; anatomical landmark/motion review pending",
        },
        "calibration": {
            "exposure_min": 20,
            "frame_interval_min": None,
            "um_per_pixel": None,
            "axes_retained": ["frame index", "image y (px)"],
        },
        "evidence": [
            {
                "url": ARTICLE,
                "section": "Results and Fig. 3 caption",
                "supports": "preparation, Movie 2 identity and caudal-to-S0 progression",
            },
            {
                "url": ARTICLE,
                "section": "Bioluminescence Imaging of the PSM",
                "supports": "37 C, 4x4 binning and 20 min exposure; not an independently verified frame interval",
            },
        ],
        "review_findings": [
            "Original movie is a grayscale display export; rawvideo encoding does not establish raw camera data.",
            "A fixed strip includes changing tissue position and shape; diagonal bands alone do not establish wave speed.",
            "No tissue segmentation, structural motion correction or background subtraction is present in the reference.",
            "Bright peaks or intensity COM must not be used as a silently substituted posterior landmark.",
            "P/A correspondence in source pixels, a motion rule and usable tissue extent must be reviewed before new anatomical extraction.",
        ],
        "source_access_limits": "Current direct PMC and legacy university PDF fetches did not provide readable figure files; article text/caption available through indexed primary-source retrieval. No exact Fig. 3-to-movie feature registration is claimed.",
        "next_review": [
            "obtain/review labeled Figure 3 or matched structural frames",
            "map S0/anterior and posterior-side landmarks over representative movie frames",
            "choose one PSM-side path and tissue extent",
            "compare new ROI with fixed-strip reference under shared controls",
        ],
        "script": "analysis/audit_masamizu_geometry.py",
        "script_sha256": digest(Path(__file__)),
    }
    (output / "review.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "selected_skill": "kymograph-axial",
                "reference_reproduced": True,
                "shape": list(raw.shape),
                "reference_preserved": True,
                "output": str(output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-movie",
        type=Path,
        default=ASSET_ROOT
        / "data/source-archive/masamizu-2006/pnas_0508658103_08658Movie2.mov",
    )
    parser.add_argument(
        "--matrix",
        type=Path,
        default=ASSET_ROOT / "data/derived/masamizu-2006/kymograph.npz",
    )
    parser.add_argument(
        "--provenance",
        type=Path,
        default=ASSET_ROOT / "data/derived/masamizu-2006/provenance.json",
    )
    parser.add_argument(
        "--output", type=Path, default=REPO_ROOT / "outputs/masamizu-geometry-review"
    )
    args = parser.parse_args()
    run(args.source_movie, args.matrix, args.provenance, args.output)

# SPDX-License-Identifier: MIT
# coding: utf-8
"""Re-render a verified experimental kymograph pair. No network or image synthesis.

Run from any directory: python render_kymograph.py
Dependencies are recorded in analysis/requirements.txt. The existing TIFF values,
orientation and entire recorded window are retained. Only colors/layout change.
"""

from paths import ASSET_ROOT
from pathlib import Path
import hashlib
import json
import os

ROOT = ASSET_ROOT
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".plot-cache"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import numpy as np
import tifffile

DATA = ROOT / "data/samples/chhabra-2026"
OUT = ROOT / "figures/chhabra-2026"
OUT.mkdir(parents=True, exist_ok=True)
meta = json.loads((DATA / "validation.json").read_text())
arrays = []
for entry in meta["files"]:
    path = DATA / entry["local_file"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    arr = tifffile.imread(path)
    assert list(arr.shape) == entry["shape_space_time"]
    assert np.isfinite(arr).all()
    arrays.append(arr)
intensity, phase = arrays
assert intensity.dtype == np.uint16 and phase.dtype == np.float32
assert intensity.shape == phase.shape
assert np.max(np.abs(phase)) <= np.pi + 1e-6
ny, nt = intensity.shape
dt_h, dx = meta["time_step_min"] / 60, meta["space_step_um"]
# Half-sample edges keep each recorded value at its correct time / space center.
# y increases downwards, matching the source array and the publication convention.
extent = [-dt_h / 2, (nt - 0.5) * dt_h, (ny - 0.5) * dx, -dx / 2]

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 9,
        "axes.titlesize": 11,
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "axes.edgecolor": "#9198a6",
        "axes.linewidth": 0.6,
        "text.color": "#252936",
        "axes.labelcolor": "#525b6b",
        "xtick.color": "#697386",
        "ytick.color": "#697386",
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "figure.dpi": 150,
        "savefig.dpi": 300,
    }
)
norm_i = Normalize(float(intensity.min()), float(intensity.max()))
norm_p = Normalize(-np.pi, np.pi)
specs = [
    ("intensity", intensity, "Her7 intensity", "OrRd", norm_i, "Intensity (a.u.)"),
    ("phase", phase, "Derived phase", "twilight_shifted", norm_p, "Phase (rad)"),
]


def panel(fig, ax, spec):
    key, arr, title, cmap, norm, label = spec
    im = ax.imshow(
        arr,
        origin="upper",
        extent=extent,
        aspect="auto",
        cmap=cmap,
        norm=norm,
        interpolation="nearest",
        rasterized=True,
    )
    ax.set(title=title, xlabel="Time (h)", ylabel="Position (µm)")
    ax.set_xticks([0, 5, 10, 15])
    ax.set_yticks([0, 100, 200, 300])
    ax.title.set_position((0, 1.025))
    ax.title.set_horizontalalignment("left")
    bar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.045, aspect=24)
    bar.outline.set_visible(False)
    bar.set_label(label, labelpad=7)
    if key == "phase":
        bar.set_ticks([-np.pi, 0, np.pi], labels=["−π", "0", "π"])
    else:
        bar.set_ticks([10000, 20000, 30000], labels=["10k", "20k", "30k"])
    return im


def save(fig, name):
    for fmt in ["png", "svg", "pdf"]:
        fig.savefig(
            OUT / (name + "." + fmt),
            dpi=300,
            metadata={"Creator": "Clock Explorer / Matplotlib"}
            if fmt != "png"
            else None,
        )
    plt.close(fig)


fig, axes = plt.subplots(1, 2, figsize=(10, 4.9))
fig.subplots_adjust(left=0.075, right=0.955, bottom=0.22, top=0.79, wspace=0.42)
for ax, spec in zip(axes, specs):
    panel(fig, ax, spec)
fig.text(0.075, 0.93, "Her7–mVenus  /  27°C", fontsize=17, fontweight=600)
fig.text(
    0.075, 0.87, "EXPERIMENTAL DATA     ·     20200815 P1", fontsize=9, color="#737c8d"
)
fig.text(
    0.075,
    0.105,
    "10 min / frame   ·   1.38 µm / row   ·   279 × 119 samples",
    fontsize=9,
    color="#626d7f",
)
fig.text(
    0.075,
    0.060,
    "Processed data · center-of-mass registration · origin: first stored frame / row",
    fontsize=8,
    color="#737c8d",
)
fig.text(
    0.075,
    0.025,
    "Data: Chhabra et al., PNAS (2026) · DOI 10.1073/pnas.2619120123 · repository MIT license",
    fontsize=8,
    color="#737c8d",
)
save(fig, "her7-27C-pair")

for spec in specs:
    fig, ax = plt.subplots(figsize=(6.9, 4.8))
    fig.subplots_adjust(left=0.115, right=0.90, bottom=0.19, top=0.86)
    panel(fig, ax, spec)
    fig.text(
        0.115, 0.96, "27°C  ·  Her7–mVenus  ·  20200815 P1", fontsize=9, color="#737c8d"
    )
    fig.text(
        0.115,
        0.065,
        "10 min / frame  ·  1.38 µm / row  ·  processed experimental data",
        fontsize=8,
        color="#737c8d",
    )
    fig.text(
        0.115,
        0.025,
        "Origin: first stored frame / row. No additional smoothing or cropping.",
        fontsize=8,
        color="#737c8d",
    )
    save(fig, "her7-27C-" + spec[0])

caption = (
    "Figure 1. Her7–mVenus intensity and derived phase at 27°C.\n"
    "One experimental tail-explant sample (20200815 P1, batch 1) from Chhabra et al. "
    "(2026), Cycles upon cycles—Temperature scaling of medaka development, PNAS, "
    "doi:10.1073/pnas.2619120123. The public processed intensity and wavelet-derived phase "
    "TIFFs are re-rendered using the complete 279-row × 119-column arrays. "
    "Time and position are measured relative to the first stored column and row, "
    "with 10 min/frame and 1.38 µm/row from the paper Methods and repository data_settings.py. "
    "Position increases downwards; the sample uses center-of-mass registration, "
    "so row zero is not assigned an anatomical origin. Intensity uses its complete observed "
    "range (6561–33060 arbitrary units) with a sequential pale-cream-to-dark-red colormap (OrRd), with low values at the bottom and high values at the top of the colorbar. "
    "Phase uses a cyclic colormap fixed at −π to π. No extra smoothing, cropping, "
    "background subtraction, normalization, phase extraction or interpolation is applied. "
    "These are processed matrices, not raw imaging stacks; phase in low-signal pixels "
    "has not been quality-masked. This sample has not been identified as the representative "
    "sample in the published Fig. 2. It is one biological sample, not two replicates. "
    "Source repository revision: " + meta["revision"] + ". Repository license: MIT.\n"
)
(OUT / "caption.txt").write_text(caption, encoding="utf-8")
trace = {
    "source": meta["repository"],
    "revision": meta["revision"],
    "source_files": [
        {"file": f["local_file"], "sha256": f["sha256"]} for f in meta["files"]
    ],
    "script": "render_kymograph.py",
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "shape_space_time": [ny, nt],
    "dt_min": dt_h * 60,
    "dx_um": dx,
    "first_last_sample_centers": {
        "time_h": [0, (nt - 1) * dt_h],
        "position_um": [0, (ny - 1) * dx],
    },
    "pixel_edge_extent": extent,
    "orientation": "time rightwards, stored row position downwards",
    "color_limits": {
        "intensity": [float(intensity.min()), float(intensity.max())],
        "phase": [-np.pi, np.pi],
    },
    "color_maps": {
        "intensity": "OrRd (sequential; light low to dark high)",
        "phase": "twilight_shifted (cyclic)",
    },
    "extra_transformations": {
        "normalization": False,
        "clipping": False,
        "smoothing": False,
        "crop": False,
        "interpolation": "nearest",
    },
    "figure_table_trace": [
        {
            "artifact_id": "her7-27C-pair",
            "source_data": {
                "dataset_id": "20200815_P1",
                "files": [f["local_file"] for f in meta["files"]],
            },
            "transformation": {
                "script": "render_kymograph.py",
                "hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            "caption_claim": "Re-rendered processed fluorescence intensity and derived phase of one experimental sample.",
            "supported_manuscript_claims": [],
            "limitations": [
                "Processed data, not raw imaging stack",
                "No quality mask for low-signal phase",
                "Stored-coordinate origin, not anatomical origin",
                "Single sample; cannot establish population robustness",
                "Not identified as published Fig2 representative sample",
            ],
        }
    ],
    "libraries": {
        "matplotlib": matplotlib.__version__,
        "numpy": np.__version__,
        "tifffile": tifffile.__version__,
    },
}
(OUT / "render-provenance.json").write_text(
    json.dumps(trace, ensure_ascii=False, indent=2) + "\n"
)
(OUT / "include.tex").write_text(
    "\\includegraphics[width=\\textwidth]{her7-27C-pair.pdf}\n"
)
print(
    json.dumps(
        {
            "shape": [ny, nt],
            "intensity_range": [int(intensity.min()), int(intensity.max())],
            "phase_range": [float(phase.min()), float(phase.max())],
            "outputs": str(OUT),
        },
        indent=2,
    )
)

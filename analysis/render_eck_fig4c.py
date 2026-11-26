# SPDX-License-Identifier: MIT
"""Reproduce measured Fig. 4C from the author's Dorado spot and AP tables."""

import hashlib
import importlib.util
import json
from zipfile import ZipFile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

from comparison_plot import panel, save
from paths import ASSET_ROOT

KEY = "eck-2026-fig4c"
ARCHIVE = ASSET_ROOT / "data/source-archive/eck-2026"
OUTPUT = ASSET_ROOT / "data/derived" / KEY
FIGURES = ASSET_ROOT / "figures" / KEY
REVISION = "fa35f5c1b9d93ccf18d14dea558f40a6f7284f4c"
ARTICLE = "https://pmc.ncbi.nlm.nih.gov/articles/PMC13522979/#F4"
DATA_URL = "https://pmc-oa-opendata.s3.amazonaws.com/PMC10802376.2/media-8.zip"
NOTEBOOK = f"https://github.com/GarciaLab/zebrafish-ms2-paper/blob/{REVISION}/notebooks/Fig4.ipynb"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_file(name, checksum):
    path = ARCHIVE / name
    if digest(path) != checksum:
        raise ValueError(f"Unexpected content for {name}")
    return path


DISPLAY_NOTE = "Card and published comparison use 0 to 25% of the full notebook matrix peak. Higher values saturate in the display."
SIGNAL_LABEL = "Summed MS2 (1 = 25% of peak)"


def render_card_views(intensity, position, hours, peak):
    item = dict(
        matrix=intensity,
        position=position,
        time=hours,
        position_unit="µm",
        native_space_only=True,
        axis_label="AP position (µm)",
        signal_label=SIGNAL_LABEL,
        display_limits=(0, peak * 0.25),
    )
    for window in ("common", "full"):
        fig, ax = plt.subplots(figsize=(4.4, 3.8))
        fig.subplots_adjust(left=0.16, right=0.89, bottom=0.19, top=0.87)
        panel(fig, ax, item, window)
        save(
            fig,
            FIGURES / window,
            ("svg", "png", "pdf") if window == "full" else ("svg",),
        )

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.1))
    fig.subplots_adjust(left=0.09, right=0.94, bottom=0.16, top=0.87, wspace=0.50)
    old = dict(item, signal_label="Relative summed MS2 intensity")
    del old["display_limits"]
    for ax, settings, title in zip(
        axes,
        (old, item),
        ("Previous · full intensity range", "Updated · 25% of peak"),
    ):
        panel(fig, ax, settings, "full")
        ax.set_title(title)
        for y, label in ((1, "A"), (0, "P")):
            ax.text(
                -0.21,
                y,
                label,
                transform=ax.transAxes,
                va="center",
                color="#6558dc",
                weight="bold",
            )
    save(fig, FIGURES / "scale-comparison", ("png",))


def main():
    archive = verified_file(
        "preprint-data.zip",
        "66ae7d19a1608e155c211144285c1e3bf5de81151b1fcc23d7a04903a79befe9",
    )
    author_code = verified_file(
        "ap_analysis.py",
        "d97667dd619c70c906bde4d7bbabac39c85d8db5526da7efabe53bd1eec26634",
    )
    figure = verified_file(
        "fig4.webp", "15eedefb801e23392a88848b2ee519e9b990cbbf2f0dbdc9247e115ee07f875c"
    )
    spec = importlib.util.spec_from_file_location("eck_author_ap", author_code)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with ZipFile(archive) as data:

        def read(name):
            with data.open(
                "SupplementalDataFiles/Supplemental_Data_File_" + name
            ) as stream:
                return pd.read_pickle(stream)

        spots = read("1-Spots.pkl")
        scans = read("3-Non-Blank_Time_Points.pkl")
        axis = read("6-Anterior-Posterior_Axis.pkl")
    grid = np.linspace(0, 521, 100)
    measured = module.get_ap_um(spots, axis, dz=1, dyx=0.485)
    binned = module.bin_aps_um(measured, grid)
    sums = binned.groupby(["t", "binned_ap"])["gauss3d_dog"].sum()
    # Match notebook cell 11, including zeros in bins with no detected spot.
    complete = (
        sums.reindex(pd.MultiIndex.from_product([range(160), range(100)]), fill_value=0)
        .to_numpy()
        .reshape(160, 100)
    )
    # Notebook cell 27 flips horizontal order, then uses xlim(19,90), ylim(140,0).
    paper_view = np.fliplr(complete)[:140, 19:90]
    recorded = scans[:140].astype(int)
    assert recorded[0] == 0 and np.all(np.diff(recorded) > 0)
    minutes = np.arange(recorded[-1] + 1)
    position = grid[1:][10:81]
    intensity = np.full((len(position), len(minutes)), np.nan)
    intensity[:, recorded] = paper_view[:, ::-1].T
    np.testing.assert_array_equal(intensity[:, recorded].T[:, ::-1], paper_view)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        OUTPUT / "kymograph.npz",
        intensity=intensity,
        time_h=minutes / 60,
        position_um=position,
        recorded_minutes=recorded,
        notebook_matrix=complete,
    )
    render_card_views(intensity, position, minutes / 60, float(complete.max()))
    image = Image.open(figure).convert("RGB")
    # Published panel C at native resolution. Color sampling excludes ticks and the bracket.
    pixels = np.asarray(image)
    xs = (152 + (np.arange(71) + 0.5) * 631 / 71).astype(int)
    ys = (876 + (np.arange(140) + 0.5) * 594 / 140).astype(int)
    published = pixels[np.ix_(ys, xs)]
    maximum = float(complete.max()) * 0.25
    rendered = plt.get_cmap("magma")(np.clip(paper_view / maximum, 0, 1), bytes=True)[
        :, :, :3
    ]
    similarity = float(
        np.corrcoef(published[3:-10, 4:-3].ravel(), rendered[3:-10, 4:-3].ravel())[0, 1]
    )
    # Side-by-side uses the author's view, uniform spacing for recorded frames and common contrast.
    fig = plt.figure(figsize=(10, 5.6))
    left = fig.add_axes((0.012, 0.045, 0.475, 0.855))
    # Match the published heatmap's physical bounds inside the panel crop.
    right = fig.add_axes(
        (
            0.602,
            0.045 + 0.855 * (1622 - 1470) / 849,
            0.475 * 631 / 786,
            0.855 * 594 / 849,
        )
    )
    left.imshow(image.crop((0, 773, 786, 1622)), aspect="auto")
    left.axis("off")
    left.set_title("Published · Figure 4C")
    right.imshow(
        paper_view,
        aspect="auto",
        interpolation="nearest",
        cmap="magma",
        vmin=0,
        vmax=maximum,
    )
    targets = [400, 300, 200, 100]
    right.set_xticks(
        [np.argmin(abs(position[::-1] - v)) for v in targets], labels=targets
    )
    ticks = [0, 40, 80, 120]
    right.set_yticks([np.argmin(abs(recorded - v)) for v in ticks], labels=ticks)
    right.set_xlabel("AP position (µm) · P to A")
    right.set_ylabel("Experiment time (min)")
    right.set_title("Recomputed · measured her1-MS2")
    fig.suptitle("Eck et al. 2026 · Zebrafish presomitic mesoderm", fontsize=15)
    fig.savefig(FIGURES / "comparison.png", dpi=175)
    plt.close(fig)
    fig, axarr = plt.subplots(
        1, 3, figsize=(8, 3), layout="constrained", sharex=True, sharey=True
    )
    for ax, frame in zip(axarr, (0, 70, 139)):
        path = axis[axis.t == frame]
        selected = binned[(binned.t == frame) & binned.binned_ap.between(10, 80)]
        ax.plot(path.x, path.y, color="#b7bdc7", linewidth=1)
        distance = module.get_microns_between_ap_bins(path, dz=1, dyx=0.485)[0].cumsum()
        keep = (distance >= position[0]) & (distance <= position[-1])
        ax.plot(path.x[keep], path.y[keep], color="#db7227", linewidth=2)
        ax.scatter(selected.x, selected.y, color="#6855c6", s=7, alpha=0.8)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(f"{recorded[frame]} min")
    axarr[0].invert_yaxis()
    fig.savefig(FIGURES / "sampling.png", dpi=150)
    plt.close(fig)
    provenance = dict(
        article=ARTICLE,
        data_url=DATA_URL,
        author_notebook=NOTEBOOK,
        author_revision=REVISION,
        source_sha256={
            f: digest(ARCHIVE / f)
            for f in ("Fig4.ipynb", "preprint-data.zip", "ap_analysis.py", "fig4.webp")
        },
        spot_count=len(spots),
        signal="gauss3d_dog sum per acquired time and author AP bin",
        bin_grid="np.linspace(0,521,100); assign nearest of grid[1:] as in ap_analysis.py",
        caption_bin_um=6.5,
        notebook_bin_um=float(grid[1]),
        viewport="Rows [0,140), columns [19,90) after fliplr",
        acquired_time_points=len(recorded),
        elapsed_minutes=recorded.tolist(),
        dimensions=list(intensity.shape),
        position_range_um=position[[0, -1]].tolist(),
        missing_scan_policy="NaN only for unacquired minutes; zero for acquired bins with no detected spots",
        display=DISPLAY_NOTE,
        display_limits_native=[0, maximum],
        published_panel_rgb_correlation=similarity,
    )
    (OUTPUT / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(
        "Panel RGB correlation",
        similarity,
        "scan extent",
        recorded[-1],
        "spot count",
        len(spots),
    )


if __name__ == "__main__":
    main()

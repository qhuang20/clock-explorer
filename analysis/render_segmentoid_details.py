# SPDX-License-Identifier: MIT
"""Redraw the Segmentoid reporter comparisons from the stored author matrices."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from comparison_plot import edge, save
from paths import ASSET_ROOT

DATA = ASSET_ROOT / "data/derived/miao-2023-segmentoid"
FIGURES = ASSET_ROOT / "figures/miao-2023-segmentoid"


def reporter_panel(ax, sample, channel, title):
    with np.load(DATA / f"{sample}-matrices.npz") as record:
        # Saved display arrays already order the positions from posterior to anterior.
        positions = edge(record["distance_from_posterior_um"][::-1])
        times = edge(record["time_h"])
        signal = record[f"{channel}_display_normalized"]
    palette = plt.get_cmap("OrRd").copy()
    palette.set_bad("#eef0f3")
    image = ax.pcolormesh(
        times,
        positions,
        np.ma.masked_invalid(signal),
        cmap=palette,
        vmin=0,
        vmax=1,
        shading="flat",
        rasterized=True,
    )
    ax.set(
        xlim=(times[0], 45),
        ylim=(positions[0], positions[-1]),
        xlabel="Time from first frame (h)",
        ylabel="Distance from posterior (µm)",
    )
    ax.set_xticks([0, 10, 20, 30, 40, 45])
    ax.set_title(title, loc="left", pad=10)
    for label, height, align in [("A", 1, "top"), ("P", 0, "bottom")]:
        ax.text(
            -0.14,
            height,
            label,
            transform=ax.transAxes,
            va=align,
            ha="right",
            weight="bold",
            color="#6559d9",
        )
    return image


def render(filename, title, subtitle, panels, rows):
    fig, axes = plt.subplots(rows, 2, figsize=(11.7, 6.9 if rows == 1 else 10.4))
    fig.subplots_adjust(
        left=0.095,
        right=0.895,
        bottom=0.20,
        top=0.81 if rows == 1 else 0.85,
        wspace=0.36,
        hspace=0.45,
    )
    for axis, panel in zip(axes.flat, panels, strict=True):
        image = reporter_panel(axis, *panel)
    bar = fig.colorbar(
        image, cax=fig.add_axes([0.925, 0.23, 0.014, 0.54]), ticks=[0, 0.5, 1]
    )
    bar.outline.set_visible(False)
    bar.set_label("Relative signal (per panel)")
    fig.text(0.095, 0.955, title, weight="bold", fontsize=17, va="top")
    fig.text(0.095, 0.90, subtitle, color="#687284")
    fig.text(
        0.095,
        0.10,
        "Authors’ posterior alignment and 50 px spatial averaging retained. Each channel is scaled independently.",
    )
    fig.text(
        0.095,
        0.067,
        "Gray marks shared edge zeros or times outside the record. The 10 positions beyond the posterior reference are included.",
    )
    fig.text(
        0.095, 0.034, "Miao et al., Nature (2023) · doi:10.1038/s41586-022-05655-4"
    )
    save(fig, FIGURES / filename)


if __name__ == "__main__":
    render(
        "wildtype-kymographs",
        "Miao 2023 · Wild-type Segmentoid",
        "WT #1 · 150 time points · 18 min per column · Movie 8, left specimen",
        [("wt", "hu", "HES7 / UNCX"), ("wt", "mesp2", "MESP2")],
        1,
    )
    render(
        "wildtype-vs-hes7null",
        "Miao 2023 · Segmentoid comparison",
        "WT #1 (Movie 8, left) · 150 time points     HES7-null #1 (Movie 9) · 139 matrix time points",
        [
            ("wt", "hu", "WT #1 · HES7 / UNCX"),
            ("null", "hu", "HES7-null #1 · pseudoHES7 / UNCX"),
            ("wt", "mesp2", "WT #1 · MESP2"),
            ("null", "mesp2", "HES7-null #1 · MESP2"),
        ],
        2,
    )

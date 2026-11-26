# SPDX-License-Identifier: MIT
"""Plot stored space-by-time arrays in the Clock Explorer comparison style."""

import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import numpy as np

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 11,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "axes.edgecolor": "#9198a6",
        "axes.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "text.color": "#252936",
        "axes.labelcolor": "#525b6b",
        "xtick.color": "#697386",
        "ytick.color": "#697386",
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
        "axes.facecolor": "#f1f3f6",
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "savefig.dpi": 300,
    }
)


def edge(x):
    x = np.asarray(x)
    assert len(x) > 1 and np.isfinite(x).all() and np.all(np.diff(x) > 0), (
        "Axis must increase"
    )
    return np.r_[
        x[0] - (x[1] - x[0]) / 2, (x[1:] + x[:-1]) / 2, x[-1] + (x[-1] - x[-2]) / 2
    ]


def panel(fig, ax, item, window="common", normalized=True):
    a = item["matrix"]
    lo, hi = float(np.nanmin(a)), float(np.nanmax(a))
    if normalized and "display_limits" in item:
        lo, hi = item["display_limits"]
    display = np.ma.masked_invalid((a - lo) / (hi - lo) if normalized else a)
    cmap = plt.get_cmap("OrRd").copy()
    cmap.set_bad("#f1f3f6")
    mesh = ax.pcolormesh(
        edge(item["time"]),
        edge(item["position"]),
        display,
        cmap=cmap,
        norm=Normalize(0, 1) if normalized else Normalize(lo, hi),
        shading="flat",
        rasterized=True,
    )
    if window == "common":
        ax.set_xlim(0, 10)
        ax.set_xticks([0, 2, 4, 6, 8, 10])
    else:
        ax.set_xlim(float(item["time"][0]), float(item["time"][-1]))
    unit = item["position_unit"]
    if (
        window == "common"
        and normalized
        and unit == "µm"
        and not item.get("native_space_only")
    ):
        ax.set_ylim(400, 0)
        ax.set_yticks([0, 100, 200, 300, 400])
    elif item.get("show_full_position_cells"):
        bounds = edge(item["position"])
        ax.set_ylim(bounds[0], bounds[-1])
    elif item.get("position_increases_up"):
        ax.set_ylim(float(item["position"][0]), float(item["position"][-1]))
    elif window == "full" and item.get("full_space_um"):
        ax.set_ylim(*reversed(item["full_space_um"]))
    else:
        ax.set_ylim(float(item["position"][-1]), float(item["position"][0]))
    ax.set_xlabel("Time (h)")
    ax.set_ylabel(item.get("axis_label", f"Local position ({unit})"))
    bar = fig.colorbar(mesh, ax=ax, pad=0.045, fraction=0.045, aspect=25)
    bar.outline.set_visible(False)
    bar.set_label(
        item.get("signal_label", "Relative intensity")
        if normalized
        else item.get("native_label", "Video display level")
    )
    if normalized:
        bar.set_ticks([0, 0.5, 1])


def save(fig, path, formats=("svg", "png", "pdf")):
    path.parent.mkdir(parents=True, exist_ok=True)
    for fmt in formats:
        fig.savefig(str(path) + "." + fmt, dpi=300)
    plt.close(fig)

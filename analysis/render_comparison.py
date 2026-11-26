# SPDX-License-Identifier: MIT
# coding: utf-8
"""Re-render saved experimental arrays without network access.

Each COMPLETE sample is independently scaled to [0,1] before windowing.
NaNs remain missing, with no spatial/time interpolation or inferred tissue mask.
Additional samples are declared in data/additional-datasets.json.
"""

from paths import ASSET_ROOT, CATALOG_ROOT
from pathlib import Path
import hashlib, json, os, math, argparse

parser = argparse.ArgumentParser()
parser.add_argument(
    "--only",
    action="append",
    help="Only redraw this dataset’s individual panels; always rebuild combined exports",
)
selected_ids = parser.parse_args().only
ROOT = ASSET_ROOT
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".plot-cache"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from comparison_plot import edge, panel, save
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import tifffile

OUT = ROOT / "figures/comparison"
OUT.mkdir(parents=True, exist_ok=True)

previous = {
    c["id"]: c
    for c in json.loads((CATALOG_ROOT / "comparison.json").read_text())["datasets"]
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


native = ROOT / "data/samples/chhabra-2026/Kymo_20200815_P1.tif"
array = tifffile.imread(native).astype(float)
items = [
    dict(
        id="chhabra-2026",
        short="Chhabra 2026",
        reporter="Her7–mVenus",
        kind="matrix",
        label="Processed matrix",
        matrix=array,
        time=np.arange(array.shape[1]) / 6,
        position=np.arange(array.shape[0]) * 1.38,
        input=native,
        source_url="https://github.com/victoria-mochulska/cycles_upon_cycles",
        origin="First stored row",
        origin_short="Stored position",
        sample="27°C · 20200815 P1",
        position_unit="µm",
    )
]
for pid, short, reporter, name, url in [
    (
        "lauschke-2013",
        "Lauschke 2013",
        "LuVeLu",
        "video5",
        "https://www.nature.com/articles/nature11804",
    ),
    (
        "sonnen-2018",
        "Sonnen 2018",
        "Axin2T2A",
        "movie-s2",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC5847172/",
    ),
]:
    # Read the reviewed selection for both studies, including later ROI revisions.
    path = ROOT / previous[pid]["input"]
    z = np.load(path)
    items.append(
        dict(
            id=pid,
            short=short,
            reporter=reporter,
            kind="video",
            label="Video-derived ROI",
            matrix=z["intensity"],
            time=z["time_h"],
            position=z["position_um"],
            input=path,
            source_url=url,
            origin="ROI start → periphery",
            origin_short="ROI origin → outer edge",
            sample=name,
            position_unit="µm",
            roi="figures/" + pid + "/" + name + "-roi.jpg",
        )
    )
# Carry the selected coordinate and geometry metadata with each saved matrix.
for pid in ["lauschke-2013", "sonnen-2018"]:
    item = next(i for i in items if i["id"] == pid)
    for key in (
        "label",
        "axis_label",
        "signal_label",
        "origin",
        "origin_short",
        "roi",
        "roi_note",
        "geometry_version",
        "provenance",
        "position_increases_up",
        "spatial_scale_approximate",
    ):
        if key in previous[pid]:
            item[key] = previous[pid][key]

extra_file = CATALOG_ROOT / "additional-datasets.json"
for entry in json.loads(extra_file.read_text()) if extra_file.exists() else []:
    item = dict(entry)
    path = ROOT / item.pop("input")
    z = np.load(path, allow_pickle=False)
    item.update(
        matrix=z["intensity"],
        time=z["time_h"] - item.get("time_offset_h", 0),
        position=z[item.pop("position_key", "position_um")],
        input=path,
    )
    item.setdefault("position_unit", "µm")
    items.append(item)
assert len({i["id"] for i in items}) == len(items)
for item in items:
    a = item["matrix"]
    assert a.ndim == 2 and a.shape == (len(item["position"]), len(item["time"]))
    assert not np.isinf(a).any() and np.isfinite(a).any()
    assert np.nanmax(a) > np.nanmin(a)
    edge(item["time"])
    edge(item["position"])


catalog = []
for item in items:
    if selected_ids and item["id"] not in selected_ids:
        catalog.append(previous[item["id"]])
        continue
    record = {
        **previous.get(item["id"], {}),
        **{
            k: v
            for k, v in item.items()
            if k not in ["matrix", "time", "position", "input"]
        },
    }
    # Editorial card labels belong to the authored comparison catalogue, not
    # the older extraction settings used to load arrays.
    for key in (
        "system_label",
        "system_meaning",
        "reporter_note",
        "card_context",
        "card_title",
    ):
        if key in previous.get(item["id"], {}):
            record[key] = previous[item["id"]][key]
    record.update(
        input=str(item["input"].relative_to(ROOT)),
        input_sha256=sha(item["input"]),
        shape_space_time=list(item["matrix"].shape),
        time_range_h=[float(item["time"][0]), float(item["time"][-1])],
        spatial_range=[float(item["position"][0]), float(item["position"][-1])],
        missing_values=int(np.isnan(item["matrix"]).sum()),
        normalization={
            "method": "linear min-max of finite values in the complete sample",
            "min": float(np.nanmin(item["matrix"])),
            "max": float(np.nanmax(item["matrix"])),
        },
    )
    if item["position_unit"] == "µm":
        record["spatial_range_um"] = record["spatial_range"]
    for window in ["common", "full"]:
        stem = "figures/comparison/" + item["id"] + "-" + window
        record[window + "_preview"] = stem + ".svg"
        if selected_ids and item["id"] not in selected_ids:
            assert (ROOT / (stem + ".svg")).is_file()
            continue
        fig, ax = plt.subplots(figsize=(4.4, 3.8))
        fig.subplots_adjust(left=0.16, right=0.89, bottom=0.19, top=0.87)
        panel(fig, ax, item, window)
        ax.set_title(item["reporter"], loc="left", pad=12)
        fig.text(0.16, 0.035, item["label"], fontsize=8, color="#737c8d")
        stem = "figures/comparison/" + item["id"] + "-" + window
        save(fig, ROOT / stem)
        record[window + "_preview"] = stem + ".svg"
    if (
        item["kind"] == "video"
        and item["id"] in ["lauschke-2013", "sonnen-2018"]
        and (not selected_ids or item["id"] in selected_ids)
    ):
        fig, ax = plt.subplots(figsize=(6.9, 4.8))
        fig.subplots_adjust(left=0.12, right=0.90, bottom=0.19, top=0.85)
        panel(fig, ax, item, "full", False)
        ax.set_title(item["reporter"] + " / " + item["short"], loc="left", pad=15)
        fig.text(
            0.12,
            0.07,
            "Wavefront-fitted radius · compressed video · not raw fluorescence"
            if item.get("geometry_version") == "video5-dark-core-wavefront-v1"
            else "COM-registered radius · compressed video · not raw fluorescence"
            if item.get("geometry_version") == "radial-com-v1"
            else "Translation-corrected ROI · compressed video · not raw fluorescence",
            fontsize=8,
            color="#737c8d",
        )
        fig.text(
            0.12,
            0.025,
            "r = 0 at fitted geometric wavefront center; BF translation continued. Masked samples stay missing."
            if item.get("geometry_version") == "video5-dark-core-wavefront-v1"
            else "r = 0 at area-centroid proxy; increasing outward. Masked samples stay missing."
            if item.get("geometry_version") == "radial-com-v1"
            else "Spatial scale measured from movie scale bar; distance starts at the chosen ROI origin.",
            fontsize=8,
            color="#737c8d",
        )
        save(fig, ROOT / "figures" / item["id"] / "video-intensity")
    catalog.append(record)


def composite(subset, window):
    rows = math.ceil(len(subset) / 3)
    fig, axes = plt.subplots(rows, 3, figsize=(12.6, rows * 4.1 + 1.1), squeeze=False)
    fig.subplots_adjust(
        left=0.065,
        right=0.96,
        bottom=0.13 / rows,
        top=1 - 0.19 / rows,
        wspace=0.48,
        hspace=0.62,
    )
    for ax, item in zip(axes.flat, subset):
        if item is None:
            ax.set_visible(False)
            continue
        panel(fig, ax, item, window)
        ax.set_title(item["short"] + "\n" + item["reporter"], loc="left", pad=14)
    for ax in list(axes.flat)[len(subset) :]:
        ax.set_visible(False)
    fig.text(
        0.065,
        1 - 0.055 / rows,
        "Segmentation clock / experimental kymographs",
        fontsize=16,
        fontweight="bold",
    )
    fig.text(
        0.065,
        0.060 / rows,
        "0–10 h · 0–400 µm where calibrated"
        if window == "common"
        else "Complete records · native time and position ranges",
        fontsize=9,
        color="#626d7f",
    )
    fig.text(
        0.065,
        0.023 / rows,
        "Independent [0,1] normalization · local coordinate origins differ · grey: missing / unsampled · methods and sources: comparison.json",
        fontsize=8,
        color="#737c8d",
    )
    return fig


groups = [
    [i for i in items if i["kind"] != "video_lut"],
    [i for i in items if i["kind"] == "video_lut"],
]
all_slots = (
    groups[0] + [None] * ((-len(groups[0])) % 3) + groups[1] if groups[1] else items
)
for window in ["common", "full"]:
    save(composite(items[:3], window), OUT / ("three-paper-" + window))
    save(composite(all_slots, window), OUT / ("all-paper-" + window), ("svg", "png"))
    with PdfPages(OUT / ("all-paper-" + window + ".pdf")) as pdf:
        for group in groups:
            for n in range(0, len(group), 3):
                fig = composite(group[n : n + 3], window)
                pdf.savefig(fig)
                plt.close(fig)

caption = (
    "Experimental kymographs rendered from stored numerical arrays using sequential OrRd "
    "(pale cream low, dark red high). Each complete sample is independently min–max normalized "
    "before display; 0 is the sample minimum, not zero fluorescence. NaNs remain masked grey. "
    "For color-index approximations, the bar labels relative color index rather than fluorescence. "
    "Time increases rightward; read each panel’s spatial tick direction. Local origins are not anatomically "
    "equivalent across samples. The common view is 0–10 h and, for physically calibrated samples, "
    "0–400 µm; image/centered or non-micrometre axes retain their explicitly labelled native range. The full view "
    "retains each record’s full time and position span. No interpolation, detrending, clipping "
    "of intensity or phase inference is performed by this renderer. Chhabra uses the processed "
    "27°C 20200815 P1 TIFF. Lauschke uses Video5 with Video4-assisted geometry-centroid registration and a 45-degree radial strip; "
    "Sonnen uses MovieS2 with its 155 burned-in timestamps. Their 100 µm scale bars measure "
    "105 and 139 video pixels respectively. Additional dataset extraction, registration and "
    "calibration are documented in each record’s provenance. Video display values are not "
    "raw fluorescence and cannot be compared as absolute molecular concentrations. "
    "Blues remains reserved for simulated intensity; no simulation is included here.\n"
)
(OUT / "caption.txt").write_text(caption)

# Dedicated matrix renderers maintain additional individual cards.
rendered_by_id = {record["id"]: record for record in catalog}
manifest = {
    "checked": "2026-11-09",
    "color_encoding": json.loads((CATALOG_ROOT / "color-policy.json").read_text()),
    "datasets": [
        (rendered_by_id[key] if key in rendered_by_id else previous[key])
        for key in dict.fromkeys((*previous, *rendered_by_id))
    ],
    "normalization": "per-sample whole-record finite-value min-max; no percentile clipping",
    "common_window_h": [0, 10],
    "common_space_um": [0, 400],
    "full_view": "full native position and time ranges",
    "source_spatial_origins_are_not_equivalent": True,
    "script_sha256": sha(Path(__file__)),
    "exports": {
        w: {
            fmt: f"figures/comparison/all-paper-{w}.{fmt}"
            for fmt in ["pdf", "svg", "png"]
        }
        for w in ["common", "full"]
    },
    "figure_table_trace": [
        {
            "artifact_id": "all-paper-" + w,
            "source_data": [
                {"file": c["input"], "sha256": c["input_sha256"]} for c in catalog
            ],
            "transformation": {
                "script": "render_comparison.py",
                "hash": sha(Path(__file__)),
            },
            "caption_claim": "Single-sample experimental records with explicit native calibration and independent display normalization.",
            "supported_manuscript_claims": [],
            "limitations": [
                "Compressed display values are not raw fluorescence",
                "Sample registration and local origins differ",
                "No shared molecular concentration scale",
                "Single samples do not establish reproducibility",
            ],
        }
        for w in ["common", "full"]
    ],
}
(CATALOG_ROOT / "comparison.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
)
print(f"Rendered {len(items)} datasets, two windows, and paginated PDF comparisons.")

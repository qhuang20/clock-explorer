# SPDX-License-Identifier: MIT
"""Materialize two constant-temperature Her7 matrix cards from the author intensity matrices."""

import hashlib
import io
import json
from zipfile import ZipFile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from comparison_plot import panel, save
from paths import ASSET_ROOT, CATALOG_ROOT, REPO_ROOT

PAPER = "chhabra-2026"
REVISION = "c8942dd1aeeea790e2cb141662b9ef235756d2c4"
REPOSITORY = "https://github.com/victoria-mochulska/cycles_upon_cycles"
# First listed 14-somite-group P1 acquisition at each added temperature.
SAMPLES = [(22, "20210301", 10), (32, "20220428", 5)]
DX = 1.38


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def create_card(archive, temp, date, dt, polarity):
    key = f"{PAPER}-{temp}c"
    filename = f"Kymo_{date}_P1.tif"
    folder = (
        f"2026_PNAS_CyclesUponCycles_intensityPhaseKymographs/batch1_chronic_{temp}C"
    )
    suffix = f"{folder}/intensityKymo/{filename}"
    (member,) = [name for name in archive.namelist() if name.endswith("/" + suffix)]
    content = archive.read(member)
    source = f"{REPOSITORY}/blob/{REVISION}/{suffix}"
    input_path = f"data/samples/{key}/{filename}"
    source_hash = hashlib.sha256(content).hexdigest()
    dest = ASSET_ROOT / input_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    with Image.open(io.BytesIO(content)) as image:
        matrix = np.array(image)
    assert (
        matrix.ndim == 2 and np.isfinite(matrix).all() and matrix.max() > matrix.min()
    )
    rows, cols = matrix.shape
    times = np.arange(cols) * dt / 60
    positions = np.arange(rows) * DX
    reporter = "Her7–mVenus"
    label = "Processed matrix"
    item = dict(
        matrix=matrix.astype(float), time=times, position=positions, position_unit="µm"
    )
    condition = f"{temp}°C"
    sample = f"{date} P1"
    provenance = f"data/derived/{key}/provenance.json"
    record = dict(
        id=key,
        paper_id=PAPER,
        short="Chhabra 2026",
        reporter=reporter,
        kind="matrix",
        label=label,
        source_url=REPOSITORY,
        data_url=source,
        sample=f"{condition} · {sample}",
        system_label="Medaka tail explant",
        card_context=dict(condition=condition, sample=sample),
        origin="First stored row",
        origin_short="Stored position",
        position_unit="µm",
        input=input_path,
        input_sha256=source_hash,
        shape_space_time=[rows, cols],
        time_range_h=[0, float(times[-1])],
        spatial_range=[0, float(positions[-1])],
        spatial_range_um=[0, float(positions[-1])],
        missing_values=0,
        normalization=dict(
            method="linear min-max of finite values in the complete sample",
            min=float(matrix.min()),
            max=float(matrix.max()),
        ),
        provenance=provenance,
        sampling_method=f"Display the stored intensity TIFF at {dt} min per column and 1.38 µm per row. Preserve its ordering and normalize over the complete sample.",
    )
    files = [input_path, provenance]
    for window in ("common", "full"):
        stem = f"figures/comparison/{key}-{window}"
        fig, ax = plt.subplots(figsize=(4.4, 3.8))
        fig.subplots_adjust(left=0.16, right=0.89, bottom=0.19, top=0.87)
        panel(fig, ax, item, window)
        ax.set_title(reporter, loc="left", pad=12)
        fig.text(0.16, 0.035, label, fontsize=8, color="#737c8d")
        formats = ("svg", "png", "pdf") if window == "full" else ("svg",)
        save(fig, ASSET_ROOT / stem, formats)
        files.extend(f"{stem}.{fmt}" for fmt in formats)
        record[f"{window}_preview"] = stem + ".svg"
    write_json(
        ASSET_ROOT / provenance,
        dict(
            source_url=source,
            revision=REVISION,
            sha256=source_hash,
            settings_url=f"{REPOSITORY}/blob/{REVISION}/SVD_analysis/src/data_settings.py",
            sample=sample,
            temperature_C=temp,
            batch=1,
            somite_group="14ss",
            registration="Center of mass",
            time_step_min=dt,
            space_step_um=DX,
            shape_space_time=[rows, cols],
            normalization=record["normalization"],
            source_dtype=str(matrix.dtype),
        ),
    )
    asset = dict(
        level="matrix",
        level_label="Author intensity matrix",
        label=f"Intensity · {condition} / {sample}",
        local_path=input_path,
        url=source,
        format="TIFF",
        bytes=len(content),
        status="verified_content",
        evidence=f"Complete intensity matrix from batch 1, {rows} positions by {cols} time points.",
        license="MIT · author data repository",
    )
    bundle = dict(
        paper=dict(
            id=PAPER,
            sources=[
                dict(
                    id=f"M{temp}",
                    url=source,
                    location=asset["label"],
                    note=asset["evidence"],
                )
            ],
        ),
        comparison=record,
        presentation=dict(
            axis_polarity=polarity,
            target_genes=["her7"],
            conditions=[condition],
            plot_layout="compact",
            experimental_facts=[
                dict(label="Preparation", value="Tail explant", evidence_ids=["C1"]),
                dict(label="Temperature", value=condition, evidence_ids=[f"M{temp}"]),
            ],
            calibration_short=f"{dt} min · 1.38 µm/px ({condition})",
            sample_asset=asset,
            overview_summary=f"Her7–mVenus intensity in medaka tail explant {sample}, batch 1 at constant {condition}.",
        ),
        coverage=dict(
            mode="all",
            unit="timepoints",
            used=cols,
            total=cols,
            ranges_inclusive=[[0, cols - 1]],
            index_origin=0,
            note=f"All {cols} time points in the {condition} intensity matrix for {sample}.",
        ),
        video=dict(videos=[], preferred_by_dataset={}),
        assets={
            f: hashlib.sha256((ASSET_ROOT / f).read_bytes()).hexdigest() for f in files
        },
    )
    if temp == 22:
        bundle["insert_before"] = PAPER
    return bundle


if __name__ == "__main__":
    archive_path = (
        ASSET_ROOT / "data/source-archive" / PAPER / "cycles-upon-cycles-c8942dd.zip"
    )
    polarity = json.loads((CATALOG_ROOT / "card-presentation.json").read_text())[PAPER][
        "axis_polarity"
    ]
    with ZipFile(archive_path) as archive:
        bundles = [
            create_card(archive, *sample, polarity=polarity) for sample in SAMPLES
        ]
    write_json(REPO_ROOT / "work/medaka-temperature/bundles.json", bundles)
    for bundle in bundles:
        record = bundle["comparison"]
        print(
            record["sample"],
            record["shape_space_time"],
            record["time_range_h"],
            record["spatial_range"],
        )

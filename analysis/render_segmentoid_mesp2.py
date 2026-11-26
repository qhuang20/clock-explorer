# SPDX-License-Identifier: MIT
"""Build the local MESP2 reporter card for wild-type Segmentoid #1."""

import hashlib
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from comparison_plot import panel, save
from paths import ASSET_ROOT, CATALOG_ROOT, REPO_ROOT


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")


def main():
    specimen = "WT #1"
    movie_name = "Movie 8, left specimen"
    sibling = "miao-2023-segmentoid"
    key = f"{sibling}-mesp2"
    source = f"data/derived/{sibling}/wt-matrices.npz"
    input_path = f"data/derived/{key}/kymograph.npz"
    provenance = f"data/derived/{key}/provenance.json"
    records = json.loads((CATALOG_ROOT / "comparison.json").read_text())["datasets"]
    record = next(r for r in records if r["id"] == sibling).copy()
    with np.load(ASSET_ROOT / source) as data:
        intensity = np.where(
            data["joint_edge_zero_mask"], np.nan, data["mesp2_author"]
        ).T[::-1]
        position = data["distance_from_posterior_um"][::-1]
        times = data["time_h"]
        low, high = float(np.nanmin(intensity)), float(np.nanmax(intensity))
        np.testing.assert_allclose(
            (intensity - low) / (high - low), data["mesp2_display_normalized"]
        )
    (ASSET_ROOT / input_path).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        ASSET_ROOT / input_path, intensity=intensity, time_h=times, position_um=position
    )
    write_json(
        ASSET_ROOT / provenance,
        dict(
            source=source,
            sha256=file_hash(ASSET_ROOT / source),
            source_url=record["data_url"],
            author_field="kimoMf_t",
            stored_channel="mesp2_author",
            specimen=specimen,
            movie=movie_name,
            mask="joint_edge_zero_mask",
            parent_record=record["provenance"],
            shape_space_time=list(intensity.shape),
            normalization={"min": low, "max": high},
        ),
    )
    rows, cols = intensity.shape
    interval_min = round(float(times[1] - times[0]) * 60)
    time_range = [float(times[0]), float(times[-1])]
    position_range = [float(position[0]), float(position[-1])]
    record.update(
        id=key,
        reporter="MESP2",
        reporter_note="Wild type · MESP2 channel",
        sample=f"{specimen} · Segmentoid",
        card_context={**record["card_context"], "sample": specimen},
        time_range_h=time_range,
        spatial_range=position_range,
        spatial_range_um=position_range,
        coverage_note=f"{cols} time points · {interval_min} min per column · {times[-1]:g} h",
        detail_primary_context=f"Author matrix · {specimen} · {movie_name} · {cols} time points · {interval_min} min per column",
        input=input_path,
        input_sha256=file_hash(ASSET_ROOT / input_path),
        provenance=provenance,
        shape_space_time=list(intensity.shape),
        missing_values=int(np.isnan(intensity).sum()),
        detail_title="Compare HES7 / UNCX and HES7-null",
        normalization={**record["normalization"], "min": low, "max": high},
    )
    files = [input_path, provenance]
    for window in ("full", "common"):
        stem = f"figures/comparison/{key}-{window}"
        formats = ("svg", "png", "pdf") if window == "full" else ("svg",)
        fig, ax = plt.subplots(figsize=(4.4, 3.8))
        fig.subplots_adjust(left=0.16, right=0.89, bottom=0.19, top=0.87)
        panel(
            fig,
            ax,
            {**record, "matrix": intensity, "position": position, "time": times},
            window,
        )
        save(fig, ASSET_ROOT / stem, formats)
        record[f"{window}_preview"] = stem + ".svg"
        files.extend(f"{stem}.{fmt}" for fmt in formats)
    display = json.loads((CATALOG_ROOT / "card-presentation.json").read_text())[sibling]
    display.update(
        target_genes=["MESP2"],
        conditions=["Segmentoid", "Wild type", "Temp. unverified"],
        signal_note=record["reporter_note"],
        primary_matrix_label=f"{specimen} · MESP2 matrix",
    )
    method = display["matrix_method"]
    method["sampling"] = (
        f"Each column gives the posterior-aligned MESP2 profile in {specimen} ({movie_name})."
    )
    method["steps"] = [
        f"Read kimoMf_t from the author MAT file for {specimen}. The authors averaged across the sampling region and applied a 50 px spatial filter.",
        f"Retain all {rows} positions in posterior-aligned coordinates. Mask shared edge zeros and keep interior zeros.",
        f"Scale finite values across all {cols} time points to 0–1 and display A above P.",
    ]
    coverage = dict(
        mode="all",
        unit="timepoints",
        used=cols,
        total=cols,
        ranges_inclusive=[[0, cols - 1]],
        index_origin=0,
        note=f"All {cols} time points in the {specimen} MESP2 matrix are displayed.",
    )
    bundle = dict(
        paper={"id": record["paper_id"], "sources": []},
        comparison=record,
        presentation=display,
        coverage=coverage,
        video={"videos": [], "preferred_by_dataset": {key: "movie-8"}},
        assets={path: file_hash(ASSET_ROOT / path) for path in files},
    )
    write_json(REPO_ROOT / "work" / "segmentoid-mesp2" / "bundle.json", bundle)


if __name__ == "__main__":
    main()

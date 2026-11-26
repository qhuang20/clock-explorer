# SPDX-License-Identifier: MIT

from paths import ASSET_ROOT, CATALOG_ROOT
from pathlib import Path
import json, base64, hashlib, argparse
import numpy as np, tifffile
import matplotlib

S = ASSET_ROOT
O = S / "data/range-explorer"
O.mkdir(parents=True, exist_ok=True)
recs = json.loads((CATALOG_ROOT / "comparison.json").read_text())["datasets"]
coverage = json.loads((CATALOG_ROOT / "temporal-coverage.json").read_text())
parser = argparse.ArgumentParser(
    description="Build range payloads from reviewed selected matrices."
)
parser.add_argument(
    "--only",
    action="append",
    help="Rebuild only this dataset payload; preserve other payloads and index entries.",
)
selected_ids = parser.parse_args().only
if selected_ids and not set(selected_ids) <= (
    {c["id"] for c in recs} | {"masamizu-2006"}
):
    raise ValueError("Unknown selected dataset")
index_path = O / "index.json"
meta = (
    (
        json.loads(index_path.read_text())
        if index_path.is_file()
        else json.loads((CATALOG_ROOT / "range-index.json").read_text())
    )
    if selected_ids
    else {}
)
palette = (
    (matplotlib.colormaps["OrRd"](np.linspace(0, 1, 256))[:, :3] * 255)
    .round()
    .astype(int)
    .tolist()
)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def variant(
    name,
    label,
    path,
    unit="frames",
    xkey="time_h",
    ykey=None,
    akey="intensity",
    note=None,
    previous=None,
):
    p = Path(path)
    p = p if p.is_absolute() else S / p
    if p.suffix == ".tif":
        a = tifffile.imread(p).astype(float)
        x = np.arange(a.shape[1]) / 6
        y = np.arange(a.shape[0]) * 1.38
    else:
        with np.load(p) as z:
            a = z[akey].astype(float)
            x = z[xkey]
            y = z[
                ykey
                or next(
                    k
                    for k in [
                        "position_um",
                        "position_px",
                        "position_row",
                        "position",
                        "image_y_px",
                        "distance_from_posterior_um",
                    ]
                    if k in z
                )
            ]
            if "joint_edge_zero_mask" in z:
                a = np.where(z["joint_edge_zero_mask"], np.nan, a).T[::-1]
                y = y[::-1]
    assert a.shape == (len(y), len(x)) and len(x) > 1
    assert np.all(np.diff(x) > 0) and np.all(np.diff(y) > 0)
    # Data retain their decoded numeric scale. Browser only normalizes display against full variant.
    out = {
        "id": name,
        "label": label,
        "unit": unit,
        "x_unit": "h" if xkey == "time_h" else "frame",
        "x": x.tolist(),
        "y": y.tolist(),
        "shape": list(a.shape),
        "array_f32_le": base64.b64encode(a.astype("<f4").tobytes()).decode(),
        "normalization": [float(np.nanmin(a)), float(np.nanmax(a))],
        "source_sha256": sha(p),
        "data_path": str(p.relative_to(S)),
        "note": note or "Full extracted matrix; missing values are retained.",
        "previous": previous,
    }
    return out


for c in recs:
    pid = c["id"]
    if selected_ids and pid not in selected_ids:
        continue
    unit = "frames" if coverage[pid]["unit"] == "frames" else "time points"
    v = variant(
        "full",
        "All available time points" if unit != "frames" else "All available frames",
        c["input"],
        unit,
    )
    if pid in {"sonnen-2018", "sonnen-2018-embryo"}:
        v["normalization"] = [c["normalization"]["min"], c["normalization"]["max"]]
        v["note"] = (
            "5 µm spatial smoothing in the source frame and along the strip. Display limits use the complete unsmoothed recording."
        )
        vs = [v]
    elif pid == "lauschke-2013":
        v["roi"] = c["roi"]
        v["note"] = (
            "Primary: dark-core-guided shared wavefront center, continued by BF translation; 45° strip, all 61 frames, original green display values. The centroid reference is retained in Figure & sampling. No author ROI, biological pacemaker or cell tracking is inferred."
        )
        vs = [v]
    elif pid in ["lauschke-2013-embryo", "lauschke-2013-mpsm"]:
        v["roi"] = c["roi"]
        v["label"] = (
            "Complete 0–20.92 h · 126 frames"
            if pid.endswith("embryo")
            else "All 160 source frames"
        )
        v["note"] = (
            "Fixed A/P reference coordinates after rigid stabilization; curve shifted 30 px inward, 20 px width mean. Unsupported extensions and disconnected intervals remain missing. Original composite display values, all 126 frames, no temporal filtering; registration remains under calibration."
            if pid.endswith("embryo")
            else "Unsmoothed display-video extraction. Per-frame experimental time overlays; geometry and FOV limits are documented in Figure & sampling. Spatial-filter comparisons are separate."
        )
        vs = [v]
    elif pid == "sanaki-2022":
        v["label"] = "Whole somitoid · all 362 frames"
        v["roi"] = c["roi"]
        v["note"] = c["roi_note"]
        vs = [v]
    elif pid == "miao-2023":
        full = variant(
            "full",
            "All 195 frames · mixed-colour estimate",
            "data/derived/miao-2023-full/kymograph.npz",
            note="HES7 / MESP2 composite video, not isolated HES7. Later colours poorly match the inferred LUT; rejected pixels remain missing. Fixed image strip, no tissue registration.",
            previous=[0, 51],
        )
        full["roi"] = "data/derived/miao-2023-full/roi-all-frames.jpg"
        v.update(
            id="right-radius",
            label="Right radius · first 52 frames",
            roi=c["roi"],
            note=c["roi_note"],
        )
        full["position_label"] = "Horizontal image position (approx. µm)"
        vs = [v, full]
    elif pid == "rohde-2024":
        v["label"] = "PSM4 tracked cohort · 300 time positions"
        v["note"] = (
            "All 300 acquisition positions are retained. Only 210 have measurements in this cohort; remaining positions are missing, not discarded frames."
        )
        vs = [
            v,
            variant(
                "tailbud",
                "Tailbud tracked cohort",
                "data/derived/rohde-2024/tailbud_cohort.npz",
                "time points",
            ),
        ]
    elif pid == "miao-2023-segmentoid":
        vs = []
        for g, glabel in [
            ("wt", "WT"),
            ("null", "HES7-null"),
        ]:
            p = S / f"data/derived/miao-2023-segmentoid/{g}-matrices.npz"
            with np.load(p) as z:
                print(g, "keys", z.files)
            for key in ["hu", "mesp2"]:
                # Extracted files preserve both author-processed channels and their shared mask.
                with np.load(p) as z:
                    actual = key if key in z else key + "_masked"
                    if actual not in z:
                        actual = key + "_author"
                vs.append(
                    variant(
                        g + "-" + key,
                        glabel
                        + " · "
                        + (
                            ("pseudoHES7 / UNCX" if g == "null" else "HES7 / UNCX")
                            if key == "hu"
                            else "MESP2"
                        ),
                        p,
                        "time points",
                        akey=actual,
                    )
                )
    else:
        vs = [v]
    payload = {
        "id": pid,
        "title": (
            "HES7 / MESP2 · composite video"
            if pid == "miao-2023"
            else c.get("reporter", c["short"])
        ),
        "position_label": c.get(
            "axis_label", "Local position (" + c["position_unit"] + ")"
        ),
        "variants": vs,
        "palette": palette,
        **({"position_increases_up": True} if pid == "miao-2023-segmentoid" else {}),
    }
    path = O / (pid + ".js")
    path.write_text(
        "window.ClockRangeExplorer.receive("
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ");\n"
    )
    meta[pid] = {
        "paper": c.get("paper_id", pid),
        "script": str(path.relative_to(S)),
        "title": payload["title"],
    }
if not selected_ids or "masamizu-2006" in selected_ids:
    pid = "masamizu-2006"
    v = variant(
        "full",
        "All 45 frames · uncalibrated time",
        "data/derived/masamizu-2006/kymograph.npz",
        xkey="frame_index",
        ykey="image_y_px",
        akey="intensity_8bit",
        note="All source frames. Biological frame interval is not verified; horizontal axis is frame index.",
    )
    payload = dict(
        id=pid,
        title="Hes1–Ub1–Luc",
        position_label="Image Y (video px)",
        variants=[v],
        palette=palette,
    )
    p = O / (pid + ".js")
    p.write_text(
        "window.ClockRangeExplorer.receive("
        + json.dumps(payload, separators=(",", ":"))
        + ");\n"
    )
    meta[pid] = dict(paper=pid, script=str(p.relative_to(S)), title=payload["title"])
(O / "index.json").write_text(json.dumps(meta, indent=2) + "\n")
(O / "index.js").write_text(
    "window.CLOCK_RANGE_INDEX = " + json.dumps(meta, separators=(",", ":")) + ";\n"
)
print("Built", len(meta), "range explorers.")

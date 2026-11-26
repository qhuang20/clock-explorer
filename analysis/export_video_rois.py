# SPDX-License-Identifier: MIT
"""Export playback-only ROI drawings from saved extraction geometry.

No measurements, masks, timestamps, centers or sampling paths are re-estimated.
The lightweight outlines describe sampling footprints, not per-pixel validity.
"""

import hashlib
import argparse
import json
from pathlib import Path

import av
import numpy as np

from paths import ASSET_ROOT, CATALOG_ROOT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rounded(points):
    return np.round(points, 2).tolist()


def runs(mask):
    edges = np.diff(np.r_[False, mask, False].astype(int))
    return zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))


def bands_from_path(path, normals, valid, width):
    bands, lines = [], []
    for start, stop in runs(valid):
        if stop - start < 2:
            continue
        indices = np.unique(np.r_[np.arange(start, stop, 6), stop - 1])
        xy = path[indices]
        n = normals[indices]
        bands.append(rounded(np.r_[xy - width / 2 * n, (xy + width / 2 * n)[::-1]]))
        lines.append(rounded(xy))
    return bands, lines


def radial_extent_guides(path, lines):
    """Draw the unsampled part of a straight radial path to its saved limit."""
    limit = rounded(path[-1])
    if lines and lines[-1][-1] != limit:
        return [[lines[-1][-1], limit]]
    return []


def playback_clock(path):
    with av.open(str(path)) as c:
        frames = [float(f.pts * f.time_base) for f in c.decode(video=0)]
    return [round(t - frames[0], 9) for t in frames]


def run(only=None):
    catalog = json.loads((CATALOG_ROOT / "videos.json").read_text())
    comparisons = json.loads((CATALOG_ROOT / "comparison.json").read_text())["datasets"]
    manifest = json.loads((CATALOG_ROOT / "assets.json").read_text())
    registered = {r["path"]: r for r in manifest["files"]}
    targets = [
        "lauschke-2013",
        "lauschke-2013-embryo",
        "lauschke-2013-mpsm",
        "lauschke-2013-mesp2",
        "sonnen-2018",
        "sonnen-2018-embryo",
        "sonnen-2018-microfluidic",
        "delaune-2012",
        "sanaki-2022",
        "miao-2023",
    ]
    if only:
        if not set(only) <= set(targets):
            raise ValueError("Unknown ROI dataset")
        targets = [target for target in targets if target in only]
    for dataset in targets:
        c = next(c for c in comparisons if c["id"] == dataset)
        paper_id = c.get("paper_id", dataset)
        paper = catalog["papers"][paper_id]
        video = next(
            v for v in paper["videos"] if dataset in v.get("source_dataset_ids", [])
        )
        playback = ASSET_ROOT / video["src"]
        if sha(playback) != video["playback_sha256"]:
            raise ValueError("Playback copy changed: " + dataset)
        starts = playback_clock(playback)
        if len(starts) != video["frames"]:
            raise ValueError("Playback frame count mismatch: " + dataset)
        numeric = ASSET_ROOT / c["input"]
        before = sha(numeric)
        frames = []
        with np.load(numeric, allow_pickle=False) as z:
            matrix = z["intensity"]
            count = matrix.shape[1]
            frame_indices = (
                z["frame_index"].astype(int) if "frame_index" in z else np.arange(count)
            )
            if (
                dataset in ["sonnen-2018", "sonnen-2018-embryo"]
                and "P_reference_source_xy" in z
            ):
                paths = z["path_xy"]
                normals = z["normals_xy"]
                width = float(z["strip_width_px"])
            elif dataset in ["lauschke-2013-embryo", "sonnen-2018-embryo"]:
                paths = z["path_xy"]
                normals = z["normals_xy"]
                width = float(z["strip_width_px"]) if "strip_width_px" in z else 20
            elif dataset == "sonnen-2018-microfluidic":
                paths = z["path_xy"]
                dx, dy = z["direction_xy"]
                normals = np.broadcast_to([-dy, dx], paths.shape)
                width = float(z["strip_width_px"])
            elif dataset in [
                "lauschke-2013",
                "lauschke-2013-mpsm",
                "lauschke-2013-mesp2",
                "sonnen-2018",
            ]:
                if dataset == "sonnen-2018":
                    origins = np.array([520.0, 480.0]) + z["shifts_xy"]
                    direction = np.array([-260.0, -240.0])
                    direction /= np.linalg.norm(direction)
                    directions = np.tile(direction, (count, 1))
                    scale = 100 / 139
                    width = 40
                else:
                    origins = z["origins_xy"]
                    directions = z["directions_xy"]
                    scale = 100 / 111 if dataset == "lauschke-2013-mpsm" else 100 / 105
                    width = 20
                paths = (
                    origins[:, None, :]
                    + z["position_um"][None, :, None] / scale * directions[:, None, :]
                )
                normal = np.stack([-directions[:, 1], directions[:, 0]], axis=-1)
                normals = np.repeat(normal[:, None, :], matrix.shape[0], axis=1)
            for i, index in enumerate(frame_indices):
                if dataset == "delaune-2012":
                    bands = [[[330, 180], [450, 180], [450, 851], [330, 851]]]
                    lines = [[[390, 180], [390, 850]]]
                elif dataset == "miao-2023":
                    start, stop = z["outline_offsets"][i : i + 2]
                    bands = [rounded(z["outline_xy"][start:stop])]
                    lines = [rounded([z["origin_xy"][i], z["edge_xy"][i]])]
                elif dataset == "sanaki-2022":
                    start, stop = z["contour_offsets"][i : i + 2]
                    outline = z["contour_xy"][start:stop]
                    bands = [rounded(outline), rounded(outline + [972, 0])]
                    lines = []
                else:
                    bands, lines = bands_from_path(
                        paths[i], normals[i], np.isfinite(matrix[:, i]), width
                    )
                frame = {"index": int(index), "bands": bands, "lines": lines}
                if dataset == "lauschke-2013-embryo" and "P_reference_source_xy" in z:
                    finite = np.isfinite(paths[i]).all(axis=1)
                    ids = np.flatnonzero(finite)[::6]
                    guide = np.r_[paths[i, ids], z["A_reference_source_xy"][i : i + 1]]
                    frame["guide_lines"] = [rounded(guide)]
                    frame["reference_points"] = rounded(
                        np.array(
                            [
                                z["P_reference_source_xy"][i],
                                z["A_reference_source_xy"][i],
                            ]
                        )
                    )
                if (
                    dataset in ["sonnen-2018", "sonnen-2018-embryo"]
                    and "P_reference_source_xy" in z
                ):
                    finite = np.isfinite(paths[i]).all(axis=1)
                    ids = np.flatnonzero(finite)
                    guide_ids = np.unique(np.r_[ids[::6], ids[-1]])
                    frame["guide_lines"] = [rounded(paths[i, guide_ids])]
                    measured = np.flatnonzero(np.isfinite(matrix[:, i]))
                    endpoint = (
                        z["A_reference_source_xy"][i]
                        if "A_reference_source_xy" in z
                        else paths[i, measured[-1]]
                    )
                    frame["reference_points"] = rounded(
                        np.array([z["P_reference_source_xy"][i], endpoint])
                    )
                elif dataset == "sonnen-2018-microfluidic":
                    frame["guide_lines"] = radial_extent_guides(paths[i], lines)
                elif dataset == "sonnen-2018-embryo" and "seam_xy" in z:
                    frame["guide_lines"] = [rounded(z["seam_xy"][i])]
                if "time_h" in z:
                    frame["experiment_h"] = float(z["time_h"][i])
                frames.append(frame)
        labels = (
            ["P", "A"]
            if dataset
            in [
                "lauschke-2013",
                "lauschke-2013-embryo",
                "lauschke-2013-mesp2",
                "sonnen-2018-embryo",
            ]
            else ["P", "E"]
            if dataset == "sonnen-2018"
            else ["O", "E"]
            if dataset in {"sonnen-2018-microfluidic", "miao-2023"}
            else None
        )
        suffix = (
            "-video-roi-with-extent.json"
            if dataset == "sonnen-2018-microfluidic"
            else "-radial-roi.json"
            if dataset == "miao-2023"
            else "-video-roi.json"
        )
        output = ASSET_ROOT / "data/derived" / paper_id / (dataset + suffix)
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "dataset_id": dataset,
            "video_id": video["id"],
            "source_sha256": video["source_sha256"],
            "playback_sha256": video["playback_sha256"],
            "width": video["width"],
            "height": video["height"],
            "frame_starts_s": starts,
            "direction_labels": labels,
            "frames": frames,
            "geometry_input": c["input"],
            "geometry_input_sha256": before,
            "drawing": "source xy coordinates, 0.01 px rounding; valid distance runs; curved paths every 6 rows with endpoints retained; no y display flip",
            "scope": "Sampling footprint only. It does not assert tissue identity or show each rejected pixel. Geometry uncertainty remains as documented in the source extraction.",
        }
        output.write_text(
            json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n"
        )
        if sha(numeric) != before:
            raise ValueError("Scientific input was modified")
        rel = str(output.relative_to(ASSET_ROOT))
        video.setdefault("sampling_rois", {})[dataset] = rel
        entry = registered.get(rel)
        if entry is None:
            entry = {
                "path": rel,
                "group": "core",
                "paper": paper_id,
                "url": "https://segmentation-clock-explorer.pages.dev/" + rel,
                "rights": "Playback-only geometry derived from the saved local extraction; retain original research source terms.",
            }
            manifest["files"].append(entry)
        entry.update(bytes=output.stat().st_size, sha256=sha(output))
        print(
            dataset,
            len(frames),
            "/",
            len(starts),
            "frames",
            output.stat().st_size,
            "bytes",
        )
    (CATALOG_ROOT / "videos.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
    )
    (CATALOG_ROOT / "assets.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only", action="append", help="Update only this dataset overlay and mapping"
    )
    run(parser.parse_args().only)

"""Resume curated reporter-movie jobs and materialize reviewed local cards."""

import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import urllib.request
from project import ROOT, CATALOG, asset_path, digest, read_json

QUEUE = CATALOG / "kymograph-tasks.json"
RUNS = ROOT / "work/kymograph-runs"
FILES = {
    "figures": ["roi.png", "plot.svg", "plot.png"],
    "videos": ["playback.mp4", "poster.jpg"],
    "data/derived": ["overlay.json", "kymograph.npz", "audit.json", "review.json"],
}


def atomic(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, mode="w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    Path(f.name).replace(path)


def resume(job):
    from mouse_roi import extract
    from verify_mouse_roi import review
    from card_bundle import package

    key = job["id"]
    out = RUNS / key
    out.mkdir(parents=True, exist_ok=True)
    with (out / "run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state_file = out / "state.json"
        if job["role"] == "library":
            atomic(
                state_file,
                dict(
                    dataset=key,
                    status="needs_data",
                    next="source audit",
                    reason=job["reason"],
                ),
            )
            return "Library · needs data"
        if job["role"] not in {"axial", "radial"}:
            raise ValueError("Select an audited axial or radial sampling model.")
        signature = hashlib.sha256(json.dumps(job, sort_keys=True).encode()).hexdigest()
        state = read_json(state_file) if state_file.exists() else {}
        if state.get("spec") != signature:
            state = dict(dataset=key, spec=signature, stages={})
        src = asset_path(f"data/sources/{key}/{job['filename']}")
        paths = {
            name: f"{folder}/{key}/{name}"
            for folder, names in FILES.items()
            for name in names
        }

        def acquire():
            audit = read_json(
                CATALOG / "source-audits" / (job.get("paper_id", key) + ".json")
            )
            if not any(
                item["movie"] == job["movie"]
                and item["source_sha256"] == job["sha256"]
                and item["source_url"] == job["source"]
                and item["route"] == job["role"]
                for item in audit["signals"]
            ):
                raise ValueError("Queue and source audit disagree")
            src.parent.mkdir(parents=True, exist_ok=True)
            if not src.exists() or digest(src) != job["sha256"]:
                target = src.with_suffix(".download")
                with (
                    urllib.request.urlopen(job["source"], timeout=60) as reader,
                    target.open("wb") as writer,
                ):
                    shutil.copyfileobj(reader, writer)
                if digest(target) != job["sha256"]:
                    raise ValueError(
                        "Publisher file hash differs from reviewed source."
                    )
                target.replace(src)
            atomic(
                out / "audit.json",
                dict(
                    paper=job["article"],
                    source_url=job["source"],
                    source_sha256=digest(src),
                    panel=job["panel"],
                    movie=job["movie"],
                    scope="Selected specimen only",
                    route=job["role"],
                    source_width_height=job["dimensions"],
                    crop_xywh=job.get("crop_xywh"),
                    scale=dict(
                        bar_um=job.get("bar_um", 200), span_px=job["bar_pixels"]
                    ),
                    experiment_time_h=job["time_h"],
                    steps=job["steps"],
                    limit=job["limit"],
                ),
            )

        def measure():
            frames, starts = extract(job, src, out)
            atomic(
                out / "overlay.json",
                dict(
                    schema_version=1,
                    dataset_id=key,
                    video_id=job.get("video_id", "movie-1"),
                    width=(job.get("crop_xywh", [0, 0, *job["dimensions"]])[2] + 1)
                    // 2
                    * 2,
                    height=job.get("crop_xywh", [0, 0, *job["dimensions"]])[3],
                    source_sha256=digest(src),
                    playback_sha256=digest(out / "playback.mp4"),
                    geometry_input_sha256=digest(out / "kymograph.npz"),
                    direction_labels=["P", "A"]
                    if job["role"] == "axial"
                    else ["O", "E"],
                    frame_starts_s=starts,
                    frames=frames,
                ),
            )

        def verify():
            atomic(out / "review.json", review(src, out, job))

        def assemble():
            data = package(job, out, paths, src)
            for name, rel in paths.items():
                target = asset_path(rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(out / name, target)
            data["assets"] = {rel: digest(asset_path(rel)) for rel in paths.values()}
            atomic(out / "bundle.json", data)

        stages = [
            (
                "source-audit",
                acquire,
                [src, out / "audit.json"],
                [CATALOG / "source-audits" / (job.get("paper_id", key) + ".json")],
            ),
            (
                job["role"],
                measure,
                [
                    out / f
                    for f in [
                        "kymograph.npz",
                        "overlay.json",
                        "roi.png",
                        "plot.png",
                        "plot.svg",
                        "poster.jpg",
                        "playback.mp4",
                    ]
                ],
                ["mouse_roi.py"]
                + (["aulehla_reference.py"] if "final_tail_reference" in job else []),
            ),
            (
                "independent-recompute",
                verify,
                [out / "review.json"],
                ["verify_mouse_roi.py"],
            ),
            (
                "ui-card",
                assemble,
                [out / "bundle.json", *(asset_path(p) for p in paths.values())],
                ["card_bundle.py"],
            ),
        ]
        changed = False
        for stage, run, outputs, code in stages:
            token = (
                signature
                + digest(Path(__file__))
                + "".join(digest(Path(__file__).parent / f) for f in code)
            )
            receipt = state["stages"].get(stage, {})
            hashes = receipt.get("sha256", [])
            if (
                not changed
                and receipt.get("version") == token
                and len(hashes) == len(outputs)
                and all(p.is_file() and digest(p) == h for p, h in zip(outputs, hashes))
            ):
                continue
            changed = True
            state.update(status="running", next=stage)
            atomic(state_file, state)
            try:
                run()
            except Exception as exc:
                state.update(status="blocked", error=str(exc))
                atomic(state_file, state)
                raise
            state["stages"][stage] = dict(
                version=token, sha256=[digest(p) for p in outputs]
            )
            state.pop("error", None)
            atomic(state_file, state)
        state.update(status="ready-local", next="anatomical review")
        atomic(state_file, state)
        return state["status"] + (
            " · updated" if changed else " · verified checkpoints"
        )


def local_bundles():
    for name in ("rohde-axial", "morimoto-2005"):
        bundle_path = ROOT / "work" / name / "bundle.json"
        if not bundle_path.is_file():
            continue
        bundle = read_json(bundle_path)
        if any(
            digest(asset_path(path)) != expected
            for path, expected in bundle["assets"].items()
        ):
            raise ValueError(f"{name} assets differ from the local bundle")
        if name == "morimoto-2005":
            bundle["library_only"] = True
        yield bundle
    queue = read_json(QUEUE)
    for job in queue["tasks"]:
        out = RUNS / job["id"]
        if not (out / "state.json").is_file():
            continue
        with (out / "run.lock").open("r") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            state = read_json(out / "state.json")
            if state.get("status") != "ready-local":
                continue
            if (
                state["spec"]
                != hashlib.sha256(json.dumps(job, sort_keys=True).encode()).hexdigest()
            ):
                continue
            receipt = state["stages"]["ui-card"]
            if digest(out / "bundle.json") != receipt["sha256"][0]:
                raise ValueError("Bundle changed; resume " + job["id"])
            bundle = read_json(out / "bundle.json")
            if any(digest(asset_path(p)) != h for p, h in bundle["assets"].items()):
                raise ValueError("Local asset changed; resume " + job["id"])
            yield {**bundle, "library_only": job["id"] in queue.get("library_only", [])}


def reviewed_batch(manifest):
    """Load exactly the local datasets selected for this preview."""
    for key, expected in read_json(manifest)["bundles"].items():
        if not key or key in (".", "..") or Path(key).name != key:
            raise ValueError(f"Invalid local dataset ID: {key}")
        path = manifest.parent / key / "bundle.json"
        if digest(path) != expected:
            raise ValueError(f"Changed local card bundle: {key}")
        item = read_json(path)
        if item["comparison"]["id"] != key:
            raise ValueError(f"Dataset ID differs from its bundle directory: {key}")
        for rel, sha256 in item["assets"].items():
            if digest(asset_path(rel)) != sha256:
                raise ValueError(f"Changed local card asset: {rel}")
        yield item


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["resume", "status"])
    parser.add_argument("dataset", nargs="*")
    options = parser.parse_args()
    jobs = read_json(QUEUE)["tasks"]
    unknown = set(options.dataset) - {j["id"] for j in jobs}
    if unknown:
        parser.error("Unknown job: " + ", ".join(sorted(unknown)))
    failures = []
    for job in jobs:
        if options.dataset and job["id"] not in options.dataset:
            continue
        try:
            if options.action == "resume":
                result = resume(job)
            else:
                path = RUNS / job["id"] / "state.json"
                result = read_json(path).get("status") if path.exists() else "queued"
            print(job["id"], result, flush=True)
        except Exception as error:
            failures.append(job["id"])
            print(job["id"], str(error), flush=True)
    if failures:
        raise SystemExit(1)

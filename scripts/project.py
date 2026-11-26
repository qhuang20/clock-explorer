# SPDX-License-Identifier: MIT
"""Project paths and small shared validation helpers; no external dependencies."""

from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog"
ASSETS = Path(os.environ.get("CLOCK_ASSET_ROOT", ROOT / "assets")).resolve()
LOCAL_PREVIEW = ROOT / ".local" / "preview"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def asset_path(relative, root=ASSETS):
    path = (root / relative).resolve()
    if (
        not relative
        or Path(relative).is_absolute()
        or not path.is_relative_to(root.resolve())
    ):
        raise ValueError("Asset path escapes its directory: " + relative)
    return path


def runtime_catalog():
    data = read_json(CATALOG / "literature.json")
    comparison = read_json(CATALOG / "comparison.json")
    papers = {paper["id"]: paper for paper in data["papers"]}
    for record in comparison["datasets"]:
        pid = record.get("paper_id", record["id"])
        if pid not in papers:
            raise ValueError("Unknown dataset paper: " + pid)
        if record["id"] == pid:
            papers[pid]["kymograph"]["comparison"] = record
    data["comparison"] = comparison
    data["temporal_coverage"] = read_json(CATALOG / "temporal-coverage.json")
    data["card_presentation"] = read_json(CATALOG / "card-presentation.json")
    return data

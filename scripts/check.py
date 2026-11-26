# SPDX-License-Identifier: MIT
"""Check authored English metadata, paths, and optional hydrated files."""

from pathlib import Path
import re
from project import (
    ROOT,
    CATALOG,
    asset_path,
    digest,
    read_json,
    runtime_catalog,
)


def validate():
    data = runtime_catalog()
    papers = data["papers"]
    ids = [paper["id"] for paper in papers]
    assert len(ids) == len(set(ids)), "Duplicate paper IDs"
    for paper in papers:
        assert paper.get("library_role", "candidate") in {"candidate", "reference"}
        assert all(
            paper.get(key) for key in ("short", "title", "url", "species", "year")
        ), paper["id"]
        evidence = {source["id"] for source in paper["sources"]}
        assert len(evidence) == len(paper["sources"]), paper["id"]
        for sources in paper["field_evidence"].values():
            assert all(source in evidence for source in sources), paper["id"]
    records = data["comparison"]["datasets"]
    assert len({r["id"] for r in records}) == len(records), "Duplicate dataset IDs"
    for record in records:
        assert record["kind"] in {"matrix", "video", "video_lut", "tracks", "spots"}
        assert record["input_sha256"] and len(record["input_sha256"]) == 64
        coverage = data["temporal_coverage"].get(record["id"])
        if coverage and coverage["mode"] != "measured":
            assert coverage["used"] == record["shape_space_time"][1], record["id"]
    manifest = read_json(CATALOG / "assets.json")["files"]
    paths = [entry["path"] for entry in manifest]
    assert len(paths) == len(set(paths)), "Duplicate optional asset paths"
    hydrated = 0
    for entry in manifest:
        path = asset_path(entry["path"])
        if entry.get("local_only"):
            assert "url" not in entry, entry["path"]
            if "source_link" in entry:
                link = entry["source_link"]
                assert link["label"] and link["url"].startswith("https://"), entry[
                    "path"
                ]
        else:
            assert entry["url"].startswith("https://"), entry["path"]
        assert entry["group"] in {"core", "videos", "sources"}
        if path.is_file():
            assert path.stat().st_size == entry["bytes"], entry["path"]
            assert digest(path) == entry["sha256"], entry["path"]
            hydrated += 1
    tracked_roots = [
        ROOT / name
        for name in (
            "web",
            "catalog",
            "scripts",
            "analysis",
            "docs",
            "tests",
            ".github",
            ".agents",
        )
    ]
    for root in tracked_roots:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {
                ".js",
                ".json",
                ".py",
                ".md",
                ".yml",
                ".html",
                ".mjs",
                ".csv",
            }:
                text = path.read_text()
                assert not re.search(r"[\u3400-\u9fff]", text), (
                    "Authored project text must use English: "
                    + str(path.relative_to(ROOT))
                )
                if path.resolve() == Path(__file__).resolve():
                    continue
                assert not re.search(
                    r"/Users/[A-Za-z0-9._-]+/|/home/[A-Za-z0-9._-]+/|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN .*PRIVATE KEY-----",
                    text,
                ), "Private path or secret pattern: " + str(path.relative_to(ROOT))
    print(
        f"Validated {len(papers)} papers, {len(records)} dataset records, {len(manifest)} optional assets ({hydrated} local)."
    )


if __name__ == "__main__":
    validate()

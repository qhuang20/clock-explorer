# SPDX-License-Identifier: MIT
"""Fetch optional research assets with SHA-256 verification, never unzip or execute them."""

import argparse
import shutil
import urllib.request
from project import CATALOG, asset_path, digest, read_json


def download(entry):
    target = asset_path(entry["path"])
    if target.is_file() and digest(target) == entry["sha256"]:
        return "cached"
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    try:
        request = urllib.request.Request(
            entry["url"], headers={"User-Agent": "Clock-Explorer/0.1"}
        )
        with (
            urllib.request.urlopen(request, timeout=90) as source,
            partial.open("wb") as out,
        ):
            shutil.copyfileobj(source, out, length=1024 * 1024)
        if (
            partial.stat().st_size != entry["bytes"]
            or digest(partial) != entry["sha256"]
        ):
            raise ValueError(
                "Downloaded bytes differ from recorded source: " + entry["path"]
            )
        partial.replace(target)
        return "downloaded"
    finally:
        partial.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--group", choices=["core", "videos", "sources", "all"], default="core"
    )
    parser.add_argument("--paper", help="Restrict to a catalogue paper ID")
    parser.add_argument("--dry-run", action="store_true")
    options = parser.parse_args()
    entries = [
        entry
        for entry in read_json(CATALOG / "assets.json")["files"]
        if not entry.get("local_only")
        and (options.group == "all" or entry["group"] == options.group)
        and (not options.paper or entry["paper"] == options.paper)
    ]
    if not entries:
        raise SystemExit("No matching assets.")
    print(
        f"{len(entries)} files, {sum(e['bytes'] for e in entries) / 1048576:.1f} MiB. Original source licenses apply."
    )
    failures = []
    for entry in entries:
        if options.dry_run:
            print(entry["path"])
            continue
        try:
            print(download(entry), entry["path"], flush=True)
        except Exception as error:
            failures.append(entry["path"])
            print(f"FAILED {entry['path']}: {error}", flush=True)
    if failures:
        raise SystemExit(
            f"{len(failures)} downloads failed; valid local assets were kept."
        )


if __name__ == "__main__":
    main()

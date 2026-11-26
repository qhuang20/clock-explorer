# SPDX-License-Identifier: MIT
"""Build a static site. Missing research assets use verified source URLs."""

import argparse
import csv
from copy import deepcopy
from html import escape
import json
from pathlib import Path
import shutil
import subprocess
from string import Template
from project import (
    ROOT,
    CATALOG,
    LOCAL_PREVIEW,
    asset_path,
    read_json,
    runtime_catalog,
    write_json,
)
from check import validate
from citation import formatted_citation
from card_previews import render_card_previews
from publication import omitted_path, omit_local_media, remove_omitted_references


def bundle(source, output, minify=True):
    esbuild = ROOT / "node_modules/.bin/esbuild"
    if not esbuild.exists():
        raise SystemExit("Run npm ci first (Node 22 or newer).")
    args = [
        str(esbuild),
        str(source),
        "--bundle",
        "--legal-comments=eof",
        "--charset=ascii",
        "--outfile=" + str(output),
    ]
    if source.suffix == ".js":
        args += ["--format=iife", "--target=es2022"]
    if minify:
        args.append("--minify")
    subprocess.run(args, cwd=ROOT, check=True)


def merge_local_cards(data, videos, local_cards):
    local_assets = []
    for item in local_cards:
        paper_id = item["paper"]["id"]
        key = item["comparison"]["id"]
        reviewed = next(
            (
                record
                for record in data["comparison"]["datasets"]
                if record["id"] == key
            ),
            None,
        )
        if reviewed is not None:
            if reviewed != item["comparison"]:
                raise ValueError(
                    "Local redraw conflicts with a cataloged dataset: " + key
                )
            continue
        paper = next((p for p in data["papers"] if p["id"] == paper_id), None)
        if paper is None:
            paper = deepcopy(item["paper"])
            if item.get("library_only"):
                paper.pop("kymograph", None)
            data["papers"].append(paper)
        else:
            for source in item["paper"]["sources"]:
                if all(existing["id"] != source["id"] for existing in paper["sources"]):
                    paper["sources"].append(source)
            known_assets = {
                (asset["level"], asset.get("local_path") or asset.get("url"))
                for asset in paper.setdefault("assets", [])
            }
            for asset in item["paper"].get("assets", []):
                identity = (asset["level"], asset.get("local_path") or asset.get("url"))
                if identity not in known_assets:
                    paper["assets"].append(asset)
                    known_assets.add(identity)
        if item.get("library_only"):
            continue
        if paper.get("kymograph") is None:
            paper["kymograph"] = {
                "kind": "experimental",
                "default_dataset": key,
                "short": item["comparison"]["reporter"],
                "comparison": item["comparison"],
            }
        elif key == paper_id:
            paper["kymograph"]["comparison"] = item["comparison"]
        records = data["comparison"]["datasets"]
        before = item.get("insert_before")
        index = next(
            (i for i, record in enumerate(records) if record["id"] == before),
            len(records),
        )
        records.insert(index, item["comparison"])
        data["card_presentation"][key] = item["presentation"]
        data["temporal_coverage"][key] = item["coverage"]
        if paper_id in videos["papers"]:
            media = videos["papers"][paper_id]
            new_ids = {v["id"] for v in item["video"]["videos"]}
            media["videos"] = [v for v in media["videos"] if v["id"] not in new_ids]
            media["videos"].extend(item["video"]["videos"])
            media.setdefault("preferred_by_dataset", {}).update(
                item["video"]["preferred_by_dataset"]
            )
        else:
            videos["papers"][paper_id] = item["video"]
        for dataset_id, updates in item.get("method_figure_updates", {}).items():
            data["card_presentation"][dataset_id]["method_figure"].update(updates)
        local_assets.extend(item["assets"])
    return local_assets


def write_review_data(destination, cards, data, videos, published_ids=None):
    """Build an independent catalog for cards awaiting the user's decision."""
    review = {
        **data,
        "papers": [],
        "comparison": {**data["comparison"], "datasets": []},
        "card_presentation": {},
        "temporal_coverage": {},
    }
    review_videos = {**videos, "papers": {}}
    if published_ids is not None:
        review = deepcopy(data)
        review_videos = deepcopy(videos)
        review["catalog_review"] = {
            "published": published_ids,
            "candidates": [card["comparison"]["id"] for card in cards],
        }
    existing_papers = {paper["id"] for paper in review["papers"]}
    assets = merge_local_cards(review, review_videos, cards)
    for paper in review["papers"]:
        if paper["id"] in existing_papers:
            continue
        record = next(
            (
                c
                for c in review["comparison"]["datasets"]
                if c.get("paper_id", c["id"]) == paper["id"]
            ),
            None,
        )
        if record is not None:
            paper["kymograph"].update(default_dataset=record["id"], comparison=record)
    review["card_previews"] = render_card_previews(review, destination)
    write_runtime_js(destination / "data/review-data.js", "CLOCK_DATA", review)
    write_runtime_js(
        destination / "data/review-videos.js", "CLOCK_VIDEO_CATALOG", review_videos
    )
    return assets


def write_runtime_js(path, variable, value):
    path.write_text(
        "window." + variable + "=" + json.dumps(value, ensure_ascii=False) + ";\n"
    )


def build(
    output=None, minify=True, local_runs=False, local_batch=None, local_media=False
):
    validate()
    manifest = read_json(CATALOG / "assets.json")["files"]
    omitted = {
        entry["path"]
        for entry in manifest
        if entry.get("local_only")
        and not (local_media and asset_path(entry["path"]).is_file())
    }
    source_links = {
        entry["path"]: entry["source_link"]
        for entry in manifest
        if entry["path"] in omitted and entry.get("source_link")
    }
    local_cards = []
    if local_runs:
        from kymograph_pipeline import local_bundles

        local_cards.extend(local_bundles())
    review_cards = []
    published_ids = None
    if local_batch:
        from kymograph_pipeline import reviewed_batch

        review_cards = list(reviewed_batch(local_batch))
        published_ids = read_json(local_batch).get("published_card_ids")
    destination = (
        output or (LOCAL_PREVIEW if local_media else ROOT / "dist")
    ).resolve()
    # Never remove an arbitrary user folder as a build side effect.
    if destination == ROOT or not destination.is_relative_to(ROOT):
        raise ValueError("Build output must be a subdirectory of this repository")
    if local_media and LOCAL_PREVIEW.parent not in destination.parents:
        raise ValueError("Local media builds must stay under .local/")
    if (
        destination.exists()
        and destination != ROOT / "dist"
        and not (destination / ".clock-build").is_file()
    ):
        raise ValueError("Custom output must be new or contain .clock-build")
    destination.mkdir(parents=True, exist_ok=True)
    for child in destination.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    (destination / ".clock-build").touch()
    data = runtime_catalog()
    videos = read_json(CATALOG / "videos.json")
    local_assets = merge_local_cards(data, videos, local_cards)
    tutorial_cases = {}
    records = {record["id"]: record for record in data["comparison"]["datasets"]}
    for key, case in read_json(CATALOG / "tutorial-cases.json").items():
        record = records[key]
        paper_id = record.get("paper_id", key)
        movie = next(
            movie
            for movie in videos["papers"][paper_id]["videos"]
            if movie["id"] == case["movie_id"]
        )
        if movie["frames"] != len(case["experiment_time_h"]):
            raise ValueError("Tutorial time points do not match movie frames: " + key)
        tutorial_cases[key] = {
            "movie": movie,
            "inputHash": record["input_sha256"],
            "hours": case["experiment_time_h"],
        }
    if omitted or not local_media:
        omit_local_media(data, videos, omitted, source_links, public=not local_media)
    data["card_previews"] = render_card_previews(data, destination)
    (destination / "data").mkdir()
    if local_batch:
        local_assets.extend(
            write_review_data(destination, review_cards, data, videos, published_ids)
        )
    write_json(destination / "data/literature.json", data)
    write_runtime_js(destination / "data/data.js", "CLOCK_DATA", data)
    for name in (
        "comparison",
        "temporal-coverage",
        "color-policy",
        "additional-datasets",
        "videos",
    ):
        target = destination / "data" / (name + ".json")
        if name in {"videos", "comparison", "temporal-coverage"}:
            value = videos if name == "videos" else data[name.replace("-", "_")]
        else:
            value = read_json(CATALOG / (name + ".json"))
            remove_omitted_references(value, omitted)
        write_json(target, value)
    write_runtime_js(destination / "data/videos.js", "CLOCK_VIDEO_CATALOG", videos)
    fields = [
        "id",
        "title",
        "authors",
        "year",
        "doi",
        "url",
        "species",
        "systems",
        "reporter_construct",
        "time_axis",
        "space_axis",
        "sources",
    ]
    with (destination / "data/literature.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for paper in data["papers"]:
            writer.writerow(
                {
                    key: json.dumps(paper[key], ensure_ascii=False)
                    if isinstance(paper[key], (list, dict))
                    else paper[key]
                    for key in fields
                }
            )
    missing = {}
    redirects = []
    copied = 0
    for entry in manifest:
        path = entry["path"]
        if path in omitted:
            continue
        source = asset_path(path)
        # Original archives stay external. Private copies have no hosting limit.
        local = (
            source.is_file()
            and entry["group"] != "sources"
            and (entry.get("local_only") or entry["bytes"] < 25 * 1024 * 1024)
        )
        if local:
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied += 1
        elif not entry.get("local_only"):
            missing[path] = entry["url"]
            redirects.append(f"/{path} {entry['url']} 302")
    for rel in local_assets:
        if rel in omitted:
            continue
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset_path(rel), target)
        copied += 1
    for name, variable in [("archive", "CLOCK_SOURCE_ARCHIVE")]:
        target = destination / "data/source-archive"
        target.mkdir(parents=True, exist_ok=True)
        value = read_json(CATALOG / "sources" / (name + ".json"))
        # Every archive download is external in a code-only build, including
        # metadata entries that intentionally are not downloadable Git assets.
        value["files"] = [
            source_file
            for source_file in value["files"]
            if not omitted_path(source_file.get("path"), omitted)
            and not omitted_path(source_file.get("url"), omitted)
        ]
        for source_file in value["files"]:
            if (
                source_file.get("status") == "archived"
                and source_file.get("path")
                and source_file.get("url")
            ):
                missing.setdefault(source_file["path"], source_file["url"])
                route = f"/{source_file['path']} {source_file['url']} 302"
                if route not in redirects:
                    redirects.append(route)
        remove_omitted_references(value, omitted)
        write_json(target / "audit.json", value)
        (target / "index.js").write_text(
            "window." + variable + "=" + json.dumps(value, ensure_ascii=False) + ";\n"
        )
    (destination / "data/asset-map.js").write_text(
        "window.CLOCK_MISSING_ASSETS=" + json.dumps(missing) + ";\n"
    )
    # Small indices are tracked metadata, even in a fresh clone without asset downloads.
    range_index = read_json(CATALOG / "range-index.json")
    range_index = {
        dataset: entry
        for dataset, entry in range_index.items()
        if not omitted_path(entry["script"], omitted)
    }
    target = destination / "data/range-explorer"
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.js").write_text(
        "window.CLOCK_RANGE_INDEX=" + json.dumps(range_index) + ";\n"
    )
    # Shared English footer for the explorer and Help.
    footer = Template((ROOT / "web/partials/footer.html").read_text())
    footer_labels = {
        "tagline": "Open science for developmental biology.",
        "project_links": "Project links",
        "contribute": "Contribute",
        "cite": "Cite",
        "copy_citation": "Copy citation",
        "copied": "Copied",
        "copy_manual": "Select and copy the citation below.",
        "citation_label": "Citation text",
    }
    citation = escape(formatted_citation(ROOT / "CITATION.cff"))
    license_title, _, license_body = (
        (ROOT / "LICENSE").read_text().strip().partition("\n\n")
    )
    license_markup = "\n".join(
        "<p>" + escape(" ".join(paragraph.splitlines())) + "</p>"
        for paragraph in license_body.split("\n\n")
    )
    pages = ["index.html", "help.en.html", "license.html"]
    if tutorial_cases:
        pages.append("tutorials.html")
        tutorial_assets = destination / "assets"
        tutorial_assets.mkdir(exist_ok=True)
        (tutorial_assets / "tutorial-cases.js").write_text(
            "window.CLOCK_TUTORIAL_CASES=" + json.dumps(tutorial_cases) + ";\n"
        )
        shutil.copy2(
            ROOT / "web/tutorial/batch-workflow.png",
            tutorial_assets / "batch-workflow.png",
        )
        bundle(ROOT / "web/src/tutorial.js", tutorial_assets / "tutorial.js", minify)
        bundle(
            ROOT / "web/styles/tutorial.css", tutorial_assets / "tutorial.css", minify
        )
    for name in pages:
        labels = {field: escape(value) for field, value in footer_labels.items()}
        labels["citation_text"] = citation
        page = (ROOT / "web" / name).read_text()
        if "tutorials.html" in pages:
            page = page.replace("<body ", '<body data-tutorials="available" ', 1)
        if name == "license.html":
            page = page.replace("<!-- license-title -->", escape(license_title))
            page = page.replace("<!-- license-text -->", license_markup)
        page = page.replace("<!-- site-footer -->", footer.substitute(labels))
        (destination / name).write_text(page)
        if name == "index.html" and local_batch:
            review_page = (
                page.replace('data-page="app"', 'data-page="review"', 1)
                .replace(
                    "<title>Clock Explorer</title>",
                    "<title>Local review · Clock Explorer</title>",
                    1,
                )
                .replace('src="data/data.js"', 'src="data/review-data.js"', 1)
                .replace('src="data/videos.js"', 'src="data/review-videos.js"', 1)
            )
            evidence_dir = local_batch.parent / "review-evidence"
            if published_ids is None and (evidence_dir / "index.html").is_file():
                shutil.copytree(evidence_dir, destination / "review-evidence")
                review_page = review_page.replace(
                    '<section id="kymographs"',
                    '<p><a href="review-evidence/index.html">View expression-domain maps and paired embryo figures</a></p>\n'
                    '      <section id="kymographs"',
                    1,
                )
            (destination / "review.html").write_text(review_page)
    shutil.copy2(ROOT / "CITATION.cff", destination / "CITATION.cff")
    shutil.copy2(ROOT / "LICENSE", destination / "LICENSE.txt")
    shutil.copy2(
        ROOT / "docs" / "THIRD_PARTY_NOTICES.md",
        destination / "THIRD_PARTY_NOTICES.md",
    )
    shutil.copytree(ROOT / "web/brand", destination / "brand")
    # Existing shared/bookmarked Help URLs now open the English page.
    for legacy in ("README.en.html", "README.html", "help.zh.html"):
        shutil.copy2(destination / "help.en.html", destination / legacy)
    for name, source in [
        ("app.js", "web/src/entry.js"),
        ("header.js", "web/src/site-header.js"),
        ("site.css", "web/styles/site.css"),
    ]:
        bundle(ROOT / source, destination / "assets" / name, minify)
    (destination / "404.html").write_text(
        '<!doctype html><html lang="en"><title>Not found</title><h1>Page not found</h1><a href="/">Clock Explorer</a></html>'
    )
    (destination / "_headers").write_text(
        "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n  Cache-Control: public, max-age=0, must-revalidate\n"
    )
    (destination / "_redirects").write_text("\n".join(redirects) + "\n")
    write_json(
        destination / "build-info.json",
        {
            "version": read_json(ROOT / "package.json")["version"],
            "local_media": local_media,
            "local_assets": copied,
            "remote_assets": len(missing),
        },
    )
    print(
        f"Built {destination.relative_to(ROOT)}: {copied} local research assets, {len(missing)} source fallbacks."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-minify", action="store_true")
    parser.add_argument(
        "--local-runs", action="store_true", help="Include verified local pilot cards"
    )
    parser.add_argument(
        "--local-batch",
        type=Path,
        help="Preview a local card manifest separately at review.html",
    )
    parser.add_argument(
        "--local-media",
        action="store_true",
        help="Include private media in .local/preview",
    )
    options = parser.parse_args()
    build(
        options.output,
        not options.no_minify,
        options.local_runs,
        options.local_batch,
        options.local_media,
    )

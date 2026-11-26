# SPDX-License-Identifier: MIT
"""Project the research catalogue into a build without private media."""

PUBLIC_ORIGIN = "https://segmentation-clock-explorer.pages.dev/"


def omitted_path(value, omitted):
    if not isinstance(value, str):
        return False
    path = value.removeprefix(PUBLIC_ORIGIN).split("?", 1)[0].split("#", 1)[0]
    return path.lstrip("/") in omitted


def remove_omitted_references(value, omitted):
    """Prune file fields and old hosted aliases from generated catalogues."""
    if isinstance(value, dict):
        for key, item in list(value.items()):
            if omitted_path(item, omitted):
                del value[key]
            else:
                remove_omitted_references(item, omitted)
    elif isinstance(value, list):
        value[:] = [item for item in value if not omitted_path(item, omitted)]
        for item in value:
            remove_omitted_references(item, omitted)


def omit_method_media(method, omitted, source_links):
    if omitted_path(method.get("roi"), omitted):
        method.pop("roi_alt", None)
        if "public_sampling_note" in method:
            method["roi_note"] = method["public_sampling_note"]
    if omitted_path(method.get("result_preview"), omitted):
        method.pop("comparison", None)
    for field in ("reference_comparison", "review_comparisons"):
        if field not in method:
            continue
        comparisons = (
            method[field] if field == "review_comparisons" else [method[field]]
        )
        retain = []
        for comparison in comparisons:
            preview = comparison["preview"]
            if omitted_path(preview, omitted):
                if preview in source_links:
                    method.setdefault("figure_sources", []).append(
                        source_links[preview]
                    )
            else:
                retain.append(comparison)
        if not retain:
            del method[field]
        elif field == "review_comparisons":
            method[field] = retain


def omit_local_media(data, videos, omitted, source_links=None, *, public=True):
    source_links = source_links or {}
    for paper in data["papers"]:
        omit_method_media(paper.get("method_figure", {}), omitted, source_links)
        for medium in paper["media"]:
            if public and medium.get("source_link_only"):
                preview = medium.pop("url", None)
                if preview:
                    remove_omitted_references(paper, {preview})
        assets = []
        for asset in paper["assets"]:
            path = asset.get("local_path") or asset.get("url")
            if not omitted_path(path, omitted):
                assets.append(asset)
            elif path in source_links:
                assets.append(
                    {
                        **source_links[path],
                        "level": asset["level"],
                        "level_label": "Author data",
                        "source_only": True,
                        "status": "verified_content",
                        "evidence": "Available from the authors’ data collection.",
                        "license": "Redistribution permission unconfirmed",
                    }
                )
        paper["assets"] = assets
    for card in data["card_presentation"].values():
        omit_method_media(card.get("method_figure", {}), omitted, source_links)
        if omitted_path(card.get("sample_asset", {}).get("local_path"), omitted):
            del card["sample_asset"]
    for record in data["comparison"]["datasets"]:
        if omitted_path(record.get("roi"), omitted):
            record.pop("roi_note", None)
        input_path = record.get("input")
        if input_path in source_links:
            related = (
                data["card_presentation"]
                .get(record["id"], {})
                .get("detail_asset_paths", [])
            )
            detail_data = [item["path"] for item in record.get("detail_data", [])]
            seen = set()
            record["author_file_links"] = links = []
            for path in [input_path, *related, *detail_data]:
                source = source_links.get(path)
                if source and source["url"] not in seen:
                    links.append(source)
                    seen.add(source["url"])
            record["data_url"] = source_links[input_path]["url"]
        # Only available comparison panels and their associated downloads are rendered.
        for field, key in (("detail_figures", "preview"), ("detail_data", "path")):
            if field in record:
                record[field] = [
                    item
                    for item in record[field]
                    if not omitted_path(item[key], omitted)
                ]
    for paper in videos["papers"].values():
        for movie in paper["videos"]:
            if public and movie.get("public_source_url"):
                movie["source_url"] = movie["public_source_url"]
            if public and movie.get("local_only_overlay"):
                movie["sampling_roi_diagrams"] = movie.pop("sampling_rois", {})
                movie.pop("sampling_roi", None)
                movie.pop("roi", None)
                movie.pop("description", None)
            if not omitted_path(movie.get("src"), omitted):
                continue
            movie["availability"] = "external_only"
            for key in (
                "poster",
                "description",
                "playback_bytes",
                "playback_duration_seconds",
                "playback_fps",
                "playback_sha256",
                "sampling_rois",
                "sampling_roi_diagrams",
                "sampling_roi",
            ):
                movie.pop(key, None)
    remove_omitted_references(data, omitted)
    remove_omitted_references(videos, omitted)

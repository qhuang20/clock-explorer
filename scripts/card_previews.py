# SPDX-License-Identifier: MIT
"""Build card-only SVG copies; scientific plots and arrays stay unchanged."""

import hashlib
import re
from pathlib import Path
import xml.etree.ElementTree as ET

from project import asset_path

SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

# Physical SVG coordinates of the reviewed Masamizu card, in points. Numerical
# limits and units remain those already rendered in each source figure.
COMPACT_LAYOUT = {
    "name": "compact",
    "canvas": [316.8, 241.2],
    "axes": [50.688, 9.648, 210.45024, 192.96],
    "colorbar": [271.54512, 9.648, 7.7184, 192.96],
}


def _text(value):
    return " ".join(str(value).replace("–", "-").replace("—", "-").split())


def compact_svg(content, duplicate_text):
    root = ET.fromstring(content)
    labels = {_text(value) for value in duplicate_text if value}
    removed = []
    for parent in root.iter():
        for child in list(parent):
            if child.tag != f"{{{SVG}}}g" or not child.get("id", "").startswith(
                "text_"
            ):
                continue
            value = _text("".join(child.itertext()))
            if value in labels:
                removed.append(value)
                parent.remove(child)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), removed


def axes_bounds(axes):
    """Read Matplotlib's rectangular axes background, not the data image extent."""
    path = axes.find(f"{{{SVG}}}g/{{{SVG}}}path")
    if path is None:
        raise ValueError("Reviewed card SVG has no axes background")
    numbers = [
        float(v)
        for v in re.findall(r"[-+]?(?:\d*\.)?\d+(?:[eE][-+]?\d+)?", path.get("d", ""))
    ]
    if len(numbers) != 8 or not path.get("d", "").rstrip().lower().endswith("z"):
        raise ValueError("Reviewed card SVG needs rectangular Matplotlib axes")
    points = list(zip(numbers[::2], numbers[1::2]))
    xs, ys = sorted(set(numbers[::2])), sorted(set(numbers[1::2]))
    if len(xs) != 2 or len(ys) != 2 or set(points) != {(x, y) for x in xs for y in ys}:
        raise ValueError("Reviewed card axes background is not a rectangle")
    return [xs[0], ys[0], xs[1] - xs[0], ys[1] - ys[0]]


def flip_plot_y(content, axes_ids=("axes_1",)):
    """Reverse reviewed plot y axes, leaving text, time and color scales upright.

    This adapter targets Matplotlib's raster kymographs. Reflect the image and
    filled data patches/collections; relocate entire y ticks without mirroring
    their glyphs. Axis titles, x ticks and unselected colorbar axes stay intact.
    """
    root = ET.fromstring(content)
    for axes_id in axes_ids:
        axes = root.find(f".//{{{SVG}}}g[@id='{axes_id}']")
        if axes is None or axes.get("transform") or axes.get("data-flipped-y"):
            raise ValueError("Y reversal requires original reviewed axes: " + axes_id)
        _, top, _, height = axes_bounds(axes)
        total = 2 * top + height
        reflection = f"matrix(1 0 0 -1 0 {total:.12g})"
        for child in axes:
            name, ident = child.tag.rsplit("}", 1)[-1], child.get("id", "")
            if ident.startswith("matplotlib.axis_"):
                for tick in child:
                    if not tick.get("id", "").startswith("ytick_"):
                        continue
                    mark = tick.find(f".//{{{SVG}}}use[@y]")
                    if mark is None or tick.get("transform"):
                        raise ValueError("Unsupported y tick in " + axes_id)
                    delta = total - 2 * float(mark.get("y"))
                    tick.set("transform", f"translate(0 {delta:.12g})")
                continue
            if ident.startswith("text_"):
                continue  # Titles remain readable in their original position.
            if ident.startswith("patch_"):
                path = child.find(f"{{{SVG}}}path")
                # Existing open, unfilled patches are the reviewed axes spines.
                if path is not None and "fill: none" in path.get("style", ""):
                    continue
            elif name != "image" and not ident.startswith(
                (
                    "QuadMesh",
                    "PolyCollection",
                    "LineCollection",
                    "PathCollection",
                    "line2d_",
                )
            ):
                raise ValueError("Unsupported plot mark during y reversal: " + ident)
            child.set("transform", reflection + " " + child.get("transform", ""))
        axes.set("data-flipped-y", "true")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def align_plot_svg(content):
    """Present existing marks in one axis box; preserve text size and rotation.

    Affine placement changes the card viewport only. It does not interpolate the
    embedded image, recompute normalization, clip data or relabel coordinates.
    The original exported scientific SVG remains untouched.
    """
    root = ET.fromstring(content)
    for axes_id, key in [("axes_1", "axes"), ("axes_2", "colorbar")]:
        axes = root.find(f".//{{{SVG}}}g[@id='{axes_id}']")
        if axes is None or axes.get("transform"):
            raise ValueError("Unsupported reviewed card axes: " + axes_id)
        x, y, width, height = axes_bounds(axes)
        tx, ty, tw, th = COMPACT_LAYOUT[key]
        sx, sy = tw / width, th / height
        axes.set(
            "transform",
            f"matrix({sx:.12g} 0 0 {sy:.12g} {tx - sx * x:.12g} {ty - sy * y:.12g})",
        )
        # Cancel the parent scale around each text anchor, retaining its original
        # rotation and font metrics while its position follows the relocated axis.
        for label in axes.iter(f"{{{SVG}}}text"):
            lx, ly = float(label.get("x", "0")), float(label.get("y", "0"))
            # Some exports name only a local plotting font. Browser SVGs need
            # the same sans-serif fallback as the reviewed reference cards.
            style = label.get("style", "")
            if "font-family:" in style and "sans-serif" not in style:
                style = re.sub(
                    r"font-family:([^;]+)", r"font-family:\1, Arial, sans-serif", style
                )
                label.set("style", style)

            # Keep the physical gutter between unscaled glyphs and the axes.
            # Scaling a wide export's label offsets into a compact canvas would
            # push y labels into ticks, even though the text itself stays 9 pt.
            def placed(value, start, extent, target, target_extent):
                if value < start:
                    return target + value - start
                if value > start + extent:
                    return target + target_extent + value - start - extent
                return target + (value - start) * target_extent / extent

            nx = placed(lx, x, width, tx, tw)
            ny = placed(ly, y, height, ty, th)
            shift_x = (nx - (tx + sx * (lx - x))) / sx
            shift_y = (ny - (ty + sy * (ly - y))) / sy
            inverse = f"matrix({1 / sx:.12g} 0 0 {1 / sy:.12g} {lx - lx / sx + shift_x:.12g} {ly - ly / sy + shift_y:.12g})"
            label.set("transform", inverse + " " + label.get("transform", ""))
    width, height = COMPACT_LAYOUT["canvas"]
    root.set("width", f"{width:g}pt")
    root.set("height", f"{height:g}pt")
    root.set("viewBox", f"0 0 {width:g} {height:g}")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def annotate_polarity(content, polarity, bounds=None):
    """Add reviewed anatomical direction cues without changing plot geometry.

    Letters indicate anterior/posterior sides, not verified tissue endpoints.
    A question mark makes provisional image-polarity inferences visible.
    """
    if {polarity.get("top"), polarity.get("bottom")} != {"A", "P"}:
        raise ValueError("AP polarity needs opposite A/P sides")
    status = polarity.get("status")
    if status not in {"supported", "inferred"}:
        raise ValueError("AP polarity needs an explicit evidence status")
    root = ET.fromstring(content)
    if bounds is None:
        axes = root.find(f".//{{{SVG}}}g[@id='axes_1']")
        if axes is None or axes.get("transform"):
            raise ValueError("AP labels need known displayed axis bounds")
        bounds = axes_bounds(axes)
    x, y, _, height = bounds
    group = ET.SubElement(
        root,
        f"{{{SVG}}}g",
        {
            "id": "axis-polarity",
            "style": "font-family:Arial,DejaVu Sans,sans-serif;font-size:9px;font-weight:600;text-anchor:middle;fill:"
            + ("#866f48" if status == "inferred" else "#6257d0"),
        },
    )
    title = ET.SubElement(group, f"{{{SVG}}}title")
    title.text = "A: anterior; P: posterior. " + (
        "Question marks denote provisional image polarity, not anatomical registration."
        if status == "inferred"
        else "Letters indicate polarity, not exact anatomical boundaries."
    )
    for side, baseline in [("top", y + 8), ("bottom", y + height - 1)]:
        label = ET.SubElement(
            group,
            f"{{{SVG}}}text",
            {
                "x": f"{max(5, x - 42):.6g}",
                "y": f"{baseline:.6g}",
                "data-side": side,
            },
        )
        label.text = polarity[side] + ("?" if status == "inferred" else "")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def render_card_previews(data, destination):
    papers = {paper["id"]: paper for paper in data["papers"]}
    records = list(data["comparison"]["datasets"])
    seen = {r.get("paper_id", r["id"]) for r in records}
    for paper in papers.values():
        if paper["id"] not in seen and paper.get("method_figure", {}).get(
            "card_preview"
        ):
            records.append(
                {
                    "id": paper["id"],
                    "full_preview": paper["method_figure"]["card_preview"],
                    "reporter": paper["reporter_short"],
                }
            )
    output = Path(destination) / "figures/cards"
    output.mkdir(parents=True, exist_ok=True)
    result = {}
    for record in records:
        source = record["full_preview"]
        path = asset_path(source)
        if path.suffix != ".svg" or not path.is_file():
            continue  # A fresh clone can still use the registered source fallback.
        original = path.read_bytes()
        content, removed = compact_svg(
            original,
            [record.get("reporter"), record.get("card_title"), record.get("label")],
        )
        presentation = data.get("card_presentation", {}).get(record["id"], {})
        layout = presentation.get("plot_layout")
        flip_y = presentation.get("flip_y", False)
        if flip_y:
            content = flip_plot_y(content, presentation.get("plot_axes", ["axes_1"]))
        if layout:
            if layout != "compact":
                raise ValueError("Unknown card plot layout: " + layout)
            content = align_plot_svg(content)
        polarity = presentation.get("axis_polarity")
        if polarity:
            content = annotate_polarity(
                content, polarity, COMPACT_LAYOUT["axes"] if layout else None
            )
        digest = hashlib.sha256(content).hexdigest()
        relative = f"figures/cards/{record['id']}-{digest[:12]}.svg"
        (Path(destination) / relative).write_bytes(content)
        result[record["id"]] = {
            "preview": relative,
            "source": source,
            "source_sha256": hashlib.sha256(original).hexdigest(),
            "sha256": digest,
            "removed_duplicate_text": removed,
            "transformation": (
                "Card-only duplicate title/caption removal and axis-box placement; embedded images, paths, masks, tick values and units preserved; text size retained."
                if layout
                else "Card-only duplicate title/caption removal; image, path, tick, colorbar and mask nodes unchanged."
            ),
            **({"layout": COMPACT_LAYOUT} if layout else {}),
            **({"flip_y": True} if flip_y else {}),
            **(
                {"axis_polarity": {k: polarity[k] for k in ("top", "bottom", "status")}}
                if polarity
                else {}
            ),
        }
        if polarity:
            result[record["id"]]["transformation"] += (
                " Added evidence-qualified A/P direction labels in the existing margin."
            )
        if flip_y:
            result[record["id"]]["transformation"] += (
                " Reversed plot data and y-tick positions together; time, text and colorbar direction unchanged."
            )
        method = presentation.get("method_figure", {})
        for variant, config, source_key in [
            ("method", method, "result_preview"),
            ("reference", method.get("reference_comparison", {}), "preview"),
        ]:
            variant_polarity = config.get("axis_polarity")
            variant_flip = config.get("flip_y", False)
            if not (variant_polarity or variant_flip) or not config.get(source_key):
                continue
            variant_source = asset_path(config[source_key])
            if variant_source.suffix != ".svg" or not variant_source.is_file():
                continue
            variant_original = variant_source.read_bytes()
            variant_content = variant_original
            if variant_flip:
                variant_content = flip_plot_y(
                    variant_content, config.get("plot_axes", ["axes_1"])
                )
            if variant_polarity:
                variant_content = annotate_polarity(variant_content, variant_polarity)
            variant_digest = hashlib.sha256(variant_content).hexdigest()
            relative = (
                f"figures/cards/{record['id']}-{variant}-{variant_digest[:12]}.svg"
            )
            (Path(destination) / relative).write_bytes(variant_content)
            result[record["id"]].update(
                {
                    f"{variant}_preview": relative,
                    f"{variant}_source": config[source_key],
                    f"{variant}_source_sha256": hashlib.sha256(
                        variant_original
                    ).hexdigest(),
                    f"{variant}_flip_y": variant_flip,
                }
            )
    return result

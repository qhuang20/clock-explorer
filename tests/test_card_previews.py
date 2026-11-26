# SPDX-License-Identifier: MIT
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from card_previews import compact_svg, SVG


class CardPreviewTests(unittest.TestCase):
    def test_removing_duplicate_labels_preserves_plot_marks_axes_and_masks(self):
        source = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
          <g id="axes_1"><path d="M1 2L3 4"/><image href="data:image/png;base64,AAAA"/>
          <clipPath id="clip"><rect x="1" y="2" width="3" height="4"/></clipPath>
          <g id="text_1"><text>Hes1-Ub1-Luc</text></g>
          <g id="text_2"><text>Image y (px)</text></g>
          <g id="text_3"><text>Video-derived ROI</text></g></g></svg>"""
        output, removed = compact_svg(source, ["Hes1-Ub1-Luc", "Video-derived ROI"])
        self.assertEqual(len(removed), 2)
        before, after = ET.fromstring(source), ET.fromstring(output)
        self.assertEqual(before.attrib, after.attrib)
        for tag in ["path", "image", "clipPath", "rect"]:
            self.assertEqual(
                [x.attrib for x in before.iter(f"{{{SVG}}}{tag}")],
                [x.attrib for x in after.iter(f"{{{SVG}}}{tag}")],
            )
        self.assertIn("Image y (px)", output.decode())
        self.assertNotIn("Hes1-Ub1-Luc", output.decode())


class AlignedCardPreviewTests(unittest.TestCase):
    # Deliberately different canvas/plot geometry, a nontrivial mask and a rotated
    # label exercise placement without depending on optional downloaded assets.
    source = b"""<svg xmlns="http://www.w3.org/2000/svg" width="200pt" height="170pt" viewBox="0 0 200 170">
      <g id="axes_1"><g id="patch_2"><path d="M 20 130 L 120 130 L 120 30 L 20 30 z"/></g>
        <image href="data:image/png;base64,AAAA" x="20" y="30" width="100" height="100"/>
        <path d="M 20 80 L 120 80" clip-path="url(#mask)"/>
        <g id="text_1"><text x="10" y="80" transform="rotate(-90 10 80)" style="font-size:9px">Distance (um)</text></g>
        <text x="20" y="145">0</text><text x="120" y="145">10</text></g>
      <g id="axes_2"><g id="patch_5"><path d="M 140 130 L 145 130 L 145 30 L 140 30 z"/></g>
        <image href="data:image/png;base64,BBBB" x="140" y="30" width="5" height="100"/>
        <text x="150" y="80">0.5</text></g>
      <defs><clipPath id="mask"><rect x="20" y="40" width="90" height="80"/></clipPath></defs></svg>"""

    def test_axis_boxes_align_without_changing_data_masks_or_label_metrics(self):
        import re
        from card_previews import align_plot_svg, axes_bounds, COMPACT_LAYOUT

        before = ET.fromstring(self.source)
        after = ET.fromstring(align_plot_svg(self.source))
        self.assertEqual(after.get("viewBox"), "0 0 316.8 241.2")
        for tag in ["image", "path", "clipPath", "rect"]:
            self.assertEqual(
                [n.attrib for n in before.iter(f"{{{SVG}}}{tag}")],
                [n.attrib for n in after.iter(f"{{{SVG}}}{tag}")],
            )
        self.assertEqual(
            [n.text for n in before.iter(f"{{{SVG}}}text")],
            [n.text for n in after.iter(f"{{{SVG}}}text")],
        )
        for axes_id, key in [("axes_1", "axes"), ("axes_2", "colorbar")]:
            axes = after.find(f".//{{{SVG}}}g[@id='{axes_id}']")
            a, b, c, d, e, f = map(
                float,
                re.search(r"matrix\(([^)]+)\)", axes.get("transform")).group(1).split(),
            )
            x, y, w, h = axes_bounds(axes)
            actual = [a * x + e, d * y + f, a * w, d * h]
            for value, expected in zip(actual, COMPACT_LAYOUT[key]):
                self.assertAlmostEqual(value, expected, places=7)
            self.assertEqual((b, c), (0, 0))
            for label in axes.iter(f"{{{SVG}}}text"):
                inverse = list(
                    map(
                        float,
                        re.search(r"matrix\(([^)]+)\)", label.get("transform"))
                        .group(1)
                        .split(),
                    )
                )
                # Parent placement times text correction has identity scale,
                # including for the original rotated distance label.
                self.assertAlmostEqual(a * inverse[0], 1, places=9)
                self.assertAlmostEqual(d * inverse[3], 1, places=9)
                lx, ly = float(label.get("x")), float(label.get("y"))
                # Labels outside the source axis keep their physical gap;
                # numeric anchors inside it follow the data placement.
                px = a * (inverse[0] * lx + inverse[4]) + e
                py = d * (inverse[3] * ly + inverse[5]) + f
                tx, ty, tw, th = COMPACT_LAYOUT[key]
                if lx < x:
                    self.assertAlmostEqual(tx - px, x - lx, places=7)
                elif lx > x + w:
                    self.assertAlmostEqual(px - tx - tw, lx - x - w, places=7)
                else:
                    self.assertAlmostEqual(px, a * lx + e, places=7)
                if ly < y:
                    self.assertAlmostEqual(ty - py, y - ly, places=7)
                elif ly > y + h:
                    self.assertAlmostEqual(py - ty - th, ly - y - h, places=7)
                else:
                    self.assertAlmostEqual(py, d * ly + f, places=7)
        self.assertIn("rotate(-90 10 80)", ET.tostring(after).decode())

    def test_alignment_is_opt_in_and_source_file_stays_unchanged(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from card_previews import render_card_previews

        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.svg"
            source.write_bytes(self.source)
            data = {
                "papers": [],
                "comparison": {
                    "datasets": [
                        {"id": key, "full_preview": "source.svg"}
                        for key in ["reviewed", "other"]
                    ]
                },
                "card_presentation": {"reviewed": {"plot_layout": "compact"}},
            }
            with patch("card_previews.asset_path", return_value=source):
                previews = render_card_previews(data, Path(tmp) / "out")
            self.assertEqual(source.read_bytes(), self.source)
            self.assertIn("layout", previews["reviewed"])
            self.assertNotIn("layout", previews["other"])
            other = ET.parse(Path(tmp) / "out" / previews["other"]["preview"]).getroot()
            self.assertEqual(other.get("viewBox"), "0 0 200 170")
            self.assertIsNone(
                other.find(f".//{{{SVG}}}g[@id='axes_1']").get("transform")
            )

    def test_unsupported_plot_fails_instead_of_guessing_bounds(self):
        from card_previews import align_plot_svg

        with self.assertRaisesRegex(ValueError, "axes"):
            align_plot_svg(b'<svg xmlns="http://www.w3.org/2000/svg"/>')


class AxisPolarityTests(unittest.TestCase):
    def test_provisional_and_supported_polarities_keep_distinct_display_order(self):
        from card_previews import annotate_polarity, COMPACT_LAYOUT, align_plot_svg

        source = align_plot_svg(AlignedCardPreviewTests.source)
        for top, bottom, status in [("A", "P", "inferred"), ("P", "A", "supported")]:
            with self.subTest(status=status):
                output = annotate_polarity(
                    source,
                    {"top": top, "bottom": bottom, "status": status},
                    COMPACT_LAYOUT["axes"],
                )
                before, after = ET.fromstring(source), ET.fromstring(output)
                self.assertEqual(before.attrib, after.attrib)
                # Annotation must not alter scientific marks, masks or transforms.
                for tag in ["image", "path", "clipPath", "rect"]:
                    self.assertEqual(
                        [n.attrib for n in before.iter(f"{{{SVG}}}{tag}")],
                        [n.attrib for n in after.iter(f"{{{SVG}}}{tag}")],
                    )
                for axes_id in ["axes_1", "axes_2"]:
                    selector = f".//{{{SVG}}}g[@id='{axes_id}']"
                    self.assertEqual(
                        ET.tostring(before.find(selector)),
                        ET.tostring(after.find(selector)),
                    )
                letters = after.findall(
                    f".//{{{SVG}}}g[@id='axis-polarity']/{{{SVG}}}text"
                )
                suffix = "?" if status == "inferred" else ""
                self.assertEqual(
                    [n.text for n in letters], [top + suffix, bottom + suffix]
                )
                self.assertLess(float(letters[0].get("y")), float(letters[1].get("y")))
                self.assertTrue(
                    all(float(n.get("x")) < COMPACT_LAYOUT["axes"][0] for n in letters)
                )

    def test_comparison_declares_its_own_direction_without_replacing_sources(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from card_previews import render_card_previews

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "original.svg"
            path.write_bytes(AlignedCardPreviewTests.source)
            data = {
                "papers": [],
                "comparison": {
                    "datasets": [{"id": "case", "full_preview": "original.svg"}]
                },
                "card_presentation": {
                    "case": {
                        "plot_layout": "compact",
                        "axis_polarity": {
                            "top": "P",
                            "bottom": "A",
                            "status": "supported",
                        },
                        "method_figure": {
                            "result_preview": "original.svg",
                            "axis_polarity": {
                                "top": "A",
                                "bottom": "P",
                                "status": "supported",
                            },
                        },
                    }
                },
            }
            with patch("card_previews.asset_path", return_value=path):
                entry = render_card_previews(data, Path(tmp) / "out")["case"]

            def letters(file):
                tree = ET.parse(Path(tmp) / "out" / file)
                return [
                    n.text
                    for n in tree.findall(
                        f".//{{{SVG}}}g[@id='axis-polarity']/{{{SVG}}}text"
                    )
                ]

            self.assertEqual(letters(entry["preview"]), ["P", "A"])
            self.assertEqual(letters(entry["method_preview"]), ["A", "P"])
            self.assertEqual(path.read_bytes(), AlignedCardPreviewTests.source)

    def test_missing_status_or_non_anatomical_sides_cannot_be_silently_labeled_ap(self):
        from card_previews import annotate_polarity

        for invalid in [
            {"top": "A", "bottom": "P"},
            {"top": "A", "bottom": "P", "status": "unverified"},
            {"top": "center", "bottom": "periphery", "status": "supported"},
        ]:
            with self.subTest(polarity=invalid), self.assertRaises(ValueError):
                annotate_polarity(AlignedCardPreviewTests.source, invalid)


class PlotYReversalTests(unittest.TestCase):
    source = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 250">
      <g id="axes_1"><g id="patch_2"><path d="M50 210 L250 210 L250 10 L50 10 z" style="fill:#eee"/></g>
        <image href="data:image/png;base64,MISSING_AND_SIGNAL" x="50" y="10" width="200" height="200"/>
        <g id="patch_3"><path d="M50 210 L50 10" style="fill: none; stroke:#888"/></g>
        <g id="patch_4"><path d="M50 210 L250 210" style="fill: none; stroke:#888"/></g>
        <g id="patch_5"><path d="M50 10 L70 10 L70 60 L50 60 z" style="fill:url(#hatch)"/></g>
        <g id="matplotlib.axis_1"><g id="xtick_1"><use x="50" y="210"/>
          <text x="50" y="225">0</text></g><text x="150" y="240">Time (h)</text></g>
        <g id="matplotlib.axis_2"><g id="ytick_1"><g><use x="50" y="10"/></g>
          <g><text x="43" y="13" style="font-size:9px">0</text></g></g>
          <g id="ytick_2"><g><use x="50" y="210"/></g>
          <g><text x="43" y="213" style="font-size:9px">200</text></g></g>
          <g><text x="20" y="110" transform="rotate(-90 20 110)">Distance (um)</text></g></g>
        <g id="text_9"><text x="50" y="6">Intensity</text></g></g>
      <g id="axes_2"><g id="patch_6"><path d="M270 210 L278 210 L278 10 L270 10 z"/></g>
        <image href="data:image/png;base64,COLORBAR_HIGH_AT_TOP" x="270" y="10" width="8" height="200"/>
        <text x="280" y="13">1.0</text><text x="280" y="213">0.0</text></g>
      <defs><clipPath id="mask"><rect x="50" y="10" width="200" height="70"/></clipPath></defs></svg>"""

    def test_reversal_moves_signal_missing_data_and_ticks_but_keeps_text_time_and_colorbar(
        self,
    ):
        from card_previews import flip_plot_y
        import re

        before, after = (
            ET.fromstring(self.source),
            ET.fromstring(flip_plot_y(self.source)),
        )

        def group(root, ident):
            return root.find(f".//{{{SVG}}}g[@id='{ident}']")

        self.assertEqual(before.attrib, after.attrib)
        for ident in ["matplotlib.axis_1", "axes_2", "patch_3", "patch_4", "text_9"]:
            self.assertEqual(
                ET.tostring(group(before, ident)), ET.tostring(group(after, ident))
            )
        old_image = group(before, "axes_1").find(f"{{{SVG}}}image")
        image = group(after, "axes_1").find(f"{{{SVG}}}image")
        self.assertEqual(old_image.get("href"), image.get("href"))
        matrix = list(
            map(
                float,
                re.search(r"matrix\(([^)]+)\)", image.get("transform"))
                .group(1)
                .split(),
            )
        )
        self.assertEqual(matrix, [1, 0, 0, -1, 0, 220])
        self.assertEqual(matrix[3] * 10 + matrix[5], 210)
        self.assertEqual(matrix[3] * 210 + matrix[5], 10)
        for ident, old_y, expected, delta in [
            ("ytick_1", 10, 210, 200),
            ("ytick_2", 210, 10, -200),
        ]:
            tick = group(after, ident)
            self.assertEqual(tick.get("transform"), f"translate(0 {delta})")
            self.assertEqual(old_y + delta, expected)
            # Labels are translated with ticks, not mirrored or numerically replaced.
            self.assertEqual(
                [n.attrib for n in group(before, ident).iter(f"{{{SVG}}}text")],
                [n.attrib for n in tick.iter(f"{{{SVG}}}text")],
            )
            self.assertEqual(
                [n.text for n in group(before, ident).iter(f"{{{SVG}}}text")],
                [n.text for n in tick.iter(f"{{{SVG}}}text")],
            )
        self.assertTrue(
            group(after, "patch_5").get("transform").startswith("matrix(1 0 0 -1")
        )
        self.assertEqual(
            [n.attrib for n in before.iter(f"{{{SVG}}}clipPath")],
            [n.attrib for n in after.iter(f"{{{SVG}}}clipPath")],
        )

    def test_reversal_rejects_stale_pretransformed_figures(self):
        from card_previews import flip_plot_y

        with self.assertRaisesRegex(ValueError, "original reviewed axes"):
            flip_plot_y(flip_plot_y(self.source))

    def test_builder_keeps_reversal_and_polarity_consistent_without_changing_source(
        self,
    ):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from card_previews import render_card_previews

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.svg"
            path.write_bytes(self.source)
            data = {
                "papers": [],
                "comparison": {
                    "datasets": [{"id": "case", "full_preview": "source.svg"}]
                },
                "card_presentation": {
                    "case": {
                        "plot_layout": "compact",
                        "flip_y": True,
                        "axis_polarity": {
                            "top": "A",
                            "bottom": "P",
                            "status": "supported",
                        },
                    }
                },
            }
            with patch("card_previews.asset_path", return_value=path):
                entry = render_card_previews(data, Path(tmp) / "out")["case"]
            self.assertTrue(entry["flip_y"])
            tree = ET.parse(Path(tmp) / "out" / entry["preview"])
            self.assertEqual(
                [
                    n.text
                    for n in tree.findall(
                        f".//{{{SVG}}}g[@id='axis-polarity']/{{{SVG}}}text"
                    )
                ],
                ["A", "P"],
            )
            self.assertEqual(
                tree.find(f".//{{{SVG}}}g[@id='axes_1']").get("data-flipped-y"), "true"
            )
            self.assertEqual(path.read_bytes(), self.source)

# SPDX-License-Identifier: MIT
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from publication import omit_local_media
from project import CATALOG, asset_path, read_json, runtime_catalog


class ProjectTests(unittest.TestCase):
    def test_asset_paths_cannot_escape(self):
        for value in ("../../secret", "/etc/passwd", ""):
            with self.assertRaises(ValueError):
                asset_path(value)
        self.assertTrue(
            str(asset_path("figures/a.svg")).endswith("assets/figures/a.svg")
        )

    def test_generated_comparison_is_derived_without_duplicate_paper(self):
        data = runtime_catalog()
        self.assertEqual(len(data["papers"]), len({p["id"] for p in data["papers"]}))
        miao = [
            c
            for c in data["comparison"]["datasets"]
            if c.get("paper_id", c["id"]) == "miao-2023"
        ]
        self.assertEqual({c["system_label"] for c in miao}, {"Somitoid", "Segmentoid"})
        self.assertEqual({c["kind"] for c in miao}, {"matrix", "video_lut"})

    def test_liu_public_catalog_preserves_the_plot_and_links_to_the_source(self):
        dataset = "liu-2024-hes7-video5"
        data = runtime_catalog()
        videos = read_json(CATALOG / "videos.json")
        manifest = read_json(CATALOG / "assets.json")["files"]
        local_media = {
            entry["path"]
            for entry in manifest
            if entry["paper"] == "liu-2024" and entry.get("local_only")
        }
        record = next(
            record
            for record in data["comparison"]["datasets"]
            if record["id"] == dataset
        )
        method = data["card_presentation"][dataset]["method_figure"]
        movie = videos["papers"]["liu-2024"]["videos"][0]
        self.assertEqual(
            local_media,
            {
                movie["src"],
                movie["poster"],
                method["roi"],
                method["reference_comparison"]["preview"],
            },
        )
        plot, matrix, source = (
            record["full_preview"],
            record["input"],
            movie["source_url"],
        )
        unrelated = deepcopy(videos["papers"]["makwana-2025"])
        omit_local_media(data, videos, local_media)
        self.assertNotIn("roi", record)
        self.assertNotIn("roi", method)
        self.assertNotIn("reference_comparison", method)
        self.assertNotIn("src", movie)
        self.assertNotIn("poster", movie)
        self.assertEqual(movie["availability"], "external_only")
        self.assertEqual(movie["source_url"], source)
        self.assertEqual(record["full_preview"], plot)
        self.assertEqual(record["input"], matrix)
        self.assertEqual(videos["papers"]["makwana-2025"], unrelated)

    def test_public_catalog_withholds_author_file_copies_and_restricted_panels(self):
        data = runtime_catalog()
        videos = read_json(CATALOG / "videos.json")
        manifest = read_json(CATALOG / "assets.json")["files"]
        withheld = {entry["path"] for entry in manifest if entry.get("local_only")}
        source_links = {
            entry["path"]: entry["source_link"]
            for entry in manifest
            if entry["path"] in withheld and entry.get("source_link")
        }
        plots = {r["id"]: r["full_preview"] for r in data["comparison"]["datasets"]}

        omit_local_media(data, videos, withheld, source_links)

        records = {record["id"]: record for record in data["comparison"]["datasets"]}
        self.assertEqual({key: r["full_preview"] for key, r in records.items()}, plots)
        for key, expected_links in {
            "chhabra-2026": 2,
            "chhabra-2026-22c": 1,
            "chhabra-2026-32c": 1,
            "miao-2023-segmentoid": 1,
            "miao-2023-segmentoid-mesp2": 1,
        }.items():
            self.assertNotIn("input", records[key])
            self.assertEqual(len(records[key]["author_file_links"]), expected_links)
        eck = data["card_presentation"]["eck-2026-fig4c"]["method_figure"]
        self.assertEqual(
            [item["label"] for item in eck["review_comparisons"]],
            ["Compare display scales"],
        )
        self.assertEqual(eck["figure_sources"][0]["label"], "View published Figure 4C")
        for paper_id in ("delaune-2012", "soroldoni-2014", "jiang-2000"):
            paper = next(p for p in data["papers"] if p["id"] == paper_id)
            self.assertNotIn("url", paper["media"][0])
            self.assertTrue(paper["media"][0]["source_url"].startswith("https://"))
        delaune = next(p for p in data["papers"] if p["id"] == "delaune-2012")
        self.assertNotIn("roi_preview", delaune["kymograph"])
        movie = next(
            v
            for v in videos["papers"]["delaune-2012"]["videos"]
            if v["id"] == "movie-s1"
        )
        self.assertNotIn("src", movie)
        self.assertEqual(movie["source_url"], movie["public_source_url"])
        self.assertTrue(movie["license"])

    def test_sonnen_public_movies_keep_licensed_copies_and_use_roi_diagrams(self):
        data = runtime_catalog()
        videos = read_json(CATALOG / "videos.json")
        movies = videos["papers"]["sonnen-2018"]["videos"]
        private_movies = deepcopy(movies)
        omit_local_media(data, videos, {movie["poster"] for movie in movies})
        for movie, private_movie in zip(movies, private_movies):
            with self.subTest(movie=movie["id"]):
                self.assertEqual(movie["src"], private_movie["src"])
                self.assertEqual(movie["source_sha256"], movie["playback_sha256"])
                self.assertEqual(movie["reuse_license"]["label"], "CC BY-NC-ND 4.0")
                self.assertNotIn("poster", movie)
                self.assertNotIn("sampling_rois", movie)
                self.assertEqual(
                    movie["sampling_roi_diagrams"], private_movie["sampling_rois"]
                )
                self.assertNotIn("sampling_roi_diagrams", private_movie)

    def test_public_playback_assets_have_source_specific_credit(self):
        manifest = read_json(CATALOG / "assets.json")["files"]
        videos = read_json(CATALOG / "videos.json")["papers"]
        playback = {
            entry["path"]
            for entry in manifest
            if entry["group"] != "sources"
            and not entry.get("local_only")
            and Path(entry["path"]).suffix in {".mp4", ".mov", ".avi"}
        }
        credited = {
            video["src"]
            for paper in videos.values()
            for video in paper["videos"]
            if video.get("src")
            and video.get("reuse_license", {}).get("url", "").startswith("https://")
            and video["reuse_license"].get("credit")
        }
        self.assertFalse(playback - credited, sorted(playback - credited))


if __name__ == "__main__":
    unittest.main()

"""Re-read original movie and recompute means using the exported ROI polygon."""

import json
import av
import numpy as np
from PIL import Image


def review(src, out, job):
    roi = json.loads((out / "overlay.json").read_text())
    with np.load(out / "kymograph.npz") as saved:
        matrix = saved["intensity"]
        assert np.array_equal(saved["time_h"], job["time_h"])
        assert np.allclose(
            saved["space_um"],
            np.arange(len(matrix)) * job.get("bar_um", 200) / job["bar_pixels"],
        )
    with av.open(str(out / "playback.mp4")) as playback:
        actual_pts = [float(frame.time) for frame in playback.decode(video=0)]
    assert np.allclose(actual_pts, roi["frame_starts_s"])
    assert len(actual_pts) == len(roi["frames"]) == matrix.shape[1] == job["frames"]
    max_error = 0.0
    checked = 0
    min_support = matrix.shape[0]
    if "final_tail_reference" in job:
        from scipy.interpolate import PchipInterpolator

        anterior_tips = PchipInterpolator(
            job["keyframes"], np.asarray(job["path_xy"])[:, -1], axis=0
        )(np.arange(job["frames"]))
    with av.open(str(src)) as source:
        for i, frame in enumerate(source.decode(video=0)):
            im = frame.to_ndarray(format="rgb24").astype(float)
            if "crop_xywh" in job:
                left, top, width, height = job["crop_xywh"]
                im = im[top : top + height, left : left + width]
            fp = roi["frames"][i]
            assert i == fp["index"]
            polygon = np.array(fp["bands"][0])
            n = len(polygon) // 2
            low, high = polygon[:n], polygon[n:][::-1]
            assert np.allclose((low + high) / 2, fp["lines"][0], atol=0.00011)
            assert np.allclose(np.linalg.norm(high - low, axis=1), 12, atol=0.0002)
            xy = (
                low[:, None]
                + (high - low)[:, None] * np.linspace(0, 1, 13)[None, :, None]
            )
            x, y = xy[:, :, 0], xy[:, :, 1]
            ix = x.astype(int)
            iy = y.astype(int)
            assert (
                x.min() >= 0
                and y.min() > 9
                and ix.max() + 1 < im.shape[1]
                and iy.max() + 1 < im.shape[0]
            )
            fracx = x - ix
            fracy = y - iy
            if job.get("channel") == "magenta":
                raw = im[:, :, [0, 2]].mean(axis=2)
            elif job["role"] == "axial":
                raw = np.maximum(0, im[:, :, 1] - 0.5 * (im[:, :, 0] + im[:, :, 2]))
            else:
                raw = im @ np.array([0.2126, 0.7152, 0.0722])
            a = raw[iy, ix] * (1 - fracx) + raw[iy, ix + 1] * fracx
            b = raw[iy + 1, ix] * (1 - fracx) + raw[iy + 1, ix + 1] * fracx
            means = (a * (1 - fracy) + b * fracy).mean(axis=1)
            start = fp.get("start", 0)
            expected = np.arange(start, start + n)
            assert np.array_equal(np.flatnonzero(np.isfinite(matrix[:, i])), expected)
            if "final_tail_reference" in job:
                tips = job["final_tail_reference"]["rim_xy"]
                posterior = (
                    np.asarray(tips[-1]) @ fp["pose_rotation"] + fp["pose_offset"]
                )
                assert np.allclose(posterior, fp["reference_points"][0], atol=0.0001)
                guides = [np.array(g) for g in fp["guide_lines"]]
                assert np.allclose(guides[0][0], posterior, atol=0.0001)
                assert np.allclose(guides[0][-1], fp["lines"][0][0])
                lengths = [
                    np.linalg.norm(np.diff(g, axis=0), axis=1).sum() for g in guides
                ]
                assert abs(lengths[0] - start) < 0.05
                assert len(guides) == 1
                end = fp["lines"][0][-1]
                assert np.allclose(end, fp["reference_points"][1])
                # Both the medial trace and the fixed-P grid use whole-pixel arc bins.
                assert np.linalg.norm(np.asarray(end) - anterior_tips[i]) < 2.001
                if i == len(actual_pts) - 1:
                    assert np.allclose(posterior, tips[-1], atol=0.0001)
            max_error = max(max_error, float(np.abs(means - matrix[expected, i]).max()))
            min_support = min(min_support, n)
            checked += n
    assert max_error < 0.01, max_error
    with Image.open(out / "roi.png") as image:
        image.verify()
    return dict(
        status="passed",
        frames=len(actual_pts),
        supported_samples_checked=checked,
        unsupported_bins=int(np.isnan(matrix).sum()),
        minimum_supported_positions=min_support,
        maximum_abs_error_display_units=max_error,
        tolerance_display_units=0.01,
        checks=[
            "Separate bilinear implementation using both serialized band edges and the original decoded RGB.",
            "Frame-by-frame time alignment, ROI width, centerline midpoint, field bounds and missing-value agreement.",
        ],
        anatomical_review="Representative frames inspected by the implementer. Independent biological reviewer pending.",
    )

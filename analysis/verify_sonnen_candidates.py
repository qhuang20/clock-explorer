# SPDX-License-Identifier: MIT
"""Independent pixel-level checks for Sonnen display-video reconstructions.

No producer extraction or registration module is imported. Saved geometry is
checked against freshly decoded native source frames with a separate bilinear
sampler. This checks numerical reproduction, not anatomical validity.
"""

import argparse
import hashlib
import json
from pathlib import Path

import av
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
OUTPUT = ROOT / "outputs/sonnen-independent-review"
SOURCE = {
    "s1": {
        "file": "mmc2.mp4",
        "sha256": "f69d385c7aad96dbbd82c0ee8ea16989c3bb07a06c8adcaf849d12efaf5500cc",
        "baseline": "data/derived/sonnen-2018/movie-s1/kymograph.npz",
        "frames": [0, 1, 23, 44, 63, 77, 80, 83, 86, 87],
        "expected_count": 88,
        "expected_shape": [982, 988, 3],
    },
    "s2": {
        "file": "mmc3.mp4",
        "sha256": "02b0f439d976b0a3cecb38ef89cab2c92fea1188242aceef40d11a7cf1594ec1",
        "baseline": "data/derived/sonnen-2018/movie-s2-kymograph.npz",
        "frames": [0, 1, 2, 30, 50, 77, 89, 110, 132, 154],
        "expected_count": 155,
        "expected_shape": [984, 990, 3],
    },
    "s3": {
        "file": "mmc4.mp4",
        "sha256": "4c48c94ab0a86ec3ebc51db9f5f5a21b438f6d0d57fcfb9c2632d340284035aa",
        "baseline": "data/derived/sonnen-2018/movie-s3/kymograph.npz",
        "frames": [0, 1, 12, 37, 55, 76, 96, 109, 110],
        "expected_count": 111,
        "expected_shape": [512, 512, 3],
    },
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def interpolate(image, xy, fill=np.nan):
    """Bilinear xy sampler; unsupported corners retain the explicit fill."""
    image = np.asarray(image, dtype=float)
    xy = np.asarray(xy, dtype=float)
    finite = np.isfinite(xy).all(axis=-1)
    safe = np.where(finite[..., None], xy, 0)
    x0 = np.floor(safe[..., 0]).astype(int)
    y0 = np.floor(safe[..., 1]).astype(int)
    ok = (
        finite
        & (x0 >= 0)
        & (y0 >= 0)
        & (x0 + 1 < image.shape[1])
        & (y0 + 1 < image.shape[0])
    )
    out = np.full(x0.shape, fill, dtype=float)
    x, y = x0[ok], y0[ok]
    u = safe[..., 0][ok] - x
    v = safe[..., 1][ok] - y
    out[ok] = (
        image[y, x] * (1 - u) * (1 - v)
        + image[y, x + 1] * u * (1 - v)
        + image[y + 1, x] * (1 - u) * v
        + image[y + 1, x + 1] * u * v
    )
    return out


def strip_profile(image, path, normals, offsets, support=None, minimum=None):
    """Independent transverse mean with an explicit per-pixel support image."""
    path, normals, offsets = map(np.asarray, (path, normals, offsets))
    if normals.ndim == 1:
        normals = np.broadcast_to(normals, path.shape)
    xy = path[:, None, :] + normals[:, None, :] * offsets[None, :, None]
    values = interpolate(image, xy)
    valid = np.isfinite(values)
    if support is not None:
        valid &= interpolate(np.asarray(support, float), xy, fill=0) >= 1 - 1e-8
    counts = valid.sum(axis=1)
    threshold = len(offsets) if minimum is None else minimum
    result = np.full(len(path), np.nan)
    keep = counts >= threshold
    total = np.where(valid, values, 0).sum(axis=1)
    result[keep] = total[keep] / counts[keep]
    return result, counts


def cap_profile(profile, distances_um, um_per_px, extent_px):
    """Retain the saved geometric prefix, with units and origin unchanged."""
    if not np.isfinite(um_per_px) or um_per_px <= 0:
        raise ValueError("A positive spatial scale is required")
    out = np.asarray(profile, float).copy()
    out[np.asarray(distances_um) / um_per_px > extent_px] = np.nan
    return out


def decode_selection(path, selection):
    """Decode original movie independently; preserve native frame order/PTS."""
    selected, pts, count, shape = {}, [], 0, None
    with av.open(str(path)) as container:
        for index, frame in enumerate(container.decode(video=0)):
            pts.append(float(frame.pts * frame.time_base))
            if index in selection:
                selected[index] = frame.to_ndarray(format="rgb24")
                shape = list(selected[index].shape)
            count += 1
    return selected, pts, count, shape


def annotation_support_s1(shape):
    y, x = np.indices(shape[:2])
    return (
        (x >= 8)
        & (x < shape[1] - 4)
        & (y >= 4)
        & (y < shape[0] - 4)
        & ~((y >= 895) & (x < 400))
        & ~((y >= 875) & (x > 770))
    )


def annotation_support_s3(shape):
    y, x = np.indices(shape[:2])
    return (
        (x >= 8)
        & (x < shape[1] - 4)
        & (y >= 4)
        & (y < shape[0] - 4)
        & ~((x < 48) & (y < 48))
        & ~((y >= 450) & ((x < 120) | (x > 395)))
    )


def baseline_check(name):
    cfg = SOURCE[name]
    source = ASSETS / "data/source-archive/sonnen-2018" / cfg["file"]
    baseline = ASSETS / cfg["baseline"]
    digest_before = sha256(baseline)
    frames, pts, count, shape = decode_selection(source, cfg["frames"])
    errors, masks = [], []
    with np.load(baseline) as z:
        matrix, clock, distance = z["intensity"], z["time_h"], z["position_um"]
        for index in cfg["frames"]:
            if name in {"s1", "s3"}:
                path, normal = z["path_xy"][index], z["normals_xy"][index]
                offsets = np.linspace(
                    -float(z["strip_width_px"]) / 2,
                    float(z["strip_width_px"]) / 2,
                    int(np.ceil(float(z["strip_width_px"]))) + 1,
                )
                support = (
                    annotation_support_s1(shape)
                    if name == "s1"
                    else annotation_support_s3(shape)
                )
            else:
                start, end = np.array([520.0, 480.0]), np.array([260.0, 240.0])
                delta = end - start
                length = np.linalg.norm(delta)
                path = (
                    start
                    + np.linspace(0, 1, len(distance))[:, None] * delta
                    + z["shifts_xy"][index]
                )
                normal = np.array([-delta[1], delta[0]]) / length
                offsets, support = np.arange(-20, 21), None
            profile, _ = strip_profile(
                frames[index][:, :, 1], path, normal, offsets, support
            )
            if name == "s3":
                profile = cap_profile(
                    profile,
                    distance,
                    float(z["um_per_px"]),
                    z["coverage_extent_px"][index],
                )
            stored = matrix[:, index]
            masks.append(
                bool(np.array_equal(np.isfinite(profile), np.isfinite(stored)))
            )
            good = np.isfinite(profile) & np.isfinite(stored)
            errors.append(float(np.max(np.abs(profile[good] - stored[good]))))
        result = {
            "movie": name,
            "source_sha256": sha256(source),
            "source_hash_matches": sha256(source) == cfg["sha256"],
            "decoded_count": count,
            "decoded_shape": shape,
            "frame_count_matches": count == cfg["expected_count"],
            "frame_shape_matches": shape == cfg["expected_shape"],
            "selected_frames": cfg["frames"],
            "matrix_shape": list(matrix.shape),
            "experimental_time_range_h": clock[[0, -1]].tolist(),
            "experimental_times_selected_h": clock[cfg["frames"]].tolist(),
            "playback_time_range_s": [pts[0], pts[-1]],
            "positions_monotonic": bool(np.all(np.diff(distance) > 0)),
            "max_profile_error_by_frame": errors,
            "max_profile_error": max(errors),
            "sampled_validity_masks_match": all(masks),
            "baseline_sha256": digest_before,
            "baseline_unchanged": digest_before == sha256(baseline),
            "numerical_pass": max(errors) < 1e-9 and all(masks),
            "scope": "Native green-display strip values and saved geometry only; anatomical validity is separately reviewed.",
        }
    return result


def run_baselines(names=("s1", "s2"), output_name="baseline-numerical-review.json"):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = {name: baseline_check(name) for name in names}
    path = OUTPUT / output_name
    path.write_text(json.dumps(results, indent=2) + "\n")
    return results


def render_clock_evidence():
    """Save visible native timestamp crops independently of producer boards."""
    from PIL import Image, ImageDraw, ImageFont

    try:
        from matplotlib import get_data_path

        font = ImageFont.truetype(
            str(Path(get_data_path()) / "fonts/ttf/DejaVuSans.ttf"), 18
        )
    except ImportError:
        font = ImageFont.load_default()
    selected = {
        "s1": [0, 1, 44, 77, 80, 83, 86, 87],
        "s2": [0, 1, 2, 50, 77, 89, 132, 154],
    }
    board = Image.new("RGB", (1000, 1040), "white")
    draw = ImageDraw.Draw(board)
    for column, name in enumerate(["s1", "s2"]):
        cfg = SOURCE[name]
        frames, _, _, _ = decode_selection(
            ASSETS / "data/source-archive/sonnen-2018" / cfg["file"], selected[name]
        )
        clock = np.load(ASSETS / cfg["baseline"])["time_h"]
        for row, index in enumerate(selected[name]):
            image = Image.fromarray(frames[index])
            box = (
                (0, image.height - 115, 410, image.height)
                if name == "s1"
                else (0, 0, 300, 70)
            )
            crop = image.crop(box)
            crop.thumbnail((460, 90))
            x, y = column * 500 + 10, row * 124 + 10
            draw.text(
                (x, y),
                f"{name.upper()} frame {index}: recorded {clock[index]:.2f} h",
                fill="#242833",
                font=font,
            )
            board.paste(crop, (x, y + 26))
    draw.text(
        (10, 1010),
        "Source display clocks; playback FPS is not the experimental interval.",
        fill="#525b6b",
        font=font,
    )
    output = ASSETS / "figures/sonnen-2018/independent-review"
    output.mkdir(parents=True, exist_ok=True)
    board.save(output / "source-clock-evidence.jpg", quality=94)


def render_s3_clock_evidence():
    """Keep S3's h:mm clock and non-gene dye inset visibly distinct."""
    from PIL import Image, ImageDraw, ImageFont
    from matplotlib import get_data_path

    font = ImageFont.truetype(
        str(Path(get_data_path()) / "fonts/ttf/DejaVuSans.ttf"), 16
    )
    indices = SOURCE["s3"]["frames"]
    frames, _, _, _ = decode_selection(
        ASSETS / "data/source-archive/sonnen-2018/mmc4.mp4", indices
    )
    board = Image.new("RGB", (1050, 590), "white")
    draw = ImageDraw.Draw(board)
    for n, index in enumerate(indices):
        x, y = (n % 3) * 350 + 8, (n // 3) * 170 + 8
        minutes = index * 10
        label = f"Frame {index}: {minutes // 60:02}:{minutes % 60:02}"
        draw.text((x, y), label, font=font, fill="#242833")
        frame = Image.fromarray(frames[index])
        board.paste(frame.crop((0, 450, 160, 512)), (x, y + 30))
        board.paste(frame.crop((0, 0, 48, 48)), (x + 190, y + 30))
        draw.text((x + 175, y + 87), "Dye inset", font=font, fill="#525b6b")
    draw.text(
        (8, 520),
        "Source S3 clock: h:mm. The inset is Cascade Blue perfusion reference, not a gene reporter.",
        font=font,
        fill="#525b6b",
    )
    draw.text(
        (8, 548),
        "Sampling masks exclude the inset; movie playback seconds are a separate clock.",
        font=font,
        fill="#525b6b",
    )
    target = (
        ASSETS / "figures/sonnen-2018/independent-review/s3-source-clock-evidence.jpg"
    )
    board.save(target, quality=94)


def candidate_check(name, numeric, provenance_path, overlay_path):
    """Check every saved candidate profile against a newly decoded source."""
    numeric = Path(numeric).resolve()
    cfg = SOURCE[name]
    movie = ASSETS / "data/source-archive/sonnen-2018" / cfg["file"]
    provenance = json.loads(Path(provenance_path).read_text())
    overlay = json.loads(Path(overlay_path).read_text())
    errors, mask_equal, count_equal, clock, native_pts = [], [], [], None, []
    with np.load(numeric) as z, np.load(ASSETS / cfg["baseline"]) as baseline:
        matrix = z["intensity"]
        paths, normals = z["path_xy"], z["normals_xy"]
        offsets = z["width_offsets_px"]
        support = z["image_validity_mask"] if "image_validity_mask" in z else None
        minimum = int(z["minimum_valid_count"]) if "minimum_valid_count" in z else None
        clock = z["time_h"]
        selected = SOURCE[name]["frames"]
        with av.open(str(movie)) as container:
            count = 0
            for index, frame in enumerate(container.decode(video=0)):
                native_pts.append(float(frame.pts * frame.time_base))
                rgb = frame.to_ndarray(format="rgb24")
                profile, counts = strip_profile(
                    rgb[:, :, 1],
                    paths[index],
                    normals[index],
                    offsets,
                    support,
                    minimum,
                )
                if name == "s3":
                    profile = cap_profile(
                        profile,
                        z["position_um"],
                        float(z["um_per_px"]),
                        z["coverage_extent_px"][index],
                    )
                masks = np.isfinite(profile)
                stored = matrix[:, index]
                mask_equal.append(bool(np.array_equal(masks, np.isfinite(stored))))
                both = masks & np.isfinite(stored)
                errors.append(float(np.max(np.abs(profile[both] - stored[both]))))
                count_key = (
                    "fov_width_counts"
                    if "fov_width_counts" in z
                    else "valid_width_counts"
                )
                if count_key in z:
                    count_equal.append(
                        bool(np.array_equal(counts, z[count_key][:, index]))
                    )
                count += 1
        transform_check = None
        if "reference_to_source" in z:
            transform = z["reference_to_source"]
            ref = np.c_[z["reference_path_xy"], np.ones(paths.shape[1])]
            mapped = np.einsum("tij,nj->tni", transform, ref)[..., :2]
            linear = transform[:, :2, :2]
            transform_check = {
                "max_native_path_error_px": float(np.max(np.abs(mapped - paths))),
                "max_rotation_orthogonality_error": float(
                    np.max(
                        np.abs(np.einsum("tji,tjk->tik", linear, linear) - np.eye(2))
                    )
                ),
                "determinant_range": [
                    float(np.min(np.linalg.det(linear))),
                    float(np.max(np.linalg.det(linear))),
                ],
            }
        overlay_errors = []
        for index, drawing in enumerate(overlay["frames"]):
            lines = drawing.get("lines", [])
            valid_path = paths[index][np.isfinite(matrix[:, index])]
            for line in lines:
                points = np.asarray(line)
                nearest = np.sqrt(
                    ((points[:, None] - valid_path[None]) ** 2).sum(axis=2)
                ).min(axis=1)
                overlay_errors.append(float(nearest.max()))
        result = {
            "movie": name,
            "numeric_path": str(Path(numeric).relative_to(ASSETS)),
            "numeric_sha256": sha256(numeric),
            "decoded_frame_count": count,
            "all_profiles_checked": count == matrix.shape[1] == cfg["expected_count"],
            "matrix_shape": list(matrix.shape),
            "max_raw_profile_error": max(errors),
            "max_error_selected_frames": {str(i): errors[i] for i in selected},
            "finite_masks_match_all_frames": all(mask_equal),
            "width_counts_match_all_frames": all(count_equal) if count_equal else None,
            "exact_baseline_times_retained": bool(
                np.array_equal(clock, baseline["time_h"])
            ),
            "exact_baseline_distances_retained": bool(
                np.array_equal(z["position_um"], baseline["position_um"])
            ),
            "baseline_copy_matches": bool(
                np.array_equal(
                    z["baseline_intensity"], baseline["intensity"], equal_nan=True
                )
            )
            if "baseline_intensity" in z
            else None,
            "transform_geometry": transform_check,
            "overlay": {
                "native_dimensions_match": [overlay["height"], overlay["width"]]
                == cfg["expected_shape"][:2],
                "source_hash_matches": overlay["source_sha256"] == cfg["sha256"],
                "matrix_hash_matches": overlay["geometry_input_sha256"]
                == sha256(numeric),
                "frame_indices_contiguous": [f["index"] for f in overlay["frames"]]
                == list(range(count)),
                "experiment_times_match": [f["experiment_h"] for f in overlay["frames"]]
                == clock.tolist(),
                "max_pts_error_s": float(
                    np.max(np.abs(np.array(overlay["frame_starts_s"]) - native_pts))
                ),
                "max_line_vertex_distance_to_saved_valid_path_px": max(
                    overlay_errors, default=0
                ),
                "direction_labels": overlay["direction_labels"],
            },
            "signal_processing": provenance.get(
                "sampling", provenance.get("measurement")
            ),
            "numerical_pass": max(errors) < 1e-9
            and all(mask_equal)
            and all(count_equal),
            "anatomical_validation": "Separately reviewed; successful numerical reconstruction does not validate origin, center or registration.",
        }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / f"{name}-candidate-numerical-review.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    return result


def s3_control_check(numeric):
    """Independently reconstruct all three sectors and matched-support arrays."""
    rows = {
        "current": (
            "baseline_path_xy",
            "baseline_normals_xy",
            "current_coverage_extent_px",
            "baseline_intensity",
            "matched_current_intensity",
            "baseline_fov_width_counts",
            0.0,
        ),
        "left": (
            "path_xy",
            "normals_xy",
            "coverage_extent_px",
            "intensity",
            "matched_left_intensity",
            "fov_width_counts",
            -15.0,
        ),
        "right": (
            "right_path_xy",
            "right_normals_xy",
            "right_coverage_extent_px",
            "right_intensity",
            "matched_right_intensity",
            "right_fov_width_counts",
            15.0,
        ),
    }
    result = {}
    with np.load(numeric) as z:
        scale = float(z["um_per_px"])
        distance = z["position_um"]
        counts = {key: [] for key in rows}
        errors = {key: [] for key in rows}
        matched_errors = {key: [] for key in rows}
        full_fov_errors = {key: [] for key in rows}
        mask_checks = {key: [] for key in rows}
        with av.open(
            str(ASSETS / "data/source-archive/sonnen-2018/mmc4.mp4")
        ) as container:
            for index, frame in enumerate(container.decode(video=0)):
                green = frame.to_ndarray(format="rgb24")[:, :, 1]
                for key, (
                    path_key,
                    normal_key,
                    extent_key,
                    data_key,
                    matched_key,
                    count_key,
                    _,
                ) in rows.items():
                    raw, width_counts = strip_profile(
                        green,
                        z[path_key][index],
                        z[normal_key][index],
                        z["width_offsets_px"],
                        z["image_validity_mask"],
                    )
                    own = cap_profile(raw, distance, scale, z[extent_key][index])
                    common = cap_profile(
                        raw, distance, scale, z["matched_coverage_extent_px"][index]
                    )
                    expected, matched = z[data_key][:, index], z[matched_key][:, index]
                    mask_checks[key].append(
                        bool(
                            np.array_equal(np.isfinite(own), np.isfinite(expected))
                            and np.array_equal(
                                np.isfinite(common), np.isfinite(matched)
                            )
                        )
                    )
                    good, common_good = np.isfinite(own), np.isfinite(common)
                    errors[key].append(
                        float(np.max(np.abs(own[good] - expected[good])))
                    )
                    matched_errors[key].append(
                        float(
                            np.max(np.abs(common[common_good] - matched[common_good]))
                        )
                    )
                    full_key = f"{key}_fov_intensity"
                    if full_key in z:
                        finite_raw = np.isfinite(raw)
                        full_fov_errors[key].append(
                            float(
                                np.max(
                                    np.abs(
                                        raw[finite_raw]
                                        - z[full_key][:, index][finite_raw]
                                    )
                                )
                            )
                        )
                    counts[key].append(
                        bool(np.array_equal(width_counts, z[count_key][:, index]))
                    )
        for key, (path_key, _, _, data_key, matched_key, _, angle) in rows.items():
            theta = np.deg2rad(angle)
            independent_path = np.array([235.0, 290.0]) + distance[:, None] / scale * [
                np.sin(theta),
                -np.cos(theta),
            ]
            result[key] = {
                "profiles_checked": len(errors[key]),
                "max_profile_error": max(errors[key]),
                "max_matched_support_error": max(matched_errors[key]),
                "max_full_fov_profile_error": max(full_fov_errors[key], default=0),
                "finite_masks_match": all(mask_checks[key]),
                "width_counts_match": all(counts[key]),
                "max_declared_ray_error_px": float(
                    np.max(np.abs(z[path_key] - independent_path))
                ),
                "missing_values": int(np.isnan(z[data_key]).sum()),
                "matched_support_missing_values": int(np.isnan(z[matched_key]).sum()),
            }
        common = np.minimum.reduce(
            [
                z["current_coverage_extent_px"],
                z["coverage_extent_px"],
                z["right_coverage_extent_px"],
            ]
        )
        support_equal = np.array_equal(
            z["image_validity_mask"], annotation_support_s3((512, 512))
        )
        output = {
            "movie": "s3",
            "numeric_sha256": sha256(numeric),
            "branches": result,
            "common_cap_is_exact_intersection": bool(
                np.array_equal(common, z["matched_coverage_extent_px"])
            ),
            "support_is_exact_fov_annotation_policy": bool(support_equal),
            "dye_inset_fully_excluded": bool(
                not z["image_validity_mask"][:48, :48].any()
            ),
            "numerical_pass": all(
                max(errors[k]) < 1e-9
                and max(matched_errors[k]) < 1e-9
                and all(mask_checks[k])
                and all(counts[k])
                for k in rows
            ),
            "scope": "Saved geometric caps reproduced; this does not independently certify tissue absence or biological origin.",
        }
    (OUTPUT / "s3-controls-numerical-review.json").write_text(
        json.dumps(output, indent=2) + "\n"
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", choices=list(SOURCE))
    parser.add_argument("--candidate", choices=list(SOURCE))
    parser.add_argument("--numeric", type=Path)
    parser.add_argument("--provenance", type=Path)
    parser.add_argument("--overlay", type=Path)
    args = parser.parse_args()
    if args.baseline:
        print(
            json.dumps(
                run_baselines(
                    [args.baseline], f"{args.baseline}-baseline-numerical-review.json"
                ),
                indent=2,
            )
        )
        if args.baseline == "s3":
            render_s3_clock_evidence()
    elif args.candidate:
        if not all([args.numeric, args.provenance, args.overlay]):
            parser.error(
                "candidate verification requires --numeric, --provenance and --overlay"
            )
        print(
            json.dumps(
                candidate_check(
                    args.candidate, args.numeric, args.provenance, args.overlay
                ),
                indent=2,
            )
        )
        if args.candidate == "s3":
            print(json.dumps(s3_control_check(args.numeric), indent=2))
    else:
        print(json.dumps(run_baselines(), indent=2))
        render_clock_evidence()

"""Build local-only catalog entries using the Explorer's existing card schema."""

import av
import numpy as np
from project import digest


def package(job, out, paths, source):
    pid = job["id"]
    paper_id = job.get("paper_id", pid)
    reporter = job.get("reporter", "LuVeLu")
    gene = job.get("gene", "Lfng")
    video_id = job.get("video_id", "movie-1")
    tissue = job.get("tissue", "Mouse PSM")
    temperature = job.get("temperature", "Unverified")
    axial = job["role"] == "axial"
    axis = "Arc length from P-side ROI" if axial else "Radius from fitted center"
    if "final_tail_reference" in job:
        axis = "Arc length from final-frame P tip"
    signal = (
        "Green excess in the LuVeLu composite"
        if axial
        else "LuVeLu pseudocolor display luminance"
    )
    signal = job.get("signal_note", signal)
    with np.load(out / "kymograph.npz") as matrix:
        z = matrix["intensity"]
        space = float(matrix["space_um"][-1])
    t = job["time_h"]
    times = [t[0], t[-1]]
    movie_evidence = job.get("video_id", "movie")
    source_info = [
        dict(
            id="article",
            url=job["article"],
            location=job["movie"] + " and primary paper",
            note=job["panel"],
        ),
        dict(
            id=movie_evidence,
            url=job["source"],
            location="Publisher movie",
            note="Decoded in full. Experiment times and scale bar checked in the movie.",
        ),
    ]
    prep = job["system"]
    method = dict(
        title="Sampling & kymograph",
        context=f"{reporter} · {job['movie']} · {len(t)} frames",
        roi=paths["roi.png"],
        roi_alt=prep + " with the sampled band in early, middle and final frames.",
        roi_note=job["steps"][0],
        steps=job["steps"],
        limit=job["limit"],
        axes=[
            ["Horizontal axis", "Experiment time (h)"],
            ["Vertical axis", axis + " (approx. µm)"],
        ],
        source_url=job["source"],
        downloads={"svg": paths["plot.svg"], "png": paths["plot.png"]},
        audit_path=paths["review.json"],
        data_path=paths["kymograph.npz"],
        provenance_path=paths["audit.json"],
        alt=f"{reporter} space–time profile",
    )
    coverage = dict(
        mode="all",
        unit="frames",
        used=len(t),
        total=len(t),
        duration_label=f"{t[0]:g}–{t[-1]:g} h",
        note="All decoded frames, timed by the source movie annotations.",
    )
    presentation = dict(
        target_genes=[gene],
        conditions=[prep],
        method_figure=method,
        plot_layout="compact",
        detail_layout="combined_sources",
        experimental_facts=[
            dict(label="Tissue", value=tissue, evidence_ids=["article"]),
            dict(label="Preparation", value=prep, evidence_ids=["article"]),
            dict(label="View", value=job["view"], evidence_ids=[movie_evidence]),
            dict(
                label="Temperature",
                value=temperature,
                unverified=temperature == "Unverified",
            ),
        ],
    )
    if axial:
        presentation["axis_polarity"] = dict(
            top="A",
            bottom="P",
            status="supported",
            note=job.get(
                "polarity_note",
                "Regional P-to-A sampling on the curved posterior embryo.",
            ),
            evidence_ids=["article", movie_evidence],
        )
    record = dict(
        id=pid,
        short=job["short"],
        reporter=reporter,
        kind="video",
        system_label=prep,
        sample=job["movie"],
        origin=axis,
        origin_short=axis,
        source_url=job["article"],
        data_url=job["source"],
        input=paths["kymograph.npz"],
        input_sha256=digest(out / "kymograph.npz"),
        roi=paths["roi.png"],
        reporter_note=signal,
        time_range_h=times,
        position_unit="µm",
        spatial_range=[0, space],
        spatial_scale_approximate=True,
        shape_space_time=list(z.shape),
        missing_values=int(np.isnan(z).sum()),
        common_preview=paths["plot.svg"],
        full_preview=paths["plot.svg"],
        provenance=paths["audit.json"],
        position_increases_up=True,
        normalization=dict(
            method="linear sample-wide finite min/max",
            min=float(np.nanmin(z)),
            max=float(np.nanmax(z)),
        ),
    )
    record["paper_id"] = paper_id
    record["card_context"] = {"sample": job["movie"]}
    paper = dict(
        id=paper_id,
        title=job["title"],
        short=job["short"],
        year=int(paper_id[-4:]),
        authors=job["authors"],
        journal=job["journal"],
        doi=job["doi"],
        url=job["article"],
        species=job.get("species", "Mus musculus"),
        species_label=job.get("species_label", "Mouse"),
        systems=job.get("systems", ["ex vivo"]),
        system_description=prep,
        tissue=tissue,
        origin="live",
        origin_label="Time-lapse",
        reporter_short=reporter,
        target_gene=gene,
        reporter_tags=[reporter],
        reporter_construct=job.get(
            "construct", "Lfng-regulated Venus reporter (LuVeLu)"
        ),
        reported_target=gene,
        patterns=["Traveling waves"],
        conditions=prep,
        summary=job["panel"],
        figure_focus=job["panel"],
        time_axis="Movie annotation (h)",
        space_axis=axis,
        calibration_short=f"Movie time and {job.get('bar_um', 200)} µm scale bar",
        time_resolution="See source movie timestamps",
        space_resolution=f"≈ {job.get('bar_um', 200) / job['bar_pixels']:.2f} µm / video pixel",
        replicates="One displayed specimen",
        preprocessing=signal,
        missing=[],
        caveats=[job["limit"]],
        field_evidence={
            "reported_target": ["article"],
            "reporter_construct": ["article"],
        },
        availability_filters=["Video"],
        availability_summary="Reporter movie decoded and sampled",
        verification_scope=job["panel"],
        media=[],
        sources=source_info,
        kymograph=dict(
            kind="experimental",
            short="Video extraction",
            card_context=dict(sample=job["movie"]),
        ),
        assets=[
            dict(
                level="movie",
                level_label="Source movie",
                label=job["movie"],
                url=job["source"],
                format=source.suffix[1:].upper(),
                bytes=source.stat().st_size,
                status="verified_content",
                evidence=job["panel"],
                license="Publisher supplement; retain original attribution.",
            )
        ],
    )
    vid = out / "playback.mp4"
    with av.open(str(vid)) as f:
        stream = f.streams.video[0]
        info = dict(
            width=stream.width,
            height=stream.height,
            playback_fps=str(stream.average_rate),
            playback_duration_seconds=float(stream.duration * stream.time_base),
        )
    video = dict(
        id=video_id,
        title=job["movie"] + " · " + prep,
        reporter=reporter,
        temperature=temperature,
        source_filename=job["source"].split("/")[-1],
        description=signal + ". " + job["steps"][0],
        source_url=job["source"],
        availability="playable",
        src=paths["playback.mp4"],
        poster=paths["poster.jpg"],
        frames=len(t),
        source_sha256=job["sha256"],
        playback_sha256=digest(vid),
        source_bytes=source.stat().st_size,
        playback_bytes=vid.stat().st_size,
        source_dataset_ids=[pid],
        used_for_kymograph=True,
        sampling_rois={pid: paths["overlay.json"]},
        **info,
    )
    return dict(
        paper=paper,
        comparison=record,
        presentation=presentation,
        coverage=coverage,
        video=dict(
            citation=job["short"],
            article_url=job["article"],
            reporter=reporter,
            videos=[video],
            preferred_by_dataset={pid: video_id},
        ),
    )

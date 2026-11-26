# Local kymograph orchestration

The unit of work is a paper, movie, specimen and reporter combination. The curated
queue is `catalog/kymograph-tasks.json`. Discovery uses the project literature-search
skill to identify new units and deduplicate against Library and Kymographs. Source
audit selects the actual reporter movie, pins its SHA-256 and records its panel
relationship. A Library-only job records the missing input and can be revisited.

The orchestrator routes embryonic AP sampling to kymograph-axial and a supported
center-to-periphery culture geometry to kymograph-radial. The pilot adapters in
`scripts/mouse_roi.py` handle the two reviewed source formats. A new signal
encoding or sampling model needs its own checked adapter. The independent check
reopens the source and reconstructs the matrix from the exported band polygons.
The UI-card stage uses the same matrix, sampling geometry and playback frame times.
An independent anatomical review can be recorded separately from numeric agreement.

Run from the project root with NumPy, SciPy, Matplotlib, PyAV and Pillow available:

```sh
work/plot-env/bin/python scripts/kymograph_pipeline.py resume
python3 scripts/kymograph_pipeline.py status
python3 scripts/build.py --local-runs
```

Pass one or more job IDs after `resume` to limit the run. Each job has an
exclusive lock, an atomic state file and stage output checksums under
`work/kymograph-runs/<id>/`. A changed job specification, source, stage
implementation or output invalidates dependent checkpoints. Each job can resume
independently. A failed job records its error and the next stage. Use the build
flag to include completed jobs in the local preview; the ordinary site build
uses the maintained catalogs. The original publisher movies remain under
`assets/data/sources/<id>/`. The build copies only the presentation assets.

To preview one independently reviewed batch, run
`npm run build -- --local-batch work/kymograph-batches/<batch>/manifest.json`.
The manifest maps dataset IDs in `bundles` to the SHA-256 of each neighboring
`<dataset-id>/bundle.json`. The build verifies those bundles and their assets
and serves the candidates at `/review.html` on localhost. The main gallery uses
its usual catalog. After approval, promote the selected datasets into that catalog.

# Research data and licensing

The MIT license applies to original project software and documentation. It does
not extend to papers, supplemental movies, raw/processed matrices, LUTs, author
repositories or research figures derived from those sources.

## Three distinct records

1. A **paper** is one publication in `catalog/literature.json`.
2. A **dataset** is one comparison input in `catalog/comparison.json`.
3. An **asset** is a downloadable file in `catalog/assets.json`.

Miao 2023 currently has separate Somitoid and Segmentoid datasets. These model
different tissue behaviors and use different signals/extraction methods; they
remain one paper in the library count. HES7/UNCX share the recorded Segmentoid
channel; the matrix is not interpreted as a separate pure UNCX measurement.

## Add data

Start from an existing paper/dataset record, retain stable IDs, and record:

- DOI, original source URL and source file hash;
- species, experimental model, sample and reporter/channel;
- temperature, acquisition interval, length calibration and coordinate origin;
- extraction method, transformations, retained range, normalization and masks;
- source-specific attribution and redistribution terms, including unknowns.

Keep the four extraction labels distinct: author matrix, video extraction,
binned tracks and pseudocolor reconstruction. Numerical comparisons should
respect differences in measured signal and coordinate definitions. Never turn an
unknown calibration into zero or infer absolute concentrations from display colors.

## Asset downloads

```sh
npm run data:fetch -- --dry-run
npm run data:fetch -- --group core
npm run data:fetch -- --group videos --paper miao-2023
npm run data:fetch -- --group sources --paper miao-2023 --dry-run
```

The core collection includes processed matrices, previews and runtime range
payloads. The video collection includes playback copies. Source archives are
optional and can exceed gigabytes. The downloader verifies size and SHA-256,
keeps valid existing files, and never extracts or executes an archive.

A hash verifies file identity, not permission to redistribute or scientific
validity. Some assets are available publicly but do not have an open reuse
license. Obtain permission as needed before redistributing, publishing derived
figures or making a data-containing release. See [third-party notices](THIRD_PARTY_NOTICES.md).

## Provenance integrity

Rebuilding the interface does not rewrite arrays. Extraction/rendering commands
may produce new artifacts; record those as new results with their script and input
hashes. Keep absent/masked measurements as NaN/null. Cropping uses the full
sample's color normalization and preserves irregular time coordinates.

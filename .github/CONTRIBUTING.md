# Contributing

The repository is private while preparing its initial community release. Invited
collaborators can use the same pull-request workflow that will be used publicly.

## Before changing code

1. Read the [architecture](../docs/architecture.md) and run the app.
   For card-interface work, also read the [ui-card guidelines](../docs/ui-card-guidelines.md).
   Codex collaborators can use the repository's
   [ui-card skill](../.agents/skills/ui-card/SKILL.md).
   For kymograph extraction, read the [shared requirements](../docs/kymograph-extraction.md)
   and choose the [kymograph-axial skill](../.agents/skills/kymograph-axial/SKILL.md)
   or [kymograph-radial skill](../.agents/skills/kymograph-radial/SKILL.md).
2. Create a branch with one focused change.
3. Run `npm run check`, `npm test`, and `npm run build`.
4. For UI changes, check the English interface and a narrow mobile layout. Include a screenshot.
5. Explain the problem, resulting behavior and validation in the pull request.

Use the exact locked Node dependencies (`npm ci`). Format with `npm run format`.
Do not commit `dist/`, `assets/`, credentials, browser notes, downloaded archives,
local environments, or temporary screenshots. New tests should protect behavior
or numerical invariants, not merely mirror the implementation.

## Adding a paper or dataset

See [data provenance](../docs/data-provenance.md). Paper IDs and dataset IDs are
stable links. A paper can have several datasets. Record source URLs, hashes,
reporter/channel identity, species, temperature, time/space calibration, extraction
method, inclusion window and missing-value treatment. Use `null` or an explicit
unknown when evidence is absent. Never synthesize time-lapse from fixed samples.

Write code, catalog records, documentation and UI text in English. Prefer a reproducible
extraction script to manual edits of numeric arrays. Before proposing new assets,
record their original license and confirm which files may be redistributed.

## Reviews and conduct

Discuss substantive analysis changes before replacing existing figures. Preserve
source data and link the new outputs to their input hashes. Be respectful, explain
uncertainty, and keep discussion focused on evidence. See [CODE_OF_CONDUCT](CODE_OF_CONDUCT.md).

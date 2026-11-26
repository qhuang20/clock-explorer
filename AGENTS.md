# Repository guidance

Read README.md and docs/architecture.md before substantial changes.

Skills in .agents/skills/ belong to this repository. Keep them project-scoped;
do not install or symlink them into user-level skill directories unless explicitly requested.

For card and card-detail UI work, read docs/ui-card-guidelines.md. The repository skill
entrypoint is .agents/skills/ui-card/SKILL.md. Check the current configuration
and task for rollout scope; reference examples guide design without freezing
future versions.

For paper-to-movie coverage audits, use `.agents/skills/kymograph-source-audit/SKILL.md`; save study inventories in `catalog/source-audits/`.

For axial or radial kymograph extraction, read docs/kymograph-extraction.md.
The skill entrypoints are .agents/skills/kymograph-axial/SKILL.md and
.agents/skills/kymograph-radial/SKILL.md; keep scientific extraction and
card-interface work as distinct scopes.

- Edit authored code in web/, catalog/, analysis/ or scripts/. Never edit dist/.
- Preserve scientific values, coordinate units, masks, channel identities and provenance.
- Keep original research files in ignored assets/; record sources and hashes in catalog/assets.json.
- Do not commit credentials, browser notes, work/, outputs/, environments or downloaded archives.
- Run npm run check, npm test and npm run build after relevant changes.
- Use English for code, catalog records, documentation and the UI; keep the interface concise.
- Do not deploy or change GitHub visibility without the user's explicit instruction.
- Do not create skills or start parallel research agents as part of routine maintenance.

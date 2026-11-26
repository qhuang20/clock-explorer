# Security

Do not put tokens, credentials, private research data or personal browser notes in
issues or pull requests. The explorer runs client-side; its development server
binds to loopback and serves only the generated `dist/` directory.

For a suspected vulnerability, contact the maintainer privately using
[the maintainer profile](https://github.com/qhuang20). If GitHub private vulnerability
reporting is available on this repository, use it. Describe the affected version,
reproduction and impact; avoid publishing exploit details before coordination.

No formal support window or response SLA is promised at this early stage. Keep
Node dependencies updated and run `npm audit` when updating the lockfile.

Downloads are optional and checked against SHA-256 before being installed. The
downloader never extracts archives or executes downloaded code. Research data
still need scientific and licensing review before reuse.

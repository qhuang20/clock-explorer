# SPDX-License-Identifier: MIT
"""Format the project's CFF metadata without adding a site-build dependency."""

import json
from pathlib import Path
import re


def formatted_citation(path):
    content = Path(path).read_text()

    def value(text):
        text = text.strip()
        return json.loads(text) if text.startswith('"') else text.strip("'")

    def scalar(key):
        match = re.search(r"^" + re.escape(key) + r":\s*(.+)$", content, re.M)
        if not match:
            raise ValueError("Missing citation metadata: " + key)
        return value(match[1])

    # This repository uses ordinary given/family-name CFF author records.
    # Reject missing records rather than publishing an incomplete citation.
    match = re.search(r"^authors:\s*\n((?:[ \t].*(?:\n|$))+)", content, re.M)
    if not match:
        raise ValueError("Missing CFF authors")
    authors = []
    for block in re.split(r"(?m)^\s*-\s+", match[1])[1:]:
        fields = dict(
            line.strip().split(":", 1) for line in block.splitlines() if ":" in line
        )
        if "family-names" not in fields or "given-names" not in fields:
            raise ValueError("CFF author requires given and family names")
        initials = " ".join(
            part[0] + "." for part in value(fields["given-names"]).split()
        )
        authors.append(value(fields["family-names"]) + ", " + initials)
    if not authors:
        raise ValueError("Empty CFF author list")
    names = (
        authors[0]
        if len(authors) == 1
        else ", ".join(authors[:-1]) + ", & " + authors[-1]
    )
    year = scalar("date-released").split("-")[0]
    return (
        f"{names} ({year}). {scalar('title')} "
        f"(Version {scalar('version')}) [Computer software]. Zenodo. "
        f"https://doi.org/{scalar('doi')}"
    )

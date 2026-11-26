# SPDX-License-Identifier: MIT
"""Portable locations for research inputs and authored metadata."""

from pathlib import Path
import os

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = Path(os.environ.get("CLOCK_ASSET_ROOT", REPO_ROOT / "assets")).resolve()
CATALOG_ROOT = Path(
    os.environ.get("CLOCK_CATALOG_ROOT", REPO_ROOT / "catalog")
).resolve()

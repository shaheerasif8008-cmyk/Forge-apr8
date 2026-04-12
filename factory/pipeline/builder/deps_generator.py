"""Generate packaged employee Python dependencies from the repo manifest."""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


async def generate_requirements_txt(build_dir: Path) -> None:
    """Write a requirements.txt containing the repo's base dependencies."""
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    dependencies = pyproject.get("project", {}).get("dependencies", [])
    (build_dir / "requirements.txt").write_text("\n".join(dependencies) + "\n")

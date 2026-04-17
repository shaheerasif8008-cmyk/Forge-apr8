"""Local artifact storage for packaged employee images."""

from __future__ import annotations

import subprocess
from pathlib import Path
from shutil import copy2
from uuid import UUID

ARTIFACT_ROOT = Path("/tmp/forge-artifacts")


async def store_container_tarball(image_tag: str, build_id: UUID) -> str:
    """Save a built Docker image to a local tarball and return its path."""
    artifact_dir = ARTIFACT_ROOT / str(build_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    tarball_path = artifact_dir / "employee.tar"
    subprocess.run(
        ["docker", "save", "-o", str(tarball_path), image_tag],
        capture_output=True,
        text=True,
        check=True,
    )
    return str(tarball_path)


async def store_file(path: str | Path, build_id: UUID, *, artifact_type: str = "artifact") -> str:
    """Copy an arbitrary build artifact into local artifact storage."""
    source = Path(path)
    artifact_dir = ARTIFACT_ROOT / str(build_id) / artifact_type
    artifact_dir.mkdir(parents=True, exist_ok=True)
    destination = artifact_dir / source.name
    copy2(source, destination)
    return str(destination)

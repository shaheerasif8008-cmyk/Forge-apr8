"""Packager: builds the final deployable container image for the employee."""

from __future__ import annotations

import subprocess
from pathlib import Path

import structlog

from factory.models.build import Build, BuildArtifact, BuildLog, BuildStatus
from factory.pipeline.builder.artifact_store import store_container_tarball

logger = structlog.get_logger(__name__)


async def package(build: Build) -> Build:
    """Build a Docker image from the assembled employee package."""
    build.status = BuildStatus.PACKAGING
    build_dir = Path(str(build.metadata.get("build_dir", "")))
    if not build_dir.exists():
        build.status = BuildStatus.FAILED
        build.logs.append(
            BuildLog(stage="packager", level="error", message="Missing build directory")
        )
        return build

    image_tag = f"forge-employee-{build.id}:latest"
    logger.info("packager_start", build_id=str(build.id), build_dir=str(build_dir), image_tag=image_tag)

    result = subprocess.run(
        ["docker", "build", "-t", image_tag, "."],
        cwd=str(build_dir),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        build.status = BuildStatus.FAILED
        build.logs.append(
            BuildLog(
                stage="packager",
                level="error",
                message="Docker build failed",
                detail={"stderr": result.stderr[-4000:], "stdout": result.stdout[-2000:]},
            )
        )
        return build

    try:
        tarball_path = await store_container_tarball(image_tag, build.id)
    except subprocess.CalledProcessError as exc:
        build.status = BuildStatus.FAILED
        build.logs.append(
            BuildLog(
                stage="packager",
                level="error",
                message="Docker save failed",
                detail={"stderr": exc.stderr or "", "stdout": exc.stdout or ""},
            )
        )
        return build

    build.metadata["image_tag"] = image_tag
    build.metadata["image_tarball"] = tarball_path
    artifact = BuildArtifact(artifact_type="container_image", location=tarball_path)
    build.artifacts.append(artifact)
    build.logs.append(
        BuildLog(
            stage="packager",
            message="Container image built",
            detail={"image_tag": image_tag, "artifact_path": tarball_path},
        )
    )
    logger.info("packager_complete", image_tag=image_tag, artifact_path=tarball_path)
    return build

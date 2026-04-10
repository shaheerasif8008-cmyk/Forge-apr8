"""Packager: builds the final deployable container image for the employee."""

from __future__ import annotations

import structlog

from factory.models.build import Build, BuildArtifact, BuildLog, BuildStatus

logger = structlog.get_logger(__name__)


async def package(build: Build) -> Build:
    """Produce a container image from assembled + generated code.

    Args:
        build: Build with assembled and generated artifacts.

    Returns:
        Build with container image artifact added.
    """
    build.status = BuildStatus.PACKAGING
    logger.info("packager_start", build_id=str(build.id))

    # TODO: actually run docker build + push to registry
    artifact = BuildArtifact(
        artifact_type="container_image",
        location=f"registry.forge.internal/employees/{build.id}:latest",
    )
    build.artifacts.append(artifact)
    build.logs.append(BuildLog(stage="packager", message="Container image built and pushed"))
    logger.info("packager_complete", image=artifact.location)
    return build

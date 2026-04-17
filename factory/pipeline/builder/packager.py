"""Packager: builds the final deployable container image for the employee."""

from __future__ import annotations

import subprocess
from os import environ
from pathlib import Path

import structlog

from factory.models.build import Build, BuildArtifact, BuildLog, BuildStatus
from factory.pipeline.builder.artifact_store import store_container_tarball, store_file

logger = structlog.get_logger(__name__)
DESKTOP_INSTALLER_SUFFIXES = (".dmg", ".exe", ".AppImage")


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

    frontend_dir = build_dir / "portal" / "employee_app"
    frontend_result = _build_frontend(frontend_dir)
    if frontend_result.returncode != 0:
        build.status = BuildStatus.FAILED
        build.logs.append(
            BuildLog(
                stage="packager",
                level="error",
                message="Frontend build failed",
                detail={"stderr": frontend_result.stderr[-4000:], "stdout": frontend_result.stdout[-2000:]},
            )
        )
        return build
    build.logs.append(
        BuildLog(
            stage="packager",
            message="Frontend bundle compiled",
            detail={"frontend_dir": str(frontend_dir)},
        )
    )

    if _should_build_desktop(build):
        desktop_result = _build_desktop_installers(build, frontend_dir)
        if desktop_result.returncode != 0:
            build.status = BuildStatus.FAILED
            build.logs.append(
                BuildLog(
                    stage="packager",
                    level="error",
                    message="Desktop installer build failed",
                    detail={"stderr": desktop_result.stderr[-4000:], "stdout": desktop_result.stdout[-2000:]},
                )
            )
            return build
        installers = await _store_desktop_installers(build, frontend_dir / "dist")
        if not installers:
            build.logs.append(
                BuildLog(
                    stage="packager",
                    level="warning",
                    message="Desktop build completed without installer artifacts",
                )
            )

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


def _build_frontend(frontend_dir: Path) -> subprocess.CompletedProcess[str]:
    package_lock = frontend_dir / "package-lock.json"
    if not package_lock.exists():
        logger.warning("frontend_package_lock_missing", frontend_dir=str(frontend_dir))
    npm_ci = subprocess.run(
        ["npm", "ci"],
        cwd=str(frontend_dir),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if npm_ci.returncode != 0:
        return npm_ci
    return subprocess.run(
        ["npm", "run", "build"],
        cwd=str(frontend_dir),
        capture_output=True,
        text=True,
        timeout=600,
    )


def _should_build_desktop(build: Build) -> bool:
    deployment_format = str(build.metadata.get("deployment_format", "web")).lower()
    return deployment_format in {"desktop", "hybrid"}


def _desktop_env(build: Build) -> dict[str, str]:
    env = dict(environ)
    env["FORGE_EMPLOYEE_ID"] = str(build.metadata.get("employee_id", build.id))
    env["FORGE_EMPLOYEE_NAME"] = str(build.metadata.get("employee_name", "Forge Employee"))
    env["FORGE_BACKEND_URL"] = str(build.metadata.get("desktop_backend_url", ""))
    return env


def _build_desktop_installers(build: Build, frontend_dir: Path) -> subprocess.CompletedProcess[str]:
    if environ.get("FORGE_SKIP_HEAVY_BUILDS") == "1":
        placeholder_dir = frontend_dir / "dist"
        placeholder_dir.mkdir(parents=True, exist_ok=True)
        placeholder_name = str(build.metadata.get("employee_name", "forge-employee")).replace(" ", "-").lower()
        (placeholder_dir / f"{placeholder_name}.AppImage").write_text("placeholder desktop installer")
        return subprocess.CompletedProcess(args=["npx", "electron-builder"], returncode=0, stdout="skipped", stderr="")

    if not environ.get("CSC_LINK") or not environ.get("CSC_KEY_PASSWORD"):
        logger.warning("desktop_codesigning_missing", build_id=str(build.id))

    return subprocess.run(
        ["npx", "electron-builder", "--mac", "--win", "--linux", "--publish=never"],
        cwd=str(frontend_dir),
        capture_output=True,
        text=True,
        timeout=1200,
        env=_desktop_env(build),
    )


async def _store_desktop_installers(build: Build, dist_dir: Path) -> list[str]:
    if not dist_dir.exists():
        return []

    stored_locations: list[str] = []
    for path in dist_dir.rglob("*"):
        if not path.is_file() or path.suffix not in DESKTOP_INSTALLER_SUFFIXES:
            continue
        stored_location = await store_file(path, build.id, artifact_type="desktop_installer")
        stored_locations.append(stored_location)
        build.artifacts.append(
            BuildArtifact(
                artifact_type="desktop_installer",
                location=stored_location,
            )
        )
        build.logs.append(
            BuildLog(
                stage="packager",
                message="Desktop installer packaged",
                detail={"source_path": str(path), "artifact_path": stored_location},
            )
        )
    return stored_locations

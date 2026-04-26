"""Packager: builds the final deployable container image for the employee."""

from __future__ import annotations

import json
import subprocess
from os import environ
from pathlib import Path
from shutil import copy2, copytree, rmtree
from tempfile import mkdtemp
from zipfile import ZipFile

import structlog

from factory.models.build import Build, BuildArtifact, BuildLog, BuildStatus
from factory.pipeline.builder.manifest_generator import select_runtime_template
from factory.pipeline.builder.artifact_store import store_container_tarball, store_file

logger = structlog.get_logger(__name__)
DESKTOP_INSTALLER_SUFFIXES = (".dmg", ".exe", ".AppImage")
REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES_DIR = REPO_ROOT / "employee_runtime" / "templates"
SERVER_BUNDLE_METADATA_FILE = "bundle-metadata.json"


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

    try:
        result = subprocess.run(
            ["docker", "build", "-t", image_tag, "."],
            cwd=str(build_dir),
            capture_output=True,
            text=True,
            timeout=int(environ.get("FORGE_DOCKER_BUILD_TIMEOUT_SECONDS", "900")),
        )
    except subprocess.TimeoutExpired as exc:
        build.status = BuildStatus.FAILED
        build.logs.append(
            BuildLog(
                stage="packager",
                level="error",
                message="Docker build timed out",
                detail={
                    "timeout_seconds": exc.timeout,
                    "stdout": _tail_text(exc.stdout, 2000),
                    "stderr": _tail_text(exc.stderr, 4000),
                },
            )
        )
        return build
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

    if _should_build_server_bundle(build):
        server_package_path = await _build_server_bundle(build, build_dir, frontend_dir)
        build.logs.append(
            BuildLog(
                stage="packager",
                message="Server deployment bundle packaged",
                detail={"artifact_path": server_package_path, "runtime_template": _runtime_template(build)},
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


def _tail_text(value: str | bytes | None, limit: int) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode(errors="replace")
    return value[-limit:]


def _should_build_desktop(build: Build) -> bool:
    deployment_format = str(build.metadata.get("deployment_format", "web")).lower()
    return deployment_format in {"desktop", "hybrid"}


def _should_build_server_bundle(build: Build) -> bool:
    deployment_format = str(build.metadata.get("deployment_format", "web")).lower()
    return deployment_format == "server"


def _desktop_env(build: Build) -> dict[str, str]:
    env = dict(environ)
    env["FORGE_EMPLOYEE_ID"] = str(build.metadata.get("employee_id", build.id))
    env["FORGE_EMPLOYEE_NAME"] = str(build.metadata.get("employee_name", "Forge Employee"))
    env["FORGE_BACKEND_URL"] = str(build.metadata.get("desktop_backend_url", ""))
    return env


def _build_desktop_installers(build: Build, frontend_dir: Path) -> subprocess.CompletedProcess[str]:
    if environ.get("FORGE_SKIP_HEAVY_BUILDS") == "1":
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


def _runtime_template(build: Build) -> str:
    configured = str(build.metadata.get("runtime_template", "")).strip()
    if configured:
        return configured
    return select_runtime_template(str(build.metadata.get("deployment_format", "web")))


async def _build_server_bundle(build: Build, build_dir: Path, frontend_dir: Path) -> str:
    bundle_root = build_dir / "handoff" / "server"
    if bundle_root.exists():
        rmtree(bundle_root)
    app_dir = bundle_root / "app"
    app_dir.mkdir(parents=True, exist_ok=True)

    _copy_runtime_context(build_dir, frontend_dir, app_dir)

    compose_path = bundle_root / "docker-compose.yml"
    compose_path.write_text(
        _render_template(
            "docker-compose.template",
            {
                "APP_CONTEXT": "./app",
                "IMAGE_NAME": f"forge-employee-{build.id}",
                "HOST_PORT": "8001",
                "CONTAINER_PORT": "8001",
            },
        )
    )
    root_env_path = bundle_root / ".env.example"
    copy2(build_dir / ".env.example", root_env_path)

    metadata = _server_bundle_metadata(build)
    (bundle_root / "README.md").write_text(_server_bundle_readme(metadata))
    metadata["included_files"] = sorted(
        path.relative_to(bundle_root).as_posix()
        for path in bundle_root.rglob("*")
        if path.is_file()
    ) + [SERVER_BUNDLE_METADATA_FILE]
    metadata_path = bundle_root / SERVER_BUNDLE_METADATA_FILE
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True))

    archive_path = _zip_directory(bundle_root, archive_name=f"forge-employee-{build.id}-server-bundle.zip")
    stored_location = await store_file(archive_path, build.id, artifact_type="server_package")
    build.artifacts.append(BuildArtifact(artifact_type="server_package", location=stored_location))

    build.metadata.setdefault("deployment_bundles", {})
    build.metadata["deployment_bundles"]["server"] = {
        "artifact_path": stored_location,
        "runtime_template": metadata["runtime_template"],
        "bundle_metadata_path": metadata_path.as_posix(),
        "bundle_root": bundle_root.as_posix(),
        "compose_file": metadata["compose_file"],
        "healthcheck_path": metadata["healthcheck_path"],
    }
    return stored_location


def _copy_runtime_context(build_dir: Path, frontend_dir: Path, app_dir: Path) -> None:
    for directory_name in ("employee_runtime", "component_library", "generated"):
        source = build_dir / directory_name
        if source.exists():
            copytree(source, app_dir / directory_name, dirs_exist_ok=True)

    for file_name in ("run.py", "requirements.txt", "config.yaml", "package_manifest.json"):
        source = build_dir / file_name
        if source.exists():
            copy2(source, app_dir / file_name)

    static_source = frontend_dir / "out"
    static_destination = app_dir / "static"
    if static_source.exists():
        copytree(static_source, static_destination, dirs_exist_ok=True)
    else:
        static_destination.mkdir(parents=True, exist_ok=True)
        _write_static_fallback(frontend_dir, static_destination)

    (app_dir / "Dockerfile").write_text(_render_template("Dockerfile.template", {"PORT": "8001"}))


def _write_static_fallback(frontend_dir: Path, static_destination: Path) -> None:
    config_path = frontend_dir / "app" / "config.ts"
    employee_name = "Forge Employee"
    employee_role = "Autonomous AI Employee"
    if config_path.exists():
        config_text = config_path.read_text()
        employee_name = _ts_config_value(config_text, "employeeName") or employee_name
        employee_role = _ts_config_value(config_text, "employeeRole") or employee_role
    index_html = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>{employee_name}</title>"
        "</head><body>"
        f"<h1>{employee_name}</h1><p>{employee_role}</p>"
        "<p>Frontend bundle fallback included because the static export output was unavailable.</p>"
        "</body></html>"
    )
    (static_destination / "index.html").write_text(index_html)


def _ts_config_value(config_text: str, key: str) -> str:
    import re

    match = re.search(rf"{key}:\s*\"([^\"]+)\"", config_text)
    return match.group(1) if match else ""


def _server_bundle_metadata(build: Build) -> dict[str, object]:
    employee_name = str(build.metadata.get("employee_name", "Forge Employee"))
    employee_id = str(build.metadata.get("employee_id", build.id))
    runtime_template = _runtime_template(build)
    return {
        "bundle_version": 1,
        "build_id": str(build.id),
        "employee_id": employee_id,
        "employee_name": employee_name,
        "deployment_format": "server",
        "runtime_template": runtime_template,
        "bundle_root": ".",
        "app_dir": "app",
        "compose_file": "docker-compose.yml",
        "config_path": "app/config.yaml",
        "manifest_path": "app/package_manifest.json",
        "healthcheck_path": "/api/v1/health",
        "expected_base_url": "http://localhost:8001",
        "handoff_steps": [
            "Copy .env.example to .env and fill in required API keys.",
            "Run docker compose build from the bundle root.",
            "Run docker compose up -d and wait for the container to start.",
            "Verify the employee at http://localhost:8001/api/v1/health.",
        ],
        "included_files": [],
    }


def _server_bundle_readme(metadata: dict[str, object]) -> str:
    handoff_steps = "\n".join(
        f"{index}. {step}"
        for index, step in enumerate(metadata.get("handoff_steps", []), start=1)
    )
    return (
        "# Forge Server Deployment Bundle\n\n"
        f"Employee: {metadata['employee_name']}\n"
        f"Employee ID: {metadata['employee_id']}\n"
        f"Build ID: {metadata['build_id']}\n"
        f"Runtime template: {metadata['runtime_template']}\n\n"
        "## Contents\n\n"
        "- `app/`: self-contained Docker build context for the employee runtime\n"
        "- `docker-compose.yml`: compose entrypoint for client-hosted deployment\n"
        "- `.env.example`: runtime environment variables to populate before launch\n"
        f"- `{SERVER_BUNDLE_METADATA_FILE}`: machine-readable handoff metadata\n\n"
        "## Handoff Steps\n\n"
        f"{handoff_steps}\n"
    )


def _render_template(template_name: str, values: dict[str, str]) -> str:
    rendered = (TEMPLATES_DIR / template_name).read_text()
    for key, value in values.items():
        rendered = rendered.replace(f"${{{key}}}", value)
    return rendered


def _zip_directory(directory: Path, *, archive_name: str) -> Path:
    archive_path = Path(mkdtemp(prefix="forge-bundle-")) / archive_name
    with ZipFile(archive_path, "w") as archive:
        for path in directory.rglob("*"):
            archive.write(path, path.relative_to(directory))
    return archive_path

"""Server deployment export provider."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from zipfile import ZipFile

import structlog

from factory.models.build import Build, BuildArtifact
from factory.models.deployment import Deployment, DeploymentStatus
from factory.pipeline.builder.artifact_store import store_file

logger = structlog.get_logger(__name__)


async def provision_server_export(deployment: Deployment, build: Build) -> Deployment:
    bundle = _server_bundle_details(build)
    if bundle is not None:
        deployment.status = DeploymentStatus.PENDING_CLIENT_ACTION
        deployment.access_url = ""
        deployment.infrastructure = {
            "provider": "docker_compose_export",
            "artifact_path": bundle["artifact_path"],
            "runtime_template": bundle["runtime_template"],
            "bundle_metadata_path": bundle["bundle_metadata_path"],
            "compose_file": bundle["compose_file"],
            "healthcheck_path": bundle["healthcheck_path"],
            "handoff_ready": True,
        }
        logger.info(
            "provision_server_export_complete",
            deployment_id=str(deployment.id),
            artifact_path=bundle["artifact_path"],
            runtime_template=bundle["runtime_template"],
        )
        return deployment

    build_dir = Path(str(build.metadata.get("build_dir", "")))
    deploy_dir = build_dir / "deploy"
    deploy_dir.mkdir(parents=True, exist_ok=True)

    image_tag = str(build.metadata.get("image_tag", "forge-employee:latest"))
    (deploy_dir / "docker-compose.yml").write_text(_docker_compose_contents(image_tag))
    (deploy_dir / ".env.example").write_text(_env_example_contents())
    (deploy_dir / "README.md").write_text(_readme_contents(build))

    archive_path = await _zip_directory(deploy_dir)
    artifact_path = await store_file(archive_path, build.id, artifact_type="server_package")
    build.artifacts.append(BuildArtifact(artifact_type="server_package", location=artifact_path))

    deployment.status = DeploymentStatus.PENDING_CLIENT_ACTION
    deployment.access_url = ""
    deployment.infrastructure = {
        "provider": "docker_compose_export",
        "deploy_dir": str(deploy_dir),
        "artifact_path": artifact_path,
    }
    logger.info("provision_server_export_complete", deployment_id=str(deployment.id), artifact_path=artifact_path)
    return deployment


def _server_bundle_details(build: Build) -> dict[str, str] | None:
    deployment_bundles = build.metadata.get("deployment_bundles")
    if isinstance(deployment_bundles, dict):
        server_bundle = deployment_bundles.get("server")
        if isinstance(server_bundle, dict) and server_bundle.get("artifact_path"):
            return {
                "artifact_path": str(server_bundle.get("artifact_path", "")),
                "runtime_template": str(server_bundle.get("runtime_template", "")),
                "bundle_metadata_path": str(server_bundle.get("bundle_metadata_path", "")),
                "compose_file": str(server_bundle.get("compose_file", "docker-compose.yml")),
                "healthcheck_path": str(server_bundle.get("healthcheck_path", "/api/v1/health")),
            }

    server_artifact = next((artifact for artifact in build.artifacts if artifact.artifact_type == "server_package"), None)
    if server_artifact is None:
        return None

    metadata_path = Path(str(build.metadata.get("build_dir", ""))) / "handoff" / "server" / "bundle-metadata.json"
    runtime_template = str(build.metadata.get("runtime_template", ""))
    compose_file = "docker-compose.yml"
    healthcheck_path = "/api/v1/health"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text())
        runtime_template = str(metadata.get("runtime_template", runtime_template))
        compose_file = str(metadata.get("compose_file", compose_file))
        healthcheck_path = str(metadata.get("healthcheck_path", healthcheck_path))

    return {
        "artifact_path": server_artifact.location,
        "runtime_template": runtime_template,
        "bundle_metadata_path": str(metadata_path),
        "compose_file": compose_file,
        "healthcheck_path": healthcheck_path,
    }


async def _zip_directory(directory: Path) -> Path:
    archive = Path(tempfile.mkdtemp(prefix="forge-server-export-")) / "deploy_package.zip"
    with ZipFile(archive, "w") as zip_file:
        for path in directory.rglob("*"):
            zip_file.write(path, path.relative_to(directory.parent))
    return archive


def _docker_compose_contents(image_tag: str) -> str:
    return (
        "version: '3.9'\n"
        "services:\n"
        "  employee:\n"
        f"    image: {image_tag}\n"
        "    env_file:\n"
        "      - .env\n"
        "    ports:\n"
        "      - '8001:8001'\n"
        "    restart: unless-stopped\n"
    )


def _env_example_contents() -> str:
    return (
        "ANTHROPIC_API_KEY=\n"
        "OPENAI_API_KEY=\n"
        "OPENROUTER_API_KEY=\n"
        "REDIS_URL=\n"
    )


def _readme_contents(build: Build) -> str:
    return (
        "# Forge Server Deployment\n\n"
        "1. Copy `.env.example` to `.env` and fill in required values.\n"
        "2. Run `docker compose up -d` from this folder.\n"
        "3. Open `http://localhost:8001/` after the container reports healthy.\n\n"
        f"Build ID: {build.id}\n"
    )

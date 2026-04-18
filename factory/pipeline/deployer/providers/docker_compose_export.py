"""Server deployment export provider."""

from __future__ import annotations

import tempfile
from pathlib import Path
from zipfile import ZipFile

import structlog

from factory.models.build import Build, BuildArtifact
from factory.models.deployment import Deployment, DeploymentStatus
from factory.pipeline.builder.artifact_store import store_file

logger = structlog.get_logger(__name__)


async def provision_server_export(deployment: Deployment, build: Build) -> Deployment:
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

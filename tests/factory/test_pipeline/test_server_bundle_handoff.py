from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from factory.models.build import Build
from factory.models.deployment import Deployment, DeploymentFormat, DeploymentStatus
from factory.pipeline.builder.assembler import assemble
from factory.pipeline.builder.packager import package
from factory.pipeline.deployer.provisioner import provision


@pytest.mark.anyio
async def test_server_bundle_is_buildable_and_handoff_ready(
    sample_requirements,
    sample_blueprint,
    monkeypatch,
    tmp_path,
) -> None:
    requirements = sample_requirements.model_copy(
        update={"deployment_format": "server", "deployment_target": "client_server"}
    )
    blueprint = sample_blueprint.model_copy(
        update={
            "deployment_spec": sample_blueprint.deployment_spec.model_copy(
                update={"format": "server", "target": "client_docker_compose"}
            )
        }
    )
    build = Build(requirements_id=requirements.id, org_id=requirements.org_id)

    artifact_root = tmp_path / "artifacts"
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    async def fake_store_container(image_tag, build_id):
        artifact_dir = artifact_root / str(build_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        tarball_path = artifact_dir / "employee.tar"
        tarball_path.write_text(f"container image for {image_tag}")
        return str(tarball_path)

    monkeypatch.setattr("factory.pipeline.builder.artifact_store.ARTIFACT_ROOT", artifact_root)
    monkeypatch.setattr("factory.pipeline.builder.packager.subprocess.run", fake_run)
    monkeypatch.setattr("factory.pipeline.builder.packager.store_container_tarball", fake_store_container)

    assembled = await assemble(blueprint, requirements, build)
    build_dir = Path(str(assembled.metadata["build_dir"]))

    try:
        packaged = await package(assembled)
        deployment = Deployment(build_id=packaged.id, org_id=packaged.org_id, format=DeploymentFormat.SERVER)
        provisioned = await provision(deployment, packaged)

        server_package = next(
            artifact for artifact in packaged.artifacts if artifact.artifact_type == "server_package"
        )
        bundle_path = Path(server_package.location)
        assert bundle_path.exists()

        with ZipFile(bundle_path) as archive:
            names = set(archive.namelist())
            assert "app/Dockerfile" in names
            assert "app/run.py" in names
            assert "app/config.yaml" in names
            assert "app/package_manifest.json" in names
            assert "app/static/index.html" in names
            assert "docker-compose.yml" in names
            assert ".env.example" in names
            assert "README.md" in names
            assert "bundle-metadata.json" in names
            metadata = json.loads(archive.read("bundle-metadata.json"))

        assert metadata["deployment_format"] == "server"
        assert metadata["runtime_template"] == "server_compose_bundle"
        assert metadata["config_path"] == "app/config.yaml"
        assert metadata["compose_file"] == "docker-compose.yml"
        assert "app/static/index.html" in metadata["included_files"]
        assert packaged.metadata["runtime_template"] == "server_compose_bundle"

        assert provisioned.status == DeploymentStatus.PENDING_CLIENT_ACTION
        assert provisioned.infrastructure["artifact_path"] == str(bundle_path)
        assert provisioned.infrastructure["runtime_template"] == "server_compose_bundle"
        assert provisioned.infrastructure["handoff_ready"] is True

        assert calls[0] == ["npm", "ci"]
        assert calls[1] == ["npm", "run", "build"]
        assert any(command[:3] == ["docker", "build", "-t"] for command in calls)
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)

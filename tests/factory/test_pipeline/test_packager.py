"""Tests for the packager stage."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from factory.models.build import BuildStatus
from factory.pipeline.builder.packager import package


@pytest.mark.anyio
async def test_packager_builds_and_records_artifact(sample_build, monkeypatch, tmp_path) -> None:
    sample_build.metadata["build_dir"] = str(tmp_path)
    Path(sample_build.metadata["build_dir"]).mkdir(parents=True, exist_ok=True)

    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="built", stderr="")

    async def fake_store(image_tag, build_id):
        return f"/tmp/forge-artifacts/{build_id}/employee.tar"

    monkeypatch.setattr("factory.pipeline.builder.packager.subprocess.run", fake_run)
    monkeypatch.setattr("factory.pipeline.builder.packager.store_container_tarball", fake_store)

    result = await package(sample_build)

    assert result.metadata["image_tag"].startswith(f"forge-employee-{sample_build.id}")
    assert result.metadata["image_tarball"].endswith("employee.tar")
    assert result.artifacts[0].location.endswith("employee.tar")
    assert calls[0][:3] == ["docker", "build", "-t"]


@pytest.mark.anyio
async def test_packager_handles_docker_failure(sample_build, monkeypatch, tmp_path) -> None:
    sample_build.metadata["build_dir"] = str(tmp_path)
    Path(sample_build.metadata["build_dir"]).mkdir(parents=True, exist_ok=True)

    def fake_run(command, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="build failed")

    monkeypatch.setattr("factory.pipeline.builder.packager.subprocess.run", fake_run)
    result = await package(sample_build)
    assert result.status == BuildStatus.FAILED
    assert any(log.stage == "packager" and log.level == "error" for log in result.logs)

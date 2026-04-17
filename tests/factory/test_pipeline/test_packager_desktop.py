from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from factory.pipeline.builder.packager import package


@pytest.mark.anyio
async def test_packager_builds_desktop_installers_when_requested(
    sample_build,
    monkeypatch,
    tmp_path,
) -> None:
    build_dir = tmp_path
    frontend_dir = build_dir / "portal" / "employee_app"
    dist_dir = frontend_dir / "dist"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)
    installer_path = dist_dir / "forge-employee.AppImage"
    installer_path.write_text("binary")

    sample_build.metadata.update(
        {
            "build_dir": str(build_dir),
            "frontend_dir": str(frontend_dir),
            "deployment_format": "desktop",
            "employee_id": "demo-employee",
            "employee_name": "Demo Employee",
            "desktop_backend_url": "https://demo.example.com",
        }
    )

    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    async def fake_store_container(image_tag, build_id):
        return str(tmp_path / "employee.tar")

    async def fake_store_file(path, build_id, *, artifact_type="artifact"):
        return str(tmp_path / artifact_type / Path(path).name)

    monkeypatch.setattr("factory.pipeline.builder.packager.subprocess.run", fake_run)
    monkeypatch.setattr("factory.pipeline.builder.packager.store_container_tarball", fake_store_container)
    monkeypatch.setattr("factory.pipeline.builder.packager.store_file", fake_store_file)

    result = await package(sample_build)

    assert any(command[:2] == ["npx", "electron-builder"] for command in calls)
    assert any(artifact.artifact_type == "desktop_installer" for artifact in result.artifacts)


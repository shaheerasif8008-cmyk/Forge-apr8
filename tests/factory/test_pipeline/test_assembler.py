"""Tests for the builder assembler stage."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from factory.pipeline.builder.assembler import assemble


@pytest.mark.anyio
async def test_assembler_creates_build_directory(sample_requirements, sample_blueprint, sample_build) -> None:
    build = await assemble(sample_blueprint, sample_requirements, sample_build)
    build_dir = Path(str(build.metadata["build_dir"]))

    try:
        assert (build_dir / "employee_runtime").exists()
        assert (build_dir / "portal" / "employee_app").exists()
        assert (build_dir / "component_library" / "interfaces.py").exists()
        assert (build_dir / "component_library" / "status.py").exists()
        assert (build_dir / "component_library" / "work" / "text_processor.py").exists()
        assert (build_dir / "component_library" / "work" / "schemas.py").exists()
        assert (build_dir / "component_library" / "quality" / "schemas.py").exists()
        assert (build_dir / "component_library" / "quality" / "autonomy_matrix.yaml").exists()
        assert (build_dir / "component_library" / "tools" / "adapter_runtime.py").exists()
        assert (build_dir / "component_library" / "tools" / "crm_tool.py").exists() is False
        assert (build_dir / "generated").exists()
        assert (build_dir / "Dockerfile").exists()
        dockerignore = (build_dir / ".dockerignore").read_text()
        assert "portal/employee_app/node_modules" in dockerignore
        assert "portal/employee_app/out" in dockerignore
        assert (build_dir / "requirements.txt").exists()
        assert (build_dir / "run.py").exists()

        config = json.loads((build_dir / "config.yaml").read_text())
        assert config["employee_name"] == sample_blueprint.employee_name
        assert config["workflow"] == "legal_intake"
        manifest = config["manifest"]
        assert manifest["kernel_baseline"]["version"] == "1.0.0"
        assert manifest["kernel_baseline"]["required_lanes"] == ["knowledge_work", "business_process", "hybrid"]
        assert manifest["workflow_packs"]
        frontend_config = (build_dir / "portal" / "employee_app" / "app" / "config.ts").read_text()
        assert str(sample_blueprint.id) in frontend_config
        assert sample_blueprint.employee_name in frontend_config
        assert "export function resolveApiBaseUrl" in frontend_config
        assert "export function resolveWsBaseUrl" in frontend_config
        assert not any(path.is_symlink() for path in build_dir.rglob("*"))
    finally:
        if build_dir.exists():
            shutil.rmtree(build_dir)

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
        assert (build_dir / "component_library" / "work" / "text_processor.py").exists()
        assert (build_dir / "component_library" / "work" / "schemas.py").exists()
        assert (build_dir / "component_library" / "tools" / "crm_tool.py").exists() is False
        assert (build_dir / "generated").exists()
        assert (build_dir / "Dockerfile").exists()
        assert (build_dir / "requirements.txt").exists()
        assert (build_dir / "run.py").exists()

        config = json.loads((build_dir / "config.yaml").read_text())
        assert config["employee_name"] == sample_blueprint.employee_name
        assert config["workflow"] == "legal_intake"
        assert not any(path.is_symlink() for path in build_dir.rglob("*"))
    finally:
        if build_dir.exists():
            shutil.rmtree(build_dir)

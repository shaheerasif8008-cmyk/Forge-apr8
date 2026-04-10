"""Integration test for the full factory pipeline (no Docker required)."""

from __future__ import annotations

import pytest

from factory.models.build import Build, BuildStatus
from factory.workers.pipeline_worker import start_pipeline


@pytest.mark.anyio
async def test_pipeline_completes(sample_requirements) -> None:
    build = Build(
        blueprint_id=sample_requirements.id,
        org_id=sample_requirements.org_id,
    )
    result = await start_pipeline(sample_requirements, build)
    assert result.status == BuildStatus.PASSED
    assert len(result.logs) > 0
    assert len(result.artifacts) > 0

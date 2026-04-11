from __future__ import annotations

import pytest

from component_library.data.working_memory import WorkingMemory


@pytest.mark.anyio
async def test_working_memory_set_get_clear() -> None:
    memory = WorkingMemory()
    await memory.initialize({"org_id": "org-1", "employee_id": "employee-1"})
    await memory.set_context("task-1", "stage", {"value": "extract"})
    assert await memory.get_context("task-1", "stage") == {"value": "extract"}
    await memory.clear_task("task-1")
    assert await memory.get_context("task-1", "stage") is None

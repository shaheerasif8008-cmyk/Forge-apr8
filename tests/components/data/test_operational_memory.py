from __future__ import annotations

import pytest

from component_library.data.operational_memory import OperationalMemory


@pytest.mark.anyio
async def test_operational_memory_store_retrieve_search() -> None:
    memory = OperationalMemory()
    await memory.initialize({"org_id": "org-1", "employee_id": "employee-1"})
    await memory.store("pref:quiet_hours", {"value": "after 5pm"}, "preference")
    retrieved = await memory.retrieve("pref:quiet_hours")
    results = await memory.search("quiet", category="preference")
    assert retrieved is not None
    assert retrieved["value"]["value"] == "after 5pm"
    assert len(results) == 1

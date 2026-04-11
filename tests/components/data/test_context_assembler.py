from __future__ import annotations

import pytest

from component_library.data.context_assembler import ContextAssembler
from component_library.data.operational_memory import OperationalMemory


@pytest.mark.anyio
async def test_context_assembler_uses_operational_memory() -> None:
    memory = OperationalMemory()
    await memory.initialize({"org_id": "org-1", "employee_id": "employee-1"})
    await memory.store("firm:name", {"value": "Cartwright"}, "general")

    assembler = ContextAssembler()
    await assembler.initialize(
        {
            "operational_memory": memory,
            "system_identity": "Arthur is a legal intake associate.",
        }
    )
    context = await assembler.assemble("Tell me about the firm", "employee-1", "org-1", "", 8000)
    assert "Cartwright" in context

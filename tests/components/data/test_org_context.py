from __future__ import annotations

import pytest

from component_library.data.org_context import OrgContext


@pytest.mark.anyio
async def test_org_context_supervisor_lookup() -> None:
    context = OrgContext()
    await context.initialize(
        {
            "people": [
                {"name": "Sarah Cartwright", "role": "Partner", "email": "sarah@example.com", "relationship": "supervisor"}
            ],
            "escalation_chain": ["Sarah Cartwright"],
        }
    )
    assert context.get_supervisor() is not None

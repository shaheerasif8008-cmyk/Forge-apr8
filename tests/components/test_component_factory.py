from __future__ import annotations

import component_library.data.operational_memory  # noqa: F401
import component_library.work.text_processor  # noqa: F401
from component_library.component_factory import create_components


async def test_create_components_initializes_requested_components() -> None:
    components = await create_components(
        ["text_processor", "operational_memory"],
        {"operational_memory": {"org_id": "org-1", "employee_id": "employee-1"}},
    )
    assert set(components.keys()) == {"text_processor", "operational_memory"}

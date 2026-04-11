from __future__ import annotations

import pytest

from component_library.quality.audit_system import AuditSystem


@pytest.mark.anyio
async def test_audit_system_hash_chain_verifies() -> None:
    audit = AuditSystem()
    await audit.initialize({})
    await audit.log_event("employee-1", "org-1", "task_started", {"node": "start"})
    await audit.log_event("employee-1", "org-1", "task_completed", {"node": "end"})
    verification = await audit.verify_chain("employee-1")
    assert verification.valid is True

from __future__ import annotations

from employee_runtime.workflow_packs.base import WorkflowPack
from employee_runtime.workflow_packs.packs import BUILTIN_WORKFLOW_PACKS

_PACKS: dict[str, WorkflowPack] = {pack.pack_id: pack for pack in BUILTIN_WORKFLOW_PACKS}


def _copy_pack(pack: WorkflowPack) -> WorkflowPack:
    return pack.model_copy(deep=True)


def list_workflow_packs() -> list[WorkflowPack]:
    return [_copy_pack(pack) for pack in _PACKS.values()]


def get_workflow_pack(pack_id: str) -> WorkflowPack:
    try:
        return _copy_pack(_PACKS[pack_id])
    except KeyError as exc:
        raise ValueError(f"Unknown workflow pack '{pack_id}'. Available: {sorted(_PACKS)}") from exc


def select_pack_ids(role_title: str, required_tools: list[str] | None = None) -> list[str]:
    lowered_role = role_title.lower()
    selected = ["executive_assistant_pack"]
    if "account" in lowered_role or "finance" in lowered_role:
        selected.append("accounting_ops_pack")
    if "legal" in lowered_role or "law" in lowered_role or "intake" in lowered_role:
        selected.append("legal_intake_pack")
    if "ops" in lowered_role or "operation" in lowered_role or "coordinator" in lowered_role:
        selected.append("operations_coordinator_pack")
    if required_tools and any(tool in {"custom_api", "crm", "crm_tool", "custom_api_tool"} for tool in required_tools):
        selected.append("operations_coordinator_pack")
    return sorted(set(selected), key=selected.index)

"""Built-in workflow pack registry and requirement-based selection."""

from __future__ import annotations

from employee_runtime.workflow_packs.base import WorkflowPack
from employee_runtime.workflow_packs.packs import BUILTIN_WORKFLOW_PACKS

_PACKS: dict[str, WorkflowPack] = {pack.pack_id: pack for pack in BUILTIN_WORKFLOW_PACKS}


def list_workflow_packs() -> list[WorkflowPack]:
    return list(_PACKS.values())


def get_workflow_pack(pack_id: str) -> WorkflowPack:
    try:
        return _PACKS[pack_id]
    except KeyError as exc:
        raise ValueError(f"Unknown workflow pack '{pack_id}'. Available: {sorted(_PACKS)}") from exc


def select_pack_ids(role_title: str, required_tools: list[str] | None = None) -> list[str]:
    lowered_role = role_title.lower()
    normalized_tools = {_normalize_tool_name(tool) for tool in (required_tools or [])}
    is_accounting = any(term in lowered_role for term in ("account", "finance", "bookkeep", "controller"))
    selected = ["accounting_ops_pack"] if is_accounting else ["executive_assistant_pack"]

    if is_accounting:
        selected.append("accounting_ops_pack")
    if any(term in lowered_role for term in ("legal", "law", "intake", "attorney")):
        selected.append("legal_intake_pack")
    if any(term in lowered_role for term in ("ops", "operation", "coordinator")):
        selected.append("operations_coordinator_pack")
    if normalized_tools & {"crm_tool", "custom_api_tool"}:
        selected.append("operations_coordinator_pack")

    return list(dict.fromkeys(selected))


def _normalize_tool_name(tool_name: str) -> str:
    lowered = tool_name.strip().lower()
    aliases = {
        "email": "email_tool",
        "gmail": "email_tool",
        "outlook": "email_tool",
        "calendar": "calendar_tool",
        "slack": "messaging_tool",
        "teams": "messaging_tool",
        "messaging": "messaging_tool",
        "crm": "crm_tool",
        "custom_api": "custom_api_tool",
    }
    return aliases.get(lowered, lowered)

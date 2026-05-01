"""Implementation status registry for selectable component-library modules.

Status meanings:
- ``production``: safe for default Architect selection.
- ``reference``: implemented enough to study or enable explicitly, but not chosen by default.
- ``stub``: placeholder only; never select by default.
"""

from __future__ import annotations

from typing import Final

COMPONENT_IMPLEMENTATION_STATUS: Final[dict[str, str]] = {
    # models
    "anthropic_provider": "production",
    "litellm_router": "production",
    # work
    "text_processor": "production",
    "document_analyzer": "production",
    "draft_generator": "production",
    "communication_manager": "production",
    "scheduler_manager": "production",
    "workflow_executor": "production",
    "data_analyzer": "production",
    "research_engine": "production",
    "monitor_scanner": "production",
    "work_intake_router": "production",
    "task_orchestrator": "production",
    # tools
    "email_tool": "production",
    "calendar_tool": "production",
    "messaging_tool": "production",
    "crm_tool": "production",
    "search_tool": "production",
    "file_storage_tool": "production",
    "document_ingestion": "production",
    "custom_api_tool": "production",
    # data
    "operational_memory": "production",
    "working_memory": "production",
    "context_assembler": "production",
    "org_context": "production",
    "knowledge_base": "production",
    # quality
    "confidence_scorer": "production",
    "audit_system": "production",
    "input_protection": "production",
    "verification_layer": "production",
    "autonomy_manager": "production",
    "approval_manager": "production",
    "adversarial_review": "production",
    "compliance_rules": "production",
    "explainability": "production",
    "evidence_binder": "production",
    "policy_authority_engine": "production",
    "quality_review_engine": "production",
    "roi_meter": "production",
}


def is_component_production_ready(component_id: str) -> bool:
    return COMPONENT_IMPLEMENTATION_STATUS.get(component_id, "stub") == "production"

from __future__ import annotations

import pytest

from employee_runtime.workflow_packs import get_workflow_pack, list_workflow_packs, select_pack_ids


BASELINE_LANES = {"knowledge_work", "business_process", "hybrid"}
CANONICAL_TOOL_IDS = {
    "email_tool",
    "calendar_tool",
    "messaging_tool",
    "custom_api_tool",
    "crm_tool",
    "file_storage_tool",
    "document_ingestion",
}


def test_builtin_workflow_packs_are_registered() -> None:
    packs = list_workflow_packs()
    pack_ids = {pack.pack_id for pack in packs}

    assert {
        "executive_assistant_pack",
        "operations_coordinator_pack",
        "accounting_ops_pack",
        "legal_intake_pack",
    }.issubset(pack_ids)


def test_workflow_pack_exposes_baseline_contract_fields() -> None:
    pack = get_workflow_pack("operations_coordinator_pack")

    assert pack.display_name == "Operations Coordinator"
    assert "business_process" in pack.supported_lanes
    assert pack.required_tools
    assert pack.output_templates["business_process"]
    assert pack.evaluation_cases
    assert pack.roi_metrics["default_minutes_saved"] > 0


def test_select_pack_ids_uses_role_and_required_tools() -> None:
    selected = select_pack_ids(
        role_title="AI Accountant",
        required_tools=["email", "calendar", "messaging"],
    )

    assert "accounting_ops_pack" in selected
    assert selected[0] == "accounting_ops_pack"
    assert "executive_assistant_pack" not in selected


def test_builtin_workflow_packs_use_baseline_lane_contract() -> None:
    for pack in list_workflow_packs():
        assert set(pack.supported_lanes).issubset(BASELINE_LANES)
        assert set(pack.output_templates).issubset(BASELINE_LANES)
        assert {case.expected_lane for case in pack.evaluation_cases}.issubset(BASELINE_LANES)


def test_builtin_workflow_packs_use_canonical_tool_ids() -> None:
    for pack in list_workflow_packs():
        assert set(pack.required_tools).issubset(CANONICAL_TOOL_IDS)
        assert set(pack.optional_tools).issubset(CANONICAL_TOOL_IDS)


def test_select_pack_ids_uses_custom_api_and_crm_tools_for_operations() -> None:
    for tool_id in ("custom_api_tool", "crm_tool", "custom_api", "crm"):
        selected = select_pack_ids(
            role_title="Customer Success Coordinator",
            required_tools=[tool_id],
        )

        assert "operations_coordinator_pack" in selected


def test_accounting_ops_pack_covers_month_end_close_inputs_and_boundaries() -> None:
    pack = get_workflow_pack("accounting_ops_pack")

    assert "month-end close" in pack.description.lower()
    for source in ("bank feed", "GL", "AP aging", "AR aging"):
        assert source in pack.domain_vocabulary
    for output in ("variance analysis", "close checklist", "statement draft"):
        assert output in pack.output_templates["hybrid"]
    assert pack.autonomy_overrides["post_journal_entry"] == "approval_required"
    assert pack.autonomy_overrides["send_external_financial_statement"] == "approval_required"
    assert pack.autonomy_overrides["file_tax_return"] == "forbidden"
    assert any(case.case_id == "accounting_month_end_close" for case in pack.evaluation_cases)


def test_select_pack_ids_keeps_legal_and_operations_paths_available() -> None:
    legal_selected = select_pack_ids(role_title="Legal Intake Associate", required_tools=["email"])
    operations_selected = select_pack_ids(role_title="Executive Assistant", required_tools=["crm"])

    assert legal_selected == ["executive_assistant_pack", "legal_intake_pack"]
    assert operations_selected == ["executive_assistant_pack", "operations_coordinator_pack"]


def test_get_workflow_pack_raises_for_unknown_pack() -> None:
    with pytest.raises(ValueError, match="Unknown workflow pack 'missing_pack'"):
        get_workflow_pack("missing_pack")


def test_registry_returns_defensive_copies() -> None:
    pack = get_workflow_pack("operations_coordinator_pack")
    pack.supported_lanes.append("not_a_kernel_lane")
    pack.output_templates["not_a_kernel_lane"] = "mutated"
    pack.evaluation_cases[0].required_terms.append("mutated")

    fresh_pack = get_workflow_pack("operations_coordinator_pack")

    assert "not_a_kernel_lane" not in fresh_pack.supported_lanes
    assert "not_a_kernel_lane" not in fresh_pack.output_templates
    assert "mutated" not in fresh_pack.evaluation_cases[0].required_terms

    listed_pack = next(
        pack for pack in list_workflow_packs() if pack.pack_id == "operations_coordinator_pack"
    )

    assert "not_a_kernel_lane" not in listed_pack.supported_lanes
    assert "not_a_kernel_lane" not in listed_pack.output_templates
    assert "mutated" not in listed_pack.evaluation_cases[0].required_terms

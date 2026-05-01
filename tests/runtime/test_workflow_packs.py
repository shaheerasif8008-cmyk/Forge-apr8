from __future__ import annotations

from employee_runtime.workflow_packs import get_workflow_pack, list_workflow_packs, select_pack_ids


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

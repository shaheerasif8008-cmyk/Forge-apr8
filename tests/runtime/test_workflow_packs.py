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
    assert "executive_assistant_pack" in selected

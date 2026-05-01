from __future__ import annotations

import pytest

import component_library.quality.evidence_binder  # noqa: F401
import component_library.quality.policy_authority_engine  # noqa: F401
import component_library.quality.quality_review_engine  # noqa: F401
import component_library.quality.roi_meter  # noqa: F401
import component_library.work.task_orchestrator  # noqa: F401
import component_library.work.work_intake_router  # noqa: F401
from component_library.component_factory import create_components
from component_library.quality.evidence_binder import EvidenceBinderInput
from component_library.quality.policy_authority_engine import AuthorityInput
from component_library.quality.quality_review_engine import QualityReviewInput
from component_library.quality.roi_meter import RoiMetricInput
from component_library.registry import describe_all_components, get_component
from component_library.work.task_orchestrator import TaskOrchestrationInput
from component_library.work.work_intake_router import WorkIntakeInput


@pytest.mark.anyio
async def test_horizontal_modules_are_registered_and_initializable() -> None:
    component_ids = [
        "work_intake_router",
        "task_orchestrator",
        "evidence_binder",
        "policy_authority_engine",
        "quality_review_engine",
        "roi_meter",
    ]

    components = await create_components(component_ids, {})
    descriptions = {description.component_id: description for description in describe_all_components()}

    assert set(components) == set(component_ids)
    for component_id in component_ids:
        assert get_component(component_id).component_id == component_id
        assert descriptions[component_id].status == "production"


@pytest.mark.anyio
async def test_work_intake_router_classifies_role_risk_and_missing_inputs() -> None:
    router = get_component("work_intake_router")()
    await router.initialize({})

    result = await router.execute(
        WorkIntakeInput(
            request_text="Prepare the Q3 investor deck from the latest CRM pipeline and finance metrics by Friday.",
            channel="slack",
            sender="ceo@example.com",
            known_context={"available_inputs": ["CRM pipeline"]},
        )
    )

    assert result.task_type == "presentation"
    assert result.risk_tier == "medium"
    assert result.urgency == "deadline"
    assert "finance metrics" in result.missing_inputs
    assert "work_product_renderer" in result.recommended_modules


@pytest.mark.anyio
async def test_task_orchestrator_builds_dependency_plan_from_intake() -> None:
    orchestrator = get_component("task_orchestrator")()
    await orchestrator.initialize({})

    result = await orchestrator.execute(
        TaskOrchestrationInput(
            task_type="month_end_close",
            objective="Prepare month-end close package",
            required_inputs=["bank statement", "GL", "AP aging"],
            risk_tier="high",
        )
    )

    assert [step.name for step in result.steps][:3] == ["collect_inputs", "validate_inputs", "perform_work"]
    assert result.steps[-1].requires_approval is True
    assert result.blockers == []
    assert result.status == "ready"


@pytest.mark.anyio
async def test_evidence_binder_creates_review_packet_and_missing_evidence() -> None:
    binder = get_component("evidence_binder")()
    await binder.initialize({})

    result = await binder.evaluate(
        EvidenceBinderInput(
            task_id="close-1",
            sources=[
                {"name": "bank statement", "uri": "s3://proof/bank.csv"},
                {"name": "GL", "uri": "s3://proof/gl.csv"},
            ],
            calculations=[{"name": "cash difference", "value": -400}],
            assumptions=["Controller reviews unexplained differences."],
            required_evidence=["bank statement", "GL", "AP aging"],
        )
    )

    assert result.packet_id == "evidence:close-1"
    assert result.complete is False
    assert result.missing_evidence == ["AP aging"]
    assert result.audit_summary["source_count"] == 2


@pytest.mark.anyio
async def test_policy_authority_engine_blocks_forbidden_and_requires_approval() -> None:
    engine = get_component("policy_authority_engine")()
    await engine.initialize({})

    forbidden = await engine.evaluate(
        AuthorityInput(action="file_tax_return", risk_tier="high", amount=0, external_impact=True)
    )
    approval = await engine.evaluate(
        AuthorityInput(action="send_external_report", risk_tier="medium", amount=25000, external_impact=True)
    )

    assert forbidden.decision == "forbidden"
    assert "never do alone" in forbidden.rationale.lower()
    assert approval.decision == "requires_approval"
    assert approval.required_approver == "supervisor"


@pytest.mark.anyio
async def test_quality_review_engine_checks_evidence_numbers_and_policy() -> None:
    reviewer = get_component("quality_review_engine")()
    await reviewer.initialize({})

    result = await reviewer.evaluate(
        QualityReviewInput(
            output_text="Adjusted bank balance is $10,100 and unexplained difference is $400.",
            required_terms=["adjusted bank balance", "controller review"],
            expected_numbers=[10100, 400],
            policy_decision="requires_approval",
        )
    )

    assert result.passed is False
    assert "controller review" in result.missing_terms
    assert result.numeric_checks_passed is True
    assert "approval required" in result.flags


@pytest.mark.anyio
async def test_roi_meter_computes_client_value() -> None:
    meter = get_component("roi_meter")()
    await meter.initialize({"default_hourly_rate": 125.0})

    result = await meter.evaluate(
        RoiMetricInput(
            tasks_completed=12,
            minutes_saved=420,
            errors_caught=2,
            rework_minutes=30,
            revenue_influenced=15000.0,
        )
    )

    assert result.hours_saved == 7.0
    assert result.labor_value_usd == 875.0
    assert result.net_minutes_saved == 390
    assert result.roi_signals["errors_caught"] == 2

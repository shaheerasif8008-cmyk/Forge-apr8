from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from component_library.quality.explainability import Explainability
from component_library.quality.schemas import DecisionPoint
from employee_runtime.core.api import create_employee_app


@pytest.mark.anyio
async def test_explainability_capture_and_retrieve_in_memory() -> None:
    engine = Explainability()
    await engine.initialize({})
    task_id = uuid4()
    record = await engine.capture(
        DecisionPoint(
            task_id=task_id,
            node_id="score_confidence",
            decision="needs_review",
            rationale="Confidence was below the automatic threshold.",
            inputs_considered={"confidence_report": {"overall_score": 0.42}},
            confidence=0.42,
            modules_invoked=["confidence_scorer"],
            latency_ms=12,
        )
    )
    assert record.node_id == "score_confidence"
    fetched = await engine.get_records(str(task_id))
    assert len(fetched) == 1
    assert fetched[0].record_id == record.record_id


@pytest.mark.anyio
async def test_reasoning_api_endpoints_return_records() -> None:
    app = create_employee_app(
        "arthur",
        {
            "org_id": "org-1",
            "manifest": {
                "employee_id": "arthur",
                "org_id": "org-1",
                "employee_name": "Arthur",
                "role_title": "Legal Intake Agent",
                "workflow": "legal_intake",
                "components": [
                    {"id": "litellm_router", "category": "models", "config": {"primary_model": "x", "fallback_model": "y"}},
                    {"id": "text_processor", "category": "work", "config": {}},
                    {"id": "document_analyzer", "category": "work", "config": {}},
                    {"id": "draft_generator", "category": "work", "config": {}},
                    {"id": "email_tool", "category": "tools", "config": {}},
                    {"id": "operational_memory", "category": "data", "config": {}},
                    {"id": "working_memory", "category": "data", "config": {}},
                    {"id": "context_assembler", "category": "data", "config": {}},
                    {"id": "org_context", "category": "data", "config": {}},
                    {"id": "confidence_scorer", "category": "quality", "config": {}},
                    {"id": "audit_system", "category": "quality", "config": {}},
                    {"id": "autonomy_manager", "category": "quality", "config": {}},
                    {"id": "explainability", "category": "quality", "config": {}},
                    {"id": "input_protection", "category": "quality", "config": {}},
                    {"id": "verification_layer", "category": "quality", "config": {}},
                ],
                "tool_permissions": ["email_tool"],
                "ui": {"app_badge": "Hosted web", "capabilities": ["triage legal intake"]},
                "org_map": [],
            },
        },
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tasks",
            json={
                "input": "My name is John Doe. I was injured in a car accident last week. Reach me at john@example.com.",
                "context": {},
                "conversation_id": "default",
            },
        )
        assert response.status_code == 200
        task_id = response.json()["task_id"]

        records_response = await client.get(f"/api/v1/reasoning/{task_id}")
        assert records_response.status_code == 200
        records = records_response.json()
        assert records
        record_id = records[0]["record_id"]

        record_response = await client.get(f"/api/v1/reasoning/record/{record_id}")
        assert record_response.status_code == 200
        payload = record_response.json()
        assert payload["record_id"] == record_id
        assert payload["node_id"]

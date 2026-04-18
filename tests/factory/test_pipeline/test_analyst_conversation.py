from __future__ import annotations

import pytest

from factory.database import get_db_session
from factory.main import app
from factory.pipeline.analyst.conversation import (
    CompletenessAssessment,
    IntentClassification,
    QuestionOutput,
    RequirementsExtraction,
)


@pytest.mark.anyio
async def test_analyst_legal_intake_completes_in_three_turns(client, sample_org, monkeypatch) -> None:
    calls = {"completeness": 0}

    async def fake_db():
        yield object()

    async def fake_save_requirements(session, requirements):
        return requirements

    async def fake_llm(response_model, *, prompt_name, payload):
        if response_model is IntentClassification:
            return IntentClassification(
                employee_type="legal_intake_associate",
                risk_tier="medium",
                summary="Handles legal intake triage.",
            )
        if response_model is RequirementsExtraction:
            message_text = " ".join(message["content"] for message in payload["messages"])
            return RequirementsExtraction(
                role_summary="Handle legal intake triage.",
                primary_responsibilities=["process client intake", "qualify matters"],
                required_tools=["email", "crm"],
                communication_channels=["email", "app"],
                supervisor_email="partner@acme.com" if "partner@acme.com" in message_text else "",
                name="Arthur" if "Arthur" in message_text else "",
                role_title="Legal Intake Associate" if "Arthur" in message_text else "",
            )
        if response_model is CompletenessAssessment:
            calls["completeness"] += 1
            return CompletenessAssessment(score=0.5 if calls["completeness"] < 3 else 0.9, gap="Need supervisor email")
        if response_model is QuestionOutput:
            return QuestionOutput(question="Who supervises this employee and what email should it use?")
        raise AssertionError(response_model)

    app.dependency_overrides[get_db_session] = fake_db
    monkeypatch.setattr("factory.api.analyst.save_requirements", fake_save_requirements)
    monkeypatch.setattr("factory.pipeline.analyst.conversation._call_structured_llm", fake_llm)

    created = await client.post("/api/v1/analyst/sessions", json={"org_id": str(sample_org.id), "prompt": "Build a legal intake employee."})
    session_id = created.json()["session_id"]
    await client.post(f"/api/v1/analyst/sessions/{session_id}/messages", json={"role": "user", "content": "It should be named Arthur."})
    final = await client.post(f"/api/v1/analyst/sessions/{session_id}/messages", json={"role": "user", "content": "Supervisor is partner@acme.com."})
    app.dependency_overrides.clear()

    assert created.status_code == 200
    assert final.status_code == 200
    assert final.json()["is_complete"] is True
    assert final.json()["requirements_id"]


@pytest.mark.anyio
async def test_analyst_ambiguous_request_requires_multiple_turns(client, sample_org, monkeypatch) -> None:
    calls = {"completeness": 0}

    async def fake_db():
        yield object()

    async def fake_save_requirements(session, requirements):
        return requirements

    async def fake_llm(response_model, *, prompt_name, payload):
        if response_model is IntentClassification:
            return IntentClassification(employee_type="executive_assistant", risk_tier="low", summary="Coordinate executive operations.")
        if response_model is RequirementsExtraction:
            return RequirementsExtraction(
                role_summary="Coordinate inbox and calendar.",
                primary_responsibilities=["coordinate scheduling"],
                required_tools=["email", "calendar", "slack"],
                communication_channels=["email", "slack"],
            )
        if response_model is CompletenessAssessment:
            calls["completeness"] += 1
            return CompletenessAssessment(score=min(0.2 * calls["completeness"], 0.9), gap="Need role title")
        if response_model is QuestionOutput:
            return QuestionOutput(question="What exact executive assistant responsibilities and reporting line should it have?")
        raise AssertionError(response_model)

    app.dependency_overrides[get_db_session] = fake_db
    monkeypatch.setattr("factory.api.analyst.save_requirements", fake_save_requirements)
    monkeypatch.setattr("factory.pipeline.analyst.conversation._call_structured_llm", fake_llm)

    created = await client.post("/api/v1/analyst/sessions", json={"org_id": str(sample_org.id), "prompt": "I need an ops helper."})
    session_id = created.json()["session_id"]
    for index in range(4):
        response = await client.post(
            f"/api/v1/analyst/sessions/{session_id}/messages",
            json={"role": "user", "content": f"Clarification {index}."},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls["completeness"] >= 5
    assert response.json()["is_complete"] is True


@pytest.mark.anyio
async def test_analyst_incomplete_request_times_out_after_ten_turns(client, sample_org, monkeypatch) -> None:
    async def fake_db():
        yield object()

    async def fake_llm(response_model, *, prompt_name, payload):
        if response_model is IntentClassification:
            return IntentClassification(employee_type="legal_intake_associate", risk_tier="medium", summary="Incomplete request.")
        if response_model is RequirementsExtraction:
            return RequirementsExtraction(role_summary="Incomplete request.")
        if response_model is CompletenessAssessment:
            return CompletenessAssessment(score=0.2, gap="Everything")
        if response_model is QuestionOutput:
            return QuestionOutput(question="Please provide more detail.")
        raise AssertionError(response_model)

    app.dependency_overrides[get_db_session] = fake_db
    monkeypatch.setattr("factory.pipeline.analyst.conversation._call_structured_llm", fake_llm)

    created = await client.post("/api/v1/analyst/sessions", json={"org_id": str(sample_org.id), "prompt": "Need some AI help."})
    session_id = created.json()["session_id"]
    last = created
    for index in range(9):
        last = await client.post(
            f"/api/v1/analyst/sessions/{session_id}/messages",
            json={"role": "user", "content": f"Still vague {index}"},
        )
    app.dependency_overrides.clear()

    assert last.status_code == 200
    assert last.json()["is_complete"] is False
    assert last.json()["timed_out"] is True

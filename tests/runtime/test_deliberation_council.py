from __future__ import annotations

import pytest

from component_library.quality.adversarial_review import AdversarialReview
from employee_runtime.modules.deliberation import Argument, DeliberationCouncil, Proposal, SupervisorReport, Verdict


@pytest.mark.anyio
async def test_deliberation_simple_approval(monkeypatch) -> None:
    council = DeliberationCouncil()

    async def fake_advocate(self, proposal, model):
        return Argument(role="advocate", model=model, reasoning="support", key_points=["safe"])

    async def fake_challenger(self, proposal, model):
        return Argument(role="challenger", model=model, reasoning="minor concern", key_points=[])

    async def fake_adjudicate(self, proposal, advocates, challengers, model):
        return Verdict(approved=True, confidence=0.82, majority_concerns=[], dissenting_views=[], reasoning="approved")

    async def fake_supervise(self, advocates, challengers, verdict):
        return SupervisorReport(rerun_needed=False, reason="ok", issues=[])

    monkeypatch.setattr("employee_runtime.modules.deliberation.advocate.AdvocateRole.argue", fake_advocate)
    monkeypatch.setattr("employee_runtime.modules.deliberation.challenger.ChallengerRole.argue", fake_challenger)
    monkeypatch.setattr("employee_runtime.modules.deliberation.adjudicator.AdjudicatorRole.adjudicate", fake_adjudicate)
    monkeypatch.setattr("employee_runtime.modules.deliberation.supervisor.ProcessSupervisor.supervise", fake_supervise)

    verdict = await council.deliberate(Proposal(proposal_id="p1", content="Send update", context={}, risk_tier="medium"))
    assert verdict.approved is True


@pytest.mark.anyio
async def test_deliberation_rejection(monkeypatch) -> None:
    council = DeliberationCouncil()

    async def fake_advocate(self, proposal, model):
        return Argument(role="advocate", model=model, reasoning="support", key_points=["speed"])

    async def fake_challenger(self, proposal, model):
        return Argument(role="challenger", model=model, reasoning="unsafe", key_points=["data leak"])

    async def fake_adjudicate(self, proposal, advocates, challengers, model):
        return Verdict(approved=False, confidence=0.31, majority_concerns=["data leak"], dissenting_views=["speed"], reasoning="rejected")

    async def fake_supervise(self, advocates, challengers, verdict):
        return SupervisorReport(rerun_needed=False, reason="ok", issues=[])

    monkeypatch.setattr("employee_runtime.modules.deliberation.advocate.AdvocateRole.argue", fake_advocate)
    monkeypatch.setattr("employee_runtime.modules.deliberation.challenger.ChallengerRole.argue", fake_challenger)
    monkeypatch.setattr("employee_runtime.modules.deliberation.adjudicator.AdjudicatorRole.adjudicate", fake_adjudicate)
    monkeypatch.setattr("employee_runtime.modules.deliberation.supervisor.ProcessSupervisor.supervise", fake_supervise)

    verdict = await council.deliberate(Proposal(proposal_id="p2", content="Delete data", context={}, risk_tier="high"))
    assert verdict.approved is False
    assert verdict.majority_concerns == ["data leak"]


@pytest.mark.anyio
async def test_deliberation_supervisor_forces_rerun(monkeypatch) -> None:
    council = DeliberationCouncil({"max_reruns": 2})
    calls = {"supervise": 0}

    async def fake_advocate(self, proposal, model):
        return Argument(role="advocate", model=model, reasoning=f"support-{model}", key_points=["safe"])

    async def fake_challenger(self, proposal, model):
        return Argument(role="challenger", model=model, reasoning=f"challenge-{model}", key_points=["risk"])

    async def fake_adjudicate(self, proposal, advocates, challengers, model):
        return Verdict(approved=True, confidence=0.6, majority_concerns=["risk"], dissenting_views=["safe"], reasoning="contested")

    async def fake_supervise(self, advocates, challengers, verdict):
        calls["supervise"] += 1
        return SupervisorReport(rerun_needed=calls["supervise"] == 1, reason="echo", issues=["echo"])

    monkeypatch.setattr("employee_runtime.modules.deliberation.advocate.AdvocateRole.argue", fake_advocate)
    monkeypatch.setattr("employee_runtime.modules.deliberation.challenger.ChallengerRole.argue", fake_challenger)
    monkeypatch.setattr("employee_runtime.modules.deliberation.adjudicator.AdjudicatorRole.adjudicate", fake_adjudicate)
    monkeypatch.setattr("employee_runtime.modules.deliberation.supervisor.ProcessSupervisor.supervise", fake_supervise)

    verdict = await council.deliberate(Proposal(proposal_id="p3", content="Act", context={}, risk_tier="medium"))
    assert verdict.approved is True
    assert calls["supervise"] == 2


@pytest.mark.anyio
async def test_deliberation_time_limit_exceeded(monkeypatch) -> None:
    council = DeliberationCouncil({"max_time_seconds": 0, "max_reruns": 1})
    verdict = await council.deliberate(Proposal(proposal_id="p4", content="Act", context={}, risk_tier="medium"))
    assert verdict.approved is False
    assert verdict.reasoning == "exceeded deliberation budget"


@pytest.mark.anyio
async def test_adversarial_review_wrapper_uses_council(monkeypatch) -> None:
    review = AdversarialReview()
    await review.initialize({})

    async def fake_deliberate(self, proposal, context=None):
        return Verdict(approved=True, confidence=0.8, majority_concerns=[], dissenting_views=[], reasoning="approved")

    monkeypatch.setattr("employee_runtime.modules.deliberation.council.DeliberationCouncil.deliberate", fake_deliberate)
    verdict = await review.evaluate({"proposal_id": "p5", "content": "Send brief", "context": {}, "risk_tier": "high"})
    assert verdict.approved is True


@pytest.mark.anyio
async def test_adversarial_review_fails_closed_when_council_provider_fails(monkeypatch) -> None:
    review = AdversarialReview()
    await review.initialize({})

    async def fake_deliberate(self, proposal, context=None):
        raise RuntimeError("provider quota exceeded")

    monkeypatch.setattr("employee_runtime.modules.deliberation.council.DeliberationCouncil.deliberate", fake_deliberate)
    verdict = await review.evaluate({"proposal_id": "p6", "content": "Send brief", "context": {}, "risk_tier": "high"})

    assert verdict.approved is False
    assert verdict.confidence == 0.0
    assert verdict.majority_concerns == ["Adversarial review unavailable; human review required."]

from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from employee_runtime.modules.deliberation.adjudicator import AdjudicatorRole
from employee_runtime.modules.deliberation.advocate import AdvocateRole
from employee_runtime.modules.deliberation.challenger import ChallengerRole
from employee_runtime.modules.deliberation.schemas import CouncilConfig, Proposal, Verdict
from employee_runtime.modules.deliberation.supervisor import ProcessSupervisor


class DeliberationCouncil:
    def __init__(
        self,
        config: CouncilConfig | dict[str, Any] | None = None,
        *,
        model_client: Any = None,
        audit_logger: Any = None,
    ) -> None:
        self.config = CouncilConfig.model_validate(config or {})
        self._model_client = model_client
        self._audit_logger = audit_logger
        self._advocate = AdvocateRole(model_client)
        self._challenger = ChallengerRole(model_client)
        self._adjudicator = AdjudicatorRole(model_client)
        self._supervisor = ProcessSupervisor(model_client)

    async def deliberate(self, proposal: Proposal, context: dict[str, Any] | None = None) -> Verdict:
        effective_proposal = proposal.model_copy(update={"context": context or proposal.context})
        start = monotonic()
        attempts = 0
        final_verdict = Verdict(
            approved=False,
            confidence=0.0,
            majority_concerns=["deliberation did not run"],
            dissenting_views=[],
            reasoning="uninitialized",
        )
        while attempts <= self.config.max_reruns:
            if monotonic() - start >= self.config.max_time_seconds:
                final_verdict = Verdict(
                    approved=False,
                    confidence=0.0,
                    majority_concerns=["deliberation budget exceeded"],
                    dissenting_views=[],
                    reasoning="exceeded deliberation budget",
                )
                await self._log_deliberation(effective_proposal, [], [], final_verdict, {"timed_out": True, "attempt": attempts})
                return final_verdict

            advocates = await asyncio.gather(
                *[self._advocate.argue(effective_proposal, model) for model in self._models_for_attempt(self.config.advocate_models, attempts)]
            )
            challengers = await asyncio.gather(
                *[self._challenger.argue(effective_proposal, model) for model in self._models_for_attempt(self.config.challenger_models, attempts)]
            )
            final_verdict = await self._adjudicator.adjudicate(
                effective_proposal,
                advocates,
                challengers,
                self.config.adjudicator_model,
            )
            supervision = await self._supervisor.supervise(advocates, challengers, final_verdict)
            await self._log_deliberation(
                effective_proposal,
                advocates,
                challengers,
                final_verdict,
                supervision.model_dump(mode="json") | {"attempt": attempts},
            )
            if not self.config.enable_reruns or not supervision.rerun_needed:
                return final_verdict
            attempts += 1

        return final_verdict

    def _models_for_attempt(self, models: list[str], attempt: int) -> list[str]:
        if attempt == 0 or not models:
            return models
        rotation = attempt % len(models)
        return models[rotation:] + models[:rotation]

    async def _log_deliberation(
        self,
        proposal: Proposal,
        advocates: list[Any],
        challengers: list[Any],
        verdict: Verdict,
        supervision: dict[str, Any],
    ) -> None:
        if self._audit_logger is None:
            return
        details = {
            "proposal": proposal.model_dump(mode="json"),
            "advocates": [argument.model_dump(mode="json") for argument in advocates],
            "challengers": [argument.model_dump(mode="json") for argument in challengers],
            "verdict": verdict.model_dump(mode="json"),
            "supervision": supervision,
            "occurred_at": datetime.now(UTC).isoformat(),
        }
        if callable(self._audit_logger):
            result = self._audit_logger(
                employee_id=str(proposal.context.get("employee_id", "employee-runtime")),
                org_id=str(proposal.context.get("org_id", "org-runtime")),
                event_type="deliberation_completed",
                details=details,
            )
            if inspect.isawaitable(result):
                await result

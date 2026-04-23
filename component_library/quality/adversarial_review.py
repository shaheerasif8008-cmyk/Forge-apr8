"""adversarial_review quality and governance component."""

from __future__ import annotations

from typing import Any

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.registry import register
from employee_runtime.modules.deliberation import (
    CouncilConfig,
    DeliberationCouncil,
    Proposal,
    Verdict,
)


@register("adversarial_review")
class AdversarialReview(QualityModule):
    config_schema = {
        "deliberation_council": {"type": "object", "required": False, "description": "CouncilConfig overrides; see DeliberationCouncil for full schema.", "default": {}},
        "model_client": {"type": "object", "required": False, "description": "Optional model client used by deliberation roles.", "default": None},
        "audit_logger": {"type": "object", "required": False, "description": "Optional async audit logger callable.", "default": None},
    }
    component_id = "adversarial_review"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._config = dict(config)
        self._model_client = config.get("model_client")
        self._audit_logger = config.get("audit_logger")
        self._rebuild_council()

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/runtime/test_deliberation_council.py"]

    async def evaluate(self, input_data: Any) -> Verdict:
        payload = input_data if isinstance(input_data, dict) else {"content": str(input_data)}
        proposal = Proposal(
            proposal_id=str(payload.get("proposal_id", "proposal")),
            content=str(payload.get("content", payload.get("text", ""))),
            context=payload.get("context", {}),
            risk_tier=str(payload.get("risk_tier", "medium")),
        )
        return await self._council.deliberate(proposal, proposal.context)

    def set_model_client(self, model_client: Any) -> None:
        self._model_client = model_client
        self._rebuild_council()

    def set_audit_logger(self, audit_logger: Any) -> None:
        self._audit_logger = audit_logger
        self._rebuild_council()

    def _rebuild_council(self) -> None:
        self._council = DeliberationCouncil(
            CouncilConfig.model_validate(self._config.get("deliberation_council", self._config)),
            model_client=self._model_client,
            audit_logger=self._audit_logger,
        )

"""Route messy human work requests into typed employee work."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from component_library.interfaces import ComponentHealth, WorkCapability
from component_library.registry import register


class WorkIntakeInput(BaseModel):
    request_text: str
    channel: str = "app"
    sender: str = ""
    known_context: dict[str, Any] = Field(default_factory=dict)


class WorkIntakeRoute(BaseModel):
    task_type: str
    urgency: str
    risk_tier: str
    missing_inputs: list[str] = Field(default_factory=list)
    recommended_modules: list[str] = Field(default_factory=list)
    rationale: str = ""


@register("work_intake_router")
class WorkIntakeRouter(WorkCapability):
    """Classifies incoming work and identifies the modules needed to complete it."""

    component_id = "work_intake_router"
    version = "1.0.0"
    config_schema = {
        "default_risk_tier": {"type": "str", "required": False, "description": "Risk tier used when no signal is present.", "default": "medium"},
    }

    async def initialize(self, config: dict[str, Any]) -> None:
        self._default_risk_tier = str(config.get("default_risk_tier", "medium"))

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/test_horizontal_employee_modules.py"]

    async def execute(self, input_data: BaseModel) -> BaseModel:
        if not isinstance(input_data, WorkIntakeInput):
            raise TypeError("WorkIntakeRouter expects WorkIntakeInput")
        text = input_data.request_text.lower()
        task_type = self._task_type(text)
        required_inputs = self._required_inputs(task_type)
        available = {str(item).lower() for item in input_data.known_context.get("available_inputs", [])}
        missing = [item for item in required_inputs if item.lower() not in available]
        return WorkIntakeRoute(
            task_type=task_type,
            urgency="deadline" if any(term in text for term in ("by friday", "today", "tomorrow", "urgent", "asap")) else "normal",
            risk_tier=self._risk_tier(text),
            missing_inputs=missing,
            recommended_modules=self._recommended_modules(task_type),
            rationale=f"Classified from {input_data.channel} request by {input_data.sender or 'unknown sender'}.",
        )

    def _task_type(self, text: str) -> str:
        if any(term in text for term in ("deck", "presentation", "slides")):
            return "presentation"
        if any(term in text for term in ("month-end", "close", "reconcile", "ap aging", "ar aging")):
            return "month_end_close"
        if any(term in text for term in ("contract", "redline", "nda")):
            return "contract_review"
        if any(term in text for term in ("credit memo", "underwrite", "covenant")):
            return "credit_underwriting"
        return "general_work"

    def _risk_tier(self, text: str) -> str:
        if any(term in text for term in ("file", "sign", "tax return", "wire", "external report", "board")):
            return "high"
        return self._default_risk_tier

    def _required_inputs(self, task_type: str) -> list[str]:
        return {
            "presentation": ["CRM pipeline", "finance metrics"],
            "month_end_close": ["bank statement", "GL", "AP aging", "AR aging"],
            "contract_review": ["contract", "playbook"],
            "credit_underwriting": ["financial statements", "credit policy"],
        }.get(task_type, [])

    def _recommended_modules(self, task_type: str) -> list[str]:
        baseline = ["task_orchestrator", "policy_authority_engine", "quality_review_engine", "roi_meter"]
        if task_type == "presentation":
            return baseline + ["work_product_renderer", "evidence_binder"]
        if task_type == "month_end_close":
            return baseline + ["data_analyzer", "evidence_binder"]
        if task_type in {"contract_review", "credit_underwriting"}:
            return baseline + ["knowledge_base", "evidence_binder"]
        return baseline

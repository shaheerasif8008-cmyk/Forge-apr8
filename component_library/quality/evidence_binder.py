"""Evidence binding for reviewer-ready employee work products."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.registry import register


class EvidenceBinderInput(BaseModel):
    task_id: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    calculations: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    audit_refs: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)


class EvidencePacket(BaseModel):
    packet_id: str
    complete: bool
    missing_evidence: list[str] = Field(default_factory=list)
    audit_summary: dict[str, Any] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    calculations: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


@register("evidence_binder")
class EvidenceBinder(QualityModule):
    """Creates evidence packets from sources, calculations, assumptions, approvals, and audit refs."""

    component_id = "evidence_binder"
    version = "1.0.0"
    config_schema = {
        "strict_required_evidence": {"type": "bool", "required": False, "description": "Fail completeness when required evidence is missing.", "default": True},
    }

    async def initialize(self, config: dict[str, Any]) -> None:
        self._strict = bool(config.get("strict_required_evidence", True))

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/test_horizontal_employee_modules.py"]

    async def evaluate(self, input_data: Any) -> BaseModel:
        payload = input_data if isinstance(input_data, EvidenceBinderInput) else EvidenceBinderInput.model_validate(input_data)
        source_names = {str(source.get("name", "")).lower() for source in payload.sources}
        missing = [name for name in payload.required_evidence if name.lower() not in source_names]
        return EvidencePacket(
            packet_id=f"evidence:{payload.task_id}",
            complete=not missing or not self._strict,
            missing_evidence=missing,
            audit_summary={
                "source_count": len(payload.sources),
                "calculation_count": len(payload.calculations),
                "assumption_count": len(payload.assumptions),
                "approval_count": len(payload.approvals),
                "audit_ref_count": len(payload.audit_refs),
            },
            sources=payload.sources,
            calculations=payload.calculations,
            assumptions=payload.assumptions,
        )

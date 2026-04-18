"""explainability quality and governance component."""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.quality.schemas import DecisionPoint, ReasoningRecord
from component_library.registry import register
from factory.models.orm import ReasoningRecordRow


@register("explainability")
class Explainability(QualityModule):
    component_id = "explainability"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._session_factory: async_sessionmaker[AsyncSession] | None = config.get("session_factory")
        self._employee_id = str(config.get("employee_id", "employee-runtime"))
        self._org_id = str(config.get("org_id", ""))
        self._audit_logger = config.get("audit_logger")
        self._records: dict[str, list[ReasoningRecord]] = defaultdict(list)
        self._records_by_id: dict[str, ReasoningRecord] = {}

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/quality/test_explainability.py"]

    def set_audit_logger(self, audit_logger: Any) -> None:
        self._audit_logger = audit_logger

    async def evaluate(self, input_data: Any) -> ReasoningRecord:
        decision = input_data if isinstance(input_data, DecisionPoint) else DecisionPoint.model_validate(input_data)
        return await self.capture(decision)

    async def capture(self, decision: DecisionPoint) -> ReasoningRecord:
        record = ReasoningRecord(
            task_id=decision.task_id,
            node_id=decision.node_id,
            decision=decision.decision,
            rationale=decision.rationale,
            inputs_considered=decision.inputs_considered,
            alternatives=decision.alternatives,
            evidence=decision.evidence,
            confidence=decision.confidence,
            modules_invoked=decision.modules_invoked,
            token_cost=decision.token_cost,
            latency_ms=decision.latency_ms,
        )
        await self._persist(record)
        await self._log(record)
        return record

    async def get_records(self, task_id: str) -> list[ReasoningRecord]:
        if self._session_factory is None:
            return list(self._records.get(task_id, []))

        async with self._session_factory() as session:
            result = await session.execute(
                select(ReasoningRecordRow)
                .where(ReasoningRecordRow.employee_id == self._employee_id)
                .where(ReasoningRecordRow.task_id == task_id)
                .order_by(ReasoningRecordRow.created_at)
            )
            rows = result.scalars().all()
            return [self._to_model(row) for row in rows]

    async def get_records_for_employee(self) -> list[ReasoningRecord]:
        if self._session_factory is None:
            all_records = [record for records in self._records.values() for record in records]
            return sorted(all_records, key=lambda record: record.created_at)

        async with self._session_factory() as session:
            result = await session.execute(
                select(ReasoningRecordRow)
                .where(ReasoningRecordRow.employee_id == self._employee_id)
                .order_by(ReasoningRecordRow.created_at)
            )
            rows = result.scalars().all()
            return [self._to_model(row) for row in rows]

    async def get_record(self, record_id: str) -> ReasoningRecord | None:
        if self._session_factory is None:
            return self._records_by_id.get(record_id)

        async with self._session_factory() as session:
            row = await session.get(ReasoningRecordRow, UUID(record_id))
            if row is None:
                return None
            return self._to_model(row)

    async def _persist(self, record: ReasoningRecord) -> None:
        if self._session_factory is None:
            task_key = str(record.task_id)
            self._records[task_key] = [item for item in self._records[task_key] if item.node_id != record.node_id]
            self._records[task_key].append(record)
            self._records_by_id[str(record.record_id)] = record
            return

        async with self._session_factory() as session:
            existing = await session.execute(
                select(ReasoningRecordRow)
                .where(ReasoningRecordRow.employee_id == self._employee_id)
                .where(ReasoningRecordRow.task_id == str(record.task_id))
                .where(ReasoningRecordRow.node_id == record.node_id)
            )
            row = existing.scalar_one_or_none()
            if row is None:
                row = ReasoningRecordRow(
                    id=record.record_id,
                    org_id=UUID(self._org_id),
                    employee_id=self._employee_id,
                    task_id=str(record.task_id),
                    node_id=record.node_id,
                )
                session.add(row)
            row.decision = record.decision
            row.rationale = record.rationale
            row.inputs_considered = record.inputs_considered
            row.alternatives = [item.model_dump(mode="json") for item in record.alternatives]
            row.evidence = [item.model_dump(mode="json") for item in record.evidence]
            row.confidence = record.confidence
            row.modules_invoked = list(record.modules_invoked)
            row.token_cost = record.token_cost
            row.latency_ms = record.latency_ms
            await session.commit()

    async def _log(self, record: ReasoningRecord) -> None:
        if self._audit_logger is None:
            return
        await self._audit_logger(
            employee_id=self._employee_id,
            org_id=self._org_id,
            event_type="reasoning_captured",
            details={
                "record_id": str(record.record_id),
                "task_id": str(record.task_id),
                "node_id": record.node_id,
                "decision": record.decision,
                "confidence": record.confidence,
            },
        )

    def _to_model(self, row: ReasoningRecordRow) -> ReasoningRecord:
        return ReasoningRecord.model_validate(
            {
                "record_id": row.id,
                "task_id": row.task_id,
                "node_id": row.node_id,
                "decision": row.decision,
                "rationale": row.rationale,
                "inputs_considered": row.inputs_considered,
                "alternatives": row.alternatives,
                "evidence": row.evidence,
                "confidence": row.confidence,
                "modules_invoked": row.modules_invoked,
                "token_cost": row.token_cost,
                "latency_ms": row.latency_ms,
                "created_at": row.created_at,
            }
        )

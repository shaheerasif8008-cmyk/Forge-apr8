"""audit_system quality and governance component."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.registry import register
from component_library.work.schemas import ChainVerification
from factory.models.orm import AuditEventRow


@register("audit_system")
class AuditSystem(QualityModule):
    component_id = "audit_system"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._session_factory: async_sessionmaker[AsyncSession] | None = config.get("session_factory")
        self._events: list[dict[str, Any]] = []

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/quality/test_audit_system.py"]

    async def evaluate(self, input_data: Any) -> BaseModel:
        employee_id = input_data["employee_id"]
        return await self.verify_chain(employee_id)

    async def log_event(
        self,
        employee_id: str,
        org_id: str,
        event_type: str,
        details: dict[str, Any],
        *,
        action: str | None = None,
        actor: str = "employee_runtime",
        entity_type: str = "employee_runtime",
        entity_id: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        prev_hash = ""
        if self._session_factory is None:
            if self._events and self._events[-1]["employee_id"] == employee_id:
                prev_hash = self._events[-1]["hash"]
            event_hash = self._compute_hash(event_type, details, prev_hash)
            event = {
                "org_id": org_id,
                "employee_id": employee_id,
                "event_type": event_type,
                "details": details,
                "prev_hash": prev_hash,
                "hash": event_hash,
                "occurred_at": datetime.now(UTC).isoformat(),
                "trace_id": trace_id,
            }
            self._events.append(event)
            return event

        async with self._session_factory() as session:
            result = await session.execute(
                select(AuditEventRow)
                .where(AuditEventRow.employee_id == employee_id)
                .order_by(AuditEventRow.occurred_at.desc())
                .limit(1)
            )
            previous = result.scalar_one_or_none()
            prev_hash = previous.hash or previous.hash_chain if previous is not None else ""
            event_hash = self._compute_hash(event_type, details, prev_hash)
            row = AuditEventRow(
                org_id=org_id,
                entity_type=entity_type,
                entity_id=entity_id or employee_id,
                actor=actor,
                employee_id=employee_id,
                action=action or event_type,
                event_type=event_type,
                detail=details,
                details=details,
                prev_hash=prev_hash,
                hash_chain=event_hash,
                hash=event_hash,
                trace_id=trace_id,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return {
                "id": str(row.id),
                "org_id": str(row.org_id),
                "employee_id": row.employee_id,
                "event_type": row.event_type,
                "details": row.details,
                "prev_hash": row.prev_hash,
                "hash": row.hash,
                "occurred_at": row.occurred_at.isoformat(),
            }

    async def get_trail(
        self,
        employee_id: str,
        since: datetime | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        if self._session_factory is None:
            events = [event for event in self._events if event["employee_id"] == employee_id]
            if since is not None:
                events = [event for event in events if event["occurred_at"] >= since.isoformat()]
            if event_type is not None:
                events = [event for event in events if event["event_type"] == event_type]
            return events

        async with self._session_factory() as session:
            stmt = select(AuditEventRow).where(AuditEventRow.employee_id == employee_id).order_by(AuditEventRow.occurred_at)
            if since is not None:
                stmt = stmt.where(AuditEventRow.occurred_at >= since)
            if event_type is not None:
                stmt = stmt.where(AuditEventRow.event_type == event_type)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    "id": str(row.id),
                    "employee_id": row.employee_id,
                    "event_type": row.event_type,
                    "details": row.details,
                    "prev_hash": row.prev_hash,
                    "hash": row.hash,
                    "occurred_at": row.occurred_at.isoformat(),
                }
                for row in rows
            ]

    async def verify_chain(self, employee_id: str) -> ChainVerification:
        events = await self.get_trail(employee_id)
        prev_hash = ""
        for index, event in enumerate(events):
            expected = self._compute_hash(event["event_type"], event["details"], prev_hash)
            if event["hash"] != expected:
                return ChainVerification(
                    valid=False,
                    checked_events=index + 1,
                    failure_reason=f"Hash mismatch at event {index + 1}",
                )
            prev_hash = event["hash"]
        return ChainVerification(valid=True, checked_events=len(events))

    def _compute_hash(self, event_type: str, details: dict[str, Any], prev_hash: str) -> str:
        raw = f"{event_type}|{json.dumps(details, sort_keys=True, default=str)}|{prev_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

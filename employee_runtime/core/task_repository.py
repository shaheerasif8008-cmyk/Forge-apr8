"""Task lifecycle persistence abstraction for employee runtime."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from employee_runtime.shared.orm import EmployeeTaskRow

INFLIGHT_TASK_STATUSES = {"queued", "running"}


class TaskRepository(Protocol):
    async def create_task(
        self,
        *,
        task_id: str,
        employee_id: str,
        org_id: str,
        conversation_id: str,
        input_text: str,
        input_type: str,
        input_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    async def get_task(self, task_id: str, employee_id: str) -> dict[str, Any] | None:
        ...

    async def update_task(self, task_id: str, employee_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        ...

    async def list_recent_tasks(self, employee_id: str, limit: int = 20) -> list[dict[str, Any]]:
        ...

    async def mark_inflight_tasks_interrupted(
        self,
        employee_id: str,
        *,
        reason: str,
    ) -> list[dict[str, Any]]:
        ...

    async def task_counts(self, employee_id: str) -> dict[str, int]:
        ...


class InMemoryTaskRepository:
    def __init__(self, *, tasks: dict[str, dict[str, Any]] | None = None) -> None:
        self._tasks = tasks if tasks is not None else {}
        self._employee_index: dict[str, list[str]] = defaultdict(list)

    async def create_task(
        self,
        *,
        task_id: str,
        employee_id: str,
        org_id: str,
        conversation_id: str,
        input_text: str,
        input_type: str,
        input_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        created_at = datetime.now(UTC).isoformat()
        task = {
            "task_id": task_id,
            "employee_id": employee_id,
            "org_id": org_id,
            "conversation_id": conversation_id,
            "status": "queued",
            "input": input_text,
            "input_type": input_type,
            "input_metadata": dict(input_metadata),
            "response_summary": "",
            "result_card": {},
            "workflow_output": {},
            "state": {},
            "error": "",
            "requires_human_approval": False,
            "interruption_reason": "",
            "created_at": created_at,
            "started_at": "",
            "completed_at": "",
            "updated_at": created_at,
        }
        self._tasks[task_id] = task
        if task_id not in self._employee_index[employee_id]:
            self._employee_index[employee_id].append(task_id)
        return deepcopy(task)

    async def get_task(self, task_id: str, employee_id: str) -> dict[str, Any] | None:
        task = self._tasks.get(task_id)
        if task is None or task.get("employee_id") != employee_id:
            return None
        return deepcopy(task)

    async def update_task(self, task_id: str, employee_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if task is None or task.get("employee_id") != employee_id:
            raise KeyError(task_id)
        task.update(deepcopy(changes))
        task["updated_at"] = datetime.now(UTC).isoformat()
        return deepcopy(task)

    async def list_recent_tasks(self, employee_id: str, limit: int = 20) -> list[dict[str, Any]]:
        task_ids = self._employee_index.get(employee_id, [])
        tasks = [deepcopy(self._tasks[task_id]) for task_id in task_ids if task_id in self._tasks]
        tasks.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return tasks[:limit]

    async def mark_inflight_tasks_interrupted(
        self,
        employee_id: str,
        *,
        reason: str,
    ) -> list[dict[str, Any]]:
        interrupted: list[dict[str, Any]] = []
        for task_id in self._employee_index.get(employee_id, []):
            task = self._tasks.get(task_id)
            if task is None or task.get("status") not in INFLIGHT_TASK_STATUSES:
                continue
            task["status"] = "interrupted"
            task["interruption_reason"] = reason
            task["completed_at"] = datetime.now(UTC).isoformat()
            task["updated_at"] = task["completed_at"]
            interrupted.append(deepcopy(task))
        return interrupted

    async def task_counts(self, employee_id: str) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for task_id in self._employee_index.get(employee_id, []):
            task = self._tasks.get(task_id)
            if task is not None:
                counts[str(task.get("status", "queued"))] += 1
        return dict(counts)


class SqlAlchemyTaskRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        org_id: str = "",
    ) -> None:
        self._session_factory = session_factory
        self._org_id = UUID(org_id) if org_id else None

    async def create_task(
        self,
        *,
        task_id: str,
        employee_id: str,
        org_id: str,
        conversation_id: str,
        input_text: str,
        input_type: str,
        input_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            row = EmployeeTaskRow(
                id=_task_uuid(task_id),
                org_id=UUID(org_id),
                employee_id=employee_id,
                conversation_id=_conversation_uuid(employee_id, conversation_id) if conversation_id else None,
                status="queued",
                input=input_text,
                input_type=input_type,
                input_metadata=dict(input_metadata),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _task_payload(row, employee_id)

    async def get_task(self, task_id: str, employee_id: str) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            result = await session.execute(self._task_lookup_stmt(task_id, employee_id))
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return _task_payload(row, employee_id)

    async def update_task(self, task_id: str, employee_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        async with self._session_factory() as session:
            result = await session.execute(self._task_lookup_stmt(task_id, employee_id))
            row = result.scalar_one_or_none()
            if row is None:
                raise KeyError(task_id)
            _apply_changes(row, employee_id, changes)
            await session.commit()
            await session.refresh(row)
            return _task_payload(row, employee_id)

    async def list_recent_tasks(self, employee_id: str, limit: int = 20) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            result = await session.execute(
                self._scope(select(EmployeeTaskRow))
                .where(EmployeeTaskRow.employee_id == employee_id)
                .order_by(EmployeeTaskRow.created_at.desc())
                .limit(limit)
            )
            return [_task_payload(row, employee_id) for row in result.scalars().all()]

    async def mark_inflight_tasks_interrupted(
        self,
        employee_id: str,
        *,
        reason: str,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            result = await session.execute(
                self._scope(select(EmployeeTaskRow))
                .where(EmployeeTaskRow.employee_id == employee_id)
                .where(EmployeeTaskRow.status.in_(tuple(INFLIGHT_TASK_STATUSES)))
            )
            rows = result.scalars().all()
            interrupted_at = datetime.now(UTC)
            for row in rows:
                row.status = "interrupted"
                row.interruption_reason = reason
                row.completed_at = interrupted_at
            await session.commit()
            return [_task_payload(row, employee_id) for row in rows]

    async def task_counts(self, employee_id: str) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        async with self._session_factory() as session:
            result = await session.execute(
                self._scope(select(EmployeeTaskRow.status)).where(EmployeeTaskRow.employee_id == employee_id)
            )
            for (status,) in result.all():
                counts[str(status)] += 1
        return dict(counts)

    def _scope(self, stmt: Select[Any]) -> Select[Any]:
        if self._org_id is None:
            return stmt
        return stmt.where(EmployeeTaskRow.org_id == self._org_id)

    def _task_lookup_stmt(self, task_id: str, employee_id: str) -> Select[Any]:
        return self._scope(select(EmployeeTaskRow)).where(
            EmployeeTaskRow.id == _task_uuid(task_id),
            EmployeeTaskRow.employee_id == employee_id,
        )


def _task_uuid(task_id: str) -> UUID:
    try:
        return UUID(str(task_id))
    except (ValueError, TypeError):
        return uuid5(NAMESPACE_URL, f"forge-task:{task_id}")


def _conversation_uuid(employee_id: str, conversation_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"forge-conversation:{employee_id}:{conversation_id}")


def _external_conversation_id(conversation_uuid: UUID | None, employee_id: str) -> str:
    if conversation_uuid is None:
        return ""
    default_uuid = _conversation_uuid(employee_id, "default")
    return "default" if conversation_uuid == default_uuid else str(conversation_uuid)


def _iso(value: datetime | None) -> str:
    return "" if value is None else value.isoformat()


def _task_payload(row: EmployeeTaskRow, employee_id: str) -> dict[str, Any]:
    return {
        "task_id": str(row.id),
        "employee_id": row.employee_id,
        "org_id": str(row.org_id),
        "conversation_id": _external_conversation_id(row.conversation_id, employee_id),
        "status": row.status,
        "input": row.input,
        "input_type": row.input_type,
        "input_metadata": dict(row.input_metadata),
        "response_summary": row.response_summary,
        "result_card": dict(row.result_card),
        "workflow_output": dict(row.workflow_output),
        "state": dict(row.state),
        "error": row.error,
        "requires_human_approval": row.requires_human_approval,
        "interruption_reason": row.interruption_reason,
        "created_at": _iso(row.created_at),
        "started_at": _iso(row.started_at),
        "completed_at": _iso(row.completed_at),
        "updated_at": _iso(row.updated_at),
    }


def _apply_changes(row: EmployeeTaskRow, employee_id: str, changes: dict[str, Any]) -> None:
    for key, value in changes.items():
        if key == "task_id":
            continue
        if key == "conversation_id":
            row.conversation_id = _conversation_uuid(employee_id, str(value)) if value else None
            continue
        if key in {"input_metadata", "result_card", "workflow_output", "state"}:
            setattr(row, key, dict(value or {}))
            continue
        setattr(row, key, value)

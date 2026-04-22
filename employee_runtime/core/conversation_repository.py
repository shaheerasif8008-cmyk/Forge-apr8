"""Conversation/message persistence abstraction for employee runtime."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from employee_runtime.shared.orm import ConversationRow, MessageRow


class ConversationRepository(Protocol):
    async def ensure_conversation(self, conversation_id: str, employee_id: str, org_id: str) -> dict[str, Any]:
        ...

    async def add_message(
        self,
        conversation_id: str,
        employee_id: str,
        org_id: str,
        role: str,
        content: str,
        message_type: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    async def history(self, conversation_id: str, employee_id: str) -> list[dict[str, Any]]:
        ...

    async def list_pending_approvals(self, employee_id: str) -> list[dict[str, Any]]:
        ...

    async def update_message_metadata(self, message_id: str, employee_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
        ...


class InMemoryConversationRepository:
    def __init__(
        self,
        *,
        conversations: dict[str, dict[str, Any]] | None = None,
        messages: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self._conversations = conversations if conversations is not None else {}
        self._messages = messages if messages is not None else defaultdict(list)

    async def ensure_conversation(self, conversation_id: str, employee_id: str, org_id: str) -> dict[str, Any]:
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = {
                "id": conversation_id,
                "employee_id": employee_id,
                "org_id": org_id,
                "created_at": datetime.now(UTC).isoformat(),
            }
        self._messages.setdefault(conversation_id, [])
        return deepcopy(self._conversations[conversation_id])

    async def add_message(
        self,
        conversation_id: str,
        employee_id: str,
        org_id: str,
        role: str,
        content: str,
        message_type: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        await self.ensure_conversation(conversation_id, employee_id, org_id)
        message = {
            "id": f"{conversation_id}:{len(self._messages[conversation_id]) + 1}",
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "message_type": message_type,
            "metadata": dict(metadata),
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._messages[conversation_id].append(message)
        return deepcopy(message)

    async def history(self, conversation_id: str, employee_id: str) -> list[dict[str, Any]]:
        return [deepcopy(message) for message in self._messages.get(conversation_id, [])]

    async def list_pending_approvals(self, employee_id: str) -> list[dict[str, Any]]:
        approvals: list[dict[str, Any]] = []
        for messages in self._messages.values():
            for message in messages:
                if message["message_type"] == "approval_request" and message["metadata"].get("status") == "pending":
                    approvals.append(deepcopy(message))
        return approvals

    async def update_message_metadata(self, message_id: str, employee_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
        for messages in self._messages.values():
            for message in messages:
                if message["id"] == message_id:
                    message["metadata"] = dict(metadata)
                    return deepcopy(message)
        raise KeyError(message_id)


class SqlAlchemyConversationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def ensure_conversation(self, conversation_id: str, employee_id: str, org_id: str) -> dict[str, Any]:
        conversation_uuid = _conversation_uuid(employee_id, conversation_id)
        async with self._session_factory() as session:
            row = await session.get(ConversationRow, conversation_uuid)
            if row is None:
                row = ConversationRow(
                    id=conversation_uuid,
                    org_id=UUID(org_id),
                    employee_id=employee_id,
                )
                session.add(row)
                await session.commit()
                await session.refresh(row)
            return _conversation_payload(row, conversation_id)

    async def add_message(
        self,
        conversation_id: str,
        employee_id: str,
        org_id: str,
        role: str,
        content: str,
        message_type: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        conversation_uuid = _conversation_uuid(employee_id, conversation_id)
        await self.ensure_conversation(conversation_id, employee_id, org_id)
        async with self._session_factory() as session:
            row = MessageRow(
                conversation_id=conversation_uuid,
                role=role,
                content=content,
                message_type=message_type,
                message_metadata=dict(metadata),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _message_payload(row, conversation_id)

    async def history(self, conversation_id: str, employee_id: str) -> list[dict[str, Any]]:
        conversation_uuid = _conversation_uuid(employee_id, conversation_id)
        async with self._session_factory() as session:
            result = await session.execute(
                select(MessageRow)
                .where(MessageRow.conversation_id == conversation_uuid)
                .order_by(MessageRow.created_at)
            )
            rows = result.scalars().all()
            return [_message_payload(row, conversation_id) for row in rows]

    async def list_pending_approvals(self, employee_id: str) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(MessageRow, ConversationRow)
                .join(ConversationRow, ConversationRow.id == MessageRow.conversation_id)
                .where(ConversationRow.employee_id == employee_id)
                .where(MessageRow.message_type == "approval_request")
                .order_by(MessageRow.created_at.desc())
            )
            approvals: list[dict[str, Any]] = []
            for message_row, conversation_row in result.all():
                if message_row.message_metadata.get("status") == "pending":
                    approvals.append(_message_payload(message_row, _external_conversation_id(conversation_row.id, employee_id)))
            return approvals

    async def update_message_metadata(self, message_id: str, employee_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
        async with self._session_factory() as session:
            row = await session.get(MessageRow, UUID(message_id))
            if row is None:
                raise KeyError(message_id)
            row.message_metadata = dict(metadata)
            await session.commit()
            await session.refresh(row)
            conversation = await session.get(ConversationRow, row.conversation_id)
            assert conversation is not None
            return _message_payload(row, _external_conversation_id(conversation.id, employee_id))


def _conversation_uuid(employee_id: str, conversation_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"forge-conversation:{employee_id}:{conversation_id}")


def _external_conversation_id(conversation_uuid: UUID, employee_id: str) -> str:
    return str(conversation_uuid) if employee_id == "" else "default" if conversation_uuid == _conversation_uuid(employee_id, "default") else str(conversation_uuid)


def _conversation_payload(row: ConversationRow, conversation_id: str) -> dict[str, Any]:
    return {
        "id": conversation_id,
        "employee_id": row.employee_id,
        "org_id": str(row.org_id),
        "created_at": row.created_at.isoformat(),
    }


def _message_payload(row: MessageRow, conversation_id: str) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "conversation_id": conversation_id,
        "role": row.role,
        "content": row.content,
        "message_type": row.message_type,
        "metadata": dict(row.message_metadata),
        "created_at": row.created_at.isoformat(),
    }

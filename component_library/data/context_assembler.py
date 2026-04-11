"""context_assembler data source component."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from component_library.interfaces import ComponentHealth, DataSource
from component_library.registry import register
from factory.models.orm import MessageRow


@register("context_assembler")
class ContextAssembler(DataSource):
    component_id = "context_assembler"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._session_factory: async_sessionmaker[AsyncSession] | None = config.get("session_factory")
        self._operational_memory = config.get("operational_memory")
        self._system_identity = config.get("system_identity", "")
        self._conversation_cache: dict[str, list[str]] = {}

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/data/test_context_assembler.py"]

    async def query(self, query: str, **kwargs: Any) -> Any:
        return await self.assemble(query, kwargs["employee_id"], kwargs["org_id"], kwargs.get("conversation_id", ""), kwargs.get("token_budget", 8000))

    async def assemble(
        self,
        task_input: str,
        employee_id: str,
        org_id: str,
        conversation_id: str,
        token_budget: int = 8000,
    ) -> str:
        sections: list[str] = []
        if self._system_identity:
            sections.append(f"SYSTEM IDENTITY\n{self._system_identity}")

        if self._operational_memory is not None:
            memories = await self._operational_memory.search(task_input, limit=8)
            if memories:
                memory_lines = [f"- {item['key']}: {item['value']}" for item in memories]
                sections.append("OPERATIONAL MEMORY\n" + "\n".join(memory_lines))

        history_text = await self._conversation_history(conversation_id)
        if history_text:
            sections.append("RECENT CONVERSATION\n" + history_text)

        sections.append("TASK INPUT\n" + task_input)
        context = "\n\n".join(sections)

        while self._estimate_tokens(context) > token_budget and "RECENT CONVERSATION\n" in context:
            history_lines = history_text.splitlines()
            if len(history_lines) <= 1:
                break
            history_text = "\n".join(history_lines[1:])
            sections = [section for section in sections if not section.startswith("RECENT CONVERSATION\n")]
            sections.insert(min(2, len(sections)), "RECENT CONVERSATION\n" + history_text)
            context = "\n\n".join(sections)
        return context

    async def _conversation_history(self, conversation_id: str) -> str:
        if not conversation_id:
            return ""
        if self._session_factory is None:
            return "\n".join(self._conversation_cache.get(conversation_id, [])[-12:])
        async with self._session_factory() as session:
            result = await session.execute(
                select(MessageRow).where(MessageRow.conversation_id == conversation_id).order_by(MessageRow.created_at.desc()).limit(12)
            )
            rows = list(reversed(result.scalars().all()))
            return "\n".join(f"{row.role}: {row.content}" for row in rows)

    def _estimate_tokens(self, text: str) -> int:
        return int(len(text.split()) * 1.3)

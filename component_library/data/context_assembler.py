"""context_assembler data source component."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from component_library.interfaces import ComponentHealth, DataSource
from component_library.registry import register
from employee_runtime.core.conversation_repository import ConversationRepository
from employee_runtime.shared.orm import MessageRow


@register("context_assembler")
class ContextAssembler(DataSource):
    config_schema = {
        "session_factory": {"type": "object", "required": False, "description": "SQLAlchemy async_sessionmaker for persistence-backed context.", "default": None},
        "operational_memory": {"type": "object", "required": False, "description": "Operational memory component used for retrieved facts.", "default": None},
        "conversation_repository": {"type": "object", "required": False, "description": "Conversation repository used for recent dialogue context.", "default": None},
        "employee_id": {"type": "str", "required": False, "description": "Employee identifier for scoped context lookup.", "default": ""},
        "system_identity": {"type": "str", "required": False, "description": "Fallback system identity when identity layers are absent.", "default": ""},
        "identity_layers": {"type": "dict", "required": False, "description": "Layered employee identity prompt sections.", "default": {}},
    }
    component_id = "context_assembler"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._session_factory: async_sessionmaker[AsyncSession] | None = config.get("session_factory")
        self._operational_memory = config.get("operational_memory")
        self._conversation_repository: ConversationRepository | None = config.get("conversation_repository")
        self._employee_id = str(config.get("employee_id", ""))
        self._system_identity = config.get("system_identity", "")
        self._identity_layers = config.get("identity_layers", {})
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
        fixed_layers = [
            ("LAYER 1 CORE IDENTITY", self._identity_layers.get("layer_1_core_identity", self._system_identity)),
            ("LAYER 2 ROLE DEFINITION", self._identity_layers.get("layer_2_role_definition", "")),
            ("LAYER 3 ORGANIZATIONAL MAP", self._identity_layers.get("layer_3_organizational_map", "")),
            ("LAYER 4 BEHAVIORAL RULES", self._identity_layers.get("layer_4_behavioral_rules", "")),
            ("LAYER 6 SELF AWARENESS", self._identity_layers.get("layer_6_self_awareness", "")),
        ]
        for title, body in fixed_layers:
            if body:
                sections.append(f"{title}\n{body}")

        if self._operational_memory is not None:
            memories = await self._relevant_memories(task_input)
            if memories:
                memory_lines = [f"- {item['key']}: {item['value']}" for item in memories]
                sections.append("LAYER 5 RETRIEVED CONTEXT\n" + "\n".join(memory_lines))

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
        if self._conversation_repository is not None and self._employee_id:
            messages = await self._conversation_repository.history(conversation_id, self._employee_id)
            return "\n".join(f"{row['role']}: {row['content']}" for row in messages[-12:])
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

    async def _relevant_memories(self, task_input: str) -> list[dict[str, Any]]:
        if self._operational_memory is None:
            return []

        queries = [task_input]
        lowered = task_input.lower()
        if "firm" in lowered:
            queries.extend(["firm", "name"])
        if "supervisor" in lowered:
            queries.append("supervisor")

        seen: set[tuple[str, str]] = set()
        ordered: list[dict[str, Any]] = []
        for query in queries:
            for memory in await self._operational_memory.search(query, limit=8):
                key = (str(memory.get("key", "")), str(memory.get("category", "")))
                if key in seen:
                    continue
                seen.add(key)
                ordered.append(memory)

        if ordered:
            return ordered[:8]
        return await self._operational_memory.list_by_category("general")

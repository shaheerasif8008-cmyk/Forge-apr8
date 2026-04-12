"""operational_memory data source component."""

from __future__ import annotations

from typing import Any

from sqlalchemy import String, cast, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from component_library.interfaces import ComponentHealth, DataSource
from component_library.registry import register
from factory.models.orm import OperationalMemoryRow


@register("operational_memory")
class OperationalMemory(DataSource):
    component_id = "operational_memory"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._org_id = config.get("org_id", "")
        self._employee_id = config.get("employee_id", "")
        self._session_factory: async_sessionmaker[AsyncSession] | None = config.get("session_factory")
        self._memory_store: dict[tuple[str, str, str], dict[str, Any]] = {}

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/data/test_operational_memory.py"]

    async def query(self, query: str, **kwargs: Any) -> Any:
        return await self.search(query, kwargs.get("category"), kwargs.get("limit", 10))

    async def store(self, key: str, value: dict[str, Any], category: str = "general") -> dict[str, Any]:
        record = {
            "org_id": str(self._org_id),
            "employee_id": self._employee_id,
            "key": key,
            "value": value,
            "category": category,
        }
        if self._session_factory is None:
            self._memory_store[(str(self._org_id), self._employee_id, key)] = record
            return record

        async with self._session_factory() as session:
            stmt = pg_insert(OperationalMemoryRow).values(
                org_id=self._org_id,
                employee_id=self._employee_id,
                key=key,
                value=value,
                category=category,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["org_id", "employee_id", "key"],
                set_={"value": value, "category": category},
            )
            await session.execute(stmt)
            await session.commit()
        return record

    async def retrieve(self, key: str) -> dict[str, Any] | None:
        if self._session_factory is None:
            return self._memory_store.get((str(self._org_id), self._employee_id, key))
        async with self._session_factory() as session:
            result = await session.execute(
                select(OperationalMemoryRow).where(
                    OperationalMemoryRow.org_id == self._org_id,
                    OperationalMemoryRow.employee_id == self._employee_id,
                    OperationalMemoryRow.key == key,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return {
                "org_id": str(row.org_id),
                "employee_id": row.employee_id,
                "key": row.key,
                "value": row.value,
                "category": row.category,
            }

    async def search(
        self,
        query: str,
        category: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        if self._session_factory is None:
            matches = []
            for record in self._memory_store.values():
                if record["org_id"] != str(self._org_id) or record["employee_id"] != self._employee_id:
                    continue
                if category and record["category"] != category:
                    continue
                haystack = f"{record['key']} {record['value']}".lower()
                if query.lower() in haystack:
                    matches.append(record)
            return matches[:limit]

        async with self._session_factory() as session:
            stmt = select(OperationalMemoryRow).where(
                OperationalMemoryRow.org_id == self._org_id,
                OperationalMemoryRow.employee_id == self._employee_id,
            )
            if category:
                stmt = stmt.where(OperationalMemoryRow.category == category)
            stmt = stmt.where(
                (OperationalMemoryRow.key.ilike(f"%{query}%"))
                | (cast(OperationalMemoryRow.value, String).ilike(f"%{query}%"))
            ).limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    "org_id": str(row.org_id),
                    "employee_id": row.employee_id,
                    "key": row.key,
                    "value": row.value,
                    "category": row.category,
                }
                for row in rows
            ]

    async def list_by_category(self, category: str) -> list[dict[str, Any]]:
        return await self.search("", category=category, limit=100)

    async def delete(self, key: str) -> None:
        if self._session_factory is None:
            self._memory_store.pop((str(self._org_id), self._employee_id, key), None)
            return
        async with self._session_factory() as session:
            await session.execute(
                delete(OperationalMemoryRow).where(
                    OperationalMemoryRow.org_id == self._org_id,
                    OperationalMemoryRow.employee_id == self._employee_id,
                    OperationalMemoryRow.key == key,
                )
            )
            await session.commit()

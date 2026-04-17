"""Employee-local runtime database bootstrap helpers."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from factory.models.orm import Base, ClientOrgRow


def normalize_org_uuid(raw_org_id: str) -> str:
    try:
        return str(UUID(str(raw_org_id)))
    except (ValueError, TypeError):
        return str(uuid5(NAMESPACE_URL, f"forge-org:{raw_org_id}"))


@dataclass(slots=True)
class RuntimeDatabaseHandle:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    org_uuid: str

    async def close(self) -> None:
        await self.engine.dispose()


async def initialize_runtime_database(
    *,
    database_url: str,
    raw_org_id: str,
    employee_id: str,
) -> RuntimeDatabaseHandle:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    org_uuid = normalize_org_uuid(raw_org_id)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        existing = await session.execute(select(ClientOrgRow).where(ClientOrgRow.id == UUID(org_uuid)))
        if existing.scalar_one_or_none() is None:
            session.add(
                ClientOrgRow(
                    id=UUID(org_uuid),
                    name=f"Employee Runtime {employee_id}",
                    slug=f"employee-runtime-{employee_id}".lower().replace("_", "-"),
                    industry="runtime",
                    tier="enterprise",
                    contact_email=f"{employee_id}@runtime.local",
                )
            )
            await session.commit()

    return RuntimeDatabaseHandle(
        engine=engine,
        session_factory=session_factory,
        org_uuid=org_uuid,
    )

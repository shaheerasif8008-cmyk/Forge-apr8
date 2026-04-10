"""Shared pytest fixtures for all Forge factory tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from uuid import uuid4

from factory.main import app
from factory.models.client import ClientOrg, SubscriptionTier
from factory.models.requirements import EmployeeRequirements, RiskTier


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture()
async def client() -> AsyncClient:
    """Async HTTP client pointed at the factory app (no real DB needed)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture()
def sample_org() -> ClientOrg:
    return ClientOrg(
        name="Acme Law",
        slug="acme-law",
        industry="legal",
        tier=SubscriptionTier.ENTERPRISE,
        contact_email="admin@acmelaw.com",
    )


@pytest.fixture()
def sample_requirements(sample_org: ClientOrg) -> EmployeeRequirements:
    return EmployeeRequirements(
        org_id=sample_org.id,
        name="Legal Intake Agent",
        role_summary="Handles incoming client inquiries, classifies matter type, and routes to the right attorney.",
        primary_responsibilities=["intake classification", "client communication", "attorney routing"],
        required_tools=["email", "crm"],
        risk_tier=RiskTier.MEDIUM,
        deployment_format="web",
        supervisor_email="partner@acmelaw.com",
    )

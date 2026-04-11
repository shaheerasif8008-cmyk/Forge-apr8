"""Shared pytest fixtures for all Forge factory tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from factory.main import app
from factory.models.blueprint import EmployeeBlueprint, SelectedComponent
from factory.models.build import Build
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


@pytest.fixture()
def sample_blueprint(sample_requirements: EmployeeRequirements) -> EmployeeBlueprint:
    return EmployeeBlueprint(
        requirements_id=sample_requirements.id,
        org_id=sample_requirements.org_id,
        employee_name=sample_requirements.name,
        workflow_description="Employee: Legal Intake Agent. Handles incoming client inquiries.",
        components=[
            SelectedComponent(category="models", component_id="anthropic_provider", config={"model": "claude-3-5-sonnet-20241022"}),
            SelectedComponent(category="work", component_id="text_processor"),
            SelectedComponent(category="work", component_id="document_analyzer"),
            SelectedComponent(category="work", component_id="draft_generator"),
            SelectedComponent(category="tools", component_id="email_tool"),
            SelectedComponent(category="data", component_id="operational_memory"),
            SelectedComponent(category="data", component_id="working_memory"),
            SelectedComponent(category="data", component_id="context_assembler"),
            SelectedComponent(category="data", component_id="org_context"),
            SelectedComponent(category="quality", component_id="confidence_scorer"),
            SelectedComponent(category="quality", component_id="audit_system"),
            SelectedComponent(category="quality", component_id="input_protection"),
            SelectedComponent(category="quality", component_id="verification_layer"),
        ],
        autonomy_profile={"risk_tier": sample_requirements.risk_tier.value},
    )


@pytest.fixture()
def sample_build(sample_requirements: EmployeeRequirements) -> Build:
    return Build(requirements_id=sample_requirements.id, org_id=sample_requirements.org_id)

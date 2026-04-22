"""Tests for factory meta/context endpoints."""

from __future__ import annotations

from uuid import UUID

import pytest

from factory.database import get_db_session
from factory.main import app
from factory.models.client import ClientOrg


@pytest.mark.anyio
async def test_context_returns_authorized_orgs_in_order(client, monkeypatch) -> None:
    async def fake_db():
        yield object()

    first_org = ClientOrg(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        name="Acme Law",
        slug="acme-law",
        industry="legal",
        contact_email="admin@acmelaw.com",
    )
    second_org = ClientOrg(
        id=UUID("00000000-0000-0000-0000-000000000002"),
        name="Northstar Ops",
        slug="northstar-ops",
        industry="operations",
        contact_email="ops@northstar.com",
    )

    async def fake_list_client_orgs(session, org_ids):
        assert list(org_ids) == [first_org.id]
        return [first_org]

    app.dependency_overrides[get_db_session] = fake_db
    monkeypatch.setattr("factory.api.health.list_client_orgs", fake_list_client_orgs)

    response = await client.get("/api/v1/context")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["subject"] == "pytest-user"
    assert payload["default_org_id"] == str(first_org.id)
    assert payload["orgs"] == [first_org.model_dump(mode="json")]

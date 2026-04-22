from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from factory.auth import create_factory_token
from factory.database import get_db_session
from factory.main import app


@pytest.mark.anyio
async def test_factory_routes_require_auth(client, sample_requirements) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as unauthenticated:
        response = await unauthenticated.get(f"/api/v1/commissions/{sample_requirements.id}")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_factory_routes_enforce_org_scope(client, sample_requirements) -> None:
    async def fake_db():
        class FakeSession:
            pass

        yield FakeSession()

    app.dependency_overrides[get_db_session] = fake_db
    token = create_factory_token(
        subject="wrong-org-user",
        org_ids=["00000000-0000-0000-0000-000000000099"],
        roles=["viewer"],
    )
    try:
        response = await client.post(
            "/api/v1/commissions",
            json=sample_requirements.model_dump(mode="json"),
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403

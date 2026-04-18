"""Railway provisioning provider."""

from __future__ import annotations

import asyncio

import httpx
import structlog

from factory.config import get_settings
from factory.models.build import Build
from factory.models.deployment import Deployment, DeploymentStatus

logger = structlog.get_logger(__name__)

RAILWAY_GRAPHQL_URL = "https://backboard.railway.app/graphql/v2"


async def provision_railway(deployment: Deployment, build: Build) -> Deployment:
    settings = get_settings()
    deployment.status = DeploymentStatus.PROVISIONING
    image_tarball = str(build.metadata.get("image_tarball", ""))
    employee_slug = _employee_slug(str(build.metadata.get("employee_name", "employee")))

    headers = {"Authorization": f"Bearer {settings.railway_api_token}"} if settings.railway_api_token else {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        upload_response = await _graphql_with_retry(
            client,
            query="mutation UploadImage($input: String!) { uploadImage(input: $input) { imageId } }",
            variables={"input": image_tarball},
            headers=headers,
        )
        image_id = upload_response["data"]["uploadImage"]["imageId"]

        service_response = await _graphql_with_retry(
            client,
            query=(
                "mutation CreateService($name: String!, $imageId: String!) "
                "{ createService(name: $name, imageId: $imageId) { serviceId domain } }"
            ),
            variables={"name": employee_slug, "imageId": image_id},
            headers=headers,
        )
        service_data = service_response["data"]["createService"]
        domain = service_data.get("domain") or f"{employee_slug}-{str(deployment.id)[:8]}.up.railway.app"

        await _graphql_with_retry(
            client,
            query=(
                "mutation ConfigureEnv($serviceId: String!, $env: JSON!) "
                "{ configureEnv(serviceId: $serviceId, env: $env) { ok } }"
            ),
            variables={
                "serviceId": service_data["serviceId"],
                "env": {"FORGE_EMPLOYEE_ID": str(build.metadata.get("employee_id", ""))},
            },
            headers=headers,
        )
        await _graphql_with_retry(
            client,
            query="query DeploymentStatus($serviceId: String!) { deploymentStatus(serviceId: $serviceId) { state } }",
            variables={"serviceId": service_data["serviceId"]},
            headers=headers,
        )

    deployment.access_url = f"https://{domain}"
    deployment.infrastructure = {
        "provider": "railway",
        "image_id": image_id,
        "service_id": service_data["serviceId"],
        "domain": domain,
    }
    return deployment


async def _graphql_with_retry(
    client: httpx.AsyncClient,
    *,
    query: str,
    variables: dict[str, object],
    headers: dict[str, str],
) -> dict:
    delay = 2.0
    for attempt in range(3):
        response = await client.post(
            RAILWAY_GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers=headers,
        )
        if response.status_code != 429:
            response.raise_for_status()
            return response.json()
        if attempt == 2:
            response.raise_for_status()
        await asyncio.sleep(delay)
        delay *= 2
    raise RuntimeError("railway_request_failed")


def _employee_slug(name: str) -> str:
    sanitized = "".join(character.lower() if character.isalnum() else "-" for character in name)
    return "-".join(part for part in sanitized.split("-") if part) or "forge-employee"

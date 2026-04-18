"""Connector: initiates OAuth flows for deployment integrations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import structlog

from factory.models.blueprint import EmployeeBlueprint
from factory.models.deployment import Deployment, DeploymentStatus, IntegrationStatus

logger = structlog.get_logger(__name__)

TOOL_PROVIDER_MAP: dict[str, str] = {
    "email_tool": "gmail",
    "calendar_tool": "google_calendar",
    "messaging_tool": "slack",
    "crm_tool": "hubspot",
}


class ComposioConnectionClient(Protocol):
    async def initiate_connection(self, *, deployment_id: str, tool_id: str, provider: str) -> dict[str, str]:
        ...

    async def get_connection_status(self, connection_id: str) -> str:
        ...

    async def delete_connection(self, connection_id: str) -> None:
        ...


@dataclass(slots=True)
class InMemoryComposioClient:
    """Default lightweight adapter used until the real SDK is wired."""

    async def initiate_connection(self, *, deployment_id: str, tool_id: str, provider: str) -> dict[str, str]:
        connection_id = f"{deployment_id}:{tool_id}"
        return {
            "connection_id": connection_id,
            "oauth_url": f"https://composio.local/connect/{deployment_id}/{provider}/{tool_id}",
        }

    async def get_connection_status(self, connection_id: str) -> str:
        return "connected"

    async def delete_connection(self, connection_id: str) -> None:
        return None


def get_composio_client() -> ComposioConnectionClient:
    return InMemoryComposioClient()


class Connector:
    def __init__(self, client: ComposioConnectionClient | None = None) -> None:
        self._client = client or get_composio_client()

    async def connect(self, deployment: Deployment, blueprint: EmployeeBlueprint) -> Deployment:
        deployment.status = DeploymentStatus.CONNECTING
        deployment.integrations = []

        tool_ids = [
            component.component_id
            for component in blueprint.components
            if component.category == "tools"
            and component.component_id in TOOL_PROVIDER_MAP
        ]

        for tool_id in tool_ids:
            provider = TOOL_PROVIDER_MAP[tool_id]
            connection = await self._client.initiate_connection(
                deployment_id=str(deployment.id),
                tool_id=tool_id,
                provider=provider,
            )
            deployment.integrations.append(
                IntegrationStatus(
                    tool_id=tool_id,
                    provider=provider,
                    composio_connection_id=connection.get("connection_id"),
                    oauth_url=connection.get("oauth_url"),
                    status="pending",
                )
            )

        logger.info(
            "connector_connect_complete",
            deployment_id=str(deployment.id),
            integration_count=len(deployment.integrations),
        )
        return deployment

    async def refresh_statuses(self, deployment: Deployment) -> Deployment:
        for integration in deployment.integrations:
            if integration.status == "connected" or not integration.composio_connection_id:
                continue
            status = await self._client.get_connection_status(integration.composio_connection_id)
            if status == "connected":
                integration.status = "connected"
        return deployment

    async def handle_callback(
        self,
        deployment: Deployment,
        *,
        tool_id: str,
        connection_id: str | None = None,
        provider: str | None = None,
        status: str = "connected",
    ) -> Deployment:
        for integration in deployment.integrations:
            if integration.tool_id != tool_id:
                continue
            if connection_id:
                integration.composio_connection_id = connection_id
            if provider:
                integration.provider = provider
            integration.status = "connected" if status == "connected" else "failed"
        return deployment

    async def delete_connections(self, deployment: Deployment) -> None:
        for integration in deployment.integrations:
            if integration.composio_connection_id:
                await self._client.delete_connection(integration.composio_connection_id)


def pending_oauth_urls(deployment: Deployment) -> list[dict[str, str]]:
    return [
        {"tool_id": integration.tool_id, "oauth_url": integration.oauth_url or ""}
        for integration in deployment.integrations
        if integration.status == "pending" and integration.oauth_url
    ]


def all_integrations_connected(deployment: Deployment) -> bool:
    return all(integration.status == "connected" for integration in deployment.integrations)

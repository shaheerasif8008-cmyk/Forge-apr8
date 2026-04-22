"""Connector: initiates OAuth flows for deployment integrations."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Protocol

import structlog

from factory.config import get_settings
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
    settings = get_settings()
    if settings.composio_api_key:
        return ComposioSdkClient(settings.composio_api_key)
    if settings.environment == "test":
        return InMemoryComposioClient()
    raise RuntimeError("Composio API key is required for deployment integrations.")


@dataclass(slots=True)
class ComposioSdkClient:
    api_key: str

    def _client(self):
        module = importlib.import_module("composio")
        client_cls = getattr(module, "Composio", None) or getattr(module, "ComposioToolSet", None)
        if client_cls is None:
            raise RuntimeError("Unsupported Composio SDK installation.")
        try:
            return client_cls(api_key=self.api_key)
        except TypeError:
            return client_cls()

    async def initiate_connection(self, *, deployment_id: str, tool_id: str, provider: str) -> dict[str, str]:
        client = self._client()
        if hasattr(client, "connected_accounts") and hasattr(client.connected_accounts, "initiate"):
            result = client.connected_accounts.initiate(app=provider, entity_id=deployment_id)
            connection_id = getattr(result, "id", "") or result.get("id", "")
            oauth_url = getattr(result, "redirect_url", "") or result.get("redirect_url", "")
            return {"connection_id": str(connection_id), "oauth_url": str(oauth_url)}
        if hasattr(client, "initiate_connection"):
            result = client.initiate_connection(app=provider, entity_id=deployment_id)
            connection_id = getattr(result, "id", "") or result.get("id", "")
            oauth_url = getattr(result, "redirect_url", "") or result.get("redirect_url", "")
            return {"connection_id": str(connection_id), "oauth_url": str(oauth_url)}
        raise RuntimeError("Composio SDK does not expose a supported connection initiation API.")

    async def get_connection_status(self, connection_id: str) -> str:
        client = self._client()
        if hasattr(client, "connected_accounts") and hasattr(client.connected_accounts, "get"):
            result = client.connected_accounts.get(connection_id)
            return str(getattr(result, "status", "") or result.get("status", "")).lower()
        if hasattr(client, "get_connection"):
            result = client.get_connection(connection_id)
            return str(getattr(result, "status", "") or result.get("status", "")).lower()
        raise RuntimeError("Composio SDK does not expose a supported status API.")

    async def delete_connection(self, connection_id: str) -> None:
        client = self._client()
        if hasattr(client, "connected_accounts") and hasattr(client.connected_accounts, "delete"):
            client.connected_accounts.delete(connection_id)
            return
        if hasattr(client, "delete_connection"):
            client.delete_connection(connection_id)
            return
        raise RuntimeError("Composio SDK does not expose a supported delete API.")


class Connector:
    def __init__(self, client: ComposioConnectionClient | None = None) -> None:
        self._client = client

    def _resolve_client(self) -> ComposioConnectionClient:
        if self._client is None:
            self._client = get_composio_client()
        return self._client

    async def connect(self, deployment: Deployment, blueprint: EmployeeBlueprint) -> Deployment:
        if deployment.status == DeploymentStatus.PENDING_CLIENT_ACTION:
            logger.info(
                "connector_connect_skipped",
                deployment_id=str(deployment.id),
                reason="pending_client_action",
            )
            return deployment

        deployment.integrations = []

        tool_ids = [
            component.component_id
            for component in blueprint.components
            if component.category == "tools"
            and component.component_id in TOOL_PROVIDER_MAP
        ]

        if not tool_ids:
            logger.info(
                "connector_connect_complete",
                deployment_id=str(deployment.id),
                integration_count=0,
            )
            return deployment

        deployment.status = DeploymentStatus.CONNECTING
        client = self._resolve_client()

        for tool_id in tool_ids:
            provider = TOOL_PROVIDER_MAP[tool_id]
            connection = await client.initiate_connection(
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
        client = self._resolve_client()
        for integration in deployment.integrations:
            if integration.status == "connected" or not integration.composio_connection_id:
                continue
            status = await client.get_connection_status(integration.composio_connection_id)
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
        client = self._resolve_client()
        for integration in deployment.integrations:
            if integration.composio_connection_id:
                await client.delete_connection(integration.composio_connection_id)


def pending_oauth_urls(deployment: Deployment) -> list[dict[str, str]]:
    return [
        {"tool_id": integration.tool_id, "oauth_url": integration.oauth_url or ""}
        for integration in deployment.integrations
        if integration.status == "pending" and integration.oauth_url
    ]


def all_integrations_connected(deployment: Deployment) -> bool:
    return all(integration.status == "connected" for integration in deployment.integrations)

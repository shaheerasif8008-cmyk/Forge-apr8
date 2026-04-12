"""Shared provider adapter helpers for runtime tool integrations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class InMemoryProviderAdapter:
    """Stateful provider adapter for local, sandbox, and fixture-backed integrations."""

    def __init__(self, provider: str, *, initial_state: dict[str, Any] | None = None) -> None:
        self.provider = provider
        self.initial_state = initial_state or {}
        self.connection_status = "ready"
        self.last_synced_at = datetime.now(UTC).isoformat()

    def metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "connection_status": self.connection_status,
            "last_synced_at": self.last_synced_at,
        }

    def touch(self) -> None:
        self.last_synced_at = datetime.now(UTC).isoformat()

"""Compatibility wrapper over the runtime-owned observability client."""

from employee_runtime.shared.observability import (
    get_langfuse_client,
    get_recorded_observations,
    reset_langfuse_client,
)

__all__ = [
    "get_langfuse_client",
    "get_recorded_observations",
    "reset_langfuse_client",
]

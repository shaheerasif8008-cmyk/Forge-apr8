"""LangFuse-compatible observability client with local fallback."""

from __future__ import annotations

import contextvars
import os
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from employee_runtime.shared.settings import get_settings

_current_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "employee_runtime_current_trace_id",
    default=None,
)
_current_span_stack: contextvars.ContextVar[tuple[str, ...]] = contextvars.ContextVar(
    "employee_runtime_current_span_stack",
    default=(),
)


@dataclass
class ObservationRecord:
    id: str
    kind: str
    name: str
    trace_id: str | None
    parent_id: str | None
    input: Any = None
    output: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    user_id: str = ""
    session_id: str = ""
    started_at: float = field(default_factory=time.monotonic)
    duration_ms: int = 0
    status: str = "open"


class _Observation:
    def __init__(
        self,
        client: "_BaseClient",
        *,
        kind: str,
        name: str,
        input: Any = None,
        metadata: dict[str, Any] | None = None,
        model: str = "",
        user_id: str = "",
        session_id: str = "",
    ) -> None:
        parent_stack = _current_span_stack.get()
        trace_id = _current_trace_id.get()
        if kind == "trace":
            trace_id = str(uuid4())
            parent_id = None
        else:
            parent_id = parent_stack[-1] if parent_stack else trace_id

        self._client = client
        self._kind = kind
        self._record = ObservationRecord(
            id=str(uuid4()),
            kind=kind,
            name=name,
            trace_id=trace_id,
            parent_id=parent_id,
            input=input,
            metadata=dict(metadata or {}),
            model=model,
            user_id=user_id,
            session_id=session_id,
        )
        self._trace_token: contextvars.Token[str | None] | None = None
        self._span_token: contextvars.Token[tuple[str, ...]] | None = None

    def __enter__(self) -> "_Observation":
        if self._kind == "trace":
            self._trace_token = _current_trace_id.set(self._record.trace_id)
            self._span_token = _current_span_stack.set((self._record.id,))
        elif self._kind == "span":
            self._span_token = _current_span_stack.set(_current_span_stack.get() + (self._record.id,))
        self._client._register(self._record)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc is not None:
            self._record.metadata.setdefault("error", str(exc))
            self._record.status = "error"
        self.end()
        if self._span_token is not None:
            _current_span_stack.reset(self._span_token)
        if self._trace_token is not None:
            _current_trace_id.reset(self._trace_token)

    def end(
        self,
        *,
        output: Any = None,
        metadata: dict[str, Any] | None = None,
        usage: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> None:
        if self._record.status == "closed":
            return
        if output is not None:
            self._record.output = output
        if metadata:
            self._record.metadata.update(metadata)
        if usage:
            self._record.usage = usage
        self._record.duration_ms = int((time.monotonic() - self._record.started_at) * 1000)
        self._record.status = status or ("error" if self._record.status == "error" else "closed")


class _BaseClient:
    enabled: bool = False

    def trace(
        self,
        name: str,
        *,
        input: Any = None,
        metadata: dict[str, Any] | None = None,
        user_id: str = "",
        session_id: str = "",
    ) -> _Observation:
        return _Observation(
            self,
            kind="trace",
            name=name,
            input=input,
            metadata=metadata,
            user_id=user_id,
            session_id=session_id,
        )

    def span(
        self,
        name: str,
        *,
        input: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> _Observation:
        return _Observation(self, kind="span", name=name, input=input, metadata=metadata)

    def generation(
        self,
        name: str,
        *,
        input: Any = None,
        metadata: dict[str, Any] | None = None,
        model: str = "",
    ) -> _Observation:
        return _Observation(
            self,
            kind="generation",
            name=name,
            input=input,
            metadata=metadata,
            model=model,
        )

    def _register(self, record: ObservationRecord) -> None:
        return None

    def reset(self) -> None:
        return None

    def export_records(self) -> list[dict[str, Any]]:
        return []


class NoOpLangfuseClient(_BaseClient):
    enabled = False


class MemoryLangfuseClient(_BaseClient):
    enabled = True

    def __init__(self) -> None:
        self._records: list[ObservationRecord] = []

    def _register(self, record: ObservationRecord) -> None:
        self._records.append(record)

    def reset(self) -> None:
        self._records.clear()

    def export_records(self) -> list[dict[str, Any]]:
        return [
            {
                "id": record.id,
                "kind": record.kind,
                "name": record.name,
                "trace_id": record.trace_id,
                "parent_id": record.parent_id,
                "input": record.input,
                "output": record.output,
                "metadata": dict(record.metadata),
                "model": record.model,
                "usage": dict(record.usage),
                "user_id": record.user_id,
                "session_id": record.session_id,
                "duration_ms": record.duration_ms,
                "status": record.status,
            }
            for record in self._records
        ]


_CLIENT: _BaseClient | None = None


def reset_langfuse_client(*, enabled: bool | None = None) -> _BaseClient:
    global _CLIENT
    is_enabled = enabled if enabled is not None else _is_enabled()
    _CLIENT = MemoryLangfuseClient() if is_enabled else NoOpLangfuseClient()
    return _CLIENT


def get_langfuse_client() -> _BaseClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = MemoryLangfuseClient() if _is_enabled() else NoOpLangfuseClient()
    return _CLIENT


def get_recorded_observations() -> list[dict[str, Any]]:
    return get_langfuse_client().export_records()


def _is_enabled() -> bool:
    env_value = os.getenv("LANGFUSE_ENABLED")
    if env_value is not None:
        return env_value.lower() in {"1", "true", "yes", "on"}
    return bool(get_settings().langfuse_enabled)

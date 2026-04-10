"""litellm multi-model router component.

Routes LLM calls to the right model based on task type and handles fallback
automatically.  This is the single point through which all factory and employee
LLM traffic flows — it enforces the architecture invariant from CLAUDE.md:

  "All LLM calls through core/llm.py — never hardcode model names or call
   providers directly. litellm routing with fallbacks is mandatory."

Task-type routing table (configurable, these are defaults):

  reasoning   → llm_reasoning_model  (o4-mini, deep thinking)
  safety      → llm_safety_model     (claude-haiku, fast guardrails)
  creative    → llm_primary_model    (sonnet, temperature 0.5)
  structured  → llm_primary_model    (sonnet, temperature 0.0 + Instructor)
  fast        → llm_fast_model       (haiku, latency-sensitive)
  default     → llm_primary_model    → fallback: llm_fallback_model

The router records every call to a RouteRecord for observability.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, TypeVar

import instructor
import litellm
import structlog
from pydantic import BaseModel

from component_library.interfaces import BaseComponent, ComponentHealth
from component_library.registry import register

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

litellm.suppress_debug_info = True


class TaskType(str, Enum):
    """Task types that influence model selection."""

    REASONING = "reasoning"    # deep multi-step reasoning → o4-mini class
    SAFETY = "safety"          # fast guardrail checks → haiku class
    CREATIVE = "creative"      # drafting, ideation → sonnet at temp 0.5
    STRUCTURED = "structured"  # Instructor extraction → sonnet at temp 0.0
    FAST = "fast"              # latency-critical → haiku class
    DEFAULT = "default"        # primary with fallback


class RouteRecord(BaseModel):
    """Logged for every routed call — feeds observability dashboards."""

    task_type: TaskType
    model_used: str
    fallback_used: bool
    latency_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    mode: str = "complete"  # complete | structure


@register("litellm_router")
class LitellmRouter(BaseComponent):
    """Multi-model router with task-type selection and automatic fallback.

    Configuration keys (passed to initialize()):
      primary_model    str  — default model (e.g. openrouter/anthropic/claude-3.5-sonnet)
      fallback_model   str  — used when primary fails
      reasoning_model  str  — for REASONING task type
      safety_model     str  — for SAFETY task type
      fast_model       str  — for FAST task type
      max_tokens       int  — default token cap (2048)
      timeout          int  — request timeout seconds (60)
      route_overrides  dict — override task→model mapping at runtime

    Example:
        router = LitellmRouter()
        await router.initialize({
            "primary_model": "openrouter/anthropic/claude-3.5-sonnet",
            "fallback_model": "openrouter/openai/gpt-4o",
        })
        result = await router.structure(MyOutput, messages, task_type=TaskType.STRUCTURED)
    """

    component_id = "litellm_router"
    version = "1.0.0"
    category = "models"

    _primary: str = ""
    _fallback: str = ""
    _reasoning: str = ""
    _safety: str = ""
    _fast: str = ""
    _max_tokens: int = 2048
    _timeout: int = 60
    _route_overrides: dict[str, str] = {}

    _instructor_client: instructor.AsyncInstructor | None = None
    _call_history: list[RouteRecord] = []

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def initialize(self, config: dict[str, Any]) -> None:
        """Configure routing table from blueprint component config.

        Args:
            config: Component config dict from EmployeeBlueprint.
        """
        self._primary = config.get("primary_model", "")
        self._fallback = config.get("fallback_model", "")
        self._reasoning = config.get("reasoning_model", self._primary)
        self._safety = config.get("safety_model", self._primary)
        self._fast = config.get("fast_model", self._primary)
        self._max_tokens = int(config.get("max_tokens", self._max_tokens))
        self._timeout = int(config.get("timeout", self._timeout))
        self._route_overrides = config.get("route_overrides", {})
        self._call_history = []

        self._instructor_client = instructor.from_litellm(
            litellm.acompletion, mode=instructor.Mode.JSON
        )
        logger.info(
            "litellm_router_init",
            primary=self._primary,
            fallback=self._fallback,
            reasoning=self._reasoning,
            safety=self._safety,
            fast=self._fast,
        )

    async def health_check(self) -> ComponentHealth:
        if not self._primary:
            return ComponentHealth(healthy=False, detail="primary_model not configured")
        return ComponentHealth(
            healthy=True,
            detail=f"primary={self._primary} fallback={self._fallback}",
        )

    def get_test_suite(self) -> list[str]:
        return ["tests/components/models/test_litellm_router.py"]

    # ── Public API ─────────────────────────────────────────────────────────────

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        task_type: TaskType = TaskType.DEFAULT,
        max_tokens: int | None = None,
        temperature: float | None = None,
        system: str | None = None,
    ) -> str:
        """Free-form text completion routed by task type.

        Args:
            messages: OpenAI-style message list.
            task_type: Determines which model to use.
            max_tokens: Override default.
            temperature: Override default (if None, inferred from task_type).
            system: Optional system prompt.

        Returns:
            Assistant text response.
        """
        model, temp = self._resolve(task_type, temperature)
        full_messages = self._build_messages(messages, system)
        kwargs = self._base_kwargs(model, max_tokens, temp)

        response, latency_ms, fallback_used = await self._call_with_fallback(
            litellm.acompletion,
            model=model,
            messages=full_messages,
            **{k: v for k, v in kwargs.items() if k != "model"},
        )
        content: str = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)

        self._record(
            task_type=task_type,
            model=kwargs["model"],
            fallback_used=fallback_used,
            latency_ms=latency_ms,
            usage=usage,
            mode="complete",
        )
        return content

    async def structure(
        self,
        response_model: type[T],
        messages: list[dict[str, str]],
        *,
        task_type: TaskType = TaskType.STRUCTURED,
        max_tokens: int | None = None,
        temperature: float | None = None,
        system: str | None = None,
        max_retries: int = 3,
    ) -> T:
        """Structured Pydantic output via Instructor, routed by task type.

        Args:
            response_model: Pydantic model class to extract.
            messages: OpenAI-style message list.
            task_type: Determines which model to use (default: STRUCTURED).
            max_tokens: Override default.
            temperature: Override default.
            system: Optional system prompt.
            max_retries: Instructor retries for schema validation failures.

        Returns:
            Populated instance of response_model.

        Raises:
            RuntimeError: If not initialised.
        """
        if self._instructor_client is None:
            raise RuntimeError("LitellmRouter not initialised — call initialize() first.")

        model, temp = self._resolve(task_type, temperature)
        full_messages = self._build_messages(messages, system)
        kwargs = self._base_kwargs(model, max_tokens, temp)

        t0 = time.monotonic()
        result: T = await self._instructor_client.chat.completions.create(
            model=kwargs["model"],
            response_model=response_model,
            messages=full_messages,
            max_retries=max_retries,
            max_tokens=kwargs["max_tokens"],
            temperature=kwargs["temperature"],
            timeout=self._timeout,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        self._record(
            task_type=task_type,
            model=kwargs["model"],
            fallback_used=False,
            latency_ms=latency_ms,
            usage=None,
            mode="structure",
        )
        return result

    @property
    def call_history(self) -> list[RouteRecord]:
        """Return the list of RouteRecord objects logged this session."""
        return list(self._call_history)

    # ── Internals ──────────────────────────────────────────────────────────────

    def _resolve(
        self,
        task_type: TaskType,
        temperature: float | None,
    ) -> tuple[str, float]:
        """Return (model_string, temperature) for a given task type.

        Args:
            task_type: Requested task type.
            temperature: Caller override; None means use task-type default.

        Returns:
            Tuple of (litellm model string, temperature float).
        """
        # Runtime override takes precedence
        if task_type.value in self._route_overrides:
            model = self._route_overrides[task_type.value]
        elif task_type == TaskType.REASONING:
            model = self._reasoning or self._primary
        elif task_type == TaskType.SAFETY:
            model = self._safety or self._primary
        elif task_type == TaskType.FAST:
            model = self._fast or self._primary
        else:
            model = self._primary

        # Default temperatures per task type
        if temperature is not None:
            temp = temperature
        elif task_type == TaskType.CREATIVE:
            temp = 0.5
        elif task_type == TaskType.REASONING:
            temp = 0.3
        else:
            temp = 0.0

        return model, temp

    def _build_messages(
        self,
        messages: list[dict[str, str]],
        system: str | None,
    ) -> list[dict[str, str]]:
        if system:
            return [{"role": "system", "content": system}, *messages]
        return messages

    def _base_kwargs(
        self,
        model: str,
        max_tokens: int | None,
        temperature: float,
    ) -> dict[str, Any]:
        return {
            "model": model,
            "max_tokens": max_tokens if max_tokens is not None else self._max_tokens,
            "temperature": temperature,
            "timeout": self._timeout,
        }

    async def _call_with_fallback(
        self,
        fn: Any,
        *,
        model: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> tuple[Any, int, bool]:
        """Try primary model; on transient failure, try fallback once.

        Args:
            fn: Async callable (litellm.acompletion).
            model: Primary model string.
            messages: Message list.
            **kwargs: Additional litellm kwargs.

        Returns:
            Tuple of (response, latency_ms, fallback_used).
        """
        _TRANSIENT = (
            litellm.exceptions.RateLimitError,
            litellm.exceptions.ServiceUnavailableError,
            litellm.exceptions.APIConnectionError,
        )

        async def _try(m: str) -> tuple[Any, int]:
            t0 = time.monotonic()
            resp = await fn(model=m, messages=messages, **kwargs)
            return resp, int((time.monotonic() - t0) * 1000)

        try:
            resp, latency_ms = await _try(model)
            return resp, latency_ms, False
        except litellm.exceptions.AuthenticationError:
            raise  # never fall back on auth errors
        except _TRANSIENT as exc:
            if not self._fallback or self._fallback == model:
                raise RuntimeError(f"Primary model failed and no fallback configured: {exc}") from exc
            logger.warning(
                "litellm_router_fallback",
                primary=model,
                fallback=self._fallback,
                reason=str(exc),
            )
            resp, latency_ms = await _try(self._fallback)
            return resp, latency_ms, True

    def _record(
        self,
        *,
        task_type: TaskType,
        model: str,
        fallback_used: bool,
        latency_ms: int,
        usage: Any,
        mode: str,
    ) -> None:
        in_tok = getattr(usage, "prompt_tokens", 0) or 0
        out_tok = getattr(usage, "completion_tokens", 0) or 0
        record = RouteRecord(
            task_type=task_type,
            model_used=model,
            fallback_used=fallback_used,
            latency_ms=latency_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            mode=mode,
        )
        self._call_history.append(record)
        logger.info(
            "litellm_router_call",
            task_type=task_type.value,
            model=model,
            fallback=fallback_used,
            latency_ms=latency_ms,
            in_tokens=in_tok,
            out_tokens=out_tok,
        )

"""Anthropic model provider component.

All LLM calls go through litellm so the rest of the factory never imports
the anthropic SDK directly.  Instructor is used for every call that expects
a structured Pydantic response — raw string parsing is forbidden per CLAUDE.md.

Supports two call modes:
  complete()  — free-form text completion (for generation tasks)
  structure() — structured Pydantic output via Instructor
"""

from __future__ import annotations

import time
from typing import Any, TypeVar

import instructor
import litellm
import structlog
from pydantic import BaseModel

from component_library.interfaces import BaseComponent, ComponentHealth
from component_library.registry import register

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

# litellm is quiet by default; errors surface through our logger
litellm.suppress_debug_info = True


@register("anthropic_provider")
class AnthropicProvider(BaseComponent):
    """Routes calls to Anthropic Claude via litellm + Instructor.

    Configuration keys (passed to initialize()):
      model          str  — litellm model string, e.g. "anthropic/claude-3-5-sonnet-20241022"
      max_tokens     int  — cap on output tokens (default 2048)
      temperature    float — 0.0 for factual, 0.3-0.7 for creative (default 0.0)
      timeout        int  — request timeout in seconds (default 60)
      api_key        str  — override ANTHROPIC_API_KEY from env (optional)

    All calls are logged with latency and token counts.
    Retries on transient errors (429, 503) with exponential backoff (max 3 tries).
    """

    component_id = "anthropic_provider"
    version = "1.0.0"
    category = "models"

    _model: str = "anthropic/claude-3-5-sonnet-20241022"
    _max_tokens: int = 2048
    _temperature: float = 0.0
    _timeout: int = 60
    _api_key: str | None = None
    _instructor_client: instructor.AsyncInstructor | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def initialize(self, config: dict[str, Any]) -> None:
        """Configure provider from blueprint component config.

        Args:
            config: Component config dict from EmployeeBlueprint.
        """
        self._model = config.get("model", self._model)
        self._max_tokens = int(config.get("max_tokens", self._max_tokens))
        self._temperature = float(config.get("temperature", self._temperature))
        self._timeout = int(config.get("timeout", self._timeout))
        self._api_key = config.get("api_key")

        # Instructor wraps litellm's async completion for structured output
        self._instructor_client = instructor.from_litellm(
            litellm.acompletion, mode=instructor.Mode.JSON
        )
        logger.info(
            "anthropic_provider_init",
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )

    async def health_check(self) -> ComponentHealth:
        """Verify the provider is configured (does not make a live API call)."""
        if not self._model:
            return ComponentHealth(healthy=False, detail="model not configured")
        return ComponentHealth(healthy=True, detail=f"model={self._model}")

    def get_test_suite(self) -> list[str]:
        return ["tests/components/models/test_anthropic_provider.py"]

    # ── Public API ─────────────────────────────────────────────────────────────

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        system: str | None = None,
    ) -> str:
        """Free-form text completion.

        Args:
            messages: OpenAI-style message list, e.g. [{"role": "user", "content": "..."}].
            max_tokens: Override instance default.
            temperature: Override instance default.
            system: Optional system prompt prepended before messages.

        Returns:
            The assistant's text response.

        Raises:
            RuntimeError: On non-retryable API errors.
        """
        full_messages = self._build_messages(messages, system)
        extra = self._call_kwargs(max_tokens, temperature)

        response, latency_ms = await self._call_with_retry(
            litellm.acompletion,
            model=self._model,
            messages=full_messages,
            **extra,
        )
        content: str = response.choices[0].message.content or ""
        self._log_call(
            mode="complete",
            latency_ms=latency_ms,
            usage=getattr(response, "usage", None),
        )
        return content

    async def structure(
        self,
        response_model: type[T],
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        system: str | None = None,
        max_retries: int = 3,
    ) -> T:
        """Structured output via Instructor — returns a validated Pydantic model.

        Args:
            response_model: The Pydantic model class to extract.
            messages: OpenAI-style message list.
            max_tokens: Override instance default.
            temperature: Override instance default.
            system: Optional system prompt.
            max_retries: Instructor retry attempts for schema validation failures.

        Returns:
            An instance of response_model populated by the LLM.

        Raises:
            RuntimeError: On non-retryable API errors.
            instructor.exceptions.InstructorRetryException: When the model
                repeatedly fails to produce a valid schema after max_retries.
        """
        if self._instructor_client is None:
            raise RuntimeError("AnthropicProvider not initialised — call initialize() first.")

        full_messages = self._build_messages(messages, system)
        extra = self._call_kwargs(max_tokens, temperature)

        t0 = time.monotonic()
        result: T = await self._instructor_client.chat.completions.create(
            model=self._model,
            response_model=response_model,
            messages=full_messages,
            max_retries=max_retries,
            **extra,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        self._log_call(mode="structure", latency_ms=latency_ms, response_model=response_model.__name__)
        return result

    # ── Internals ──────────────────────────────────────────────────────────────

    def _build_messages(
        self,
        messages: list[dict[str, str]],
        system: str | None,
    ) -> list[dict[str, str]]:
        """Prepend system message if provided."""
        if system:
            return [{"role": "system", "content": system}, *messages]
        return messages

    def _call_kwargs(
        self,
        max_tokens: int | None,
        temperature: float | None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "max_tokens": max_tokens if max_tokens is not None else self._max_tokens,
            "temperature": temperature if temperature is not None else self._temperature,
            "timeout": self._timeout,
        }
        if self._api_key:
            kwargs["api_key"] = self._api_key
        return kwargs

    async def _call_with_retry(
        self,
        fn: Any,
        *,
        max_attempts: int = 3,
        **kwargs: Any,
    ) -> tuple[Any, int]:
        """Call fn with exponential backoff on transient errors (429, 503).

        Args:
            fn: The async callable (e.g. litellm.acompletion).
            max_attempts: Maximum attempts before re-raising.
            **kwargs: Forwarded to fn.

        Returns:
            Tuple of (response, latency_ms).

        Raises:
            litellm.exceptions.RateLimitError: After max_attempts on rate limits.
            litellm.exceptions.ServiceUnavailableError: After max_attempts on 503s.
            litellm.exceptions.AuthenticationError: Immediately — not retried.
        """
        import asyncio

        delay = 0.5
        last_exc: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                t0 = time.monotonic()
                response = await fn(**kwargs)
                latency_ms = int((time.monotonic() - t0) * 1000)
                return response, latency_ms
            except litellm.exceptions.AuthenticationError:
                raise  # never retry auth errors
            except (
                litellm.exceptions.RateLimitError,
                litellm.exceptions.ServiceUnavailableError,
            ) as exc:
                last_exc = exc
                if attempt == max_attempts:
                    break
                logger.warning(
                    "anthropic_provider_retry",
                    attempt=attempt,
                    delay_s=delay,
                    error=str(exc),
                )
                await asyncio.sleep(delay)
                delay *= 2
            except litellm.exceptions.BadRequestError as exc:
                # 4xx that aren't auth — don't retry
                raise RuntimeError(f"LLM bad request: {exc}") from exc

        raise RuntimeError(
            f"LLM call failed after {max_attempts} attempts: {last_exc}"
        ) from last_exc

    def _log_call(self, *, mode: str, latency_ms: int, **extra: Any) -> None:
        logger.info(
            "anthropic_provider_call",
            mode=mode,
            model=self._model,
            latency_ms=latency_ms,
            **extra,
        )

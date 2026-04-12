"""Tests for LitellmRouter.

All LLM calls are mocked — no real API keys required.
Tests cover: routing table, fallback on transient errors, structured output,
RouteRecord logging, health check, and auth-error non-fallback.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import litellm
import pytest
from pydantic import BaseModel

from component_library.models.litellm_router import LitellmRouter, RouteRecord, TaskType

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_completion_response(content: str = "result") -> MagicMock:
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = MagicMock(prompt_tokens=8, completion_tokens=4)
    return resp


async def _init_router(**extra: object) -> LitellmRouter:
    router = LitellmRouter()
    config = {
        "primary_model": "openrouter/anthropic/claude-3.5-sonnet",
        "fallback_model": "openrouter/openai/gpt-4o",
        "reasoning_model": "openrouter/openai/o4-mini",
        "safety_model": "openrouter/anthropic/claude-3.5-haiku",
        "fast_model": "openrouter/anthropic/claude-3.5-haiku",
        **extra,
    }
    await router.initialize(config)
    return router


# ── Initialisation ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_initialize_sets_routing_table() -> None:
    router = await _init_router()
    assert router._primary == "openrouter/anthropic/claude-3.5-sonnet"
    assert router._fallback == "openrouter/openai/gpt-4o"
    assert router._reasoning == "openrouter/openai/o4-mini"
    assert router._safety == "openrouter/anthropic/claude-3.5-haiku"


@pytest.mark.anyio
async def test_health_check_ok() -> None:
    router = await _init_router()
    health = await router.health_check()
    assert health.healthy is True
    assert "sonnet" in health.detail


@pytest.mark.anyio
async def test_health_check_fails_without_primary() -> None:
    router = LitellmRouter()
    await router.initialize({})
    health = await router.health_check()
    assert health.healthy is False


# ── Task-type routing ─────────────────────────────────────────────────────────

@pytest.mark.anyio
@pytest.mark.parametrize(
    "task_type, expected_model_substr",
    [
        (TaskType.REASONING, "o4-mini"),
        (TaskType.SAFETY, "haiku"),
        (TaskType.FAST, "haiku"),
        (TaskType.DEFAULT, "sonnet"),
        (TaskType.CREATIVE, "sonnet"),
        (TaskType.STRUCTURED, "sonnet"),
    ],
)
async def test_complete_routes_to_correct_model(
    task_type: TaskType, expected_model_substr: str
) -> None:
    router = await _init_router()
    captured: list[str] = []

    async def fake_completion(**kwargs: object) -> MagicMock:
        captured.append(str(kwargs.get("model", "")))
        return _make_completion_response()

    with patch("litellm.acompletion", side_effect=fake_completion):
        await router.complete(
            [{"role": "user", "content": "test"}],
            task_type=task_type,
        )

    assert expected_model_substr in captured[0], (
        f"Expected model containing '{expected_model_substr}' for {task_type}, "
        f"got '{captured[0]}'"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "task_type, expected_temp",
    [
        (TaskType.CREATIVE, 0.5),
        (TaskType.REASONING, 0.3),
        (TaskType.STRUCTURED, 0.0),
        (TaskType.DEFAULT, 0.0),
        (TaskType.SAFETY, 0.0),
    ],
)
async def test_temperature_per_task_type(task_type: TaskType, expected_temp: float) -> None:
    router = await _init_router()
    captured: list[float] = []

    async def fake_completion(**kwargs: object) -> MagicMock:
        captured.append(float(kwargs.get("temperature", -1)))
        return _make_completion_response()

    with patch("litellm.acompletion", side_effect=fake_completion):
        await router.complete([{"role": "user", "content": "x"}], task_type=task_type)

    assert captured[0] == pytest.approx(expected_temp), (
        f"Wrong temperature for {task_type}: got {captured[0]}, expected {expected_temp}"
    )


@pytest.mark.anyio
async def test_temperature_override_respected() -> None:
    router = await _init_router()
    captured: list[float] = []

    async def fake(**kwargs: object) -> MagicMock:
        captured.append(float(kwargs.get("temperature", -1)))
        return _make_completion_response()

    with patch("litellm.acompletion", side_effect=fake):
        await router.complete(
            [{"role": "user", "content": "x"}],
            task_type=TaskType.CREATIVE,
            temperature=0.9,
        )

    assert captured[0] == pytest.approx(0.9)


# ── Route overrides ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_runtime_route_override() -> None:
    router = await _init_router(
        route_overrides={"reasoning": "openrouter/openai/gpt-4o"}
    )
    captured: list[str] = []

    async def fake(**kwargs: object) -> MagicMock:
        captured.append(str(kwargs.get("model", "")))
        return _make_completion_response()

    with patch("litellm.acompletion", side_effect=fake):
        await router.complete(
            [{"role": "user", "content": "x"}],
            task_type=TaskType.REASONING,
        )

    assert "gpt-4o" in captured[0]


# ── Fallback ──────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_fallback_used_on_rate_limit() -> None:
    router = await _init_router()
    call_models: list[str] = []

    async def fake(**kwargs: object) -> MagicMock:
        model = str(kwargs.get("model", ""))
        call_models.append(model)
        if "sonnet" in model:
            import litellm
            raise litellm.exceptions.RateLimitError(
                message="rate limit", llm_provider="openrouter", model=model
            )
        return _make_completion_response("fallback response")

    with patch("litellm.acompletion", side_effect=fake):
        result = await router.complete([{"role": "user", "content": "hi"}])

    assert result == "fallback response"
    assert any("sonnet" in m for m in call_models)  # primary tried
    assert any("gpt-4o" in m for m in call_models)  # fallback used


@pytest.mark.anyio
async def test_auth_error_does_not_fallback() -> None:
    router = await _init_router()
    call_count = 0

    async def fake(**kwargs: object) -> None:
        nonlocal call_count
        call_count += 1
        import litellm
        raise litellm.exceptions.AuthenticationError(
            message="bad key", llm_provider="openrouter", model="sonnet"
        )

    with patch("litellm.acompletion", side_effect=fake):
        with pytest.raises(litellm.exceptions.AuthenticationError):
            await router.complete([{"role": "user", "content": "hi"}])

    assert call_count == 1  # never tried fallback


@pytest.mark.anyio
async def test_fallback_raises_if_none_configured() -> None:
    router = await _init_router(fallback_model="")

    async def always_fail(**kwargs: object) -> None:
        import litellm
        raise litellm.exceptions.RateLimitError(
            message="rl", llm_provider="openrouter", model="sonnet"
        )

    with patch("litellm.acompletion", side_effect=always_fail):
        with pytest.raises(RuntimeError, match="no fallback"):
            await router.complete([{"role": "user", "content": "hi"}])


# ── Structured output ─────────────────────────────────────────────────────────

class _Extraction(BaseModel):
    entity: str
    confidence: float


@pytest.mark.anyio
async def test_structure_returns_pydantic_model() -> None:
    router = await _init_router()
    expected = _Extraction(entity="Acme Corp", confidence=0.95)

    with patch.object(
        router._instructor_client.chat.completions,  # type: ignore[union-attr]
        "create",
        new_callable=AsyncMock,
        return_value=expected,
    ):
        result = await router.structure(
            _Extraction,
            [{"role": "user", "content": "Extract entity from: Acme Corp signed."}],
        )

    assert isinstance(result, _Extraction)
    assert result.entity == "Acme Corp"
    assert result.confidence == pytest.approx(0.95)


@pytest.mark.anyio
async def test_structure_raises_if_not_initialized() -> None:
    router = LitellmRouter()
    with pytest.raises(RuntimeError, match="not initialised"):
        await router.structure(_Extraction, [{"role": "user", "content": "x"}])


# ── RouteRecord logging ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_call_history_recorded() -> None:
    router = await _init_router()

    with patch("litellm.acompletion", new_callable=AsyncMock,
               return_value=_make_completion_response()):
        await router.complete([{"role": "user", "content": "x"}], task_type=TaskType.FAST)
        await router.complete([{"role": "user", "content": "y"}], task_type=TaskType.SAFETY)

    history = router.call_history
    assert len(history) == 2
    assert history[0].task_type == TaskType.FAST
    assert history[1].task_type == TaskType.SAFETY
    assert all(isinstance(r, RouteRecord) for r in history)


@pytest.mark.anyio
async def test_fallback_recorded_in_history() -> None:
    router = await _init_router()
    call_count = 0

    async def fake(**kwargs: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            import litellm
            raise litellm.exceptions.ServiceUnavailableError(
                message="503", llm_provider="openrouter", model="sonnet"
            )
        return _make_completion_response()

    with patch("litellm.acompletion", side_effect=fake):
        await router.complete([{"role": "user", "content": "hi"}])

    assert router.call_history[0].fallback_used is True


# ── Metadata ──────────────────────────────────────────────────────────────────

def test_component_metadata() -> None:
    router = LitellmRouter()
    assert router.component_id == "litellm_router"
    assert router.category == "models"
    assert router.version == "1.0.0"
    assert "test_litellm_router" in router.get_test_suite()[0]

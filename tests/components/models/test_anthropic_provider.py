"""Tests for AnthropicProvider.

All LLM calls are mocked — no real API keys required.
Tests cover: initialization, complete(), structure(), retry logic,
health_check, and auth-error non-retry.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import litellm
import pytest
from pydantic import BaseModel

from component_library.models.anthropic_provider import AnthropicProvider
from component_library.interfaces import ComponentHealth


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_completion_response(content: str = "hello") -> MagicMock:
    """Build a mock litellm completion response."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
    return resp


async def _init_provider(**extra: object) -> AnthropicProvider:
    provider = AnthropicProvider()
    config = {
        "model": "anthropic/claude-3-5-haiku-20241022",
        "max_tokens": 512,
        "temperature": 0.0,
        **extra,
    }
    await provider.initialize(config)
    return provider


# ── Initialisation ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_initialize_sets_model() -> None:
    provider = await _init_provider()
    assert provider._model == "anthropic/claude-3-5-haiku-20241022"
    assert provider._max_tokens == 512


@pytest.mark.anyio
async def test_health_check_ok_after_init() -> None:
    provider = await _init_provider()
    health: ComponentHealth = await provider.health_check()
    assert health.healthy is True
    assert "claude" in health.detail


@pytest.mark.anyio
async def test_health_check_fails_before_init() -> None:
    provider = AnthropicProvider()
    provider._model = ""
    health = await provider.health_check()
    assert health.healthy is False


# ── complete() ────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_complete_returns_content() -> None:
    provider = await _init_provider()
    mock_resp = _make_completion_response("The answer is 42.")

    with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
        result = await provider.complete([{"role": "user", "content": "What is 42?"}])

    assert result == "The answer is 42."


@pytest.mark.anyio
async def test_complete_prepends_system_message() -> None:
    provider = await _init_provider()
    mock_resp = _make_completion_response("ok")
    captured: list[list[dict]] = []

    async def fake_completion(**kwargs: object) -> MagicMock:
        captured.append(kwargs["messages"])  # type: ignore[arg-type]
        return mock_resp

    with patch("litellm.acompletion", side_effect=fake_completion):
        await provider.complete(
            [{"role": "user", "content": "hi"}],
            system="You are a helpful assistant.",
        )

    assert captured[0][0]["role"] == "system"
    assert "helpful" in captured[0][0]["content"]


@pytest.mark.anyio
async def test_complete_uses_override_tokens() -> None:
    provider = await _init_provider()
    mock_resp = _make_completion_response("ok")
    captured: list[dict] = []

    async def fake_completion(**kwargs: object) -> MagicMock:
        captured.append(dict(kwargs))
        return mock_resp

    with patch("litellm.acompletion", side_effect=fake_completion):
        await provider.complete(
            [{"role": "user", "content": "hi"}],
            max_tokens=128,
        )

    assert captured[0]["max_tokens"] == 128


# ── structure() ───────────────────────────────────────────────────────────────

class _Summary(BaseModel):
    title: str
    key_points: list[str]


@pytest.mark.anyio
async def test_structure_returns_pydantic_model() -> None:
    provider = await _init_provider()
    expected = _Summary(title="Test", key_points=["point1", "point2"])

    # Patch the instructor client's create method
    with patch.object(
        provider._instructor_client.chat.completions,  # type: ignore[union-attr]
        "create",
        new_callable=AsyncMock,
        return_value=expected,
    ):
        result = await provider.structure(
            _Summary, [{"role": "user", "content": "Summarise this."}]
        )

    assert isinstance(result, _Summary)
    assert result.title == "Test"
    assert len(result.key_points) == 2


@pytest.mark.anyio
async def test_structure_raises_if_not_initialized() -> None:
    provider = AnthropicProvider()  # not initialized
    with pytest.raises(RuntimeError, match="not initialised"):
        await provider.structure(_Summary, [{"role": "user", "content": "x"}])


# ── Retry logic ───────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_complete_retries_on_rate_limit() -> None:
    provider = await _init_provider()
    mock_resp = _make_completion_response("ok after retry")
    call_count = 0

    async def flaky(**kwargs: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            import litellm
            raise litellm.exceptions.RateLimitError(
                message="rate limit", llm_provider="anthropic", model="claude"
            )
        return mock_resp

    with patch("litellm.acompletion", side_effect=flaky):
        with patch("asyncio.sleep", new_callable=AsyncMock):  # skip real waits
            result = await provider.complete([{"role": "user", "content": "hi"}])

    assert result == "ok after retry"
    assert call_count == 3


@pytest.mark.anyio
async def test_complete_raises_after_max_retries() -> None:
    provider = await _init_provider()

    async def always_rate_limit(**kwargs: object) -> None:
        import litellm
        raise litellm.exceptions.RateLimitError(
            message="rate limit", llm_provider="anthropic", model="claude"
        )

    with patch("litellm.acompletion", side_effect=always_rate_limit):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="failed after"):
                await provider.complete([{"role": "user", "content": "hi"}])


@pytest.mark.anyio
async def test_complete_does_not_retry_auth_error() -> None:
    provider = await _init_provider()
    call_count = 0

    async def auth_fail(**kwargs: object) -> None:
        nonlocal call_count
        call_count += 1
        import litellm
        raise litellm.exceptions.AuthenticationError(
            message="invalid key", llm_provider="anthropic", model="claude"
        )

    with patch("litellm.acompletion", side_effect=auth_fail):
        with pytest.raises(litellm.exceptions.AuthenticationError):
            await provider.complete([{"role": "user", "content": "hi"}])

    assert call_count == 1  # no retries


# ── Metadata ──────────────────────────────────────────────────────────────────

def test_component_metadata() -> None:
    provider = AnthropicProvider()
    assert provider.component_id == "anthropic_provider"
    assert provider.category == "models"
    assert provider.version == "1.0.0"
    assert "test_anthropic_provider" in provider.get_test_suite()[0]

from __future__ import annotations

from types import SimpleNamespace

from factory.pipeline.builder.generator import _resolve_generation_model


def test_generator_uses_openrouter_model_when_openrouter_and_openai_keys_present() -> None:
    settings = SimpleNamespace(
        anthropic_api_key="",
        openrouter_api_key="sk-or-test",
        openai_api_key="sk-test",
        generator_model="anthropic/claude-3-5-sonnet-20241022",
        llm_primary_model="openrouter/anthropic/claude-3.5-sonnet",
        llm_fallback_model="openrouter/openai/gpt-4o",
    )

    assert _resolve_generation_model(settings) == "openrouter/anthropic/claude-3.5-sonnet"


def test_generator_uses_openrouter_model_when_only_openrouter_key_present() -> None:
    settings = SimpleNamespace(
        anthropic_api_key="",
        openrouter_api_key="sk-or-test",
        openai_api_key="",
        generator_model="anthropic/claude-3-5-sonnet-20241022",
        llm_primary_model="openrouter/anthropic/claude-3.5-sonnet",
        llm_fallback_model="openrouter/openai/gpt-4o",
    )

    assert _resolve_generation_model(settings) == "openrouter/anthropic/claude-3.5-sonnet"


def test_generator_keeps_configured_model_when_anthropic_key_present() -> None:
    settings = SimpleNamespace(
        anthropic_api_key="sk-ant-test",
        openrouter_api_key="sk-or-test",
        openai_api_key="",
        generator_model="anthropic/claude-3-5-sonnet-20241022",
        llm_primary_model="openrouter/anthropic/claude-3.5-sonnet",
        llm_fallback_model="openrouter/openai/gpt-4o",
    )

    assert _resolve_generation_model(settings) == "anthropic/claude-3-5-sonnet-20241022"

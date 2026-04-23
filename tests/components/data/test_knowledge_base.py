from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from component_library.data.knowledge_base import KnowledgeBase
from component_library.interfaces import ComponentInitializationError
from component_library.tools.document_ingestion import DocumentIngestion


def _settings(embedding_model: str = "openai/test-embedding") -> SimpleNamespace:
    return SimpleNamespace(
        embedding_model=embedding_model,
        llm_primary_model="openrouter/anthropic/claude-3.5-sonnet",
        llm_fallback_model="openrouter/openai/gpt-4o",
        llm_reasoning_model="openrouter/openai/o4-mini",
        llm_safety_model="openrouter/anthropic/claude-3.5-haiku",
        llm_fast_model="openrouter/anthropic/claude-3.5-haiku",
    )


@pytest.fixture(autouse=True)
def disable_live_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    async def unavailable(**kwargs):
        raise ModuleNotFoundError("litellm unavailable")

    monkeypatch.setattr(
        "component_library.models.litellm_router.litellm.aembedding",
        unavailable,
    )


@pytest.mark.anyio
async def test_default_embedder_uses_litellm_router(monkeypatch: pytest.MonkeyPatch) -> None:
    embedding_mock = AsyncMock(return_value={"data": [{"embedding": [0.25] * 1536}]})
    monkeypatch.setattr(
        "component_library.data.knowledge_base.get_settings",
        lambda: _settings("openai/text-embedding-3-small"),
    )
    monkeypatch.setattr(
        "component_library.models.litellm_router.litellm.aembedding",
        embedding_mock,
    )

    kb = KnowledgeBase()
    await kb.initialize({"tenant_id": "tenant-a"})
    vector = await kb._embed("hello")

    assert len(vector) == 1536
    embedding_mock.assert_awaited_once()
    call = embedding_mock.await_args.kwargs
    assert call["model"] == "openai/text-embedding-3-small"
    assert call["input"] == "hello"


@pytest.mark.anyio
async def test_deterministic_fallback_is_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    warnings: list[dict[str, object]] = []

    monkeypatch.setattr(
        "component_library.data.knowledge_base.get_settings",
        lambda: _settings(),
    )
    monkeypatch.setattr(
        "component_library.data.knowledge_base.logger.warning",
        lambda event, **kwargs: warnings.append({"event": event, **kwargs}),
    )

    kb = KnowledgeBase()
    await kb.initialize({"tenant_id": "tenant-a"})
    with pytest.raises(RuntimeError, match="allow_deterministic_fallback=True"):
        await kb._embed("hello")

    fallback = KnowledgeBase()
    await fallback.initialize({"tenant_id": "tenant-a", "allow_deterministic_fallback": True})
    vector = await fallback._embed("hello")

    assert len(vector) == 1536
    assert warnings
    assert warnings[0]["event"] == "component_fallback_active"
    assert warnings[0]["component"] == "knowledge_base"

    health = await fallback.health_check()
    assert health.healthy is False
    assert "fallback_mode" in health.detail


@pytest.mark.anyio
async def test_knowledge_base_strict_mode_raises_on_embedding_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FORGE_STRICT_PROVIDERS", "true")
    monkeypatch.setattr(
        "component_library.data.knowledge_base.get_settings",
        lambda: _settings(),
    )

    kb = KnowledgeBase()
    await kb.initialize({"tenant_id": "tenant-a", "allow_deterministic_fallback": True})

    with pytest.raises(ComponentInitializationError):
        await kb._embed("hello")


class _FakeResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> _FakeResult:
        return self

    def all(self) -> list[dict[str, object]]:
        return self._rows


class _FakeSession:
    def __init__(self) -> None:
        self.statement = None
        self.params = None

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def execute(self, statement, params):
        self.statement = statement
        self.params = params
        return _FakeResult(
            [
                {
                    "tenant_id": uuid4(),
                    "document_id": uuid4(),
                    "chunk_index": 0,
                    "content": "Employment complaint checklist",
                    "metadata": {"practice_area": "employment"},
                }
            ]
        )


@pytest.mark.anyio
async def test_pgvector_query_uses_sql_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_session = _FakeSession()

    monkeypatch.setattr(
        "component_library.data.knowledge_base.get_settings",
        lambda: _settings(),
    )

    kb = KnowledgeBase()
    await kb.initialize(
        {
            "tenant_id": "tenant-a",
            "embedder": lambda text: [0.1] * 1536,
            "session_factory": lambda: fake_session,
        }
    )

    results = await kb.query("policy", k=3, filters={"practice_area": "employment"})

    assert results[0]["metadata"]["practice_area"] == "employment"
    statement_text = str(fake_session.statement)
    assert "WHERE tenant_id = :tenant_id" in statement_text
    assert "ORDER BY embedding <=> CAST(:query_embedding AS vector)" in statement_text
    assert "LIMIT :k" in statement_text
    assert fake_session.params["k"] == 3


@pytest.mark.anyio
async def test_chunk_fallback_splits_on_paragraphs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "component_library.data.knowledge_base.get_settings",
        lambda: _settings(),
    )

    kb = KnowledgeBase()
    await kb.initialize({"tenant_id": "tenant-a", "allow_deterministic_fallback": True})
    document = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."

    inserted = await kb.ingest("doc-1", document=document, metadata={})

    assert len(inserted) == 3
    assert all(len(chunk["content"]) <= 500 for chunk in inserted)


@pytest.mark.anyio
async def test_knowledge_base_ingest_and_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "component_library.data.knowledge_base.get_settings",
        lambda: _settings(),
    )

    kb = KnowledgeBase()
    await kb.initialize({"tenant_id": "tenant-a", "allow_deterministic_fallback": True})
    await kb.ingest(
        "doc-1",
        chunks=["The finance policy requires approvals above $5,000."],
        metadata={"practice_area": "finance"},
    )
    results = await kb.query("What approval threshold applies?", k=1)
    assert len(results) == 1
    assert "approval" in results[0]["content"].lower()


@pytest.mark.anyio
async def test_knowledge_base_cross_tenant_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "component_library.data.knowledge_base.get_settings",
        lambda: _settings(),
    )
    shared_store: list[dict] = []

    tenant_a = KnowledgeBase()
    await tenant_a.initialize(
        {
            "tenant_id": "tenant-a",
            "memory_store": shared_store,
            "allow_deterministic_fallback": True,
        }
    )
    await tenant_a.ingest("doc-a", chunks=["Alpha policy"], metadata={})

    tenant_b = KnowledgeBase()
    await tenant_b.initialize(
        {
            "tenant_id": "tenant-b",
            "memory_store": shared_store,
            "allow_deterministic_fallback": True,
        }
    )
    await tenant_b.ingest("doc-b", chunks=["Bravo policy"], metadata={})

    a_results = await tenant_a.query("policy", k=5)
    b_results = await tenant_b.query("policy", k=5)
    assert all(result["document_id"] != b_results[0]["document_id"] for result in a_results)
    assert all(result["document_id"] != a_results[0]["document_id"] for result in b_results)


@pytest.mark.anyio
async def test_knowledge_base_metadata_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "component_library.data.knowledge_base.get_settings",
        lambda: _settings(),
    )

    kb = KnowledgeBase()
    await kb.initialize({"tenant_id": "tenant-a", "allow_deterministic_fallback": True})
    await kb.ingest("doc-1", chunks=["Corporate filing checklist"], metadata={"practice_area": "corporate"})
    await kb.ingest("doc-2", chunks=["Employment complaint checklist"], metadata={"practice_area": "employment"})
    results = await kb.query("checklist", k=5, filters={"practice_area": "employment"})
    assert len(results) == 1
    assert results[0]["metadata"]["practice_area"] == "employment"


@pytest.mark.anyio
async def test_knowledge_base_ingests_document_via_document_ingestion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "component_library.data.knowledge_base.get_settings",
        lambda: _settings(),
    )

    ingestion = DocumentIngestion()
    await ingestion.initialize({})

    kb = KnowledgeBase()
    await kb.initialize(
        {
            "tenant_id": "tenant-a",
            "document_ingestion": ingestion,
            "allow_deterministic_fallback": True,
        }
    )
    await kb.ingest("doc-1", document="First paragraph.\n\nSecond paragraph.", metadata={})
    results = await kb.query("second", k=5)
    assert results


@pytest.mark.anyio
async def test_knowledge_base_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "component_library.data.knowledge_base.get_settings",
        lambda: _settings(),
    )

    kb = KnowledgeBase()
    await kb.initialize({"tenant_id": "tenant-a", "allow_deterministic_fallback": True})
    results = await kb.query("nothing here", k=3)
    assert results == []

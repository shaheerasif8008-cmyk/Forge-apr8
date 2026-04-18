from __future__ import annotations

import pytest

from component_library.data.knowledge_base import KnowledgeBase
from component_library.tools.document_ingestion import DocumentIngestion
from component_library.tools.search_tool import SearchTool
from component_library.work.research_engine import ResearchEngine
from component_library.work.schemas import ResearchReport, ResearchRequest


class _MockRouter:
    component_id = "litellm_router"

    def __init__(self) -> None:
        self.calls: list[tuple[tuple, dict]] = []

    async def complete_structured(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return ResearchReport(
            question="ignored",
            sources_used=["web"],
            key_findings=[],
            contradictions=[],
            confidence=0.81,
        )


def _embed_stub(text: str) -> list[float]:
    value = 1.0 if "retention" in text.lower() else 0.2
    return [value] * 1536


@pytest.mark.anyio
async def test_research_engine_happy_path() -> None:
    search = SearchTool()
    await search.initialize(
        {
            "fixtures": [
                {
                    "title": "Policy update",
                    "content": "The retention deadline increased to 90 days.",
                    "url": "https://example.com/policy",
                }
            ]
        }
    )

    docs = DocumentIngestion()
    await docs.initialize({})

    kb = KnowledgeBase()
    await kb.initialize({"tenant_id": "tenant-a", "embedder": _embed_stub})
    await kb.ingest("doc-1", chunks=["The handbook says retention is required for 90 days."])

    engine = ResearchEngine()
    await engine.initialize(
        {
            "search_tool": search,
            "knowledge_base": kb,
            "document_ingestion": docs,
        }
    )

    report = await engine.execute(
        ResearchRequest(
            question="What is the retention deadline?",
            sources=["web", "knowledge_base", "docs"],
            documents=["The local memo also says the retention deadline is required for 90 days."],
        )
    )
    assert report.question == "What is the retention deadline?"
    assert len(report.key_findings) >= 2
    assert "web" in report.sources_used


@pytest.mark.anyio
async def test_research_engine_empty_input() -> None:
    engine = ResearchEngine()
    await engine.initialize({})
    report = await engine.execute(ResearchRequest(question=""))
    assert report.key_findings == []
    assert report.confidence == 0.0


@pytest.mark.anyio
async def test_research_engine_surfaces_tool_errors() -> None:
    class _BrokenSearch:
        async def invoke(self, action: str, params: dict[str, str]) -> dict[str, str]:
            raise RuntimeError("search unavailable")

    engine = ResearchEngine()
    await engine.initialize(
        {
            "search_tool": _BrokenSearch(),
            "fallback_mode": "raise",
        }
    )
    with pytest.raises(RuntimeError, match="search unavailable"):
        await engine.execute(ResearchRequest(question="policy", sources=["web"]))


@pytest.mark.anyio
async def test_research_engine_uses_structured_model_when_forced() -> None:
    router = _MockRouter()
    search = SearchTool()
    await search.initialize({"fixtures": [{"title": "One", "content": "required", "url": "https://x.test"}]})

    engine = ResearchEngine()
    await engine.initialize(
        {
            "search_tool": search,
            "model_client": router,
            "force_llm": True,
        }
    )
    report = await engine.execute(ResearchRequest(question="required?", sources=["web"]))
    assert report.confidence == 0.81
    assert router.calls

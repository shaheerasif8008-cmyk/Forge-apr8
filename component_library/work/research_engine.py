"""research_engine work capability component."""

from __future__ import annotations

import os
from collections.abc import Iterable
from itertools import combinations
from typing import Any

import structlog
from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, WorkCapability
from component_library.models.litellm_router import TaskType
from component_library.registry import register
from component_library.work.schemas import Finding, ResearchReport, ResearchRequest

logger = structlog.get_logger(__name__)


@register("research_engine")
class ResearchEngine(WorkCapability):
    component_id = "research_engine"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._config = config
        self._search_tool = config.get("search_tool")
        self._knowledge_base = config.get("knowledge_base")
        self._document_ingestion = config.get("document_ingestion")
        self._model_client = config.get("model_client")
        self._fallback_mode = str(config.get("fallback_mode", "deterministic"))

    async def health_check(self) -> ComponentHealth:
        source_count = sum(
            component is not None
            for component in (self._search_tool, self._knowledge_base, self._document_ingestion)
        )
        mode = "llm_backed" if self._model_client is not None else "deterministic_fallback"
        return ComponentHealth(healthy=source_count > 0, detail=f"sources={source_count}; mode={mode}")

    def get_test_suite(self) -> list[str]:
        return ["tests/components/work/test_research_engine.py"]

    async def execute(self, input_data: BaseModel) -> BaseModel:
        if not isinstance(input_data, ResearchRequest):
            raise TypeError("ResearchEngine expects ResearchRequest")
        return await self.research(input_data)

    async def research(self, request: ResearchRequest) -> ResearchReport:
        question = request.question.strip()
        if not question:
            return ResearchReport(question="", sources_used=[], key_findings=[], contradictions=[], confidence=0.0)

        normalized_sources = [source.strip().lower() for source in request.sources if source.strip()]
        documents = [document.strip() for document in request.documents if document.strip()]
        raw_items: list[dict[str, Any]] = []

        if "web" in normalized_sources and self._search_tool is not None:
            raw_items.extend(await self._fetch_web_results(question, request.max_results))
        if "knowledge_base" in normalized_sources and self._knowledge_base is not None:
            raw_items.extend(
                await self._fetch_knowledge_results(
                    question=question,
                    max_results=request.max_results,
                    metadata_filters=request.metadata_filters,
                )
            )
        if ("docs" in normalized_sources or "documents" in normalized_sources) and documents:
            raw_items.extend(await self._fetch_document_results(documents))

        logger.info(
            "research_engine_sources_complete",
            question=question,
            source_count=len(raw_items),
            sources=normalized_sources,
        )

        if not raw_items:
            return ResearchReport(
                question=question,
                sources_used=normalized_sources,
                key_findings=[],
                contradictions=[],
                confidence=0.0,
            )

        if self._can_use_model():
            try:
                return await self._synthesize_with_model(question, normalized_sources, raw_items, request.notes)
            except Exception as exc:
                logger.warning("research_engine_llm_failed", error=str(exc))
                if self._fallback_mode != "deterministic":
                    raise

        return self._synthesize_deterministic(question, normalized_sources, raw_items)

    async def _fetch_web_results(self, question: str, max_results: int) -> list[dict[str, Any]]:
        payload = await self._search_tool.invoke(
            "search",
            {"query": question, "max_results": max_results},
        )
        results = payload.get("results", [])
        return [
            {
                "source_type": "web",
                "title": result.get("title", ""),
                "content": result.get("snippet", ""),
                "citation": result.get("url", ""),
            }
            for result in results
        ]

    async def _fetch_knowledge_results(
        self,
        *,
        question: str,
        max_results: int,
        metadata_filters: dict[str, str],
    ) -> list[dict[str, Any]]:
        results = await self._knowledge_base.query(question, k=max_results, filters=metadata_filters)
        return [
            {
                "source_type": "knowledge_base",
                "title": result.get("document_id", "knowledge-base"),
                "content": result.get("content", ""),
                "citation": f"kb:{result.get('document_id', 'unknown')}#{result.get('chunk_index', 0)}",
            }
            for result in results
        ]

    async def _fetch_document_results(self, documents: Iterable[str]) -> list[dict[str, Any]]:
        if self._document_ingestion is None:
            return []

        results: list[dict[str, Any]] = []
        for document in documents:
            params = {"file_path": document} if os.path.exists(document) else {"content": document}
            extracted = await self._document_ingestion.invoke("extract_text", params)
            text = str(extracted.get("text", "")).strip()
            if text:
                results.append(
                    {
                        "source_type": "docs",
                        "title": os.path.basename(document) if os.path.exists(document) else "inline-document",
                        "content": text[:1500],
                        "citation": document if os.path.exists(document) else "inline-document",
                    }
                )
        return results

    def _can_use_model(self) -> bool:
        if self._model_client is None:
            return False
        if self._config.get("force_llm"):
            return True
        client_id = getattr(self._model_client, "component_id", "")
        if client_id == "litellm_router":
            return any(
                os.getenv(name)
                for name in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")
            )
        if client_id == "anthropic_provider":
            return bool(getattr(self._model_client, "_api_key", None) or os.getenv("ANTHROPIC_API_KEY"))
        return True

    async def _synthesize_with_model(
        self,
        question: str,
        sources_used: list[str],
        raw_items: list[dict[str, Any]],
        notes: str,
    ) -> ResearchReport:
        system_prompt = (
            "You are a research synthesis engine. Produce concise findings with grounded citations only. "
            "Highlight contradictions when sources materially disagree. Keep confidence between 0 and 1."
        )
        evidence_block = "\n\n".join(
            (
                f"SOURCE TYPE: {item['source_type']}\n"
                f"TITLE: {item['title']}\n"
                f"CITATION: {item['citation']}\n"
                f"CONTENT: {item['content']}"
            )
            for item in raw_items[:12]
        )
        user_message = (
            f"QUESTION: {question}\n"
            f"SOURCES REQUESTED: {', '.join(sources_used)}\n"
            f"CLIENT NOTES: {notes or 'None'}\n\n"
            f"EVIDENCE:\n{evidence_block}"
        )
        result = await self._call_structured_model(system_prompt, user_message)
        return result.model_copy(
            update={
                "question": question,
                "sources_used": sources_used,
                "confidence": round(max(0.0, min(result.confidence, 1.0)), 2),
            }
        )

    async def _call_structured_model(
        self,
        system_prompt: str,
        user_message: str,
    ) -> ResearchReport:
        if getattr(self._model_client, "component_id", "") == "litellm_router":
            return await self._model_client.complete_structured(
                TaskType.STRUCTURED,
                system_prompt,
                user_message,
                ResearchReport,
            )
        if hasattr(self._model_client, "complete_structured"):
            return await self._model_client.complete_structured(
                system_prompt,
                user_message,
                ResearchReport,
            )
        return await self._model_client.structure(
            ResearchReport,
            user_message,
            system_prompt=system_prompt,
        )

    def _synthesize_deterministic(
        self,
        question: str,
        sources_used: list[str],
        raw_items: list[dict[str, Any]],
    ) -> ResearchReport:
        findings: list[Finding] = []
        for item in raw_items[:5]:
            statement = item.get("content", "").strip() or item.get("title", "").strip()
            if not statement:
                continue
            findings.append(
                Finding(
                    statement=statement[:220],
                    rationale=f"Derived from {item.get('title', 'source')}.",
                    citations=[item.get("citation", "")],
                    source_type=item.get("source_type", ""),
                    confidence=0.65 if item.get("content") else 0.45,
                )
            )

        contradictions = self._detect_contradictions(raw_items)
        confidence = 0.0
        if findings:
            confidence = round(min(0.92, 0.45 + (0.08 * min(len(findings), 4)) - (0.08 * len(contradictions))), 2)

        return ResearchReport(
            question=question,
            sources_used=sources_used,
            key_findings=findings,
            contradictions=contradictions,
            confidence=max(0.0, confidence),
        )

    def _detect_contradictions(self, raw_items: list[dict[str, Any]]) -> list[str]:
        contradiction_pairs = [
            ("required", "not required"),
            ("must", "must not"),
            ("increase", "decrease"),
            ("allowed", "prohibited"),
        ]
        contradictions: list[str] = []
        for first, second in combinations(raw_items, 2):
            first_text = f"{first.get('title', '')} {first.get('content', '')}".lower()
            second_text = f"{second.get('title', '')} {second.get('content', '')}".lower()
            for left, right in contradiction_pairs:
                if (left in first_text and right in second_text) or (right in first_text and left in second_text):
                    contradictions.append(
                        f"{first.get('citation', 'source')} appears to conflict with {second.get('citation', 'source')}."
                    )
                    break
        return list(dict.fromkeys(contradictions))

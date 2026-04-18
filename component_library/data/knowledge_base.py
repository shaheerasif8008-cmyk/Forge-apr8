"""knowledge_base data source component."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from component_library.interfaces import ComponentHealth, DataSource
from component_library.models.litellm_router import LitellmRouter
from component_library.registry import register
from factory.config import get_settings
from factory.models.orm import KnowledgeChunkRow

logger = structlog.get_logger(__name__)

EmbeddingCallable = Callable[[str], list[float] | Awaitable[list[float]]]
MAX_CHUNK_CHARS = 500


@register("knowledge_base")
class KnowledgeBase(DataSource):
    component_id = "knowledge_base"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        settings = get_settings()

        self._tenant_id = self._coerce_uuid(config.get("tenant_id", "default-tenant"))
        self._session_factory: async_sessionmaker[AsyncSession] | None = config.get("session_factory")
        self._document_ingestion = config.get("document_ingestion")
        self._embedder: EmbeddingCallable | None = config.get("embedder")
        self._memory_chunks: list[dict[str, Any]] = config.get("memory_store", [])
        self._embedding_model = str(config.get("embedding_model", settings.embedding_model))
        self._allow_deterministic_fallback = bool(config.get("allow_deterministic_fallback", False))
        self._router: LitellmRouter | None = None

        if self._embedder is None:
            router = LitellmRouter()
            await router.initialize(
                {
                    "primary_model": settings.llm_primary_model,
                    "fallback_model": settings.llm_fallback_model,
                    "reasoning_model": settings.llm_reasoning_model,
                    "safety_model": settings.llm_safety_model,
                    "fast_model": settings.llm_fast_model,
                    "embedding_model": self._embedding_model,
                }
            )
            self._router = router

    async def health_check(self) -> ComponentHealth:
        storage = "database" if self._session_factory is not None else "memory"
        embedder_mode = "custom" if self._embedder is not None else "litellm_router"
        if self._embedder is None and self._router is None:
            embedder_mode = "unavailable"
        return ComponentHealth(
            healthy=bool(self._tenant_id),
            detail=f"tenant={self._tenant_id}; storage={storage}; embedder={embedder_mode}",
        )

    def get_test_suite(self) -> list[str]:
        return ["tests/components/data/test_knowledge_base.py"]

    async def query(self, query: str, **kwargs: Any) -> Any:
        k = int(kwargs.get("k", 5))
        filters = dict(kwargs.get("filters", {}))
        query_embedding = await self._embed(query)
        chunks = await self._load_chunks(filters=filters, query_embedding=query_embedding, k=k)

        if self._session_factory is not None:
            return chunks

        scored = [
            {
                **chunk,
                "score": round(self._cosine_similarity(query_embedding, chunk["embedding"]), 4),
            }
            for chunk in chunks
        ]
        scored.sort(key=lambda item: item["score"], reverse=True)
        return [{key: value for key, value in item.items() if key != "embedding"} for item in scored[:k]]

    async def ingest(
        self,
        document_id: str | UUID,
        chunks: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        *,
        document: str | None = None,
    ) -> list[dict[str, Any]]:
        metadata = metadata or {}
        chunk_texts = list(chunks or [])
        if not chunk_texts and document:
            if self._document_ingestion is None:
                chunk_texts = self._chunk_document_fallback(document)
            else:
                payload = await self._document_ingestion.invoke(
                    "chunk",
                    {"content": document, "max_chunk_size": MAX_CHUNK_CHARS},
                )
                chunk_texts = [item["content"] for item in payload.get("chunks", [])]

        inserted: list[dict[str, Any]] = []
        for index, content in enumerate(chunk_texts):
            normalized_content = content.strip()
            if not normalized_content:
                continue
            chunk = {
                "tenant_id": str(self._tenant_id),
                "document_id": str(self._coerce_uuid(document_id)),
                "chunk_index": index,
                "content": normalized_content,
                "embedding": await self._embed(normalized_content),
                "metadata": metadata,
            }
            inserted.append(chunk)

        if self._session_factory is None:
            self._memory_chunks.extend(inserted)
            return [{key: value for key, value in item.items() if key != "embedding"} for item in inserted]

        async with self._session_factory() as session:
            session.add_all(
                [
                    KnowledgeChunkRow(
                        tenant_id=self._tenant_id,
                        document_id=self._coerce_uuid(item["document_id"]),
                        chunk_index=item["chunk_index"],
                        content=item["content"],
                        embedding=item["embedding"],
                        chunk_metadata=item["metadata"],
                    )
                    for item in inserted
                ]
            )
            await session.commit()
        return [{key: value for key, value in item.items() if key != "embedding"} for item in inserted]

    async def _load_chunks(
        self,
        *,
        filters: dict[str, Any],
        query_embedding: list[float],
        k: int,
    ) -> list[dict[str, Any]]:
        if self._session_factory is None:
            return [
                chunk
                for chunk in self._memory_chunks
                if chunk["tenant_id"] == str(self._tenant_id) and self._matches_filters(chunk["metadata"], filters)
            ]

        statement_parts = [
            "SELECT tenant_id, document_id, chunk_index, content, metadata",
            "FROM knowledge_chunks",
            "WHERE tenant_id = :tenant_id",
        ]
        params: dict[str, Any] = {
            "tenant_id": self._tenant_id,
            "query_embedding": self._vector_literal(query_embedding),
            "k": k,
        }
        if filters:
            statement_parts.append("AND metadata @> CAST(:metadata_filter AS JSONB)")
            params["metadata_filter"] = json.dumps(filters, sort_keys=True)
        statement_parts.extend(
            [
                "ORDER BY embedding <=> CAST(:query_embedding AS vector)",
                "LIMIT :k",
            ]
        )
        statement = text("\n".join(statement_parts))

        async with self._session_factory() as session:
            result = await session.execute(statement, params)
            rows = result.mappings().all()
        return [
            {
                "tenant_id": str(row["tenant_id"]),
                "document_id": str(row["document_id"]),
                "chunk_index": row["chunk_index"],
                "content": row["content"],
                "metadata": row["metadata"],
            }
            for row in rows
        ]

    async def _embed(self, text: str) -> list[float]:
        if callable(self._embedder):
            result = self._embedder(text)
            if hasattr(result, "__await__"):
                result = await result
            return [float(value) for value in result]

        if self._router is not None:
            try:
                return await self._router.embed(text)
            except (AttributeError, ImportError, ModuleNotFoundError) as exc:
                if not self._allow_deterministic_fallback:
                    raise RuntimeError(
                        "KnowledgeBase requires litellm embeddings unless "
                        "allow_deterministic_fallback=True is set explicitly."
                    ) from exc
                logger.warning(
                    "knowledge_base_deterministic_fallback",
                    tenant_id=str(self._tenant_id),
                    embedding_model=self._embedding_model,
                    reason=str(exc),
                )
                return self._deterministic_embed(text)

        if self._allow_deterministic_fallback:
            logger.warning(
                "knowledge_base_deterministic_fallback",
                tenant_id=str(self._tenant_id),
                embedding_model=self._embedding_model,
                reason="router unavailable",
            )
            return self._deterministic_embed(text)
        raise RuntimeError(
            "KnowledgeBase embedder is not configured and deterministic fallback is disabled."
        )

    def _chunk_document_fallback(self, document: str) -> list[str]:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", document) if part.strip()]
        if not paragraphs:
            return []

        chunks: list[str] = []
        for paragraph in paragraphs:
            if len(paragraph) > MAX_CHUNK_CHARS:
                chunks.extend(self._split_long_paragraph(paragraph))
            else:
                chunks.append(paragraph)
        return chunks

    def _split_long_paragraph(self, paragraph: str) -> list[str]:
        chunks: list[str] = []
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip() if current else word
            if len(candidate) > MAX_CHUNK_CHARS and current:
                chunks.append(current)
                current = word
            elif len(candidate) > MAX_CHUNK_CHARS:
                start = 0
                while start < len(word):
                    end = start + MAX_CHUNK_CHARS
                    chunks.append(word[start:end])
                    start = end
                current = ""
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks

    def _matches_filters(self, metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
        return all(metadata.get(key) == value for key, value in filters.items())

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right, strict=False))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    def _deterministic_embed(self, text: str) -> list[float]:
        vector: list[float] = []
        index = 0
        while len(vector) < 1536:
            digest = hashlib.sha256(f"{text}:{index}".encode()).digest()
            vector.extend(((byte / 255.0) * 2.0) - 1.0 for byte in digest)
            index += 1
        return vector[:1536]

    def _vector_literal(self, values: list[float]) -> str:
        return "[" + ",".join(f"{value:.12f}" for value in values) + "]"

    def _coerce_uuid(self, value: str | UUID) -> UUID:
        if isinstance(value, UUID):
            return value
        try:
            return UUID(str(value))
        except ValueError:
            return uuid5(NAMESPACE_URL, str(value))

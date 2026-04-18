"""knowledge_base data source component."""

from __future__ import annotations

import hashlib
import math
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from component_library.interfaces import ComponentHealth, DataSource
from component_library.registry import register
from factory.models.orm import KnowledgeChunkRow

logger = structlog.get_logger(__name__)


@register("knowledge_base")
class KnowledgeBase(DataSource):
    component_id = "knowledge_base"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._tenant_id = self._coerce_uuid(config.get("tenant_id", "default-tenant"))
        self._session_factory: async_sessionmaker[AsyncSession] | None = config.get("session_factory")
        self._document_ingestion = config.get("document_ingestion")
        self._embedder = config.get("embedder")
        self._memory_chunks: list[dict[str, Any]] = config.get("memory_store", [])

    async def health_check(self) -> ComponentHealth:
        storage = "database" if self._session_factory is not None else "memory"
        return ComponentHealth(healthy=bool(self._tenant_id), detail=f"tenant={self._tenant_id}; storage={storage}")

    def get_test_suite(self) -> list[str]:
        return ["tests/components/data/test_knowledge_base.py"]

    async def query(self, query: str, **kwargs: Any) -> Any:
        k = int(kwargs.get("k", 5))
        filters = dict(kwargs.get("filters", {}))
        query_embedding = await self._embed(query)
        chunks = await self._load_chunks(filters)
        scored = [
            {
                **chunk,
                "score": round(self._cosine_similarity(query_embedding, chunk["embedding"]), 4),
            }
            for chunk in chunks
        ]
        scored.sort(key=lambda item: item["score"], reverse=True)
        return [{k: v for k, v in item.items() if k != "embedding"} for item in scored[:k]]

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
                chunk_texts = [document]
            else:
                payload = await self._document_ingestion.invoke(
                    "chunk",
                    {"content": document, "max_chunk_size": 500},
                )
                chunk_texts = [item["content"] for item in payload.get("chunks", [])]

        inserted: list[dict[str, Any]] = []
        for index, content in enumerate(chunk_texts):
            if not content.strip():
                continue
            chunk = {
                "tenant_id": str(self._tenant_id),
                "document_id": str(self._coerce_uuid(document_id)),
                "chunk_index": index,
                "content": content,
                "embedding": await self._embed(content),
                "metadata": metadata,
            }
            inserted.append(chunk)

        if self._session_factory is None:
            self._memory_chunks.extend(inserted)
            return [{k: v for k, v in item.items() if k != "embedding"} for item in inserted]

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
        return [{k: v for k, v in item.items() if k != "embedding"} for item in inserted]

    async def _load_chunks(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        if self._session_factory is None:
            return [
                chunk
                for chunk in self._memory_chunks
                if chunk["tenant_id"] == str(self._tenant_id) and self._matches_filters(chunk["metadata"], filters)
            ]

        async with self._session_factory() as session:
            result = await session.execute(
                select(KnowledgeChunkRow).where(KnowledgeChunkRow.tenant_id == self._tenant_id)
            )
            rows = result.scalars().all()
            return [
                {
                    "tenant_id": str(row.tenant_id),
                    "document_id": str(row.document_id),
                    "chunk_index": row.chunk_index,
                    "content": row.content,
                    "embedding": list(row.embedding),
                    "metadata": row.chunk_metadata,
                }
                for row in rows
                if self._matches_filters(row.chunk_metadata, filters)
            ]

    async def _embed(self, text: str) -> list[float]:
        if callable(self._embedder):
            result = self._embedder(text)
            if hasattr(result, "__await__"):
                result = await result
            return list(result)

        vector: list[float] = []
        index = 0
        while len(vector) < 1536:
            digest = hashlib.sha256(f"{text}:{index}".encode()).digest()
            vector.extend(((byte / 255.0) * 2.0) - 1.0 for byte in digest)
            index += 1
        return vector[:1536]

    def _matches_filters(self, metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
        return all(metadata.get(key) == value for key, value in filters.items())

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right, strict=False))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    def _coerce_uuid(self, value: str | UUID) -> UUID:
        if isinstance(value, UUID):
            return value
        try:
            return UUID(str(value))
        except ValueError:
            return uuid5(NAMESPACE_URL, str(value))

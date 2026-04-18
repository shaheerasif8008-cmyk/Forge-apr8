from __future__ import annotations

import pytest

from component_library.data.knowledge_base import KnowledgeBase
from component_library.tools.document_ingestion import DocumentIngestion


@pytest.mark.anyio
async def test_knowledge_base_ingest_and_query() -> None:
    kb = KnowledgeBase()
    await kb.initialize({"tenant_id": "tenant-a"})
    await kb.ingest(
        "doc-1",
        chunks=["The finance policy requires approvals above $5,000."],
        metadata={"practice_area": "finance"},
    )
    results = await kb.query("What approval threshold applies?", k=1)
    assert len(results) == 1
    assert "approval" in results[0]["content"].lower()


@pytest.mark.anyio
async def test_knowledge_base_cross_tenant_isolation() -> None:
    shared_store: list[dict] = []

    tenant_a = KnowledgeBase()
    await tenant_a.initialize({"tenant_id": "tenant-a", "memory_store": shared_store})
    await tenant_a.ingest("doc-a", chunks=["Alpha policy"], metadata={})

    tenant_b = KnowledgeBase()
    await tenant_b.initialize({"tenant_id": "tenant-b", "memory_store": shared_store})
    await tenant_b.ingest("doc-b", chunks=["Bravo policy"], metadata={})

    a_results = await tenant_a.query("policy", k=5)
    b_results = await tenant_b.query("policy", k=5)
    assert all(result["document_id"] != b_results[0]["document_id"] for result in a_results)
    assert all(result["document_id"] != a_results[0]["document_id"] for result in b_results)


@pytest.mark.anyio
async def test_knowledge_base_metadata_filter() -> None:
    kb = KnowledgeBase()
    await kb.initialize({"tenant_id": "tenant-a"})
    await kb.ingest("doc-1", chunks=["Corporate filing checklist"], metadata={"practice_area": "corporate"})
    await kb.ingest("doc-2", chunks=["Employment complaint checklist"], metadata={"practice_area": "employment"})
    results = await kb.query("checklist", k=5, filters={"practice_area": "employment"})
    assert len(results) == 1
    assert results[0]["metadata"]["practice_area"] == "employment"


@pytest.mark.anyio
async def test_knowledge_base_ingests_document_via_document_ingestion() -> None:
    ingestion = DocumentIngestion()
    await ingestion.initialize({})

    kb = KnowledgeBase()
    await kb.initialize({"tenant_id": "tenant-a", "document_ingestion": ingestion})
    await kb.ingest("doc-1", document="First paragraph.\n\nSecond paragraph.", metadata={})
    results = await kb.query("second", k=5)
    assert results


@pytest.mark.anyio
async def test_knowledge_base_empty_result() -> None:
    kb = KnowledgeBase()
    await kb.initialize({"tenant_id": "tenant-a"})
    results = await kb.query("nothing here", k=3)
    assert results == []

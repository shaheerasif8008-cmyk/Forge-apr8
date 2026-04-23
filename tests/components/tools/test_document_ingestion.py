from __future__ import annotations

import pytest

import component_library.tools.document_ingestion as document_ingestion_module
from component_library.interfaces import ComponentInitializationError
from component_library.tools.document_ingestion import DocumentIngestion


@pytest.mark.anyio
async def test_document_ingestion_parse_and_chunk() -> None:
    tool = DocumentIngestion()
    await tool.initialize({})
    parsed = await tool.invoke("parse", {"content": "First paragraph.\n\nSecond paragraph."})
    chunked = await tool.invoke("chunk", {"elements": parsed["elements"], "max_chunk_size": 20})
    assert len(parsed["elements"]) == 2
    assert chunked["chunks"]


@pytest.mark.anyio
async def test_document_ingestion_extract_text(tmp_path) -> None:
    file_path = tmp_path / "doc.txt"
    file_path.write_text("Hello <b>world</b>", encoding="utf-8")

    tool = DocumentIngestion()
    await tool.initialize({})
    result = await tool.invoke("extract_text", {"file_path": str(file_path)})
    assert result["text"] == "Hello world"


@pytest.mark.anyio
async def test_document_ingestion_handles_empty_input() -> None:
    tool = DocumentIngestion()
    await tool.initialize({})
    result = await tool.invoke("extract_text", {})
    assert result["text"] == ""


@pytest.mark.anyio
async def test_document_ingestion_rejects_unknown_action() -> None:
    tool = DocumentIngestion()
    await tool.initialize({})
    with pytest.raises(ValueError, match="Unsupported document ingestion action"):
        await tool.invoke("unknown", {})


@pytest.mark.anyio
async def test_document_ingestion_reports_unhealthy_parse_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(document_ingestion_module, "partition", None)
    tool = DocumentIngestion()
    await tool.initialize({})

    health = await tool.health_check()

    assert health.healthy is False
    assert "fallback_mode" in health.detail


@pytest.mark.anyio
async def test_document_ingestion_strict_mode_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(document_ingestion_module, "partition", None)
    monkeypatch.setenv("FORGE_STRICT_PROVIDERS", "true")
    tool = DocumentIngestion()

    with pytest.raises(ComponentInitializationError):
        await tool.initialize({})

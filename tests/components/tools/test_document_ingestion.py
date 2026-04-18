from __future__ import annotations

import pytest

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

from __future__ import annotations

import pytest

from component_library.interfaces import ComponentInitializationError
from component_library.tools.file_storage_tool import FileStorageTool


@pytest.mark.anyio
async def test_file_storage_tool_upload_download_list_delete(tmp_path) -> None:
    tool = FileStorageTool()
    await tool.initialize({"provider": "local", "tenant_id": "tenant-1", "root_dir": tmp_path})
    await tool.invoke("upload", {"key": "docs/report.txt", "content": "hello"})
    listed = await tool.invoke("list", {"prefix": "docs"})
    downloaded = await tool.invoke("download", {"key": "docs/report.txt"})
    deleted = await tool.invoke("delete", {"key": "docs/report.txt"})
    assert listed["items"]
    assert downloaded["content"] == "hello"
    assert deleted["deleted"] is True


@pytest.mark.anyio
async def test_file_storage_tool_scopes_keys_by_tenant(tmp_path) -> None:
    tool = FileStorageTool()
    await tool.initialize({"provider": "local", "tenant_id": "tenant-abc", "root_dir": tmp_path})
    result = await tool.invoke("upload", {"key": "inbox/item.txt", "content": "x"})
    assert result["key"].startswith("tenant-abc/")


@pytest.mark.anyio
async def test_file_storage_tool_handles_missing_download(tmp_path) -> None:
    tool = FileStorageTool()
    await tool.initialize({"provider": "local", "tenant_id": "tenant-1", "root_dir": tmp_path})
    result = await tool.invoke("download", {"key": "missing.txt"})
    assert result["exists"] is False


@pytest.mark.anyio
async def test_file_storage_tool_rejects_unknown_action(tmp_path) -> None:
    tool = FileStorageTool()
    await tool.initialize({"provider": "local", "tenant_id": "tenant-1", "root_dir": tmp_path})
    with pytest.raises(ValueError, match="Unsupported file storage action"):
        await tool.invoke("unknown", {})


@pytest.mark.anyio
async def test_file_storage_tool_reports_unhealthy_s3_fallback(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    tool = FileStorageTool()
    await tool.initialize({"provider": "s3", "tenant_id": "tenant-1", "root_dir": tmp_path})

    health = await tool.health_check()

    assert health.healthy is False
    assert "fallback_mode" in health.detail


@pytest.mark.anyio
async def test_file_storage_tool_strict_mode_raises(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.setenv("FORGE_STRICT_PROVIDERS", "true")
    tool = FileStorageTool()

    with pytest.raises(ComponentInitializationError):
        await tool.initialize({"provider": "s3", "tenant_id": "tenant-1", "root_dir": tmp_path})

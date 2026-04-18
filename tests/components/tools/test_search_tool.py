from __future__ import annotations

import httpx
import pytest

from component_library.tools.search_tool import SearchTool


@pytest.mark.anyio
async def test_search_tool_fixture_search() -> None:
    tool = SearchTool()
    await tool.initialize(
        {
            "fixtures": [
                {"title": "Retention policy", "content": "Retention is required for 90 days.", "url": "https://a"},
                {"title": "Other", "content": "Completely unrelated", "url": "https://b"},
            ]
        }
    )
    result = await tool.invoke("search", {"query": "retention", "max_results": 1})
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Retention policy"


@pytest.mark.anyio
async def test_search_tool_remote_tavily_path() -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://api.tavily.com/search")
        return httpx.Response(
            200,
            json={"results": [{"url": "https://remote", "title": "Remote", "content": "Live result"}]},
        )

    tool = SearchTool()
    await tool.initialize(
        {
            "tavily_api_key": "test-key",
            "transport": httpx.MockTransport(_handler),
        }
    )
    result = await tool.invoke("search", {"query": "live"})
    assert result["results"][0]["url"] == "https://remote"


@pytest.mark.anyio
async def test_search_tool_empty_query() -> None:
    tool = SearchTool()
    await tool.initialize({})
    result = await tool.invoke("search", {"query": ""})
    assert result["results"] == []


@pytest.mark.anyio
async def test_search_tool_rejects_unknown_action() -> None:
    tool = SearchTool()
    await tool.initialize({})
    with pytest.raises(ValueError, match="Unsupported search action"):
        await tool.invoke("unknown", {})

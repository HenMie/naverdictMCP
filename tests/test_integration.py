"""In-memory MCP integration tests."""

from __future__ import annotations

import logging

import pytest
from fastmcp import Client

from src.application import create_mcp
from src.models import DictionaryEntry
from src.service import DictionaryService
from tests.conftest import StubGateway, StubGatewayFactory


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_lists_only_structured_search_tool(sample_entry: DictionaryEntry) -> None:
    gateway = StubGateway((sample_entry,))
    service = DictionaryService(StubGatewayFactory(gateway), concurrency=5)
    mcp = create_mcp(service, logging.getLogger("test-mcp"))

    async with Client(mcp) as client:
        tools = await client.list_tools()
        result = await client.call_tool(
            "search_words",
            {"words": [" 안녕하세요 ", "", "안녕하세요"], "dict_type": "ko-zh"},
        )

    assert [tool.name for tool in tools] == ["search_words"]
    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["summary"] == {"total": 3, "succeeded": 2, "failed": 1}
    assert result.structured_content["items"][1]["error"]["code"] == "validation_error"
    assert gateway.calls == [("안녕하세요", "ko-zh")]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_schema_rejects_more_than_ten_words(sample_entry: DictionaryEntry) -> None:
    service = DictionaryService(StubGatewayFactory(StubGateway((sample_entry,))), concurrency=5)
    mcp = create_mcp(service, logging.getLogger("test-mcp-validation"))

    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_words",
            {"words": [str(index) for index in range(11)], "dict_type": "ko-zh"},
            raise_on_error=False,
        )

    assert result.is_error is True

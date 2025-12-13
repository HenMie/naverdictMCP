"""Integration tests for MCP server (in-memory transport).

为了让测试在本地/CI 环境中稳定运行，这里的集成测试使用 FastMCP 的 in-memory transport，
避免依赖端口、进程管理和外部网络。
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from src.cache import cache
from src.metrics import metrics
from src.rate_limiter import rate_limiter
from src.server import mcp


def _tool_name(tool: object) -> str:
    """兼容 Tool 对象或 dict 结构。"""
    if hasattr(tool, "name"):
        return getattr(tool, "name")
    if isinstance(tool, dict):
        return str(tool.get("name", ""))
    return str(tool)


@pytest.fixture
async def mcp_client():
    async with Client(mcp) as client:
        yield client


@pytest.fixture(autouse=True)
def reset_global_state():
    """确保测试之间互不影响（缓存/指标/限流都是全局单例）。"""
    cache.clear()
    metrics.reset()
    rate_limiter.reset()


async def test_list_tools_only_two_tools(mcp_client):
    tools = await mcp_client.list_tools()
    names = sorted(_tool_name(t) for t in tools)
    assert names == ["batch_search_words", "search_word"]


async def test_search_word_normalizes_word(mcp_client, sample_api_response):
    """search_word 应在 server 层做 strip/规范化，并把规范化后的 word 返回给客户端。"""
    with patch("src.server.NaverClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.search.return_value = sample_api_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        result = await mcp_client.call_tool(
            "search_word",
            {"word": "  안녕하세요  ", "dict_type": "ko-zh"},
        )
        payload = json.loads(result.data)

        assert payload["success"] is True
        assert payload["word"] == "안녕하세요"
        mock_client.search.assert_awaited_once_with("안녕하세요", "ko-zh")


async def test_batch_search_dedup_and_partial_success(mcp_client, sample_api_response):
    """batch_search_words：去重 miss、结构化错误、整体 partial_success 语义。"""
    with patch("src.server.NaverClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.search.return_value = sample_api_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        result = await mcp_client.call_tool(
            "batch_search_words",
            {"words": ["  안녕하세요  ", "", "안녕하세요"], "dict_type": "ko-zh"},
        )
        payload = json.loads(result.data)

        assert payload["success"] is False
        assert payload["partial_success"] is True
        assert payload["count"] == 3
        assert payload["success_count"] == 2
        assert payload["fail_count"] == 1

        # 去重 miss：只应对 "안녕하세요" 访问一次上游
        mock_client.search.assert_awaited_once_with("안녕하세요", "ko-zh")

        # 第 2 个词是校验失败
        assert payload["results"][1]["success"] is False
        assert payload["results"][1]["error_type"] == "validation"

"""Tests for unified MCP v2 search tool."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.cache import cache
from src.metrics import metrics
from src.rate_limiter import rate_limiter
from src.server import _search_words_impl


class TestSearchWordsTool:
    """Tests for the unified _search_words_impl tool."""

    def setup_method(self) -> None:
        cache.clear()
        metrics.reset()
        rate_limiter.reset()

    @pytest.mark.asyncio
    async def test_search_words_single_success(self, sample_api_response):
        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search.return_value = sample_api_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _search_words_impl(["안녕하세요"], "ko-zh")
            payload = json.loads(result)

            assert payload["success"] is True
            assert payload["partial_success"] is False
            assert payload["total_count"] == 1
            assert payload["success_count"] == 1
            assert payload["fail_count"] == 0
            assert len(payload["successful_results"]) == 1
            assert payload["successful_results"][0]["index"] == 0
            assert payload["successful_results"][0]["word"] == "안녕하세요"
            mock_client.search.assert_awaited_once_with("안녕하세요", "ko-zh")

    @pytest.mark.asyncio
    async def test_search_words_empty_list_validation(self):
        result = await _search_words_impl([], "ko-zh")
        payload = json.loads(result)

        assert payload["success"] is False
        assert payload["total_count"] == 0
        assert payload["fail_count"] == 1
        assert payload["failed_results"][0]["error_type"] == "validation"

    @pytest.mark.asyncio
    async def test_search_words_max_30_validation(self):
        words = [f"word{i}" for i in range(31)]
        result = await _search_words_impl(words, "ko-zh")
        payload = json.loads(result)

        assert payload["success"] is False
        assert payload["total_count"] == 31
        assert payload["fail_count"] == 1
        assert payload["failed_results"][0]["error_type"] == "validation"
        assert "最多支持 30" in payload["failed_results"][0]["details"]

    @pytest.mark.asyncio
    async def test_search_words_partial_success_with_invalid_item(self, sample_api_response):
        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search.return_value = sample_api_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _search_words_impl(["안녕하세요", ""], "ko-zh")
            payload = json.loads(result)

            assert payload["success"] is False
            assert payload["partial_success"] is True
            assert payload["success_count"] == 1
            assert payload["fail_count"] == 1
            assert payload["failed_results"][0]["index"] == 1
            assert payload["failed_results"][0]["error_type"] == "validation"

    @pytest.mark.asyncio
    async def test_search_words_deduped_miss_only_calls_upstream_once(self, sample_api_response):
        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search.return_value = sample_api_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _search_words_impl(["  안녕하세요  ", "안녕하세요"], "ko-zh")
            payload = json.loads(result)

            assert payload["success_count"] == 2
            assert payload["fail_count"] == 0
            assert payload["successful_results"][0]["deduped"] is False
            assert payload["successful_results"][1]["deduped"] is True
            mock_client.search.assert_awaited_once_with("안녕하세요", "ko-zh")

    @pytest.mark.asyncio
    async def test_search_words_cache_hit_returns_from_cache(self):
        cached = json.dumps(
            {
                "success": True,
                "word": "안녕하세요",
                "dict_type": "ko-zh",
                "count": 1,
                "results": [{"word": "안녕하세요"}],
            },
            ensure_ascii=False,
        )
        cache.set("안녕하세요", "ko-zh", cached)

        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _search_words_impl(["안녕하세요"], "ko-zh")
            payload = json.loads(result)

            assert payload["success"] is True
            assert payload["successful_results"][0]["from_cache"] is True
            mock_client.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_words_rate_limit_allows_partial_miss(self, sample_api_response):
        cached = json.dumps(
            {
                "success": True,
                "word": "안녕하세요",
                "dict_type": "ko-zh",
                "count": 1,
                "results": [{"word": "안녕하세요"}],
            },
            ensure_ascii=False,
        )
        cache.set("안녕하세요", "ko-zh", cached)

        with (
            patch("src.server.NaverClient") as mock_client_class,
            patch("src.server.rate_limiter.consume", side_effect=[True, False]),
            patch("src.server.rate_limiter.get_remaining_tokens", return_value=0),
        ):
            mock_client = AsyncMock()
            mock_client.search.return_value = sample_api_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _search_words_impl(
                ["안녕하세요", "학교", "선생님"],
                "ko-zh",
            )
            payload = json.loads(result)

            assert payload["partial_success"] is True
            assert payload["success_count"] == 2
            assert payload["fail_count"] == 1
            assert payload["failed_results"][0]["error_type"] == "rate_limit"
            mock_client.search.assert_awaited_once_with("학교", "ko-zh")

    @pytest.mark.asyncio
    async def test_search_words_failure_has_clear_reason(self):
        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search.side_effect = httpx.TimeoutException("timeout")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _search_words_impl(["학교"], "ko-zh")
            payload = json.loads(result)

            assert payload["success"] is False
            assert payload["fail_count"] == 1
            assert payload["failed_results"][0]["error_type"] == "timeout"
            assert payload["failed_results"][0]["details"] != ""

    @pytest.mark.asyncio
    async def test_search_words_upstream_429_error_type(self):
        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "1"}
            mock_client.search.side_effect = httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=MagicMock(),
                response=mock_response,
            )
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _search_words_impl(["학교"], "ko-zh")
            payload = json.loads(result)

            assert payload["success"] is False
            assert payload["failed_results"][0]["error_type"] == "upstream_rate_limit"

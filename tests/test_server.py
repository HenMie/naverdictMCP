"""Tests for MCP server module."""

import asyncio
import pytest
import json
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from src.server import _batch_search_words_impl, _search_word_impl
from src.client import ValidationError
from src.cache import cache
from src.config import config
from src.metrics import metrics
from src.rate_limiter import rate_limiter


class TestSearchWordTool:
    """Tests for the _search_word_impl MCP tool."""
    
    def setup_method(self):
        """Clear cache and metrics before each test."""
        cache.clear()
        metrics.reset()
        rate_limiter.reset()
    
    @pytest.mark.asyncio
    async def test__search_word_impl_success(self, sample_api_response):
        """Test successful word search."""
        with patch("src.server.NaverClient") as mock_client_class:
            # Setup mock client
            mock_client = AsyncMock()
            mock_client.search.return_value = sample_api_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            # Call the tool
            result = await _search_word_impl("안녕하세요", "ko-zh")
            
            # Verify result
            assert "안녕하세요" in result
            assert "你好" in result
            assert isinstance(result, str)
            
            # Verify client was called correctly
            mock_client.search.assert_called_once_with("안녕하세요", "ko-zh")
    
    @pytest.mark.asyncio
    async def test__search_word_impl_default_dict_type(self, sample_api_response):
        """Test search with default dictionary type."""
        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search.return_value = sample_api_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            # Call without specifying dict_type
            result = await _search_word_impl("안녕하세요")
            
            # Should default to "ko-zh"
            mock_client.search.assert_called_once_with("안녕하세요", "ko-zh")
    
    @pytest.mark.asyncio
    async def test__search_word_impl_ko_en(self, sample_api_response):
        """Test search with Korean-English dictionary."""
        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search.return_value = sample_api_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            result = await _search_word_impl("학교", "ko-en")
            
            mock_client.search.assert_called_once_with("학교", "ko-en")
    
    @pytest.mark.asyncio
    async def test__search_word_impl_empty_results(self, empty_api_response):
        """Test search with no results."""
        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search.return_value = empty_api_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            result = await _search_word_impl("不存在的词")
            
            # Verify it returns valid JSON with empty results
            assert '"success": true' in result
            assert '"count": 0' in result
            assert '"results": []' in result

    @pytest.mark.asyncio
    async def test__search_word_impl_negative_cache_ttl(self, empty_api_response):
        """未找到结果应走负缓存短 TTL，过期后需要重新访问上游。"""
        with (
            patch("src.server.NaverClient") as mock_client_class,
            patch.object(config, "CACHE_NEGATIVE_TTL", 1),
            patch.object(config, "CACHE_TTL", 3600),
        ):
            mock_client = AsyncMock()
            mock_client.search.return_value = empty_api_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            # 第一次：cache miss -> upstream
            result1 = await _search_word_impl("不存在的词", "ko-zh")
            assert json.loads(result1)["success"] is True

            # 第二次：短 TTL 内应缓存命中（不再访问上游）
            result2 = await _search_word_impl("不存在的词", "ko-zh")
            assert json.loads(result2)["success"] is True
            mock_client.search.assert_awaited_once_with("不存在的词", "ko-zh")

            # 负缓存过期后：再次访问上游
            await asyncio.sleep(1.1)
            result3 = await _search_word_impl("不存在的词", "ko-zh")
            assert json.loads(result3)["success"] is True
            assert mock_client.search.await_count == 2
    
    @pytest.mark.asyncio
    async def test__search_word_impl_validation_error(self):
        """Test handling of validation errors."""
        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search.side_effect = ValidationError("搜索词不能为空")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            result = await _search_word_impl("")
            result_dict = json.loads(result)
            
            assert result_dict["success"] is False
            assert result_dict["error_type"] == "validation"
            assert "验证" in result_dict["error"]
    
    @pytest.mark.asyncio
    async def test__search_word_impl_timeout_error(self):
        """Test handling of timeout errors."""
        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search.side_effect = httpx.TimeoutException("Request timeout")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            result = await _search_word_impl("테스트")
            result_dict = json.loads(result)
            
            assert result_dict["success"] is False
            assert result_dict["error_type"] == "timeout"
            assert "超时" in result_dict["error"]
    
    @pytest.mark.asyncio
    async def test__search_word_impl_http_error(self):
        """Test handling of HTTP errors."""
        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.headers = {}
            mock_client.search.side_effect = httpx.HTTPStatusError(
                "404 Not Found",
                request=MagicMock(),
                response=mock_response
            )
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            result = await _search_word_impl("테스트")
            result_dict = json.loads(result)
            
            assert result_dict["success"] is False
            assert result_dict["error_type"] == "http_error"
            assert "404" in result_dict["error"] or "未找到" in result_dict["error"]

    @pytest.mark.asyncio
    async def test__search_word_impl_retries_on_retryable_http_status(self, sample_api_response):
        """对上游 5xx（可重试）应按策略重试（指数退避+抖动），成功后返回正常结果。"""
        with (
            patch("src.server.NaverClient") as mock_client_class,
            patch("src.server.asyncio.sleep", new=AsyncMock()) as mock_sleep,
            patch("src.server._try_consume_retry_token", return_value=True) as mock_consume_retry,
            patch.object(config, "UPSTREAM_RETRY_MAX_ATTEMPTS", 2),
        ):
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_response.headers = {}
            upstream_err = httpx.HTTPStatusError(
                "503 Service Unavailable",
                request=MagicMock(),
                response=mock_response,
            )
            # 第一次 503，第二次成功
            mock_client.search.side_effect = [upstream_err, sample_api_response]
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _search_word_impl("테스트", "ko-zh")
            payload = json.loads(result)

            assert payload["success"] is True
            assert mock_client.search.await_count == 2
            mock_sleep.assert_awaited_once()
            mock_consume_retry.assert_called_once()

    @pytest.mark.asyncio
    async def test__search_word_impl_does_not_retry_on_404(self):
        """对 404（不可重试）不应重试。"""
        with (
            patch("src.server.NaverClient") as mock_client_class,
            patch("src.server.asyncio.sleep", new=AsyncMock()) as mock_sleep,
            patch("src.server._try_consume_retry_token", return_value=True) as mock_consume_retry,
            patch.object(config, "UPSTREAM_RETRY_MAX_ATTEMPTS", 2),
        ):
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.headers = {}
            mock_client.search.side_effect = httpx.HTTPStatusError(
                "404 Not Found",
                request=MagicMock(),
                response=mock_response,
            )
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _search_word_impl("테스트", "ko-zh")
            payload = json.loads(result)

            assert payload["success"] is False
            assert payload["error_type"] == "http_error"
            assert mock_client.search.await_count == 1
            mock_sleep.assert_not_called()
            mock_consume_retry.assert_not_called()

    @pytest.mark.asyncio
    async def test__search_word_impl_upstream_429_error_type(self):
        """上游 429 应分类为 upstream_rate_limit。"""
        with (
            patch("src.server.NaverClient") as mock_client_class,
            patch.object(config, "UPSTREAM_RETRY_MAX_ATTEMPTS", 1),
        ):
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

            result = await _search_word_impl("테스트", "ko-zh")
            payload = json.loads(result)
            assert payload["success"] is False
            assert payload["error_type"] == "upstream_rate_limit"

    @pytest.mark.asyncio
    async def test__search_word_impl_upstream_5xx_error_type(self):
        """上游 5xx 应分类为 upstream_server_error。"""
        with (
            patch("src.server.NaverClient") as mock_client_class,
            patch.object(config, "UPSTREAM_RETRY_MAX_ATTEMPTS", 1),
        ):
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 502
            mock_response.headers = {}
            mock_client.search.side_effect = httpx.HTTPStatusError(
                "502 Bad Gateway",
                request=MagicMock(),
                response=mock_response,
            )
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _search_word_impl("테스트", "ko-zh")
            payload = json.loads(result)
            assert payload["success"] is False
            assert payload["error_type"] == "upstream_server_error"
    
    @pytest.mark.asyncio
    async def test__search_word_impl_network_error(self):
        """Test handling of network errors."""
        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search.side_effect = httpx.ConnectError("Connection failed")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            result = await _search_word_impl("테스트")
            result_dict = json.loads(result)
            
            assert result_dict["success"] is False
            assert result_dict["error_type"] == "network_error"
            assert "网络" in result_dict["error"]
    
    @pytest.mark.asyncio
    async def test__search_word_impl_parse_error(self):
        """Test handling of parse errors."""
        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search.side_effect = KeyError("missing_key")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            result = await _search_word_impl("테스트")
            result_dict = json.loads(result)
            
            assert result_dict["success"] is False
            assert result_dict["error_type"] == "parse_error"
            assert "解析" in result_dict["error"]
    
    @pytest.mark.asyncio
    async def test__search_word_impl_unknown_error(self):
        """Test handling of unknown errors."""
        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search.side_effect = RuntimeError("Unexpected error")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            result = await _search_word_impl("테스트")
            result_dict = json.loads(result)
            
            assert result_dict["success"] is False
            assert result_dict["error_type"] == "unknown"

    @pytest.mark.asyncio
    async def test__search_word_impl_normalizes_word_and_uses_cache(self, sample_api_response):
        """Test that server normalizes word and cache key is based on normalized word."""
        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search.return_value = sample_api_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            # First call: cache miss -> upstream
            result1 = await _search_word_impl("  안녕하세요  ", "ko-zh")
            data1 = json.loads(result1)
            assert data1["success"] is True
            assert data1["word"] == "안녕하세요"

            # Second call: should hit cache (no extra upstream call)
            result2 = await _search_word_impl("안녕하세요", "ko-zh")
            data2 = json.loads(result2)
            assert data2["success"] is True
            assert data2["word"] == "안녕하세요"

            mock_client.search.assert_awaited_once_with("안녕하세요", "ko-zh")


class TestBatchSearchWordsTool:
    """Tests for the batch_search_words MCP tool."""

    def setup_method(self):
        cache.clear()
        metrics.reset()
        rate_limiter.reset()

    @pytest.mark.asyncio
    async def test_batch_search_words_partial_success_and_dedup(self, sample_api_response):
        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search.return_value = sample_api_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _batch_search_words_impl(
                words=["  안녕하세요  ", "", "안녕하세요"],
                dict_type="ko-zh",
            )
            payload = json.loads(result)

            assert payload["success"] is False
            assert payload["partial_success"] is True
            assert payload["count"] == 3
            assert payload["success_count"] == 2
            assert payload["fail_count"] == 1

            # 去重 miss：只对 "안녕하세요" 访问一次
            mock_client.search.assert_awaited_once_with("안녕하세요", "ko-zh")

            assert payload["results"][1]["success"] is False
            assert payload["results"][1]["error_type"] == "validation"

            # 去重回填标记：第 3 个词复用第 1 个词的上游结果
            assert payload["results"][0]["deduped"] is False
            assert payload["results"][0]["source_word"] == "안녕하세요"
            assert payload["results"][2]["deduped"] is True
            assert payload["results"][2]["source_word"] == "안녕하세요"

    @pytest.mark.asyncio
    async def test_batch_search_words_rate_limit_only_affects_misses(self):
        # 预置一个缓存命中项
        cached = json.dumps(
            {
                "success": True,
                "word": "안녕하세요",
                "dict_type": "ko-zh",
                "count": 0,
                "results": [],
            },
            ensure_ascii=False,
        )
        cache.set("안녕하세요", "ko-zh", cached)

        with patch("src.server.rate_limiter.consume", return_value=False), patch(
            "src.server.rate_limiter.get_remaining_tokens", return_value=0
        ):
            result = await _batch_search_words_impl(
                words=["안녕하세요", "학교"],
                dict_type="ko-zh",
            )
            payload = json.loads(result)

            assert payload["count"] == 2
            assert payload["results"][0]["success"] is True  # 缓存命中不受限流影响
            assert payload["results"][1]["success"] is False
            assert payload["results"][1]["error_type"] == "rate_limit"

    @pytest.mark.asyncio
    async def test_batch_search_words_return_cached_json(self):
        cached = json.dumps(
            {
                "success": True,
                "word": "안녕하세요",
                "dict_type": "ko-zh",
                "count": 0,
                "results": [],
            },
            ensure_ascii=False,
        )
        cache.set("안녕하세요", "ko-zh", cached)

        result = await _batch_search_words_impl(
            words=["안녕하세요"],
            dict_type="ko-zh",
            return_cached_json=True,
        )
        payload = json.loads(result)

        assert payload["success"] is True
        assert payload["results"][0]["from_cache"] is True
        assert payload["results"][0]["cached_json"] == cached
        assert "results" not in payload["results"][0]  # 避免反序列化与拼装

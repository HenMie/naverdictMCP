"""Tests for MCP server module."""

import pytest
import json
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from src.server import _search_word_impl
from src.client import ValidationError
from src.cache import cache
from src.metrics import metrics


class TestSearchWordTool:
    """Tests for the _search_word_impl MCP tool."""
    
    def setup_method(self):
        """Clear cache and metrics before each test."""
        cache.clear()
        metrics.reset()
    
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

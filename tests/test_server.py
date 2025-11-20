"""Tests for MCP server module."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.server import _search_word_impl


class TestSearchWordTool:
    """Tests for the _search_word_impl MCP tool."""
    
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
            
            assert "未找到相关结果" in result
    
    @pytest.mark.asyncio
    async def test__search_word_impl_client_error(self):
        """Test handling of client errors."""
        with patch("src.server.NaverClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search.side_effect = Exception("API Error")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            with pytest.raises(Exception, match="API Error"):
                await _search_word_impl("테스트")

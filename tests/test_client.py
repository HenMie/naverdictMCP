"""Tests for HTTP client module."""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from src.client import NaverClient, DICT_CODE_MAP


class TestNaverClient:
    """Tests for NaverClient class."""
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager initialization and cleanup."""
        async with NaverClient() as client:
            assert client.client is not None
            assert isinstance(client.client, httpx.AsyncClient)
        
        # Client should be closed after exiting context
        # We can't directly check if it's closed, but we verified it was created
    
    @pytest.mark.asyncio
    async def test_search_without_context_manager(self):
        """Test that search raises error without context manager."""
        client = NaverClient()
        
        with pytest.raises(RuntimeError, match="Client not initialized"):
            await client.search("테스트")
    
    @pytest.mark.asyncio
    async def test_search_ko_zh_success(self):
        """Test successful Korean-Chinese dictionary search."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"searchResultMap": {}}
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            async with NaverClient() as client:
                result = await client.search("안녕", "ko-zh")
            
            # Verify the request was made correctly
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            
            # Check URL
            assert "kozh/search" in call_args[0][0]
            
            # Check params
            params = call_args[1]["params"]
            assert params["query"] == "안녕"
            assert params["lang"] == "zh_CN"
            assert params["m"] == "mobile"
    
    @pytest.mark.asyncio
    async def test_search_ko_en_success(self):
        """Test successful Korean-English dictionary search."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"searchResultMap": {}}
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            async with NaverClient() as client:
                result = await client.search("학교", "ko-en")
            
            # Verify the request was made correctly
            call_args = mock_get.call_args
            
            # Check URL
            assert "koen/search" in call_args[0][0]
            
            # Check params
            params = call_args[1]["params"]
            assert params["query"] == "학교"
            assert params["lang"] == "en"
    
    @pytest.mark.asyncio
    async def test_search_http_error(self):
        """Test handling of HTTP errors."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.HTTPStatusError(
                "404 Not Found",
                request=MagicMock(),
                response=MagicMock(status_code=404)
            )
            
            async with NaverClient() as client:
                with pytest.raises(httpx.HTTPStatusError):
                    await client.search("테스트")
    
    @pytest.mark.asyncio
    async def test_search_network_error(self):
        """Test handling of network errors."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection failed")
            
            async with NaverClient() as client:
                with pytest.raises(httpx.ConnectError):
                    await client.search("테스트")
    
    @pytest.mark.asyncio
    async def test_client_uses_config(self):
        """Test that client uses configuration values."""
        from src.config import config
        
        async with NaverClient() as client:
            assert client.base_url == config.NAVER_BASE_URL
            assert client.client.timeout.read == config.HTTP_TIMEOUT
    
    def test_dict_code_mapping(self):
        """Test dictionary type to code mapping."""
        assert DICT_CODE_MAP["ko-zh"] == ("kozh", "zh_CN")
        assert DICT_CODE_MAP["ko-en"] == ("koen", "en")

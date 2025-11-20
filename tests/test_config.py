"""Tests for configuration module."""

import pytest
import os
from unittest.mock import patch
from src.config import Config


class TestConfig:
    """Tests for Config class."""
    
    def test_default_values(self):
        """Test that default configuration values are set correctly."""
        config = Config()
        
        assert config.SERVER_HOST == "127.0.0.1"
        assert config.SERVER_PORT == 8000
        assert config.HTTP_TIMEOUT == 30.0
        assert config.LOG_LEVEL == "INFO"
        assert config.NAVER_BASE_URL == "https://korean.dict.naver.com/api3"
    
    def test_get_server_address(self):
        """Test server address generation."""
        config = Config()
        address = config.get_server_address()
        
        assert address == f"http://{config.SERVER_HOST}:{config.SERVER_PORT}"
        assert "http://127.0.0.1:8000" == address
    
    @patch.dict(os.environ, {
        "SERVER_HOST": "127.0.0.1",
        "SERVER_PORT": "9000",
        "HTTP_TIMEOUT": "60.0",
        "LOG_LEVEL": "DEBUG"
    })
    def test_environment_variable_override(self):
        """Test that environment variables override defaults."""
        # Need to reload the module to pick up new env vars
        from importlib import reload
        import src.config as config_module
        reload(config_module)
        
        config = config_module.Config()
        
        assert config.SERVER_HOST == "127.0.0.1"
        assert config.SERVER_PORT == 9000
        assert config.HTTP_TIMEOUT == 60.0
        assert config.LOG_LEVEL == "DEBUG"

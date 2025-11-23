"""Tests for configuration module."""

import pytest
import os
from unittest.mock import patch
from src.config import Config, ConfigError


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


class TestConfigValidation:
    """Tests for configuration validation."""
    
    def test_invalid_port_too_low(self):
        """Test that port number validation catches values too low."""
        config = Config()
        config.SERVER_PORT = 0
        
        with pytest.raises(ConfigError):
            config.validate()
    
    def test_invalid_port_too_high(self):
        """Test that port number validation catches values too high."""
        config = Config()
        config.SERVER_PORT = 70000
        
        with pytest.raises(ConfigError):
            config.validate()
    
    def test_valid_port_range(self):
        """Test that valid port numbers pass validation."""
        config = Config()
        
        # Test boundary values
        config.SERVER_PORT = 1
        config.validate()  # Should not raise
        
        config.SERVER_PORT = 65535
        config.validate()  # Should not raise
        
        config.SERVER_PORT = 8000
        config.validate()  # Should not raise
    
    def test_invalid_timeout_zero(self):
        """Test that zero timeout is rejected."""
        config = Config()
        config.HTTP_TIMEOUT = 0
        
        with pytest.raises(ConfigError):
            config.validate()
    
    def test_invalid_timeout_negative(self):
        """Test that negative timeout is rejected."""
        config = Config()
        config.HTTP_TIMEOUT = -10
        
        with pytest.raises(ConfigError):
            config.validate()
    
    def test_timeout_warning_too_long(self):
        """Test that very long timeouts trigger a warning."""
        config = Config()
        config.HTTP_TIMEOUT = 400
        
        with pytest.raises(ConfigError):
            config.validate()
    
    def test_valid_timeout_range(self):
        """Test that reasonable timeout values pass validation."""
        config = Config()
        
        config.HTTP_TIMEOUT = 1.0
        config.validate()  # Should not raise
        
        config.HTTP_TIMEOUT = 30.0
        config.validate()  # Should not raise
        
        config.HTTP_TIMEOUT = 300.0
        config.validate()  # Should not raise
    
    def test_invalid_log_level(self):
        """Test that invalid log levels are rejected."""
        config = Config()
        config.LOG_LEVEL = "INVALID"
        
        with pytest.raises(ConfigError):
            config.validate()
    
    def test_valid_log_levels(self):
        """Test that all valid log levels pass validation."""
        config = Config()
        
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config.LOG_LEVEL = level
            config.validate()  # Should not raise
    
    def test_invalid_url_format(self):
        """Test that invalid URL formats are rejected."""
        config = Config()
        config.NAVER_BASE_URL = "not-a-valid-url"
        
        with pytest.raises(ConfigError):
            config.validate()
    
    def test_valid_url_formats(self):
        """Test that valid URL formats pass validation."""
        config = Config()
        
        config.NAVER_BASE_URL = "http://example.com"
        config.validate()  # Should not raise
        
        config.NAVER_BASE_URL = "https://example.com/api"
        config.validate()  # Should not raise

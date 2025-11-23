"""Tests for logger module."""

import pytest
import logging
from src.logger import setup_logger


class TestLogger:
    """Tests for logger setup."""
    
    def test_setup_logger_default(self):
        """Test logger setup with default parameters."""
        logger = setup_logger("test_logger_1", "INFO")
        
        assert logger is not None
        assert logger.name == "test_logger_1"
        assert logger.level == logging.INFO
        assert len(logger.handlers) > 0
    
    def test_setup_logger_debug_level(self):
        """Test logger setup with DEBUG level."""
        logger = setup_logger("test_logger_2", "DEBUG")
        
        assert logger.level == logging.DEBUG
    
    def test_setup_logger_error_level(self):
        """Test logger setup with ERROR level."""
        logger = setup_logger("test_logger_3", "ERROR")
        
        assert logger.level == logging.ERROR
    
    def test_setup_logger_no_duplicate_handlers(self):
        """Test that handlers are not duplicated."""
        logger = setup_logger("test_logger_4", "INFO")
        handler_count = len(logger.handlers)
        
        # Call again with same name
        logger2 = setup_logger("test_logger_4", "INFO")
        
        # Should return the same logger without adding more handlers
        assert logger is logger2
        assert len(logger2.handlers) == handler_count
    
    def test_logger_output(self, caplog):
        """Test that logger actually outputs messages."""
        logger = setup_logger("test_logger_5", "INFO")
        
        with caplog.at_level(logging.INFO, logger="test_logger_5"):
            logger.info("Test message")
        
        assert "Test message" in caplog.text


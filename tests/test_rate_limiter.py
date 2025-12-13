"""Tests for rate limiter module."""

import pytest
import time
from src.rate_limiter import RateLimiter


class TestRateLimiter:
    """Tests for RateLimiter class."""
    
    def test_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(requests_per_minute=60)
        
        assert limiter.requests_per_minute == 60
        assert limiter.refill_rate == 1.0  # 60 / 60
    
    def test_first_consume_allowed(self):
        """Test that first consume is always allowed when bucket is full."""
        limiter = RateLimiter(requests_per_minute=60)

        assert limiter.consume(1) is True
    
    def test_rate_limit_enforcement(self):
        """Test that rate limit is enforced."""
        limiter = RateLimiter(requests_per_minute=2)  # Very low limit for testing
        
        # First 2 tokens should be allowed
        assert limiter.consume(1) is True
        assert limiter.consume(1) is True
        
        # Third should be denied (no time passed)
        assert limiter.consume(1) is False
    
    def test_consume_multiple_tokens(self):
        """Test consuming multiple tokens in one call."""
        limiter = RateLimiter(requests_per_minute=5)

        assert limiter.consume(3) is True
        assert limiter.get_remaining_tokens() == 2

        # Not enough tokens left
        assert limiter.consume(3) is False
    
    def test_token_refill_over_time(self):
        """Test that tokens refill over time."""
        limiter = RateLimiter(requests_per_minute=60)  # 1 token per second
        
        # Use up all tokens
        assert limiter.consume(60) is True
        assert limiter.consume(1) is False
        
        # Wait for token to refill (need at least 1 second)
        time.sleep(1.1)
        
        # Should have a new token now
        assert limiter.consume(1) is True
    
    def test_get_remaining_tokens(self):
        """Test getting remaining tokens."""
        limiter = RateLimiter(requests_per_minute=10)
        
        # New limiter should have full tokens
        assert limiter.get_remaining_tokens() == 10
        
        # After one consume
        limiter.consume(1)
        assert limiter.get_remaining_tokens() == 9
        
        # After two more consumes
        limiter.consume(1)
        limiter.consume(1)
        assert limiter.get_remaining_tokens() == 7
    
    def test_reset(self):
        """Test resetting rate limiter state."""
        limiter = RateLimiter(requests_per_minute=2)

        assert limiter.consume(2) is True
        assert limiter.consume(1) is False

        limiter.reset()
        assert limiter.get_remaining_tokens() == 2
    
    def test_max_tokens_cap(self):
        """Test that tokens don't exceed maximum."""
        limiter = RateLimiter(requests_per_minute=5)
        
        limiter.consume(1)
        
        # Wait a very long time
        time.sleep(2)
        
        # Should have at most 5 tokens (the max)
        remaining = limiter.get_remaining_tokens()
        assert remaining <= 5




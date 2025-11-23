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
    
    def test_first_request_allowed(self):
        """Test that first request is always allowed."""
        limiter = RateLimiter(requests_per_minute=60)
        
        assert limiter.is_allowed("client1") is True
    
    def test_rate_limit_enforcement(self):
        """Test that rate limit is enforced."""
        limiter = RateLimiter(requests_per_minute=2)  # Very low limit for testing
        
        # First 2 requests should be allowed
        assert limiter.is_allowed("client2") is True
        assert limiter.is_allowed("client2") is True
        
        # Third request should be denied (no time passed)
        assert limiter.is_allowed("client2") is False
    
    def test_different_clients_independent(self):
        """Test that different clients have independent limits."""
        limiter = RateLimiter(requests_per_minute=1)
        
        # Each client should be allowed one request
        assert limiter.is_allowed("client3") is True
        assert limiter.is_allowed("client4") is True
        
        # Second request from each should be denied
        assert limiter.is_allowed("client3") is False
        assert limiter.is_allowed("client4") is False
    
    def test_token_refill_over_time(self):
        """Test that tokens refill over time."""
        limiter = RateLimiter(requests_per_minute=60)  # 1 token per second
        
        # Use up one token
        assert limiter.is_allowed("client5") is True
        
        # Wait for token to refill (need at least 1 second)
        time.sleep(1.1)
        
        # Should have a new token now
        assert limiter.is_allowed("client5") is True
    
    def test_get_remaining_tokens(self):
        """Test getting remaining tokens for a client."""
        limiter = RateLimiter(requests_per_minute=10)
        
        # New client should have full tokens
        assert limiter.get_remaining_tokens("client6") == 10
        
        # After one request
        limiter.is_allowed("client6")
        assert limiter.get_remaining_tokens("client6") == 9
        
        # After two more requests
        limiter.is_allowed("client6")
        limiter.is_allowed("client6")
        assert limiter.get_remaining_tokens("client6") == 7
    
    def test_reset_client(self):
        """Test resetting rate limit for a client."""
        limiter = RateLimiter(requests_per_minute=2)
        
        # Use up tokens
        limiter.is_allowed("client7")
        limiter.is_allowed("client7")
        assert limiter.is_allowed("client7") is False
        
        # Reset the client
        limiter.reset_client("client7")
        
        # Should be allowed again
        assert limiter.is_allowed("client7") is True
    
    def test_clear_all(self):
        """Test clearing all rate limit data."""
        limiter = RateLimiter(requests_per_minute=1)
        
        # Use tokens for multiple clients
        limiter.is_allowed("client8")
        limiter.is_allowed("client9")
        
        # Clear all data
        limiter.clear_all()
        
        # All clients should have full tokens again
        assert limiter.get_remaining_tokens("client8") == 1
        assert limiter.get_remaining_tokens("client9") == 1
    
    def test_max_tokens_cap(self):
        """Test that tokens don't exceed maximum."""
        limiter = RateLimiter(requests_per_minute=5)
        
        # New client
        limiter.is_allowed("client10")
        
        # Wait a very long time
        time.sleep(2)
        
        # Should have at most 5 tokens (the max)
        remaining = limiter.get_remaining_tokens("client10")
        assert remaining <= 5


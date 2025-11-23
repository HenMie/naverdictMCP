"""Tests for metrics module."""

import pytest
import time
from src.metrics import Metrics


class TestMetrics:
    """Test cases for Metrics."""
    
    def test_metrics_initialization(self):
        """Test metrics initialization."""
        metrics = Metrics()
        
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.cache_hits == 0
        assert metrics.cache_misses == 0
        assert metrics.total_latency == 0.0
    
    def test_record_successful_request(self):
        """Test recording successful request."""
        metrics = Metrics()
        
        metrics.record_request(success=True, latency=0.5, endpoint="search")
        
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 0
        assert metrics.total_latency == 0.5
    
    def test_record_failed_request(self):
        """Test recording failed request."""
        metrics = Metrics()
        
        metrics.record_request(success=False, latency=1.0, endpoint="search")
        
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 1
        assert metrics.total_latency == 1.0
    
    def test_record_multiple_requests(self):
        """Test recording multiple requests."""
        metrics = Metrics()
        
        metrics.record_request(success=True, latency=0.3, endpoint="search")
        metrics.record_request(success=True, latency=0.4, endpoint="search")
        metrics.record_request(success=False, latency=0.5, endpoint="search")
        
        assert metrics.total_requests == 3
        assert metrics.successful_requests == 2
        assert metrics.failed_requests == 1
        assert metrics.total_latency == 1.2
    
    def test_record_cache_hits_and_misses(self):
        """Test recording cache hits and misses."""
        metrics = Metrics()
        
        metrics.record_cache_hit()
        metrics.record_cache_hit()
        metrics.record_cache_miss()
        
        assert metrics.cache_hits == 2
        assert metrics.cache_misses == 1
    
    def test_record_errors(self):
        """Test recording errors by type."""
        metrics = Metrics()
        
        metrics.record_error("validation")
        metrics.record_error("timeout")
        metrics.record_error("validation")
        
        assert metrics.error_counts["validation"] == 2
        assert metrics.error_counts["timeout"] == 1
    
    def test_get_stats_basic(self):
        """Test getting basic statistics."""
        metrics = Metrics()
        
        metrics.record_request(success=True, latency=0.5, endpoint="search")
        metrics.record_request(success=False, latency=0.3, endpoint="search")
        metrics.record_cache_hit()
        metrics.record_cache_miss()
        
        stats = metrics.get_stats()
        
        assert stats["total_requests"] == 2
        assert stats["successful_requests"] == 1
        assert stats["failed_requests"] == 1
        assert stats["success_rate"] == 0.5
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1
        assert stats["cache_hit_rate"] == 0.5
        assert stats["average_latency"] == 0.4  # (0.5 + 0.3) / 2
    
    def test_get_stats_no_requests(self):
        """Test statistics with no requests."""
        metrics = Metrics()
        
        stats = metrics.get_stats()
        
        assert stats["total_requests"] == 0
        assert stats["success_rate"] == 0
        assert stats["cache_hit_rate"] == 0
        assert stats["average_latency"] == 0
    
    def test_endpoint_stats(self):
        """Test per-endpoint statistics."""
        metrics = Metrics()
        
        metrics.record_request(success=True, latency=0.1, endpoint="search")
        metrics.record_request(success=True, latency=0.2, endpoint="search")
        metrics.record_request(success=True, latency=0.5, endpoint="batch_search")
        
        stats = metrics.get_stats()
        
        assert "search" in stats["endpoint_stats"]
        assert "batch_search" in stats["endpoint_stats"]
        
        search_stats = stats["endpoint_stats"]["search"]
        assert search_stats["count"] == 2
        assert abs(search_stats["avg"] - 0.15) < 0.001  # Allow for float precision
        assert search_stats["min"] == 0.1
        assert search_stats["max"] == 0.2
    
    def test_percentile_calculation(self):
        """Test latency percentile calculations."""
        metrics = Metrics()
        
        # Add 100 requests with varying latencies
        for i in range(100):
            metrics.record_request(success=True, latency=i/100, endpoint="search")
        
        stats = metrics.get_stats()
        search_stats = stats["endpoint_stats"]["search"]
        
        assert search_stats["count"] == 100
        assert search_stats["p50"] < search_stats["p95"]
        assert search_stats["p95"] < search_stats["p99"]
        assert search_stats["p99"] <= search_stats["max"]
    
    def test_metrics_reset(self):
        """Test resetting all metrics."""
        metrics = Metrics()
        
        metrics.record_request(success=True, latency=0.5, endpoint="search")
        metrics.record_cache_hit()
        metrics.record_error("timeout")
        
        assert metrics.total_requests > 0
        
        metrics.reset()
        
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.cache_hits == 0
        assert metrics.cache_misses == 0
        assert metrics.total_latency == 0.0
        assert len(metrics.request_times) == 0
        assert len(metrics.error_counts) == 0
    
    def test_request_times_limit(self):
        """Test request times list doesn't grow unbounded."""
        metrics = Metrics()
        
        # Record more than 100 requests
        for i in range(150):
            metrics.record_request(success=True, latency=0.1, endpoint="search")
        
        # Should keep only last 100
        assert len(metrics.request_times["search"]) == 100
    
    def test_multiple_endpoints(self):
        """Test tracking metrics for multiple endpoints."""
        metrics = Metrics()
        
        metrics.record_request(success=True, latency=0.1, endpoint="search")
        metrics.record_request(success=True, latency=0.2, endpoint="batch_search")
        metrics.record_request(success=True, latency=0.3, endpoint="health_check")
        
        stats = metrics.get_stats()
        
        assert len(stats["endpoint_stats"]) == 3
        assert "search" in stats["endpoint_stats"]
        assert "batch_search" in stats["endpoint_stats"]
        assert "health_check" in stats["endpoint_stats"]
    
    def test_error_counting(self):
        """Test error counting by type."""
        metrics = Metrics()
        
        metrics.record_error("validation")
        metrics.record_error("validation")
        metrics.record_error("timeout")
        metrics.record_error("http_error")
        metrics.record_error("http_error")
        metrics.record_error("http_error")
        
        stats = metrics.get_stats()
        
        assert stats["error_counts"]["validation"] == 2
        assert stats["error_counts"]["timeout"] == 1
        assert stats["error_counts"]["http_error"] == 3
    
    def test_high_precision_latency(self):
        """Test metrics handle high precision latency values."""
        metrics = Metrics()
        
        # Very small latency values
        metrics.record_request(success=True, latency=0.000123, endpoint="cache_hit")
        metrics.record_request(success=True, latency=0.000456, endpoint="cache_hit")
        
        stats = metrics.get_stats()
        cache_stats = stats["endpoint_stats"]["cache_hit"]
        
        assert cache_stats["avg"] < 0.001  # Sub-millisecond
        assert cache_stats["min"] > 0


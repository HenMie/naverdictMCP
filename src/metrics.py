"""Application metrics for monitoring and performance tracking."""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Any
from .logger import logger


@dataclass
class Metrics:
    """Application metrics collector."""
    
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_latency: float = 0.0
    request_times: Dict[str, List[float]] = field(default_factory=dict)
    error_counts: Dict[str, int] = field(default_factory=dict)
    
    def record_request(self, success: bool, latency: float, endpoint: str = "search") -> None:
        """
        Record a request with its result and latency.
        
        Args:
            success: Whether the request succeeded
            latency: Request latency in seconds
            endpoint: The endpoint name
        """
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
        
        self.total_latency += latency
        
        if endpoint not in self.request_times:
            self.request_times[endpoint] = []
        self.request_times[endpoint].append(latency)
        
        # Keep only last 100 request times per endpoint to prevent memory growth
        if len(self.request_times[endpoint]) > 100:
            self.request_times[endpoint] = self.request_times[endpoint][-100:]
        
        logger.debug(f"记录请求: endpoint={endpoint}, success={success}, latency={latency:.3f}s")
    
    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        self.cache_hits += 1
        logger.debug(f"缓存命中记录: 总命中={self.cache_hits}")
    
    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        self.cache_misses += 1
        logger.debug(f"缓存未命中记录: 总未命中={self.cache_misses}")
    
    def record_error(self, error_type: str) -> None:
        """
        Record an error by type.
        
        Args:
            error_type: Type of error (validation, timeout, http_error, etc.)
        """
        if error_type not in self.error_counts:
            self.error_counts[error_type] = 0
        self.error_counts[error_type] += 1
        logger.debug(f"记录错误: type={error_type}, count={self.error_counts[error_type]}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current statistics.
        
        Returns:
            Dictionary containing all metrics
        """
        avg_latency = (
            self.total_latency / self.total_requests 
            if self.total_requests > 0 else 0
        )
        
        cache_hit_rate = (
            self.cache_hits / (self.cache_hits + self.cache_misses)
            if (self.cache_hits + self.cache_misses) > 0 else 0
        )
        
        success_rate = (
            self.successful_requests / self.total_requests
            if self.total_requests > 0 else 0
        )
        
        # Calculate percentiles for each endpoint
        endpoint_stats = {}
        for endpoint, times in self.request_times.items():
            if times:
                sorted_times = sorted(times)
                n = len(sorted_times)
                endpoint_stats[endpoint] = {
                    "count": n,
                    "avg": sum(sorted_times) / n,
                    "min": sorted_times[0],
                    "max": sorted_times[-1],
                    "p50": sorted_times[n // 2],
                    "p95": sorted_times[int(n * 0.95)] if n > 1 else sorted_times[0],
                    "p99": sorted_times[int(n * 0.99)] if n > 1 else sorted_times[0],
                }
        
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": success_rate,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": cache_hit_rate,
            "average_latency": avg_latency,
            "endpoint_stats": endpoint_stats,
            "error_counts": self.error_counts,
        }
    
    def reset(self) -> None:
        """Reset all metrics to zero."""
        logger.info("重置指标统计")
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_latency = 0.0
        self.request_times.clear()
        self.error_counts.clear()


# Global metrics instance
metrics = Metrics()



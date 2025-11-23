"""Rate limiting for API endpoints."""

import time
from typing import Dict, Tuple
from collections import defaultdict
from .logger import logger


class RateLimiter:
    """
    Token bucket rate limiter for API endpoints.
    
    Uses token bucket algorithm to limit requests per time window.
    Each client gets a bucket with N tokens that refill over time.
    """
    
    def __init__(self, requests_per_minute: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute per client
        """
        self.requests_per_minute = requests_per_minute
        # 格式: {client_id: (last_check_time, available_tokens)}
        self.buckets: Dict[str, Tuple[float, int]] = defaultdict(
            lambda: (time.time(), requests_per_minute)
        )
        self.refill_rate = requests_per_minute / 60.0  # tokens per second
        
        logger.info(f"限流器初始化: {requests_per_minute} 请求/分钟")
    
    def is_allowed(self, client_id: str) -> bool:
        """
        Check if request is allowed for the client.
        
        Args:
            client_id: Client identifier (e.g., IP address or user ID)
            
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        current_time = time.time()
        last_check, tokens = self.buckets[client_id]
        
        # 计算应该补充的令牌数
        time_passed = current_time - last_check
        new_tokens = min(
            self.requests_per_minute,
            tokens + int(time_passed * self.refill_rate)
        )
        
        if new_tokens > 0:
            # 有可用令牌，允许请求
            self.buckets[client_id] = (current_time, new_tokens - 1)
            logger.debug(f"限流检查通过: client={client_id}, tokens={new_tokens-1}")
            return True
        else:
            # 没有可用令牌，拒绝请求
            self.buckets[client_id] = (current_time, 0)
            logger.warning(f"限流触发: client={client_id} 超出速率限制")
            return False
    
    def get_remaining_tokens(self, client_id: str) -> int:
        """
        Get remaining tokens for a client.
        
        Args:
            client_id: Client identifier
            
        Returns:
            Number of remaining tokens
        """
        if client_id not in self.buckets:
            return self.requests_per_minute
        
        current_time = time.time()
        last_check, tokens = self.buckets[client_id]
        
        # 计算当前可用令牌数
        time_passed = current_time - last_check
        new_tokens = min(
            self.requests_per_minute,
            tokens + int(time_passed * self.refill_rate)
        )
        
        return new_tokens
    
    def reset_client(self, client_id: str) -> None:
        """
        Reset rate limit for a specific client.
        
        Args:
            client_id: Client identifier
        """
        if client_id in self.buckets:
            del self.buckets[client_id]
            logger.info(f"重置限流: client={client_id}")
    
    def clear_all(self) -> None:
        """Clear all rate limit data."""
        self.buckets.clear()
        logger.info("清空所有限流数据")


# 全局限流器实例
# 默认每分钟 60 个请求（平均每秒 1 个）
rate_limiter = RateLimiter(requests_per_minute=60)


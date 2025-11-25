"""API 限流模块。

基于令牌桶算法实现请求限流，防止 API 滥用。
"""

import time
from collections import defaultdict
from typing import Dict, Tuple

from .logger import logger


class RateLimiter:
    """
    基于令牌桶算法的限流器。
    
    使用令牌桶算法限制每个时间窗口内的请求数。
    每个客户端有一个独立的令牌桶，令牌会随时间自动补充。
    
    算法说明:
        - 每个客户端初始有 N 个令牌
        - 每次请求消耗 1 个令牌
        - 令牌以固定速率补充（每秒 refill_rate 个）
        - 令牌数量上限为 requests_per_minute
    """
    
    def __init__(self, requests_per_minute: int = 60) -> None:
        """
        初始化限流器。
        
        Args:
            requests_per_minute: 每分钟最大请求数（每个客户端）
        """
        self.requests_per_minute = requests_per_minute
        # 格式: {client_id: (last_check_time, available_tokens)}
        self.buckets: Dict[str, Tuple[float, int]] = defaultdict(
            lambda: (time.time(), requests_per_minute)
        )
        self.refill_rate = requests_per_minute / 60.0  # 每秒补充的令牌数
        
        logger.info(f"限流器初始化: {requests_per_minute} 请求/分钟")
    
    def is_allowed(self, client_id: str) -> bool:
        """
        检查该客户端的请求是否被允许。
        
        Args:
            client_id: 客户端标识符（如 IP 地址或用户 ID）
            
        Returns:
            True 表示允许请求，False 表示超过限流
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
        获取客户端的剩余令牌数。
        
        Args:
            client_id: 客户端标识符
            
        Returns:
            剩余令牌数
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
        重置指定客户端的限流状态。
        
        Args:
            client_id: 客户端标识符
        """
        if client_id in self.buckets:
            del self.buckets[client_id]
            logger.info(f"重置限流: client={client_id}")
    
    def clear_all(self) -> None:
        """清空所有限流数据。"""
        self.buckets.clear()
        logger.info("清空所有限流数据")


# 全局限流器实例
# 默认每分钟 60 个请求（平均每秒 1 个）
rate_limiter = RateLimiter(requests_per_minute=60)

"""API 限流模块。

本项目的限流目标是**保护服务器出口 IP**，避免 Naver 对服务器 IP 做频率限制。
因此限流器采用**全局共享**的令牌桶（不区分 client_id）。
"""

import time

from .logger import logger


class RateLimiter:
    """基于令牌桶算法的**全局**限流器（不区分 client_id）。

算法说明（全局共享桶）:
    - 初始有 N 个令牌（N = requests_per_minute）
    - 每次需要访问上游（Naver）时消耗若干令牌（tokens）
    - 令牌以固定速率补充（每秒 requests_per_minute/60 个）
    - 令牌数量上限为 requests_per_minute

注意：这里的“请求/分钟”代表**对上游的请求**配额，而不是本服务的总 QPS。
"""

    def __init__(self, requests_per_minute: int = 60) -> None:
        """
        初始化限流器。

        Args:
            requests_per_minute: 每分钟允许访问上游（Naver）的最大次数
        """
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute 必须大于 0")

        self.requests_per_minute = requests_per_minute
        self.refill_rate = requests_per_minute / 60.0  # 每秒补充的令牌数

        self._last_check: float = time.time()
        self._tokens: float = float(requests_per_minute)

        logger.info(f"限流器初始化(全局): {requests_per_minute} 请求/分钟")

    def _refill(self, now: float) -> None:
        """按时间推进补充令牌（内部方法）。"""
        elapsed = now - self._last_check
        if elapsed <= 0:
            return

        self._tokens = min(self.requests_per_minute, self._tokens + elapsed * self.refill_rate)
        self._last_check = now

    def consume(self, tokens: int = 1) -> bool:
        """消耗指定数量令牌，判断是否允许访问上游。

        Args:
            tokens: 本次需要消耗的令牌数量（>=1）

        Returns:
            True 代表允许（已扣减令牌），False 代表拒绝（不扣减）
        """
        if tokens <= 0:
            raise ValueError("tokens 必须大于 0")

        now = time.time()
        self._refill(now)

        if self._tokens >= tokens:
            self._tokens -= tokens
            logger.debug(f"限流检查通过(全局): consume={tokens}, remaining={int(self._tokens)}")
            return True

        logger.warning(f"限流触发(全局): need={tokens}, remaining={int(self._tokens)}")
        return False

    def get_remaining_tokens(self) -> int:
        """获取当前剩余令牌数（整数）。"""
        now = time.time()
        self._refill(now)
        return int(self._tokens)

    def reset(self) -> None:
        """重置限流器状态为满配额（用于测试或运维）。"""
        self._last_check = time.time()
        self._tokens = float(self.requests_per_minute)
        logger.info("重置限流器(全局)")


# 全局限流器实例（默认每分钟 60 个上游请求）
rate_limiter = RateLimiter(requests_per_minute=60)

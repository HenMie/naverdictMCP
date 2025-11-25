"""应用监控指标模块。

提供请求统计、缓存统计、延迟分析等性能监控功能。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .logger import logger


@dataclass
class Metrics:
    """应用指标收集器。
    
    收集和统计以下指标:
        - 请求统计：总数、成功数、失败数
        - 缓存统计：命中数、未命中数
        - 延迟统计：总延迟、各端点延迟
        - 错误统计：按类型分类的错误计数
    """
    
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
        记录一次请求及其结果和延迟。
        
        Args:
            success: 请求是否成功
            latency: 请求延迟（秒）
            endpoint: 端点名称
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
        
        # 每个端点只保留最近 100 条记录，防止内存增长
        if len(self.request_times[endpoint]) > 100:
            self.request_times[endpoint] = self.request_times[endpoint][-100:]
        
        logger.debug(f"记录请求: endpoint={endpoint}, success={success}, latency={latency:.3f}s")
    
    def record_cache_hit(self) -> None:
        """记录一次缓存命中。"""
        self.cache_hits += 1
        logger.debug(f"缓存命中记录: 总命中={self.cache_hits}")
    
    def record_cache_miss(self) -> None:
        """记录一次缓存未命中。"""
        self.cache_misses += 1
        logger.debug(f"缓存未命中记录: 总未命中={self.cache_misses}")
    
    def record_error(self, error_type: str) -> None:
        """
        按类型记录错误。
        
        Args:
            error_type: 错误类型（validation、timeout、http_error 等）
        """
        if error_type not in self.error_counts:
            self.error_counts[error_type] = 0
        self.error_counts[error_type] += 1
        logger.debug(f"记录错误: type={error_type}, count={self.error_counts[error_type]}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取当前统计信息。
        
        Returns:
            包含所有指标的字典
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
        
        # 计算各端点的百分位延迟
        endpoint_stats: Dict[str, Dict[str, Any]] = {}
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
        """重置所有指标为零。"""
        logger.info("重置指标统计")
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_latency = 0.0
        self.request_times.clear()
        self.error_counts.clear()


# 全局指标实例
metrics = Metrics()

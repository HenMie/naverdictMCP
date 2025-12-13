"""带 TTL 支持的简单 LRU 缓存。

提供 API 响应缓存功能，支持 TTL 过期和 LRU 淘汰策略。
"""

import hashlib
import time
from typing import Any, Dict, Optional, Tuple

from .config import config
from .logger import logger


class TTLCache:
    """带 TTL 过期和 LRU 淘汰策略的缓存。
    
    特性:
        - TTL 过期：缓存项在指定时间后自动过期
        - LRU 淘汰：缓存满时淘汰最少使用的条目
        - 自动清理：获取时自动清理过期数据
    """
    
    def __init__(self, max_size: int = 1000, ttl: int = 3600) -> None:
        """
        初始化缓存。
        
        Args:
            max_size: 最大缓存条目数
            ttl: 过期时间（秒），默认 1 小时
        """
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.max_size = max_size
        self.ttl = ttl
        self.access_times: Dict[str, float] = {}  # LRU 访问时间跟踪
        logger.debug(f"初始化缓存: max_size={max_size}, ttl={ttl}s")
    
    def _make_key(self, word: str, dict_type: str) -> str:
        """
        根据单词和字典类型生成缓存键。
        
        Args:
            word: 搜索词
            dict_type: 字典类型
            
        Returns:
            组合后的 MD5 哈希值
        """
        data = f"{word}:{dict_type}"
        return hashlib.md5(data.encode('utf-8')).hexdigest()
    
    def get(self, word: str, dict_type: str) -> Optional[Any]:
        """
        获取缓存值（如果存在且未过期）。
        
        Args:
            word: 搜索词
            dict_type: 字典类型
            
        Returns:
            缓存值（如果存在且有效），否则返回 None
        """
        key = self._make_key(word, dict_type)
        
        if key in self.cache:
            value, timestamp = self.cache[key]
            current_time = time.time()
            
            # 检查是否过期
            if current_time - timestamp < self.ttl:
                # 更新 LRU 访问时间
                self.access_times[key] = current_time
                logger.debug(f"缓存命中: word='{word}', dict_type={dict_type}")
                return value
            else:
                # 已过期，从缓存中移除
                logger.debug(f"缓存过期: word='{word}', dict_type={dict_type}")
                del self.cache[key]
                if key in self.access_times:
                    del self.access_times[key]
        
        logger.debug(f"缓存未命中: word='{word}', dict_type={dict_type}")
        return None
    
    def set(self, word: str, dict_type: str, value: Any) -> None:
        """
        设置缓存值（带当前时间戳）。
        
        Args:
            word: 搜索词
            dict_type: 字典类型
            value: 要缓存的值
        """
        # 如果缓存已满，淘汰最少使用的条目
        if len(self.cache) >= self.max_size:
            self._evict_lru()
        
        key = self._make_key(word, dict_type)
        current_time = time.time()
        self.cache[key] = (value, current_time)
        self.access_times[key] = current_time
        logger.debug(f"已缓存: word='{word}', dict_type={dict_type}, 当前大小={len(self.cache)}")
    
    def _evict_lru(self) -> None:
        """淘汰最少使用的缓存条目。"""
        if not self.access_times:
            return
        
        # 找到访问时间最早的键
        oldest_key = min(self.access_times.keys(), 
                        key=lambda k: self.access_times[k])
        
        logger.debug(f"LRU 淘汰缓存项: key={oldest_key[:8]}...")
        if oldest_key in self.cache:
            del self.cache[oldest_key]
        if oldest_key in self.access_times:
            del self.access_times[oldest_key]
    
    def clear(self) -> None:
        """清空所有缓存条目。"""
        count = len(self.cache)
        self.cache.clear()
        self.access_times.clear()
        logger.info(f"清空缓存: 已删除 {count} 项")
    
    def size(self) -> int:
        """
        获取当前缓存大小。
        
        Returns:
            缓存中的条目数量
        """
        return len(self.cache)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息。
        
        Returns:
            包含缓存统计的字典
        """
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "ttl": self.ttl,
            "utilization": len(self.cache) / self.max_size if self.max_size > 0 else 0
        }


# 全局缓存实例
# 默认值由 Config 统一管理（支持环境变量配置）
cache = TTLCache(max_size=config.CACHE_MAX_SIZE, ttl=config.CACHE_TTL)

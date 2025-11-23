"""Simple LRU cache for API responses with TTL support."""

import hashlib
import json
import time
from typing import Dict, Any, Optional, Tuple
from .logger import logger


class TTLCache:
    """Time-To-Live cache for API responses with LRU eviction."""
    
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        """
        Initialize cache.
        
        Args:
            max_size: Maximum number of cached items
            ttl: Time to live in seconds (default: 1 hour)
        """
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.max_size = max_size
        self.ttl = ttl
        self.access_times: Dict[str, float] = {}  # For LRU tracking
        logger.debug(f"初始化缓存: max_size={max_size}, ttl={ttl}s")
    
    def _make_key(self, word: str, dict_type: str) -> str:
        """
        Generate cache key from word and dict_type.
        
        Args:
            word: Search word
            dict_type: Dictionary type
            
        Returns:
            MD5 hash of the combination
        """
        data = f"{word}:{dict_type}"
        return hashlib.md5(data.encode('utf-8')).hexdigest()
    
    def get(self, word: str, dict_type: str) -> Optional[Any]:
        """
        Get cached value if exists and not expired.
        
        Args:
            word: Search word
            dict_type: Dictionary type
            
        Returns:
            Cached value if found and valid, None otherwise
        """
        key = self._make_key(word, dict_type)
        
        if key in self.cache:
            value, timestamp = self.cache[key]
            current_time = time.time()
            
            # Check if expired
            if current_time - timestamp < self.ttl:
                # Update access time for LRU
                self.access_times[key] = current_time
                logger.debug(f"缓存命中: word='{word}', dict_type={dict_type}")
                return value
            else:
                # Expired, remove from cache
                logger.debug(f"缓存过期: word='{word}', dict_type={dict_type}")
                del self.cache[key]
                if key in self.access_times:
                    del self.access_times[key]
        
        logger.debug(f"缓存未命中: word='{word}', dict_type={dict_type}")
        return None
    
    def set(self, word: str, dict_type: str, value: Any) -> None:
        """
        Set cache value with current timestamp.
        
        Args:
            word: Search word
            dict_type: Dictionary type
            value: Value to cache
        """
        # Evict oldest item if cache is full
        if len(self.cache) >= self.max_size:
            self._evict_lru()
        
        key = self._make_key(word, dict_type)
        current_time = time.time()
        self.cache[key] = (value, current_time)
        self.access_times[key] = current_time
        logger.debug(f"已缓存: word='{word}', dict_type={dict_type}, 当前大小={len(self.cache)}")
    
    def _evict_lru(self) -> None:
        """Evict the least recently used item from cache."""
        if not self.access_times:
            return
        
        # Find the key with oldest access time
        oldest_key = min(self.access_times.keys(), 
                        key=lambda k: self.access_times[k])
        
        logger.debug(f"LRU 淘汰缓存项: key={oldest_key[:8]}...")
        if oldest_key in self.cache:
            del self.cache[oldest_key]
        if oldest_key in self.access_times:
            del self.access_times[oldest_key]
    
    def clear(self) -> None:
        """Clear all cached items."""
        count = len(self.cache)
        self.cache.clear()
        self.access_times.clear()
        logger.info(f"清空缓存: 已删除 {count} 项")
    
    def size(self) -> int:
        """
        Get current cache size.
        
        Returns:
            Number of items in cache
        """
        return len(self.cache)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "ttl": self.ttl,
            "utilization": len(self.cache) / self.max_size if self.max_size > 0 else 0
        }


# Global cache instance
# 1 hour TTL, max 1000 items
cache = TTLCache(max_size=1000, ttl=3600)


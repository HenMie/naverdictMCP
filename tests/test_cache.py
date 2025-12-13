"""Tests for cache module."""

import pytest
import time
from src.cache import TTLCache


class TestTTLCache:
    """Test cases for TTLCache."""
    
    def test_cache_initialization(self):
        """Test cache initialization with custom parameters."""
        cache = TTLCache(max_size=500, ttl=1800)
        
        assert cache.max_size == 500
        assert cache.ttl == 1800
        assert cache.size() == 0
    
    def test_cache_set_and_get(self):
        """Test basic cache set and get operations."""
        cache = TTLCache(max_size=10, ttl=60)
        
        # Set a value
        cache.set("hello", "ko-zh", {"result": "안녕하세요"})
        
        # Get the value
        result = cache.get("hello", "ko-zh")
        
        assert result is not None
        assert result["result"] == "안녕하세요"
        assert cache.size() == 1
    
    def test_cache_miss(self):
        """Test cache returns None for non-existent keys."""
        cache = TTLCache(max_size=10, ttl=60)
        
        result = cache.get("nonexistent", "ko-zh")
        
        assert result is None
    
    def test_cache_different_dict_types(self):
        """Test cache distinguishes between different dict types."""
        cache = TTLCache(max_size=10, ttl=60)
        
        cache.set("word", "ko-zh", {"lang": "zh"})
        cache.set("word", "ko-en", {"lang": "en"})
        
        result_zh = cache.get("word", "ko-zh")
        result_en = cache.get("word", "ko-en")
        
        assert result_zh["lang"] == "zh"
        assert result_en["lang"] == "en"
        assert cache.size() == 2
    
    def test_cache_ttl_expiration(self):
        """Test cache entries expire after TTL."""
        cache = TTLCache(max_size=10, ttl=1)  # 1 second TTL
        
        cache.set("temporary", "ko-zh", {"data": "test"})
        
        # Should exist immediately
        result = cache.get("temporary", "ko-zh")
        assert result is not None
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be expired
        result = cache.get("temporary", "ko-zh")
        assert result is None
    
    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        import time
        cache = TTLCache(max_size=3, ttl=60)
        
        # Fill cache to capacity with slight delays to ensure ordering
        cache.set("word1", "ko-zh", {"data": 1})
        time.sleep(0.01)
        cache.set("word2", "ko-zh", {"data": 2})
        time.sleep(0.01)
        cache.set("word3", "ko-zh", {"data": 3})
        
        assert cache.size() == 3
        
        # Access word1 and word3 to make them recently used
        time.sleep(0.01)
        cache.get("word1", "ko-zh")
        time.sleep(0.01)
        cache.get("word3", "ko-zh")
        
        # Add new item, should evict word2 (least recently used)
        time.sleep(0.01)
        cache.set("word4", "ko-zh", {"data": 4})
        
        assert cache.size() == 3
        # word2 should be evicted as it was not accessed and is oldest
        assert cache.get("word2", "ko-zh") is None
    
    def test_cache_clear(self):
        """Test clearing all cache entries."""
        cache = TTLCache(max_size=10, ttl=60)
        
        cache.set("word1", "ko-zh", {"data": 1})
        cache.set("word2", "ko-zh", {"data": 2})
        
        assert cache.size() == 2
        
        cache.clear()
        
        assert cache.size() == 0
        assert cache.get("word1", "ko-zh") is None
        assert cache.get("word2", "ko-zh") is None
    
    def test_cache_stats(self):
        """Test cache statistics reporting."""
        cache = TTLCache(max_size=100, ttl=3600)
        
        cache.set("word1", "ko-zh", {"data": 1})
        cache.set("word2", "ko-zh", {"data": 2})
        
        stats = cache.get_stats()
        
        assert stats["size"] == 2
        assert stats["max_size"] == 100
        assert stats["ttl"] == 3600
        assert stats["utilization"] == 0.02  # 2/100
    
    def test_cache_key_generation(self):
        """Test cache key generation is consistent."""
        cache = TTLCache(max_size=10, ttl=60)
        
        key1 = cache._make_key("word", "ko-zh")
        key2 = cache._make_key("word", "ko-zh")
        key3 = cache._make_key("word", "ko-en")
        
        assert key1 == key2  # Same word and dict_type
        assert key1 != key3  # Different dict_type
        assert len(key1) == 32  # MD5 hash length
    
    def test_cache_update_existing_key(self):
        """Test updating an existing cache entry."""
        cache = TTLCache(max_size=10, ttl=60)
        
        cache.set("word", "ko-zh", {"version": 1})
        cache.set("word", "ko-zh", {"version": 2})
        
        result = cache.get("word", "ko-zh")
        
        assert result["version"] == 2
        assert cache.size() == 1  # Should not create duplicate
    
    def test_cache_large_dataset(self):
        """Test cache with large number of entries."""
        cache = TTLCache(max_size=1000, ttl=60)
        
        # Add many entries
        for i in range(100):
            cache.set(f"word_{i}", "ko-zh", {"index": i})
        
        assert cache.size() == 100
        
        # Verify some entries
        assert cache.get("word_0", "ko-zh")["index"] == 0
        assert cache.get("word_50", "ko-zh")["index"] == 50
        assert cache.get("word_99", "ko-zh")["index"] == 99

    def test_cache_set_custom_ttl_overrides_default(self):
        """set(ttl=...) 应覆盖默认 TTL（用于负缓存等场景）。"""
        cache = TTLCache(max_size=10, ttl=60)

        cache.set("negative", "ko-zh", {"data": "miss"}, ttl=1)
        assert cache.get("negative", "ko-zh") is not None

        time.sleep(1.1)
        assert cache.get("negative", "ko-zh") is None

    def test_cache_key_mode_plain_and_hash_with_plain(self):
        """key_mode 应支持可读 key（plain/hash_with_plain），便于调试。"""
        cache_plain = TTLCache(max_size=10, ttl=60, key_mode="plain")
        assert cache_plain._make_key("word", "ko-zh") == "word:ko-zh"

        cache_mix = TTLCache(max_size=10, ttl=60, key_mode="hash_with_plain")
        key = cache_mix._make_key("word", "ko-zh")
        assert key.startswith("word:ko-zh|")
        assert len(key.split("|", 1)[1]) == 32  # MD5 hash 长度


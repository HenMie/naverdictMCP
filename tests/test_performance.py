"""Performance benchmarks and stress tests."""

import pytest
import time
import asyncio
from src.client import NaverClient
from src.cache import TTLCache
from src.metrics import Metrics


@pytest.mark.performance
class TestPerformance:
    """Performance benchmarks for the Naver Dictionary MCP."""
    
    @pytest.mark.asyncio
    async def test_single_search_latency(self):
        """Test single search latency should be under 2 seconds."""
        async with NaverClient() as client:
            start = time.time()
            await client.search("안녕하세요", "ko-zh")
            duration = time.time() - start
            
            print(f"\n单次查询延迟: {duration:.3f}s")
            assert duration < 2.0, f"查询耗时过长: {duration:.2f}s (期望 < 2.0s)"
    
    @pytest.mark.asyncio
    async def test_concurrent_searches(self):
        """Test concurrent search performance with 5 different words."""
        words = ["안녕하세요", "학교", "선생님", "학생", "책"]
        
        async with NaverClient() as client:
            start = time.time()
            tasks = [client.search(word, "ko-zh") for word in words]
            await asyncio.gather(*tasks)
            duration = time.time() - start
            
            print(f"\n并发查询 {len(words)} 个单词延迟: {duration:.3f}s")
            print(f"平均延迟: {duration/len(words):.3f}s/查询")
            
            # 并发查询应该比顺序快
            assert duration < 5.0, f"并发查询耗时: {duration:.2f}s (期望 < 5.0s)"
    
    @pytest.mark.asyncio
    async def test_cache_performance(self):
        """Test cache hit performance is significantly faster than API calls."""
        cache = TTLCache(max_size=100, ttl=60)
        word = "테스트"
        dict_type = "ko-zh"
        
        # First call - cache miss (should be slower)
        async with NaverClient() as client:
            start = time.time()
            data = await client.search(word, dict_type)
            api_duration = time.time() - start
            
            # Cache the result
            cache.set(word, dict_type, data)
        
        # Second call - cache hit (should be faster)
        start = time.time()
        cached_data = cache.get(word, dict_type)
        cache_duration = time.time() - start
        
        print(f"\nAPI 调用延迟: {api_duration:.3f}s")
        print(f"缓存读取延迟: {cache_duration:.6f}s")
        print(f"加速比: {api_duration/cache_duration:.0f}x")
        
        assert cached_data is not None, "缓存应该返回数据"
        assert cache_duration < 0.01, "缓存读取应该在 10ms 内"
        assert api_duration > cache_duration * 100, "缓存应该至少快 100 倍"
    
    @pytest.mark.asyncio
    async def test_connection_pool_reuse(self):
        """Test connection pool reuse improves performance."""
        words = ["안녕", "감사", "미안"]
        
        # Without connection pool (create new client each time)
        start = time.time()
        for word in words:
            async with NaverClient() as client:
                client._use_pool = False
                await client.search(word, "ko-zh")
        without_pool_duration = time.time() - start
        
        # With connection pool (reuse connections)
        start = time.time()
        async with NaverClient() as client:
            for word in words:
                await client.search(word, "ko-zh")
        with_pool_duration = time.time() - start
        
        print(f"\n不使用连接池: {without_pool_duration:.3f}s")
        print(f"使用连接池: {with_pool_duration:.3f}s")
        print(f"性能提升: {(without_pool_duration - with_pool_duration)/without_pool_duration * 100:.1f}%")
        
        # Connection pool should be at least slightly faster
        assert with_pool_duration <= without_pool_duration * 1.2, \
            "连接池应该提供性能优势或相当"
    
    @pytest.mark.asyncio
    async def test_metrics_overhead(self):
        """Test metrics recording has minimal overhead."""
        metrics = Metrics()
        iterations = 1000
        
        # Measure overhead of metrics recording
        start = time.time()
        for i in range(iterations):
            metrics.record_request(success=True, latency=0.1, endpoint="test")
            if i % 2 == 0:
                metrics.record_cache_hit()
            else:
                metrics.record_cache_miss()
        duration = time.time() - start
        
        overhead_per_call = duration / iterations
        print(f"\n指标记录开销: {overhead_per_call*1000:.3f}ms/请求")
        print(f"总请求: {iterations}, 总时间: {duration:.3f}s")
        
        # Overhead should be negligible (< 0.1ms per call)
        assert overhead_per_call < 0.0001, \
            f"指标记录开销过大: {overhead_per_call*1000:.3f}ms (期望 < 0.1ms)"
    
    @pytest.mark.asyncio
    async def test_cache_lru_eviction_performance(self):
        """Test LRU eviction doesn't significantly slow down cache operations."""
        cache = TTLCache(max_size=10, ttl=60)  # Small cache to trigger evictions
        
        # Fill cache beyond capacity
        start = time.time()
        for i in range(100):
            cache.set(f"word_{i}", "ko-zh", {"data": f"result_{i}"})
        duration = time.time() - start
        
        avg_time = duration / 100
        print(f"\nLRU 淘汰场景下平均缓存写入时间: {avg_time*1000:.3f}ms")
        print(f"缓存大小: {cache.size()} (最大: {cache.max_size})")
        
        # Even with evictions, cache operations should be fast
        assert avg_time < 0.001, \
            f"LRU 淘汰导致缓存操作过慢: {avg_time*1000:.3f}ms (期望 < 1ms)"
        assert cache.size() == cache.max_size, "缓存应该维持在最大容量"
    
    @pytest.mark.asyncio  
    async def test_high_concurrency(self):
        """Test system handles high concurrency (50 concurrent requests)."""
        words = ["테스트"] * 50  # 50 concurrent requests for same word
        
        async with NaverClient() as client:
            start = time.time()
            tasks = [client.search(word, "ko-zh") for word in words]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            duration = time.time() - start
            
            # Check results
            errors = [r for r in results if isinstance(r, Exception)]
            successes = len(results) - len(errors)
            
            print(f"\n高并发测试 (50 请求):")
            print(f"  总时间: {duration:.3f}s")
            print(f"  成功: {successes}, 失败: {len(errors)}")
            print(f"  吞吐量: {len(results)/duration:.1f} 请求/秒")
            
            assert len(errors) == 0, f"高并发测试出现 {len(errors)} 个错误"
            assert duration < 10.0, f"高并发处理耗时过长: {duration:.2f}s"


@pytest.mark.benchmark
class TestBenchmarks:
    """Detailed benchmarks for comparison."""
    
    @pytest.mark.asyncio
    async def test_cache_vs_api_benchmark(self):
        """Detailed benchmark comparing cache vs API performance."""
        cache = TTLCache(max_size=100, ttl=60)
        word = "벤치마크"
        dict_type = "ko-zh"
        
        # Warm up
        async with NaverClient() as client:
            data = await client.search(word, dict_type)
            cache.set(word, dict_type, data)
        
        # Benchmark API calls
        api_times = []
        for _ in range(5):
            async with NaverClient() as client:
                start = time.time()
                await client.search(word, dict_type)
                api_times.append(time.time() - start)
        
        # Benchmark cache hits
        cache_times = []
        for _ in range(1000):
            start = time.time()
            cache.get(word, dict_type)
            cache_times.append(time.time() - start)
        
        print(f"\nAPI 调用统计 (n={len(api_times)}):")
        print(f"  平均: {sum(api_times)/len(api_times)*1000:.2f}ms")
        print(f"  最小: {min(api_times)*1000:.2f}ms")
        print(f"  最大: {max(api_times)*1000:.2f}ms")
        
        print(f"\n缓存读取统计 (n={len(cache_times)}):")
        print(f"  平均: {sum(cache_times)/len(cache_times)*1000000:.2f}μs")
        print(f"  最小: {min(cache_times)*1000000:.2f}μs")
        print(f"  最大: {max(cache_times)*1000000:.2f}μs")
        
        avg_api = sum(api_times) / len(api_times)
        avg_cache = sum(cache_times) / len(cache_times)
        print(f"\n加速比: {avg_api/avg_cache:.0f}x")


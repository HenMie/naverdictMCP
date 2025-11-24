"""FastMCP server for Naver Dictionary."""

from fastmcp import FastMCP
import sys
import os
import json
import httpx
import time
import asyncio

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.client import NaverClient, DictType, ValidationError, client_pool
from src.parser import parse_search_results, format_results
from src.config import config
from src.logger import logger
from src.cache import cache
from src.metrics import metrics

# Initialize FastMCP server
mcp = FastMCP("Naver Dictionary")


async def _search_word_impl(word: str, dict_type: DictType = "ko-zh") -> str:
    """
    Core implementation of word search functionality with comprehensive error handling.
    
    Args:
        word: The word to search for
        dict_type: Dictionary type - "ko-zh" for Korean-Chinese or "ko-en" for Korean-English
        
    Returns:
        JSON formatted dictionary results including word, pronunciation, meanings, and examples
        
    Error Response Format:
        {
            "success": false,
            "error": "error message",
            "error_type": "validation|timeout|http_error|parse_error|unknown",
            "details": "detailed error information"
        }
    """
    start_time = time.time()
    
    try:
        logger.info(f"收到搜索请求: word='{word}', dict_type={dict_type}")
        
        # Try to get from cache first
        cached_result = cache.get(word, dict_type)
        if cached_result:
            metrics.record_cache_hit()
            latency = time.time() - start_time
            metrics.record_request(success=True, latency=latency, endpoint="search")
            logger.info(f"缓存命中: word='{word}', latency={latency:.3f}s")
            return cached_result
        
        # Cache miss, fetch from API
        metrics.record_cache_miss()
        
        async with NaverClient() as client:
            data = await client.search(word, dict_type)
            results = parse_search_results(data)
            
            logger.info(f"搜索成功: 找到 {len(results)} 条结果")
            
            # Create JSON response
            result_json = json.dumps({
                "success": True,
                "word": word,
                "dict_type": dict_type,
                "count": len(results),
                "results": results
            }, ensure_ascii=False, indent=2)
            
            # Cache the result
            cache.set(word, dict_type, result_json)
            
            # Record metrics
            latency = time.time() - start_time
            metrics.record_request(success=True, latency=latency, endpoint="search")
            
            return result_json
    
    except ValidationError as e:
        latency = time.time() - start_time
        metrics.record_request(success=False, latency=latency, endpoint="search")
        metrics.record_error("validation")
        logger.warning(f"输入验证失败: {e}")
        return json.dumps({
            "success": False,
            "error": "输入验证失败",
            "error_type": "validation",
            "details": str(e)
        }, ensure_ascii=False, indent=2)
    
    except httpx.TimeoutException as e:
        latency = time.time() - start_time
        metrics.record_request(success=False, latency=latency, endpoint="search")
        metrics.record_error("timeout")
        logger.error(f"请求超时: {e}")
        return json.dumps({
            "success": False,
            "error": "请求超时",
            "error_type": "timeout",
            "details": f"API 请求超时，请稍后重试（超时时间: {config.HTTP_TIMEOUT}s）"
        }, ensure_ascii=False, indent=2)
    
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        latency = time.time() - start_time
        metrics.record_request(success=False, latency=latency, endpoint="search")
        metrics.record_error("http_error")
        logger.error(f"HTTP 错误 {status_code}: {e}")
        
        error_messages = {
            400: "请求参数错误",
            404: "未找到请求的资源",
            429: "请求过于频繁，请稍后重试",
            500: "服务器内部错误",
            502: "网关错误",
            503: "服务暂时不可用",
        }
        
        return json.dumps({
            "success": False,
            "error": error_messages.get(status_code, f"HTTP 错误 {status_code}"),
            "error_type": "http_error",
            "details": str(e)
        }, ensure_ascii=False, indent=2)
    
    except httpx.RequestError as e:
        latency = time.time() - start_time
        metrics.record_request(success=False, latency=latency, endpoint="search")
        metrics.record_error("network_error")
        logger.error(f"网络请求错误: {e}", exc_info=True)
        return json.dumps({
            "success": False,
            "error": "网络连接错误",
            "error_type": "network_error",
            "details": "无法连接到 Naver API，请检查网络连接"
        }, ensure_ascii=False, indent=2)
    
    except (KeyError, ValueError, TypeError) as e:
        latency = time.time() - start_time
        metrics.record_request(success=False, latency=latency, endpoint="search")
        metrics.record_error("parse_error")
        logger.error(f"解析错误: {e}", exc_info=True)
        return json.dumps({
            "success": False,
            "error": "响应解析失败",
            "error_type": "parse_error",
            "details": "API 返回的数据格式异常，可能是 API 接口发生了变化"
        }, ensure_ascii=False, indent=2)
    
    except Exception as e:
        latency = time.time() - start_time
        metrics.record_request(success=False, latency=latency, endpoint="search")
        metrics.record_error("unknown")
        logger.error(f"未知错误: {e}", exc_info=True)
        return json.dumps({
            "success": False,
            "error": "未知错误",
            "error_type": "unknown",
            "details": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def search_word(word: str, dict_type: DictType = "ko-zh") -> str:
    """
    Search for a word in Naver Dictionary.
    
    Args:
        word: The word to search for
        dict_type: Dictionary type - "ko-zh" for Korean-Chinese or "ko-en" for Korean-English
        
    Returns:
        JSON formatted string containing dictionary results with the following structure:
        {
            "success": true,
            "word": "searched word",
            "dict_type": "ko-zh or ko-en",
            "count": number of results,
            "results": [
                {
                    "word": "word/phrase",
                    "pronunciation": "pronunciation",
                    "meanings": ["meaning1", "meaning2", ...],
                    "examples": ["example1", "example2", ...]
                },
                ...
            ]
        }
    """
    return await _search_word_impl(word, dict_type)


@mcp.tool()
async def batch_search_words(
    words: list[str], 
    dict_type: DictType = "ko-zh"
) -> str:
    """
    Batch search multiple words in parallel.
    
    Args:
        words: List of words to search (maximum 10 words per request)
        dict_type: Dictionary type - "ko-zh" for Korean-Chinese or "ko-en" for Korean-English
        
    Returns:
        JSON formatted batch results with individual results for each word
        
    Example:
        {
            "success": true,
            "count": 3,
            "dict_type": "ko-zh",
            "results": [
                {
                    "word": "안녕하세요",
                    "success": true,
                    "results": [...]
                },
                ...
            ]
        }
    """
    start_time = time.time()
    
    # Validate input
    if not words:
        metrics.record_error("validation")
        return json.dumps({
            "success": False,
            "error": "单词列表不能为空",
            "error_type": "validation"
        }, ensure_ascii=False, indent=2)
    
    if len(words) > 10:
        metrics.record_error("validation")
        return json.dumps({
            "success": False,
            "error": "批量查询最多支持 10 个单词",
            "error_type": "validation",
            "details": f"当前请求 {len(words)} 个单词，超过限制"
        }, ensure_ascii=False, indent=2)
    
    logger.info(f"收到批量查询请求: {len(words)} 个单词, dict_type={dict_type}")
    
    results = []
    
    async with NaverClient() as client:
        # Create tasks for all searches
        tasks = []
        for word in words:
            async def search_single(w: str):
                try:
                    # Check cache first
                    cached = cache.get(w, dict_type)
                    if cached:
                        metrics.record_cache_hit()
                        cached_data = json.loads(cached)
                        return {
                            "word": w,
                            "success": True,
                            "results": cached_data.get("results", []),
                            "from_cache": True
                        }
                    
                    # Fetch from API
                    metrics.record_cache_miss()
                    data = await client.search(w, dict_type)
                    parsed = parse_search_results(data)
                    
                    # Cache result
                    result_json = json.dumps({
                        "success": True,
                        "word": w,
                        "dict_type": dict_type,
                        "count": len(parsed),
                        "results": parsed
                    }, ensure_ascii=False)
                    cache.set(w, dict_type, result_json)
                    
                    return {
                        "word": w,
                        "success": True,
                        "results": parsed,
                        "from_cache": False
                    }
                except Exception as e:
                    logger.warning(f"批量查询中单词 '{w}' 失败: {e}")
                    return {
                        "word": w,
                        "success": False,
                        "error": str(e)
                    }
            
            tasks.append(search_single(word))
        
        # Execute all searches in parallel
        results = await asyncio.gather(*tasks, return_exceptions=False)
    
    # Record metrics
    latency = time.time() - start_time
    success_count = sum(1 for r in results if r.get("success"))
    metrics.record_request(
        success=success_count == len(words), 
        latency=latency, 
        endpoint="batch_search"
    )
    
    logger.info(f"批量查询完成: {success_count}/{len(words)} 成功, 耗时 {latency:.3f}s")
    
    return json.dumps({
        "success": True,
        "count": len(results),
        "dict_type": dict_type,
        "results": results,
        "latency": latency
    }, ensure_ascii=False, indent=2)


async def cleanup():
    """Cleanup resources on server shutdown."""
    logger.info("开始清理资源...")
    await client_pool.close()
    logger.info("资源清理完成")


if __name__ == "__main__":
    # Run the MCP server in HTTP mode
    try:
        logger.info("="*60)
        logger.info(f"启动 Naver Dictionary MCP 服务器")
        logger.info(f"服务器地址: {config.get_server_address()}")
        logger.info(f"日志级别: {config.LOG_LEVEL}")
        logger.info(f"HTTP 超时: {config.HTTP_TIMEOUT}s")
        logger.info(f"缓存配置: 最大 {cache.max_size} 项, TTL {cache.ttl}s")
        logger.info("="*60)
        
        mcp.run(
            transport="streamable-http",
            host=config.SERVER_HOST,
            port=config.SERVER_PORT,
            stateless_http=True
        )
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在关闭服务器...")
        asyncio.run(cleanup())
    except Exception as e:
        logger.error(f"服务器启动失败: {e}", exc_info=True)
        asyncio.run(cleanup())
        sys.exit(1)

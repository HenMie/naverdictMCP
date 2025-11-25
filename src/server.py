"""Naver 辞典 FastMCP 服务器。

基于 FastMCP 2.0 的 Streamable HTTP MCP 服务器，用于查询 Naver 辞典（韩中、韩英）。
"""

import asyncio
import json
import os
import signal
import sys
import time
from typing import Optional

import httpx
from fastmcp import FastMCP

# 添加父目录到路径以支持导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cache import cache
from src.client import DictType, NaverClient, ValidationError, client_pool
from src.config import config
from src.logger import logger
from src.metrics import metrics
from src.parser import parse_search_results
from src.rate_limiter import rate_limiter

# 初始化 FastMCP 服务器
mcp = FastMCP("Naver Dictionary")

# 全局关闭事件
_shutdown_event: Optional[asyncio.Event] = None


def _check_rate_limit(client_id: str = "default") -> Optional[str]:
    """
    检查请求是否超过限流限制。
    
    Args:
        client_id: 客户端标识符
        
    Returns:
        如果超过限制返回错误 JSON 字符串，否则返回 None
    """
    if not rate_limiter.is_allowed(client_id):
        remaining = rate_limiter.get_remaining_tokens(client_id)
        metrics.record_error("rate_limit")
        logger.warning(f"请求被限流: client={client_id}, remaining={remaining}")
        return json.dumps({
            "success": False,
            "error": "请求频率超限",
            "error_type": "rate_limit",
            "details": f"请求过于频繁，请稍后重试。当前剩余配额: {remaining}"
        }, ensure_ascii=False, indent=2)
    return None


async def _search_word_impl(word: str, dict_type: DictType = "ko-zh") -> str:
    """
    单词搜索的核心实现，包含完整的错误处理。
    
    Args:
        word: 要搜索的单词
        dict_type: 字典类型 - "ko-zh" 韩中辞典，"ko-en" 韩英辞典
        
    Returns:
        JSON 格式的搜索结果，包含单词、发音、释义和例句
        
    错误响应格式:
        {
            "success": false,
            "error": "错误信息",
            "error_type": "validation|timeout|http_error|parse_error|rate_limit|unknown",
            "details": "详细错误信息"
        }
    """
    start_time = time.time()
    
    # 检查限流
    rate_limit_error = _check_rate_limit()
    if rate_limit_error:
        return rate_limit_error
    
    try:
        logger.info(f"收到搜索请求: word='{word}', dict_type={dict_type}")
        
        # 先尝试从缓存获取
        cached_result = cache.get(word, dict_type)
        if cached_result:
            metrics.record_cache_hit()
            latency = time.time() - start_time
            metrics.record_request(success=True, latency=latency, endpoint="search")
            logger.info(f"缓存命中: word='{word}', latency={latency:.3f}s")
            return cached_result
        
        # 缓存未命中，从 API 获取
        metrics.record_cache_miss()
        
        async with NaverClient() as client:
            data = await client.search(word, dict_type)
            results = parse_search_results(data)
            
            logger.info(f"搜索成功: 找到 {len(results)} 条结果")
            
            # 创建 JSON 响应
            result_json = json.dumps({
                "success": True,
                "word": word,
                "dict_type": dict_type,
                "count": len(results),
                "results": results
            }, ensure_ascii=False, indent=2)
            
            # 缓存结果
            cache.set(word, dict_type, result_json)
            
            # 记录指标
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
    在 Naver 辞典中搜索单词。
    
    Args:
        word: 要搜索的单词
        dict_type: 字典类型 - "ko-zh" 韩中辞典，"ko-en" 韩英辞典
        
    Returns:
        JSON 格式字符串，包含搜索结果:
        {
            "success": true,
            "word": "搜索的单词",
            "dict_type": "ko-zh 或 ko-en",
            "count": 结果数量,
            "results": [
                {
                    "word": "单词/短语",
                    "pronunciation": "发音",
                    "meanings": ["释义1", "释义2", ...],
                    "examples": ["例句1", "例句2", ...]
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
    批量并发搜索多个单词。
    
    Args:
        words: 要搜索的单词列表（最多 10 个）
        dict_type: 字典类型 - "ko-zh" 韩中辞典，"ko-en" 韩英辞典
        
    Returns:
        JSON 格式的批量搜索结果:
        {
            "success": true,
            "count": 3,
            "dict_type": "ko-zh",
            "results": [
                {
                    "word": "안녕하세요",
                    "success": true,
                    "results": [...],
                    "from_cache": true
                },
                ...
            ],
            "latency": 0.234
        }
    """
    start_time = time.time()
    
    # 检查限流（批量查询消耗更多配额）
    rate_limit_error = _check_rate_limit()
    if rate_limit_error:
        return rate_limit_error
    
    # 输入验证
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
    
    async def search_single(w: str) -> dict:
        """搜索单个单词的辅助函数。"""
        try:
            # 先检查缓存
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
            
            # 从 API 获取
            metrics.record_cache_miss()
            async with NaverClient() as client:
                data = await client.search(w, dict_type)
                parsed = parse_search_results(data)
                
                # 缓存结果
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
    
    # 并发执行所有搜索任务
    tasks = [search_single(word) for word in words]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    
    # 记录指标
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


async def cleanup() -> None:
    """清理资源。"""
    logger.info("开始清理资源...")
    await client_pool.close()
    logger.info("资源清理完成")


def _signal_handler(sig: int, frame: object) -> None:
    """
    信号处理器，用于优雅关闭。
    
    Args:
        sig: 信号编号
        frame: 当前栈帧
    """
    sig_name = signal.Signals(sig).name
    logger.info(f"收到 {sig_name} 信号，正在优雅关闭...")
    
    # 设置关闭事件
    global _shutdown_event
    if _shutdown_event:
        _shutdown_event.set()
    
    # 运行清理任务
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(cleanup())
        else:
            asyncio.run(cleanup())
    except RuntimeError:
        # 如果没有事件循环，同步清理
        pass


def setup_signal_handlers() -> None:
    """设置信号处理器以支持优雅关闭。"""
    # 注册信号处理器
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    
    # Windows 不支持 SIGHUP
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, _signal_handler)
    
    logger.debug("信号处理器已设置")


if __name__ == "__main__":
    # 设置信号处理器
    setup_signal_handlers()
    
    # 运行 MCP 服务器（HTTP 模式）
    try:
        logger.info("=" * 60)
        logger.info("启动 Naver Dictionary MCP 服务器")
        logger.info(f"服务器地址: {config.get_server_address()}")
        logger.info(f"日志级别: {config.LOG_LEVEL}")
        logger.info(f"HTTP 超时: {config.HTTP_TIMEOUT}s")
        logger.info(f"缓存配置: 最大 {cache.max_size} 项, TTL {cache.ttl}s")
        logger.info(f"限流配置: {rate_limiter.requests_per_minute} 请求/分钟")
        logger.info("=" * 60)
        
        mcp.run(
            transport="streamable-http",
            host=config.SERVER_HOST,
            port=config.SERVER_PORT,
            stateless_http=True
        )
    except KeyboardInterrupt:
        logger.info("收到键盘中断，正在关闭服务器...")
        asyncio.run(cleanup())
    except Exception as e:
        logger.error(f"服务器启动失败: {e}", exc_info=True)
        asyncio.run(cleanup())
        sys.exit(1)

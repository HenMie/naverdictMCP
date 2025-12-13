"""Naver 辞典 FastMCP 服务器。

基于 FastMCP 2.0 的 Streamable HTTP MCP 服务器，用于查询 Naver 辞典（韩中、韩英）。
"""

import asyncio
import json
import os
import random
import signal
import sys
import time
import unicodedata
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional

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
from src.responses import (
    build_batch_payload,
    build_cached_json_item,
    build_error_item,
    build_success_item,
    dumps_json,
    patch_from_cache_flag,
)

# 初始化 FastMCP 服务器
mcp = FastMCP("Naver Dictionary")

# 全局关闭事件
_shutdown_event: Optional[asyncio.Event] = None


def _normalize_word(word: str) -> str:
    """对搜索词做统一规范化（server 层）。

    规则：
    - 保留“空字符串”和“全空格”两类错误的区分（便于给出更准确的错误信息）
    - 去掉首尾空白（strip）
    - Unicode 统一为 NFC（减少同形不同码的缓存 miss）

    Args:
        word: 原始搜索词

    Returns:
        规范化后的搜索词

    Raises:
        ValidationError: 搜索词无效时抛出
    """
    if word is None:  # type: ignore[truthy-bool]
        raise ValidationError("搜索词不能为空")

    if word == "":
        raise ValidationError("搜索词不能为空")

    stripped = word.strip()
    if stripped == "":
        raise ValidationError("搜索词不能只包含空格")

    normalized = unicodedata.normalize("NFC", stripped)

    # 与 client 层保持一致：最大 100 字符
    if len(normalized) > 100:
        raise ValidationError(f"搜索词过长（最大 100 字符，当前 {len(normalized)} 字符）")

    return normalized


def _build_success_json(
    *,
    word: str,
    dict_type: str,
    results: list[dict[str, Any]],
    from_cache: bool,
) -> str:
    """构建成功响应 JSON（字符串）。

    为保证 `search_word` 与 `batch_search_words` 子项字段一致，这里统一补齐：
    - from_cache: 是否来自缓存
    - deduped: 是否为批量去重回填（单查恒为 false）
    - source_word: 去重源词（单查恒等于 word）
    """

    payload = build_success_item(
        word=word,
        dict_type=dict_type,
        results=results,
        from_cache=from_cache,
        deduped=False,
        source_word=word,
        include_dict_type=True,
    )
    return dumps_json(payload)


def _check_rate_limit(tokens: int = 1) -> Optional[int]:
    """检查全局限流（按 tokens 消耗）。

    注意：限流用于保护服务器出口 IP，避免上游 Naver 对 IP 限制。

    Args:
        tokens: 本次需要消耗的令牌数量（通常等于需要访问上游的请求数）

    Returns:
        如果超过限制返回 remaining（剩余配额），否则返回 None
    """
    if not rate_limiter.consume(tokens):
        remaining = rate_limiter.get_remaining_tokens()
        metrics.record_error("rate_limit")
        logger.warning(f"请求被限流(全局): need={tokens}, remaining={remaining}")
        return remaining
    return None


def _cache_ttl_for_results(results: list[dict[str, Any]]) -> int:
    """根据查询结果选择缓存 TTL。

    - 正常命中：使用 CACHE_TTL
    - 未找到结果（负缓存）：使用 CACHE_NEGATIVE_TTL（短 TTL，降低热点 miss 压力）
    """

    return config.CACHE_NEGATIVE_TTL if len(results) == 0 else config.CACHE_TTL


def _parse_retry_after_seconds(value: Optional[str]) -> Optional[float]:
    """解析 Retry-After（秒）。

    Retry-After 可能是：
    - 整数秒（最常见）
    - HTTP-date（RFC 7231）
    """

    if not value:
        return None

    raw = value.strip()
    if raw == "":
        return None

    # 1) delta-seconds
    try:
        seconds = float(int(raw))
        return seconds if seconds > 0 else None
    except (TypeError, ValueError):
        pass

    # 2) HTTP-date
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        seconds = (dt - now).total_seconds()
        return seconds if seconds > 0 else None
    except Exception:
        return None


def _is_retryable_upstream_status(status_code: int) -> bool:
    """判断是否为可重试的上游状态码（仅对幂等请求）。"""

    return status_code in {429, 500, 502, 503, 504}


def _http_error_type_for_upstream_status(status_code: int) -> str:
    """将上游 HTTP 状态码映射为更明确的 error_type。"""

    if status_code == 429:
        return "upstream_rate_limit"
    if 500 <= status_code < 600:
        return "upstream_server_error"
    return "http_error"


def _compute_backoff_delay(
    *,
    retry_index: int,
    base_delay: float,
    max_delay: float,
    retry_after: Optional[float] = None,
) -> float:
    """计算指数退避 + 抖动的等待时间（秒）。

    - retry_index 从 1 开始（第一次重试为 1）
    - 采用指数退避，并加入随机抖动，避免“惊群”
    - 对 429 优先参考 Retry-After（若可解析）
    """

    exp = base_delay * (2 ** (retry_index - 1))
    cap = min(max_delay, exp)

    if retry_after is not None:
        # 尽量尊重 Retry-After（但不超过 max_delay），同时添加少量“正向抖动”
        wait = min(max_delay, max(cap, retry_after))
        extra_cap = max(0.0, min(max_delay - wait, wait * 0.1))
        return wait + (random.uniform(0.0, extra_cap) if extra_cap > 0 else 0.0)

    # Full jitter：在 [0, cap] 内随机，避免并发重试同步
    return random.uniform(0.0, cap)


def _try_consume_retry_token(tokens: int = 1) -> bool:
    """为“重试”额外消耗令牌（不计入 metrics.rate_limit 错误）。

    说明：
    - 首次上游请求的令牌消耗由调用方（search_word/batch_search_words 的全局限流）负责
    - 重试会额外产生上游请求，因此需要额外消耗令牌，确保不突破全局配额
    """

    if tokens <= 0:
        raise ValueError("tokens 必须大于 0")

    if not rate_limiter.can_consume(tokens):
        return False
    return rate_limiter.consume(tokens)


async def _upstream_search_with_retry(
    *,
    client: NaverClient,
    word: str,
    dict_type: DictType,
    semaphore: Optional[asyncio.Semaphore] = None,
) -> dict[str, Any]:
    """对上游请求增加精细重试（仅幂等 GET/特定错误码/网络异常）。"""

    max_attempts = config.UPSTREAM_RETRY_MAX_ATTEMPTS
    base_delay = config.UPSTREAM_RETRY_BASE_DELAY
    max_delay = config.UPSTREAM_RETRY_MAX_DELAY

    last_exc: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            if semaphore is not None:
                async with semaphore:
                    return await client.search(word, dict_type)
            return await client.search(word, dict_type)

        except httpx.HTTPStatusError as e:
            last_exc = e
            status_code = e.response.status_code
            if (attempt >= max_attempts) or (not _is_retryable_upstream_status(status_code)):
                raise

            retry_after = _parse_retry_after_seconds(
                getattr(getattr(e, "response", None), "headers", {}).get("Retry-After")  # type: ignore[attr-defined]
            )
            retry_index = attempt  # attempt=1 => 第一次重试

            delay = _compute_backoff_delay(
                retry_index=retry_index,
                base_delay=base_delay,
                max_delay=max_delay,
                retry_after=retry_after if status_code == 429 else None,
            )

            # 下一次重试会额外产生一次上游请求，需要额外消耗令牌
            await asyncio.sleep(delay)
            if not _try_consume_retry_token(tokens=1):
                raise
            continue

        except httpx.TimeoutException as e:
            last_exc = e
            if attempt >= max_attempts:
                raise

            retry_index = attempt
            delay = _compute_backoff_delay(
                retry_index=retry_index,
                base_delay=base_delay,
                max_delay=max_delay,
            )
            await asyncio.sleep(delay)
            if not _try_consume_retry_token(tokens=1):
                raise
            continue

        except httpx.RequestError as e:
            last_exc = e
            if attempt >= max_attempts:
                raise

            retry_index = attempt
            delay = _compute_backoff_delay(
                retry_index=retry_index,
                base_delay=base_delay,
                max_delay=max_delay,
            )
            await asyncio.sleep(delay)
            if not _try_consume_retry_token(tokens=1):
                raise
            continue

    # 理论上不会到这里（循环内要么 return，要么 raise），兜底
    if last_exc is not None:  # pragma: no cover
        raise last_exc
    raise RuntimeError("上游请求失败")  # pragma: no cover


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
    normalized_word: Optional[str] = None

    try:
        # 统一规范化（保证缓存 key 与下游一致）
        normalized_word = _normalize_word(word)

        logger.info(f"收到搜索请求: word='{normalized_word}', dict_type={dict_type}")
        
        # 先尝试从缓存获取
        cached_result = cache.get(normalized_word, dict_type)
        if cached_result:
            metrics.record_cache_hit()
            latency = time.time() - start_time
            metrics.record_request(success=True, latency=latency, endpoint="search")
            logger.info(f"缓存命中: word='{normalized_word}', latency={latency:.3f}s")
            # 缓存里存的是 from_cache=false 的“规范响应”，返回给调用方时修正为 true
            return patch_from_cache_flag(str(cached_result), True)
        
        # 缓存未命中：需要访问上游，先做全局限流
        metrics.record_cache_miss()
        remaining = _check_rate_limit(tokens=1)
        if remaining is not None:
            latency = time.time() - start_time
            metrics.record_request(success=False, latency=latency, endpoint="search")
            payload = build_error_item(
                word=normalized_word,
                dict_type=dict_type,
                error="请求频率超限",
                error_type="rate_limit",
                details=f"请求过于频繁，请稍后重试。当前剩余配额: {remaining}",
                from_cache=False,
                deduped=False,
                source_word=normalized_word,
                include_dict_type=True,
            )
            return dumps_json(payload)
        
        async with NaverClient() as client:
            data = await _upstream_search_with_retry(
                client=client,
                word=normalized_word,
                dict_type=dict_type,
            )
            results = parse_search_results(data)
            
            logger.info(f"搜索成功: 找到 {len(results)} 条结果")
            
            # 创建 JSON 响应
            result_json = _build_success_json(
                word=normalized_word,
                dict_type=dict_type,
                results=results,
                from_cache=False,
            )
            
            # 缓存结果
            cache.set(
                normalized_word,
                dict_type,
                result_json,
                ttl=_cache_ttl_for_results(results),
            )
            
            # 记录指标
            latency = time.time() - start_time
            metrics.record_request(success=True, latency=latency, endpoint="search")
            
            return result_json
    
    except ValidationError as e:
        latency = time.time() - start_time
        metrics.record_request(success=False, latency=latency, endpoint="search")
        metrics.record_error("validation")
        logger.warning(f"输入验证失败: {e}")
        w = normalized_word if normalized_word is not None else (word or "")
        payload = build_error_item(
            word=w,
            dict_type=dict_type,
            error="输入验证失败",
            error_type="validation",
            details=str(e),
            from_cache=False,
            deduped=False,
            source_word=w,
            include_dict_type=True,
        )
        return dumps_json(payload)
    
    except httpx.TimeoutException as e:
        latency = time.time() - start_time
        metrics.record_request(success=False, latency=latency, endpoint="search")
        metrics.record_error("timeout")
        logger.error(f"请求超时: {e}")
        w = normalized_word if normalized_word is not None else (word or "")
        payload = build_error_item(
            word=w,
            dict_type=dict_type,
            error="请求超时",
            error_type="timeout",
            details=f"API 请求超时，请稍后重试（超时时间: {config.HTTP_TIMEOUT}s）",
            from_cache=False,
            deduped=False,
            source_word=w,
            include_dict_type=True,
        )
        return dumps_json(payload)
    
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        latency = time.time() - start_time
        metrics.record_request(success=False, latency=latency, endpoint="search")
        error_type = _http_error_type_for_upstream_status(status_code)
        metrics.record_error(error_type)
        logger.error(f"HTTP 错误 {status_code}: {e}")
        
        error_messages = {
            400: "请求参数错误",
            404: "未找到请求的资源",
            429: "上游请求过于频繁，请稍后重试",
            500: "服务器内部错误",
            502: "网关错误",
            503: "服务暂时不可用",
        }
        
        w = normalized_word if normalized_word is not None else (word or "")
        if error_type == "upstream_rate_limit":
            error_msg = error_messages.get(429, "上游请求频率限制")
        elif error_type == "upstream_server_error":
            error_msg = error_messages.get(status_code, f"上游服务错误（HTTP {status_code}）")
        else:
            error_msg = error_messages.get(status_code, f"HTTP 错误 {status_code}")
        payload = build_error_item(
            word=w,
            dict_type=dict_type,
            error=error_msg,
            error_type=error_type,
            details=f"上游返回 HTTP {status_code}: {e}",
            from_cache=False,
            deduped=False,
            source_word=w,
            include_dict_type=True,
        )
        return dumps_json(payload)
    
    except httpx.RequestError as e:
        latency = time.time() - start_time
        metrics.record_request(success=False, latency=latency, endpoint="search")
        metrics.record_error("network_error")
        logger.error(f"网络请求错误: {e}", exc_info=True)
        w = normalized_word if normalized_word is not None else (word or "")
        payload = build_error_item(
            word=w,
            dict_type=dict_type,
            error="网络连接错误",
            error_type="network_error",
            details="无法连接到 Naver API，请检查网络连接",
            from_cache=False,
            deduped=False,
            source_word=w,
            include_dict_type=True,
        )
        return dumps_json(payload)
    
    except (KeyError, ValueError, TypeError) as e:
        latency = time.time() - start_time
        metrics.record_request(success=False, latency=latency, endpoint="search")
        metrics.record_error("parse_error")
        logger.error(f"解析错误: {e}", exc_info=True)
        w = normalized_word if normalized_word is not None else (word or "")
        payload = build_error_item(
            word=w,
            dict_type=dict_type,
            error="响应解析失败",
            error_type="parse_error",
            details="API 返回的数据格式异常，可能是 API 接口发生了变化",
            from_cache=False,
            deduped=False,
            source_word=w,
            include_dict_type=True,
        )
        return dumps_json(payload)
    
    except Exception as e:
        latency = time.time() - start_time
        metrics.record_request(success=False, latency=latency, endpoint="search")
        metrics.record_error("unknown")
        logger.error(f"未知错误: {e}", exc_info=True)
        w = normalized_word if normalized_word is not None else (word or "")
        payload = build_error_item(
            word=w,
            dict_type=dict_type,
            error="未知错误",
            error_type="unknown",
            details=str(e),
            from_cache=False,
            deduped=False,
            source_word=w,
            include_dict_type=True,
        )
        return dumps_json(payload)


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


async def _batch_search_words_impl(
    words: list[str], 
    dict_type: DictType = "ko-zh",
    return_cached_json: bool = False,
) -> str:
    """批量查询核心实现（便于单元测试与复用）。"""
    start_time = time.time()
    include_dict_type = config.BATCH_ITEM_INCLUDE_DICT_TYPE

    # 输入验证
    if not words:
        metrics.record_error("validation")
        return dumps_json(
            {
                "success": False,
                "error": "单词列表不能为空",
                "error_type": "validation",
                "details": "words 不能为空",
                "dict_type": dict_type,
            }
        )
    
    if len(words) > 10:
        metrics.record_error("validation")
        return dumps_json(
            {
                "success": False,
                "error": "批量查询最多支持 10 个单词",
                "error_type": "validation",
                "details": f"当前请求 {len(words)} 个单词，超过限制",
                "dict_type": dict_type,
            }
        )
    
    logger.info(f"收到批量查询请求: {len(words)} 个单词, dict_type={dict_type}")

    # 预分配结果（保持与输入顺序一致）
    results: list[dict[str, Any]] = [{} for _ in range(len(words))]

    # 需要访问上游的词（按词去重，减少上游请求与配额消耗）
    miss_indices_by_word: dict[str, list[int]] = {}

    # 1) 规范化 + 缓存优先（不访问上游不消耗配额）
    for idx, raw_word in enumerate(words):
        try:
            normalized_word = _normalize_word(raw_word)
        except ValidationError as e:
            metrics.record_error("validation")
            w = raw_word or ""
            results[idx] = build_error_item(
                word=w,
                dict_type=dict_type,
                error="输入验证失败",
                error_type="validation",
                details=str(e),
                from_cache=False,
                deduped=False,
                source_word=w.strip(),
                include_dict_type=include_dict_type,
            )
            continue

        cached = cache.get(normalized_word, dict_type)
        if cached:
            metrics.record_cache_hit()
            cached_str = str(cached)
            if return_cached_json:
                # 直接返回缓存 JSON，避免反序列化与拼装（调用方可自行解析）
                results[idx] = build_cached_json_item(
                    word=normalized_word,
                    dict_type=dict_type,
                    cached_json=cached_str,
                    deduped=False,
                    source_word=normalized_word,
                    include_dict_type=include_dict_type,
                )
            else:
                cached_data = json.loads(cached_str)
                cached_results = cached_data.get("results", [])
                results[idx] = build_success_item(
                    word=normalized_word,
                    dict_type=dict_type,
                    results=cached_results,
                    from_cache=True,
                    deduped=False,
                    source_word=normalized_word,
                    include_dict_type=include_dict_type,
                )
                # 兼容：如果缓存里包含 count 且与 results 不一致，以 count 为准
                if "count" in cached_data:
                    results[idx]["count"] = cached_data.get("count", len(cached_results))
            continue

        metrics.record_cache_miss()
        miss_indices_by_word.setdefault(normalized_word, []).append(idx)

    # 2) 对缓存 miss 的“去重词”做限流扣配额（只为上游请求消耗 token）
    miss_words = list(miss_indices_by_word.keys())
    if miss_words:
        remaining = _check_rate_limit(tokens=len(miss_words))
        if remaining is not None:
            # 限流时不访问上游：对 miss 的词填充 rate_limit 错误，其余（缓存命中/校验失败）保留
            for w in miss_words:
                indices = miss_indices_by_word[w]
                source_idx = indices[0]
                for idx in indices:
                    results[idx] = build_error_item(
                        word=w,
                        dict_type=dict_type,
                        error="请求频率超限",
                        error_type="rate_limit",
                        details=f"请求过于频繁，请稍后重试。当前剩余配额: {remaining}",
                        from_cache=False,
                        deduped=idx != source_idx,
                        source_word=w,
                        include_dict_type=include_dict_type,
                    )
        else:
            async with NaverClient() as client:
                semaphore = asyncio.Semaphore(config.BATCH_CONCURRENCY)

                async def fetch_one(w: str) -> dict[str, Any]:
                    """获取并解析单个词（仅处理缓存 miss 的词）。"""
                    try:
                        # 批量内部并发上限：只限制访问上游的瞬时并发，避免瞬时并发把上游打爆
                        data = await _upstream_search_with_retry(
                            client=client,
                            word=w,
                            dict_type=dict_type,
                            semaphore=semaphore,
                        )
                        parsed = parse_search_results(data)

                        # 缓存结果（与 search_word 一致）
                        cache_json = _build_success_json(
                            word=w,
                            dict_type=dict_type,
                            results=parsed,
                            from_cache=False,
                        )
                        cache.set(w, dict_type, cache_json, ttl=_cache_ttl_for_results(parsed))

                        return build_success_item(
                            word=w,
                            dict_type=dict_type,
                            results=parsed,
                            from_cache=False,
                            deduped=False,
                            source_word=w,
                            include_dict_type=include_dict_type,
                        )
                    except ValidationError as e:
                        metrics.record_error("validation")
                        return build_error_item(
                            word=w,
                            dict_type=dict_type,
                            error="输入验证失败",
                            error_type="validation",
                            details=str(e),
                            from_cache=False,
                            deduped=False,
                            source_word=w,
                            include_dict_type=include_dict_type,
                        )
                    except httpx.TimeoutException:
                        metrics.record_error("timeout")
                        return build_error_item(
                            word=w,
                            dict_type=dict_type,
                            error="请求超时",
                            error_type="timeout",
                            details=f"API 请求超时，请稍后重试（超时时间: {config.HTTP_TIMEOUT}s）",
                            from_cache=False,
                            deduped=False,
                            source_word=w,
                            include_dict_type=include_dict_type,
                        )
                    except httpx.HTTPStatusError as e:
                        status_code = e.response.status_code
                        error_type = _http_error_type_for_upstream_status(status_code)
                        metrics.record_error(error_type)
                        error_messages = {
                            400: "请求参数错误",
                            404: "未找到请求的资源",
                            429: "上游请求过于频繁，请稍后重试",
                            500: "服务器内部错误",
                            502: "网关错误",
                            503: "服务暂时不可用",
                        }
                        if error_type == "upstream_rate_limit":
                            error_msg = error_messages.get(429, "上游请求频率限制")
                        elif error_type == "upstream_server_error":
                            error_msg = error_messages.get(status_code, f"上游服务错误（HTTP {status_code}）")
                        else:
                            error_msg = error_messages.get(status_code, f"HTTP 错误 {status_code}")
                        return build_error_item(
                            word=w,
                            dict_type=dict_type,
                            error=error_msg,
                            error_type=error_type,
                            details=f"上游返回 HTTP {status_code}: {e}",
                            from_cache=False,
                            deduped=False,
                            source_word=w,
                            include_dict_type=include_dict_type,
                        )
                    except httpx.RequestError:
                        metrics.record_error("network_error")
                        return build_error_item(
                            word=w,
                            dict_type=dict_type,
                            error="网络连接错误",
                            error_type="network_error",
                            details="无法连接到 Naver API，请检查网络连接",
                            from_cache=False,
                            deduped=False,
                            source_word=w,
                            include_dict_type=include_dict_type,
                        )
                    except (KeyError, ValueError, TypeError):
                        metrics.record_error("parse_error")
                        return build_error_item(
                            word=w,
                            dict_type=dict_type,
                            error="响应解析失败",
                            error_type="parse_error",
                            details="API 返回的数据格式异常，可能是 API 接口发生了变化",
                            from_cache=False,
                            deduped=False,
                            source_word=w,
                            include_dict_type=include_dict_type,
                        )
                    except Exception as e:
                        metrics.record_error("unknown")
                        return build_error_item(
                            word=w,
                            dict_type=dict_type,
                            error="未知错误",
                            error_type="unknown",
                            details=str(e),
                            from_cache=False,
                            deduped=False,
                            source_word=w,
                            include_dict_type=include_dict_type,
                        )

                fetched = await asyncio.gather(*(fetch_one(w) for w in miss_words))
                fetched_by_word = {item["word"]: item for item in fetched}

                for w in miss_words:
                    item = fetched_by_word[w]
                    indices = miss_indices_by_word[w]
                    source_idx = indices[0]
                    for idx in indices:
                        # 去重回填：同一个 miss 词只访问一次上游，但要对重复项标记 deduped/source_word
                        per_item = dict(item)
                        per_item["deduped"] = idx != source_idx
                        per_item["source_word"] = w
                        results[idx] = per_item

    # 记录指标
    latency = time.time() - start_time
    success_count = sum(1 for r in results if r.get("success") is True)
    metrics.record_request(
        success=success_count == len(words),
        latency=latency, 
        endpoint="batch_search"
    )
    
    logger.info(f"批量查询完成: {success_count}/{len(words)} 成功, 耗时 {latency:.3f}s")
    
    return dumps_json(build_batch_payload(dict_type=dict_type, results=results, latency=latency))


@mcp.tool()
async def batch_search_words(
    words: list[str],
    dict_type: DictType = "ko-zh",
    return_cached_json: bool = False,
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
            "partial_success": false,
            "count": 3,
            "success_count": 3,
            "fail_count": 0,
            "dict_type": "ko-zh",
            "results": [
                {
                    "word": "안녕하세요",
                    "success": true,
                    "count": 1,
                    "results": [...],
                    "from_cache": true
                },
                ...
            ],
            "latency": 0.234
        }
    """
    return await _batch_search_words_impl(words, dict_type, return_cached_json)


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
        logger.info(f"运行模式: {config.APP_ENV}")
        logger.info(f"服务器地址: {config.get_server_address()}")
        logger.info(f"日志级别: {config.LOG_LEVEL}")
        logger.info(f"HTTP 超时: {config.HTTP_TIMEOUT}s")
        logger.info(
            "缓存配置: max_size=%s, ttl=%ss, negative_ttl=%ss, key_mode=%s",
            cache.max_size,
            cache.ttl,
            config.CACHE_NEGATIVE_TTL,
            getattr(cache, "key_mode", "unknown"),
        )
        logger.info(
            "批量子项字段: BATCH_ITEM_INCLUDE_DICT_TYPE=%s",
            config.BATCH_ITEM_INCLUDE_DICT_TYPE,
        )
        logger.info(f"限流配置: {rate_limiter.requests_per_minute} 请求/分钟")
        logger.info(
            "连接池配置: max_connections=%s, max_keepalive=%s, keepalive_expiry=%ss",
            config.HTTPX_MAX_CONNECTIONS,
            config.HTTPX_MAX_KEEPALIVE_CONNECTIONS,
            config.HTTPX_KEEPALIVE_EXPIRY,
        )
        logger.info(f"批量并发上限: {config.BATCH_CONCURRENCY}")
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

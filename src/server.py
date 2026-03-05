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
    build_failed_result_item,
    build_grouped_payload,
    build_success_result_item,
    dumps_json,
)

# 初始化 FastMCP 服务器
mcp = FastMCP("Naver Dictionary")

# 全局关闭事件
_shutdown_event: Optional[asyncio.Event] = None
MAX_WORDS_PER_REQUEST = 30


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
) -> str:
    """构建缓存落盘用的成功响应 JSON（字符串）。"""
    payload = {
        "success": True,
        "word": word,
        "dict_type": dict_type,
        "count": len(results),
        "results": results,
    }
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
    - 首次上游请求的令牌消耗由调用方（search_words 的全局限流）负责
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


def _build_input_validation_response(
    *,
    words_count: int,
    dict_type: DictType,
    details: str,
) -> str:
    """构造请求级输入校验失败响应。"""
    payload = build_grouped_payload(
        dict_type=dict_type,
        total_count=words_count,
        successful_results=[],
        failed_results=[
            build_failed_result_item(
                index=-1,
                word="",
                source_word="",
                deduped=False,
                error="输入验证失败",
                error_type="validation",
                details=details,
            )
        ],
        latency=0.0,
    )
    return dumps_json(payload)


def _build_failed_template(
    *,
    word: str,
    error: str,
    error_type: str,
    details: str,
) -> dict[str, Any]:
    """构造统一失败模板。"""
    return {
        "success": False,
        "word": word,
        "error": error,
        "error_type": error_type,
        "details": details,
    }


def _build_http_status_failed_template(word: str, exc: httpx.HTTPStatusError) -> dict[str, Any]:
    """构造 HTTP 状态码错误模板。"""
    status_code = exc.response.status_code
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
        message = error_messages.get(429, "上游请求频率限制")
    elif error_type == "upstream_server_error":
        message = error_messages.get(status_code, f"上游服务错误（HTTP {status_code}）")
    else:
        message = error_messages.get(status_code, f"HTTP 错误 {status_code}")
    return _build_failed_template(
        word=word,
        error=message,
        error_type=error_type,
        details=f"上游返回 HTTP {status_code}: {exc}",
    )


def _failed_template_from_exception(word: str, exc: Exception) -> dict[str, Any]:
    """将异常映射为统一失败模板。"""
    if isinstance(exc, ValidationError):
        metrics.record_error("validation")
        return _build_failed_template(
            word=word,
            error="输入验证失败",
            error_type="validation",
            details=str(exc),
        )
    if isinstance(exc, httpx.TimeoutException):
        metrics.record_error("timeout")
        return _build_failed_template(
            word=word,
            error="请求超时",
            error_type="timeout",
            details=f"API 请求超时，请稍后重试（超时时间: {config.HTTP_TIMEOUT}s）",
        )
    if isinstance(exc, httpx.HTTPStatusError):
        return _build_http_status_failed_template(word, exc)
    if isinstance(exc, httpx.RequestError):
        metrics.record_error("network_error")
        return _build_failed_template(
            word=word,
            error="网络连接错误",
            error_type="network_error",
            details="无法连接到 Naver API，请检查网络连接",
        )
    if isinstance(exc, (KeyError, ValueError, TypeError)):
        metrics.record_error("parse_error")
        return _build_failed_template(
            word=word,
            error="响应解析失败",
            error_type="parse_error",
            details="API 返回的数据格式异常，可能是 API 接口发生了变化",
        )
    metrics.record_error("unknown")
    return _build_failed_template(
        word=word,
        error="未知错误",
        error_type="unknown",
        details=str(exc),
    )


def _fill_rate_limited_items(
    *,
    resolved: list[Optional[dict[str, Any]]],
    miss_indices_by_word: dict[str, list[int]],
    denied_words: dict[str, int],
) -> None:
    """填充被限流的词项。"""
    for word, remaining in denied_words.items():
        indices = miss_indices_by_word[word]
        source_idx = indices[0]
        for idx in indices:
            resolved[idx] = build_failed_result_item(
                index=idx,
                word=word,
                source_word=word,
                deduped=idx != source_idx,
                error="请求频率超限",
                error_type="rate_limit",
                details=f"请求过于频繁，请稍后重试。当前剩余配额: {remaining}",
            )


async def _fetch_one_word(
    *,
    client: NaverClient,
    word: str,
    dict_type: DictType,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    """拉取并缓存单词查询结果，返回成功/失败模板。"""
    try:
        data = await _upstream_search_with_retry(
            client=client,
            word=word,
            dict_type=dict_type,
            semaphore=semaphore,
        )
        parsed = parse_search_results(data)
        cache_json = _build_success_json(word=word, dict_type=dict_type, results=parsed)
        cache.set(word, dict_type, cache_json, ttl=_cache_ttl_for_results(parsed))
        return {"success": True, "word": word, "results": parsed}
    except Exception as exc:
        return _failed_template_from_exception(word, exc)


def _build_grouped_results(
    resolved: list[Optional[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """将逐项结果按成功/失败分组。"""
    successful: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for item in resolved:
        if item is None:
            continue
        if item.get("success") is True:
            successful.append(item)
        else:
            failed.append(item)
    return successful, failed


def _validate_words_or_return_error(words: list[str], dict_type: DictType) -> Optional[str]:
    """校验请求级输入，失败时直接返回响应。"""
    if not words:
        metrics.record_error("validation")
        metrics.record_request(success=False, latency=0.0, endpoint="search_words")
        return _build_input_validation_response(
            words_count=0,
            dict_type=dict_type,
            details="words 不能为空",
        )
    if len(words) > MAX_WORDS_PER_REQUEST:
        metrics.record_error("validation")
        metrics.record_request(success=False, latency=0.0, endpoint="search_words")
        return _build_input_validation_response(
            words_count=len(words),
            dict_type=dict_type,
            details=f"批量查询最多支持 {MAX_WORDS_PER_REQUEST} 个单词，当前 {len(words)} 个",
        )
    return None


def _build_invalid_word_item(index: int, raw_word: str, exc: ValidationError) -> dict[str, Any]:
    """构建单个词项校验失败结果。"""
    metrics.record_error("validation")
    raw = raw_word or ""
    return build_failed_result_item(
        index=index,
        word=raw,
        source_word=raw.strip(),
        deduped=False,
        error="输入验证失败",
        error_type="validation",
        details=str(exc),
    )


def _build_cached_item_or_parse_error(
    *,
    index: int,
    word: str,
    cached_value: Any,
) -> dict[str, Any]:
    """从缓存值构建成功项，缓存格式异常时返回 parse_error。"""
    try:
        cached_data = json.loads(str(cached_value))
        cached_results = cached_data.get("results", [])
        return build_success_result_item(
            index=index,
            word=word,
            source_word=word,
            from_cache=True,
            deduped=False,
            results=cached_results,
        )
    except (TypeError, ValueError, KeyError) as exc:
        metrics.record_error("parse_error")
        return build_failed_result_item(
            index=index,
            word=word,
            source_word=word,
            deduped=False,
            error="响应解析失败",
            error_type="parse_error",
            details=f"缓存数据格式异常: {exc}",
        )


def _collect_initial_items(
    words: list[str],
    dict_type: DictType,
) -> tuple[list[Optional[dict[str, Any]]], dict[str, list[int]]]:
    """处理输入校验、缓存命中与 miss 收集。"""
    resolved: list[Optional[dict[str, Any]]] = [None for _ in words]
    miss_indices_by_word: dict[str, list[int]] = {}
    for idx, raw_word in enumerate(words):
        try:
            normalized_word = _normalize_word(raw_word)
        except ValidationError as exc:
            resolved[idx] = _build_invalid_word_item(idx, raw_word, exc)
            continue

        cached = cache.get(normalized_word, dict_type)
        if cached is not None:
            metrics.record_cache_hit()
            resolved[idx] = _build_cached_item_or_parse_error(
                index=idx,
                word=normalized_word,
                cached_value=cached,
            )
            continue

        metrics.record_cache_miss()
        miss_indices_by_word.setdefault(normalized_word, []).append(idx)
    return resolved, miss_indices_by_word


def _allocate_rate_limit_for_words(miss_words: list[str]) -> tuple[list[str], dict[str, int]]:
    """按词序分配上游配额，允许部分放行。"""
    allowed_words: list[str] = []
    denied_words: dict[str, int] = {}
    for word in miss_words:
        remaining = _check_rate_limit(tokens=1)
        if remaining is None:
            allowed_words.append(word)
            continue
        denied_words[word] = remaining
    return allowed_words, denied_words


async def _fetch_templates_for_words(
    words: list[str],
    dict_type: DictType,
) -> dict[str, dict[str, Any]]:
    """批量拉取词项模板。"""
    if not words:
        return {}
    semaphore = asyncio.Semaphore(config.BATCH_CONCURRENCY)
    async with NaverClient() as client:
        fetched = await asyncio.gather(
            *(
                _fetch_one_word(
                    client=client,
                    word=word,
                    dict_type=dict_type,
                    semaphore=semaphore,
                )
                for word in words
            )
        )
    return {item["word"]: item for item in fetched}


def _fill_fetched_items(
    *,
    resolved: list[Optional[dict[str, Any]]],
    miss_indices_by_word: dict[str, list[int]],
    allowed_words: list[str],
    fetched_by_word: dict[str, dict[str, Any]],
) -> None:
    """将上游查询结果按输入索引回填。"""
    for word in allowed_words:
        template = fetched_by_word[word]
        indices = miss_indices_by_word[word]
        source_idx = indices[0]
        for idx in indices:
            deduped = idx != source_idx
            if template.get("success") is True:
                resolved[idx] = build_success_result_item(
                    index=idx,
                    word=word,
                    source_word=word,
                    from_cache=False,
                    deduped=deduped,
                    results=template.get("results", []),
                )
                continue
            resolved[idx] = build_failed_result_item(
                index=idx,
                word=word,
                source_word=word,
                deduped=deduped,
                error=str(template.get("error", "未知错误")),
                error_type=str(template.get("error_type", "unknown")),
                details=str(template.get("details", "")),
            )


async def _search_words_impl(words: list[str], dict_type: DictType = "ko-zh") -> str:
    """统一单查/批查实现（MCP v2）。"""
    start_time = time.time()
    validation_response = _validate_words_or_return_error(words, dict_type)
    if validation_response is not None:
        return validation_response

    logger.info(f"收到统一查询请求: {len(words)} 个单词, dict_type={dict_type}")
    resolved, miss_indices_by_word = _collect_initial_items(words, dict_type)
    allowed_words, denied_words = _allocate_rate_limit_for_words(list(miss_indices_by_word.keys()))

    _fill_rate_limited_items(
        resolved=resolved,
        miss_indices_by_word=miss_indices_by_word,
        denied_words=denied_words,
    )

    fetched_by_word = await _fetch_templates_for_words(allowed_words, dict_type)
    _fill_fetched_items(
        resolved=resolved,
        miss_indices_by_word=miss_indices_by_word,
        allowed_words=allowed_words,
        fetched_by_word=fetched_by_word,
    )

    successful_results, failed_results = _build_grouped_results(resolved)
    latency = time.time() - start_time
    metrics.record_request(
        success=len(failed_results) == 0,
        latency=latency,
        endpoint="search_words",
    )
    payload = build_grouped_payload(
        dict_type=dict_type,
        total_count=len(words),
        successful_results=successful_results,
        failed_results=failed_results,
        latency=latency,
    )
    logger.info(
        "统一查询完成: %s/%s 成功, 耗时 %.3fs",
        len(successful_results),
        len(words),
        latency,
    )
    return dumps_json(payload)


@mcp.tool()
async def search_words(words: list[str], dict_type: DictType = "ko-zh") -> str:
    """统一查询工具：单查与批查共用 `words` 入参（1..30）。"""
    return await _search_words_impl(words, dict_type)


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

"""MCP v2 响应模型构造器。"""

from __future__ import annotations

import json
from typing import Any


def dumps_json(payload: dict[str, Any]) -> str:
    """统一 JSON 序列化参数（保证中文可读）。"""
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_success_result_item(
    *,
    index: int,
    word: str,
    source_word: str,
    from_cache: bool,
    deduped: bool,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """构造查询成功的子项。"""
    return {
        "success": True,
        "index": index,
        "word": word,
        "source_word": source_word,
        "from_cache": from_cache,
        "deduped": deduped,
        "count": len(results),
        "results": results,
    }


def build_failed_result_item(
    *,
    index: int,
    word: str,
    source_word: str,
    deduped: bool,
    error: str,
    error_type: str,
    details: str,
) -> dict[str, Any]:
    """构造查询失败的子项。"""
    return {
        "success": False,
        "index": index,
        "word": word,
        "source_word": source_word,
        "deduped": deduped,
        "error": error,
        "error_type": error_type,
        "details": details,
    }


def build_grouped_payload(
    *,
    dict_type: str,
    total_count: int,
    successful_results: list[dict[str, Any]],
    failed_results: list[dict[str, Any]],
    latency: float,
) -> dict[str, Any]:
    """构造 MCP v2 顶层返回。"""
    success_count = len(successful_results)
    fail_count = len(failed_results)
    return {
        "success": fail_count == 0,
        "partial_success": success_count > 0 and fail_count > 0,
        "total_count": total_count,
        "success_count": success_count,
        "fail_count": fail_count,
        "dict_type": dict_type,
        "successful_results": successful_results,
        "failed_results": failed_results,
        "latency": latency,
    }



"""响应模型与构造器（统一单查/批查字段）。

这里集中管理 JSON 响应的字段与构造逻辑，避免 `search_word` 与 `batch_search_words`
各自拼装导致字段不一致、调用方难以消费的问题。
"""

from __future__ import annotations

import json
from typing import Any, Optional


def dumps_json(payload: dict[str, Any]) -> str:
    """统一 JSON 序列化参数（保证中文可读）。"""

    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_success_item(
    *,
    word: str,
    dict_type: str,
    results: list[dict[str, Any]],
    from_cache: bool,
    deduped: bool,
    source_word: str,
    include_dict_type: bool = True,
) -> dict[str, Any]:
    """构造单词查询成功响应（单查与批查子项共用）。"""

    payload: dict[str, Any] = {
        "success": True,
        "word": word,
        "count": len(results),
        "results": results,
        "from_cache": from_cache,
        "deduped": deduped,
        "source_word": source_word,
    }
    if include_dict_type:
        payload["dict_type"] = dict_type
    return payload


def build_error_item(
    *,
    word: str,
    dict_type: str,
    error: str,
    error_type: str,
    details: str,
    from_cache: bool,
    deduped: bool,
    source_word: str,
    include_dict_type: bool = True,
) -> dict[str, Any]:
    """构造单词查询失败响应（单查与批查子项共用）。"""

    payload: dict[str, Any] = {
        "success": False,
        "word": word,
        "error": error,
        "error_type": error_type,
        "details": details,
        "from_cache": from_cache,
        "deduped": deduped,
        "source_word": source_word,
    }
    if include_dict_type:
        payload["dict_type"] = dict_type
    return payload


def build_cached_json_item(
    *,
    word: str,
    dict_type: str,
    cached_json: str,
    deduped: bool,
    source_word: str,
    include_dict_type: bool = True,
) -> dict[str, Any]:
    """构造缓存命中 + 直接返回 cached_json 的子项（避免反序列化与拼装）。

    注意：该模式下为了性能，允许不返回 count/results（由调用方自行解析 cached_json）。
    """

    payload: dict[str, Any] = {
        "success": True,
        "word": word,
        "from_cache": True,
        "cached_json": cached_json,
        "deduped": deduped,
        "source_word": source_word,
    }
    if include_dict_type:
        payload["dict_type"] = dict_type
    return payload


def build_batch_payload(
    *,
    dict_type: str,
    results: list[dict[str, Any]],
    latency: float,
) -> dict[str, Any]:
    """构造批量查询的顶层响应。"""

    success_count = sum(1 for r in results if r.get("success") is True)
    fail_count = len(results) - success_count
    return {
        "success": success_count == len(results),
        "partial_success": (success_count > 0 and success_count < len(results)),
        "count": len(results),
        "success_count": success_count,
        "fail_count": fail_count,
        "dict_type": dict_type,
        "results": results,
        "latency": latency,
    }


def patch_from_cache_flag(payload_json: str, from_cache: bool) -> str:
    """在不反序列化 JSON 的情况下，尽量将 from_cache 字段修正为目标值。

    用于 `search_word` 的缓存命中路径：缓存里存储的是 from_cache=false 的“规范响应”，
    返回给调用方时需要将 from_cache 纠正为 true。
    """

    desired = "true" if from_cache else "false"

    # 1) 已包含 from_cache 字段：做最小替换
    if '"from_cache":' in payload_json:
        # 优先替换常见的 true/false 形态（仅替换第一个命中）
        if from_cache:
            if '"from_cache": true' in payload_json:
                return payload_json
            return payload_json.replace('"from_cache": false', '"from_cache": true', 1)
        if '"from_cache": false' in payload_json:
            return payload_json
        return payload_json.replace('"from_cache": true', '"from_cache": false', 1)

    # 2) 未包含：插入到 "success": true 之后（保持 JSON 合法）
    marker = '"success": true,'
    if marker in payload_json:
        return payload_json.replace(
            marker, f'{marker} "from_cache": {desired},', 1
        )

    # 3) 兜底：不修改（避免破坏不可预期的 JSON）
    return payload_json



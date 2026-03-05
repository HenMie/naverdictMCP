"""Naver 辞典 API 响应 JSON 解析器。

提供从 API 响应中提取和格式化词典数据的功能。
"""

import html
import re
from typing import Any, Dict, List, Union


def decode_html_entities(text: str) -> str:
    """
    解码 HTML 实体编码（如 &lt; → <, &quot; → "）。
    
    Args:
        text: 包含 HTML 实体的文本
        
    Returns:
        解码后的纯文本
    """
    if not text:
        return ""
    return html.unescape(text)


def extract_related_words(text: str) -> List[str]:
    """
    提取近义词/相关词。
    
    从 <span class="related_word" lang="ko">궤붕하다(潰崩--)</span> 提取文本内容。
    
    Args:
        text: 包含 HTML 标签的文本
        
    Returns:
        相关词列表
    """
    if not text:
        return []
    
    # 匹配 <span class="related_word"...>...</span>
    pattern = r'<span\s+class="related_word"[^>]*>(.*?)</span>'
    matches = re.findall(pattern, text, re.IGNORECASE)
    
    # 清理提取的文本
    return [decode_html_entities(match.strip()) for match in matches if match.strip()]


def extract_text_from_autolink(text: str) -> str:
    """
    处理 autoLink 标签，提取纯文本。
    
    将 <autoLink search="使">使</autoLink> 转换为 "使"。
    
    Args:
        text: 包含 autoLink 标签的文本
        
    Returns:
        清理后的文本
    """
    if not text:
        return ""
    
    # 移除 autoLink 标签但保留内容
    text = re.sub(r'<autoLink[^>]*>(.*?)</autoLink>', r'\1', text, flags=re.IGNORECASE)
    return text


def clean_html_tags(text: str) -> str:
    """
    清理 HTML 标签，先处理特殊标签再移除所有标签。
    
    Args:
        text: 包含 HTML 的原始文本
        
    Returns:
        清理后的纯文本
    """
    if not text:
        return ""
    
    # 1. 处理 autoLink 标签
    text = extract_text_from_autolink(text)
    
    # 2. 解码 HTML 实体
    text = decode_html_entities(text)
    
    # 3. 移除所有剩余的 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    
    return text.strip()


def _strip_html_tags(text: str) -> str:
    """移除 HTML 标签（保留向后兼容）。"""
    return clean_html_tags(text)


def _dedupe_keep_order(values: List[str], max_items: int = 0) -> List[str]:
    """按输入顺序去重，可选限制最大数量。"""
    seen: set[str] = set()
    deduped: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
        if max_items > 0 and len(deduped) >= max_items:
            break
    return deduped


def _meaning_key(meaning: Union[str, Dict[str, Any]]) -> str:
    """生成释义去重 key。"""
    if isinstance(meaning, dict):
        return str(meaning.get("text", ""))
    return meaning


def _extract_meanings_and_related(
    means_collector: List[Dict[str, Any]],
    source_type: str,
) -> tuple[List[Union[str, Dict[str, Any]]], List[str]]:
    """提取释义与相关词。"""
    meanings: List[Union[str, Dict[str, Any]]] = []
    related_words_all: List[str] = []

    for collector in means_collector:
        pos2 = clean_html_tags(str(collector.get("partOfSpeech2", "")))
        for mean in collector.get("means", []):
            meaning_value = str(mean.get("value", ""))
            if not meaning_value:
                continue
            related_words = extract_related_words(meaning_value)
            related_words_all.extend(related_words)

            clean_text = clean_html_tags(meaning_value)
            formatted_text = f"[{pos2}] {clean_text}" if pos2 else clean_text
            if source_type == "OPEN":
                formatted_text = f"[OPEN] {formatted_text}"

            if related_words:
                meanings.append(
                    {
                        "text": formatted_text,
                        "related_words": _dedupe_keep_order(related_words),
                        "source_type": source_type,
                    }
                )
            else:
                meanings.append(formatted_text)

    return meanings, _dedupe_keep_order(related_words_all)


def _extract_examples(means_collector: List[Dict[str, Any]]) -> List[str]:
    """从 meansCollector 提取并去重例句。"""
    examples: List[str] = []
    for collector in means_collector:
        for mean in collector.get("means", []):
            example_ori = clean_html_tags(str(mean.get("exampleOri", "")))
            example_trans = clean_html_tags(str(mean.get("exampleTrans", "")))
            if not example_ori:
                continue
            if example_trans:
                examples.append(f"{example_ori} → {example_trans}")
            else:
                examples.append(example_ori)
    return _dedupe_keep_order(examples, max_items=5)


def _extract_pronunciation(item: Dict[str, Any]) -> str:
    """提取发音字段。"""
    pron_list = item.get("searchPhoneticSymbolList", [])
    if not isinstance(pron_list, list) or not pron_list:
        return ""
    return _strip_html_tags(str(pron_list[0].get("symbolValue", "")))


def _extract_word(item: Dict[str, Any]) -> str:
    """提取词条文本。"""
    raw_word = item.get("expEntry") or item.get("entryName") or item.get("entry") or ""
    return _strip_html_tags(str(raw_word))


def _parse_section_items(items: List[Dict[str, Any]], source_type: str) -> List[Dict[str, Any]]:
    """解析单个 section（WORD/OPEN）的 items。"""
    parsed: List[Dict[str, Any]] = []
    for item in items:
        word = _extract_word(item)
        if not word:
            continue
        means_collector = item.get("meansCollector", [])
        if not isinstance(means_collector, list):
            means_collector = []

        meanings, related_words = _extract_meanings_and_related(means_collector, source_type)
        parsed.append(
            {
                "word": word,
                "pronunciation": _extract_pronunciation(item),
                "meanings": meanings,
                "examples": _extract_examples(means_collector),
                "related_words": related_words,
                "source_type": source_type,
                "source_types": [source_type],
            }
        )
    return parsed


def _merge_entries(base: Dict[str, Any], incoming: Dict[str, Any]) -> None:
    """按词条合并多个来源结果。"""
    if not base.get("pronunciation") and incoming.get("pronunciation"):
        base["pronunciation"] = incoming["pronunciation"]

    meaning_seen = {_meaning_key(m) for m in base.get("meanings", [])}
    for meaning in incoming.get("meanings", []):
        key = _meaning_key(meaning)
        if key in meaning_seen:
            continue
        meaning_seen.add(key)
        base.setdefault("meanings", []).append(meaning)

    merged_examples = base.get("examples", []) + incoming.get("examples", [])
    base["examples"] = _dedupe_keep_order(merged_examples, max_items=5)

    merged_related = base.get("related_words", []) + incoming.get("related_words", [])
    base["related_words"] = _dedupe_keep_order(merged_related)

    source_types = set(base.get("source_types", [])) | set(incoming.get("source_types", []))
    base["source_types"] = sorted(source_types)
    base["source_type"] = "WORD" if "WORD" in source_types else "OPEN"


def parse_search_results(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    解析 Naver 辞典 API 的 JSON 响应。
    
    API 响应结构:
        {
            "searchResultMap": {
                "searchResultListMap": {
                    "WORD": {
                        "items": [...]
                    },
                    "OPEN": {
                        "items": [...]
                    }
                }
            }
        }
    
    Args:
        data: API 返回的 JSON 响应
        
    Returns:
        包含单词信息的字典列表:
        - word: 单词/短语
        - pronunciation: 发音
        - pos: 词性
        - meanings: 释义列表
        - examples: 例句列表
    """
    results: List[Dict[str, Any]] = []

    search_result_map = data.get("searchResultMap", {})
    search_result_list_map = search_result_map.get("searchResultListMap", {})

    word_items = search_result_list_map.get("WORD", {}).get("items", [])
    open_items = search_result_list_map.get("OPEN", {}).get("items", [])

    if isinstance(word_items, list):
        results.extend(_parse_section_items(word_items, "WORD"))
    if isinstance(open_items, list):
        results.extend(_parse_section_items(open_items, "OPEN"))

    merged: Dict[str, Dict[str, Any]] = {}
    for result in results:
        key = str(result.get("word", ""))
        if key == "":
            continue
        if key not in merged:
            merged[key] = dict(result)
            continue
        _merge_entries(merged[key], result)

    return list(merged.values())


def format_results(results: List[Dict[str, Any]]) -> str:
    """
    将解析结果格式化为可读字符串。
    
    Args:
        results: 解析后的单词字典列表
        
    Returns:
        格式化的字符串表示
    """
    if not results:
        return "未找到相关结果"
    
    output = []
    for i, result in enumerate(results, 1):
        lines = [f"\n【{i}】 {result.get('word', 'N/A')}"]

        if result.get("source_types"):
            lines.append(f"来源: {'/'.join(result['source_types'])}")
        
        if result.get("pronunciation"):
            lines.append(f"发音: {result['pronunciation']}")
        
        if result.get("meanings"):
            lines.append("释义:")
            for j, meaning in enumerate(result["meanings"], 1):
                # 支持新旧两种格式：字符串或字典
                if isinstance(meaning, dict):
                    # 新格式：包含 text 和 related_words
                    lines.append(f"  {j}. {meaning['text']}")
                    if meaning.get("related_words"):
                        related = ", ".join(meaning["related_words"])
                        lines.append(f"     (≒ {related})")
                else:
                    # 旧格式：简单字符串（向后兼容）
                    lines.append(f"  {j}. {meaning}")
        
        if result.get("examples"):
            lines.append("例句:")
            # 每个条目最多显示 5 个例句
            for example in result["examples"][:5]:
                lines.append(f"  • {example}")

        if result.get("related_words"):
            lines.append(f"相关词: {', '.join(result['related_words'])}")
        
        output.append("\n".join(lines))
    
    return "\n".join(output)

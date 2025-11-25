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
    results = []
    
    search_result_map = data.get("searchResultMap", {})
    search_result_list_map = search_result_map.get("searchResultListMap", {})
    
    # 从 WORD 部分获取条目（官方词典）
    word_section = search_result_list_map.get("WORD", {})
    items = word_section.get("items", [])
    
    for item in items:
        result: Dict[str, Any] = {}
        
        # 提取基本信息
        exp_entry = item.get("expEntry", "")
        result["word"] = _strip_html_tags(exp_entry)
        
        # 从 searchPhoneticSymbolList 提取发音
        pron_list = item.get("searchPhoneticSymbolList", [])
        if pron_list:
            pron_value = pron_list[0].get("symbolValue", "")
            result["pronunciation"] = _strip_html_tags(pron_value)
        else:
            result["pronunciation"] = ""
        
        # 从 meansCollector 提取释义
        meanings: List[Union[str, Dict[str, Any]]] = []
        means_collector = item.get("meansCollector", [])
        
        for collector in means_collector:
            # 获取词性
            pos2 = collector.get("partOfSpeech2", "")
            
            # 获取释义
            means_list = collector.get("means", [])
            for mean in means_list:
                meaning_value = mean.get("value", "")
                if meaning_value:
                    # 提取相关词
                    related_words = extract_related_words(meaning_value)
                    
                    # 清理 HTML 得到纯文本
                    clean_text = clean_html_tags(meaning_value)
                    
                    # 格式化：[词性] 释义
                    if pos2:
                        formatted_text = f"[{pos2}] {clean_text}"
                    else:
                        formatted_text = clean_text
                    
                    # 构建结构化数据
                    if related_words:
                        meanings.append({
                            "text": formatted_text,
                            "related_words": related_words
                        })
                    else:
                        # 如果没有相关词，保持简单字符串格式（向后兼容）
                        meanings.append(formatted_text)
        
        result["meanings"] = meanings
        
        # 从 meansCollector 提取例句
        examples: List[str] = []
        for collector in means_collector:
            means_list = collector.get("means", [])
            for mean in means_list:
                example_ori = mean.get("exampleOri", "")
                example_trans = mean.get("exampleTrans", "")
                
                if example_ori:
                    # 使用 clean_html_tags 处理 HTML 实体和 autoLink
                    example_ori_clean = clean_html_tags(example_ori)
                    example_trans_clean = clean_html_tags(example_trans) if example_trans else ""
                    
                    if example_trans_clean:
                        examples.append(f"{example_ori_clean} → {example_trans_clean}")
                    else:
                        examples.append(example_ori_clean)
        
        result["examples"] = examples
        
        # 只有找到单词时才添加
        if result.get("word"):
            results.append(result)
    
    return results


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
            # 每个条目最多显示 3 个例句
            for example in result["examples"][:3]:
                lines.append(f"  • {example}")
        
        output.append("\n".join(lines))
    
    return "\n".join(output)

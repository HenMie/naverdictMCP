"""JSON parser for Naver Dictionary API responses."""

from typing import List, Dict, Any, Union
import re
import html


def decode_html_entities(text: str) -> str:
    """解码HTML实体编码（如 &lt; → <, &quot; → "）"""
    if not text:
        return ""
    return html.unescape(text)


def extract_related_words(text: str) -> List[str]:
    """
    提取近义词/相关词。
    从 <span class="related_word" lang="ko">궤붕하다(潰崩--)</span> 提取文本内容。
    
    Args:
        text: 包含HTML标签的文本
        
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
    处理autoLink标签，提取纯文本。
    <autoLink search="使">使</autoLink> → 使
    
    Args:
        text: 包含autoLink标签的文本
        
    Returns:
        清理后的文本
    """
    if not text:
        return ""
    
    # 移除autoLink标签但保留内容
    text = re.sub(r'<autoLink[^>]*>(.*?)</autoLink>', r'\1', text, flags=re.IGNORECASE)
    return text


def clean_html_tags(text: str) -> str:
    """
    清理HTML标签，先处理特殊标签再移除所有标签。
    
    Args:
        text: 包含HTML的原始文本
        
    Returns:
        清理后的纯文本
    """
    if not text:
        return ""
    
    # 1. 处理autoLink标签
    text = extract_text_from_autolink(text)
    
    # 2. 解码HTML实体
    text = decode_html_entities(text)
    
    # 3. 移除所有剩余的HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    
    return text.strip()


def _strip_html_tags(text: str) -> str:
    """移除HTML标签（保留向后兼容）"""
    return clean_html_tags(text)


def parse_search_results(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse JSON response from Naver Dictionary API.
    
    Args:
        data: JSON response from the API
        
    Returns:
        List of dictionaries containing word information:
        - word: The word/phrase
        - pronunciation: Pronunciation
        - pos: Part of speech
        - meanings: List of meanings/translations
        - examples: List of example sentences
    """
    results = []
    
    # The actual API structure is:
    # {
    #   "searchResultMap": {
    #     "searchResultListMap": {
    #       "WORD": {
    #         "items": [...]
    #       },
    #       "OPEN": {
    #         "items": [...]
    #       }
    #     }
    #   }
    # }
    
    search_result_map = data.get("searchResultMap", {})
    search_result_list_map = search_result_map.get("searchResultListMap", {})
    
    # Get items from WORD section (official dictionary)
    word_section = search_result_list_map.get("WORD", {})
    items = word_section.get("items", [])
    
    for item in items:
        result = {}
        
        # Extract basic info
        exp_entry = item.get("expEntry", "")
        result["word"] = _strip_html_tags(exp_entry)
        
        # Extract pronunciation from searchPhoneticSymbolList
        pron_list = item.get("searchPhoneticSymbolList", [])
        if pron_list:
            pron_value = pron_list[0].get("symbolValue", "")
            result["pronunciation"] = _strip_html_tags(pron_value)
        else:
            result["pronunciation"] = ""
        
        # Extract meanings from meansCollector
        meanings = []
        means_collector = item.get("meansCollector", [])
        
        for collector in means_collector:
            # Get part of speech
            pos = collector.get("partOfSpeech", "")
            pos2 = collector.get("partOfSpeech2", "")
            
            # Get meanings
            means_list = collector.get("means", [])
            for mean in means_list:
                meaning_value = mean.get("value", "")
                if meaning_value:
                    # 提取相关词
                    related_words = extract_related_words(meaning_value)
                    
                    # 清理HTML得到纯文本
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
        
        # Extract examples from meansCollector
        examples = []
        for collector in means_collector:
            means_list = collector.get("means", [])
            for mean in means_list:
                example_ori = mean.get("exampleOri", "")
                example_trans = mean.get("exampleTrans", "")
                
                if example_ori:
                    # 使用新的clean_html_tags处理HTML实体和autoLink
                    example_ori_clean = clean_html_tags(example_ori)
                    example_trans_clean = clean_html_tags(example_trans) if example_trans else ""
                    
                    if example_trans_clean:
                        examples.append(f"{example_ori_clean} → {example_trans_clean}")
                    else:
                        examples.append(example_ori_clean)
        
        result["examples"] = examples
        
        if result.get("word"):  # Only add if we found a word
            results.append(result)
    
    return results


def format_results(results: List[Dict[str, Any]]) -> str:
    """
    Format parsed results into a readable string.
    
    Args:
        results: List of parsed word dictionaries
        
    Returns:
        Formatted string representation
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
                    # 新格式：包含text和related_words
                    lines.append(f"  {j}. {meaning['text']}")
                    if meaning.get("related_words"):
                        related = ", ".join(meaning["related_words"])
                        lines.append(f"     (≒ {related})")
                else:
                    # 旧格式：简单字符串（向后兼容）
                    lines.append(f"  {j}. {meaning}")
        
        if result.get("examples"):
            lines.append("例句:")
            # Limit to 3 examples per entry
            for example in result["examples"][:3]:
                lines.append(f"  • {example}")
        
        output.append("\n".join(lines))
    
    return "\n".join(output)

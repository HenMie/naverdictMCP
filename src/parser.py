"""JSON parser for Naver Dictionary API responses."""

from typing import List, Dict, Any
import re


def _strip_html_tags(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r'<[^>]+>', '', text) if text else ""


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
                    # Format: [词性] 释义
                    if pos2:
                        meanings.append(f"[{pos2}] {meaning_value}")
                    else:
                        meanings.append(meaning_value)
        
        result["meanings"] = meanings
        
        # Extract examples from meansCollector
        examples = []
        for collector in means_collector:
            means_list = collector.get("means", [])
            for mean in means_list:
                example_ori = mean.get("exampleOri", "")
                example_trans = mean.get("exampleTrans", "")
                
                if example_ori:
                    example_ori_clean = _strip_html_tags(example_ori)
                    if example_trans:
                        examples.append(f"{example_ori_clean} → {example_trans}")
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
                lines.append(f"  {j}. {meaning}")
        
        if result.get("examples"):
            lines.append("例句:")
            # Limit to 3 examples per entry
            for example in result["examples"][:3]:
                lines.append(f"  • {example}")
        
        output.append("\n".join(lines))
    
    return "\n".join(output)

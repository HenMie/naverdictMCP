"""Tests for parser module."""

import pytest
from src.parser import _strip_html_tags, parse_search_results, format_results


class TestStripHtmlTags:
    """Tests for HTML tag stripping."""
    
    def test_strip_simple_tags(self):
        """Test stripping simple HTML tags."""
        text = "<b>Hello</b> <i>World</i>"
        assert _strip_html_tags(text) == "Hello World"
    
    def test_strip_nested_tags(self):
        """Test stripping nested HTML tags."""
        text = "<div><span>Test</span></div>"
        assert _strip_html_tags(text) == "Test"
    
    def test_strip_tags_with_attributes(self):
        """Test stripping tags with attributes."""
        text = '<a href="test.html">Link</a>'
        assert _strip_html_tags(text) == "Link"
    
    def test_empty_string(self):
        """Test with empty string."""
        assert _strip_html_tags("") == ""
    
    def test_none_value(self):
        """Test with None value."""
        assert _strip_html_tags(None) == ""
    
    def test_no_tags(self):
        """Test text without HTML tags."""
        text = "Plain text"
        assert _strip_html_tags(text) == "Plain text"


class TestParseSearchResults:
    """Tests for API response parsing."""
    
    def test_parse_valid_response(self, sample_api_response):
        """Test parsing valid API response."""
        results = parse_search_results(sample_api_response)
        
        assert len(results) == 1
        assert results[0]["word"] == "안녕하세요"
        assert results[0]["pronunciation"] == "[안녕하세요]"
        assert len(results[0]["meanings"]) == 1
        assert results[0]["meanings"][0] == "[感叹词] 你好"
        assert len(results[0]["examples"]) == 1
    
    def test_parse_empty_response(self, empty_api_response):
        """Test parsing empty API response."""
        results = parse_search_results(empty_api_response)
        assert results == []
    
    def test_parse_missing_fields(self):
        """Test parsing response with missing fields."""
        data = {
            "searchResultMap": {
                "searchResultListMap": {
                    "WORD": {
                        "items": [
                            {
                                "expEntry": "테스트"
                                # Missing other fields
                            }
                        ]
                    }
                }
            }
        }
        results = parse_search_results(data)
        
        assert len(results) == 1
        assert results[0]["word"] == "테스트"
        assert results[0]["pronunciation"] == ""
        assert results[0]["meanings"] == []
        assert results[0]["examples"] == []
    
    def test_parse_malformed_response(self):
        """Test parsing malformed response."""
        data = {"invalid": "structure"}
        results = parse_search_results(data)
        assert results == []
    
    def test_parse_multiple_items(self):
        """Test parsing response with multiple items."""
        data = {
            "searchResultMap": {
                "searchResultListMap": {
                    "WORD": {
                        "items": [
                            {
                                "expEntry": "단어1",
                                "searchPhoneticSymbolList": [],
                                "meansCollector": []
                            },
                            {
                                "expEntry": "단어2",
                                "searchPhoneticSymbolList": [],
                                "meansCollector": []
                            }
                        ]
                    }
                }
            }
        }
        results = parse_search_results(data)
        assert len(results) == 2
        assert results[0]["word"] == "단어1"
        assert results[1]["word"] == "단어2"


class TestFormatResults:
    """Tests for result formatting."""
    
    def test_format_single_result(self, sample_parsed_result):
        """Test formatting single result."""
        output = format_results(sample_parsed_result)
        
        assert "【1】 안녕하세요" in output
        assert "发音: [안녕하세요]" in output
        assert "释义:" in output
        assert "[感叹词] 你好" in output
        assert "例句:" in output
    
    def test_format_empty_results(self):
        """Test formatting empty results."""
        output = format_results([])
        assert output == "未找到相关结果"
    
    def test_format_multiple_results(self):
        """Test formatting multiple results."""
        results = [
            {
                "word": "단어1",
                "pronunciation": "[단어1]",
                "meanings": ["意思1"],
                "examples": []
            },
            {
                "word": "단어2",
                "pronunciation": "",
                "meanings": ["意思2", "意思3"],
                "examples": ["例句1"]
            }
        ]
        output = format_results(results)
        
        assert "【1】 단어1" in output
        assert "【2】 단어2" in output
        assert "意思1" in output
        assert "意思2" in output
        assert "意思3" in output
    
    def test_format_limits_examples(self):
        """Test that formatting limits examples to 3."""
        results = [
            {
                "word": "테스트",
                "pronunciation": "",
                "meanings": ["测试"],
                "examples": ["例1", "例2", "例3", "例4", "例5"]
            }
        ]
        output = format_results(results)
        
        # Should only show first 3 examples
        assert "例1" in output
        assert "例2" in output
        assert "例3" in output
        assert "例4" not in output
        assert "例5" not in output
    
    def test_format_missing_optional_fields(self):
        """Test formatting with missing optional fields."""
        results = [
            {
                "word": "테스트",
                "pronunciation": "",
                "meanings": [],
                "examples": []
            }
        ]
        output = format_results(results)
        
        assert "【1】 테스트" in output
        # Should not show empty sections
        assert "发音:" not in output

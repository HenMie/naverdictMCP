"""Pytest configuration and shared fixtures."""

import pytest
import json
from pathlib import Path


@pytest.fixture
def sample_api_response():
    """Sample API response for testing parser."""
    return {
        "searchResultMap": {
            "searchResultListMap": {
                "WORD": {
                    "items": [
                        {
                            "expEntry": "안녕하세요",
                            "searchPhoneticSymbolList": [
                                {"symbolValue": "[안녕하세요]"}
                            ],
                            "meansCollector": [
                                {
                                    "partOfSpeech": "감탄사",
                                    "partOfSpeech2": "感叹词",
                                    "means": [
                                        {
                                            "value": "你好",
                                            "exampleOri": "안녕하세요, 만나서 반갑습니다.",
                                            "exampleTrans": "你好,很高兴见到你。"
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            }
        }
    }


@pytest.fixture
def empty_api_response():
    """Empty API response for testing."""
    return {
        "searchResultMap": {
            "searchResultListMap": {
                "WORD": {
                    "items": []
                }
            }
        }
    }


@pytest.fixture
def sample_parsed_result():
    """Sample parsed result for testing formatter."""
    return [
        {
            "word": "안녕하세요",
            "pronunciation": "[안녕하세요]",
            "meanings": ["[感叹词] 你好"],
            "examples": ["안녕하세요, 만나서 반갑습니다. → 你好,很高兴见到你。"]
        }
    ]

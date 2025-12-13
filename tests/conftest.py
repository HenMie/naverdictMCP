"""Pytest configuration and shared fixtures."""

import pytest


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


@pytest.fixture
def mock_cache():
    """Provide a fresh cache instance for testing."""
    from src.cache import TTLCache
    return TTLCache(max_size=100, ttl=60)


@pytest.fixture
def mock_metrics():
    """Provide a fresh metrics instance for testing."""
    from src.metrics import Metrics
    m = Metrics()
    yield m
    m.reset()


@pytest.fixture(scope="function")
async def cleanup_resources():
    """Cleanup resources after each test."""
    yield
    # Cleanup shared resources
    try:
        from src.cache import cache
        from src.metrics import metrics
        cache.clear()
        metrics.reset()
    except ImportError:
        pass

"""Pytest configuration and shared fixtures."""

import pytest
import json
import asyncio
import time
from pathlib import Path
from multiprocessing import Process
import httpx
import sys
import os


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


def run_test_server():
    """Run server in separate process for integration tests."""
    # Add parent directory to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from src.server import mcp
    from src.config import config
    
    # Use different port for testing
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8001,
        stateless_http=True
    )


@pytest.fixture(scope="session")
def test_server():
    """
    Start server for integration tests (session scope).
    
    Yields:
        Base URL of the test server
    """
    server_process = Process(target=run_test_server)
    server_process.start()
    
    # Wait for server to start (max 10 seconds)
    server_url = "http://127.0.0.1:8001"
    for i in range(100):  # 10 seconds total
        try:
            response = httpx.get(f"{server_url}/health", timeout=0.1)
            if response.status_code == 200:
                print(f"\n测试服务器已启动: {server_url}")
                break
        except:
            time.sleep(0.1)
    else:
        server_process.terminate()
        pytest.fail("测试服务器启动失败")
    
    yield server_url
    
    # Cleanup
    print("\n正在关闭测试服务器...")
    server_process.terminate()
    server_process.join(timeout=5)
    if server_process.is_alive():
        server_process.kill()


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

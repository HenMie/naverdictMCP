"""Integration tests for MCP server over HTTP.

This module contains integration tests that verify the MCP server's
functionality when running in HTTP mode. These tests require the server
to be running on http://127.0.0.1:8000.
"""

import httpx
import asyncio
import json
import pytest


def parse_sse_response(text: str) -> dict:
    """Parse Server-Sent Events (SSE) response.
    
    Args:
        text: Raw SSE response text
        
    Returns:
        Parsed JSON data from the SSE response
    """
    lines = text.strip().split('\n')
    data_lines = [line[6:] for line in lines if line.startswith('data: ')]
    if data_lines:
        return json.loads(data_lines[0])
    return None


class TestMCPIntegration:
    """Integration tests for MCP server HTTP transport."""
    
    BASE_URL = "http://127.0.0.1:8000/mcp"
    HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    TIMEOUT = 30.0
    
    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test MCP protocol initialization."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(self.BASE_URL, headers=self.HEADERS, json=payload)
            
            assert response.status_code == 200
            data = parse_sse_response(response.text)
            assert data is not None
            assert 'error' not in data
            assert 'result' in data
    
    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test listing available MCP tools."""
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(self.BASE_URL, headers=self.HEADERS, json=payload)
            
            assert response.status_code == 200
            data = parse_sse_response(response.text)
            assert data is not None
            assert 'error' not in data
            assert 'result' in data
            assert 'tools' in data['result']
            
            # Verify search_word tool exists
            tools = data['result']['tools']
            tool_names = [tool['name'] for tool in tools]
            assert 'search_word' in tool_names
    
    @pytest.mark.asyncio
    async def test_search_word_korean_chinese(self):
        """Test Korean-Chinese dictionary search."""
        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "search_word",
                "arguments": {
                    "word": "안녕",
                    "dict_type": "ko-zh"
                }
            }
        }
        
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(self.BASE_URL, headers=self.HEADERS, json=payload)
            
            assert response.status_code == 200
            data = parse_sse_response(response.text)
            assert data is not None
            assert 'error' not in data
            assert 'result' in data
    
    @pytest.mark.asyncio
    async def test_search_word_korean_english(self):
        """Test Korean-English dictionary search."""
        payload = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "search_word",
                "arguments": {
                    "word": "학교",
                    "dict_type": "ko-en"
                }
            }
        }
        
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(self.BASE_URL, headers=self.HEADERS, json=payload)
            
            assert response.status_code == 200
            data = parse_sse_response(response.text)
            assert data is not None
            assert 'error' not in data
            assert 'result' in data
    
    @pytest.mark.asyncio
    async def test_search_word_default_dict_type(self):
        """Test search with default dictionary type (should be ko-zh)."""
        payload = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "search_word",
                "arguments": {
                    "word": "사랑"
                }
            }
        }
        
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(self.BASE_URL, headers=self.HEADERS, json=payload)
            
            assert response.status_code == 200
            data = parse_sse_response(response.text)
            assert data is not None
            assert 'error' not in data
            assert 'result' in data


# Standalone test runner for manual testing
async def run_integration_tests():
    """Run integration tests manually without pytest."""
    print("="*70)
    print(" Naver Dictionary MCP 服务器集成测试")
    print("="*70)
    
    test_suite = TestMCPIntegration()
    tests = [
        ("初始化 MCP 会话", test_suite.test_initialize),
        ("列出可用工具", test_suite.test_list_tools),
        ("查询韩中辞典 (안녕)", test_suite.test_search_word_korean_chinese),
        ("查询韩英辞典 (학교)", test_suite.test_search_word_korean_english),
        ("默认辞典类型 (사랑)", test_suite.test_search_word_default_dict_type),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n【测试】{name}")
        print("-"*70)
        try:
            await test_func()
            print("✅ 通过")
            results.append((name, True))
        except Exception as e:
            print(f"❌ 失败: {e}")
            results.append((name, False))
    
    # Print summary
    print("\n" + "="*70)
    print(" 测试总结")
    print("="*70)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"\n总计: {passed}/{total} 测试通过 ({passed/total*100:.1f}%)\n")
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status} - {test_name}")
    
    print("\n" + "="*70)
    return passed == total


if __name__ == "__main__":
    print("提示: 确保 MCP 服务器正在运行")
    print("运行命令: python src/server.py\n")
    success = asyncio.run(run_integration_tests())
    exit(0 if success else 1)

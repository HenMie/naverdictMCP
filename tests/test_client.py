"""Tests for the request-scoped Naver gateway."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from src.client import DictionaryError, NaverDictionaryGateway
from src.config import Settings

VALID_KEY = "a" * 32


def make_settings(**overrides: Any) -> Settings:
    return Settings(
        mcp_api_key=VALID_KEY,
        naver_base_url="https://naver.test/api3",
        retry_base_delay_seconds=0,
        retry_max_delay_seconds=0,
        **overrides,
    )


@pytest.mark.asyncio
async def test_search_builds_expected_naver_request(sample_api_response: dict[str, Any]) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api3/kozh/search"
        assert request.url.params["query"] == "안녕"
        assert request.url.params["lang"] == "zh_CN"
        return httpx.Response(200, json=sample_api_response)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NaverDictionaryGateway(client, make_settings())
        entries = await gateway.search("안녕", "ko-zh")

    assert entries[0].word == "안녕하세요"


@pytest.mark.asyncio
async def test_retryable_status_is_retried(sample_api_response: dict[str, Any]) -> None:
    call_count = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, json=sample_api_response)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NaverDictionaryGateway(client, make_settings())
        await gateway.search("안녕", "ko-zh")

    assert call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [
        (429, "upstream_rate_limit"),
        (503, "upstream_server_error"),
        (404, "upstream_response_error"),
    ],
)
async def test_http_failures_have_stable_codes(status_code: int, expected_code: str) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text="failure")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NaverDictionaryGateway(client, make_settings())
        with pytest.raises(DictionaryError) as captured:
            await gateway.search("안녕", "ko-en")

    assert captured.value.code == expected_code


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "expected_code"),
    [
        (httpx.ReadTimeout("timeout"), "timeout"),
        (httpx.ConnectError("network"), "network_error"),
    ],
)
async def test_transport_failures_have_stable_codes(
    exception: httpx.RequestError, expected_code: str
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        exception.request = request
        raise exception

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NaverDictionaryGateway(client, make_settings())
        with pytest.raises(DictionaryError) as captured:
            await gateway.search("안녕", "ko-zh")

    assert captured.value.code == expected_code


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [httpx.Response(200, json=["not", "an", "object"]), httpx.Response(200, text="not-json")],
)
async def test_invalid_payload_is_explicit(response: httpx.Response) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return response

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NaverDictionaryGateway(client, make_settings())
        with pytest.raises(DictionaryError) as captured:
            await gateway.search("안녕", "ko-zh")

    assert captured.value.code == "invalid_upstream_payload"


@pytest.mark.asyncio
async def test_unexpected_failure_is_not_swallowed() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise RuntimeError("programming error")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NaverDictionaryGateway(client, make_settings())
        with pytest.raises(RuntimeError, match="programming error"):
            await gateway.search("안녕", "ko-zh")

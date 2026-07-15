"""Request-scoped Naver Dictionary gateway."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from types import MappingProxyType
from typing import Any, Final, Protocol, cast

import httpx

from src.config import Settings
from src.models import DictionaryEntry, DictType, ErrorCode
from src.parser import parse_search_results

DICT_CODE_MAP: Final[Mapping[DictType, tuple[str, str]]] = MappingProxyType(
    {"ko-zh": ("kozh", "zh_CN"), "ko-en": ("koen", "en")}
)
RETRYABLE_STATUS_CODES: Final = frozenset({429, 500, 502, 503, 504})


class DictionaryError(Exception):
    """Known upstream failure that can be returned for one search item."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DictionaryGateway(Protocol):
    async def search(self, word: str, dict_type: DictType) -> tuple[DictionaryEntry, ...]: ...


class DictionaryGatewayFactory(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[DictionaryGateway]: ...


class NaverDictionaryGateway:
    """Concrete gateway backed by an injected request-scoped HTTP client."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def search(self, word: str, dict_type: DictType) -> tuple[DictionaryEntry, ...]:
        dict_code, language = DICT_CODE_MAP[dict_type]
        url = f"{self._settings.naver_base_url}/{dict_code}/search"
        params = {
            "query": word,
            "m": "mobile",
            "lang": language,
            "shouldSearchVlive": "true",
        }

        for attempt in range(1, self._settings.retry_attempts + 1):
            try:
                response = await self._client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, Mapping):
                    raise DictionaryError(
                        "invalid_upstream_payload", "Naver 返回了无效的 JSON 结构"
                    )
                return parse_search_results(cast(Mapping[str, Any], payload))
            except httpx.TimeoutException as exc:
                if attempt == self._settings.retry_attempts:
                    raise DictionaryError("timeout", "Naver 请求超时") from exc
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code not in RETRYABLE_STATUS_CODES:
                    raise DictionaryError(
                        "upstream_response_error", f"Naver 返回 HTTP {status_code}"
                    ) from exc
                if attempt == self._settings.retry_attempts:
                    code: ErrorCode = (
                        "upstream_rate_limit" if status_code == 429 else "upstream_server_error"
                    )
                    message = (
                        "Naver 请求频率受限"
                        if status_code == 429
                        else f"Naver 服务异常（HTTP {status_code}）"
                    )
                    raise DictionaryError(code, message) from exc
            except httpx.RequestError as exc:
                if attempt == self._settings.retry_attempts:
                    raise DictionaryError("network_error", "无法连接 Naver") from exc
            except ValueError as exc:
                raise DictionaryError(
                    "invalid_upstream_payload", "Naver 返回了无法解析的 JSON"
                ) from exc

            delay = min(
                self._settings.retry_max_delay_seconds,
                self._settings.retry_base_delay_seconds * (2 ** (attempt - 1)),
            )
            await asyncio.sleep(delay)

        raise RuntimeError("unreachable retry state")


class NaverGatewayFactory:
    """Create one HTTP client and gateway per MCP tool invocation."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def __call__(self) -> AbstractAsyncContextManager[DictionaryGateway]:
        return self._create()

    @asynccontextmanager
    async def _create(self) -> AsyncIterator[DictionaryGateway]:
        headers = {
            "User-Agent": "naver-dict-mcp/2.0 (+https://github.com/HenMie/naverdictMCP)",
            "Accept": "application/json,*/*",
            "Referer": "https://korean.dict.naver.com/",
        }
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self._settings.http_timeout_seconds),
            follow_redirects=True,
            headers=headers,
        ) as client:
            yield NaverDictionaryGateway(client, self._settings)

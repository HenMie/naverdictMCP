"""Shared immutable fixtures and gateway fakes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

import pytest

from src.client import DictionaryGateway
from src.models import DictionaryEntry, DictType, Meaning


@pytest.fixture
def sample_api_response() -> dict[str, Any]:
    return {
        "searchResultMap": {
            "searchResultListMap": {
                "WORD": {
                    "items": [
                        {
                            "expEntry": "안녕하세요",
                            "searchPhoneticSymbolList": [{"symbolValue": "[안녕하세요]"}],
                            "meansCollector": [
                                {
                                    "partOfSpeech2": "感叹词",
                                    "means": [
                                        {
                                            "value": "你好",
                                            "exampleOri": "안녕하세요, 만나서 반갑습니다.",
                                            "exampleTrans": "你好，很高兴见到你。",
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                }
            }
        }
    }


@pytest.fixture
def sample_entry() -> DictionaryEntry:
    return DictionaryEntry(
        word="안녕하세요",
        pronunciation="[안녕하세요]",
        meanings=(Meaning(text="[感叹词] 你好", source="WORD"),),
        examples=("안녕하세요, 만나서 반갑습니다. → 你好，很高兴见到你。",),
        sources=("WORD",),
    )


class StubGateway:
    def __init__(self, result: tuple[DictionaryEntry, ...]) -> None:
        self.result = result
        self.calls: list[tuple[str, DictType]] = []
        self.exception: Exception | None = None

    async def search(self, word: str, dict_type: DictType) -> tuple[DictionaryEntry, ...]:
        self.calls.append((word, dict_type))
        if self.exception is not None:
            raise self.exception
        return self.result


class StubGatewayFactory:
    def __init__(self, gateway: DictionaryGateway) -> None:
        self.gateway = gateway
        self.open_count = 0

    def __call__(self) -> AbstractAsyncContextManager[DictionaryGateway]:
        return self._open()

    @asynccontextmanager
    async def _open(self) -> AsyncIterator[DictionaryGateway]:
        self.open_count += 1
        yield self.gateway

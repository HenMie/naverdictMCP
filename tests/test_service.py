"""Tests for batch search business behavior."""

import unicodedata

import pytest

from src.client import DictionaryError
from src.models import DictionaryEntry
from src.service import DictionaryService, InputValidationError, normalize_word
from tests.conftest import StubGateway, StubGatewayFactory


def test_normalize_word_uses_nfc_and_reports_item_errors() -> None:
    decomposed = unicodedata.normalize("NFD", "한")
    assert normalize_word(f"  {decomposed}  ", 0).normalized == "한"
    assert normalize_word("   ", 1).error.code == "validation_error"  # type: ignore[union-attr]
    assert normalize_word("가" * 101, 2).error.code == "validation_error"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_search_preserves_order_and_deduplicates(
    sample_entry: DictionaryEntry,
) -> None:
    gateway = StubGateway((sample_entry,))
    factory = StubGatewayFactory(gateway)
    service = DictionaryService(factory, concurrency=5)

    response = await service.search_words([" 안녕하세요 ", "", "안녕하세요"], "ko-zh")

    assert response.summary.model_dump() == {"total": 3, "succeeded": 2, "failed": 1}
    assert tuple(item.index for item in response.items) == (0, 1, 2)
    assert response.items[0].success is True
    assert response.items[1].success is False
    assert response.items[2].success is True
    assert gateway.calls == [("안녕하세요", "ko-zh")]
    assert factory.open_count == 1


@pytest.mark.asyncio
async def test_all_invalid_items_do_not_open_gateway(sample_entry: DictionaryEntry) -> None:
    gateway = StubGateway((sample_entry,))
    factory = StubGatewayFactory(gateway)
    service = DictionaryService(factory, concurrency=5)

    response = await service.search_words(["", " "], "ko-en")

    assert response.summary.failed == 2
    assert factory.open_count == 0


@pytest.mark.asyncio
async def test_known_gateway_error_is_item_failure(sample_entry: DictionaryEntry) -> None:
    gateway = StubGateway((sample_entry,))
    gateway.exception = DictionaryError("timeout", "Naver 请求超时")
    service = DictionaryService(StubGatewayFactory(gateway), concurrency=5)

    response = await service.search_words(["학교"], "ko-zh")

    assert response.summary.failed == 1
    failure = response.items[0]
    assert failure.success is False
    assert failure.error.code == "timeout"


@pytest.mark.asyncio
async def test_unexpected_gateway_error_propagates(sample_entry: DictionaryEntry) -> None:
    gateway = StubGateway((sample_entry,))
    gateway.exception = RuntimeError("broken parser")
    service = DictionaryService(StubGatewayFactory(gateway), concurrency=5)

    with pytest.raises(RuntimeError, match="broken parser"):
        await service.search_words(["학교"], "ko-zh")


@pytest.mark.asyncio
@pytest.mark.parametrize("words", [[], [str(index) for index in range(11)]])
async def test_request_bounds_are_business_invariants(
    sample_entry: DictionaryEntry, words: list[str]
) -> None:
    service = DictionaryService(StubGatewayFactory(StubGateway((sample_entry,))), concurrency=5)
    with pytest.raises(InputValidationError):
        await service.search_words(words, "ko-zh")

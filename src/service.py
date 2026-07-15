"""Dictionary search use case with no process-global state."""

from __future__ import annotations

import asyncio
import unicodedata
from dataclasses import dataclass

from src.client import DictionaryError, DictionaryGateway, DictionaryGatewayFactory
from src.models import (
    DictionaryEntry,
    DictType,
    SearchError,
    SearchFailure,
    SearchItem,
    SearchResponse,
    SearchSuccess,
    SearchSummary,
)

MAX_WORDS_PER_REQUEST = 10
MAX_WORD_LENGTH = 100
type LookupResult = tuple[DictionaryEntry, ...] | SearchError


class InputValidationError(ValueError):
    """Raised when the request itself cannot be processed."""


@dataclass(frozen=True, slots=True)
class NormalizedWord:
    index: int
    original: str
    normalized: str | None
    error: SearchError | None


def normalize_word(word: str, index: int) -> NormalizedWord:
    """Normalize one word without mutating or rejecting other batch items."""

    stripped = word.strip()
    if not stripped:
        return NormalizedWord(
            index=index,
            original=word,
            normalized=None,
            error=SearchError(code="validation_error", message="搜索词不能为空"),
        )
    normalized = unicodedata.normalize("NFC", stripped)
    if len(normalized) > MAX_WORD_LENGTH:
        return NormalizedWord(
            index=index,
            original=word,
            normalized=None,
            error=SearchError(
                code="validation_error", message=f"搜索词不能超过 {MAX_WORD_LENGTH} 个字符"
            ),
        )
    return NormalizedWord(index=index, original=word, normalized=normalized, error=None)


class DictionaryService:
    """Search words through an injected gateway factory."""

    def __init__(self, gateway_factory: DictionaryGatewayFactory, concurrency: int) -> None:
        self._gateway_factory = gateway_factory
        self._concurrency = concurrency

    async def search_words(self, words: list[str], dict_type: DictType) -> SearchResponse:
        if not words:
            raise InputValidationError("words must contain at least one item")
        if len(words) > MAX_WORDS_PER_REQUEST:
            raise InputValidationError(
                f"words cannot contain more than {MAX_WORDS_PER_REQUEST} items"
            )

        normalized_words = tuple(normalize_word(word, index) for index, word in enumerate(words))
        unique_words = tuple(
            dict.fromkeys(
                item.normalized for item in normalized_words if item.normalized is not None
            )
        )
        outcomes: dict[str, LookupResult] = {}
        if unique_words:
            async with self._gateway_factory() as gateway:
                semaphore = asyncio.Semaphore(self._concurrency)
                results = await asyncio.gather(
                    *(self._lookup(gateway, semaphore, word, dict_type) for word in unique_words)
                )
            outcomes = dict(zip(unique_words, results, strict=True))

        items = tuple(self._materialize(item, outcomes) for item in normalized_words)
        succeeded = sum(isinstance(item, SearchSuccess) for item in items)
        return SearchResponse(
            dict_type=dict_type,
            summary=SearchSummary(
                total=len(items), succeeded=succeeded, failed=len(items) - succeeded
            ),
            items=items,
        )

    @staticmethod
    async def _lookup(
        gateway: DictionaryGateway,
        semaphore: asyncio.Semaphore,
        word: str,
        dict_type: DictType,
    ) -> LookupResult:
        try:
            async with semaphore:
                return await gateway.search(word, dict_type)
        except DictionaryError as exc:
            return SearchError(code=exc.code, message=exc.message)

    @staticmethod
    def _materialize(item: NormalizedWord, outcomes: dict[str, LookupResult]) -> SearchItem:
        if item.error is not None:
            return SearchFailure(index=item.index, word=item.original, error=item.error)
        if item.normalized is None:
            raise RuntimeError("normalized word is missing without a validation error")

        outcome = outcomes[item.normalized]
        if isinstance(outcome, SearchError):
            return SearchFailure(index=item.index, word=item.normalized, error=outcome)
        return SearchSuccess(index=item.index, word=item.normalized, entries=outcome)

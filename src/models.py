"""Typed domain and MCP response models."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

DictType = Literal["ko-zh", "ko-en"]
SourceType = Literal["WORD", "OPEN"]
ErrorCode = Literal[
    "validation_error",
    "timeout",
    "upstream_rate_limit",
    "upstream_server_error",
    "upstream_response_error",
    "network_error",
    "invalid_upstream_payload",
]


class ImmutableModel(BaseModel):
    """Base model that prevents mutation after validation."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Meaning(ImmutableModel):
    text: str
    related_words: tuple[str, ...] = ()
    source: SourceType


class DictionaryEntry(ImmutableModel):
    word: str
    pronunciation: str | None = None
    meanings: tuple[Meaning, ...] = ()
    examples: tuple[str, ...] = ()
    related_words: tuple[str, ...] = ()
    sources: tuple[SourceType, ...]


class SearchError(ImmutableModel):
    code: ErrorCode
    message: str


class SearchSuccess(ImmutableModel):
    index: int
    word: str
    success: Literal[True] = True
    entries: tuple[DictionaryEntry, ...]


class SearchFailure(ImmutableModel):
    index: int
    word: str
    success: Literal[False] = False
    error: SearchError


SearchItem = Annotated[SearchSuccess | SearchFailure, Field(discriminator="success")]


class SearchSummary(ImmutableModel):
    total: int
    succeeded: int
    failed: int


class SearchResponse(ImmutableModel):
    dict_type: DictType
    summary: SearchSummary
    items: tuple[SearchItem, ...]

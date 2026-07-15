"""Pure parser for Naver Dictionary response payloads."""

from __future__ import annotations

import html
import re
from collections.abc import Mapping, Sequence
from typing import Any, cast

from src.models import DictionaryEntry, Meaning, SourceType

_RELATED_WORD_PATTERN = re.compile(r'<span\s+class="related_word"[^>]*>(.*?)</span>', re.IGNORECASE)
_AUTOLINK_PATTERN = re.compile(r"<autoLink[^>]*>(.*?)</autoLink>", re.IGNORECASE)
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


def _dedupe[T](values: Sequence[T], *, limit: int | None = None) -> tuple[T, ...]:
    result: list[T] = []
    for value in values:
        if value not in result:
            result.append(value)
        if limit is not None and len(result) == limit:
            break
    return tuple(result)


def _as_mapping(value: object) -> Mapping[str, Any]:
    return cast(Mapping[str, Any], value) if isinstance(value, Mapping) else {}


def _as_sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return cast(Sequence[object], value)
    return ()


def _string(value: object) -> str:
    return "" if value is None else str(value)


def clean_html(text: object) -> str:
    """Decode entities and remove Naver-specific and ordinary HTML tags."""

    raw = _string(text)
    if not raw:
        return ""
    without_autolink = _AUTOLINK_PATTERN.sub(r"\1", raw)
    decoded = html.unescape(without_autolink)
    return _HTML_TAG_PATTERN.sub("", decoded).strip()


def extract_related_words(text: object) -> tuple[str, ...]:
    """Extract related-word spans while preserving source order."""

    matches = _RELATED_WORD_PATTERN.findall(_string(text))
    return _dedupe(tuple(clean_html(match) for match in matches if clean_html(match)))


def _extract_meanings(collectors: Sequence[object], source: SourceType) -> tuple[Meaning, ...]:
    meanings: list[Meaning] = []
    for raw_collector in collectors:
        collector = _as_mapping(raw_collector)
        part_of_speech = clean_html(collector.get("partOfSpeech2"))
        for raw_meaning in _as_sequence(collector.get("means")):
            meaning = _as_mapping(raw_meaning)
            raw_value = meaning.get("value")
            text = clean_html(raw_value)
            if not text:
                continue
            meanings.append(
                Meaning(
                    text=f"[{part_of_speech}] {text}" if part_of_speech else text,
                    related_words=extract_related_words(raw_value),
                    source=source,
                )
            )
    return _dedupe(meanings)


def _extract_examples(collectors: Sequence[object]) -> tuple[str, ...]:
    examples: list[str] = []
    for raw_collector in collectors:
        collector = _as_mapping(raw_collector)
        for raw_meaning in _as_sequence(collector.get("means")):
            meaning = _as_mapping(raw_meaning)
            original = clean_html(meaning.get("exampleOri"))
            translated = clean_html(meaning.get("exampleTrans"))
            if original:
                examples.append(f"{original} → {translated}" if translated else original)
    return _dedupe(examples, limit=5)


def _extract_pronunciation(item: Mapping[str, Any]) -> str | None:
    pronunciations = _as_sequence(item.get("searchPhoneticSymbolList"))
    if not pronunciations:
        return None
    pronunciation = clean_html(_as_mapping(pronunciations[0]).get("symbolValue"))
    return pronunciation or None


def _parse_item(raw_item: object, source: SourceType) -> DictionaryEntry | None:
    item = _as_mapping(raw_item)
    word = clean_html(item.get("expEntry") or item.get("entryName") or item.get("entry"))
    if not word:
        return None
    collectors = _as_sequence(item.get("meansCollector"))
    meanings = _extract_meanings(collectors, source)
    return DictionaryEntry(
        word=word,
        pronunciation=_extract_pronunciation(item),
        meanings=meanings,
        examples=_extract_examples(collectors),
        related_words=_dedupe(
            tuple(related for meaning in meanings for related in meaning.related_words)
        ),
        sources=(source,),
    )


def _merge_entries(base: DictionaryEntry, incoming: DictionaryEntry) -> DictionaryEntry:
    source_order: tuple[SourceType, ...] = ("WORD", "OPEN")
    sources = tuple(source for source in source_order if source in base.sources + incoming.sources)
    return DictionaryEntry(
        word=base.word,
        pronunciation=base.pronunciation or incoming.pronunciation,
        meanings=_dedupe(base.meanings + incoming.meanings),
        examples=_dedupe(base.examples + incoming.examples, limit=5),
        related_words=_dedupe(base.related_words + incoming.related_words),
        sources=sources,
    )


def parse_search_results(data: Mapping[str, Any]) -> tuple[DictionaryEntry, ...]:
    """Parse WORD and OPEN sections into one immutable entry per headword."""

    search_map = _as_mapping(data.get("searchResultMap"))
    section_map = _as_mapping(search_map.get("searchResultListMap"))
    parsed: list[DictionaryEntry] = []
    sources: tuple[SourceType, ...] = ("WORD", "OPEN")
    for source in sources:
        section = _as_mapping(section_map.get(source))
        for raw_item in _as_sequence(section.get("items")):
            item = _parse_item(raw_item, source)
            if item is not None:
                parsed.append(item)

    merged: dict[str, DictionaryEntry] = {}
    for item in parsed:
        existing = merged.get(item.word)
        merged[item.word] = item if existing is None else _merge_entries(existing, item)
    return tuple(merged.values())

"""Tests for the typed Naver response parser."""

from typing import Any

from src.parser import clean_html, extract_related_words, parse_search_results


def test_clean_html_handles_entities_and_naver_links() -> None:
    value = '<autoLink search="使">使</autoLink> &lt;b&gt;<b>用</b>'
    assert clean_html(value) == "使 用"


def test_extract_related_words_deduplicates_in_order() -> None:
    value = (
        '<span class="related_word" lang="ko">시험</span>'
        '<span class="related_word" lang="ko">검사</span>'
        '<span class="related_word" lang="ko">시험</span>'
    )
    assert extract_related_words(value) == ("시험", "검사")


def test_parse_word_response(sample_api_response: dict[str, Any]) -> None:
    entries = parse_search_results(sample_api_response)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.word == "안녕하세요"
    assert entry.pronunciation == "[안녕하세요]"
    assert entry.meanings[0].text == "[感叹词] 你好"
    assert entry.meanings[0].source == "WORD"
    assert entry.examples == ("안녕하세요, 만나서 반갑습니다. → 你好，很高兴见到你。",)
    assert entry.sources == ("WORD",)


def test_parse_merges_word_and_open_without_mutation() -> None:
    payload = {
        "searchResultMap": {
            "searchResultListMap": {
                "WORD": {
                    "items": [
                        {
                            "expEntry": "테스트",
                            "searchPhoneticSymbolList": [{"symbolValue": "[테스트]"}],
                            "meansCollector": [
                                {
                                    "partOfSpeech2": "名词",
                                    "means": [
                                        {
                                            "value": '<span class="related_word">시험</span> 测试',
                                            "exampleOri": "테스트 예문",
                                            "exampleTrans": "测试例句",
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                },
                "OPEN": {
                    "items": [
                        {
                            "expEntry": "테스트",
                            "meansCollector": [
                                {
                                    "partOfSpeech2": "名词",
                                    "means": [
                                        {
                                            "value": "补充释义",
                                            "exampleOri": "테스트 예문",
                                            "exampleTrans": "测试例句",
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                },
            }
        }
    }

    entries = parse_search_results(payload)
    assert len(entries) == 1
    assert entries[0].sources == ("WORD", "OPEN")
    assert tuple(meaning.source for meaning in entries[0].meanings) == ("WORD", "OPEN")
    assert entries[0].related_words == ("시험",)
    assert len(entries[0].examples) == 1


def test_parse_tolerates_missing_and_malformed_sections() -> None:
    assert parse_search_results({}) == ()
    payload = {
        "searchResultMap": {
            "searchResultListMap": {
                "WORD": {"items": [{"expEntry": "단어"}, None, "bad"]},
                "OPEN": {"items": "not-a-list"},
            }
        }
    }
    entries = parse_search_results(payload)
    assert len(entries) == 1
    assert entries[0].word == "단어"
    assert entries[0].pronunciation is None
    assert entries[0].meanings == ()

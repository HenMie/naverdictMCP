"""Structured logging tests."""

import json
import logging
import sys

from src.logger import JsonFormatter, create_logger


def test_json_formatter_includes_extra_fields_and_exception() -> None:
    formatter = JsonFormatter()
    try:
        raise RuntimeError("visible failure")
    except RuntimeError:
        record = logging.getLogger("test").makeRecord(
            "test",
            logging.ERROR,
            __file__,
            1,
            "request failed",
            (),
            exc_info=sys.exc_info(),
            extra={"error_code": "upstream"},
        )

    payload = json.loads(formatter.format(record))
    assert payload["message"] == "request failed"
    assert payload["error_code"] == "upstream"
    assert "visible failure" in payload["exception"]


def test_create_logger_is_idempotent() -> None:
    first = create_logger("idempotent-test")
    second = create_logger("idempotent-test")
    assert first is second
    assert len(first.handlers) == 1

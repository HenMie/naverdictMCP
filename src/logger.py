"""Structured logging for Vercel's log collector."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Render standard log records as one JSON object per line."""

    _standard_fields = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(
            {
                key: value
                for key, value in record.__dict__.items()
                if key not in self._standard_fields and key not in {"message", "asctime"}
            }
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def create_logger(name: str = "naver-dict-mcp") -> logging.Logger:
    """Create an idempotently configured application logger."""

    application_logger = logging.getLogger(name)
    application_logger.setLevel(logging.INFO)
    application_logger.propagate = False
    if not application_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        application_logger.addHandler(handler)
    return application_logger

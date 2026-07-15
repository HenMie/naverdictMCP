"""Immutable application settings for the Vercel runtime."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse


class ConfigError(ValueError):
    """Raised when required deployment configuration is invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings.

    Only the authentication secret is configured by deployers. Operational
    limits stay in code so a one-click deployment has no hidden tuning step.
    """

    mcp_api_key: str
    naver_base_url: str = "https://korean.dict.naver.com/api3"
    http_timeout_seconds: float = 10.0
    batch_concurrency: int = 5
    retry_attempts: int = 2
    retry_base_delay_seconds: float = 0.2
    retry_max_delay_seconds: float = 1.0

    def __post_init__(self) -> None:
        if len(self.mcp_api_key.encode("utf-8")) < 32:
            raise ConfigError("MCP_API_KEY must contain at least 32 bytes")

        parsed_url = urlparse(self.naver_base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ConfigError("naver_base_url must be an absolute HTTP(S) URL")
        if self.http_timeout_seconds <= 0:
            raise ConfigError("http_timeout_seconds must be greater than zero")
        if not 1 <= self.batch_concurrency <= 10:
            raise ConfigError("batch_concurrency must be between 1 and 10")
        if self.retry_attempts not in {1, 2}:
            raise ConfigError("retry_attempts must be 1 or 2")
        if self.retry_base_delay_seconds < 0:
            raise ConfigError("retry_base_delay_seconds cannot be negative")
        if self.retry_max_delay_seconds < self.retry_base_delay_seconds:
            raise ConfigError(
                "retry_max_delay_seconds cannot be lower than retry_base_delay_seconds"
            )

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Build settings from the deployment environment."""

        values = os.environ if environ is None else environ
        api_key = values.get("MCP_API_KEY", "")
        if not api_key:
            raise ConfigError("MCP_API_KEY is required")
        return cls(mcp_api_key=api_key)

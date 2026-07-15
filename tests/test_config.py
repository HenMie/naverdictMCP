"""Settings validation tests."""

import pytest

from src.config import ConfigError, Settings

VALID_KEY = "a" * 32


def test_from_env_requires_api_key() -> None:
    with pytest.raises(ConfigError, match="MCP_API_KEY is required"):
        Settings.from_env({})


def test_from_env_accepts_single_deployment_value() -> None:
    settings = Settings.from_env({"MCP_API_KEY": VALID_KEY, "IGNORED": "value"})
    assert settings.mcp_api_key == VALID_KEY
    assert settings.naver_base_url == "https://korean.dict.naver.com/api3"


@pytest.mark.parametrize("key", ["", "short", "한" * 10])
def test_api_key_must_be_at_least_32_bytes(key: str) -> None:
    with pytest.raises(ConfigError, match="at least 32 bytes"):
        Settings(mcp_api_key=key)


@pytest.mark.parametrize("url", ["", "not-a-url", "ftp://example.com"])
def test_base_url_must_be_http(url: str) -> None:
    with pytest.raises(ConfigError, match="absolute HTTP"):
        Settings(mcp_api_key=VALID_KEY, naver_base_url=url)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"http_timeout_seconds": 0}, "greater than zero"),
        ({"batch_concurrency": 0}, "between 1 and 10"),
        ({"batch_concurrency": 11}, "between 1 and 10"),
        ({"retry_attempts": 3}, "must be 1 or 2"),
        ({"retry_base_delay_seconds": -1}, "cannot be negative"),
        (
            {"retry_base_delay_seconds": 1, "retry_max_delay_seconds": 0.5},
            "cannot be lower",
        ),
    ],
)
def test_operational_settings_are_validated(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        Settings(mcp_api_key=VALID_KEY, **overrides)  # type: ignore[arg-type]

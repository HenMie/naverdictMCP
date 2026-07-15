"""ASGI routing and authentication tests."""

from __future__ import annotations

import importlib
import sys

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from src.application import create_app
from src.config import Settings
from src.models import DictionaryEntry
from tests.conftest import StubGateway, StubGatewayFactory

VALID_KEY = "a" * 32


def build_app(sample_entry: DictionaryEntry) -> Starlette:
    gateway = StubGateway((sample_entry,))
    return create_app(Settings(mcp_api_key=VALID_KEY), StubGatewayFactory(gateway))


def test_public_routes_do_not_require_authentication(sample_entry: DictionaryEntry) -> None:
    with TestClient(build_app(sample_entry)) as client:
        assert client.get("/").json() == {
            "service": "naver-dictionary-mcp",
            "status": "ok",
            "mcp_endpoint": "/mcp",
        }
        assert client.get("/health").json() == {"status": "ok"}


def test_mcp_requires_exact_bearer_token(sample_entry: DictionaryEntry) -> None:
    with TestClient(build_app(sample_entry)) as client:
        for headers in ({}, {"Authorization": "Bearer wrong"}):
            response = client.post("/mcp", headers=headers, json={})
            assert response.status_code == 401
            assert response.json()["error"] == "unauthorized"
            assert response.headers["www-authenticate"] == "Bearer"


def test_valid_token_reaches_mcp_initialize(sample_entry: DictionaryEntry) -> None:
    headers = {
        "Authorization": f"Bearer {VALID_KEY}",
        "Accept": "application/json, text/event-stream",
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1"},
        },
    }
    with TestClient(build_app(sample_entry)) as client:
        response = client.post("/mcp", headers=headers, json=payload)

    assert response.status_code == 200
    assert response.json()["result"]["serverInfo"]["name"] == "Naver Dictionary"


def test_vercel_entrypoint_reads_required_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_API_KEY", VALID_KEY)
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    assert module.app is not None

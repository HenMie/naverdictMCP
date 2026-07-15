"""ASGI application factory for Vercel and local tests."""

from __future__ import annotations

import logging
import time
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from src.auth import BearerAuthMiddleware
from src.client import DictionaryGatewayFactory, NaverGatewayFactory
from src.config import Settings
from src.logger import create_logger
from src.models import DictType, SearchResponse
from src.service import DictionaryService


def create_mcp(service: DictionaryService, logger: logging.Logger) -> FastMCP:
    """Create the MCP server and bind its only public tool."""

    mcp = FastMCP("Naver Dictionary")

    @mcp.tool(
        name="search_words",
        description="查询 1 至 10 个韩语词条，支持韩中和韩英辞典。",
    )
    async def search_words(
        words: Annotated[list[str], Field(min_length=1, max_length=10)],
        dict_type: DictType = "ko-zh",
    ) -> SearchResponse:
        started_at = time.monotonic()
        result = await service.search_words(words, dict_type)
        logger.info(
            "dictionary_search_completed",
            extra={
                "dict_type": dict_type,
                "word_count": len(words),
                "succeeded": result.summary.succeeded,
                "failed": result.summary.failed,
                "duration_ms": round((time.monotonic() - started_at) * 1000, 2),
            },
        )
        return result

    return mcp


async def home(_request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "service": "naver-dictionary-mcp",
            "status": "ok",
            "mcp_endpoint": "/mcp",
        }
    )


async def health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def create_app(
    settings: Settings | None = None,
    gateway_factory: DictionaryGatewayFactory | None = None,
) -> Starlette:
    """Build the complete application with explicit infrastructure injection."""

    runtime_settings = settings or Settings.from_env()
    logger = create_logger()
    factory = gateway_factory or NaverGatewayFactory(runtime_settings)
    service = DictionaryService(factory, concurrency=runtime_settings.batch_concurrency)
    mcp = create_mcp(service, logger)
    mcp_app = mcp.http_app(path="/mcp", stateless_http=True, json_response=True)

    return Starlette(
        routes=[
            Route("/", home, methods=["GET"]),
            Route("/health", health, methods=["GET"]),
            *mcp_app.routes,
        ],
        middleware=[Middleware(BearerAuthMiddleware, api_key=runtime_settings.mcp_api_key)],
        lifespan=mcp_app.lifespan,
    )

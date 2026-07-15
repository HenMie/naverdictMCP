"""Bearer authentication middleware for the public MCP endpoint."""

from __future__ import annotations

import secrets

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class BearerAuthMiddleware:
    """Require one deployment secret for all requests to ``/mcp``."""

    def __init__(self, app: ASGIApp, api_key: str) -> None:
        self._app = app
        self._expected = f"Bearer {api_key}".encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") == "/mcp":
            authorization = dict(scope.get("headers", ())).get(b"authorization", b"")
            if not secrets.compare_digest(authorization, self._expected):
                response = JSONResponse(
                    {"error": "unauthorized", "message": "A valid Bearer token is required"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return
        await self._app(scope, receive, send)

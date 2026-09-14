"""HTTP access-style logging for API requests (visible in uvicorn terminal)."""
from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        path = request.url.path
        if path in ("/health", "/ready", "/favicon.ico"):
            return await call_next(request)

        logger.info("→ %s %s", request.method, path)
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("✗ %s %s failed", request.method, path)
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "← %s %s %s (%.0f ms)",
            request.method,
            path,
            response.status_code,
            elapsed_ms,
        )
        return response

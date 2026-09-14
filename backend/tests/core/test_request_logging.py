"""Tests for request logging middleware async dispatch."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.responses import Response

from app.core.request_logging import RequestLoggingMiddleware


@pytest.mark.asyncio
async def test_request_logging_dispatch_awaits_call_next_for_options_request():
    middleware = RequestLoggingMiddleware(app=lambda scope, receive, send: None)
    request = SimpleNamespace(
        method="OPTIONS",
        url=SimpleNamespace(path="/api/v1/tenants/etl-sources/"),
    )

    async def call_next(_request):
        return Response(status_code=204)

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 204

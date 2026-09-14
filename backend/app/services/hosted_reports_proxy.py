"""Proxy HR report reads to hosted MintHRM API when local warehouse is empty or unreachable."""
from __future__ import annotations

import atexit
from threading import Lock
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import settings

_TIMEOUT = httpx.Timeout(60.0, connect=15.0)
_client: httpx.Client | None = None
_client_lock = Lock()


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = httpx.Client(timeout=_TIMEOUT)
    return _client


@atexit.register
def _close_proxy_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def use_hosted_reports() -> bool:
    return bool(
        settings.REPORTS_USE_HOSTED_API
        and settings.HOSTED_REPORTS_API_URL.strip()
        and settings.HOSTED_REPORTS_API_KEY.strip()
    )


def _base_url() -> str:
    return settings.HOSTED_REPORTS_API_URL.rstrip("/")


def _headers(tenant_id: str) -> dict[str, str]:
    return {
        "X-API-Key": settings.HOSTED_REPORTS_API_KEY.strip(),
        "X-Tenant-Id": tenant_id.strip(),
    }


def proxy_json(
    method: str,
    path: str,
    tenant_id: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: Any | None = None,
) -> Any:
    url = f"{_base_url()}{path}"
    client = _get_client()
    try:
        response = client.request(
            method,
            url,
            headers=_headers(tenant_id),
            params=params,
            json=json_body,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Hosted reports API unreachable: {exc}",
        ) from exc

    if response.status_code >= 400:
        detail: Any
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text or response.reason_phrase
        raise HTTPException(status_code=response.status_code, detail=detail)

    if not response.content:
        return None
    return response.json()


def proxy_stream(
    method: str,
    path: str,
    tenant_id: str,
    *,
    params: dict[str, Any] | None = None,
) -> StreamingResponse:
    url = f"{_base_url()}{path}"
    if params:
        url = f"{url}?{urlencode(params, doseq=True)}"

    client = _get_client()
    try:
        request = client.build_request(method, url, headers=_headers(tenant_id))
        response = client.send(request, stream=True)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Hosted reports API unreachable: {exc}",
        ) from exc

    if response.status_code >= 400:
        body = response.read()
        detail = body.decode("utf-8", errors="replace")
        raise HTTPException(status_code=response.status_code, detail=detail)

    media_type = response.headers.get("content-type", "application/octet-stream")
    disposition = response.headers.get("content-disposition")

    def _iter():
        try:
            for chunk in response.iter_bytes():
                yield chunk
        finally:
            response.close()

    headers = {}
    if disposition:
        headers["Content-Disposition"] = disposition
    return StreamingResponse(_iter(), media_type=media_type, headers=headers)

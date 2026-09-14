"""Proxy JWT refresh to the customer's HRIS monolith (session-bound reissue)."""

from __future__ import annotations

import httpx
from fastapi import HTTPException, status

from app.core.logging import get_logger
from app.core.security import reissue_sso_token

log = get_logger(__name__)


class HrisRefreshError(Exception):
    """HRIS refused or failed to extend the session."""


def _refresh_urls(hris_origin: str) -> list[str]:
    base = hris_origin.rstrip("/")
    return [
        f"{base}/index.php/apiV1/reportBuilderExtendSession",
        f"{base}/index.php?r=apiV1/reportBuilderExtendSession",
        f"{base}/apiV1/reportBuilderExtendSession",
    ]


def refresh_via_hris(hris_origin: str, access_token: str, *, timeout: float) -> dict:
    """Call HRIS reportBuilderExtendSession and return {access_token, expires_in}."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Access-Token": access_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = {"access_token": access_token}
    last_error = "HRIS refresh failed"

    for url in _refresh_urls(hris_origin):
        try:
            resp = httpx.post(
                url,
                headers=headers,
                json=body,
                timeout=timeout,
                follow_redirects=False,
            )
        except httpx.RequestError as exc:
            last_error = f"HRIS unreachable: {exc}"
            log.warning("hris_refresh_unreachable", url=url, error=str(exc))
            continue

        if resp.status_code in (301, 302, 303, 307, 308):
            last_error = f"HRIS refresh redirected ({resp.status_code})"
            log.warning("hris_refresh_redirect", url=url, status=resp.status_code)
            continue

        if resp.status_code >= 400:
            detail = (resp.text or resp.reason_phrase or "")[:200]
            last_error = f"HRIS refresh failed ({resp.status_code}): {detail}"
            log.warning(
                "hris_refresh_http_error",
                url=url,
                status=resp.status_code,
                detail=detail,
            )
            if resp.status_code == 404:
                continue
            raise HrisRefreshError(last_error)

        try:
            data = resp.json()
        except ValueError as exc:
            last_error = "HRIS returned non-JSON response"
            log.warning("hris_refresh_non_json", url=url)
            raise HrisRefreshError(last_error) from exc

        if not data.get("ok"):
            raise HrisRefreshError(str(data.get("error") or "Refresh rejected"))

        access = data.get("access_token")
        if not access:
            raise HrisRefreshError("HRIS response missing access_token")

        return {
            "access_token": str(access),
            "expires_in": int(data.get("expires_in") or 900),
            "token_type": str(data.get("token_type") or "bearer"),
        }

    raise HrisRefreshError(last_error)


def _is_logout_reject(message: str) -> bool:
    lowered = message.lower()
    return any(
        phrase in lowered
        for phrase in (
            "version mismatch",
            "session mismatch",
            "no session binding",
            "user not found",
            "session expired",
            "invalid token payload",
        )
    )


def refresh_or_http_exception(hris_origin: str, access_token: str, *, timeout: float) -> dict:
    try:
        return refresh_via_hris(hris_origin, access_token, timeout=timeout)
    except HrisRefreshError as exc:
        if _is_logout_reject(str(exc)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        log.warning("hris_refresh_fallback_local", error=str(exc), hris_origin=hris_origin)
        try:
            return reissue_sso_token(access_token)
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

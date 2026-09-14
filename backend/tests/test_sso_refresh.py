"""SSO access-token refresh: local reissue when HRIS is unreachable."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from authlib.jose import jwt

from app.core.config import settings
from app.core.security import reissue_sso_token, refresh_leeway_seconds
from app.services.hris_refresh import HrisRefreshError, refresh_or_http_exception


def _mint(*, exp_offset: int = 900, extra: dict | None = None) -> str:
    now = int(time.time())
    payload = {
        "sub": "42",
        "tenant_id": "ccbsl",
        "role": "client_end_user",
        "iat": now,
        "exp": now + exp_offset,
        "iss": settings.app_name,
        "hris_origin": "https://hris.example.test",
        "sid": "sess-1",
        "ver": 1,
        "auth_time": now,
    }
    if extra:
        payload.update(extra)
    encoded = jwt.encode({"alg": settings.jwt_algorithm}, payload, settings.jwt_secret)
    return encoded.decode("utf-8") if isinstance(encoded, bytes) else encoded


def test_refresh_leeway_is_at_least_24h():
    assert refresh_leeway_seconds() >= 86400


def test_reissue_accepts_expired_access_token():
    token = _mint(exp_offset=-120)  # expired 2 minutes ago
    out = reissue_sso_token(token)
    assert out["access_token"]
    claims = jwt.decode(out["access_token"], settings.jwt_secret)
    assert int(claims["exp"]) > int(time.time())
    assert claims["sid"] == "sess-1"
    assert claims["sub"] == "42"


def test_reissue_rejects_token_past_auth_window():
    old = int(time.time()) - 90000
    token = _mint(exp_offset=-89000, extra={"iat": old, "auth_time": old, "exp": old + 900})
    with pytest.raises(Exception) as exc:
        reissue_sso_token(token)
    assert getattr(exc.value, "status_code", None) in (401, None) or "refresh" in str(exc.value).lower() or "expired" in str(exc.value).lower()


def test_hris_failure_falls_back_to_local_reissue():
    token = _mint(exp_offset=-60)

    def boom(*_a, **_k):
        raise HrisRefreshError("HRIS unreachable: connection timed out")

    with patch("app.services.hris_refresh.refresh_via_hris", side_effect=boom):
        out = refresh_or_http_exception("https://hris.example.test", token, timeout=1.0)
    assert out["access_token"] != token


def test_version_mismatch_does_not_local_reissue():
    token = _mint()
    with patch(
        "app.services.hris_refresh.refresh_via_hris",
        side_effect=HrisRefreshError("HRIS refresh failed (401): Version mismatch"),
    ):
        with pytest.raises(Exception) as exc:
            refresh_or_http_exception("https://hris.example.test", token, timeout=1.0)
    assert getattr(exc.value, "status_code", 401) == 401


@pytest.mark.parametrize("message", [
    "Session mismatch",
    "No session binding",
    "User not found",
    "Session expired",
])
def test_hris_session_rejection_does_not_local_reissue(message):
    token = _mint()
    with patch(
        "app.services.hris_refresh.refresh_via_hris",
        side_effect=HrisRefreshError(message),
    ):
        with pytest.raises(Exception) as exc:
            refresh_or_http_exception("https://hris.example.test", token, timeout=1.0)
    assert getattr(exc.value, "status_code", 401) == 401

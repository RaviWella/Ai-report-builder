"""Auth: OAuth2/JWT + RBAC dependencies (Architecture §4.2, §7.4).

Short-lived JWTs carry the caller's identity, tenant, and role. RBAC is enforced
as per-endpoint FastAPI dependencies. Tenant scope itself is resolved in
tenancy.py and ultimately enforced server-side in the Query Engine — never the UI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from authlib.jose import JoseError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from app.core.config import settings
from app.domain.enums import Role

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# auto_error=False so a missing token doesn't auto-401 — the dev bypass path needs
# to run without one. Production (bypass off) still requires a valid Bearer token.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_v1_prefix}/auth/token", auto_error=False
)


def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return pwd_context.verify(raw, hashed)


def create_access_token(*, user_id: str, tenant_id: str, role: Role) -> str:
    now = int(time.time())
    header = {"alg": settings.jwt_algorithm}
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role.value,
        "iat": now,
        "exp": now + settings.jwt_access_ttl_seconds,
        "iss": settings.app_name,
    }
    token = jwt.encode(header, payload, settings.jwt_secret)
    return token.decode("utf-8") if isinstance(token, bytes) else token


@dataclass(frozen=True)
class Principal:
    """The authenticated caller. `tenant_id` here is the *claimed* tenant; the
    Tenant Guard binds it as the active scope for the request."""

    user_id: str
    tenant_id: str
    role: Role
    logo_url: str | None = None
    company_name: str | None = None


@dataclass(frozen=True)
class TokenClaims:
    """Decoded JWT claims needed for HRIS-backed refresh."""

    user_id: str
    tenant_id: str
    role: Role
    hris_origin: str
    sid: str
    ver: int
    logo_url: str | None = None


def _decode(token: str, *, leeway: int = 0) -> dict:
    try:
        claims = jwt.decode(token, settings.jwt_secret)
        if leeway <= 0:
            claims.validate()  # exp/iat
        else:
            now = int(time.time())
            exp = int(claims.get("exp", 0))
            if now > exp + leeway:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        return dict(claims)
    except HTTPException:
        raise
    except JoseError as exc:  # pragma: no cover - thin wrapper
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _resolve_logo_url(claims: dict) -> str | None:
    """Resolve tenant logo URL from JWT claims (logo_url or logo_file + hris_origin)."""
    logo = claims.get("logo_url") or claims.get("company_logo_url")
    if logo:
        resolved = str(logo).strip()
        if resolved:
            return resolved
    logo_file = claims.get("logo_file") or claims.get("com_logo")
    if not logo_file or str(logo_file).strip() in ("", "0"):
        return None
    origin = claims.get("hris_origin")
    if not origin:
        return None
    return f"{str(origin).rstrip('/')}/uploads/company/200/{str(logo_file).strip()}"


def _resolve_company_name(claims: dict) -> str | None:
    """HRIS company display name from JWT (Company.com_name via SSO)."""
    raw = claims.get("company_name") or claims.get("com_name")
    if not raw:
        return None
    name = str(raw).strip()
    if not name or name == "0":
        return None
    return name


def refresh_leeway_seconds() -> int:
    """Seconds past JWT exp that /auth/refresh will still accept the token.

    Older deploys pin JWT_REFRESH_LEEWAY_SECONDS=60, which cannot cover a 15-minute
    access token if the HRIS round-trip fails. Floor at 24h (HRIS PHP session).
    """
    return max(int(settings.jwt_refresh_leeway_seconds or 0), 86400)


def reissue_sso_token(token: str) -> dict:
    """Mint a new access JWT from a still-signed SSO token without calling HRIS.

    Used when the customer's HRIS is unreachable, CSRF-blocked, or otherwise
    fails for infrastructure reasons. Logout still wins when HRIS returns
    version mismatch. Lifetime is capped by original auth_time / iat + leeway.
    """
    claims = _decode(token, leeway=refresh_leeway_seconds())
    now = int(time.time())
    try:
        auth_time = int(claims.get("auth_time") or claims.get("iat") or 0)
    except (TypeError, ValueError):
        auth_time = 0
    if auth_time <= 0 or now - auth_time > refresh_leeway_seconds():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh window exceeded",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not claims.get("hris_origin") or not claims.get("sid"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing refresh claims (hris_origin, sid, ver)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = {k: v for k, v in dict(claims).items() if k not in ("exp", "nbf")}
    payload["iat"] = now
    payload["exp"] = now + settings.jwt_access_ttl_seconds
    payload["auth_time"] = auth_time
    header = {"alg": settings.jwt_algorithm}
    encoded = jwt.encode(header, payload, settings.jwt_secret)
    access = encoded.decode("utf-8") if isinstance(encoded, bytes) else encoded
    return {
        "access_token": str(access),
        "expires_in": int(settings.jwt_access_ttl_seconds),
        "token_type": "bearer",
    }


def decode_for_refresh(token: str) -> TokenClaims:
    """Decode an SSO token for the refresh BFF path.

    Signature and refresh claims (hris_origin, sid, ver) are required. Expiry is
    allowed up to jwt_refresh_leeway_seconds (default 24h, matching HRIS PHP
    session timeout) so a background tab can still renew while HRIS is logged in.
    """
    claims = _decode(token, leeway=refresh_leeway_seconds())
    try:
        return TokenClaims(
            user_id=str(claims["sub"]),
            tenant_id=str(claims["tenant_id"]),
            role=Role(claims["role"]),
            hris_origin=str(claims["hris_origin"]).rstrip("/"),
            sid=str(claims["sid"]),
            ver=int(claims["ver"]),
            logo_url=_resolve_logo_url(claims),
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing refresh claims (hris_origin, sid, ver)",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _dev_bypass_enabled() -> bool:
    # Hard guard: the bypass is ignored in production regardless of the flag.
    return settings.dev_auth_bypass and settings.environment != "production"


def get_principal(token: str | None = Depends(oauth2_scheme)) -> Principal:
    # Local dev: run as a hardcoded identity, no token required.
    if _dev_bypass_enabled():
        return Principal(
            user_id=settings.dev_user_id,
            tenant_id=settings.dev_tenant_id,
            role=Role(settings.dev_role),
        )

    # Production / normal: identity must arrive in the Authorization header.
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = _decode(token)
    try:
        return Principal(
            user_id=str(claims["sub"]),
            tenant_id=str(claims["tenant_id"]),
            role=Role(claims["role"]),
            logo_url=_resolve_logo_url(claims),
            company_name=_resolve_company_name(claims),
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token claims"
        ) from exc


def require_roles(*allowed: Role):
    """Endpoint dependency factory enforcing RBAC (SRS §9)."""

    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role for this action",
            )
        return principal

    return _dep


# Convenience role-bundles
BuilderRoles = (Role.SUPPORT_ADMIN, Role.CLIENT_HR_ADMIN)
ViewerRoles = (Role.SUPPORT_ADMIN, Role.CLIENT_HR_ADMIN, Role.CLIENT_END_USER)
AdminRoles = (Role.SUPPORT_ADMIN, Role.SYSTEM)

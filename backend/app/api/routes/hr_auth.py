"""HRIS launch authentication — verify encrypted payload from MinHRM PHP."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.security import create_access_token, verify_api_key
from app.services.hris_launch.crypto import list_hris_launch_secret_keys
from app.services.hris_launch.validate import (
    HrisLaunchValidationError,
    parse_and_validate_launch_payload,
)

router = APIRouter()


class VerifyPayloadRequest(BaseModel):
    payload: str = Field(..., min_length=1, description="URL-encoded base64 launch blob")
    subdomain: Optional[str] = Field(None, description="Optional query subdomain cross-check")
    employee_id: Optional[str] = Field(None, description="Optional query employee_id cross-check")


class BrandingResponse(BaseModel):
    company_name: Optional[str] = None
    logo_url: Optional[str] = None


class VerifyPayloadResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    tenant_id: str
    user_id: str
    branding: BrandingResponse


@router.post("/auth/verify-payload", response_model=VerifyPayloadResponse)
def verify_launch_payload(
    body: VerifyPayloadRequest,
    _: str = Depends(verify_api_key),
):
    """
    Decrypt MinHRM PHP launch payload and issue a Mint Analytics JWT.

    PHP encrypts JSON with AES-256-CBC; browser sends the ``payload`` query value here.
    """
    if not list_hris_launch_secret_keys():
        raise HTTPException(
            status_code=503,
            detail="HRIS launch authentication is not configured (HRIS_LAUNCH_SECRET_KEY)",
        )

    try:
        claims = parse_and_validate_launch_payload(
            body.payload,
            query_subdomain=body.subdomain,
            query_employee_id=body.employee_id,
        )
    except HrisLaunchValidationError as exc:
        msg = str(exc)
        if "expired" in msg.lower():
            raise HTTPException(status_code=401, detail=msg) from exc
        if "warehouse" in msg.lower() or "permission" in msg.lower():
            raise HTTPException(status_code=403, detail=msg) from exc
        if "tenant" in msg.lower():
            raise HTTPException(status_code=404, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc

    expires_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    token = create_access_token(
        tenant_id=claims.tenant_id,
        user_id=claims.user_id,
        email=claims.email,
        name=claims.name,
        role="user",
        permissions=claims.permissions,
        expires_minutes=expires_minutes,
    )

    return VerifyPayloadResponse(
        access_token=token,
        expires_in=expires_minutes * 60,
        tenant_id=claims.tenant_id,
        user_id=claims.user_id,
        branding=BrandingResponse(
            company_name=claims.company_name,
            logo_url=claims.logo_url,
        ),
    )

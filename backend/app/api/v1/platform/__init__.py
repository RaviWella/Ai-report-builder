"""Platform / internal API routes."""

from fastapi import APIRouter

from app.api.v1.platform import admin_tenants, internal_tenants

router = APIRouter()
router.include_router(internal_tenants.router)
router.include_router(admin_tenants.router)

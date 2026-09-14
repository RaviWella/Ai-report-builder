"""MintHRM API router — registers all route modules."""
from fastapi import APIRouter

from app.api.routes import (
    hr_auth,
    hr_etl,
    hr_metrics,
    hr_employment,
    hr_payroll,
    hr_custom_reports,
    tenant_routes,
    database_connections,
    etl_sources,
    datamart_chat,
)

api_router = APIRouter()

api_router.include_router(hr_auth.router, tags=["HRIS Authentication"])
api_router.include_router(
    tenant_routes.router, prefix="/tenants", tags=["Tenant Management"]
)
api_router.include_router(
    etl_sources.router, prefix="/tenants/etl-sources", tags=["ETL Sources"]
)
api_router.include_router(
    database_connections.router, prefix="/connections", tags=["Database Connections"]
)
api_router.include_router(
    hr_etl.router, prefix="/hr-etl", tags=["HR Intelligence ETL"]
)
api_router.include_router(
    hr_metrics.router, prefix="/hr", tags=["HR Metric API"]
)
api_router.include_router(
    hr_employment.router, prefix="/hr", tags=["HR Employment Marts"]
)
api_router.include_router(
    hr_payroll.router, prefix="/hr", tags=["HR Payroll Marts"]
)
api_router.include_router(
    hr_custom_reports.router, prefix="/hr", tags=["HR Custom Reports"]
)
api_router.include_router(
    datamart_chat.router, prefix="/datamart", tags=["Datamart AI Chat"]
)

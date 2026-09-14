"""Pydantic schemas for tenant custom report definitions."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

ReportType = Literal["table", "payslip"]
ReportSource = Literal["dbt", "sync"]


class CustomReportDefinitionOut(BaseModel):
    id: int
    tenant_id: str
    module: str
    report_name: str
    view_name: str
    view_query: Optional[str] = None
    report_type: ReportType
    source: ReportSource
    sort_order: int
    is_active: bool
    is_system: bool = False
    period_year_column: Optional[str] = None
    period_month_column: Optional[str] = None


class CustomReportDefinitionCreate(BaseModel):
    module: str = Field(..., min_length=1, max_length=64)
    report_name: str = Field(..., min_length=1, max_length=255)
    view_name: str = Field(..., min_length=1, max_length=128)
    view_query: str = Field(..., min_length=1)
    report_type: ReportType = "table"
    sort_order: int = 100


class CustomReportDefinitionUpdate(BaseModel):
    module: Optional[str] = Field(None, min_length=1, max_length=64)
    report_name: Optional[str] = Field(None, min_length=1, max_length=255)
    view_query: Optional[str] = Field(None, min_length=1)
    report_type: Optional[ReportType] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class CustomReportSyncResponse(BaseModel):
    tenant_id: str
    warehouse_schema: str
    created: list[str]
    skipped: list[str]
    errors: list[str]
    ok: bool

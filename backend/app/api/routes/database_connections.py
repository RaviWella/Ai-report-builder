"""Database Connections API — CRUD + test + schema inspection + query execution.

Ported from mint-analytics. Lets HR analysts connect to any customer database
(MySQL, PostgreSQL, SQL Server) to run ad-hoc queries and build visualizations.

Endpoints:
  GET    /connections/                          list saved connections
  POST   /connections/                          create connection
  GET    /connections/{id}                      get connection
  PUT    /connections/{id}                      update connection
  DELETE /connections/{id}                      delete connection
  POST   /connections/test                      test without saving
  POST   /connections/{id}/health               health check
  GET    /connections/{id}/schemas              list schemas
  GET    /connections/{id}/tables               list tables
  GET    /connections/{id}/tables/{t}/fields    list fields
  GET    /connections/{id}/metadata             full metadata
  POST   /connections/{id}/refresh-schema       clear schema cache
  POST   /connections/{id}/query                execute SELECT
  GET    /connections/{id}/rules                list RLS rules
  POST   /connections/{id}/rules                create RLS rule
  PUT    /connections/{id}/rules/{rid}          update RLS rule
  DELETE /connections/{id}/rules/{rid}          delete RLS rule
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_tenant_db
from app.core.security import get_current_tenant, verify_api_key
from app.schemas.auth import TenantContext
from app.schemas.database_connection import (
    ConnectionCreate,
    ConnectionOut,
    ConnectionUpdate,
    QueryRequest,
    RuleCreate,
    RuleUpdate,
    TestConnectionRequest,
)
from app.services.database_connection import (
    DatabaseConnectionService,
    QueryEngine,
    SchemaInspector,
    TenantQuotaExceeded,
    _invalidate_schema_cache,
    engine_pool_stats,
)

router = APIRouter()


# ── Static routes (must be registered before /{connection_id}) ───

@router.post("/test")
async def test_connection(
    data: TestConnectionRequest,
    _ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
):
    """Test a connection without saving it."""
    svc = DatabaseConnectionService(None)  # type: ignore[arg-type]
    return svc.test_connection(data.model_dump())


@router.get("/pool/stats")
async def pool_stats(
    _ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
):
    """Diagnostic: current engine pool size and capacity."""
    return engine_pool_stats()


# ── Connection CRUD ──────────────────────────────────────────────

@router.get("/", response_model=List[ConnectionOut])
async def list_connections(
    _ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_tenant_db),
):
    svc = DatabaseConnectionService(db)
    return svc.list_connections()


@router.post("/", response_model=ConnectionOut, status_code=201)
async def create_connection(
    data: ConnectionCreate,
    _ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_tenant_db),
):
    svc = DatabaseConnectionService(db)
    try:
        return svc.create_connection(data.model_dump())
    except TenantQuotaExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{connection_id}", response_model=ConnectionOut)
async def get_connection(
    connection_id: int,
    _ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_tenant_db),
):
    svc = DatabaseConnectionService(db)
    conn = svc.get_connection(connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return conn


@router.put("/{connection_id}", response_model=ConnectionOut)
async def update_connection(
    connection_id: int,
    data: ConnectionUpdate,
    _ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_tenant_db),
):
    svc = DatabaseConnectionService(db)
    try:
        conn = svc.update_connection(
            connection_id, data.model_dump(exclude_none=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return conn


@router.delete("/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: int,
    _ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_tenant_db),
):
    svc = DatabaseConnectionService(db)
    if not svc.delete_connection(connection_id):
        raise HTTPException(status_code=404, detail="Connection not found")


@router.post("/{connection_id}/health")
async def check_health(
    connection_id: int,
    _ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_tenant_db),
):
    svc = DatabaseConnectionService(db)
    return svc.update_health(connection_id)


# ── Schema Inspection ────────────────────────────────────────────

@router.get("/{connection_id}/schemas")
async def list_schemas(
    connection_id: int,
    _ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_tenant_db),
):
    inspector = SchemaInspector(db)
    try:
        return {"schemas": await inspector.get_schemas(connection_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{connection_id}/tables")
async def list_tables(
    connection_id: int,
    schema: Optional[str] = None,
    search: str = "",
    _ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_tenant_db),
):
    inspector = SchemaInspector(db)
    try:
        tables = await inspector.get_tables(connection_id, schema=schema, search=search)
        return {"tables": tables, "total": len(tables)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{connection_id}/tables/{table_name}/fields")
async def get_table_fields(
    connection_id: int,
    table_name: str,
    schema: Optional[str] = None,
    _ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_tenant_db),
):
    inspector = SchemaInspector(db)
    try:
        return {
            "fields": await inspector.get_table_fields(
                connection_id, table_name, schema=schema
            )
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{connection_id}/metadata")
async def get_metadata(
    connection_id: int,
    _ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_tenant_db),
):
    inspector = SchemaInspector(db)
    try:
        return await inspector.get_metadata(connection_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{connection_id}/refresh-schema")
async def refresh_schema(
    connection_id: int,
    _ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
):
    """Force a refresh of the cached schema metadata for this connection."""
    _invalidate_schema_cache(connection_id)
    return {"success": True, "message": "Schema cache cleared"}


# ── Query Execution ──────────────────────────────────────────────

@router.post("/{connection_id}/query")
async def execute_query(
    connection_id: int,
    request: QueryRequest,
    ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_tenant_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    x_permission_level_id: Optional[str] = Header(None, alias="X-Permission-Level-Id"),
    x_role: Optional[str] = Header(None, alias="X-Role"),
):
    """Execute a read-only SELECT query against a saved connection.

    Applies row-level security rules if any are configured for the connection.
    """
    user_context: Dict[str, str] = {"tenant_id": ctx.tenant_id}
    if x_user_id:
        user_context["user_id"] = x_user_id
    if x_permission_level_id:
        user_context["permission_level_id"] = x_permission_level_id
    if x_role:
        user_context["role"] = x_role

    engine = QueryEngine(db)
    result = await engine.execute(
        connection_id,
        request.sql,
        limit=request.limit,
        user_context=user_context if len(user_context) > 1 else None,
        schema_name=request.schema_name,
    )

    if result.get("status") == "failed":
        error_msg = result.get("error", "Query execution failed")
        if "requires user authentication context" in error_msg:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg)
        if "SQL safety check failed" in error_msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    return result


# ── Data Access Rules (Row-Level Security) ───────────────────────

def _rule_to_dict(rule) -> dict:
    return {
        "id":                   rule.id,
        "connection_id":        rule.connection_id,
        "name":                 rule.name,
        "description":          rule.description,
        "target_column":        rule.target_column,
        "apply_to_tables":      rule.apply_to_tables,
        "external_api_url":     rule.external_api_url,
        "external_api_method":  rule.external_api_method,
        "external_api_headers": rule.external_api_headers,
        "external_api_body":    rule.external_api_body,
        "response_values_path": rule.response_values_path,
        "cache_ttl_seconds":    rule.cache_ttl_seconds,
        "applies_to_roles":     rule.applies_to_roles,
        "priority":             rule.priority,
        "is_active":            rule.is_active,
    }


@router.get("/{connection_id}/rules")
async def list_rules(
    connection_id: int,
    _ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_tenant_db),
):
    from app.services.data_access import get_active_rules
    rules = get_active_rules(db, connection_id)
    return [_rule_to_dict(r) for r in rules]


@router.post("/{connection_id}/rules", status_code=201)
async def create_rule(
    connection_id: int,
    data: RuleCreate,
    _ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_tenant_db),
):
    from app.models.database_connection import DataAccessRule
    rule = DataAccessRule(**{**data.model_dump(), "connection_id": connection_id})
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _rule_to_dict(rule)


@router.put("/{connection_id}/rules/{rule_id}")
async def update_rule(
    connection_id: int,
    rule_id: int,
    data: RuleUpdate,
    _ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_tenant_db),
):
    from sqlalchemy import select
    from app.models.database_connection import DataAccessRule
    result = db.execute(
        select(DataAccessRule).where(
            DataAccessRule.id == rule_id,
            DataAccessRule.connection_id == connection_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(rule, k, v)
    db.commit()
    db.refresh(rule)
    return _rule_to_dict(rule)


@router.delete("/{connection_id}/rules/{rule_id}", status_code=204)
async def delete_rule(
    connection_id: int,
    rule_id: int,
    _ctx: TenantContext = Depends(get_current_tenant),
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_tenant_db),
):
    from sqlalchemy import select
    from app.models.database_connection import DataAccessRule
    result = db.execute(
        select(DataAccessRule).where(
            DataAccessRule.id == rule_id,
            DataAccessRule.connection_id == connection_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()

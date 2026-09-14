"""Tenant isolation tests for schema-per-tenant PostgreSQL."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.pg_schema_provisioner import PostgresSchemaProvisioner
from app.db.postgres import PostgresDatabase
from app.repositories.tenant_provision import mark_tenant_provisioned
from app.tenancy.pg_schema import subdomain_to_pg_schema


@pytest.fixture()
def pg_db():
    db = PostgresDatabase()
    yield db
    db.dispose()


def test_schema_name_normalization():
    assert subdomain_to_pg_schema("lk-minthrm") == "lk_minthrm"
    assert subdomain_to_pg_schema("demo_tenant") == "demo_tenant"
    assert subdomain_to_pg_schema("coca-cola") == "coca_cola"


def test_tenant_schemas_are_isolated(pg_db):
    provisioner = PostgresSchemaProvisioner()
    session = pg_db.session()
    try:
        session.execute(text("SET search_path TO platform, public"))
        mark_tenant_provisioned(session, "tenant_a", "tenant_a", datamart_key="tenant_a")
        mark_tenant_provisioned(session, "tenant_b", "tenant_b", datamart_key="tenant_b")
        session.commit()

        provisioner.ensure_schema(session, "tenant_a")
        provisioner.ensure_schema(session, "tenant_b")
        session.commit()

        session.execute(text('SET search_path TO "tenant_a", public'))
        session.execute(text('INSERT INTO report_templates (id, name, created_by) VALUES (:id, :n, :u)'),
                        {"id": "tpl-a", "n": "A Report", "u": "tester"})
        session.commit()

        session.execute(text('SET search_path TO "tenant_b", public'))
        count_b = session.execute(text("SELECT count(*) FROM report_templates WHERE id = 'tpl-a'")).scalar()
        assert count_b == 0

        session.execute(text('SET search_path TO "tenant_a", public'))
        count_a = session.execute(text("SELECT count(*) FROM report_templates WHERE id = 'tpl-a'")).scalar()
        assert count_a == 1
    finally:
        session.close()

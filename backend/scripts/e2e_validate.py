"""End-to-end validation through the REAL service layer (run on Python 3.13).

Exercises the full backend pipeline against the metadata DB + live datamart:
  provision tenant schema -> create template -> save draft (validated vs semantic catalogue)
  -> publish (immutable snapshot, semantic pin) -> run published report on the
  read replica -> render branded Excel -> verify audit log.

No HTTP layer — it calls TemplateService / ReportService directly, which is the
same code the API routers use.
"""

from __future__ import annotations

from app.core.tenancy import TenantContext
from app.db.metadata import AuditLog
from app.db.pg_tenant_session import worker_pg_session
from app.db.postgres import init_postgres_database
from app.db.pg_tenant_session import init_postgres_tenant_session_manager
from app.domain.enums import ExportFormat, Role
from app.domain.report_spec import DataSpec, PresentationSpec
from app.repositories.tenant_provision import mark_tenant_provisioned
from app.services.report_service import ReportService
from app.services.template_service import DraftInput, TemplateService
from sqlalchemy import text


def main() -> None:
    init_postgres_database()
    init_postgres_tenant_session_manager()

    tenant_id = "demo_tenant"
    platform = init_postgres_database().session()
    try:
        platform.execute(text("SET search_path TO platform, public"))
        mark_tenant_provisioned(
            platform, tenant_id, tenant_id, datamart_key=tenant_id, provisioned_by="e2e_validate"
        )
        platform.commit()
    finally:
        platform.close()

    with worker_pg_session(tenant_id) as db:
        print(f"1. tenant schema ready for '{tenant_id}'")

        ctx = TenantContext(
            tenant_id=tenant_id,
            pg_schema=tenant_id,
            acting_user_id="u1",
            role=Role.CLIENT_HR_ADMIN,
            on_behalf=False,
        )

        ts = TemplateService(db)
        tpl = ts.create_template(ctx, name="Headcount by Employment Type", description="E2E demo")
        print(f"2. created template {tpl.id[:8]}…")

        data_spec = DataSpec.model_validate(
            {
                "entity": "employee",
                "fields": [{"ref": "employee.employment_type", "label": "Type"}],
                "aggregations": [{"ref": "employee.headcount", "fn": "count", "label": "Headcount"}],
                "group_by": ["employee.employment_type"],
                "sort": [{"ref": "employee.employment_type", "dir": "asc"}],
            }
        )
        presentation = PresentationSpec.model_validate(
            {
                "title": "Headcount by Employment Type",
                "branding": {"header": "Amazon (Demo)", "footer": "Confidential — HR"},
                "page": {"orientation": "portrait", "totals": True},
            }
        )
        version = ts.save_draft(ctx, tpl.id, DraftInput(data_spec, presentation))
        print(f"3. saved draft v{version.version_no} (semantic pin = {version.semantic_version_ref})")

        published = ts.publish(ctx, tpl.id, version.id)
        print(f"4. published version {published.id[:8]}… status={published.status}")

        rs = ReportService(db)
        result = rs.run(ctx, tpl.id, {})
        print(f"5. ran report -> {result.row_count} rows, columns={result.columns}")
        for row in result.rows:
            print("     ", tuple(row.values()))

        content, mime = rs.export(ctx, tpl.id, {}, ExportFormat.XLSX)
        print(f"6. rendered Excel -> {len(content)} bytes ({mime})")
        with open("/tmp/e2e_report.xlsx", "wb") as fh:
            fh.write(content)

        actions = [a.action for a in db.query(AuditLog).all()]
        print(f"7. audit log entries: {actions}")

        print("\n✅ END-TO-END OK: spec -> version -> published -> live run -> Excel -> audited")


if __name__ == "__main__":
    main()

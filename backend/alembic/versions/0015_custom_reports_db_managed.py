"""Move custom report SQL to application DB; seed templates and backfill tenants.

Revision ID: 0015_custom_reports_db_managed
Revises: 0014_tenant_custom_reports
Create Date: 2026-06-09
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision: str = "0015_custom_reports_db_managed"
down_revision: Union[str, None] = "0014_tenant_custom_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "hrm_control"
_SQL_DIR = Path(__file__).resolve().parent.parent / "data" / "custom_report_sql"

# Platform report templates — SQL loaded from alembic/data/custom_report_sql/
_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "view_name": "vw_statutory_remittance_by_month",
        "report_name": "Statutory Payment Report",
        "module": "payroll",
        "report_type": "table",
        "sort_order": 10,
        "period_year_column": "reporting_year",
        "period_month_column": "reporting_month",
    },
    {
        "view_name": "vw_je_allowance_ot_cost_summary",
        "report_name": "Journal Entry Wise OT & Allowance Summary Report",
        "module": "payroll",
        "report_type": "table",
        "sort_order": 20,
        "period_year_column": "proc_year",
        "period_month_column": "proc_month",
    },
    {
        "view_name": "vw_employee_nopay_detail",
        "report_name": "Nopay Report",
        "module": "payroll",
        "report_type": "table",
        "sort_order": 30,
        "period_year_column": "proc_year",
        "period_month_column": "proc_month",
    },
    {
        "view_name": "vw_employee_allowance_ot_payment_detail",
        "report_name": "OT and Allowance Report",
        "module": "payroll",
        "report_type": "table",
        "sort_order": 40,
        "period_year_column": "proc_year",
        "period_month_column": "proc_month",
    },
    {
        "view_name": "vw_employee_ot_worksheet",
        "report_name": "OT Worksheet",
        "module": "payroll",
        "report_type": "table",
        "sort_order": 50,
        "period_year_column": "proc_year",
        "period_month_column": "proc_month",
    },
    {
        "view_name": "vw_employee_payslip_vertical",
        "report_name": "Vertical Employee Payslip Report",
        "module": "payroll",
        "report_type": "payslip",
        "sort_order": 60,
        "period_year_column": None,
        "period_month_column": None,
    },
)


def _load_view_query(view_name: str) -> str:
    path = _SQL_DIR / f"{view_name}.sql"
    if not path.is_file():
        raise FileNotFoundError(f"Custom report SQL seed missing: {path}")
    return path.read_text(encoding="utf-8").strip()


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if "custom_report_templates" not in insp.get_table_names(schema=_SCHEMA):
        op.create_table(
            "custom_report_templates",
            sa.Column("view_name", sa.String(length=128), nullable=False),
            sa.Column("report_name", sa.String(length=255), nullable=False),
            sa.Column("module", sa.String(length=64), nullable=False),
            sa.Column("view_query", sa.Text(), nullable=False),
            sa.Column(
                "report_type",
                sa.String(length=32),
                nullable=False,
                server_default="table",
            ),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "is_system",
                sa.Boolean(),
                nullable=False,
                server_default="true",
            ),
            sa.Column("period_year_column", sa.String(length=64), nullable=True),
            sa.Column("period_month_column", sa.String(length=64), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("view_name"),
            schema=_SCHEMA,
        )

    tcr_cols = {
        col["name"]
        for col in insp.get_columns("tenant_custom_reports", schema=_SCHEMA)
    }
    if "is_system" not in tcr_cols:
        op.add_column(
            "tenant_custom_reports",
            sa.Column(
                "is_system",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
            schema=_SCHEMA,
        )
    if "period_year_column" not in tcr_cols:
        op.add_column(
            "tenant_custom_reports",
            sa.Column("period_year_column", sa.String(length=64), nullable=True),
            schema=_SCHEMA,
        )
    if "period_month_column" not in tcr_cols:
        op.add_column(
            "tenant_custom_reports",
            sa.Column("period_month_column", sa.String(length=64), nullable=True),
            schema=_SCHEMA,
        )

    for spec in _TEMPLATES:
        view_query = _load_view_query(spec["view_name"])
        bind.execute(
            text(
                f"""
                INSERT INTO {_SCHEMA}.custom_report_templates
                    (view_name, report_name, module, view_query, report_type,
                     sort_order, is_system, period_year_column, period_month_column)
                VALUES
                    (:view_name, :report_name, :module, :view_query, :report_type,
                     :sort_order, TRUE, :period_year_column, :period_month_column)
                ON CONFLICT (view_name) DO UPDATE SET
                    report_name = EXCLUDED.report_name,
                    module = EXCLUDED.module,
                    view_query = EXCLUDED.view_query,
                    report_type = EXCLUDED.report_type,
                    sort_order = EXCLUDED.sort_order,
                    is_system = EXCLUDED.is_system,
                    period_year_column = EXCLUDED.period_year_column,
                    period_month_column = EXCLUDED.period_month_column,
                    updated_at = NOW()
                """
            ),
            {
                **spec,
                "view_query": view_query,
            },
        )

    tenant_rows = bind.execute(
        text(
            f"SELECT tenant_id FROM {_SCHEMA}.tenant_registry WHERE is_active = TRUE"
        )
    ).fetchall()

    for (tenant_id,) in tenant_rows:
        for spec in _TEMPLATES:
            view_query = _load_view_query(spec["view_name"])
            bind.execute(
                text(
                    f"""
                    INSERT INTO {_SCHEMA}.tenant_custom_reports
                        (tenant_id, module, report_name, view_name, view_query,
                         report_type, source, sort_order, is_active, is_system,
                         period_year_column, period_month_column)
                    VALUES
                        (:tenant_id, :module, :report_name, :view_name, :view_query,
                         :report_type, 'sync', :sort_order, TRUE, TRUE,
                         :period_year_column, :period_month_column)
                    ON CONFLICT (tenant_id, view_name) DO UPDATE SET
                        report_name = EXCLUDED.report_name,
                        module = EXCLUDED.module,
                        view_query = EXCLUDED.view_query,
                        report_type = EXCLUDED.report_type,
                        source = 'sync',
                        sort_order = EXCLUDED.sort_order,
                        is_system = TRUE,
                        period_year_column = EXCLUDED.period_year_column,
                        period_month_column = EXCLUDED.period_month_column,
                        updated_at = NOW()
                    WHERE tenant_custom_reports.source = 'dbt'
                       OR tenant_custom_reports.view_query IS NULL
                       OR trim(tenant_custom_reports.view_query) = ''
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    **spec,
                    "view_query": view_query,
                },
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if "tenant_custom_reports" in insp.get_table_names(schema=_SCHEMA):
        tcr_cols = {
            col["name"]
            for col in insp.get_columns("tenant_custom_reports", schema=_SCHEMA)
        }
        for col in ("period_month_column", "period_year_column", "is_system"):
            if col in tcr_cols:
                op.drop_column("tenant_custom_reports", col, schema=_SCHEMA)

    if "custom_report_templates" in insp.get_table_names(schema=_SCHEMA):
        op.drop_table("custom_report_templates", schema=_SCHEMA)

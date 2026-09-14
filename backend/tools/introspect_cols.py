"""Print warehouse columns for key tables."""
from app.services.ai_services.datamart.workspace.runtime_context import run_with_datamart_context
from app.services.ai_services.datamart.schema import introspect_table_columns, list_warehouse_tables

TABLES = [
    "vw_payroll_summary",
    "vw_attendance_summary",
    "mart_attendance_monthly_summary",
    "dim_payroll_period",
    "vw_lifecycle_summary",
    "fact_recruitment_pipeline",
    "dim_candidate",
    "mart_employee_current",
    "vw_turnover",
    "vw_headcount",
    "fact_leave_balance",
    "fct_lifecycle_event",
]


def _run() -> None:
    all_tables = {t.rsplit(".", 1)[-1].lower(): t for t in list_warehouse_tables()}
    for short in TABLES:
        q = all_tables.get(short.lower())
        if not q:
            print(f"{short}: NOT IN WAREHOUSE")
            continue
        cols = sorted(introspect_table_columns([q]).get(q, []) or [])
        print(f"{short} ({len(cols)}): {', '.join(cols)}")


if __name__ == "__main__":
    run_with_datamart_context("demo_tenant", _run)

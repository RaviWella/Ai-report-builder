from app.services.ai_services.datamart.workspace.runtime_context import run_with_datamart_context
from app.services.ai_services.datamart.schema import introspect_table_columns

TABLES = [
    "fct_overtime",
    "mart_headcount_monthly",
    "fct_salary_change",
    "dim_canonical_pay_item",
    "hr_semantic.vw_salary_bands",
    "mart_employee_current",
    "fct_processed_add_ded",
]


def main() -> None:
    def _run() -> None:
        for t in TABLES:
            m = introspect_table_columns([t])
            for q, cols in m.items():
                print(q, ":", cols)

    run_with_datamart_context("demo_tenant", _run)


if __name__ == "__main__":
    main()

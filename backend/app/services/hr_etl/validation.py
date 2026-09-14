"""HR ETL validation — post-load data quality checks.

Mirrors finance_etl/validation.py pattern.
Checks run against the mart schema ({tenant_id}_hr) after dbt completes.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("hr_etl.validation")


class HrValidationRunner:
    def __init__(self, pg: Engine, tenant_id: str):
        from app.services.hr_etl.schema_names import control_schema, mart_schema

        self.pg = pg
        self.tenant_id = tenant_id
        self.mart = mart_schema(tenant_id)
        self.ctrl = control_schema(tenant_id)

    def _record(
        self,
        run_id: int,
        check_name: str,
        severity: str,
        status: str,
        message: str,
    ) -> None:
        with self.pg.begin() as conn:
            conn.execute(
                text(
                    f'INSERT INTO "{self.ctrl}".hr_validation_result'
                    " (run_id, check_name, severity, status, message)"
                    " VALUES (:rid, :cn, :sev, :st, :msg)"
                ),
                {
                    "rid": run_id,
                    "cn": check_name,
                    "sev": severity,
                    "st": status,
                    "msg": message,
                },
            )

    def run_all(self, run_id: int) -> dict[str, Any]:
        checks = [
            self._check_employee_count,
            self._check_orphan_attendance,
            self._check_payroll_balance,
            self._check_negative_leave_balance,
        ]
        total = passed = errors = warnings = 0
        for check in checks:
            try:
                result = check(run_id)
                total += 1
                if result["status"] == "pass":
                    passed += 1
                elif result["severity"] == "error":
                    errors += 1
                else:
                    warnings += 1
            except Exception as exc:
                logger.warning("validation check failed: %s", exc)
                total += 1
                errors += 1

        return {
            "total":    total,
            "passed":   passed,
            "failed":   total - passed,
            "errors":   errors,
            "warnings": warnings,
        }

    def _check_employee_count(self, run_id: int) -> dict[str, Any]:
        """At least one active employee must exist."""
        with self.pg.connect() as conn:
            count = conn.execute(
                text(
                    f'SELECT COUNT(*) FROM "{self.mart}".dim_employee'
                    " WHERE is_current AND employment_status = 'active'"
                )
            ).scalar() or 0
        status = "pass" if count > 0 else "fail"
        msg = f"Active employees: {count}"
        self._record(run_id, "active_employee_count", "error", status, msg)
        return {"status": status, "severity": "error"}

    def _check_orphan_attendance(self, run_id: int) -> dict[str, Any]:
        """Attendance records must link to a known employee."""
        with self.pg.connect() as conn:
            orphans = conn.execute(
                text(
                    f'SELECT COUNT(*) FROM "{self.mart}".fact_attendance a'
                    f' LEFT JOIN "{self.mart}".dim_employee e'
                    " ON e.employee_sk = a.employee_sk"
                    " WHERE e.employee_sk IS NULL"
                )
            ).scalar() or 0
        status = "pass" if orphans == 0 else "fail"
        msg = f"Orphan attendance rows: {orphans}"
        self._record(run_id, "orphan_attendance", "warning", status, msg)
        return {"status": status, "severity": "warning"}

    def _check_payroll_balance(self, run_id: int) -> dict[str, Any]:
        """Net salary must equal gross minus deductions (within rounding)."""
        with self.pg.connect() as conn:
            mismatches = conn.execute(
                text(
                    f'SELECT COUNT(*) FROM "{self.mart}".fact_payroll'
                    " WHERE ABS(net_salary - (gross_salary - total_deductions)) > 1.0"
                )
            ).scalar() or 0
        status = "pass" if mismatches == 0 else "fail"
        msg = f"Payroll balance mismatches: {mismatches}"
        self._record(run_id, "payroll_balance", "error", status, msg)
        return {"status": status, "severity": "error"}

    def _check_negative_leave_balance(self, run_id: int) -> dict[str, Any]:
        """No employee should have a negative leave balance."""
        with self.pg.connect() as conn:
            negatives = conn.execute(
                text(
                    f'SELECT COUNT(*) FROM "{self.mart}".fact_leave_balance'
                    " WHERE balance_days < 0"
                )
            ).scalar() or 0
        status = "pass" if negatives == 0 else "fail"
        msg = f"Negative leave balances: {negatives}"
        self._record(run_id, "negative_leave_balance", "warning", status, msg)
        return {"status": status, "severity": "warning"}

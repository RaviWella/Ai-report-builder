"""WS-3 — data-quality validation gates (mirrors mint-analytics' validators).

A declarative set of assertions run against a tenant's datamart. Each is a single
SQL count that must be 0 to pass. Results are stored in `mart_validation_result`
and queried latest-per-check. The framework surfaces issues; it never mutates data.

Add a validator by appending to VALIDATORS — no code change elsewhere.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.tenancy import TenantContext
from app.db.datamart import datamart_connection
from app.db.metadata import MartValidationResult
from app.query_engine import guards

log = get_logger(__name__)

_CORE = settings.datamart_schema_core
_SEM = settings.datamart_schema_semantic


@dataclass(frozen=True)
class Validator:
    name: str
    category: str   # balance | referential | completeness | uniqueness | period | freshness
    severity: str   # error | warning | info
    description: str
    sql: str        # returns ONE integer count; 0 = pass


# The checks. SQL uses configured schema names (not user input). Counts of 0 pass.
VALIDATORS: list[Validator] = [
    Validator(
        name="paysheet_period_grain_unique", category="uniqueness", severity="error",
        description="The wide paysheet must have at most one row per employee per period.",
        sql=f"""SELECT count(*) FROM (
                  SELECT 1 FROM {_CORE}.mart_horizontal_paysheet_dynamic
                  GROUP BY employee_sk, payroll_year, payroll_month HAVING count(*) > 1
                ) d""",
    ),
    Validator(
        name="payroll_summary_period_grain_unique", category="uniqueness", severity="error",
        description="Payroll summary must be unique per employee per period.",
        sql=f"""SELECT count(*) FROM (
                  SELECT 1 FROM {_SEM}.vw_payroll_summary
                  GROUP BY employee_sk, payroll_year, payroll_month HAVING count(*) > 1
                ) d""",
    ),
    Validator(
        name="paysheet_employee_referential", category="referential", severity="warning",
        description="Every paysheet employee should exist in the employee mart.",
        sql=f"""SELECT count(*) FROM (
                  SELECT DISTINCT employee_sk FROM {_CORE}.mart_horizontal_paysheet_dynamic
                ) p
                LEFT JOIN {_CORE}.mart_employee_current e ON e.employee_sk = p.employee_sk
                WHERE e.employee_sk IS NULL""",
    ),
    Validator(
        name="paysheet_net_salary_nonnegative", category="balance", severity="warning",
        description="Net salary should not be negative.",
        sql=f"SELECT count(*) FROM {_CORE}.mart_horizontal_paysheet_dynamic WHERE net_salary < 0",
    ),
]


@dataclass
class ValidationResult:
    name: str
    category: str
    severity: str
    status: str          # pass | fail | error
    row_count: int | None
    description: str
    details: dict = field(default_factory=dict)


def _run_one(ctx: TenantContext, datamart_key: str, v: Validator) -> ValidationResult:
    """Each validator runs in its own connection: a failed statement aborts the
    read-only transaction, so isolation keeps one bad check from poisoning the rest."""
    try:
        guards.assert_select_only(v.sql)
        with datamart_connection(ctx, datamart_key) as conn:
            count = int(conn.execute(text(v.sql)).scalar() or 0)
        return ValidationResult(v.name, v.category, v.severity,
                                "pass" if count == 0 else "fail", count, v.description)
    except Exception as exc:  # noqa: BLE001 - infra/schema issue, not a data verdict
        return ValidationResult(v.name, v.category, v.severity, "error", None, v.description,
                                {"error": str(exc)[:200]})


class ValidationService:
    def __init__(self, db: Session):
        self.db = db

    def run(self, ctx: TenantContext, datamart_key: str) -> dict:
        validation_run_id = uuid.uuid4().hex
        results = [_run_one(ctx, datamart_key, v) for v in VALIDATORS]
        for r in results:
            self.db.add(MartValidationResult(
                validation_run_id=validation_run_id,
                name=r.name, category=r.category, severity=r.severity, status=r.status,
                row_count=r.row_count, description=r.description, details=r.details,
            ))
        self.db.commit()
        return {"validation_run_id": validation_run_id, "results": [r.__dict__ for r in results],
                "summary": _summary(results)}

    def latest(self, ctx: TenantContext) -> dict:
        """Most-recent result per check for this tenant (Postgres DISTINCT ON)."""
        rows = self.db.execute(
            select(MartValidationResult)
            .where(True)
            .distinct(MartValidationResult.name)
            .order_by(MartValidationResult.name, MartValidationResult.created_at.desc())
        ).scalars().all()
        results = [
            ValidationResult(r.name, r.category, r.severity, r.status, r.row_count, r.description or "", r.details or {})
            for r in rows
        ]
        return {"results": [r.__dict__ for r in results], "summary": _summary(results)}


def _summary(results: list[ValidationResult]) -> dict:
    failed = [r for r in results if r.status == "fail"]
    return {
        "checks": len(results),
        "passed": sum(1 for r in results if r.status == "pass"),
        "failed": len(failed),
        "errored": sum(1 for r in results if r.status == "error"),
        # A critical failure = a failing 'error'-severity check; serve policy can block on this.
        "critical_failure": any(r.severity == "error" for r in failed),
    }

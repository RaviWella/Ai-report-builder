"""Read employment marts for dashboard APIs."""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, TypeVar

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError

logger = logging.getLogger("hr_etl.employment_data")

T = TypeVar("T")


def _jsonify_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _json_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: _jsonify_value(v) for k, v in row.items()}


from app.services.hr_etl.schema_names import mart_schema as _mart_schema
from app.services.hr_etl.schema_names import semantic_schema as _semantic_schema


def _period_to_month_start(period_label: str) -> date:
    """YYYY-MM → first day of month."""
    year, month = period_label.split("-")
    return date(int(year), int(month), 1)


def _is_missing_relation(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return (
        "does not exist" in msg
        or "undefinedtable" in msg
        or "undefined table" in msg
        or "undefined_object" in msg
    )


def marts_ready(pg: Engine, tenant_id: str) -> bool:
    """True when core employment marts exist (post-ETL + dbt)."""
    mart = _mart_schema(tenant_id)
    with pg.connect() as conn:
        n = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = :schema
                  AND table_name = 'mart_headcount_monthly'
                """
            ),
            {"schema": mart},
        ).scalar()
    return bool(n)


def _with_mart_fallback(
    pg: Engine, tenant_id: str, empty: T, run: Callable[[], T]
) -> T:
    try:
        return run()
    except ProgrammingError as exc:
        if _is_missing_relation(exc):
            logger.info(
                "Employment marts not ready for tenant %s — empty API response",
                tenant_id,
            )
            return empty
        raise


def _empty_employment_summary(tenant_id: str) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "period_label": None,
        "active_headcount": 0,
        "employees_with_salary": 0,
        "average_basic_salary": None,
        "total_basic_salary_cost": None,
        "new_hires": 0,
        "separations": 0,
        "turnover_rate": None,
        "latest_month_active_headcount": None,
        "mom_active_change": None,
        "monthly_salary_cost_active": None,
        "salary_band_count": 0,
    }


def default_period(pg: Engine, tenant_id: str) -> str | None:
    if not marts_ready(pg, tenant_id):
        return None

    def _run() -> str | None:
        mart = _mart_schema(tenant_id)
        with pg.connect() as conn:
            row = conn.execute(
                text(
                    f"""
                    SELECT TO_CHAR(snapshot_month, 'YYYY-MM')
                    FROM "{mart}".mart_headcount_monthly
                    ORDER BY snapshot_month DESC
                    LIMIT 1
                    """
                )
            ).scalar()
        if row:
            return str(row)
        return latest_attendance_period(pg, tenant_id)

    return _with_mart_fallback(pg, tenant_id, None, _run)


def list_available_periods(pg: Engine, tenant_id: str) -> list[str]:
    if not marts_ready(pg, tenant_id):
        return []

    def _run() -> list[str]:
        mart = _mart_schema(tenant_id)
        semantic = _semantic_schema(tenant_id)
        with pg.connect() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT DISTINCT period_label
                    FROM (
                        SELECT TO_CHAR(snapshot_month, 'YYYY-MM') AS period_label
                        FROM "{mart}".mart_headcount_monthly
                        UNION
                        SELECT period_label FROM "{semantic}".vw_attendance_summary
                        WHERE period_label IS NOT NULL
                        UNION
                        SELECT period_label FROM "{semantic}".vw_lifecycle_summary
                        WHERE period_label IS NOT NULL
                        UNION
                        SELECT period_label FROM "{semantic}".vw_payroll_summary
                        WHERE period_label IS NOT NULL
                    ) p
                    WHERE period_label IS NOT NULL
                    ORDER BY period_label DESC
                    """
                )
            ).scalars().all()
        return [str(r) for r in rows]

    return _with_mart_fallback(pg, tenant_id, [], _run)


def latest_attendance_period(pg: Engine, tenant_id: str) -> str | None:
    if not marts_ready(pg, tenant_id):
        return None

    def _run() -> str | None:
        semantic = _semantic_schema(tenant_id)
        with pg.connect() as conn:
            return conn.execute(
                text(
                    f'SELECT period_label FROM "{semantic}".vw_attendance_summary'
                    " WHERE period_label IS NOT NULL"
                    " ORDER BY period_label DESC LIMIT 1"
                )
            ).scalar()

    return _with_mart_fallback(pg, tenant_id, None, _run)


def fetch_employment_summary(
    pg: Engine, tenant_id: str, *, period_label: str | None = None
) -> dict[str, Any]:
    if not marts_ready(pg, tenant_id):
        return _empty_employment_summary(tenant_id)

    def _run() -> dict[str, Any]:
        mart = _mart_schema(tenant_id)
        semantic = _semantic_schema(tenant_id)
        period = period_label or default_period(pg, tenant_id)
        month_start = _period_to_month_start(period) if period else None

        with pg.connect() as conn:
            monthly = None
            if month_start:
                monthly = conn.execute(
                    text(
                        f"""
                        SELECT
                            TO_CHAR(snapshot_month, 'YYYY-MM') AS period_label,
                            active_headcount,
                            net_active_headcount_change_mom,
                            monthly_salary_cost_active
                        FROM "{mart}".mart_headcount_monthly
                        WHERE snapshot_month = :month_start
                        """
                    ),
                    {"month_start": month_start},
                ).mappings().first()

            active = int(monthly["active_headcount"]) if monthly else (
                conn.execute(
                    text(f'SELECT COUNT(*) FROM "{mart}".mart_employee_current')
                ).scalar() or 0
            )

            if month_start:
                comp = conn.execute(
                    text(
                        f"""
                        SELECT
                            COUNT(*) FILTER (WHERE comp_salary IS NOT NULL),
                            ROUND(AVG(comp_salary)::numeric, 2),
                            ROUND(SUM(comp_salary)::numeric, 2)
                        FROM (
                            SELECT COALESCE(f.basic_salary, e.basic_salary) AS comp_salary
                            FROM "{mart}".fct_employment_snapshot f
                            LEFT JOIN "{mart}".dim_employee e
                                ON e.employee_sk = f.employee_sk
                               AND e.is_current = TRUE
                            WHERE f.snapshot_month = :month_start
                              AND f.is_active = TRUE
                        ) s
                        """
                    ),
                    {"month_start": month_start},
                ).one()
            else:
                comp = conn.execute(
                    text(
                        f"""
                        SELECT
                            COUNT(*) FILTER (WHERE basic_salary IS NOT NULL),
                            ROUND(AVG(basic_salary)::numeric, 2),
                            ROUND(SUM(basic_salary)::numeric, 2)
                        FROM "{mart}".mart_employee_current
                        """
                    )
                ).one()

            lifecycle = {"new_hires": 0, "separations": 0}
            if period:
                lifecycle = conn.execute(
                    text(
                        f"""
                        SELECT
                            COUNT(*) FILTER (
                                WHERE event_category IN ('hire', 'employment')
                            ) AS new_hires,
                            COUNT(*) FILTER (
                                WHERE event_category = 'separation'
                            ) AS separations
                        FROM "{semantic}".vw_lifecycle_summary
                        WHERE period_label = :period
                        """
                    ),
                    {"period": period},
                ).mappings().one()

            if month_start:
                band_count = conn.execute(
                    text(
                        f"""
                        SELECT COUNT(*) FROM (
                            SELECT 1
                            FROM "{mart}".fct_employment_snapshot f
                            LEFT JOIN "{mart}".dim_designation d
                                ON d.designation_sk = f.designation_sk
                            LEFT JOIN "{mart}".dim_employee e
                                ON e.employee_sk = f.employee_sk AND e.is_current = TRUE
                            WHERE f.snapshot_month = :month_start
                              AND f.is_active = TRUE
                              AND f.basic_salary IS NOT NULL
                            GROUP BY
                                COALESCE(e.legal_entity_name, 'Unknown'),
                                COALESCE(d.designation_name, 'Unknown'),
                                COALESCE(d.grade_name, 'Unknown')
                        ) bands
                        """
                    ),
                    {"month_start": month_start},
                ).scalar() or 0
            else:
                band_count = conn.execute(
                    text(f'SELECT COUNT(*) FROM "{mart}".mart_salary_band_summary')
                ).scalar() or 0

        total_hc = float(active)
        separations = float(lifecycle.get("separations") or 0)
        turnover_rate = (separations / total_hc * 100.0) if total_hc > 0 else None

        return {
            "tenant_id": tenant_id,
            "period_label": period,
            "active_headcount": int(active),
            "employees_with_salary": int(comp[0] or 0),
            "average_basic_salary": float(comp[1]) if comp[1] is not None else None,
            "total_basic_salary_cost": float(comp[2]) if comp[2] is not None else None,
            "new_hires": int(lifecycle.get("new_hires") or 0),
            "separations": int(separations),
            "turnover_rate": turnover_rate,
            "latest_month_active_headcount": (
                int(monthly["active_headcount"]) if monthly else None
            ),
            "mom_active_change": (
                float(monthly["net_active_headcount_change_mom"])
                if monthly and monthly["net_active_headcount_change_mom"] is not None
                else None
            ),
            "monthly_salary_cost_active": (
                float(monthly["monthly_salary_cost_active"])
                if monthly and monthly["monthly_salary_cost_active"] is not None
                else (float(comp[2]) if comp[2] is not None else None)
            ),
            "salary_band_count": int(band_count),
        }

    return _with_mart_fallback(
        pg, tenant_id, _empty_employment_summary(tenant_id), _run
    )


def fetch_headcount_monthly(
    pg: Engine,
    tenant_id: str,
    *,
    limit: int = 12,
    period_label: str | None = None,
) -> list[dict[str, Any]]:
    if not marts_ready(pg, tenant_id):
        return []

    def _run() -> list[dict[str, Any]]:
        semantic = _semantic_schema(tenant_id)
        with pg.connect() as conn:
            if period_label:
                rows = conn.execute(
                    text(
                        f"""
                        SELECT *
                        FROM "{semantic}".vw_employment_monthly
                        WHERE period_label = :period
                        """
                    ),
                    {"period": period_label},
                ).mappings().all()
            else:
                rows = conn.execute(
                    text(
                        f"""
                        SELECT *
                        FROM "{semantic}".vw_employment_monthly
                        ORDER BY snapshot_month DESC
                        LIMIT :lim
                        """
                    ),
                    {"lim": limit},
                ).mappings().all()
        return [dict(r) for r in rows]

    return _with_mart_fallback(pg, tenant_id, [], _run)


def _fetch_salary_bands_from_view(
    pg: Engine, tenant_id: str, *, limit: int
) -> list[dict[str, Any]]:
    semantic = _semantic_schema(tenant_id)
    with pg.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT
                    salary_band_sk,
                    legal_entity_name,
                    designation_name,
                    grade_name,
                    headcount,
                    min_salary,
                    max_salary,
                    avg_salary,
                    median_salary,
                    payroll_cost
                FROM "{semantic}".vw_salary_bands
                ORDER BY payroll_cost DESC NULLS LAST, headcount DESC
                LIMIT :lim
                """
            ),
            {"lim": limit},
        ).mappings().all()
    return [_json_row(dict(r)) for r in rows]


def fetch_salary_bands(
    pg: Engine,
    tenant_id: str,
    *,
    limit: int = 50,
    period_label: str | None = None,
) -> list[dict[str, Any]]:
    if not marts_ready(pg, tenant_id):
        return []

    def _run() -> list[dict[str, Any]]:
        mart = _mart_schema(tenant_id)
        period = period_label or default_period(pg, tenant_id)
        month_start = _period_to_month_start(period) if period else None

        if not month_start:
            return _fetch_salary_bands_from_view(pg, tenant_id, limit=limit)

        with pg.connect() as conn:
            rows = conn.execute(
                text(
                    f"""
                SELECT
                    MD5(CONCAT(
                        f.tenant_id, '|', f.source_system, '|',
                        COALESCE(e.legal_entity_name, 'Unknown'), '|',
                        COALESCE(d.designation_name, 'Unknown'), '|',
                        COALESCE(d.grade_name, 'Unknown')
                    )) AS salary_band_sk,
                    COALESCE(e.legal_entity_name, 'Unknown') AS legal_entity_name,
                    COALESCE(d.designation_name, 'Unknown') AS designation_name,
                    COALESCE(d.grade_name, 'Unknown') AS grade_name,
                    COUNT(*) AS headcount,
                    MIN(comp_salary) AS min_salary,
                    MAX(comp_salary) AS max_salary,
                    ROUND(AVG(comp_salary)::numeric, 2) AS avg_salary,
                    ROUND(
                        (PERCENTILE_CONT(0.5) WITHIN GROUP (
                            ORDER BY comp_salary
                        ))::numeric,
                        2
                    ) AS median_salary,
                    ROUND(SUM(comp_salary)::numeric, 2) AS payroll_cost
                FROM (
                    SELECT
                        f.tenant_id,
                        f.source_system,
                        f.designation_sk,
                        f.employee_sk,
                        COALESCE(f.basic_salary, e.basic_salary) AS comp_salary
                    FROM "{mart}".fct_employment_snapshot f
                    LEFT JOIN "{mart}".dim_employee e
                        ON e.employee_sk = f.employee_sk
                       AND e.is_current = TRUE
                    WHERE f.snapshot_month = :month_start
                      AND f.is_active = TRUE
                ) f
                LEFT JOIN "{mart}".dim_designation d
                    ON d.designation_sk = f.designation_sk
                LEFT JOIN "{mart}".dim_employee e
                    ON e.employee_sk = f.employee_sk
                   AND e.is_current = TRUE
                WHERE f.comp_salary IS NOT NULL
                GROUP BY
                    f.tenant_id, f.source_system,
                    COALESCE(e.legal_entity_name, 'Unknown'),
                    COALESCE(d.designation_name, 'Unknown'),
                    COALESCE(d.grade_name, 'Unknown')
                ORDER BY payroll_cost DESC NULLS LAST, headcount DESC
                LIMIT :lim
                    """
                ),
                {"month_start": month_start, "lim": limit},
            ).mappings().all()

        result = [_json_row(dict(r)) for r in rows]
        if result:
            return result
        return _fetch_salary_bands_from_view(pg, tenant_id, limit=limit)

    return _with_mart_fallback(pg, tenant_id, [], _run)


def fetch_employees(
    pg: Engine,
    tenant_id: str,
    *,
    limit: int = 100,
    offset: int = 0,
    period_label: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    if not marts_ready(pg, tenant_id):
        return [], 0

    def _run() -> tuple[list[dict[str, Any]], int]:
        mart = _mart_schema(tenant_id)
        period = period_label or default_period(pg, tenant_id)
        month_start = _period_to_month_start(period) if period else None

        if not month_start:
            with pg.connect() as conn:
                total = conn.execute(
                    text(f'SELECT COUNT(*) FROM "{mart}".mart_employee_current')
                ).scalar() or 0
                rows = conn.execute(
                    text(
                        f"""
                        SELECT
                            source_emp_id, emp_no, emp_fullname, designation, grade,
                            legal_entity, location_name, employment_type, join_date,
                            tenure_years, tenure_bucket, basic_salary, is_on_probation,
                            superior_fullname
                        FROM "{mart}".mart_employee_current
                        ORDER BY emp_fullname NULLS LAST, emp_no
                        LIMIT :lim OFFSET :off
                        """
                    ),
                    {"lim": limit, "off": offset},
                ).mappings().all()
            return [_json_row(dict(r)) for r in rows], int(total)

        with pg.connect() as conn:
            total = conn.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM "{mart}".fct_employment_snapshot f
                    WHERE f.snapshot_month = :month_start AND f.is_active = TRUE
                    """
                ),
                {"month_start": month_start},
            ).scalar() or 0
            rows = conn.execute(
                text(
                    f"""
                    SELECT
                        e.source_emp_id,
                        e.emp_no,
                        e.emp_fullname,
                        d.designation_name AS designation,
                        d.grade_name AS grade,
                        e.legal_entity_name AS legal_entity,
                        e.location_name,
                        f.employment_type,
                        e.join_date,
                        f.years_of_service AS tenure_years,
                        f.tenure_band AS tenure_bucket,
                        f.basic_salary,
                        f.is_on_probation,
                        sup.emp_fullname AS superior_fullname
                    FROM "{mart}".fct_employment_snapshot f
                    JOIN "{mart}".dim_employee e ON e.employee_sk = f.employee_sk
                    LEFT JOIN "{mart}".dim_designation d
                        ON d.designation_sk = f.designation_sk
                    LEFT JOIN "{mart}".dim_employee sup
                        ON sup.emp_no = e.superior_emp_no
                        AND sup.is_current = TRUE
                        AND sup.tenant_id = e.tenant_id
                    WHERE f.snapshot_month = :month_start
                      AND f.is_active = TRUE
                    ORDER BY e.emp_fullname NULLS LAST, e.emp_no
                    LIMIT :lim OFFSET :off
                    """
                ),
                {"month_start": month_start, "lim": limit, "off": offset},
            ).mappings().all()
        return [_json_row(dict(r)) for r in rows], int(total)

    return _with_mart_fallback(pg, tenant_id, ([], 0), _run)


def fetch_lifecycle_by_category(
    pg: Engine, tenant_id: str, *, period_label: str | None = None, limit: int = 24
) -> list[dict[str, Any]]:
    if not marts_ready(pg, tenant_id):
        return []

    def _run() -> list[dict[str, Any]]:
        semantic = _semantic_schema(tenant_id)
        period = period_label or default_period(pg, tenant_id)
        with pg.connect() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT
                        period_label,
                        event_category,
                        COUNT(*) AS event_count
                    FROM "{semantic}".vw_lifecycle_summary
                    WHERE period_label = :period
                    GROUP BY period_label, event_category
                    ORDER BY event_count DESC
                    LIMIT :lim
                    """
                ),
                {"period": period, "lim": limit},
            ).mappings().all()
        return [dict(r) for r in rows]

    return _with_mart_fallback(pg, tenant_id, [], _run)


def fetch_attendance_monthly_totals(
    pg: Engine, tenant_id: str, *, period_label: str | None = None
) -> dict[str, Any]:
    period = period_label or default_period(pg, tenant_id)
    empty = {
        "period_label": period,
        "scheduled_days": 0,
        "present_days": 0,
        "late_arrivals": 0,
        "total_overtime_hours": 0,
        "attendance_rate": None,
    }
    if not marts_ready(pg, tenant_id):
        return empty

    def _run() -> dict[str, Any]:
        semantic = _semantic_schema(tenant_id)
        with pg.connect() as conn:
            row = conn.execute(
                text(
                    f"""
                    SELECT
                        :period AS period_label,
                        SUM(scheduled_days) AS scheduled_days,
                        SUM(present_days) AS present_days,
                        SUM(late_count) AS late_arrivals,
                        SUM(overtime_hours) AS total_overtime_hours,
                        CASE
                            WHEN SUM(scheduled_days) > 0
                            THEN ROUND(
                                SUM(present_days)::numeric
                                    / SUM(scheduled_days) * 100,
                                2
                            )
                        END AS attendance_rate
                    FROM "{semantic}".vw_attendance_summary
                    WHERE period_label = :period
                    """
                ),
                {"period": period},
            ).mappings().one()
        return dict(row)

    return _with_mart_fallback(pg, tenant_id, empty, _run)

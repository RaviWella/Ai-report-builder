"""Read Phase 6 payroll marts for dashboard APIs."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services.hr_etl.employment_data import _json_row, default_period
from app.services.hr_etl.schema_names import mart_schema as _mart_schema
from app.services.hr_etl.schema_names import semantic_schema as _semantic_schema


def _period_filter_sql(*, period_alias: str = "p") -> str:
    return (
        f"TO_CHAR({period_alias}.period_start_date, 'YYYY-MM') = :period_label"
    )


def fetch_payroll_summary(
    pg: Engine, tenant_id: str, *, period_label: str | None = None
) -> dict[str, Any]:
    """Aggregates from vw_payroll_summary for the selected month."""
    semantic = _semantic_schema(tenant_id)
    period = period_label or default_period(pg, tenant_id)
    if not period:
        return {"tenant_id": tenant_id, "period_label": None}

    with pg.connect() as conn:
        row = conn.execute(
            text(
                f"""
                SELECT
                    COUNT(DISTINCT employee_sk)              AS payroll_employee_count,
                    COALESCE(SUM(net_salary), 0)              AS total_payroll_cost,
                    COALESCE(SUM(gross_salary), 0)            AS total_gross,
                    COALESCE(SUM(total_additions), 0)         AS total_additions,
                    COALESCE(SUM(total_deductions), 0)        AS total_deductions,
                    COALESCE(SUM(tax_amount), 0)              AS total_tax,
                    COALESCE(SUM(epf_employee_amount), 0)     AS total_epf_employee,
                    COALESCE(SUM(epf_employer_amount), 0)     AS total_epf_employer,
                    COALESCE(SUM(etf_amount), 0)              AS total_etf,
                    COALESCE(SUM(pay_cut_amount), 0)          AS total_pay_cut,
                    COALESCE(SUM(increment_amount), 0)        AS total_increment
                FROM "{semantic}".vw_payroll_summary
                WHERE period_label = :period_label
                """
            ),
            {"period_label": period},
        ).mappings().first()

    if not row:
        return {"tenant_id": tenant_id, "period_label": period}

    count = int(row["payroll_employee_count"] or 0)
    net = float(row["total_payroll_cost"] or 0)
    result = {
        "tenant_id": tenant_id,
        "period_label": period,
        "payroll_employee_count": count,
        "total_payroll_cost": net,
        "total_gross": float(row["total_gross"] or 0),
        "total_additions": float(row["total_additions"] or 0),
        "total_deductions": float(row["total_deductions"] or 0),
        "total_tax": float(row["total_tax"] or 0),
        "total_epf_employee": float(row["total_epf_employee"] or 0),
        "total_epf_employer": float(row["total_epf_employer"] or 0),
        "total_etf": float(row["total_etf"] or 0),
        "total_pay_cut": float(row["total_pay_cut"] or 0),
        "total_increment": float(row["total_increment"] or 0),
        "total_deductions": float(row["total_deductions"] or 0),
        "average_salary": (net / count) if count > 0 else None,
        "total_statutory": (
            float(row["total_epf_employee"] or 0)
            + float(row["total_epf_employer"] or 0)
            + float(row["total_etf"] or 0)
        ),
    }
    return result


def fetch_payroll_register(
    pg: Engine,
    tenant_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
    period_label: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    semantic = _semantic_schema(tenant_id)
    period = period_label or default_period(pg, tenant_id)
    if not period:
        return [], 0

    with pg.connect() as conn:
        total = conn.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM "{semantic}".vw_payroll_summary
                WHERE period_label = :period_label
                """
            ),
            {"period_label": period},
        ).scalar() or 0
        rows = conn.execute(
            text(
                f"""
                SELECT
                    employee_sk,
                    employee_id,
                    emp_no,
                    emp_fullname,
                    designation,
                    legal_entity,
                    branch,
                    payroll_group_name,
                    basic_salary,
                    gross_salary,
                    total_additions,
                    total_deductions,
                    net_salary,
                    tax_amount,
                    epf_employee_amount,
                    epf_employer_amount,
                    etf_amount,
                    pay_cut_amount,
                    increment_amount,
                    run_status
                FROM "{semantic}".vw_payroll_summary
                WHERE period_label = :period_label
                ORDER BY emp_fullname NULLS LAST, emp_no
                LIMIT :lim OFFSET :off
                """
            ),
            {"period_label": period, "lim": limit, "off": offset},
        ).mappings().all()
    return [_json_row(dict(r)) for r in rows], int(total)


def fetch_payroll_compliance(
    pg: Engine, tenant_id: str, *, period_label: str | None = None
) -> list[dict[str, Any]]:
    mart = _mart_schema(tenant_id)
    period = period_label or default_period(pg, tenant_id)
    if not period:
        return []

    with pg.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT compliance_domain, SUM(total_amount) AS total_amount,
                       SUM(employee_count) AS employee_count
                FROM (
                    SELECT
                        v.compliance_domain,
                        SUM(v.compliance_amount)               AS total_amount,
                        COUNT(DISTINCT c.employee_sk)          AS employee_count
                    FROM "{mart}".fct_compliance_payroll c
                    INNER JOIN "{mart}".dim_payroll_period p
                        ON p.payroll_period_sk = c.payroll_period_sk
                    CROSS JOIN LATERAL (
                        VALUES
                            ('compliance_salary', c.compliance_salary),
                            ('compliance_ot', c.compliance_ot),
                            ('compliance_nopay', c.compliance_nopay)
                    ) AS v(compliance_domain, compliance_amount)
                    WHERE {_period_filter_sql(period_alias="p")}
                      AND COALESCE(v.compliance_amount, 0) <> 0
                    GROUP BY v.compliance_domain

                    UNION ALL

                    SELECT
                        v.compliance_domain,
                        SUM(v.compliance_amount)               AS total_amount,
                        COUNT(DISTINCT s.employee_sk)          AS employee_count
                    FROM "{mart}".fct_processed_salary s
                    INNER JOIN "{mart}".dim_payroll_period p
                        ON p.payroll_period_sk = s.payroll_period_sk
                    CROSS JOIN LATERAL (
                        VALUES
                            ('epf_employee', s.epf_employee_amount),
                            ('epf_employer', s.epf_employer_amount),
                            ('etf', s.etf_amount)
                    ) AS v(compliance_domain, compliance_amount)
                    WHERE {_period_filter_sql(period_alias="p")}
                      AND COALESCE(v.compliance_amount, 0) <> 0
                      AND NOT EXISTS (
                          SELECT 1 FROM "{mart}".fct_compliance_payroll LIMIT 1
                      )
                    GROUP BY v.compliance_domain
                ) u
                GROUP BY compliance_domain
                ORDER BY compliance_domain
                """
            ),
            {"period_label": period},
        ).mappings().all()
    return [_json_row(dict(r)) for r in rows]


def fetch_payroll_components(
    pg: Engine,
    tenant_id: str,
    *,
    period_label: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    mart = _mart_schema(tenant_id)
    period = period_label or default_period(pg, tenant_id)
    if not period:
        return []

    with pg.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT
                    COALESCE(f.payroll_item_name, f.payroll_item_code, 'Unknown')
                                                               AS component_name,
                    f.add_ded_type,
                    SUM(f.amount)                                AS total_amount,
                    COUNT(*)                                     AS line_count
                FROM "{mart}".fct_processed_add_ded f
                INNER JOIN "{mart}".dim_payroll_period p
                    ON p.payroll_period_sk = f.payroll_period_sk
                WHERE {_period_filter_sql(period_alias="p")}
                GROUP BY 1, f.add_ded_type
                ORDER BY ABS(SUM(f.amount)) DESC
                LIMIT :lim
                """
            ),
            {"period_label": period, "lim": limit},
        ).mappings().all()
    return [_json_row(dict(r)) for r in rows]

"""Document generation — render a per-record document (one page per record) to a
multi-page PDF.

Two data parts:
  1. Scalar per-record values (identity + section lines/totals) via the common
     Query Engine as a wide row per record — reusing refs, joins, guards and the
     period-aligned-join fix.
  2. Optional one→many DETAIL BLOCKS (e.g. an employee's bank accounts) supplied
     by named providers in DETAIL_PROVIDERS — generic, so new block types are
     added by registering a provider, not by touching the renderer.
"""

from __future__ import annotations

import calendar
from typing import Any, Callable

from sqlalchemy import text

from app.core.config import settings
from app.core.tenancy import TenantContext
from app.db.datamart import datamart_connection
from app.domain.document_spec import DocumentLine, DocumentSpec
from app.domain.enums import FilterOp
from app.domain.report_spec import DataSpec, FieldSelection, FilterClause
from app.domain.semantic import SemanticCatalog
from app.query_engine import guards
from app.query_engine.runner import run_query
from app.rendering.document_renderer import fmt_amount, render_document_pdf

# --------------------------------------------------------------------------- #
# Detail-block providers — one→many child rows per record, keyed by emp_no.
# --------------------------------------------------------------------------- #

def _bank_instructions(
    ctx: TenantContext, datamart_key: str, *, year: int | None, month: int | None,
    record_key: str | None,
) -> dict[str, list[list[dict]]]:
    core = settings.datamart_schema_core       # dims/facts (e.g. "core")
    mart = settings.datamart_schema_semantic   # report-ready marts (e.g. "mart")
    # Bank + branch names are denormalised onto the payment fact — no bank dims to
    # join. Account shown as its last 4 digits (the raw number is stored encrypted).
    sql = text(
        f"""
        SELECT e.employee_no AS emp_no,
               trim(both ' -' FROM
                 coalesce(b.bank_name, '')
                 || CASE WHEN b.bank_branch_name IS NOT NULL THEN ' - ' || b.bank_branch_name ELSE '' END
               ) AS bank_branch,
               b.account_no_last4 AS account_no,
               b.payment_amount AS amount
        FROM {core}.fct_payroll_bank_payment b
        JOIN {mart}.mart_employee e ON e.employee_sk = b.employee_sk
        JOIN {core}.dim_pay_period pp ON pp.pay_period_sk = b.pay_period_sk
        WHERE pp.proc_year = :year AND pp.proc_month = :month
          AND (CAST(:rk AS text) IS NULL OR e.employee_no = CAST(:rk AS text))
        ORDER BY e.employee_no, b.payment_amount DESC
        """
    )
    guards.assert_select_only(str(sql))
    out: dict[str, list[list[dict]]] = {}
    with datamart_connection(ctx, datamart_key) as conn:
        for r in conn.execute(sql, {"year": year, "month": month, "rk": record_key}).mappings():
            item = [
                {"label": "Bank Name - Branch", "value": r["bank_branch"] or "—"},
                {"label": "Account Number", "value": r["account_no"] or "—"},
            ]
            if r["amount"]:
                item.append({"label": "Amount", "value": fmt_amount(r["amount"])})
            out.setdefault(str(r["emp_no"]), []).append(item)
    return out


DETAIL_PROVIDERS: dict[str, Callable[..., dict[str, list[list[dict]]]]] = {
    "bank_instructions": _bank_instructions,
}


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #

def _line_ctx(line: DocumentLine | None, row: dict[str, Any]) -> dict | None:
    if line is None:
        return None
    has_ref = line.ref is not None
    return {"label": line.label, "amount": fmt_amount(row.get(line.ref)) if has_ref else "", "blank": not has_ref}


def generate_documents(
    ctx: TenantContext,
    datamart_key: str,
    catalog: SemanticCatalog,
    spec: DocumentSpec,
    *,
    year: int | None = None,
    month: int | None = None,
    record_key: str | None = None,
    max_records: int | None = None,
) -> bytes:
    # 1. Wide per-record row. Labels = refs so we can read values back by ref.
    filters: list[FilterClause] = []
    if spec.period_year_ref and spec.period_month_ref and year and month:
        filters.append(FilterClause(ref=spec.period_year_ref, op=FilterOp.EQ, value=year))
        filters.append(FilterClause(ref=spec.period_month_ref, op=FilterOp.EQ, value=month))
    if spec.record_key_ref and record_key:
        filters.append(FilterClause(ref=spec.record_key_ref, op=FilterOp.EQ, value=record_key))

    data_spec = DataSpec(
        entity="employee",
        fields=[FieldSelection(ref=r, label=r) for r in spec.value_refs()],
        filters=filters,
    )
    result = run_query(
        ctx=ctx, datamart_key=datamart_key, spec=data_spec, catalog=catalog,
        params={}, row_limit=100_000,
    )
    rows = result.rows[:max_records] if max_records else result.rows

    # 2. Detail blocks (one query per enabled provider).
    detail_data: dict[str, dict[str, list[list[dict]]]] = {}
    for blk in spec.detail_blocks:
        if blk.enabled and blk.provider in DETAIL_PROVIDERS:
            detail_data[blk.provider] = DETAIL_PROVIDERS[blk.provider](
                ctx, datamart_key, year=year, month=month, record_key=record_key,
            )

    # 3. Per-record render context.
    period_label = (
        f"Period: {calendar.month_name[month]} {year}" if year and month else None
    )
    records = []
    for row in rows:
        rk = str(row.get(spec.record_key_ref)) if spec.record_key_ref else None
        records.append(
            {
                "period_label": period_label,
                "identity": [
                    {"label": ln.label, "value": row.get(ln.ref) or ""}
                    for ln in spec.identity_fields
                ],
                "sections": [
                    {
                        "title": s.title,
                        "lines": [_line_ctx(ln, row) for ln in s.lines],
                        "total": _line_ctx(s.total, row),
                    }
                    for s in spec.sections
                ],
                "detail_blocks": [
                    {"title": blk.title, "rows": detail_data.get(blk.provider, {}).get(rk or "", [])}
                    for blk in spec.detail_blocks if blk.enabled
                ],
            }
        )

    context = {
        "company_name": spec.company_name or "",
        "value_label": spec.value_label,
        "logo_data_url": spec.logo_data_url,
        "footer": spec.footer,
        "records": records,
    }
    return render_document_pdf(context)

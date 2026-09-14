"""Phase 6E payroll extractors — compliance, multi-currency, benefits, analyze, loan masters.

Skips extraction when source tables are absent (optional MintHRM modules).
"""
from __future__ import annotations

from typing import Callable

from sqlalchemy.engine import Engine

from app.services.hr_etl.extractors import _bool, _float, _int, _safe_datetime, _str, _stream_extract
from app.services.hr_etl.extractors_minthrm import _payroll_run_id
from app.services.hr_etl.payroll_source import optional_extractor
from app.services.hr_etl.sql_dialect import sql_cast_text, sql_now

_NOW = sql_now()

_PAYROLL_RUN_ID_LN = _payroll_run_id(
    "b.ref_payroll_group_id", "ln.proc_ln_proc_year", "ln.proc_ln_proc_month", "ln.proc_ln_proc_half"
)
_PAYROLL_RUN_ID_IP = _payroll_run_id(
    "b.ref_payroll_group_id", "ip.proc_ipd_proc_year", "ip.proc_ipd_proc_month", "ip.proc_ipd_proc_half"
)
_PAYROLL_RUN_ID_BC = _payroll_run_id(
    "b.ref_payroll_group_id", "b.psbc_proc_year", "b.psbc_proc_month", "b.psbc_proc_half"
)
_PAYROLL_RUN_ID_SAC = _payroll_run_id(
    "b.ref_payroll_group_id", "c.psac_proc_year", "c.psac_proc_month", "c.psac_proc_half"
)
_PAYROLL_RUN_ID_MC = _payroll_run_id(
    "b.ref_payroll_group_id", "m.pmce_proc_year", "m.pmce_proc_month", "m.pmce_proc_half"
)
_PAYROLL_RUN_ID_NC = _payroll_run_id(
    "b.ref_payroll_group_id", "n.pncpi_proc_year", "n.pncpi_proc_month", "n.pncpi_proc_half"
)
_PAYROLL_RUN_ID_NB = _payroll_run_id(
    "b.ref_payroll_group_id", "nb.pncb_proc_year", "nb.pncb_proc_month", "nb.pncb_proc_half"
)


_optional = optional_extractor  # backward-compatible alias


def extract_payroll_loan_data_only(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """processed_loan_data → stg_payroll_loan_data."""
    sql = f"""
        SELECT
            ln.proc_ln_id                                 AS id,
            {_PAYROLL_RUN_ID_LN.strip()}                  AS payroll_run_id,
            ln.ref_emp_id                                 AS employee_id,
            NULL                                          AS loan_id,
            NULL                                          AS installment_id,
            NULL                                          AS installment_no,
            NULLIF(TRIM(ln.proc_loan_type_name), '')      AS deduction_name,
            COALESCE(ln.proc_ln_amount, 0)                AS amount,
            NULL                                          AS remaining_balance,
            0                                             AS is_final_installment,
            ln.proc_ln_proc_year                          AS proc_year,
            ln.proc_ln_proc_month                         AS proc_month,
            COALESCE(ln.proc_ln_proc_half, 0)             AS proc_half,
            COALESCE(ln.proc_ln_update_date, {_NOW})      AS created_at,
            COALESCE(ln.proc_ln_update_date, {_NOW})      AS updated_at
        FROM processed_loan_data ln
        LEFT JOIN processed_sal_basic_data b
            ON b.ref_emp_id = ln.ref_emp_id
           AND b.psb_proc_year = ln.proc_ln_proc_year
           AND b.psb_proc_month = ln.proc_ln_proc_month
           AND COALESCE(b.psb_proc_half, 0) = COALESCE(ln.proc_ln_proc_half, 0)
        WHERE ln.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_loan_data", sql,
        [
            ("id", _int), ("payroll_run_id", _int), ("employee_id", _int),
            ("loan_id", _int), ("installment_id", _int), ("installment_no", _int),
            ("deduction_name", _str), ("amount", _float), ("remaining_balance", _float),
            ("is_final_installment", _bool),
            ("proc_year", _int), ("proc_month", _int), ("proc_half", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_payroll_installment_data_only(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """processed_installment_payment_data → stg_payroll_installment_payments."""
    sql = f"""
        SELECT
            ip.proc_ipd_id                                AS id,
            {_PAYROLL_RUN_ID_IP.strip()}                  AS payroll_run_id,
            ip.ref_emp_id                                 AS employee_id,
            NULL                                          AS loan_id,
            NULL                                          AS installment_id,
            NULL                                          AS installment_no,
            NULLIF(TRIM(ip.proc_ipd_type_name), '')       AS deduction_name,
            COALESCE(ip.proc_ipd_amount, 0)               AS amount,
            NULL                                          AS remaining_balance,
            0                                             AS is_final_installment,
            ip.proc_ipd_proc_year                         AS proc_year,
            ip.proc_ipd_proc_month                        AS proc_month,
            COALESCE(ip.proc_ipd_proc_half, 0)            AS proc_half,
            COALESCE(ip.proc_update_date, {_NOW})         AS created_at,
            COALESCE(ip.proc_update_date, {_NOW})         AS updated_at
        FROM processed_installment_payment_data ip
        LEFT JOIN processed_sal_basic_data b
            ON b.ref_emp_id = ip.ref_emp_id
           AND b.psb_proc_year = ip.proc_ipd_proc_year
           AND b.psb_proc_month = ip.proc_ipd_proc_month
           AND COALESCE(b.psb_proc_half, 0) = COALESCE(ip.proc_ipd_proc_half, 0)
        WHERE ip.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_installment_payments", sql,
        [
            ("id", _int), ("payroll_run_id", _int), ("employee_id", _int),
            ("loan_id", _int), ("installment_id", _int), ("installment_no", _int),
            ("deduction_name", _str), ("amount", _float), ("remaining_balance", _float),
            ("is_final_installment", _bool),
            ("proc_year", _int), ("proc_month", _int), ("proc_half", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_payroll_compliance_basic(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    sql = f"""
        SELECT
            b.psbc_id                                     AS id,
            {_PAYROLL_RUN_ID_BC.strip()}                  AS payroll_run_id,
            b.ref_emp_id                                  AS employee_id,
            COALESCE(b.psbc_gross_salary, b.gross_salary_vw, b.psbc_net_total, 0)
                                                          AS compliance_salary,
            COALESCE(b.psbc_ot_amount, b.psbc_ot, 0)      AS compliance_ot,
            COALESCE(b.psbc_nopay_amount, b.psbc_nopay, 0)
                                                          AS compliance_nopay,
            COALESCE(b.psbc_attendance_days, 0)           AS compliance_attendance_days,
            COALESCE(b.psbc_work_hours, 0)                AS compliance_work_hours,
            COALESCE(NULLIF(TRIM(b.psbc_status), ''), 'processed')
                                                          AS compliance_status,
            b.psbc_proc_year                              AS proc_year,
            b.psbc_proc_month                             AS proc_month,
            COALESCE(b.psbc_proc_half, 0)                 AS proc_half,
            COALESCE(b.psbc_update_date, {_NOW})          AS created_at,
            COALESCE(b.psbc_update_date, {_NOW})          AS updated_at
        FROM processed_sal_basic_data_compliance b
        WHERE b.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_compliance_basic", sql,
        [
            ("id", _int), ("payroll_run_id", _int), ("employee_id", _int),
            ("compliance_salary", _float), ("compliance_ot", _float),
            ("compliance_nopay", _float), ("compliance_attendance_days", _float),
            ("compliance_work_hours", _float), ("compliance_status", _str),
            ("proc_year", _int), ("proc_month", _int), ("proc_half", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_payroll_compliance_attendance(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    sql = f"""
        SELECT
            c.psac_id                                     AS id,
            {_PAYROLL_RUN_ID_SAC.strip()}                 AS payroll_run_id,
            c.ref_emp_id                                  AS employee_id,
            {sql_cast_text('c.psac_type')}                AS attendance_item_type,
            COALESCE(c.psac_days, c.psac_value, 0)        AS attendance_days,
            COALESCE(c.psac_payable_days, 0)              AS payable_days,
            COALESCE(c.psac_absent_days, 0)               AS absent_days,
            COALESCE(c.psac_late_days, 0)                 AS late_days,
            COALESCE(c.psac_nopay_days, 0)                AS nopay_days,
            COALESCE(c.psac_ot_hours, 0)                  AS ot_hours,
            COALESCE(c.psac_amount, 0)                    AS attendance_amount,
            COALESCE(c.psac_deduction, 0)                 AS attendance_deduction,
            c.psac_proc_year                              AS proc_year,
            c.psac_proc_month                             AS proc_month,
            COALESCE(c.psac_proc_half, 0)                 AS proc_half,
            COALESCE(c.psac_update_date, {_NOW})          AS created_at,
            COALESCE(c.psac_update_date, {_NOW})          AS updated_at
        FROM processed_sal_attendance_compliance c
        LEFT JOIN processed_sal_basic_data b
            ON b.ref_emp_id = c.ref_emp_id
           AND b.psb_proc_year = c.psac_proc_year
           AND b.psb_proc_month = c.psac_proc_month
           AND COALESCE(b.psb_proc_half, 0) = COALESCE(c.psac_proc_half, 0)
        WHERE c.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_compliance_attendance", sql,
        [
            ("id", _int), ("payroll_run_id", _int), ("employee_id", _int),
            ("attendance_item_type", _str),
            ("attendance_days", _float), ("payable_days", _float),
            ("absent_days", _float), ("late_days", _float), ("nopay_days", _float),
            ("ot_hours", _float), ("attendance_amount", _float),
            ("attendance_deduction", _float),
            ("proc_year", _int), ("proc_month", _int), ("proc_half", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_payroll_multi_currency(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    sql = f"""
        SELECT
            m.pmce_id                                     AS id,
            {_PAYROLL_RUN_ID_MC.strip()}                  AS payroll_run_id,
            m.ref_emp_id                                  AS employee_id,
            COALESCE(NULLIF(TRIM(m.pmce_source_currency), ''), NULLIF(TRIM(m.source_currency), ''), 'LKR')
                                                          AS source_currency,
            COALESCE(NULLIF(TRIM(m.pmce_target_currency), ''), NULLIF(TRIM(m.target_currency), ''), 'LKR')
                                                          AS target_currency,
            COALESCE(m.pmce_exchange_rate, m.exchange_rate, 1)
                                                          AS exchange_rate,
            COALESCE(m.pmce_salary_amount, m.salary_amount, 0)
                                                          AS salary_amount,
            COALESCE(m.pmce_converted_amount, m.converted_amount, 0)
                                                          AS converted_amount,
            m.pmce_proc_year                              AS proc_year,
            m.pmce_proc_month                             AS proc_month,
            COALESCE(m.pmce_proc_half, 0)                 AS proc_half,
            COALESCE(m.pmce_update_date, {_NOW})          AS created_at,
            COALESCE(m.pmce_update_date, {_NOW})          AS updated_at
        FROM processed_multi_currency_for_emp_sal m
        LEFT JOIN processed_sal_basic_data b
            ON b.ref_emp_id = m.ref_emp_id
           AND b.psb_proc_year = m.pmce_proc_year
           AND b.psb_proc_month = m.pmce_proc_month
           AND COALESCE(b.psb_proc_half, 0) = COALESCE(m.pmce_proc_half, 0)
        WHERE m.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_multi_currency", sql,
        [
            ("id", _int), ("payroll_run_id", _int), ("employee_id", _int),
            ("source_currency", _str), ("target_currency", _str),
            ("exchange_rate", _float), ("salary_amount", _float),
            ("converted_amount", _float),
            ("proc_year", _int), ("proc_month", _int), ("proc_half", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_payroll_noncash_benefits(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    sql = f"""
        SELECT
            nb.pncb_id                                    AS id,
            {_PAYROLL_RUN_ID_NB.strip()}                  AS payroll_run_id,
            nb.ref_emp_id                                 AS employee_id,
            NULLIF(TRIM(nb.pncb_benefit_name), '')         AS benefit_name,
            NULLIF(TRIM(nb.pncb_benefit_type), '')        AS benefit_type,
            COALESCE(nb.pncb_benefit_value, nb.pncb_amount, 0)
                                                          AS benefit_value,
            COALESCE(nb.pncb_taxable_value, 0)            AS taxable_value,
            nb.pncb_proc_year                             AS proc_year,
            nb.pncb_proc_month                            AS proc_month,
            COALESCE(nb.pncb_proc_half, 0)                AS proc_half,
            COALESCE(nb.pncb_update_date, {_NOW})         AS created_at,
            COALESCE(nb.pncb_update_date, {_NOW})         AS updated_at
        FROM prl_processed_nonecash_benefits nb
        LEFT JOIN processed_sal_basic_data b
            ON b.ref_emp_id = nb.ref_emp_id
           AND b.psb_proc_year = nb.pncb_proc_year
           AND b.psb_proc_month = nb.pncb_proc_month
           AND COALESCE(b.psb_proc_half, 0) = COALESCE(nb.pncb_proc_half, 0)
        WHERE nb.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_noncash_benefits", sql,
        [
            ("id", _int), ("payroll_run_id", _int), ("employee_id", _int),
            ("benefit_name", _str), ("benefit_type", _str),
            ("benefit_value", _float), ("taxable_value", _float),
            ("proc_year", _int), ("proc_month", _int), ("proc_half", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_payroll_non_consider_items(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    sql = f"""
        SELECT
            n.pncpi_id                                    AS id,
            {_PAYROLL_RUN_ID_NC.strip()}                  AS payroll_run_id,
            n.ref_emp_id                                  AS employee_id,
            NULLIF(TRIM(n.pncpi_item_name), '')           AS item_name,
            COALESCE(n.pncpi_amount, 0)                   AS amount,
            CASE WHEN COALESCE(n.pncpi_consider_for_payroll, 1) = 1 THEN 1 ELSE 0 END
                                                          AS is_considered_for_payroll,
            n.pncpi_proc_year                             AS proc_year,
            n.pncpi_proc_month                            AS proc_month,
            COALESCE(n.pncpi_proc_half, 0)                AS proc_half,
            COALESCE(n.pncpi_update_date, {_NOW})         AS created_at,
            COALESCE(n.pncpi_update_date, {_NOW})         AS updated_at
        FROM processed_non_consider_pay_items n
        LEFT JOIN processed_sal_basic_data b
            ON b.ref_emp_id = n.ref_emp_id
           AND b.psb_proc_year = n.pncpi_proc_year
           AND b.psb_proc_month = n.pncpi_proc_month
           AND COALESCE(b.psb_proc_half, 0) = COALESCE(n.pncpi_proc_half, 0)
        WHERE n.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_non_consider_items", sql,
        [
            ("id", _int), ("payroll_run_id", _int), ("employee_id", _int),
            ("item_name", _str), ("amount", _float), ("is_considered_for_payroll", _bool),
            ("proc_year", _int), ("proc_month", _int), ("proc_half", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_payroll_salary_analyze(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    sql = f"""
        SELECT
            a.pra_id                                      AS id,
            a.ref_payroll_group_id                        AS payroll_group_id,
            a.pra_proc_year                               AS proc_year,
            a.pra_proc_month                              AS proc_month,
            COALESCE(a.pra_proc_half, 0)                  AS proc_half,
            a.pra_process_start                           AS process_start_time,
            a.pra_process_end                             AS process_end_time,
            COALESCE(a.pra_processed_employee_count, 0)   AS processed_employee_count,
            COALESCE(a.pra_failed_employee_count, 0)      AS failed_employee_count,
            COALESCE(a.pra_reversed_employee_count, 0)    AS reversed_employee_count,
            NULLIF(TRIM(a.pra_process_type), '')          AS process_type,
            COALESCE(NULLIF(TRIM(a.pra_status), ''), 'processed')
                                                          AS process_status,
            NULLIF(TRIM(a.pra_triggered_by), '')          AS triggered_by,
            COALESCE(a.pra_update_date, {_NOW})           AS created_at,
            COALESCE(a.pra_update_date, {_NOW})           AS updated_at
        FROM prl_processed_salary_analyze a
        WHERE a.ref_payroll_group_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_salary_analyze", sql,
        [
            ("id", _int), ("payroll_group_id", _int),
            ("proc_year", _int), ("proc_month", _int), ("proc_half", _int),
            ("process_start_time", _safe_datetime), ("process_end_time", _safe_datetime),
            ("processed_employee_count", _int), ("failed_employee_count", _int),
            ("reversed_employee_count", _int),
            ("process_type", _str), ("process_status", _str), ("triggered_by", _str),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_prl_loan_master(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    sql = f"""
        SELECT
            l.loan_id                                     AS id,
            l.ref_emp_id                                  AS employee_id,
            NULLIF(TRIM(l.loan_type_name), '')            AS loan_type_name,
            COALESCE(l.loan_amount, 0)                    AS loan_amount,
            COALESCE(l.loan_balance, 0)                   AS loan_balance,
            COALESCE(l.is_active, 1)                      AS is_active,
            COALESCE(l.loan_create_date, {_NOW})          AS created_at,
            COALESCE(l.loan_update_date, {_NOW})          AS updated_at
        FROM prl_loan l
        WHERE l.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_prl_loan", sql,
        [
            ("id", _int), ("employee_id", _int),
            ("loan_type_name", _str), ("loan_amount", _float), ("loan_balance", _float),
            ("is_active", _bool),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_payroll_salary_analyze_data(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    sql = f"""
        SELECT
            d.prad_id                                     AS id,
            d.ref_analyze_id                              AS analyze_id,
            d.ref_emp_id                                  AS employee_id,
            COALESCE(d.prad_amount, 0)                    AS line_amount,
            NULLIF(TRIM(d.prad_line_name), '')            AS line_name,
            d.prad_proc_year                              AS proc_year,
            d.prad_proc_month                             AS proc_month,
            COALESCE(d.prad_proc_half, 0)                 AS proc_half,
            COALESCE(d.prad_update_date, {_NOW})          AS created_at,
            COALESCE(d.prad_update_date, {_NOW})          AS updated_at
        FROM prl_processed_salary_analyze_data d
        WHERE d.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_salary_analyze_data", sql,
        [
            ("id", _int), ("analyze_id", _int), ("employee_id", _int),
            ("line_amount", _float), ("line_name", _str),
            ("proc_year", _int), ("proc_month", _int), ("proc_half", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


PHASE6_EXTRACTORS: list[tuple[str, Callable]] = [
    ("stg_payroll_loan_data", extract_payroll_loan_data_only),
    ("stg_payroll_installment_payments", extract_payroll_installment_data_only),
    (
        "stg_payroll_compliance_basic",
        _optional(
            "processed_sal_basic_data_compliance",
            extract_payroll_compliance_basic,
            "psbc_id",
            "ref_emp_id",
            "psbc_proc_year",
            "psbc_proc_month",
        ),
    ),
    (
        "stg_payroll_compliance_attendance",
        _optional(
            "processed_sal_attendance_compliance",
            extract_payroll_compliance_attendance,
            "psac_id",
            "ref_emp_id",
            "psac_proc_year",
            "psac_proc_month",
        ),
    ),
    (
        "stg_payroll_multi_currency",
        _optional(
            "processed_multi_currency_for_emp_sal",
            extract_payroll_multi_currency,
            "pmce_id",
            "ref_emp_id",
            "pmce_proc_year",
            "pmce_proc_month",
        ),
    ),
    (
        "stg_payroll_noncash_benefits",
        _optional(
            "prl_processed_nonecash_benefits",
            extract_payroll_noncash_benefits,
            "pncb_id",
            "ref_emp_id",
            "pncb_proc_year",
            "pncb_proc_month",
        ),
    ),
    (
        "stg_payroll_non_consider_items",
        _optional(
            "processed_non_consider_pay_items",
            extract_payroll_non_consider_items,
            "pncpi_id",
            "ref_emp_id",
            "pncpi_proc_year",
            "pncpi_proc_month",
        ),
    ),
    (
        "stg_payroll_salary_analyze",
        _optional(
            "prl_processed_salary_analyze",
            extract_payroll_salary_analyze,
            "pra_id",
            "ref_payroll_group_id",
            "pra_proc_year",
            "pra_proc_month",
        ),
    ),
    (
        "stg_prl_loan",
        _optional("prl_loan", extract_prl_loan_master, "loan_id", "ref_emp_id"),
    ),
    (
        "stg_payroll_salary_analyze_data",
        _optional(
            "prl_processed_salary_analyze_data",
            extract_payroll_salary_analyze_data,
            "prad_id",
            "ref_emp_id",
            "prad_proc_year",
            "prad_proc_month",
        ),
    ),
]

PHASE6_INCREMENTAL_TABLES: set[str] = {name for name, _ in PHASE6_EXTRACTORS}

"""Dialect-aware SQL fragments for HR ETL extractors (MySQL / PostgreSQL).

Used inside ``source_dialect()`` context (see ``source_connection``).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.hr_etl.source_connection import SourceType


def _dialect() -> "SourceType":
    from app.services.hr_etl.source_connection import get_dialect

    return get_dialect()


def sql_now() -> str:
    return "NOW()"  # valid in both MySQL and PostgreSQL


def sql_concat(*parts: str) -> str:
    if _dialect() == "postgres":
        rendered: list[str] = []
        for p in parts:
            p = p.strip()
            if p.startswith("'") and p.endswith("'"):
                rendered.append(p)
            else:
                rendered.append(f"({p})::text")
        return " || ".join(rendered)
    return f"CONCAT({', '.join(parts)})"


def sql_lpad(expr: str, length: int, pad: str) -> str:
    if _dialect() == "postgres":
        return f"LPAD(({expr})::text, {length}, '{pad}')"
    return f"LPAD({expr}, {length}, '{pad}')"


def sql_cast_text(expr: str) -> str:
    if _dialect() == "postgres":
        return f"({expr})::text"
    return f"CAST({expr} AS CHAR)"


def sql_cast_signed_int(expr: str) -> str:
    if _dialect() == "postgres":
        return f"({expr})::bigint"
    return f"CAST({expr} AS SIGNED)"


def sql_substring_index(expr: str, delim: str, count: int) -> str:
    """MySQL SUBSTRING_INDEX compatible (count > 0: from left; count < 0: last segment)."""
    if count > 0:
        if _dialect() == "postgres":
            esc = delim.replace("'", "''")
            return f"split_part({expr}, '{esc}', {count})"
        return f"SUBSTRING_INDEX({expr}, '{delim}', {count})"
    if _dialect() == "postgres":
        arr = f"regexp_split_to_array(TRIM({expr}), E'\\\\s+')"
        return f"({arr})[array_length({arr}, 1)]"
    return f"SUBSTRING_INDEX({expr}, '{delim}', {count})"


def sql_hash_mod_int(expr: str, modulo: int = 2_147_483_647) -> str:
    """Stable-ish int bucket from string (CRC32 on MySQL, hashtext on PostgreSQL)."""
    if _dialect() == "postgres":
        return f"(ABS(hashtext({expr})::bigint) % {modulo})"
    return f"ABS(CRC32({expr})) % {modulo}"


def sql_date_diff_inclusive(start: str, end: str) -> str:
    """Inclusive day count (MySQL DATEDIFF(end, start) + 1)."""
    if _dialect() == "postgres":
        return f"(({end})::date - ({start})::date + 1)"
    return f"DATEDIFF({end}, {start}) + 1"


def sql_zero_date_null(expr: str) -> str:
    if _dialect() == "postgres":
        return (
            f"CASE WHEN {expr} IS NULL OR {expr} < DATE '1900-01-01' "
            f"THEN NULL ELSE {expr} END"
        )
    return f"NULLIF({expr}, '0000-00-00')"


def sql_safe_date_case(expr: str) -> str:
    """Map invalid / zero dates to NULL."""
    if _dialect() == "postgres":
        return (
            f"CASE WHEN {expr} IS NULL OR {expr} < TIMESTAMP '1900-01-01' "
            f"THEN NULL ELSE ({expr})::date END"
        )
    return f"""CASE
                WHEN {expr} IS NULL THEN NULL
                WHEN {expr} < '1900-01-01' THEN NULL
                ELSE DATE({expr})
            END"""


def sql_timestamp_from_date_and_time(date_expr: str, time_expr: str) -> str:
    if _dialect() == "postgres":
        return f"(({date_expr})::date + ({time_expr})::time)"
    return f"TIMESTAMP({date_expr}, {time_expr})"


def sql_year(expr: str) -> str:
    if _dialect() == "postgres":
        return f"EXTRACT(YEAR FROM ({expr}))::integer"
    return f"YEAR({expr})"


def sql_month(expr: str) -> str:
    if _dialect() == "postgres":
        return f"EXTRACT(MONTH FROM ({expr}))::integer"
    return f"MONTH({expr})"


def sql_time_to_seconds(expr: str) -> str:
    """Convert TIME / interval column to seconds (prl_overtime OT duration fields)."""
    if _dialect() == "postgres":
        return (
            f"COALESCE(EXTRACT(EPOCH FROM ({expr})::interval), "
            f"EXTRACT(EPOCH FROM ({expr})::time), 0)"
        )
    return f"COALESCE(TIME_TO_SEC({expr}), 0)"


def sql_minute_diff(start_expr: str, end_expr: str) -> str:
    if _dialect() == "postgres":
        return (
            f"GREATEST(EXTRACT(EPOCH FROM (({end_expr})::timestamp - "
            f"({start_expr})::timestamp)) / 60, 0)"
        )
    return f"GREATEST(TIMESTAMPDIFF(MINUTE, {start_expr}, {end_expr}), 0)"


def sql_payroll_run_code(
    group_expr: str,
    year_expr: str,
    month_expr: str,
    half_expr: str,
) -> str:
    half_part = sql_concat("'-H'", half_expr)
    half_suffix = (
        f"CASE WHEN COALESCE({half_expr}, 0) > 0 "
        f"THEN {half_part} ELSE '' END"
    )
    return sql_concat(
        "'PG'",
        f"COALESCE({group_expr}, 1)",
        "'-'",
        year_expr,
        "'-'",
        sql_lpad(month_expr, 2, "0"),
        half_suffix,
    )


def qident(name: str) -> str:
    from app.services.hr_etl.source_connection import qident as _q

    return _q(name)

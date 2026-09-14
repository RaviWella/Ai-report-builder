"""
Pre-execution join semantics: catch label↔surrogate mismatches before the warehouse runs.

Examples blocked/repaired:
- mart_employee_current.designation (text title) = dim_designation.designation_sk (surrogate)
- source_desig_id = designation_sk (use source_desig_id = source_desig_id instead)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

import sqlglot
from sqlglot import exp

from ..schema_broker import SchemaGrounding
from ..semantic.semantic_layer import _load_catalog
from .sql_aliases import alias_to_table_short
from .sql_column_allowlist import columns_by_table_short

logger = logging.getLogger("ai_services.datamart.join_semantics")

_LABEL_COLUMNS = frozenset(
    {
        "designation",
        "designation_name",
        "emp_fullname",
        "full_name",
        "employee_name",
        "emp_name",
        "leave_type_name",
        "branch",
        "department",
        "job_title",
        "title",
        "bank_name",
        "shift_name",
        "payroll_group_name",
        "nationality",
        "superior_fullname",
    }
)

_SURROGATE_SUFFIX = "_sk"
_SOURCE_ID_RE = re.compile(r"^source_.*_id$", re.IGNORECASE)


@dataclass(frozen=True)
class _JoinEq:
    left_alias: str
    left_col: str
    right_alias: str
    right_col: str


def _column_role(column: str) -> str:
    col = (column or "").strip().lower()
    if not col:
        return "neutral"
    if col in _LABEL_COLUMNS:
        return "label"
    if col.endswith(_SURROGATE_SUFFIX):
        return "surrogate"
    if _SOURCE_ID_RE.match(col):
        return "source_id"
    if col.endswith("_id"):
        return "fk_id"
    if col.endswith("_name") or col.endswith("_code"):
        return "label"
    return "neutral"


def _unwrap_column(node: exp.Expression) -> Optional[exp.Column]:
    if isinstance(node, exp.Cast):
        return _unwrap_column(node.this)
    if isinstance(node, exp.Paren):
        return _unwrap_column(node.this)
    if isinstance(node, exp.Column):
        return node
    return None


def _eq_predicates(node: Optional[exp.Expression]) -> list[_JoinEq]:
    if node is None:
        return []
    out: list[_JoinEq] = []

    def walk(n: exp.Expression) -> None:
        if isinstance(n, exp.And):
            walk(n.left)
            walk(n.right)
            return
        if isinstance(n, exp.EQ):
            lc = _unwrap_column(n.left)
            rc = _unwrap_column(n.right)
            if lc and rc and lc.name and rc.name:
                out.append(
                    _JoinEq(
                        left_alias=(lc.table or "").lower(),
                        left_col=lc.name.lower(),
                        right_alias=(rc.table or "").lower(),
                        right_col=rc.name.lower(),
                    )
                )

    walk(node)
    return out


def _catalog_allowed_pairs() -> set[tuple[str, str, str, str]]:
    """(left_table, left_col, right_table, right_col) from semantic catalog joins."""
    catalog = _load_catalog()
    pairs: set[tuple[str, str, str, str]] = set()
    for j in catalog.get("joins") or []:
        if not isinstance(j, dict):
            continue
        lt = str(j.get("left_table") or "").lower()
        rt = str(j.get("right_table") or "").lower()
        lc = str(j.get("left_column") or "").lower()
        rc = str(j.get("right_column") or "").lower()
        if lt and rt and lc and rc:
            pairs.add((lt, lc, rt, rc))
            pairs.add((rt, rc, lt, lc))
    return pairs


def _table_has_col(cols_by_short: dict[str, set[str]], table: str, column: str) -> bool:
    return column.lower() in cols_by_short.get(table.lower(), set())


def _pair_allowed(
    left_table: str,
    left_col: str,
    right_table: str,
    right_col: str,
    *,
    catalog_pairs: set[tuple[str, str, str, str]],
) -> bool:
    lt, rt = left_table.lower(), right_table.lower()
    lc, rc = left_col.lower(), right_col.lower()
    if (lt, lc, rt, rc) in catalog_pairs:
        return True
    if lc == rc and lc not in _LABEL_COLUMNS:
        return True
    return False


def _describe_bad_join(
    left_table: str,
    left_col: str,
    right_table: str,
    right_col: str,
) -> Optional[str]:
    left_role = _column_role(left_col)
    right_role = _column_role(right_col)
    if left_role == "label" and right_role in ("surrogate", "fk_id", "source_id"):
        return (
            f"Invalid join: {left_table}.{left_col} is a display/label column but "
            f"{right_table}.{right_col} is a key column. Join keys must match "
            f"(e.g. employee_sk = employee_sk, source_desig_id = source_desig_id). "
            f"For job title on mart_employee_current use column designation directly — "
            f"do not join dim_designation on designation_sk."
        )
    if right_role == "label" and left_role in ("surrogate", "fk_id", "source_id"):
        return (
            f"Invalid join: {left_table}.{left_col} is a key column but "
            f"{right_table}.{right_col} is a display/label column. "
            f"Use the dimension key on both sides, then SELECT the *_name column."
        )
    if left_role == "surrogate" and right_role == "label":
        return (
            f"Invalid join: {left_table}.{left_col} (surrogate key) cannot join "
            f"{right_table}.{right_col} (label text)."
        )
    if left_col != right_col and left_role != "neutral" and right_role != "neutral":
        if left_role == "source_id" and right_role == "surrogate":
            return (
                f"Invalid join: {left_table}.{left_col} should join "
                f"{right_table}.source_desig_id (or matching source_*_id), not "
                f"{right_col}."
            )
    return None


def validate_join_semantics(
    sql: str,
    grounding: SchemaGrounding,
) -> Optional[str]:
    """
    Return an error message when JOIN keys pair label columns with surrogate/FK keys,
    or use catalog-forbidden column pairs.
    """
    if not grounding.columns_by_table:
        return None
    try:
        tree = sqlglot.parse_one(sql, dialect="postgres")
    except Exception as exc:  # noqa: BLE001
        return f"Join semantics check could not parse SQL: {exc}"

    alias_map = alias_to_table_short(sql)
    if not alias_map:
        return None

    cols_by_short = columns_by_table_short(grounding)
    catalog_pairs = _catalog_allowed_pairs()
    errors: list[str] = []

    for join in tree.find_all(exp.Join):
        on = join.args.get("on")
        for pred in _eq_predicates(on):
            la, lc, ra, rc = pred.left_alias, pred.left_col, pred.right_alias, pred.right_col
            lt = alias_map.get(la) or alias_map.get(la.lower())
            rt = alias_map.get(ra) or alias_map.get(ra.lower())
            if not lt or not rt:
                continue
            if not _table_has_col(cols_by_short, lt, lc):
                continue
            if not _table_has_col(cols_by_short, rt, rc):
                continue
            if _pair_allowed(lt, lc, rt, rc, catalog_pairs=catalog_pairs):
                continue
            msg = _describe_bad_join(lt, lc, rt, rc)
            if msg:
                errors.append(msg)

    if not errors:
        return None
    return errors[0]


def try_repair_join_semantics(
    sql: str,
    grounding: SchemaGrounding,
) -> Optional[str]:
    """
    Deterministic fixes for common bad joins (before execution).
    Returns rewritten SQL or None.
    """
    if not grounding.columns_by_table:
        return None
    cols_by_short = columns_by_table_short(grounding)
    alias_map = alias_to_table_short(sql)
    out = sql

    # source_*_id = *_sk → source_*_id = source_*_id when dimension has source column
    m = re.search(
        r"(\w+)\.(source_desig_id)(?:::text)?\s*=\s*(\w+)\.(designation_sk)(?:::text)?",
        out,
        flags=re.IGNORECASE,
    )
    if m:
        left_a, _, right_a, _ = m.groups()
        left_t = alias_map.get(left_a.lower(), "")
        right_t = alias_map.get(right_a.lower(), "")
        if _table_has_col(cols_by_short, right_t, "source_desig_id"):
            out = re.sub(
                rf"\b{re.escape(left_a)}\.source_desig_id(?:::text)?\s*=\s*"
                rf"{re.escape(right_a)}\.designation_sk(?:::text)?",
                f"{left_a}.source_desig_id = {right_a}.source_desig_id",
                out,
                count=1,
                flags=re.IGNORECASE,
            )

    # mart designation (label) = dim designation_sk — drop bad join; use mart designation in SELECT
    bad_mart_des = re.search(
        r"(\w+)\.designation(?:::text)?\s*=\s*(\w+)\.designation_sk(?:::text)?",
        out,
        flags=re.IGNORECASE,
    )
    if bad_mart_des:
        mart_a, dim_a = bad_mart_des.groups()
        mart_t = alias_map.get(mart_a.lower(), "")
        dim_t = alias_map.get(dim_a.lower(), "")
        if "mart_employee" in mart_t and "dim_designation" in dim_t:
            if _table_has_col(cols_by_short, mart_t, "designation"):
                out = re.sub(
                    rf"\s*JOIN\s+[\w.]+\.dim_designation\s+{re.escape(dim_a)}\s+"
                    rf"ON\s+{re.escape(mart_a)}\.designation(?:::text)?\s*=\s*"
                    rf"{re.escape(dim_a)}\.designation_sk(?:::text)?",
                    "",
                    out,
                    count=1,
                    flags=re.IGNORECASE,
                )
                out = re.sub(
                    rf"\b{re.escape(dim_a)}\.designation_name\b",
                    f"{mart_a}.designation",
                    out,
                    flags=re.IGNORECASE,
                )
                logger.info(
                    "join_semantics: removed bad mart.designation=dim.designation_sk join"
                )

    if out.strip() != sql.strip():
        return out
    return None

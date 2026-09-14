"""
Validate POST_PROCESS JSON against known result columns / schema allowlist.
"""
from __future__ import annotations

import re
from typing import Optional

from ..schema_broker import SchemaGrounding


def _allowed_column_names(
    grounding: Optional[SchemaGrounding],
    result_columns: Optional[list[str]],
) -> set[str]:
    allowed: set[str] = set()
    if result_columns:
        allowed.update(c.lower() for c in result_columns if c)
    if grounding:
        allowed.update(grounding.all_column_names())
    return allowed


def _check_col(name: str, allowed: set[str], ctx: str) -> Optional[str]:
    if not name:
        return f"{ctx}: missing column name"
    if name.lower() not in allowed:
        return f"{ctx}: column '{name}' is not in the SQL result or schema allowlist"
    return None


def validate_post_process_config(
    config: Optional[list[dict]],
    *,
    grounding: Optional[SchemaGrounding] = None,
    result_columns: Optional[list[str]] = None,
) -> Optional[str]:
    """
    Return an error message if any step references unknown columns; else None.
    """
    if not config:
        return None

    allowed = _allowed_column_names(grounding, result_columns)
    if not allowed:
        return None

    for i, step in enumerate(config):
        if not isinstance(step, dict):
            return f"POST_PROCESS step {i}: must be an object"
        stype = step.get("type")
        if stype == "add_percentage_column":
            err = _check_col(str(step.get("source_column", "")), allowed, f"step {i}")
            if err:
                return err
        elif stype == "append_aggregate_row":
            aggs = step.get("aggregations")
            if isinstance(aggs, dict):
                for col in aggs:
                    err = _check_col(str(col), allowed, f"step {i} aggregations")
                    if err:
                        return err
            lc = step.get("label_column")
            if lc:
                err = _check_col(str(lc), allowed, f"step {i} label_column")
                if err:
                    return err
        elif stype == "append_per_group_aggregate_rows":
            err = _check_col(str(step.get("group_column", "")), allowed, f"step {i} group_column")
            if err:
                return err
            aggs = step.get("aggregations")
            if isinstance(aggs, dict):
                for col in aggs:
                    err = _check_col(str(col), allowed, f"step {i} aggregations")
                    if err:
                        return err
            lc = step.get("label_column")
            if lc:
                err = _check_col(str(lc), allowed, f"step {i} label_column")
                if err:
                    return err
        elif stype == "add_derived_column":
            expr = str(step.get("expression", ""))
            for m in re.finditer(r"row\['([^']+)'\]", expr):
                err = _check_col(m.group(1), allowed, f"step {i} expression")
                if err:
                    return err
    return None

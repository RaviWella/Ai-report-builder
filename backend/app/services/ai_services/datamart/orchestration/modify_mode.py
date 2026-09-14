"""
Strict modify (continue_last) vs add-scenario behaviour.

Modify: edit only the anchored prior SQL / selected scenario(s).
Add scenario: new ADDITIONAL_RESULT_BLOCKS only; prior scenarios stay on server.
"""
from __future__ import annotations

import re
from typing import Optional

import sqlglot
from sqlglot import exp

from ..models import FollowUpMode
from ..scenario.scenario_scope import PRIMARY_SCENARIO_ID

_MODIFY_FOOTER = """

## Modify mode (mandatory — user chose "Modify last result")
- Apply **only** what the latest user message asks. Do **not** add columns, filters, joins, or scenarios they did not request.
- **Start from the anchored SQL** below (or in scenario anchors). Edit that query **in place** — same FROM/JOIN/WHERE unless they explicitly change those.
- **Do not** write a fresh report from different base tables.
- **Do not** output ADDITIONAL_RESULT_BLOCKS unless they explicitly asked for another dataset in this message.
- **Do not** use SQL:NONE unless the change is POST_PROCESS-only (labels/summary cards) with the same SELECT as the anchor.
"""


def is_modify_turn(
    follow_up_mode: Optional[FollowUpMode],
    *,
    is_new_question: bool,
    is_add_scenario: bool,
) -> bool:
    if is_new_question or is_add_scenario:
        return False
    if follow_up_mode == FollowUpMode.CONTINUE_LAST:
        return True
    # Legacy sessions without explicit mode still refine when not starting fresh.
    return follow_up_mode is None


def resolve_anchor_sql(
    *,
    previous_primary_sql: Optional[str],
    last_sql: Optional[str],
    targets: Optional[set[str]],
) -> Optional[str]:
    """SQL the model must minimally edit for this modify turn."""
    primary = (previous_primary_sql or last_sql or "").strip()
    if not primary:
        return None
    if targets and PRIMARY_SCENARIO_ID not in targets:
        return None
    return primary


def format_continue_last_modify_addon() -> str:
    return _MODIFY_FOOTER.strip()


def should_skip_deterministic_sql_shortcuts(
    *,
    is_modify: bool,
    is_add_scenario: bool,
    targets: Optional[set[str]],
) -> bool:
    """Catalog / verified-metric SQL must not replace a user modify request."""
    return is_modify or is_add_scenario or bool(targets)


def _tables_in_select(sql: str) -> set[str]:
    try:
        tree = sqlglot.parse_one(sql, dialect="postgres")
    except Exception:  # noqa: BLE001
        return set()
    names: set[str] = set()
    for table in tree.find_all(exp.Table):
        if table.name:
            names.add(str(table.name).lower())
    return names


def check_modify_sql_anchored(
    *,
    anchor_sql: Optional[str],
    new_sql: Optional[str],
) -> Optional[str]:
    """
    Block rewrites that ignore the prior query (modify mode only).
    Returns a user-facing error when the new SQL is not plausibly an edit of the anchor.
    """
    anchor = (anchor_sql or "").strip()
    new = (new_sql or "").strip()
    if not anchor or not new:
        return None

    anchor_tables = _tables_in_select(anchor)
    new_tables = _tables_in_select(new)
    if anchor_tables and new_tables and not anchor_tables.intersection(new_tables):
        return (
            "Modify mode must change the previous SQL in place. "
            "The new query uses different tables — adjust filters/columns on the prior query instead."
        )

    anchor_norm = re.sub(r"\s+", " ", anchor.lower())
    new_norm = re.sub(r"\s+", " ", new.lower())
    if len(anchor_norm) > 80 and anchor_norm not in new_norm:
        anchor_tokens = set(re.findall(r"[a-z_][a-z0-9_]*", anchor_norm))
        new_tokens = set(re.findall(r"[a-z_][a-z0-9_]*", new_norm))
        overlap = len(anchor_tokens & new_tokens) / max(len(anchor_tokens), 1)
        if overlap < 0.35:
            return (
                "Modify mode must minimally edit the previous SQL. "
                "Try a smaller change (e.g. add/remove one column or filter)."
            )
    return None

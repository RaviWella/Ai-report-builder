"""History shaping for add-scenario turns (do not leak prior SQL into the LLM)."""
from __future__ import annotations

import re

_SQL_BLOCK = re.compile(r"```sql\s*[\s\S]*?```", re.IGNORECASE)
_SQL_TURN = re.compile(r"\[SQL turn \d+\]\s*```sql[\s\S]*?```", re.IGNORECASE)
_POST_PROCESS = re.compile(
    r"\[POST_PROCESS[^\]]*\][\s\S]*?```json[\s\S]*?```",
    re.IGNORECASE,
)
_EXTRA_SQL = re.compile(
    r"\[Additional dataset:[^\]]+\]\s*```sql[\s\S]*?```",
    re.IGNORECASE,
)

_ADD_SCENARIO_HISTORY_FOOTER = """

## Add-scenario mode (mandatory)
Prior scenario result sets are **unchanged** on the server. Do **not** output a top-level `SQL:` block.
Author **only** the latest user question as one object inside **ADDITIONAL_RESULT_BLOCKS** (new block_id, title, sql).
"""


def format_add_scenario_history(history_text: str) -> str:
    """
    Remove prior SQL/POST_PROCESS from conversation history so the model does not
    merge or rewrite earlier scenarios when adding a new dataset.
    """
    raw = (history_text or "").strip()
    if not raw or raw == "(No previous messages)":
        return (
            "(Prior scenarios are stored separately — do not repeat or edit their SQL.)\n"
            + _ADD_SCENARIO_HISTORY_FOOTER.strip()
        )

    stripped = _SQL_TURN.sub("[Prior scenario SQL — kept on server; do not output again]", raw)
    stripped = _EXTRA_SQL.sub("[Prior extra scenario SQL — kept on server]", stripped)
    stripped = _SQL_BLOCK.sub("[SQL omitted — prior scenario unchanged]", stripped)
    stripped = _POST_PROCESS.sub("", stripped)
    return stripped.strip() + _ADD_SCENARIO_HISTORY_FOOTER

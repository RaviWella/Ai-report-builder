"""Second-pass LLM repairs when the first response omits SQL."""
from __future__ import annotations

import logging
from typing import Optional

from ..config import MAX_RESULT_ROWS, primary_schema_name
from ..llm.llm_client import LlmRole, call_llm
from ..llm.llm_response import (
    extract_narrative,
    extract_post_process_config,
    extract_sql,
    extract_last_sql_from_history,
)
from ..llm.prompt_budget import clip_text
from ..schema import execute_sql
from ..schema_broker import SchemaGrounding

logger = logging.getLogger("ai_services.datamart.sql_repairs")

_PER_GROUP_REPAIR_SYSTEM_PROMPT = """You are fixing a MintHRM datamart assistant reply.

The user asked for **per-group** numeric summaries (e.g. average salary **per branch**)
appended **under** the existing detail rows. The first model reply wrongly omitted SQL.

## Output format — MUST follow exactly (same as production datamart agent)

NARRATIVE:
<1-2 sentences>

SQL:
```sql
<EXACT copy of the PROVIDED last SQL — only whitespace/LIMIT __MAX_ROWS__ may differ>
```

POST_PROCESS:
```json
[
  {{
    "type": "append_per_group_aggregate_rows",
    "group_column": "<MUST be one of the result column names exactly>",
    "aggregations": {{"<numeric column name exactly>": "AVG"}},
    "label_column": "<a non-numeric display column from the result, e.g. employee name>",
    "label_format": "Branch average (__GRP__)"
  }}
]
```

Rules:
- Use ONLY column names from the provided comma-separated list.
- group_column must segment the detail rows (branch / pay group / department / company column).
- Append **one summary row per DISTINCT** group_column value present in the result — not a single group
  when the user asked for each/every/all companies or groups.
- aggregations values: AVG, SUM, MIN, MAX, or COUNT only. For counts of rows per group, use COUNT with any
  column name from the list (COUNT = number of detail rows in that group).
- label_format MUST contain the placeholder {group} (curly braces around the word group), e.g. "Branch average ({group})".
- Never output SQL:NONE. Never refuse if the last SQL and columns are provided.
"""

_PER_GROUP_REPAIR_USER_TEMPLATE = """## Column names from executing the last SQL (choose only from this list)
__RESULT_COLUMNS__

## Last SQL to reuse verbatim in your ```sql``` block
```sql
__LAST_SQL__
```

## User request
__QUESTION__

## Prior assistant reply (broken — missing executable SQL)
__PRIOR_REPLY__

Respond with NARRATIVE, SQL (same query as above), and POST_PROCESS JSON.
"""

_MISSING_SQL_REPAIR_SYSTEM = """You are the MintHRM datamart SQL assistant.
The previous reply did not include executable SQL. Respond with this format only:

NARRATIVE:
<1-2 sentences>

SQL:
```sql
<PostgreSQL SELECT using schema {schema}.table_name, LIMIT {max_rows}>
```

Rules:
- SELECT only (WITH allowed). Never SQL:NONE.
- Use only tables/columns from the schema section below.
- Map business terms via SEMANTIC GUIDANCE (employee name → full_name, branch → branch, etc.).
- Qualify every table: {schema}.<table>
- Omit POST_PROCESS unless the user explicitly needs appended summary rows.
- Do not refuse because the user used a business label; use the mapped physical column name.
"""


def _per_group_repair_system_text() -> str:
    s = _PER_GROUP_REPAIR_SYSTEM_PROMPT.replace("__MAX_ROWS__", str(MAX_RESULT_ROWS))
    return s.replace("__GRP__", "{group}")


def looks_like_per_group_aggregate_followup(question: str, history_text: str) -> bool:
    if "```sql" not in history_text.lower():
        return False
    q = question.lower()
    groupish = (
        "branch" in q
        or "by branch" in q
        or "per branch" in q
        or "pay group" in q
        or "paygroup" in q
        or ("payroll" in q and "group" in q)
        or "department" in q
        or "each group" in q
        or "per group" in q
        or "company" in q
        or "companies" in q
        or "organisation" in q
        or "organization" in q
    )
    wants_agg = (
        "average" in q
        or "avg" in q
        or "mean" in q
        or "total" in q
        or "sum" in q
        or "count" in q
        or "how many" in q
        or "number of" in q
    )
    wants_layout = (
        "row" in q
        or "under" in q
        or "below" in q
        or "append" in q
        or "add " in q
        or "each" in q
        or "per " in q
        or "record" in q
    )
    return groupish and wants_agg and wants_layout


def attempt_per_group_sql_repair(
    question: str,
    history_text: str,
    narrative: str,
    failed_llm_output: str,
) -> tuple[str, Optional[str], Optional[list[dict]]]:
    if not looks_like_per_group_aggregate_followup(question, history_text):
        return narrative, None, None

    last_sql = extract_last_sql_from_history(history_text)
    if not last_sql:
        logger.info("per_group repair skipped: no ```sql``` block in history")
        return narrative, None, None

    try:
        cols, _rows, _rc = execute_sql(last_sql)
        result_columns = ", ".join(cols)
    except RuntimeError as exc:
        logger.warning("per_group repair skipped: last history SQL does not run: %s", exc)
        return narrative, None, None

    repair_user = (
        _PER_GROUP_REPAIR_USER_TEMPLATE.replace("__RESULT_COLUMNS__", result_columns)
        .replace("__LAST_SQL__", last_sql.strip())
        .replace("__QUESTION__", question.strip())
        .replace("__PRIOR_REPLY__", clip_text(failed_llm_output, 4_000, "prior_reply"))
    )
    try:
        fixed = call_llm(_per_group_repair_system_text(), repair_user, role=LlmRole.REPAIR)
    except Exception as exc:  # noqa: BLE001
        logger.warning("per_group repair LLM failed: %s", exc)
        return narrative, None, None

    n2 = extract_narrative(fixed) or narrative
    s2 = extract_sql(fixed)
    p2 = extract_post_process_config(fixed)
    if not s2 or not p2:
        logger.info("per_group repair: second pass still produced no SQL or no POST_PROCESS")
        return narrative, None, None
    logger.info("per_group repair: recovered SQL + POST_PROCESS from second LLM pass")
    return n2, s2, p2


def attempt_missing_sql_repair(
    question: str,
    grounding: SchemaGrounding,
    narrative: str,
    failed_llm_output: str,
) -> tuple[str, Optional[str], Optional[list[dict]]]:
    repair_system = _MISSING_SQL_REPAIR_SYSTEM.format(
        schema=primary_schema_name(),
        max_rows=MAX_RESULT_ROWS,
    )
    compact_schema = clip_text(grounding.to_prompt_text(), 3_800, "schema")
    repair_user = (
        f"## Grounded schema\n{compact_schema}\n\n"
        f"## User question\n{question.strip()}\n\n"
        f"## Prior reply (broken — no SQL was parsed; may have wrongly refused)\n"
        f"{clip_text(failed_llm_output, 1_200, 'prior')}\n\n"
        "The prior reply must be ignored if it claimed columns are missing but SEMANTIC GUIDANCE "
        "and the allowlist contain matching physical columns. Output NARRATIVE and SQL now."
    )
    try:
        fixed = call_llm(repair_system, repair_user, role=LlmRole.REPAIR)
    except Exception as exc:  # noqa: BLE001
        logger.warning("missing_sql repair LLM failed: %s", exc)
        return narrative, None, None

    n2 = extract_narrative(fixed)
    s2 = extract_sql(fixed)
    p2 = extract_post_process_config(fixed)
    if not s2:
        logger.warning(
            "missing_sql repair: still no SQL (response_len=%d preview=%r)",
            len(fixed),
            fixed[:300].replace("\n", " "),
        )
        return narrative, None, None
    logger.info("missing_sql repair: recovered SQL (%d chars)", len(s2))
    return (n2 or narrative), s2, p2

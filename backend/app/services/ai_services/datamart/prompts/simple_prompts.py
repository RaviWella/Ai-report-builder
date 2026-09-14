"""Prompts for the simplified datamart SQL chat flow."""
from __future__ import annotations

from dataclasses import dataclass

SIMPLE_SQL_SYSTEM = """You are a PostgreSQL analyst for MintHRM warehouse data.

Rules:
- Write one SELECT query that answers the user's question.
- Use only tables and columns from the provided context.
- Always schema-qualify tables exactly as shown (e.g. hr.mart_employee_current, hr_semantic.vw_attendance_summary).
- Do not use hr_snap unless that schema appears in the warehouse schema section.
- Add LIMIT 500 on the outer query when returning many rows.
- Prefer joins on employee_sk or employee_id when linking employee tables.
- Use clear table aliases (e.g. mec for mart_employee_current, bi for dim_bank). Never use alias `db`.
- Employee fields (emp_no, emp_fullname, employee_sk) come from mart_employee_current, not dim_bank.
- Bank account fields come from fct_salary_bank_instruction joined to dim_bank / dim_bank_branch.
- Shift names: JOIN hr.dim_shift ON dim_shift.source_shift_id::text = mart_employee_current.shift_id::text
  (never join shift_sk to shift_id).
- Pending leave approvals: prefer hr_semantic.vw_pending_leave_approvals when available.
  Approver name/number: join hr.mart_employee_current ON mec.emp_no::text = source_approver_emp_id::text
  (never join employee_sk to source_approved_by or source_approver_emp_id).
  That view is already filtered to pending rows — do not add approval_status = 'Pending'.
- WHERE clause values: use ONLY literals from "Sample column values" when present (exact case/spelling).
  If no sample is shown, prefer ILIKE '%keyword%' for status/type columns instead of guessing 'Pending' vs 'pending'.
  Never invent categorical codes; omit a filter rather than guess a wrong literal.
- When retrying after a failed query, keep the user's original intent; fix only the failing joins/columns.
- Output format:

NARRATIVE:
One or two sentences explaining the result.

SQL:
```sql
SELECT ...
```
"""


def build_simple_user_prompt(
    *,
    question: str,
    history_text: str,
    mappings_text: str,
    datahub_text: str,
    schema_text: str,
    mode_instructions: str = "",
    follow_up_note: str = "",
) -> str:
    parts = [
        f"User question:\n{question.strip()}",
    ]
    if mode_instructions.strip():
        parts.append(f"\n## Mode\n{mode_instructions.strip()}")
    parts.append(f"\n## Conversation context\n{history_text.strip() or '(none)'}")
    parts.append(f"\n## Top catalog mappings (semantic YAML)\n{mappings_text}")
    parts.append(f"\n## DataHub metadata\n{datahub_text}")
    parts.append(f"\n## Warehouse schema (live introspection)\n{schema_text}")
    if follow_up_note.strip():
        parts.append(f"\n## Follow-up note\n{follow_up_note.strip()}")
    parts.append("\nWrite NARRATIVE and SQL as specified.")
    return "\n".join(parts)


    return "\n".join(parts)


@dataclass(frozen=True)
class SqlAttemptRecord:
    attempt: int
    failed_sql: str
    error: str
    issue_kind: str
    user_hint: str
    llm_guidance: str
    action_taken: str
    tables_added: tuple[str, ...] = ()


def _format_attempt_history(records: list[SqlAttemptRecord]) -> str:
    if not records:
        return ""
    lines = [
        "Earlier attempts failed. Keep the original question intent; fix only what broke.",
        f"You are on retry {len(records) + 1} of up to 4 attempts.",
        "",
    ]
    for rec in records:
        lines.append(f"### Attempt {rec.attempt} ({rec.issue_kind})")
        if rec.action_taken:
            lines.append(f"Recovery action: {rec.action_taken}")
        if rec.tables_added:
            lines.append(f"Tables added to context: {', '.join(rec.tables_added)}")
        lines.append(f"Hint: {rec.user_hint}")
        if rec.llm_guidance:
            lines.append(f"Guidance: {rec.llm_guidance}")
        if rec.failed_sql.strip():
            lines.append("```sql\n" + rec.failed_sql.strip()[:4000] + "\n```")
        lines.append(f"Error: {rec.error.strip()[:800]}")
        lines.append("")
    return "\n".join(lines)


def build_simple_retry_prompt(
    *,
    question: str,
    failed_sql: str,
    error_message: str,
    mappings_text: str,
    datahub_text: str,
    schema_text: str,
    mode_instructions: str = "",
    history_text: str = "",
    attempt: int = 2,
    max_attempts: int = 4,
    prior_attempts: list[SqlAttemptRecord] | None = None,
    llm_guidance: str = "",
    tables_added_this_retry: list[str] | None = None,
) -> str:
    parts = [
        f"User question:\n{question.strip()}",
    ]
    if mode_instructions.strip():
        parts.append(f"\n## Mode\n{mode_instructions.strip()}")
    if history_text.strip():
        parts.append(f"\n## Conversation context\n{history_text.strip()}")

    history_block = _format_attempt_history(prior_attempts or [])
    if history_block.strip():
        parts.append(f"\n## Prior failed attempts\n{history_block}")

    parts.append(
        f"\n## Current retry (attempt {attempt}/{max_attempts})"
    )
    if llm_guidance.strip():
        parts.append(f"Focus: {llm_guidance.strip()}")
    if tables_added_this_retry:
        parts.append(
            "New schema loaded for this retry (merged with earlier context): "
            + ", ".join(tables_added_this_retry)
        )

    if failed_sql.strip():
        parts.extend(
            [
                "\n## Previous SQL (failed)\n```sql\n" + failed_sql.strip() + "\n```",
                f"\n## Latest warehouse error\n{error_message.strip()}",
            ]
        )
    elif error_message.strip():
        parts.append(f"\n## Latest error\n{error_message.strip()}")

    parts.extend(
        [
            "\n## Retry instructions",
            "- Keep the same report intent and columns the user asked for.",
            "- Fix ONLY the joins/columns/tables that caused the error above.",
            "- Use columns from BOTH the original schema block and any newly added tables below.",
            "- Do not repeat the same wrong join keys from prior attempts.",
            f"\n## Top catalog mappings\n{mappings_text}",
            f"\n## DataHub metadata\n{datahub_text}",
            f"\n## Warehouse schema (cumulative introspection)\n{schema_text}",
            "\nWrite NARRATIVE and a corrected SQL block.",
        ]
    )
    return "\n".join(parts)

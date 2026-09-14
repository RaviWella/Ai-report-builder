"""User-facing messages when datamart cannot run SQL (no internal schema jargon)."""
from __future__ import annotations

import re
from typing import Optional

from ..validation.validation_models import RetrievalValidation


def _is_recruitment_question(q: str) -> bool:
    return bool(
        re.search(
            r"\b(?:recruitment|recruit|hiring|candidate|candidates|pipeline|"
            r"linkedin|referral|requisition|applicant)\b",
            q,
            re.I,
        )
    )


def _is_employee_roster_question(q: str) -> bool:
    if _is_recruitment_question(q):
        return False
    return bool(
        re.search(r"\b(?:employee|employees|staff|workforce)\b", q, re.I)
    )


def build_retrieval_clarification_message(
    *,
    question: str,
    retrieval: RetrievalValidation,
) -> str:
    """Friendly message when schema context is thin (rare with catalog-first grounding)."""
    if retrieval.message:
        lead = retrieval.message.strip()
    else:
        lead = "I need a bit more context to run this report safely."

    hints = [h.strip() for h in (retrieval.clarification_hints or []) if h and h.strip()]
    if hints:
        lines = [lead, "", "Please confirm:"]
        for h in hints[:3]:
            lines.append(f"- {h if h.endswith('?') else h + '?'}")
        return "\n".join(lines)

    q = (question or "").lower()
    if _is_recruitment_question(q):
        return (
            f"{lead}\n\n"
            "For recruitment reports, specify the joining window (e.g. next 60 days), "
            "sources to include (LinkedIn, referrals), and whether you need branch or "
            "department filters."
        )
    if _is_employee_roster_question(q):
        return (
            f"{lead}\n\n"
            "For employee lists, specify which fields you need (name, number, department, "
            "shift, bank, etc.) and whether you want current employees only."
        )
    return (
        f"{lead}\n\n"
        "Add a time period and whether you need a detailed list or a summary."
    )


def build_mixed_domain_clarification_message(*, question: str) -> str:
    """When payroll + recruitment (etc.) keywords tie, ask user to pick scope."""
    q = (question or "").lower()
    parts: list[str] = [
        "Your question touches more than one HR area (for example payroll and recruitment).",
        "",
        "Which report do you want?",
    ]
    if re.search(r"\b(?:recruitment|candidate|linkedin|referral|hiring)\b", q, re.I):
        parts.append("- Recruitment pipeline / candidates")
    if re.search(r"\b(?:payroll|payslip|salary|gross|net)\b", q, re.I):
        parts.append("- Payroll / compensation")
    if re.search(r"\bleave\b", q, re.I):
        parts.append("- Leave balances or transactions")
    if re.search(r"\battendance\b", q, re.I):
        parts.append("- Attendance summary")
    if re.search(r"\b(?:employee|workforce|staff)\b", q, re.I):
        parts.append("- Employee roster / workforce list")
    parts.extend(
        [
            "",
            "Reply with the area you need (and any date range or filters). "
            "I will run the matching governed report.",
        ]
    )
    return "\n".join(parts)


def build_generation_clarification_message(
    *,
    question: str,
    failure_summary: Optional[str] = None,
) -> str:
    """Final assistant summary when SQL could not be produced (shown as normal message text)."""
    q = question or ""
    q_lower = q.lower()

    if failure_summary == "missing_sql":
        if _is_recruitment_question(q_lower):
            return (
                "I could not generate SQL for this recruitment pipeline report. "
                "The warehouse may not expose recruitment tables (candidates and pipeline facts) "
                "for your tenant, or the requested columns are not available yet. "
                "Try a shorter list (candidate name, source, expected joining date) or ask "
                "your admin to sync recruitment tables into the analytics catalog."
            )
        if _is_employee_roster_question(q_lower):
            return (
                "I could not generate SQL for this employee report. "
                "Try asking for a specific list (employee number, name, department, shift, bank) "
                "for current employees. If this worked before, restart the backend and use a new chat session."
            )
        return (
            "I could not produce runnable SQL for that question. "
            "Try naming the columns you need and a time period, or start a new session."
        )

    if failure_summary in ("binding_or_validation", "warehouse_execution_failed"):
        if _is_recruitment_question(q_lower):
            return (
                "The query could not be validated against available recruitment data. "
                "Check that candidate and pipeline tables exist in the warehouse, then retry "
                "with fewer columns."
            )
        return (
            "The query did not match the tables available for this topic. "
            "Rephrase with the exact fields you need or narrow the question."
        )

    if _is_recruitment_question(q_lower):
        return (
            "I could not complete this recruitment report. "
            "Confirm joining-date window and sources (LinkedIn, referrals), then retry."
        )

    return (
        "I could not run this report. "
        "State the columns and filters you need (time period, branch, current employees only)."
    )

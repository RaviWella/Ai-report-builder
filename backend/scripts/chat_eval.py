"""Chat resolver eval harness — runs a corpus of realistic HR prompts through the
deterministic chat path (intent gate + hybrid resolver + guard validation) and
reports, per prompt, how it routes: a deterministic report (no LLM), a
conversational reply (greeting/help), or a fall-through that would need the LLM.

Run in the Py3.13 container against a tenant's live catalogue:
    docker exec <backend> python scripts/chat_eval.py [tenant_id]

Gives a coverage % (how much resolves with zero LLM) and a per-prompt table —
so you don't have to type each prompt into the UI by hand. This is the seed of
the NL→spec eval harness (roadmap #1): freeze expected specs here for CI.
"""

from __future__ import annotations

import sys

from app.db.pg_tenant_session import init_postgres_tenant_session_manager, worker_pg_session
from app.db.postgres import init_postgres_database
from app.services.ai_service import AIService, _is_refinement
from app.services.chat_intent import classify_message
from app.services.nl_hybrid import hybrid_resolve, refine_spec
from app.query_engine import guards

# Refinements are applied to an existing report; this is the base for eval.
BASE_SPEC = {
    "entity": "employee",
    "fields": [{"ref": "employee.full_name"}, {"ref": "employee.department"}],
    "filters": [], "group_by": [], "aggregations": [],
    "calculated_fields": [], "sort": [], "runtime_params": [],
}

# (category, prompt). Mirrors how end users actually phrase HR report requests.
CORPUS: list[tuple[str, str]] = [
    ("greeting", "Hi"),
    ("greeting", "good morning"),
    ("help", "what can you do"),
    ("off-topic", "asdf qwer blorp"),

    ("field-list", "Show employee name, department and designation"),
    ("field-list", "employee name, gender, age, grade, location"),
    ("field-list", "employee name, department, designation, gender, age, grade, location"),
    ("field-list", "full name, NIC, EPF no, join date"),
    ("field-list", "employee name and current basic salary"),

    ("filter-status", "active employees: full name, department, basic salary"),
    ("filter-status", "resigned employees with name and designation"),
    ("filter-tenure", "employee name and tenure where tenure is more than 5 years"),
    ("filter-tenure", "full name, at least 3 years tenure"),

    ("rollup", "headcount by department"),
    ("rollup", "total basic salary by department"),
    ("rollup", "average basic salary by grade"),
    ("rollup", "count of employees by employment type"),
    ("rollup", "headcount by location"),

    ("payroll", "employee name, branch, payroll group, net salary"),
    ("payroll", "total net pay by payroll group"),
    ("payroll", "basic salary, gross salary, deductions by payroll group"),

    ("leave", "leave balance by leave type"),
    ("leave", "employee name, days taken, leave balance"),

    ("attendance", "present days and overtime hours by department"),

    ("unmatched", "employee name, department, compa-ratio"),
    ("unmatched", "employee name, branch, business unit, compa-ratio"),

    ("prose", "give me a list of all employees and their departments"),
    ("prose", "I want to see staff salaries grouped by branch"),
    ("prose", "Provide a list of active employees, including employee name, department, branch"),
    ("synonym", "take home pay by department"),

    ("count", "how many active employees"),
    ("count", "active user count"),
    ("count", "number of resigned employees"),

    ("time", "total net pay by payroll group this month"),
    ("time", "total net pay by payroll group year to date"),
    ("time", "employees who joined in the last 12 months"),
    ("time", "headcount by department this year"),

    ("refinement", "only active"),
    ("refinement", "add designation"),
    ("refinement", "also show grade and location"),
    ("refinement", "remove department"),
    ("refinement", "only employees with more than 2 years tenure"),
    ("refinement", "group by grade"),
]


def evaluate(tenant_id: str) -> None:
    init_postgres_database()
    init_postgres_tenant_session_manager()
    with worker_pg_session(tenant_id) as db:
        svc = AIService(db)
        catalog = svc.semantic.get_active_catalog(tenant_id)

        det = reply = llm = 0
        rows: list[tuple[str, str, str, str]] = []
        for cat, prompt in CORPUS:
            kind = classify_message(prompt)
            if kind in ("smalltalk", "help"):
                reply += 1
                rows.append((cat, prompt, "REPLY (gate)", ""))
                continue
            if _is_refinement(prompt):
                res = refine_spec(BASE_SPEC, prompt, catalog)
                if res is None:
                    llm += 1
                    rows.append((cat, prompt, "→ LLM (refinement)", ""))
                    continue
                try:
                    guards.validate_refs(res.data_spec, catalog)
                    guards.validate_joins(res.data_spec, catalog)
                except guards.GuardError:
                    llm += 1
                    rows.append((cat, prompt, "→ LLM (invalid)", ""))
                    continue
                det += 1
                rows.append((cat, prompt, "DETERMINISTIC (refine)", res.rationale[:58]))
                continue
            res = hybrid_resolve(prompt, catalog)
            if res is None or res.confidence < AIService._HYBRID_MIN:
                llm += 1
                rows.append((cat, prompt, "→ LLM (low/none)", ""))
                continue
            try:
                guards.validate_refs(res.data_spec, catalog)
                guards.validate_joins(res.data_spec, catalog)
            except guards.GuardError:
                llm += 1
                rows.append((cat, prompt, "→ LLM (invalid)", ""))
                continue
            det += 1
            detail = ", ".join(m.label for m in res.matched)
            if res.filters:
                detail += "  | filters: " + "; ".join(res.filters)
            if res.unmatched:
                detail += "  | ✕ " + ", ".join(res.unmatched)
            rows.append((cat, prompt, f"DETERMINISTIC ({res.confidence})", detail))

        print(f"\n{'CAT':<13} {'PROMPT':<58} {'ROUTE':<26} DETAIL")
        print("-" * 130)
        for cat, prompt, route, detail in rows:
            print(f"{cat:<13} {prompt[:56]:<58} {route:<26} {detail[:60]}")

        total = len(CORPUS)
        print("-" * 130)
        print(
            f"\nTOTAL {total} | deterministic (no LLM): {det} ({det*100//total}%) | "
            f"reply-gate: {reply} | needs-LLM: {llm}"
        )
        print(
            "Report-intent prompts only:",
            f"{det}/{det+llm} resolved deterministically "
            f"({det*100//max(1, det+llm)}%)",
        )


if __name__ == "__main__":
    evaluate(sys.argv[1] if len(sys.argv) > 1 else "demo_tenant")

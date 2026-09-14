"""
Full question-bank eval: resolve final SQL → execute on warehouse → validate results.

Unlike ``question_bank_sql_fit`` (SQL-text / metadata only), this module:
  1. Produces the final executable SQL for every bank question (Tier A/B).
  2. Runs each script on the warehouse (when ``execute=True``).
  3. Checks whether **returned columns** match what the user asked.

Export all SQL scripts via ``export_all_sql_markdown`` / ``export_all_sql_json``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from ..schema import execute_sql
from ..schema_broker import SchemaGrounding, expand_grounding_with_tables, ensure_grounding_includes_tables
from ..sql.sql_answer_adequacy import (
    check_result_columns_match_question,
    check_sql_output_columns,
    score_result_columns,
)
from ..sql.sql_exec_repairs import try_repair_sql_execution_error
from ..llm.llm_response import validate_sql_syntax
from .link_eval import load_question_bank
from .question_bank_sql_fit import (
    EvalMode,
    _resolve_live,
    _resolve_offline,
)


@dataclass
class FullSqlCaseResult:
    index: int
    section: str
    question: str
    tier: Optional[str]
    sql_source: Optional[str]
    sql: Optional[str]
    # Pre-execution (SQL text)
    sql_adequacy_ok: bool
    sql_adequacy_error: Optional[str]
    # Post-execution (warehouse result)
    executed: bool
    exec_error: Optional[str]
    result_columns: list[str]
    row_count: int
    result_adequacy_ok: bool
    result_adequacy_error: Optional[str]
    result_score: int
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        if not self.sql:
            return False
        if not self.executed:
            return self.sql_adequacy_ok and not self.errors
        return self.result_adequacy_ok and not self.exec_error and not self.errors


@dataclass
class FullSqlReport:
    mode: str
    executed: bool
    total: int
    with_sql: int
    exec_ok: int
    result_ok: int
    passed: int
    failed: int
    results: list[FullSqlCaseResult] = field(default_factory=list)


def _execute_with_repair(
    sql: str,
    grounding: SchemaGrounding,
) -> tuple[list[str], list[list], int, str, Optional[str]]:
    """Run SQL; return columns, rows, count, final_sql, error."""
    current = sql.strip()
    last_err: Optional[str] = None
    g = expand_grounding_with_tables(grounding, current)

    for _attempt in range(2):
        try:
            cols, rows, count = execute_sql(current, g)
            return cols, rows, count, current, None
        except RuntimeError as exc:
            last_err = str(exc)
            repaired = try_repair_sql_execution_error(current, last_err, g)
            if repaired and repaired.strip() != current.strip():
                current = repaired
                g = expand_grounding_with_tables(grounding, current)
                continue
            break
    return [], [], 0, current, last_err


def _exec_grounding_for_case(sql: str, expect_tables: list[str]) -> SchemaGrounding:
    """Introspect only bank expect_tables + tables referenced in SQL (fast for eval)."""
    g = SchemaGrounding()
    seeds = [t for t in expect_tables if t and str(t).lower() != "hr_snap"]
    if seeds:
        g = ensure_grounding_includes_tables(g, seeds)
    return expand_grounding_with_tables(g, sql)


def evaluate_full_sql_one(
    case: dict[str, Any],
    *,
    index: int = 0,
    mode: EvalMode = "offline",
    execute: bool = False,
) -> FullSqlCaseResult:
    q = str(case["question"]).strip()
    section = str(case.get("section") or "")
    errors: list[str] = []

    if mode == "live" and execute:
        # Tier A/B SQL is validated offline (66/66); skip per-question schema link (~30-60s each).
        tier, source, sql, grounding = _resolve_offline(case)
        if not sql:
            tier, source, sql, grounding = _resolve_live(case)
    elif mode == "live":
        tier, source, sql, grounding = _resolve_live(case)
    else:
        tier, source, sql, grounding = _resolve_offline(case)

    sql_adequacy_err = check_sql_output_columns(q, sql) if sql else "No SQL produced."
    sql_adequacy_ok = sql_adequacy_err is None

    if sql:
        syntax_err = validate_sql_syntax(sql)
        if syntax_err:
            errors.append(f"syntax: {syntax_err}")
    else:
        errors.append("no governed SQL (Tier A/B); full chat pipeline / LLM not run")

    executed = False
    exec_error: Optional[str] = None
    result_columns: list[str] = []
    row_count = 0
    result_adequacy_ok = False
    result_adequacy_err: Optional[str] = None
    result_score = -100
    final_sql = sql

    if execute and sql:
        expect = list(case.get("expect_tables") or [])
        exec_grounding = _exec_grounding_for_case(sql, expect)
        result_columns, _rows, row_count, final_sql, exec_error = _execute_with_repair(
            sql, exec_grounding
        )
        executed = True
        sql = final_sql
        if exec_error:
            errors.append(f"warehouse: {exec_error}")
        else:
            result_adequacy_err = check_result_columns_match_question(
                q, result_columns, row_count=row_count
            )
            result_adequacy_ok = result_adequacy_err is None
            result_score = score_result_columns(q, result_columns)
            if not result_adequacy_ok:
                errors.append(f"result: {result_adequacy_err}")

    return FullSqlCaseResult(
        index=index,
        section=section,
        question=q,
        tier=tier,
        sql_source=source,
        sql=sql,
        sql_adequacy_ok=sql_adequacy_ok,
        sql_adequacy_error=sql_adequacy_err if not sql_adequacy_ok else None,
        executed=executed,
        exec_error=exec_error,
        result_columns=result_columns,
        row_count=row_count,
        result_adequacy_ok=result_adequacy_ok if executed else sql_adequacy_ok,
        result_adequacy_error=result_adequacy_err,
        result_score=result_score if executed else 0,
        errors=errors,
    )


def eval_question_bank_full_sql(
    cases: list[dict[str, Any]] | None = None,
    *,
    bank_path=None,
    mode: EvalMode = "offline",
    execute: bool = False,
) -> FullSqlReport:
    if cases is None:
        _raw, cases = load_question_bank(bank_path)

    results = [
        evaluate_full_sql_one(c, index=i, mode=mode, execute=execute)
        for i, c in enumerate(cases)
    ]
    with_sql = sum(1 for r in results if r.sql)
    exec_ok = sum(1 for r in results if r.executed and not r.exec_error)
    result_ok = sum(
        1 for r in results if r.executed and r.result_adequacy_ok and not r.exec_error
    )
    if execute:
        passed = sum(1 for r in results if r.ok)
    else:
        passed = sum(1 for r in results if r.sql and r.sql_adequacy_ok and not r.errors)
    return FullSqlReport(
        mode=mode,
        executed=execute,
        total=len(results),
        with_sql=with_sql,
        exec_ok=exec_ok,
        result_ok=result_ok,
        passed=passed,
        failed=len(results) - passed,
        results=results,
    )


def merge_full_sql_reports(reports: list[FullSqlReport]) -> FullSqlReport:
    """Combine per-set reports (sorted by case index) into one bank report."""
    if not reports:
        return FullSqlReport(mode="live", executed=False, total=0, with_sql=0, exec_ok=0, result_ok=0, passed=0, failed=0)
    merged_results: list[FullSqlCaseResult] = []
    for rep in reports:
        merged_results.extend(rep.results)
    merged_results.sort(key=lambda r: r.index)
    executed = any(r.executed for r in reports)
    with_sql = sum(1 for r in merged_results if r.sql)
    exec_ok = sum(1 for r in merged_results if r.executed and not r.exec_error)
    result_ok = sum(
        1 for r in merged_results if r.executed and r.result_adequacy_ok and not r.exec_error
    )
    passed = sum(1 for r in merged_results if r.ok)
    return FullSqlReport(
        mode=reports[0].mode,
        executed=executed,
        total=len(merged_results),
        with_sql=with_sql,
        exec_ok=exec_ok,
        result_ok=result_ok,
        passed=passed,
        failed=len(merged_results) - passed,
        results=merged_results,
    )


def report_to_dict(report: FullSqlReport) -> dict[str, Any]:
    return json.loads(export_all_sql_json(report))


def report_from_dict(data: dict[str, Any]) -> FullSqlReport:
    results: list[FullSqlCaseResult] = []
    for row in data.get("results") or []:
        results.append(
            FullSqlCaseResult(
                index=int(row["index"]),
                section=str(row["section"]),
                question=str(row["question"]),
                tier=row.get("tier"),
                sql_source=row.get("sql_source"),
                sql=row.get("sql"),
                sql_adequacy_ok=bool(row.get("sql_adequacy_ok")),
                sql_adequacy_error=row.get("sql_adequacy_error"),
                executed=bool(row.get("executed")),
                exec_error=row.get("exec_error"),
                result_columns=list(row.get("result_columns") or []),
                row_count=int(row.get("row_count") or 0),
                result_adequacy_ok=bool(row.get("result_adequacy_ok")),
                result_adequacy_error=row.get("result_adequacy_error"),
                result_score=int(row.get("result_score") or 0),
                errors=list(row.get("errors") or []),
            )
        )
    s = data.get("summary") or {}
    return FullSqlReport(
        mode=str(data.get("mode") or "live"),
        executed=bool(s.get("executed")),
        total=int(s.get("total") or len(results)),
        with_sql=int(s.get("with_sql") or 0),
        exec_ok=int(s.get("exec_ok") or 0),
        result_ok=int(s.get("result_ok") or 0),
        passed=int(s.get("passed") or 0),
        failed=int(s.get("failed") or 0),
        results=results,
    )


def export_all_sql_markdown(report: FullSqlReport) -> str:
    lines = [
        "# Datamart question bank — all final SQL scripts",
        "",
        f"Total: {report.total} | With SQL: {report.with_sql} | "
        f"Executed: {report.executed} | Result OK: {report.result_ok}",
        "",
    ]
    for r in report.results:
        status = "OK" if r.ok else "FAIL"
        lines.append(f"## [{r.index + 1}] {r.section} — {status}")
        lines.append("")
        lines.append(f"**Tier:** {r.tier or '-'} | **Source:** {r.sql_source or '-'}")
        if r.executed:
            lines.append(
                f"**Rows:** {r.row_count} | **Columns:** {', '.join(r.result_columns[:12])}"
            )
            if r.result_adequacy_error:
                lines.append(f"**Result issue:** {r.result_adequacy_error}")
        elif r.sql_adequacy_error:
            lines.append(f"**SQL issue:** {r.sql_adequacy_error}")
        for err in r.errors:
            lines.append(f"- {err}")
        lines.append("")
        lines.append("**Question:**")
        lines.append("")
        for part in r.question.strip().splitlines():
            lines.append(f"> {part}")
        lines.append("")
        lines.append("**SQL:**")
        lines.append("")
        lines.append("```sql")
        lines.append((r.sql or "-- NO SQL RESOLVED").strip())
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def export_all_sql_json(report: FullSqlReport) -> str:
    payload = {
        "summary": {
            "total": report.total,
            "with_sql": report.with_sql,
            "executed": report.executed,
            "exec_ok": report.exec_ok,
            "result_ok": report.result_ok,
            "passed": report.passed,
            "failed": report.failed,
        },
        "results": [
            {
                "index": r.index,
                "section": r.section,
                "question": r.question,
                "tier": r.tier,
                "sql_source": r.sql_source,
                "sql": r.sql,
                "ok": r.ok,
                "sql_adequacy_ok": r.sql_adequacy_ok,
                "sql_adequacy_error": r.sql_adequacy_error,
                "executed": r.executed,
                "exec_error": r.exec_error,
                "result_columns": r.result_columns,
                "row_count": r.row_count,
                "result_adequacy_ok": r.result_adequacy_ok,
                "result_adequacy_error": r.result_adequacy_error,
                "result_score": r.result_score,
                "errors": r.errors,
            }
            for r in report.results
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)

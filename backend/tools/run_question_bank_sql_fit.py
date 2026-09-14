"""
Run every question in datamart_question_bank.yaml through SQL resolve + relevance checks.

For each question this reports:
  - Final executable SQL (Tier A/B governed templates + verified queries)
  - Syntax validity
  - Output-column adequacy (does SELECT match what the user asked for?)
  - Table overlap (does SQL use expect_tables from the bank?)
  - Faithfulness warnings (LIMIT, ORDER BY, join keys, etc.)

Usage (from backend/):
  PYTHONPATH=. python tools/run_question_bank_sql_fit.py
  PYTHONPATH=. python tools/run_question_bank_sql_fit.py --live
  PYTHONPATH=. python tools/run_question_bank_sql_fit.py --json tools/question_bank_sql_fit.json
  PYTHONPATH=. python tools/run_question_bank_sql_fit.py --section advanced_workforce
  PYTHONPATH=. python tools/run_question_bank_sql_fit.py --show-sql --failures-only

Offline (default): mock grounding, no LLM, no warehouse — fast CI.
Live (--live): real schema link + warehouse introspection — still Tier A/B only.

Note: Tier C (LLM) is intentionally skipped here for speed/repeatability.
      Use the datamart chat UI or a separate LLM eval harness for Tier C cases.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.services.ai_services.datamart.pipeline.link_eval import load_question_bank
from app.services.ai_services.datamart.pipeline.question_bank_sql_fit import (
    eval_question_bank_sql_fit,
)
from app.services.ai_services.datamart.workspace.runtime_context import run_with_datamart_context

BANK_PATH = Path(__file__).parent / "datamart_question_bank.yaml"
MIN_SQL_FIT_PASS_RATE = 0.85


def _result_to_dict(r) -> dict:
    return {
        "section": r.section,
        "question_preview": r.question_preview,
        "tier": r.tier,
        "sql_source": r.sql_source,
        "sql": r.sql,
        "fit_ok": r.fit_ok,
        "syntax_ok": r.syntax_ok,
        "adequacy_ok": r.adequacy_ok,
        "adequacy_score": r.adequacy_score,
        "adequacy_error": r.adequacy_error,
        "tables_in_sql": r.tables_in_sql,
        "expect_tables_hit": r.expect_tables_hit,
        "expect_tables_missing": r.expect_tables_missing,
        "tables_overlap_ok": r.tables_overlap_ok,
        "tables_overlap_note": r.tables_overlap_note,
        "faithfulness_warnings": r.faithfulness_warnings,
        "errors": r.errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Question bank SQL fit eval (resolve + relevance)",
    )
    parser.add_argument(
        "--bank",
        type=Path,
        default=BANK_PATH,
        help="Path to datamart_question_bank.yaml",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live warehouse schema link (slower; needs DB)",
    )
    parser.add_argument(
        "--tenant",
        default=os.getenv("DATAMART_TENANT_ID", "demo_tenant"),
        help="Tenant for --live mode",
    )
    parser.add_argument("--json", type=Path, help="Write full report JSON")
    parser.add_argument(
        "--section",
        action="append",
        dest="sections",
        help="Run only bank section(s), e.g. advanced_workforce",
    )
    parser.add_argument(
        "--show-sql",
        action="store_true",
        help="Print SQL for each question",
    )
    parser.add_argument(
        "--failures-only",
        action="store_true",
        help="Only print failed cases",
    )
    args = parser.parse_args(
        argv if argv is not None else (sys.argv[1:] if __name__ == "__main__" else [])
    )

    _raw, cases = load_question_bank(args.bank)
    meta = _raw.get("meta") or {}
    if args.sections:
        allow = {s.lower() for s in args.sections}
        cases = [c for c in cases if str(c.get("section", "")).lower() in allow]

    mode = "live" if args.live else "offline"

    def _run():
        return eval_question_bank_sql_fit(cases, mode=mode)

    if args.live:
        report = run_with_datamart_context(args.tenant, _run)
    else:
        report = _run()

    print(
        f"Question bank SQL fit ({mode}, tenant={meta.get('tenant', '?')})",
        flush=True,
    )
    print(
        f"  Resolved SQL: {report.with_sql}/{report.total} "
        f"(Tier A={report.tier_a}, B={report.tier_b}, unresolved={report.unresolved})",
        flush=True,
    )
    print(
        f"  Fit passed:   {report.passed}/{report.total} "
        f"(SQL + syntax + column adequacy vs question)",
        flush=True,
    )
    overlap_pass = sum(1 for r in report.results if r.full_ok)
    print(
        f"  Full match:   {overlap_pass}/{report.total} "
        f"(fit + expect_tables overlap)",
        flush=True,
    )

    for r in report.results:
        if args.failures_only and r.fit_ok:
            continue
        status = "OK" if r.fit_ok else "FAIL"
        print(
            f"\n  [{status}] {r.section} tier={r.tier or '-'} "
            f"score={r.adequacy_score} source={r.sql_source or '-'}",
            flush=True,
        )
        print(f"    Q: {r.question_preview}", flush=True)
        if r.errors:
            for err in r.errors:
                print(f"    ! {err}", flush=True)
        if r.faithfulness_warnings:
            for w in r.faithfulness_warnings[:3]:
                print(f"    ~ {w}", flush=True)
        if r.tables_overlap_note:
            print(f"    tables: {r.tables_overlap_note}", flush=True)
        if args.show_sql and r.sql:
            print("    SQL:", flush=True)
            for line in r.sql.strip().splitlines()[:12]:
                print(f"      {line}", flush=True)
            if r.sql.count("\n") > 12:
                print("      ...", flush=True)

    if args.json:
        payload = {
            "meta": meta,
            "mode": mode,
            "summary": {
                "total": report.total,
                "passed": report.passed,
                "failed": report.failed,
                "with_sql": report.with_sql,
                "tier_a": report.tier_a,
                "tier_b": report.tier_b,
                "unresolved": report.unresolved,
                "full_match": sum(1 for r in report.results if r.full_ok),
            },
            "results": [_result_to_dict(r) for r in report.results],
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nWrote {args.json}", flush=True)

    rate = report.passed / report.total if report.total else 0
    if report.unresolved:
        return 1
    if rate < MIN_SQL_FIT_PASS_RATE:
        print(
            f"\nFAIL: fit pass rate {rate:.1%} below {MIN_SQL_FIT_PASS_RATE:.0%}",
            flush=True,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

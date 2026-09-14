"""
Run questions from datamart_question_bank.yaml against live broker + catalog SQL.

Usage (from backend/):
  PYTHONPATH=. python tools/run_question_bank_eval.py
  PYTHONPATH=. python tools/run_question_bank_eval.py --set 1
  PYTHONPATH=. python tools/run_question_bank_eval.py --set 1 --json tools/question_bank_reports/set_1.json

  # All 10 sets (6 questions each), parallel (default):
  PYTHONPATH=. python tools/run_question_bank_eval.py --all-sets --parallel

  # Sequential (legacy):
  PYTHONPATH=. python tools/run_question_bank_eval.py --all-sets --sequential

  # PowerShell wrapper:
  ..\\scripts\\run_question_bank_sets.ps1

Checks per question:
  - At least one expect_tables entry appears in broker grounding
  - If template is set: catalog router returns SQL + spec validation
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.services.ai_services.datamart.orchestration.intent_router import ChatIntent, classify_chat_intent
from app.services.ai_services.datamart.domain_sql.report_spec import ReportDomain, compile_report_spec
from app.services.ai_services.datamart.validation.report_spec_validate import validate_sql_against_report_spec
from app.services.ai_services.datamart.domain_sql.report_sql_router import try_build_sql_from_report_spec
from app.services.ai_services.datamart.workspace.runtime_context import run_with_datamart_context
from app.services.ai_services.datamart.pipeline.question_bank_report import (
    pipeline_fields_for_question,
)
from app.services.ai_services.datamart.schema_broker import (
    BrokerMode,
    build_schema_grounding,
    ensure_grounding_includes_tables,
)

BANK_PATH = Path(__file__).parent / "datamart_question_bank.yaml"
DEFAULT_REPORTS_DIR = Path(__file__).parent / "question_bank_reports"


def _load_bank_raw(path: Path = BANK_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _bank_dimensions(raw: dict[str, Any]) -> tuple[int, int]:
    meta = raw.get("meta") or {}
    set_count = int(meta.get("set_count", 10))
    set_size = int(meta.get("set_size", 6))
    return set_count, set_size


def _load_bank(path: Path = BANK_PATH) -> tuple[list[dict[str, Any]], int, int]:
    raw = _load_bank_raw(path)
    set_count, set_size = _bank_dimensions(raw)
    items: list[dict[str, Any]] = []
    for section, entries in raw.items():
        if section == "meta" or not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and entry.get("question"):
                items.append({**entry, "section": section})
    return items, set_count, set_size


def split_into_sets(
    cases: list[dict[str, Any]],
    *,
    set_size: int,
    set_count: int,
) -> list[list[dict[str, Any]]]:
    """Split flat question list into fixed-size sets (last set may be shorter)."""
    sets: list[list[dict[str, Any]]] = []
    for i in range(set_count):
        start = i * set_size
        chunk = cases[start : start + set_size]
        if chunk:
            sets.append(chunk)
    return sets


def _tables_ok(
    shorts: list[str],
    expect: list[str],
    *,
    require_all: bool,
) -> tuple[bool, list[str]]:
    missing = []
    for e in expect:
        if not any(e.lower() in t.lower() for t in shorts):
            missing.append(e)
    if require_all:
        return (not missing, missing)
    if not expect:
        return (bool(shorts), [])
    any_hit = any(
        any(e.lower() in t.lower() for t in shorts) for e in expect
    )
    return (any_hit, missing)


def _eval_one(case: dict[str, Any], *, index: int) -> dict[str, Any]:
    q = case["question"].strip()
    expect = case.get("expect_tables") or []
    template = case.get("template")
    errors: list[str] = []

    intent = classify_chat_intent(q, last_sql=None, has_prior_post_process=False)
    spec = compile_report_spec(q, chat_intent=intent or ChatIntent.NEW_QUERY)
    grounding = build_schema_grounding(
        question=q,
        mode=BrokerMode.CHAT,
        last_sql=None,
        chat_intent=intent,
    )
    if spec.required_tables:
        grounding = ensure_grounding_includes_tables(grounding, spec.required_tables)
    if spec.domain == ReportDomain.PAYROLL:
        grounding = ensure_grounding_includes_tables(
            grounding,
            ["vw_payroll_summary", "dim_payroll_group", "mart_employee_current"],
        )
    if spec.domain == ReportDomain.LEAVE:
        grounding = ensure_grounding_includes_tables(
            grounding,
            ["fact_leave_balance", "mart_employee_current", "dim_employee"],
        )
    # Extra must-include for common sub-intents that the broker may miss in short prompts.
    q_l = q.lower()
    if spec.template_id == "top_paid.ranking":
        grounding = ensure_grounding_includes_tables(grounding, ["mart_employee_current"])
    if ("pay item" in q_l) or ("additions" in q_l) or ("deductions" in q_l):
        grounding = ensure_grounding_includes_tables(
            grounding,
            ["fct_processed_add_ded", "dim_canonical_pay_item"],
        )
    if ("performance" in q_l) or ("rating" in q_l) or ("review" in q_l):
        grounding = ensure_grounding_includes_tables(
            grounding,
            ["vw_performance_summary", "mart_employee_current"],
        )

    shorts = grounding.table_short_names
    require_all = bool(case.get("require_all_tables"))
    ok_tables, missing_tables = _tables_ok(shorts, expect, require_all=require_all)
    if not ok_tables:
        errors.append(
            "broker grounded none of expect_tables"
            if not require_all
            else f"broker missing expect_tables: {', '.join(missing_tables)}"
        )

    sql = None
    sql_source = None
    if template:
        if spec.template_id != template:
            errors.append(
                f"template_id {spec.template_id!r} != bank template {template!r}"
            )
        routed = try_build_sql_from_report_spec(q, spec, grounding=grounding)
        if not routed:
            errors.append("catalog SQL router returned None")
        else:
            sql, sql_source = routed
            spec_err = validate_sql_against_report_spec(q, sql, spec)
            if spec_err:
                errors.append(f"spec validate: {spec_err}")

    pipeline = pipeline_fields_for_question(
        case,
        sql_source=sql_source,
        report_spec_domain=spec.domain.value,
    )
    return {
        "index": index,
        "id": f"{case['section']}:{q[:48]}",
        "section": case["section"],
        "ok": not errors,
        "errors": errors,
        "template": template,
        "spec_template": spec.template_id,
        "domain": spec.domain.value,
        "tables": shorts[:12],
        "sql_source": sql_source,
        "has_sql": sql is not None,
        "missing_expect_tables": missing_tables if expect else [],
        **pipeline,
    }


def _eval_batch(cases: list[dict[str, Any]], *, base_index: int) -> list[dict[str, Any]]:
    """Evaluate all cases in one call (caller binds warehouse context once)."""
    results: list[dict[str, Any]] = []
    for i, case in enumerate(cases):
        t0 = time.perf_counter()
        r = _eval_one(case, index=base_index + i)
        r["elapsed_ms"] = round((time.perf_counter() - t0) * 1000)
        results.append(r)
        status = "ok" if r["ok"] else "FAIL"
        tier = r.get("sql_tier") or "-"
        dom = r.get("classified_domain") or "?"
        print(
            f"  [{i + 1}/{len(cases)}] {status} {r['section']} "
            f"domain={dom} tier={tier}: {case['question'][:48]}...",
            flush=True,
        )
    return results


def _run_set_chunk(
    tenant_id: str,
    set_number: int,
    chunk: list[dict[str, Any]],
    *,
    base_index: int,
    set_count: int,
    set_size: int,
    quiet: bool = False,
) -> dict[str, Any]:
    if not quiet:
        print(
            f"Set {set_number}/{set_count}: questions {base_index + 1}-"
            f"{base_index + len(chunk)} ({len(chunk)} items)",
            flush=True,
        )
    t0 = time.perf_counter()
    results = run_with_datamart_context(tenant_id, _eval_batch, chunk, base_index=base_index)
    elapsed_s = round(time.perf_counter() - t0, 1)
    passed = sum(1 for r in results if r["ok"])
    return {
        "tenant": tenant_id,
        "set": set_number,
        "set_count": set_count,
        "set_size": set_size,
        "index_range": [base_index, base_index + len(chunk) - 1],
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "elapsed_seconds": elapsed_s,
        "results": results,
    }


def _run_set(
    tenant_id: str,
    set_number: int,
    all_cases: list[dict[str, Any]],
    *,
    set_count: int,
    set_size: int,
) -> dict[str, Any]:
    sets = split_into_sets(all_cases, set_size=set_size, set_count=set_count)
    if set_number < 1 or set_number > len(sets):
        raise SystemExit(f"--set must be 1..{len(sets)} (got {set_number})")
    chunk = sets[set_number - 1]
    base_index = (set_number - 1) * set_size
    return _run_set_chunk(
        tenant_id,
        set_number,
        chunk,
        base_index=base_index,
        set_count=len(sets),
        set_size=set_size,
    )


def _run_all_sets_parallel(
    tenant_id: str,
    all_cases: list[dict[str, Any]],
    *,
    set_count: int,
    set_size: int,
    reports_dir: Path,
) -> tuple[list[dict[str, Any]], bool]:
    sets = split_into_sets(all_cases, set_size=set_size, set_count=set_count)
    print(
        f"Running {len(sets)} sets × {set_size} questions in parallel "
        f"({len(all_cases)} total)...",
        flush=True,
    )
    wall_t0 = time.perf_counter()
    any_fail = False
    reports: list[dict[str, Any]] = []

    def _job(set_number: int, chunk: list[dict[str, Any]]) -> dict[str, Any]:
        base_index = (set_number - 1) * set_size
        return _run_set_chunk(
            tenant_id,
            set_number,
            chunk,
            base_index=base_index,
            set_count=len(sets),
            set_size=set_size,
            quiet=True,
        )

    with ThreadPoolExecutor(max_workers=len(sets)) as pool:
        futures = {
            pool.submit(_job, n, chunk): n for n, chunk in enumerate(sets, start=1)
        }
        for fut in as_completed(futures):
            set_num = futures[fut]
            try:
                out = fut.result()
            except Exception as exc:  # noqa: BLE001
                any_fail = True
                print(f"Set {set_num} ERROR: {exc}", flush=True)
                continue
            path = reports_dir / f"set_{set_num}.json"
            path.write_text(json.dumps(out, indent=2), encoding="utf-8")
            reports.append(out)
            status = "PASS" if not out["failed"] else "FAIL"
            print(
                f"Set {set_num}: {status} {out['passed']}/{out['total']} "
                f"in {out['elapsed_seconds']}s -> {path.name}",
                flush=True,
            )
            if out["failed"]:
                any_fail = True

    wall_s = round(time.perf_counter() - wall_t0, 1)
    print(f"All sets finished in {wall_s}s wall time (parallel).", flush=True)
    reports.sort(key=lambda r: r.get("set", 0))
    return reports, any_fail


def merge_set_reports(
    reports_dir: Path,
    tenant_id: str,
    *,
    set_count: int = 10,
) -> dict[str, Any]:
    merged: list[dict[str, Any]] = []
    set_summaries: list[dict[str, Any]] = []
    for n in range(1, set_count + 1):
        path = reports_dir / f"set_{n}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        set_summaries.append(
            {
                "set": n,
                "passed": data.get("passed", 0),
                "total": data.get("total", 0),
                "elapsed_seconds": data.get("elapsed_seconds"),
            }
        )
        merged.extend(data.get("results") or [])
    passed = sum(1 for r in merged if r.get("ok"))
    out = {
        "tenant": tenant_id,
        "sets": set_summaries,
        "total": len(merged),
        "passed": passed,
        "failed": len(merged) - passed,
        "results": merged,
    }
    out_path = reports_dir / "merged.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate datamart question bank (live broker).",
    )
    parser.add_argument("--tenant", default=os.getenv("DATAMART_TENANT_ID", "demo_tenant"))
    parser.add_argument("--json", default=None, help="Write report JSON for this run")
    parser.add_argument(
        "--set",
        type=int,
        default=None,
        metavar="N",
        help="Run only set N (1..set_count from bank meta, 6 questions per set by default)",
    )
    parser.add_argument(
        "--all-sets",
        action="store_true",
        help="Run all sets (default: parallel; use --sequential for one-after-another)",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="With --all-sets: run every set concurrently (default when --all-sets)",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="With --all-sets: run sets one after another (legacy)",
    )
    parser.add_argument(
        "--indices",
        default=None,
        help="Comma-separated 0-based indices (overrides --set)",
    )
    parser.add_argument(
        "--merge-reports",
        default=None,
        metavar="DIR",
        help="Merge set_1.json .. set_5.json from DIR into merged.json",
    )
    args = parser.parse_args()

    raw = _load_bank_raw()
    set_count, set_size = _bank_dimensions(raw)
    expected = set_count * set_size

    if args.merge_reports:
        out = merge_set_reports(
            Path(args.merge_reports),
            args.tenant,
            set_count=set_count,
        )
        print(json.dumps(out, indent=2))
        if out["failed"]:
            sys.exit(1)
        print(f"\nMerged: {out['passed']}/{out['total']} passed -> {args.merge_reports}/merged.json")
        return

    all_cases, set_count, set_size = _load_bank()
    if len(all_cases) != expected:
        print(
            f"Warning: bank has {len(all_cases)} questions; expected {expected} "
            f"({set_count}×{set_size}).",
            file=sys.stderr,
        )

    reports: list[dict[str, Any]] = []

    if args.indices:
        idxs = [int(x.strip()) for x in args.indices.split(",") if x.strip()]
        chunk = [all_cases[i] for i in idxs]
        print(f"Running {len(chunk)} questions by index...", flush=True)
        t0 = time.perf_counter()
        results = run_with_datamart_context(
            args.tenant, _eval_batch, chunk, base_index=idxs[0] if idxs else 0
        )
        out = {
            "tenant": args.tenant,
            "total": len(results),
            "passed": sum(1 for r in results if r["ok"]),
            "failed": sum(1 for r in results if not r["ok"]),
            "elapsed_seconds": round(time.perf_counter() - t0, 1),
            "results": results,
        }
        reports.append(out)
    elif args.all_sets:
        DEFAULT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        use_parallel = args.parallel or not args.sequential
        if use_parallel:
            _, any_fail = _run_all_sets_parallel(
                args.tenant,
                all_cases,
                set_count=set_count,
                set_size=set_size,
                reports_dir=DEFAULT_REPORTS_DIR,
            )
        else:
            any_fail = False
            for n in range(1, set_count + 1):
                out = _run_set(
                    args.tenant,
                    n,
                    all_cases,
                    set_count=set_count,
                    set_size=set_size,
                )
                path = DEFAULT_REPORTS_DIR / f"set_{n}.json"
                path.write_text(json.dumps(out, indent=2), encoding="utf-8")
                print(
                    f"Set {n}: {out['passed']}/{out['total']} passed in {out['elapsed_seconds']}s "
                    f"-> {path}",
                    flush=True,
                )
                if out["failed"]:
                    any_fail = True
        merged = merge_set_reports(
            DEFAULT_REPORTS_DIR,
            args.tenant,
            set_count=set_count,
        )
        print(json.dumps(merged, indent=2))
        if any_fail or merged["failed"]:
            sys.exit(1)
        print(f"\nAll sets passed: {merged['passed']}/{merged['total']} questions.")
        return
    elif args.set:
        out = _run_set(
            args.tenant,
            args.set,
            all_cases,
            set_count=set_count,
            set_size=set_size,
        )
        reports.append(out)
    else:
        # Legacy: all 50 in one set (slow — prefer --all-sets or --set N)
        print(
            f"Running all {len(all_cases)} questions in one batch "
            "(use --set 1..5 or --all-sets for faster runs).",
            flush=True,
        )
        t0 = time.perf_counter()
        results = run_with_datamart_context(
            args.tenant, _eval_batch, all_cases, base_index=0
        )
        out = {
            "tenant": args.tenant,
            "total": len(results),
            "passed": sum(1 for r in results if r["ok"]),
            "failed": sum(1 for r in results if not r["ok"]),
            "elapsed_seconds": round(time.perf_counter() - t0, 1),
            "results": results,
        }
        reports.append(out)

    out = reports[-1]
    text = json.dumps(out, indent=2)
    if args.json:
        Path(args.json).write_text(text, encoding="utf-8")
    print(text)

    if out.get("failed"):
        print(
            f"\nQuestion bank: {out['passed']}/{out['total']} passed; "
            f"{out['failed']} failed.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"\nQuestion bank: {out['passed']}/{out['total']} passed.")


if __name__ == "__main__":
    main()

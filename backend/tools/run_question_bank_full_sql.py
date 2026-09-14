"""
Run all 66 question-bank prompts → final SQL → (optional) warehouse execute → result check.

Batch mode (recommended for --execute):
  11 sets × 6 questions in parallel (default). Much faster than --sequential (~10–15 min vs ~45 min).

Usage (from backend/):
  # Export all 66 SQL scripts (offline, fast)
  PYTHONPATH=. python tools/run_question_bank_full_sql.py --export-md tools/question_bank_reports/all_66_sql.md

  # Execute all 66 on warehouse — parallel sets (default, 4 workers)
  PYTHONPATH=. python tools/run_question_bank_full_sql.py --all-sets --execute --export-json tools/question_bank_reports/all_66_executed.json

  # More parallelism (if warehouse allows extra connections)
  PYTHONPATH=. python tools/run_question_bank_full_sql.py --all-sets --execute --max-workers 6

  # One OS process per set (11 subprocesses; use when in-process parallel is flaky)
  PYTHONPATH=. python tools/run_question_bank_full_sql.py --all-sets --execute --spawn-sets --wait-sets

  # Slow/debug: one set after another
  PYTHONPATH=. python tools/run_question_bank_full_sql.py --all-sets --execute --sequential

  # Single set only
  PYTHONPATH=. python tools/run_question_bank_full_sql.py --set 3 --execute
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.services.ai_services.datamart.pipeline.link_eval import load_question_bank
from app.services.ai_services.datamart.pipeline.question_bank_full_sql_eval import (
    FullSqlReport,
    eval_question_bank_full_sql,
    export_all_sql_json,
    export_all_sql_markdown,
    merge_full_sql_reports,
    report_from_dict,
    report_to_dict,
)
from app.services.ai_services.datamart.workspace.runtime_context import run_with_datamart_context

BANK_PATH = Path(__file__).parent / "datamart_question_bank.yaml"
REPORTS_DIR = Path(__file__).parent / "question_bank_reports"
DEFAULT_MD = REPORTS_DIR / "all_66_sql.md"
DEFAULT_JSON = REPORTS_DIR / "all_66_sql.json"
MIN_RESULT_PASS_RATE = 0.80


def _bank_dimensions(raw: dict[str, Any]) -> tuple[int, int]:
    meta = raw.get("meta") or {}
    return int(meta.get("set_count", 11)), int(meta.get("set_size", 6))


def split_into_sets(
    cases: list[dict[str, Any]],
    *,
    set_size: int,
    set_count: int,
) -> list[list[dict[str, Any]]]:
    sets: list[list[dict[str, Any]]] = []
    for i in range(set_count):
        chunk = cases[i * set_size : i * set_size + set_size]
        if chunk:
            sets.append(chunk)
    return sets


def _print_summary(report: FullSqlReport, *, tenant: str, meta: dict) -> None:
    print(
        f"Question bank full SQL (tenant={meta.get('tenant', tenant)})",
        flush=True,
    )
    print(f"  Questions:     {report.total}", flush=True)
    print(f"  With SQL:      {report.with_sql}/{report.total}", flush=True)
    if report.executed:
        print(f"  Warehouse OK:  {report.exec_ok}/{report.with_sql}", flush=True)
        print(
            f"  Result fit OK: {report.result_ok}/{report.with_sql} "
            f"(returned columns match question)",
            flush=True,
        )
    else:
        print(
            "  (Add --execute to run SQL on warehouse and validate result columns)",
            flush=True,
        )
    print(f"  Passed:        {report.passed}/{report.total}", flush=True)


def _print_results(report: FullSqlReport, *, failures_only: bool) -> None:
    for r in report.results:
        if failures_only and r.ok:
            continue
        status = "OK" if r.ok else "FAIL"
        print(f"\n  [{r.index + 1}] {status} {r.section} tier={r.tier or '-'}", flush=True)
        print(f"    {r.question[:100]}{'…' if len(r.question) > 100 else ''}", flush=True)
        if r.errors:
            for e in r.errors[:4]:
                print(f"    ! {e}", flush=True)
        if r.executed and r.result_columns:
            print(f"    cols: {', '.join(r.result_columns[:10])}", flush=True)


def _run_set_chunk(
    tenant_id: str,
    set_number: int,
    chunk: list[dict[str, Any]],
    *,
    base_index: int,
    execute: bool,
    quiet: bool = False,
) -> FullSqlReport:
    if not quiet:
        print(
            f"Set {set_number}: questions {base_index + 1}-{base_index + len(chunk)} "
            f"({len(chunk)} items)",
            flush=True,
        )
    t0 = time.perf_counter()

    def _eval_batch() -> FullSqlReport:
        results = []
        for i, case in enumerate(chunk):
            from app.services.ai_services.datamart.pipeline.question_bank_full_sql_eval import (
                evaluate_full_sql_one,
            )

            results.append(
                evaluate_full_sql_one(
                    case,
                    index=base_index + i,
                    mode="live" if execute else "offline",
                    execute=execute,
                )
            )
        with_sql = sum(1 for r in results if r.sql)
        exec_ok = sum(1 for r in results if r.executed and not r.exec_error)
        result_ok = sum(
            1 for r in results if r.executed and r.result_adequacy_ok and not r.exec_error
        )
        passed = sum(1 for r in results if r.ok)
        return FullSqlReport(
            mode="live" if execute else "offline",
            executed=execute,
            total=len(results),
            with_sql=with_sql,
            exec_ok=exec_ok,
            result_ok=result_ok,
            passed=passed,
            failed=len(results) - passed,
            results=results,
        )

    report = run_with_datamart_context(tenant_id, _eval_batch)
    elapsed = round(time.perf_counter() - t0, 1)
    if not quiet:
        print(
            f"Set {set_number} done: {report.passed}/{report.total} passed in {elapsed}s",
            flush=True,
        )
    return report


def _run_all_sets_parallel(
    tenant_id: str,
    all_cases: list[dict[str, Any]],
    *,
    set_count: int,
    set_size: int,
    execute: bool,
    reports_dir: Path,
    max_workers: int = 4,
) -> tuple[FullSqlReport, bool]:
    sets = split_into_sets(all_cases, set_size=set_size, set_count=set_count)
    workers = min(max_workers, len(sets))
    print(
        f"Running {len(sets)} sets × {set_size} questions "
        f"({len(all_cases)} total, execute={execute}, workers={workers})...",
        flush=True,
    )
    wall_t0 = time.perf_counter()
    any_fail = False
    reports: list[FullSqlReport] = []

    def _job(set_number: int, chunk: list[dict[str, Any]]) -> FullSqlReport:
        base_index = (set_number - 1) * set_size
        return _run_set_chunk(
            tenant_id,
            set_number,
            chunk,
            base_index=base_index,
            execute=execute,
            quiet=True,
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_job, n, chunk): n for n, chunk in enumerate(sets, start=1)
        }
        for fut in as_completed(futures):
            set_num = futures[fut]
            try:
                rep = fut.result()
            except Exception as exc:  # noqa: BLE001
                any_fail = True
                print(f"Set {set_num} ERROR: {exc}", flush=True)
                continue
            path = reports_dir / f"full_sql_set_{set_num}.json"
            path.write_text(json.dumps(report_to_dict(rep), indent=2), encoding="utf-8")
            reports.append(rep)
            status = "PASS" if rep.failed == 0 else "FAIL"
            print(
                f"Set {set_num}: {status} {rep.passed}/{rep.total} "
                f"(warehouse {rep.exec_ok}/{rep.with_sql}, result {rep.result_ok}/{rep.with_sql}) "
                f"-> {path.name}",
                flush=True,
            )
            if rep.failed:
                any_fail = True

    wall_s = round(time.perf_counter() - wall_t0, 1)
    print(f"All sets finished in {wall_s}s wall time (parallel).", flush=True)
    merged = merge_full_sql_reports(reports)
    return merged, any_fail


def merge_set_reports(reports_dir: Path, *, set_count: int = 11) -> FullSqlReport:
    reports: list[FullSqlReport] = []
    for n in range(1, set_count + 1):
        path = reports_dir / f"full_sql_set_{n}.json"
        if not path.exists():
            continue
        reports.append(report_from_dict(json.loads(path.read_text(encoding="utf-8"))))
    return merge_full_sql_reports(reports)


def spawn_all_sets_subprocess(
    *,
    set_count: int,
    tenant: str,
    execute: bool,
    reports_dir: Path,
    bank: Path,
) -> list[subprocess.Popen]:
    """Launch one OS process per set (true background batches)."""
    procs: list[subprocess.Popen] = []
    script = Path(__file__).resolve()
    env = {**os.environ, "PYTHONPATH": str(script.parent.parent), "PYTHONUNBUFFERED": "1"}
    for n in range(1, set_count + 1):
        cmd = [
            sys.executable,
            str(script),
            "--set",
            str(n),
            "--tenant",
            tenant,
            "--bank",
            str(bank),
        ]
        if execute:
            cmd.append("--execute")
        log_path = reports_dir / f"full_sql_set_{n}.log"
        log_f = log_path.open("w", encoding="utf-8")
        print(f"Spawn set {n} -> {log_path.name}", flush=True)
        procs.append(
            subprocess.Popen(
                cmd,
                cwd=str(script.parent.parent),
                env=env,
                stdout=log_f,
                stderr=subprocess.STDOUT,
            )
        )
    return procs


def wait_spawned_sets(
    procs: list[subprocess.Popen],
    *,
    reports_dir: Path,
    set_count: int,
) -> bool:
    any_fail = False
    for i, proc in enumerate(procs, start=1):
        code = proc.wait()
        status = "OK" if code == 0 else f"exit {code}"
        print(f"Set {i} process {status}", flush=True)
        if code != 0:
            any_fail = True
    merged = merge_set_reports(reports_dir, set_count=set_count)
    return not any_fail and merged.failed == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Question bank: resolve all SQL, export, execute, validate results",
    )
    parser.add_argument("--bank", type=Path, default=BANK_PATH)
    parser.add_argument(
        "--tenant",
        default=os.getenv("DATAMART_TENANT_ID", "demo_tenant"),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run each SQL on the warehouse and validate result columns",
    )
    parser.add_argument(
        "--all-sets",
        action="store_true",
        help="Run all bank sets (11×6 by default); use with --parallel",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="With --all-sets: run every set concurrently (default when --all-sets)",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="With --all-sets: run sets one after another (slow; default is parallel)",
    )
    parser.add_argument(
        "--set",
        type=int,
        default=None,
        metavar="N",
        help="Run only set N (1..set_count)",
    )
    parser.add_argument(
        "--merge-reports",
        type=Path,
        default=None,
        metavar="DIR",
        help="Merge full_sql_set_*.json from DIR into merged report",
    )
    parser.add_argument("--export-md", type=Path, default=None)
    parser.add_argument("--export-json", type=Path, default=None)
    parser.add_argument(
        "--failures-only",
        action="store_true",
        help="Print only failed cases",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Max parallel set workers when using --parallel (default 4)",
    )
    parser.add_argument(
        "--spawn-sets",
        action="store_true",
        help="Launch one OS subprocess per set (11 background processes)",
    )
    parser.add_argument(
        "--wait-sets",
        action="store_true",
        help="With --spawn-sets: block until all set processes finish and merge",
    )
    parser.add_argument("--section", action="append", dest="sections")
    args = parser.parse_args(
        argv if argv is not None else (sys.argv[1:] if __name__ == "__main__" else [])
    )

    raw = yaml.safe_load(args.bank.read_text(encoding="utf-8")) or {}
    set_count, set_size = _bank_dimensions(raw)
    meta = raw.get("meta") or {}
    _raw, all_cases = load_question_bank(args.bank)

    if args.merge_reports:
        report = merge_set_reports(args.merge_reports, set_count=set_count)
        _print_summary(report, tenant=args.tenant, meta=meta)
        out_md = args.export_md or (args.merge_reports / "all_66_sql.md")
        out_md.write_text(export_all_sql_markdown(report), encoding="utf-8")
        out_json = args.export_json or (args.merge_reports / "all_66_sql.json")
        out_json.write_text(export_all_sql_json(report), encoding="utf-8")
        print(f"Merged -> {out_md} and {out_json}", flush=True)
        return 0 if report.failed == 0 else 1

    cases = all_cases
    if args.sections:
        allow = {s.lower() for s in args.sections}
        cases = [c for c in cases if str(c.get("section", "")).lower() in allow]

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    any_fail = False

    if args.spawn_sets:
        procs = spawn_all_sets_subprocess(
            set_count=set_count,
            tenant=args.tenant,
            execute=args.execute,
            reports_dir=REPORTS_DIR,
            bank=args.bank,
        )
        if not args.wait_sets:
            print(
                f"Launched {len(procs)} set processes. "
                f"Logs: {REPORTS_DIR}/full_sql_set_N.log "
                f"JSON: {REPORTS_DIR}/full_sql_set_N.json",
                flush=True,
            )
            print(
                "When done, merge with:\n"
                f"  PYTHONPATH=. python tools/run_question_bank_full_sql.py "
                f"--merge-reports {REPORTS_DIR}",
                flush=True,
            )
            return 0
        any_fail = not wait_spawned_sets(procs, reports_dir=REPORTS_DIR, set_count=set_count)
        report = merge_set_reports(REPORTS_DIR, set_count=set_count)
    elif args.all_sets or (args.execute and not args.set):
        use_parallel = args.parallel or not args.sequential
        if use_parallel:
            report, any_fail = _run_all_sets_parallel(
                args.tenant,
                cases,
                set_count=set_count,
                set_size=set_size,
                execute=args.execute,
                reports_dir=REPORTS_DIR,
                max_workers=max(1, args.max_workers),
            )
        else:
            sets = split_into_sets(cases, set_size=set_size, set_count=set_count)
            reps: list[FullSqlReport] = []
            for n, chunk in enumerate(sets, start=1):
                rep = _run_set_chunk(
                    args.tenant,
                    n,
                    chunk,
                    base_index=(n - 1) * set_size,
                    execute=args.execute,
                )
                path = REPORTS_DIR / f"full_sql_set_{n}.json"
                path.write_text(json.dumps(report_to_dict(rep), indent=2), encoding="utf-8")
                reps.append(rep)
                if rep.failed:
                    any_fail = True
            report = merge_full_sql_reports(reps)
    elif args.set:
        sets = split_into_sets(cases, set_size=set_size, set_count=set_count)
        if args.set < 1 or args.set > len(sets):
            raise SystemExit(f"--set must be 1..{len(sets)}")
        chunk = sets[args.set - 1]
        report = _run_set_chunk(
            args.tenant,
            args.set,
            chunk,
            base_index=(args.set - 1) * set_size,
            execute=args.execute,
        )
        path = REPORTS_DIR / f"full_sql_set_{args.set}.json"
        path.write_text(json.dumps(report_to_dict(report), indent=2), encoding="utf-8")
        _print_summary(report, tenant=args.tenant, meta=meta)
        _print_results(report, failures_only=args.failures_only)
        print(f"Wrote {path}", flush=True)
        return 0 if report.failed == 0 else 1
    else:
        def _run_single():
            return eval_question_bank_full_sql(
                cases,
                mode="live" if args.execute else "offline",
                execute=args.execute,
            )

        if args.execute:
            report = run_with_datamart_context(args.tenant, _run_single)
        else:
            report = _run_single()
        any_fail = report.failed > 0

    _print_summary(report, tenant=args.tenant, meta=meta)
    _print_results(report, failures_only=args.failures_only)

    export_md = args.export_md or DEFAULT_MD
    export_md.parent.mkdir(parents=True, exist_ok=True)
    export_md.write_text(export_all_sql_markdown(report), encoding="utf-8")
    print(f"\nWrote all SQL scripts -> {export_md}", flush=True)

    json_path = args.export_json or DEFAULT_JSON
    json_path.write_text(export_all_sql_json(report), encoding="utf-8")
    print(f"Wrote JSON report -> {json_path}", flush=True)

    if report.with_sql < report.total:
        return 1
    if report.executed:
        rate = report.result_ok / report.with_sql if report.with_sql else 0
        if rate < MIN_RESULT_PASS_RATE:
            print(
                f"\nFAIL: result fit {rate:.1%} below {MIN_RESULT_PASS_RATE:.0%}",
                flush=True,
            )
            return 1
    return 1 if any_fail or (report.executed and report.failed) else 0


if __name__ == "__main__":
    sys.exit(main())

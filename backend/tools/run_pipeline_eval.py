"""
S5 combined offline eval: schema link + SQL resolve (no LLM, no warehouse).

Usage (from backend/):
  PYTHONPATH=. python tools/run_pipeline_eval.py
  PYTHONPATH=. python tools/run_pipeline_eval.py --json tools/pipeline_eval_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.services.ai_services.datamart.pipeline.link_eval import (
    eval_question_bank,
    load_question_bank,
)
from app.services.ai_services.datamart.pipeline.resolve_eval import (
    eval_question_bank_resolve,
)

MIN_TIER_AB_COVERAGE = 0.85


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Datamart S5 pipeline offline eval")
    parser.add_argument(
        "--bank",
        type=Path,
        default=Path(__file__).parent / "datamart_question_bank.yaml",
    )
    parser.add_argument("--json", type=Path, help="Write combined report JSON")
    args = parser.parse_args(
        argv
        if argv is not None
        else (sys.argv[1:] if __name__ == "__main__" else [])
    )

    raw, cases = load_question_bank(args.bank)
    meta = raw.get("meta") or {}

    link = eval_question_bank(cases, bank_path=args.bank)
    resolve = eval_question_bank_resolve(cases, bank_path=args.bank)

    print(
        f"S5 pipeline eval (tenant={meta.get('tenant', '?')})",
        flush=True,
    )
    print(
        f"  Link:    {link.passed}/{link.total} passed",
        flush=True,
    )
    print(
        f"  Resolve: {resolve.passed}/{resolve.total} passed "
        f"(Tier A={resolve.tier_a}, B={resolve.tier_b}, unresolved={resolve.unresolved})",
        flush=True,
    )
    if resolve.total:
        governed = resolve.tier_a + resolve.tier_b
        pct = round(100.0 * governed / resolve.total, 1)
        print(
            f"  Tier A+B coverage: {governed}/{resolve.total} ({pct}%) — target >=85% for production",
            flush=True,
        )
        if governed / resolve.total < MIN_TIER_AB_COVERAGE:
            print(
                f"  FAIL: Tier A+B coverage {pct}% below {MIN_TIER_AB_COVERAGE * 100:.0f}% target",
                flush=True,
            )
            return 1

    for r in resolve.results:
        if not r.ok:
            print(f"  FAIL [{r.section}] tier={r.tier} {r.errors}", flush=True)

    if args.json:
        payload = {
            "meta": meta,
            "link": {
                "passed": link.passed,
                "failed": link.failed,
                "total": link.total,
            },
            "resolve": {
                "passed": resolve.passed,
                "failed": resolve.failed,
                "total": resolve.total,
                "tier_a": resolve.tier_a,
                "tier_b": resolve.tier_b,
                "unresolved": resolve.unresolved,
            },
            "failures": [
                {
                    "section": r.section,
                    "question": r.question_preview,
                    "tier": r.tier,
                    "sql_source": r.sql_source,
                    "errors": r.errors,
                }
                for r in resolve.results
                if not r.ok
            ],
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {args.json}", flush=True)

    return 0 if link.success and resolve.success else 1


if __name__ == "__main__":
    sys.exit(main())

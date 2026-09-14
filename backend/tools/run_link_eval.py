"""
Offline S4 link eval — domain + allowlist + Tier-B scoping (no LLM, no warehouse).

Usage (from backend/):
  PYTHONPATH=. python tools/run_link_eval.py
  PYTHONPATH=. python tools/run_link_eval.py --json tools/link_eval_report.json
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Datamart question-bank link eval (S4)")
    parser.add_argument(
        "--bank",
        type=Path,
        default=Path(__file__).parent / "datamart_question_bank.yaml",
    )
    parser.add_argument("--json", type=Path, help="Write full report JSON")
    parser.add_argument(
        "--no-tier-b",
        action="store_true",
        help="Skip Tier-B retrieval probes",
    )
    if argv is None:
        import sys

        argv = sys.argv[1:] if __name__ == "__main__" else []
    args = parser.parse_args(argv)

    raw, cases = load_question_bank(args.bank)
    meta = raw.get("meta") or {}
    report = eval_question_bank(
        cases,
        bank_path=args.bank,
        check_tier_b=not args.no_tier_b,
    )

    print(
        f"Link eval: {report.passed}/{report.total} passed "
        f"(tenant={meta.get('tenant', '?')}, sets={meta.get('set_count', '?')})"
    )
    for r in report.results:
        if not r.ok:
            print(f"  FAIL [{r.section}] {r.question_preview}")
            for err in r.errors:
                print(f"       - {err}".encode("ascii", "replace").decode("ascii"))

    if args.json:
        payload = {
            "meta": meta,
            "total": report.total,
            "passed": report.passed,
            "failed": report.failed,
            "failures": [
                {
                    "section": r.section,
                    "question": r.question_preview,
                    "eval_domain": r.eval_domain,
                    "classified_domain": r.classified_domain,
                    "errors": r.errors,
                    "tier_b_source": r.tier_b_source,
                }
                for r in report.results
                if not r.ok
            ],
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {args.json}")

    return 0 if report.success else 1


if __name__ == "__main__":
    sys.exit(main())

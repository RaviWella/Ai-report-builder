"""
Suggest verified_queries.yaml rows for unresolved question-bank cases.

Usage (from backend/):
  PYTHONPATH=. python tools/sync_verified_candidates.py
  PYTHONPATH=. python tools/sync_verified_candidates.py --json tools/verified_candidates.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.services.ai_services.datamart.pipeline.link_eval import load_question_bank
from app.services.ai_services.datamart.pipeline.resolve_eval import eval_resolve_one


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="List question-bank rows with no Tier A/B SQL (candidates for verified_queries.yaml)",
    )
    parser.add_argument(
        "--bank",
        type=Path,
        default=Path(__file__).parent / "datamart_question_bank.yaml",
    )
    parser.add_argument("--json", type=Path, help="Write candidate list as JSON")
    args = parser.parse_args(argv or sys.argv[1:])

    _raw, cases = load_question_bank(args.bank)
    unresolved: list[dict] = []
    for case in cases:
        r = eval_resolve_one(case)
        if r.tier is None and not r.errors:
            unresolved.append(
                {
                    "section": r.section,
                    "eval_domain": case.get("eval_domain"),
                    "expect_tables": case.get("expect_tables"),
                    "question": case.get("question"),
                    "suggested_id": (
                        str(case.get("section") or "row")
                        .lower()
                        .replace(" ", "_")
                        .replace(".", "_")[:48]
                    ),
                }
            )

    print(f"Unresolved (no Tier A/B): {len(unresolved)} / {len(cases)}", flush=True)
    for item in unresolved[:15]:
        print(f"  - [{item['section']}] domain={item['eval_domain']}", flush=True)
    if len(unresolved) > 15:
        print(f"  ... and {len(unresolved) - 15} more", flush=True)

    if args.json:
        args.json.write_text(json.dumps(unresolved, indent=2), encoding="utf-8")
        print(f"Wrote {args.json}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

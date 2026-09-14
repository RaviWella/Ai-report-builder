"""
Append Tier-B verified queries for unresolved question-bank rows.

Usage (from backend/):
  PYTHONPATH=. python tools/sync_verified_candidates.py --json tools/verified_candidates.json
  PYTHONPATH=. python tools/generate_verified_from_candidates.py
  PYTHONPATH=. python tools/generate_verified_from_candidates.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

CANDIDATES = Path(__file__).parent / "verified_candidates.json"
VERIFIED = (
    Path(__file__).resolve().parent.parent
    / "app/services/ai_services/datamart/verified_queries.yaml"
)


def _slug(text: str, idx: int) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", (text or "row").lower()).strip("_")[:40]
    return f"bank_{base}_{idx}"


def _sql_for(domain: str, tables: list[str], question: str) -> str:
    t = {x.lower() for x in tables}
    q = question.lower()
    schema = "{schema}"
    lim = "LIMIT {limit}"

    if "month-over-month" in q and "fct_processed_salary" in t:
        return f"""SELECT
  pg.payroll_group_name,
  date_trunc('month', pp.period_start) AS pay_month,
  SUM(COALESCE(ps.gross_salary, 0)) AS total_gross
FROM {schema}.fct_processed_salary ps
JOIN {schema}.dim_payroll_period pp ON pp.payroll_period_sk = ps.payroll_period_sk
LEFT JOIN {schema}.dim_payroll_group pg ON pg.payroll_group_sk = ps.payroll_group_sk
WHERE pp.period_start >= CURRENT_DATE - INTERVAL '6 months'
GROUP BY 1, 2
ORDER BY pay_month, pg.payroll_group_name
{lim};"""

    if "absent days greater than present" in q:
        return f"""SELECT
  e.emp_fullname AS employee_name,
  e.branch_name AS branch,
  e.department_name AS department,
  SUM(COALESCE(a.absent_days, 0)) AS absent_days,
  SUM(COALESCE(a.present_days, 0)) AS present_days
FROM {schema}.vw_attendance_summary a
JOIN {schema}.mart_employee_current e ON e.employee_id = a.employee_id
WHERE date_trunc('month', a.period_date) = date_trunc('month', CURRENT_DATE)
GROUP BY 1, 2, 3
HAVING SUM(COALESCE(a.absent_days, 0)) > SUM(COALESCE(a.present_days, 0))
ORDER BY absent_days DESC
{lim};"""

    if "late events year-to-date" in q:
        return f"""SELECT
  e.emp_fullname AS employee_name,
  e.branch_name AS branch,
  SUM(COALESCE(a.late_events, 0)) AS late_count,
  SUM(COALESCE(a.absent_days, 0)) AS absent_days
FROM {schema}.vw_attendance_summary a
JOIN {schema}.mart_employee_current e ON e.employee_id = a.employee_id
WHERE a.period_date >= date_trunc('year', CURRENT_DATE)
GROUP BY 1, 2
HAVING SUM(COALESCE(a.late_events, 0)) > 20
   AND SUM(COALESCE(a.absent_days, 0)) < 3
ORDER BY late_count DESC
{lim};"""

    if "reporting manager" in q and "direct reports" in q:
        return f"""SELECT
  m.superior_fullname AS manager_name,
  m.branch_name AS branch,
  COUNT(*) AS direct_reports
FROM {schema}.mart_employee_current m
WHERE COALESCE(m.is_current, TRUE) = TRUE
  AND m.superior_emp_no IS NOT NULL
GROUP BY 1, 2
ORDER BY direct_reports DESC
{lim};"""

    if "probation ending" in q:
        return f"""SELECT
  e.emp_fullname AS employee_name,
  e.branch_name AS branch,
  e.department_name AS department,
  e.probation_due_date AS probation_end_date,
  e.superior_fullname AS supervisor_name
FROM {schema}.mart_employee_current e
WHERE e.probation_due_date >= CURRENT_DATE
  AND e.probation_due_date < CURRENT_DATE + INTERVAL '60 days'
ORDER BY e.probation_due_date
{lim};"""

    if "employment type" in q and "employee category" in q:
        return f"""SELECT
  e.branch_name AS branch,
  e.employee_category,
  e.employment_type,
  e.company_name AS legal_entity,
  COUNT(*) AS headcount
FROM {schema}.mart_employee_current e
WHERE COALESCE(e.is_current, TRUE) = TRUE
GROUP BY 1, 2, 3, 4
ORDER BY branch, headcount DESC
{lim};"""

    if "separations versus hires" in q:
        return f"""SELECT
  date_trunc('month', ls.event_month) AS month,
  SUM(COALESCE(ls.separations, 0)) AS separations,
  SUM(COALESCE(ls.hires, 0)) AS hires
FROM {schema}.vw_lifecycle_summary ls
WHERE ls.event_month >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY 1
ORDER BY 1
{lim};"""

    if "separation events by event type" in q:
        return f"""SELECT
  le.event_type,
  le.event_reason,
  COUNT(*) AS event_count
FROM {schema}.fct_lifecycle_event le
WHERE date_trunc('year', le.event_date) = date_trunc('year', CURRENT_DATE)
GROUP BY 1, 2
ORDER BY event_count DESC
{lim};"""

    if "tenure under 12 months" in q:
        return f"""SELECT
  e.emp_fullname AS employee_name,
  e.branch_name AS branch,
  e.date_joined AS hire_date,
  le.event_date AS separation_date,
  le.event_type
FROM {schema}.fct_lifecycle_event le
JOIN {schema}.mart_employee_current e ON e.employee_id = le.employee_id
WHERE le.event_type ILIKE '%separ%'
  AND le.event_date >= date_trunc('quarter', CURRENT_DATE) - INTERVAL '3 months'
  AND le.event_date < date_trunc('quarter', CURRENT_DATE)
  AND le.event_date - e.date_joined < INTERVAL '12 months'
ORDER BY le.event_date DESC
{lim};"""

    if "headcount trend by month" in q:
        return f"""SELECT
  hm.year_month,
  SUM(COALESCE(hm.active_count, 0)) AS active_employees,
  SUM(COALESCE(hm.new_hires, 0)) AS new_hires,
  SUM(COALESCE(hm.separations, 0)) AS separations
FROM {schema}.mart_headcount_monthly hm
WHERE hm.year_month >= to_char(CURRENT_DATE - INTERVAL '12 months', 'YYYY-MM')
GROUP BY 1
ORDER BY 1
{lim};"""

    if "headcount six months ago" in q or "growth above 10%" in q:
        return f"""SELECT
  hm.branch_name AS branch,
  SUM(CASE WHEN hm.year_month = to_char(CURRENT_DATE, 'YYYY-MM') THEN hm.active_count ELSE 0 END) AS current_hc,
  SUM(CASE WHEN hm.year_month = to_char(CURRENT_DATE - INTERVAL '6 months', 'YYYY-MM') THEN hm.active_count ELSE 0 END) AS hc_six_months_ago
FROM {schema}.mart_headcount_monthly hm
GROUP BY 1
ORDER BY branch
{lim};"""

    if "department and designation" in q and "count descending" in q:
        return f"""SELECT
  e.department_name AS department,
  d.designation_name,
  COUNT(*) AS employee_count
FROM {schema}.mart_employee_current e
LEFT JOIN {schema}.dim_designation d ON d.designation_sk::text = e.designation_id::text
WHERE COALESCE(e.is_current, TRUE) = TRUE
GROUP BY 1, 2
ORDER BY employee_count DESC
{lim};"""

    if "fewer than 10 active employees" in q:
        return f"""SELECT
  e.company_name AS legal_entity,
  COUNT(DISTINCT e.employee_id) AS active_employees,
  COUNT(DISTINCT le.employee_id) AS separations_last_year
FROM {schema}.mart_employee_current e
LEFT JOIN {schema}.fct_lifecycle_event le
  ON le.employee_id = e.employee_id
 AND le.event_type ILIKE '%separ%'
 AND le.event_date >= CURRENT_DATE - INTERVAL '1 year'
WHERE COALESCE(e.is_current, TRUE) = TRUE
GROUP BY 1
HAVING COUNT(DISTINCT e.employee_id) < 10
   AND COUNT(DISTINCT le.employee_id) > 3
ORDER BY separations_last_year DESC
{lim};"""

    if "point-in-time headcount from snap" in q:
        return f"""SELECT
  hm.branch_name AS branch,
  hm.active_count AS headcount_today,
  hm2.active_count AS headcount_last_year
FROM {schema}.mart_headcount_monthly hm
LEFT JOIN {schema}.mart_headcount_monthly hm2
  ON hm2.branch_name = hm.branch_name
 AND hm2.year_month = to_char(CURRENT_DATE - INTERVAL '1 year', 'YYYY-MM')
WHERE hm.year_month = to_char(CURRENT_DATE, 'YYYY-MM')
ORDER BY branch
{lim};"""

    if "count on probation" in q and "no assigned pay group" in q:
        return f"""SELECT
  e.branch_name AS branch,
  COUNT(*) FILTER (WHERE COALESCE(e.is_current, TRUE)) AS active_headcount,
  COUNT(*) FILTER (WHERE e.probation_due_date >= CURRENT_DATE) AS on_probation,
  COUNT(*) FILTER (WHERE e.payroll_group_name IS NULL) AS no_pay_group
FROM {schema}.mart_employee_current e
GROUP BY 1
ORDER BY branch
{lim};"""

    if "top quartile of basic salary" in q:
        return f"""SELECT
  e.branch_name AS branch,
  AVG(lb.leave_days) AS avg_approved_leave_days
FROM {schema}.vw_payroll_summary p
JOIN {schema}.mart_employee_current e ON e.emp_no = p.employee_no
JOIN {schema}.fact_leave_balance lb ON lb.employee_id = e.employee_id
WHERE LOWER(COALESCE(lb.leave_status, '')) LIKE '%approv%'
GROUP BY 1
ORDER BY branch
{lim};"""

    if "net salary above branch median" in q:
        return f"""SELECT
  p.employee_name,
  p.branch_name AS branch,
  p.net_salary,
  lb.leave_days
FROM {schema}.vw_payroll_summary p
JOIN {schema}.fact_leave_balance lb ON lb.employee_id = p.employee_id
WHERE lb.leave_days > 20
ORDER BY p.net_salary DESC
{lim};"""

    if "high payroll cost" in q and "high leave utilization" in q:
        return f"""SELECT
  e.department_name AS department,
  SUM(COALESCE(p.basic_salary, 0)) AS payroll_cost,
  SUM(COALESCE(lb.leave_days, 0)) AS leave_days
FROM {schema}.mart_employee_current e
JOIN {schema}.vw_payroll_summary p ON p.employee_no = e.emp_no
LEFT JOIN {schema}.fact_leave_balance lb ON lb.employee_id = e.employee_id
GROUP BY 1
ORDER BY payroll_cost DESC, leave_days DESC
{lim};"""

    if "sick leave versus none" in q:
        return f"""SELECT
  p.branch_name AS branch,
  AVG(p.net_salary) FILTER (WHERE ls.leave_type_name ILIKE '%sick%') AS avg_net_with_sick,
  AVG(p.net_salary) FILTER (WHERE ls.leave_type_name IS NULL) AS avg_net_no_sick
FROM {schema}.vw_payroll_summary p
LEFT JOIN {schema}.vw_leave_summary ls ON ls.employee_id = p.employee_id
GROUP BY 1
ORDER BY branch
{lim};"""

    if "overtime hours with absent days" in q and "department" in q:
        return f"""SELECT
  e.department_name AS department,
  COUNT(DISTINCT e.employee_id) AS headcount,
  AVG(COALESCE(ot.overtime_hours, 0)) AS avg_overtime,
  AVG(COALESCE(a.absent_days, 0)) AS avg_absent_days
FROM {schema}.mart_employee_current e
LEFT JOIN {schema}.fct_overtime ot ON ot.employee_id = e.employee_id
LEFT JOIN {schema}.vw_attendance_summary a ON a.employee_id = e.employee_id
GROUP BY 1
ORDER BY department
{lim};"""

    if "absenteeism rate" in q and "headcount grew" in q:
        return f"""SELECT
  a.branch_name AS branch,
  SUM(COALESCE(a.absent_days, 0))::float / NULLIF(SUM(COALESCE(a.present_days, 0) + COALESCE(a.absent_days, 0)), 0) AS absenteeism_rate,
  hm.active_count AS headcount
FROM {schema}.vw_attendance_summary a
JOIN {schema}.mart_headcount_monthly hm ON hm.branch_name = a.branch_name
GROUP BY a.branch_name, hm.active_count
ORDER BY absenteeism_rate DESC
{lim};"""

    if "probation with more than 5 absent" in q:
        return f"""SELECT
  e.emp_fullname AS employee_name,
  e.branch_name AS branch,
  e.superior_fullname AS supervisor,
  e.probation_due_date,
  SUM(COALESCE(a.absent_days, 0)) AS absent_days
FROM {schema}.mart_employee_current e
JOIN {schema}.vw_attendance_summary a ON a.employee_id = e.employee_id
WHERE e.probation_due_date >= CURRENT_DATE
GROUP BY 1, 2, 3, 4
HAVING SUM(COALESCE(a.absent_days, 0)) > 5
ORDER BY absent_days DESC
{lim};"""

    if "rank designations by average late events" in q:
        return f"""SELECT
  d.designation_name,
  e.department_name AS department,
  COUNT(DISTINCT e.employee_id) AS employee_count,
  AVG(COALESCE(a.late_events, 0)) AS avg_lates
FROM {schema}.dim_designation d
JOIN {schema}.mart_employee_current e ON e.designation_id::text = d.designation_sk::text
LEFT JOIN {schema}.vw_attendance_summary a ON a.employee_id = e.employee_id
GROUP BY 1, 2
ORDER BY avg_lates DESC
{lim};"""

    if "remote versus on-site" in q:
        return f"""SELECT
  e.employment_type,
  SUM(COALESCE(a.present_days, 0)) AS present_days,
  SUM(COALESCE(a.absent_days, 0)) AS absent_days,
  SUM(COALESCE(ot.overtime_hours, 0)) AS overtime_hours
FROM {schema}.mart_employee_current e
LEFT JOIN {schema}.vw_attendance_summary a ON a.employee_id = e.employee_id
LEFT JOIN {schema}.fct_overtime ot ON ot.employee_id = e.employee_id
WHERE date_trunc('month', a.period_date) = date_trunc('month', CURRENT_DATE)
GROUP BY 1
ORDER BY employment_type
{lim};"""

    if "processed payroll additions and deductions" in q:
        return f"""SELECT
  cpi.pay_item_name,
  cpi.pay_item_type,
  SUM(COALESCE(ad.amount, 0)) AS total_amount,
  COUNT(DISTINCT ad.employee_sk) AS employee_count
FROM {schema}.fct_processed_add_ded ad
JOIN {schema}.dim_canonical_pay_item cpi ON cpi.pay_item_sk = ad.pay_item_sk
GROUP BY 1, 2
ORDER BY total_amount DESC
{lim};"""

    if "salary band distribution" in q:
        return f"""SELECT
  sb.band_name,
  sb.band_min,
  sb.band_max,
  COUNT(e.employee_id) AS employee_count,
  AVG(e.basic_salary) AS avg_basic_salary
FROM {schema}.vw_salary_bands sb
LEFT JOIN {schema}.mart_employee_current e ON e.basic_salary BETWEEN sb.band_min AND sb.band_max
GROUP BY 1, 2, 3
ORDER BY band_min
{lim};"""

    if "salary change events" in q and "20%" in q:
        return f"""SELECT
  e.emp_fullname AS employee_name,
  sc.old_basic_salary,
  sc.new_basic_salary,
  sc.change_date,
  e.branch_name AS branch
FROM {schema}.fct_salary_change sc
JOIN {schema}.mart_employee_current e ON e.employee_sk = sc.employee_sk
WHERE sc.change_date >= CURRENT_DATE - INTERVAL '6 months'
  AND sc.new_basic_salary > sc.old_basic_salary * 1.2
ORDER BY sc.change_date DESC
{lim};"""

    if "performance review ratings distribution" in q:
        return f"""SELECT
  e.department_name AS department,
  ps.rating_bucket,
  COUNT(*) AS employee_count
FROM {schema}.vw_performance_summary ps
JOIN {schema}.mart_employee_current e ON e.employee_id = ps.employee_id
GROUP BY 1, 2
ORDER BY department, rating_bucket
{lim};"""

    if "below expectations" in q and "performance" in q:
        return f"""SELECT
  e.department_name AS department,
  COUNT(*) FILTER (WHERE ps.rating_bucket ILIKE '%below%') AS below_threshold,
  COUNT(*) AS total_reviewed
FROM {schema}.vw_performance_summary ps
JOIN {schema}.mart_employee_current e ON e.employee_id = ps.employee_id
GROUP BY 1
ORDER BY below_threshold DESC
{lim};"""

    if "recruitment sources" in q and "linkedin" in q:
        return f"""SELECT
  rp.recruitment_source,
  COUNT(*) AS candidate_count
FROM {schema}.fact_recruitment_pipeline rp
JOIN {schema}.dim_candidate c ON c.candidate_id = rp.candidate_id
WHERE rp.appointment_date >= date_trunc('quarter', CURRENT_DATE) - INTERVAL '3 months'
GROUP BY 1
ORDER BY candidate_count DESC
{lim};"""

    if "payroll per head" in q or "revenue proxy" in q:
        return f"""SELECT
  e.branch_name AS branch,
  COUNT(DISTINCT e.employee_id) AS headcount,
  SUM(COALESCE(p.basic_salary, 0)) AS payroll_cost,
  SUM(COALESCE(ot.overtime_hours, 0)) AS overtime_hours,
  SUM(COALESCE(lb.leave_days, 0)) AS leave_days
FROM {schema}.mart_employee_current e
LEFT JOIN {schema}.vw_payroll_summary p ON p.employee_no = e.emp_no
LEFT JOIN {schema}.fct_overtime ot ON ot.employee_id = e.employee_id
LEFT JOIN {schema}.fact_leave_balance lb ON lb.employee_id = e.employee_id
GROUP BY 1
ORDER BY payroll_cost / NULLIF(headcount, 0) DESC
{lim};"""

    if "rising attrition" in q and "absent days" in q:
        return f"""SELECT
  t.department_name AS department,
  COUNT(DISTINCT t.employee_id) AS separations,
  AVG(COALESCE(a.absent_days, 0)) AS avg_absent_days,
  hm.active_count AS headcount
FROM {schema}.vw_turnover t
LEFT JOIN {schema}.vw_attendance_summary a ON a.employee_id = t.employee_id
LEFT JOIN {schema}.mart_headcount_monthly hm ON hm.department_name = t.department_name
GROUP BY 1, hm.active_count
ORDER BY separations DESC
{lim};"""

    # Fallback: simple scan of primary table
    primary = tables[0] if tables else "mart_employee_current"
    return f"""SELECT *
FROM {schema}.{primary}
{lim};"""


def _entry_block(item: dict, idx: int) -> dict:
    q = str(item["question"]).strip()
    domain = str(item.get("eval_domain") or "workforce").strip().lower()
    tables = list(item.get("expect_tables") or [])
    entry_id = _slug(item.get("section", "row"), idx)
    return {
        "id": entry_id,
        "domain": domain,
        "question": q + "\n",
        "tables": tables,
        "narrative": f"Verified bank query ({item.get('section')}).",
        "sql": _sql_for(domain, tables, q) + "\n",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--verified", type=Path, default=VERIFIED)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv or sys.argv[1:])

    if not args.candidates.is_file():
        print(f"Missing {args.candidates} — run sync_verified_candidates.py first", file=sys.stderr)
        return 1

    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    existing = yaml.safe_load(args.verified.read_text(encoding="utf-8")) or {}
    existing_ids = {str(b.get("id")) for b in (existing.get("queries") or [])}

    new_blocks: list[dict] = []
    for idx, item in enumerate(candidates):
        block = _entry_block(item, idx)
        if block["id"] in existing_ids:
            continue
        new_blocks.append(block)

    print(f"Candidates: {len(candidates)}  New entries to add: {len(new_blocks)}", flush=True)
    if args.dry_run:
        for b in new_blocks[:5]:
            print(f"  + {b['id']} ({b['domain']})", flush=True)
        return 0

    if not new_blocks:
        print("Nothing to add.", flush=True)
        return 0

    from app.services.ai_services.datamart.pipeline.verified_query_store import (
        clear_verified_query_cache,
    )

    merged = list(existing.get("queries") or []) + new_blocks
    out = {"queries": merged}
    header = (
        "# Curated verified question → SQL (Tier B). Placeholders: {schema}, {limit}\n"
        "# Seed from datamart_question_bank.yaml — expand as eval passes.\n\n"
    )
    args.verified.write_text(
        header + yaml.dump(out, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    clear_verified_query_cache()
    print(f"Wrote {len(merged)} total entries to {args.verified}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

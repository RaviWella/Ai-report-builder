from app.services.ai_services.datamart.domain_sql.catalog_report_sql import (
    looks_like_headcount_breakdown,
    try_build_headcount_breakdown_sql,
)
from app.services.ai_services.datamart.llm.llm_response import normalize_executable_sql, strip_ansi_escapes
from app.services.ai_services.datamart.pipeline.verified_query_store import (
    clear_verified_query_cache,
    retrieve_verified_sql,
)
from app.services.ai_services.datamart.sql.sql_fast_path import try_resolve_deterministic_sql
from app.services.ai_services.datamart.schema_broker import SchemaGrounding

HEADCOUNT_DEPT_Q = "What is our current headcount by department?"
HEADCOUNT_BRANCH_Q = "What is the current headcount by branch?"


def test_headcount_by_department_detected():
    assert looks_like_headcount_breakdown(HEADCOUNT_DEPT_Q)
    assert not looks_like_headcount_breakdown(
        "Which departments have the highest attrition rate?"
    )


def test_headcount_by_department_sql():
    sql = try_build_headcount_breakdown_sql(HEADCOUNT_DEPT_Q)
    assert sql
    assert "designation_department" in sql
    assert "GROUP BY" in sql
    assert "headcount" in sql.lower()


def test_verified_headcount_by_department_exact_match():
    clear_verified_query_cache()
    grounded = {"mart_employee_current", "dim_employee"}
    hit = retrieve_verified_sql(
        HEADCOUNT_DEPT_Q,
        grounded_tables=grounded,
        domain="mixed",
        min_score=6,
    )
    assert hit is not None
    assert hit[1] == "verified:headcount_by_department"


def test_ansi_stripped_from_sql():
    raw = "SELECT \x1b[4mthe\x1b[0m department FROM hr.mart_employee_current"
    cleaned = normalize_executable_sql(raw)
    assert cleaned
    assert "\x1b" not in cleaned
    assert "the department" in cleaned


def test_fast_path_headcount_breakdown():
    grounding = SchemaGrounding(
        columns_by_table={
            "hr.mart_employee_current": [
                "employee_sk",
                "designation_department",
                "emp_status",
            ],
        },
    )
    resolved = try_resolve_deterministic_sql(HEADCOUNT_DEPT_Q, grounding=grounding)
    assert resolved
    assert resolved[1] == "headcount_breakdown_template"


def test_headcount_by_branch_sql():
    sql = try_build_headcount_breakdown_sql(HEADCOUNT_BRANCH_Q)
    assert sql
    assert "location_name" in sql

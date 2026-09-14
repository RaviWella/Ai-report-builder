"""Fast output-column adequacy and pick-best-after-regen."""
from app.services.ai_services.datamart.sql.sql_answer_adequacy import (
    check_sql_output_columns,
    pick_better_sql_for_question,
    score_sql_output_columns,
)

WORKFORCE_Q = (
    "Generate a workforce report. Include employee name, employee ID, company, branch."
)

COUNT_SQL = (
    "SELECT COUNT(DISTINCT employee_id) AS employee_count FROM hr.dim_employee"
)

DETAIL_SQL = """
SELECT e.emp_fullname AS employee_name, e.emp_no AS employee_id,
       e.legal_entity AS company, e.location_name AS branch
FROM hr.mart_employee_current e
LIMIT 500
"""

PARTIAL_SQL = """
SELECT e.emp_fullname AS employee_name, e.emp_no AS employee_id
FROM hr.mart_employee_current e
LIMIT 500
"""


def test_count_sql_rejected():
    assert check_sql_output_columns(WORKFORCE_Q, COUNT_SQL) is not None


def test_detail_sql_accepted():
    assert check_sql_output_columns(WORKFORCE_Q, DETAIL_SQL) is None


def test_pick_better_prefers_more_columns():
    sa = score_sql_output_columns(WORKFORCE_Q, PARTIAL_SQL)
    sb = score_sql_output_columns(WORKFORCE_Q, DETAIL_SQL)
    assert sb > sa
    chosen, tag = pick_better_sql_for_question(WORKFORCE_Q, PARTIAL_SQL, DETAIL_SQL)
    assert tag == "regen_candidate"
    assert "branch" in chosen.lower()

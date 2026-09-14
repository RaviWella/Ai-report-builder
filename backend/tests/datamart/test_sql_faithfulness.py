"""SQL faithfulness checks."""
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.sql.sql_faithfulness import check_sql_faithfulness


def test_detail_report_with_count_only_warns():
    q = (
        "Generate a workforce report combining employee and organization data. "
        "Include employee name, company, branch, department"
    )
    sql = "SELECT COUNT(DISTINCT employee_id) AS employee_count FROM hr.dim_employee"
    gen = check_sql_faithfulness(
        question=q,
        sql=sql,
        grounding=SchemaGrounding(
            columns_by_table={"hr.dim_employee": ["employee_id"]},
            source="test",
        ),
        schema_links=[],
        binding_passed=True,
    )
    assert any("detailed report" in w.lower() for w in gen.warnings)


def test_top_n_limit_mismatch_warns():
    gen = check_sql_faithfulness(
        question="Show top 10 employees by salary",
        sql="SELECT employee_id FROM hr.dim_employee ORDER BY basic_salary DESC LIMIT 50",
        grounding=SchemaGrounding(
            columns_by_table={"hr.dim_employee": ["employee_id", "basic_salary"]},
            source="test",
        ),
        schema_links=[],
        binding_passed=True,
    )
    assert any("top 10" in w and "LIMIT 50" in w for w in gen.warnings)

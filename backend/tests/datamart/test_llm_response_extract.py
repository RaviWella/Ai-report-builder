"""LLM response SQL extraction."""
from app.services.ai_services.datamart.llm.llm_response import extract_sql, normalize_executable_sql
from app.services.ai_services.datamart.sql.sql_generation import finish_generate_sql_trace
from app.services.ai_services.datamart.pipeline_trace import PipelineStepStatus, PipelineTracer


def test_extract_sql_from_sql_section_without_fence():
    text = """NARRATIVE:
Here is the report.

SQL:
SELECT e.emp_fullname, e.emp_no
FROM hr.mart_employee_current e
LIMIT 100

POST_PROCESS:
```json
[]
```
"""
    sql = normalize_executable_sql(extract_sql(text))
    assert sql is not None
    assert "mart_employee_current" in sql


def test_finish_generate_sql_trace_after_template():
    trace = PipelineTracer.begin()
    trace.start("generate_sql")
    finish_generate_sql_trace(trace, sql="SELECT 1", source="workforce_template")
    built = trace.build()
    gen = next(s for s in built.steps if s.id == "generate_sql")
    assert gen.status == PipelineStepStatus.COMPLETED
    assert "catalog template" in (gen.detail or "").lower()

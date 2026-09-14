"""Query Engine safety + correctness tests (Phase 1 done-when criteria).

These lock in the non-negotiable rules: no raw SQL, parameterized values, only
declared joins, refs resolved through the semantic layer, and the row-limit guard.
"""

from __future__ import annotations

import pytest
from sqlalchemy.dialects import postgresql

from app.domain.enums import FieldRole, FieldType
from app.domain.report_spec import DataSpec
from app.domain.semantic import Entity, PhysicalColumn, SemanticCatalog, SemanticField
from app.query_engine import guards
from app.query_engine.compiler import compile_query
from app.services.semantic_seed import build_seed_catalog


@pytest.fixture
def catalog():
    return build_seed_catalog("tenant_test", 1)


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def test_grouped_report_compiles_with_joins_and_params(catalog):
    spec = DataSpec.model_validate(
        {
            "entity": "employee",
            "fields": [{"ref": "employee.department", "label": "Department"}],
            "filters": [
                {"ref": "employee.status", "op": "eq", "value": "active"},
                {"ref": "employee.join_date", "op": "between", "param": "join_range"},
            ],
            "group_by": ["employee.department"],
            "aggregations": [{"ref": "payroll.basic", "fn": "sum", "label": "Total Basic"}],
            "sort": [{"ref": "employee.department", "dir": "asc"}],
        }
    )
    compiled = compile_query(spec, catalog, {"join_range": ["2024-01-01", "2024-12-31"]}, preview=True)
    sql = _sql(compiled.statement)
    guards.assert_select_only(sql)

    # department is denormalised on the employee mart -> only payroll needs a join.
    assert "JOIN mart.mart_payroll_summary" in sql
    assert "GROUP BY mart.mart_employee.department" in sql
    # Values are bound, never inlined.
    assert "'active'" not in sql
    assert "%(employment_status_1)s" in sql
    # Exactly one base FROM table (no phantom cartesian froms).
    assert sql.count("FROM mart.mart_employee") == 1
    # Row-limit guard always present.
    assert "LIMIT" in sql


def test_lookup_calculated_field_compiles_to_case(catalog):
    # A lookup/mapping derived field -> a safe CASE over the source column, labels bound.
    spec = DataSpec.model_validate(
        {
            "entity": "employee",
            "fields": [{"ref": "employee.emp_no"}, {"ref": "calc.grade_band"}],
            "calculated_fields": [
                {"name": "grade_band", "label": "Grade Band",
                 "lookup": {"on": "employee.grade",
                            "map": {"A": "Senior", "B": "Mid"}, "default": "Other"}},
            ],
        }
    )
    sql = _sql(compile_query(spec, catalog, {}).statement)
    assert "CASE WHEN" in sql
    assert "mart.mart_employee.grade" in sql          # maps on the real column
    assert "'Senior'" not in sql and "'Other'" not in sql  # labels are bound, not inlined


def test_calculated_field_exactly_one_kind():
    # expression + lookup together is rejected (governed: exactly one kind).
    with pytest.raises(ValueError):
        DataSpec.model_validate(
            {"entity": "employee", "fields": [{"ref": "calc.x"}],
             "calculated_fields": [{"name": "x", "label": "X",
                                    "expression": "payroll.net",
                                    "lookup": {"on": "employee.grade", "map": {"A": "Senior"}}}]}
        )


def test_calculated_field_pulls_joined_table(catalog):
    spec = DataSpec.model_validate(
        {
            "entity": "employee",
            "fields": [{"ref": "employee.full_name"}, {"ref": "calc.net"}],
            "calculated_fields": [
                {"name": "net", "label": "Net", "expression": "payroll.gross - payroll.deductions"}
            ],
        }
    )
    sql = _sql(compile_query(spec, catalog, {}).statement)
    assert "gross_salary - mart.mart_payroll_summary.total_deductions" in sql


def test_banding_field_compiles_to_case(catalog):
    spec = DataSpec.model_validate(
        {
            "entity": "employee",
            "fields": [{"ref": "employee.full_name"}, {"ref": "calc.age_band"}],
            "calculated_fields": [
                {
                    "name": "age_band",
                    "label": "Age Group",
                    "cases": [
                        {"ref": "employee.age", "op": "lt", "value": 20, "label": "Under 20"},
                        {"ref": "employee.age", "op": "lt", "value": 30, "label": "20-29"},
                    ],
                    "else_label": "30+",
                }
            ],
        }
    )
    sql = _sql(compile_query(spec, catalog, {}).statement)
    assert "CASE WHEN" in sql
    # branch labels and thresholds are bound params, never inlined
    assert "'Under 20'" not in sql and "'30+'" not in sql
    assert "< %(age_years_1)s" in sql


def test_calc_requires_exactly_one_kind():
    from pydantic import ValidationError

    # both expression AND cases -> invalid
    with pytest.raises(ValidationError):
        DataSpec.model_validate(
            {
                "entity": "employee",
                "fields": [{"ref": "calc.x"}],
                "calculated_fields": [
                    {"name": "x", "label": "x", "expression": "employee.age + 1",
                     "cases": [{"ref": "employee.age", "op": "lt", "value": 1, "label": "a"}]}
                ],
            }
        )


def test_unknown_ref_is_rejected(catalog):
    spec = DataSpec.model_validate({"entity": "employee", "fields": [{"ref": "employee.secret"}]})
    with pytest.raises(guards.GuardError):
        compile_query(spec, catalog, {})


def test_calc_injection_is_rejected(catalog):
    spec = DataSpec.model_validate(
        {
            "entity": "employee",
            "fields": [{"ref": "calc.x"}],
            "calculated_fields": [
                {"name": "x", "label": "x", "expression": "payroll.gross; DROP TABLE x"}
            ],
        }
    )
    with pytest.raises(guards.GuardError):
        compile_query(spec, catalog, {})


@pytest.mark.parametrize(
    "expr",
    [
        "abs(payroll.gross)",          # function call
        "payroll.gross ** 2",          # power operator
        "payroll.gross.real",          # attribute access
        "__import__('os')",            # dunder call
        "payroll.gross % 2",           # modulo (not whitelisted)
    ],
)
def test_calc_ast_rejects_non_arithmetic(catalog, expr):
    """WS-5: the calculated-field evaluator walks an AST with a strict whitelist
    (numbers, bound names, + - * / and unary +/-). Everything else is rejected —
    no eval()/exec()."""
    spec = DataSpec.model_validate(
        {"entity": "employee", "fields": [{"ref": "calc.x"}],
         "calculated_fields": [{"name": "x", "label": "x", "expression": expr}]}
    )
    with pytest.raises(guards.GuardError):
        compile_query(spec, catalog, {})


def test_calc_ast_allows_arithmetic_and_unary(catalog):
    """A legitimate arithmetic expression (incl. unary minus + parentheses) compiles."""
    spec = DataSpec.model_validate(
        {"entity": "employee", "fields": [{"ref": "calc.x"}],
         "calculated_fields": [
             {"name": "x", "label": "x", "expression": "-(payroll.gross - payroll.deductions) / 2 + 1"}
         ]}
    )
    sql = _sql(compile_query(spec, catalog, {}).statement)
    assert "DROP" not in sql.upper()


def test_no_eval_or_exec_in_query_engine():
    """WS-5 invariant: the query engine never *calls* eval/exec (AST-checked, so a
    mention in a comment/string doesn't count)."""
    import ast as _ast
    import pathlib

    engine_dir = pathlib.Path(__file__).resolve().parents[1] / "app" / "query_engine"
    for path in engine_dir.glob("*.py"):
        tree = _ast.parse(path.read_text())
        calls = [
            n.func.id
            for n in _ast.walk(tree)
            if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Name)
        ]
        assert "eval" not in calls and "exec" not in calls, f"{path.name} calls eval/exec"


def test_filter_requires_exactly_one_value_source():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        DataSpec.model_validate(
            {
                "entity": "employee",
                "fields": [{"ref": "employee.emp_no"}],
                "filters": [{"ref": "employee.status", "op": "eq", "value": "a", "param": "p"}],
            }
        )


def test_preview_limit_capped(catalog):
    spec = DataSpec.model_validate({"entity": "employee", "fields": [{"ref": "employee.emp_no"}]})
    sql = _sql(compile_query(spec, catalog, {}, preview=True).statement)
    assert "LIMIT" in sql


def test_assert_select_only_rejects_writes_and_ddl():
    """The datamart is strictly read-only: only SELECT + calculations, never any
    INSERT/UPDATE/DELETE/DDL."""
    for bad in [
        "INSERT INTO hr.t VALUES (1)",
        "UPDATE hr.t SET x = 1",
        "DELETE FROM hr.t",
        "DROP TABLE hr.t",
        "TRUNCATE hr.t",
        "CREATE TABLE x (a int)",
        "ALTER TABLE hr.t ADD COLUMN c int",
        "GRANT ALL ON hr.t TO public",
        "SELECT 1; DROP TABLE hr.t",  # statement chaining
        "SELECT * INTO hr.copy FROM hr.t",  # SELECT INTO creates a table
        "MERGE INTO hr.t USING s ON (1=1)",
        "COPY hr.t FROM '/etc/passwd'",
    ]:
        with pytest.raises(guards.GuardError):
            guards.assert_select_only(bad)


def test_assert_select_only_allows_legit_selects():
    # a quoted label containing a keyword-like word must NOT trip the guard
    guards.assert_select_only('SELECT a AS "Promoted Into Senior" FROM hr.t')
    guards.assert_select_only("WITH x AS (SELECT 1) SELECT * FROM x")
    guards.assert_select_only(
        'SELECT CASE WHEN age < 20 THEN \'Under 20\' ELSE \'20+\' END AS "Age Group" FROM hr.t'
    )


def test_two_period_marts_align_on_period_not_just_employee(catalog):
    """Regression: joining two period-grained marts (payroll + attendance) must
    match on (year, month) as well as employee, or every employee's periods
    cross-multiply and rows duplicate (the Horizontal Pay Sheet bug)."""
    spec = DataSpec.model_validate(
        {
            "entity": "employee",
            "fields": [
                {"ref": "employee.full_name"},
                {"ref": "payroll.basic"},
                {"ref": "attendance.ot_hours"},
            ],
        }
    )
    sql = _sql(compile_query(spec, catalog, {}).statement)
    guards.assert_select_only(sql)

    # Both period marts are joined…
    assert "JOIN mart.mart_payroll_summary" in sql
    assert "JOIN mart.mart_attendance_monthly" in sql
    # …and the second one aligns to the first on BOTH year and month (either
    # ordering of the equality is fine; the anchor is whichever joins first).
    assert (
        "mart_payroll_summary.year_no = mart.mart_attendance_monthly.year_no" in sql
        or "mart_attendance_monthly.year_no = mart.mart_payroll_summary.year_no" in sql
    ), sql
    assert (
        "mart_payroll_summary.month_no = mart.mart_attendance_monthly.month_no" in sql
        or "mart_attendance_monthly.month_no = mart.mart_payroll_summary.month_no" in sql
    ), sql
    # No phantom cartesian FROMs.
    assert sql.count("FROM mart.mart_employee") == 1


def test_single_period_mart_has_no_period_alignment(catalog):
    """One period mart joined to employee needs no period alignment (there's
    nothing to align it to); the employee-key join is correct on its own."""
    spec = DataSpec.model_validate(
        {
            "entity": "employee",
            "fields": [{"ref": "employee.full_name"}, {"ref": "payroll.basic"}],
        }
    )
    sql = _sql(compile_query(spec, catalog, {}).statement)
    assert "JOIN mart.mart_payroll_summary" in sql
    # No second period mart, so no year/month equality is introduced.
    assert "year_no =" not in sql and "month_no =" not in sql


def test_metadata_for_ai_has_no_physical_names(catalog):
    meta = catalog.metadata_for_ai()
    blob = str(meta)
    # The AI projection must not leak physical table/column names.
    assert "mart_employee" not in blob
    assert "mart_payroll_summary" not in blob
    assert all("ref" in m and "label" in m for m in meta)


def test_json_key_field_compiles_to_arrow_operator():
    """A field bound via PhysicalColumn.json_key (a discovered key inside a JSON
    "extra fields" blob — see semantic_autobuild._json_key_fields) must compile
    to `column ->> key`, the key bound as a parameter — never inlined into SQL,
    matching every other value in this engine."""
    field = SemanticField(
        ref="employment.extra_fields__probation_notes", label="Probation Notes",
        type=FieldType.STRING, role=FieldRole.DIMENSION,
        physical=PhysicalColumn(
            table="mart_employment", column="extra_fields",
            schema_name="mart", json_key="probation_notes",
        ),
    )
    entity = Entity(
        name="Employment", key="employment", base_schema="mart",
        base_table="mart_employment", primary_key="employment_sk", fields=[field],
    )
    cat = SemanticCatalog(tenant_id="t", version=1, entities=[entity])
    spec = DataSpec.model_validate({
        "entity": "employment",
        "fields": [{"ref": "employment.extra_fields__probation_notes", "label": "Probation Notes"}],
    })

    sql = _sql(compile_query(spec, cat, {}, preview=True).statement)
    guards.assert_select_only(sql)
    assert "->>" in sql
    assert "'probation_notes'" not in sql  # the key is bound, not inlined

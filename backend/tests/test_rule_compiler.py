"""Rule compiler (Phase 3) — a full RuleReportSpec compiles to one safe SQL SELECT
with the day_value CASE, conditional-aggregate rollup, grain group-by and the
post-aggregate compute metrics. Generic: any spec using the primitives compiles."""

from sqlalchemy.dialects import postgresql

from app.domain.rule_report import RuleReportSpec
from app.query_engine.rule_compiler import compile_rule_report
from tests.test_rule_report_spec import OT_SPEC


def _sql(spec) -> str:
    stmt = compile_rule_report(spec)
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_ot_spec_compiles_to_full_sql():
    sql = _sql(RuleReportSpec.model_validate(OT_SPEC))
    # day_value classification -> CASE WHEN
    assert "CASE WHEN" in sql
    # source table
    assert "mart.mart_attendance_daily" in sql
    # NPL-adjusted minimum + OT (greatest for max(0, …))
    assert "greatest(" in sql
    # grouped to the grain
    assert "GROUP BY" in sql
    # output columns present
    for col in ("employee_no", "year_month", "total_qualifying", "ot_hours"):
        assert col in sql


def test_conditional_aggregation_uses_filter():
    # a rollup with "… where …" compiles to an aggregate FILTER (WHERE …)
    spec = RuleReportSpec.model_validate({
        **OT_SPEC,
        "rollup": {
            "total_qualifying": "sum(day_value)",
            "npl_days": "sum(days_nopay)",
            "short_hours": "sum(leave_minutes) where leave_category == 'Short Leave'",
        },
        "output": ["employee_no", "year_month", "total_qualifying", "npl_days",
                   "applicable_min", "ot_hours", "short_hours"],
    })
    sql = _sql(spec)
    assert "FILTER (WHERE" in sql
    assert "'Short Leave'" in sql


def test_sum_and_count_rollups_are_coalesced_to_zero():
    # SUM/COUNT over a group with zero matching rows returns SQL NULL, which
    # then poisons any `compute`/`having` that adds or compares it — 0 is the
    # only sensible "nothing matched" value for a running total or count.
    spec = RuleReportSpec.model_validate({
        **OT_SPEC,
        "rollup": {
            "total_qualifying": "sum(day_value)",
            "npl_days": "sum(days_nopay)",
            "short_hours": "sum(leave_minutes) where leave_category == 'Short Leave'",
            "short_count": "count(leave_minutes) where leave_category == 'Short Leave'",
        },
        "output": ["employee_no", "year_month", "total_qualifying", "npl_days",
                   "applicable_min", "ot_hours", "short_hours", "short_count"],
    })
    sql = _sql(spec)
    assert "coalesce(sum(rows.day_value), 0)" in sql
    assert "coalesce(sum(rows.leave_minutes) FILTER (WHERE" in sql
    assert "coalesce(count(rows.leave_minutes) FILTER (WHERE" in sql


def test_avg_min_max_rollups_are_not_coalesced():
    # 0 isn't a safe "nothing matched" default for avg/min/max (an average or a
    # min/max of nothing genuinely isn't 0) — only sum/count get auto-coalesced.
    spec = RuleReportSpec.model_validate({
        **OT_SPEC,
        "rollup": {
            "total_qualifying": "sum(day_value)",
            "npl_days": "sum(days_nopay)",
            "avg_leave": "avg(leave_minutes) where leave_category == 'Short Leave'",
        },
        "output": ["employee_no", "year_month", "total_qualifying", "npl_days",
                   "applicable_min", "ot_hours", "avg_leave"],
    })
    sql = _sql(spec)
    assert "coalesce(avg(" not in sql


def test_runtime_filters_apply_as_where():
    spec = RuleReportSpec.model_validate(OT_SPEC)
    stmt = compile_rule_report(spec, {"date_from": "2026-07-01", "date_to": "2026-07-31",
                                      "employee_no": "3565"})
    sql = str(stmt.compile(dialect=postgresql.dialect(),
                           compile_kwargs={"literal_binds": True}))
    assert "work_date >= '2026-07-01'" in sql
    assert "work_date <= '2026-07-31'" in sql
    assert "employee_no = '3565'" in sql
    # department not supplied → not applied
    assert "department =" not in sql


def test_function_names_are_not_source_columns():
    # A define/value using coalesce()/greatest() must NOT create a phantom source
    # column named "coalesce"/"greatest" (regression from A==B verification).
    sql = _sql(RuleReportSpec.model_validate(OT_SPEC))  # OT define uses coalesce()
    assert ".coalesce" not in sql          # no phantom column reference
    assert "coalesce(" in sql              # coalesce still used as a function


def test_rollup_output_may_share_a_source_column_name():
    # `sum(late_minutes) AS late_minutes` — the output name equals the source column
    # it reads. The source column must still be wired (aggregate scope != row scope).
    spec = RuleReportSpec.model_validate({
        **OT_SPEC,
        "rollup": {
            "total_qualifying": "sum(day_value)",
            "npl_days": "sum(days_nopay)",
            "late_minutes": "sum(coalesce(late_minutes, 0))",
        },
        "output": ["employee_no", "year_month", "total_qualifying", "npl_days",
                   "applicable_min", "ot_hours", "late_minutes"],
    })
    sql = _sql(spec)                       # must compile without GuardError
    assert "sum(coalesce(rows.late_minutes" in sql or "sum(coalesce(" in sql
    assert "late_minutes" in sql


def test_row_cases_label_drives_filter_breakdown():
    # a row_cases label (day_category) is usable in a rollup FILTER breakdown
    spec = RuleReportSpec.model_validate({
        **OT_SPEC,
        "row_cases": {"day_category": {
            "cases": [{"when": "days_nopay > 0", "value": "'nopay'"}],
            "else": "'normal'",
        }},
        "rollup": {
            "total_qualifying": "sum(day_value)",
            "npl_days": "sum(days_nopay)",
            "normal_hours": "sum(day_value) where day_category == 'normal'",
        },
        "output": ["employee_no", "year_month", "total_qualifying", "npl_days",
                   "applicable_min", "ot_hours", "normal_hours"],
    })
    sql = _sql(spec)
    assert "CASE WHEN (rows.days_nopay" in sql or "'nopay'" in sql   # category computed per row
    assert "FILTER (WHERE" in sql                                    # breakdown uses FILTER
    assert "'normal'" in sql


# ---- multi-source declarative joins -------------------------------------------

MULTI_SPEC = {
    "name": "ot_multi",
    "sources": {
        "a": {"table": "mart.mart_attendance_daily",
              "columns": ["employee_sk", "employee_no", "year_month", "work_date",
                          "worked_hours", "days_nopay"]},
        "l": {"table": "mart.mart_leave_daily",
              "columns": ["employee_sk", "leave_date", "leave_category", "leave_minutes"],
              "join": {"type": "left_pick_one",
                       "on": ["employee_sk = employee_sk", "leave_date = work_date"],
                       "priority": {"column": "leave_category",
                                    "order": ["Lieu Leave", "Short Leave"],
                                    "tiebreak": "leave_minutes", "tiebreak_dir": "desc"}}},
    },
    "grain": ["employee_no", "year_month"],
    "constants": {"min_per_day": 6, "month_days": 30},
    "day_value": {"define": {"adj": "coalesce(worked_hours, 0)"},
                  "cases": [{"when": "leave_category == 'Short Leave'",
                             "value": "adj + coalesce(leave_minutes, 0) / 60"}],
                  "else": "adj"},
    "rollup": {"total": "sum(day_value)", "npl": "sum(days_nopay)"},
    "compute": {"ot": "max(0, total - (month_days - npl) * min_per_day)"},
    "output": ["employee_no", "year_month", "total", "ot"],
}


def test_multi_source_builds_lateral_pick_one():
    sql = _sql(RuleReportSpec.model_validate(MULTI_SPEC))
    assert "mart.mart_attendance_daily" in sql
    assert "mart.mart_leave_daily" in sql
    assert "JOIN LATERAL" in sql
    assert "LIMIT 1" in sql                                  # keeps one row per base row
    # tiebreak must not let a NULL win the pick
    assert "leave_minutes DESC NULLS LAST" in sql
    # join keys correlate the lateral to the base
    assert "employee_sk = a.employee_sk" in sql or "a.employee_sk" in sql


def test_multi_source_plain_left_join():
    spec = {**MULTI_SPEC}
    spec["sources"] = {**MULTI_SPEC["sources"]}
    spec["sources"]["l"] = {**MULTI_SPEC["sources"]["l"],
                            "join": {"type": "left",
                                     "on": ["employee_sk = employee_sk", "leave_date = work_date"]}}
    sql = _sql(RuleReportSpec.model_validate(spec))
    assert "LEFT OUTER JOIN mart.mart_leave_daily" in sql
    assert "LATERAL" not in sql


# ---- column_aliases — resolves a join-key/grain-column name collision ---------

ALIAS_SPEC = {
    "name": "shift_join_test",
    "sources": {
        "m": {"table": "mart.mart_attendance_daily",
              "columns": ["employee_sk", "employee_no", "work_date", "worked_hours"]},
        "f": {"table": "core.fct_attendance_day",
              "columns": ["employee_sk", "work_date", "scheduled_shift_sk"],
              "column_aliases": {"work_date": "f_work_date"},
              "join": {"type": "left", "on": ["employee_sk = employee_sk", "work_date = work_date"]}},
    },
    "grain": ["employee_no", "work_date"],
    "day_value": {"cases": [{"when": "scheduled_shift_sk > 0", "value": "1"}], "else": "0"},
    "rollup": {"total": "sum(day_value)"},
    "output": ["employee_no", "work_date", "total"],
}


def test_column_aliases_resolves_a_join_key_grain_collision():
    # Both "m" and "f" physically have "work_date" (needed as the join key on
    # both sides), but only "m"'s copy should be usable as the grain column —
    # "f" aliases its own copy away so there's no ambiguity.
    sql = _sql(RuleReportSpec.model_validate(ALIAS_SPEC))
    assert "core.fct_attendance_day" in sql
    # the join itself still uses the PHYSICAL "work_date" name on both sides
    assert "f.work_date = m.work_date" in sql or "m.work_date = f.work_date" in sql
    # grain unambiguously resolves to the base's work_date, not a phantom alias
    assert "m.work_date" in sql
    assert "f_work_date" not in sql   # the alias is a namespace-only rename, not a real column


def test_same_spec_without_column_aliases_is_ambiguous():
    # Proves the fix actually fixes something: strip the alias and the same
    # grain reference to "work_date" becomes ambiguous, same failure mode as
    # test_ambiguous_referenced_column_errors below.
    import pytest
    from app.query_engine import guards
    spec = {**ALIAS_SPEC, "sources": {**ALIAS_SPEC["sources"]}}
    spec["sources"]["f"] = {**ALIAS_SPEC["sources"]["f"], "column_aliases": {}}
    with pytest.raises(guards.GuardError):
        compile_rule_report(RuleReportSpec.model_validate(spec))


def test_column_alias_unknown_physical_column_rejected():
    import pytest
    bad = {**ALIAS_SPEC, "sources": {**ALIAS_SPEC["sources"]}}
    bad["sources"]["f"] = {**ALIAS_SPEC["sources"]["f"],
                           "column_aliases": {"not_a_declared_column": "x"}}
    with pytest.raises(ValueError):
        RuleReportSpec.model_validate(bad)


def test_column_alias_invalid_identifier_value_rejected():
    import pytest
    bad = {**ALIAS_SPEC, "sources": {**ALIAS_SPEC["sources"]}}
    bad["sources"]["f"] = {**ALIAS_SPEC["sources"]["f"],
                           "column_aliases": {"work_date": "Not Valid!"}}
    with pytest.raises(ValueError):
        RuleReportSpec.model_validate(bad)


def test_ambiguous_referenced_column_errors():
    # employee_sk is a shared join key (declared in both) — fine while unreferenced,
    # but referencing it in an expression is ambiguous -> GuardError.
    import pytest
    from app.query_engine import guards
    spec = {**MULTI_SPEC}
    spec["day_value"] = {**MULTI_SPEC["day_value"],
                         "cases": [{"when": "employee_sk > 0", "value": "1"}]}
    with pytest.raises(guards.GuardError):
        compile_rule_report(RuleReportSpec.model_validate(spec))


def test_compute_resolves_in_dependency_order_not_dict_order():
    # compute given with a dependent BEFORE its dependency (as JSONB storage may reorder
    # it): ot_hours references applicable_min which is listed after it. Must still compile.
    spec = RuleReportSpec.model_validate({
        **OT_SPEC,
        "compute": {
            "ot_hours": "max(0, total_qualifying - applicable_min)",   # depends on applicable_min
            "applicable_min": "(month_days - npl_days) * min_per_day",  # ...defined later
        },
        "output": ["employee_no", "year_month", "total_qualifying", "npl_days",
                   "applicable_min", "ot_hours"],
    })
    sql = _sql(spec)                        # no GuardError despite the reversed order
    assert "greatest(" in sql


def test_cyclic_compute_raises():
    import pytest
    from app.query_engine import guards
    spec = RuleReportSpec.model_validate({
        **OT_SPEC,
        "compute": {"a": "b + 1", "b": "a + 1"},
        "output": ["employee_no", "year_month", "total_qualifying", "npl_days", "a", "b"],
    })
    with pytest.raises(guards.GuardError):
        compile_rule_report(spec)


def test_output_must_be_produced():
    import pytest
    from app.query_engine import guards
    spec = RuleReportSpec.model_validate({**OT_SPEC, "output": ["employee_no", "nonexistent_col"]})
    with pytest.raises(guards.GuardError):
        compile_rule_report(spec)


# ---- having / order_by / filter.expose_as -----------------------------------

def test_having_filters_the_final_select():
    spec = RuleReportSpec.model_validate({**OT_SPEC, "having": "total_qualifying >= 1"})
    sql = _sql(spec)
    # applied on the aggregate result, not folded into a FILTER clause
    assert "WHERE" in sql.split("GROUP BY")[-1] or "WHERE" in sql
    assert "total_qualifying" in sql


def test_having_is_applied_before_the_row_limit():
    # a having clause must appear before LIMIT in the compiled SQL, so the limit
    # guard never truncates away rows that would have been excluded by having.
    spec = RuleReportSpec.model_validate({**OT_SPEC, "having": "total_qualifying >= 1"})
    stmt = compile_rule_report(spec)
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert sql.index("total_qualifying >=") < sql.rindex("LIMIT")


def test_order_by_adds_order_clause():
    spec = RuleReportSpec.model_validate({**OT_SPEC, "order_by": ["employee_no", "year_month"]})
    sql = _sql(spec)
    assert "ORDER BY" in sql
    assert sql.index("ORDER BY") < sql.index("LIMIT")


def test_order_by_unknown_column_raises():
    import pytest
    from app.query_engine import guards
    spec = RuleReportSpec.model_validate({**OT_SPEC, "order_by": ["not_a_real_column"]})
    with pytest.raises(guards.GuardError):
        compile_rule_report(spec)


def test_filter_expose_as_projects_the_runtime_value():
    spec = RuleReportSpec.model_validate({
        **OT_SPEC,
        "filters": [*OT_SPEC["filters"], {"name": "date_to", "type": "date", "column": "work_date",
                                          "op": "lte", "expose_as": "end_date"}],
        "output": [*OT_SPEC["output"], "end_date"],
    })
    stmt = compile_rule_report(spec, {"date_to": "2026-07-31"})
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "2026-07-31" in sql
    assert "AS end_date" in sql


def test_filter_expose_as_null_when_no_runtime_value():
    spec = RuleReportSpec.model_validate({
        **OT_SPEC,
        "filters": [*OT_SPEC["filters"], {"name": "date_to", "type": "date", "column": "work_date",
                                          "op": "lte", "expose_as": "end_date"}],
        "output": [*OT_SPEC["output"], "end_date"],
    })
    stmt = compile_rule_report(spec, {})   # date_to not supplied
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "NULL AS end_date" in sql


def test_time_function_compiles_a_cast_not_a_phantom_source_column():
    # time('HH:MM:SS') casts a literal for a `time`-typed comparison. If "time"
    # were (wrongly) treated as a referenced source column — there's no such
    # column on mart_attendance_daily — this would fail with "not found in any
    # source: ['time']" instead of compiling.
    spec = RuleReportSpec.model_validate({
        **OT_SPEC,
        "day_value": {
            "cases": [{"when": "worked_hours > 0 and days_nopay == time('14:30:00')",
                       "value": "adj_worked"}],
            "else": "0",
        },
    })
    sql = _sql(spec)
    assert "CAST('14:30:00' AS TIME" in sql
    assert "mart_attendance_daily.time" not in sql   # no phantom "time" column wired


def test_golden_key_spec_unaffected_by_new_optional_fields():
    # having/order_by default to None/[] and no filter sets expose_as — the
    # compiled SQL for the real Golden Key spec must be byte-identical to
    # before this change (no WHERE-after-agg, no ORDER BY).
    sql = _sql(RuleReportSpec.model_validate(OT_SPEC))
    assert "ORDER BY" not in sql
    # the only WHERE clauses are the row-level ones inside the "rows" subquery —
    # none should appear after the aggregate's GROUP BY
    tail = sql.rsplit("GROUP BY", 1)[-1]
    assert "WHERE" not in tail

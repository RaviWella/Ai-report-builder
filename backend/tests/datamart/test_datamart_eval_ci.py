"""CI wrapper for offline datamart eval (mocked warehouse grounding for broker cases)."""
from app.services.ai_services.datamart.schema_broker import SchemaGrounding


def _rich_test_grounding(**_kwargs) -> SchemaGrounding:
    """Tables needed for leave / attrition / attendance / workforce broker golden cases."""
    return SchemaGrounding(
        columns_by_table={
            "public_mint_audit.dim_employee": ["employee_id", "full_name"],
            "public_mint_audit.fact_payroll_detail": ["employee_id", "basic_salary"],
            "public_mint_audit.fact_leave_transaction": ["employee_id", "leave_type_id"],
            "public_mint_audit.dim_leave_type": ["leave_type_id", "leave_type_name"],
            "public_mint_audit.vw_turnover": ["department", "separations"],
            "public_mint_audit.vw_headcount": ["department", "headcount"],
            "public_mint_audit.vw_attendance_summary": ["period_label", "present_days"],
            "public_mint_audit.mart_employee_current": ["emp_no", "emp_fullname"],
        },
        source="test",
    )


def test_golden_report_eval_without_mocks():
    """Golden SQL cases do not need warehouse or LLM."""
    from tools.run_datamart_eval import eval_golden_reports

    results = eval_golden_reports()
    assert results, "expected golden report cases"
    failed = [r for r in results if not r["ok"]]
    assert not failed, failed


def test_run_link_eval_exits_zero():
    from tools.run_link_eval import main

    assert main([]) == 0


def test_run_pipeline_eval_exits_zero():
    from tools.run_pipeline_eval import main

    assert main([]) == 0


def test_run_question_bank_sql_fit_exits_zero():
    from tools.run_question_bank_sql_fit import main

    assert main([]) == 0


def test_question_bank_full_sql_offline_resolve_exits_zero():
    """Tier A/B SQL for all 66 bank questions (no warehouse)."""
    from tools.run_question_bank_full_sql import main

    assert (
        main(
            [
                "--export-json",
                "tools/question_bank_reports/all_66_offline_ci.json",
            ]
        )
        == 0
    )


def test_run_datamart_eval_exits_zero(monkeypatch):
    def _fake_retrieval(**_kwargs):
        from app.services.ai_services.datamart.validation.validation_models import (
            RetrievalValidation,
            ValidationStatus,
        )

        return RetrievalValidation(
            status=ValidationStatus.SUFFICIENT,
            tables_selected=["dim_employee"],
        )

    monkeypatch.setattr(
        "tools.run_datamart_eval.build_schema_grounding",
        _rich_test_grounding,
    )
    monkeypatch.setattr(
        "tools.run_datamart_eval.validate_retrieval",
        _fake_retrieval,
    )
    from tools.run_datamart_eval import main

    main()

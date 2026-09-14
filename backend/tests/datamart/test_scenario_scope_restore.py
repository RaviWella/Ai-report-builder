"""Restore untouched extra scenarios after targeted modify."""
from app.services.ai_services.datamart.models import DatamartResponse, DatamartResultBlock
from app.services.ai_services.datamart.scenario.scenario_scope import apply_target_scope_to_result


def _noop_execute(_sql: str, _pp):  # noqa: ANN001
    class _R:
        columns = []
        rows = []
        row_count = 0
        error = None
        raw_columns = None
        raw_rows = None
        raw_row_count = None

    return _R()


def test_apply_target_scope_restores_untouched_extra_blocks():
    prior_extras = [
        {
            "block_id": "block-a",
            "title": "Leave",
            "sql_script": "SELECT 1 AS a",
        },
        {
            "block_id": "block-b",
            "title": "Payroll",
            "sql_script": "SELECT 2 AS b",
        },
    ]
    result = DatamartResponse(
        question="change payroll",
        narrative="ok",
        sql="SELECT 2 AS b",
        extra_result_blocks=[
            DatamartResultBlock(
                block_id="block-b",
                title="Payroll updated",
                sql="SELECT 2 AS b",
                columns=["b"],
                rows=[[2]],
                row_count=1,
            ),
        ],
    )
    out = apply_target_scope_to_result(
        result,
        targets={"block-b"},
        prior_sql="SELECT 0 AS p",
        prior_post_process=None,
        prior_extra_blocks=prior_extras,
        execute_primary=_noop_execute,
    )
    assert out.extra_result_blocks is not None
    by_id = {b.block_id: b for b in out.extra_result_blocks}
    assert by_id["block-a"].sql == "SELECT 1 AS a"
    assert by_id["block-b"].title == "Payroll updated"

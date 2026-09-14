from app.services.ai_services.datamart.scenario.extra_blocks import run_extra_datamart_block


def test_extra_block_none_sql_returns_non_executable() -> None:
    blk = run_extra_datamart_block(
        spec={"block_id": "b1234", "title": "t", "sql": "NONE"},
        system_prompt="",
        primary_sql="SELECT 1",
        question="q",
        grounding=None,
    )
    assert blk.sql is None
    assert blk.error


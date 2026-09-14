from app.services.legacy_sql_converter.converter_service import build_prompt_text


def test_prompt_includes_reference_and_sql():
    prompt = build_prompt_text("SELECT 1 FROM legacy_table", "core.dim_x:\n  col — Col")
    assert "core.dim_x:" in prompt
    assert "SELECT 1 FROM legacy_table" in prompt
    assert "```sql" in prompt


def test_prompt_notes_missing_reference():
    prompt = build_prompt_text("SELECT 1", "")
    assert "No schema reference could be gathered" in prompt
    assert "SELECT 1" in prompt

"""Regression: template group API models require string ids, not UUID objects."""
from types import SimpleNamespace

from app.api.routes.datamart_chat import _template_group_response


def test_template_group_response_accepts_string_id_dto():
    dto = SimpleNamespace(
        id="bfcddbd0-2c40-4b81-b7fa-014e2b0ac69d",
        name="rich group",
        position=0,
        created_at="2026-05-20T00:00:00",
        updated_at="2026-05-20T00:00:00",
    )
    resp = _template_group_response(dto)
    assert resp.id == dto.id
    assert resp.name == "rich group"

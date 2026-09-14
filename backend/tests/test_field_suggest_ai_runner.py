"""suggest_field_sdk — the tool-equipped replacement for the plain
AIProvider.converse() call AIService.suggest_fields() used to make. Mocks the
Claude Code SDK client (no live model call); locks in: the chosen ref is
extracted from structured_output, an error with no structured output raises
(so the caller's try/except degrades to the deterministic order), and a
missing/null ref returns None rather than raising.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.core.tenancy import TenantContext
from app.domain.enums import Role
from app.services.field_suggest_ai_runner import suggest_field_sdk

_CTX = TenantContext(tenant_id="t", pg_schema="t", acting_user_id="u", role=Role.CLIENT_HR_ADMIN, on_behalf=False)


class ResultMessage:  # name matters: the runner checks __class__.__name__ == "ResultMessage"
    def __init__(self, is_error=False, result=None):
        self.is_error = is_error
        self.result = result
        self.structured_output = None


class _TextMessage:
    def __init__(self, structured_output=None):
        self.structured_output = structured_output


def _fake_client(messages):
    class _Client:
        def __init__(self, options):
            self.options = options

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def query(self, user):
            self.queried = user

        async def receive_response(self):
            for m in messages:
                yield m

    return _Client


def _patched(messages):
    return (
        patch("app.services.field_suggest_ai_runner.build_datamart_tools", return_value=[]),
        patch("claude_agent_sdk.create_sdk_mcp_server", return_value={}),
        patch("claude_agent_sdk.ClaudeSDKClient", _fake_client(messages)),
    )


@pytest.mark.asyncio
async def test_returns_the_chosen_ref_from_structured_output():
    messages = [_TextMessage(structured_output={"ref": "employee.grade_from"})]
    p1, p2, p3 = _patched(messages)
    with p1, p2, p3:
        out = await suggest_field_sdk(_CTX, "Grade F", "employee.grade_from: Grade From", get_settings())
    assert out == "employee.grade_from"


@pytest.mark.asyncio
async def test_null_ref_returns_none():
    messages = [_TextMessage(structured_output={"ref": None})]
    p1, p2, p3 = _patched(messages)
    with p1, p2, p3:
        out = await suggest_field_sdk(_CTX, "Mystery Column", "employee.grade_from: Grade From", get_settings())
    assert out is None


@pytest.mark.asyncio
async def test_error_with_no_structured_output_raises():
    messages = [ResultMessage(is_error=True, result="budget exceeded")]
    p1, p2, p3 = _patched(messages)
    with p1, p2, p3, pytest.raises(RuntimeError, match="budget exceeded"):
        await suggest_field_sdk(_CTX, "Grade F", "employee.grade_from: Grade From", get_settings())

"""HRIS launch validation — MinHRM PHP actionLaunchAnalytics payload shape."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.hris_launch.validate import (
    HrisLaunchValidationError,
    parse_and_validate_launch_payload,
)


@pytest.fixture
def active_tenant():
    with patch(
        "app.services.hris_launch.validate._tenant_active",
        return_value=(True, "Acme Corp"),
    ):
        yield


def test_php_launch_payload_shape(active_tenant: None) -> None:
    """Fields from PythonPayroll::encryptAuthPayload in actionLaunchAnalytics."""
    with patch(
        "app.services.hris_launch.validate.decrypt_hris_payload_with_configured_secrets",
        return_value={
            "token": "rotating-auth-code-32-chars-ok!!!!",
            "subdomain": "demo_tenant",
            "user_emp_id": 1001,
            "company_logo_url": "https://hris.example/uploads/logo.png",
        },
    ):
        claims = parse_and_validate_launch_payload("dummy-b64")

    assert claims.tenant_id == "demo_tenant"
    assert claims.user_id == "1001"
    assert claims.logo_url == "https://hris.example/uploads/logo.png"
    assert "warehouse_access" in claims.permissions


def test_still_requires_permissions_without_php_token(active_tenant: None) -> None:
    with patch(
        "app.services.hris_launch.validate.decrypt_hris_payload_with_configured_secrets",
        return_value={"subdomain": "demo_tenant", "employee_id": "1"},
    ):
        with pytest.raises(HrisLaunchValidationError, match="warehouse access"):
            parse_and_validate_launch_payload("dummy-b64")

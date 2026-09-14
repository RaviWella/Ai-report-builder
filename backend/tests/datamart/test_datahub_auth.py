"""DataHub GMS auth headers."""
from app.services.ai_services.datamart import config as dh_config
from app.services.ai_services.datamart.semantic.datahub import datahub_request_headers


def test_datahub_headers_without_token(monkeypatch):
    monkeypatch.setattr(dh_config, "DATAHUB_GMS_TOKEN", "")
    headers = datahub_request_headers()
    assert headers["Content-Type"] == "application/json"
    assert "Authorization" not in headers


def test_datahub_headers_with_token(monkeypatch):
    monkeypatch.setattr(dh_config, "DATAHUB_GMS_TOKEN", "pat-test-token")
    headers = datahub_request_headers()
    assert headers["Authorization"] == "Bearer pat-test-token"

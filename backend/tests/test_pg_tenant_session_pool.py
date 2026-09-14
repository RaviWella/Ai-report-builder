"""Tenant session must use one pool checkout per request (not two)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import TimeoutError as SATimeoutError

from app.db.pg_schema_provisioner import PostgresSchemaProvisioner
from app.db.pg_tenant_session import PostgresTenantSessionManager
from app.services.tenant_scope import clear_datamart_key_cache, resolve_datamart_key


def _session_mock() -> MagicMock:
    session = MagicMock()
    session.info = {}
    return session


def test_scope_opens_one_session():
    postgres = MagicMock()
    session = _session_mock()
    postgres.session.return_value = session
    postgres.pool_status.return_value = {}

    mgr = PostgresTenantSessionManager(postgres=postgres)
    mgr._validate_tenant_for_provisioning = MagicMock()
    mgr._provisioner.ensure_schema = MagicMock(return_value=False)

    with mgr.scope("demo_tenant") as yielded:
        assert yielded is session

    assert postgres.session.call_count == 1
    session.close.assert_called_once()
    mgr._validate_tenant_for_provisioning.assert_called_once()
    assert session.info.get("pg_tenant_schema") == "demo_tenant"


def test_scope_does_not_wrap_pool_timeout():
    postgres = MagicMock()
    session = _session_mock()
    postgres.session.return_value = session
    postgres.pool_status.return_value = {"checked_out": 10}
    session.execute.side_effect = SATimeoutError("QueuePool limit of size 5 overflow 5 reached")

    mgr = PostgresTenantSessionManager(postgres=postgres)

    with pytest.raises(SATimeoutError):
        with mgr.scope("demo_tenant"):
            pass

    session.close.assert_called_once()


def test_ensure_schema_skips_db_when_cached():
    provisioner = PostgresSchemaProvisioner()
    provisioner.remember_schema("tenant_a")
    session = MagicMock()

    assert provisioner.ensure_schema(session, "tenant_a") is False
    session.execute.assert_not_called()


class _FakeSharedCache:
    """Stands in for the Redis-backed result cache — a plain dict, so this test
    verifies resolve_datamart_key's own get-then-set wiring (the Redis transport
    itself is covered by test_result_cache.py) without needing a live Redis."""

    def __init__(self):
        self._store: dict[str, object] = {}

    def get(self, key):
        return self._store.get(key)

    def set(self, key, value, ttl=None):
        self._store[key] = value

    def delete(self, key):
        self._store.pop(key, None)


def test_resolve_datamart_key_reuses_cache():
    with (
        patch("app.services.tenant_scope.result_cache.cache", return_value=_FakeSharedCache()),
        patch("app.services.tenant_scope.get_postgres_database") as get_db,
    ):
        session = _session_mock()
        session.execute.return_value = session
        get_db.return_value.session.return_value = session
        with patch("app.services.tenant_scope.get_datamart_key", return_value="coca_cola"):
            assert resolve_datamart_key("coca-cola") == "coca_cola"
            assert resolve_datamart_key("coca-cola") == "coca_cola"
        assert get_db.return_value.session.call_count == 1


def test_clear_datamart_key_cache_forces_a_fresh_lookup():
    fake = _FakeSharedCache()
    with (
        patch("app.services.tenant_scope.result_cache.cache", return_value=fake),
        patch("app.services.tenant_scope.get_postgres_database") as get_db,
    ):
        session = _session_mock()
        session.execute.return_value = session
        get_db.return_value.session.return_value = session
        with patch("app.services.tenant_scope.get_datamart_key", return_value="gamma_lanka"):
            assert resolve_datamart_key("gammalanka") == "gamma_lanka"
            clear_datamart_key_cache("gammalanka")
            assert resolve_datamart_key("gammalanka") == "gamma_lanka"
        assert get_db.return_value.session.call_count == 2

from __future__ import annotations

from hr_agent.configs.config import settings
from hr_agent.utils import db as db_utils


def test_resolve_db_settings_prefers_turso_env(monkeypatch):
    monkeypatch.setattr(settings, "turso_database_url", "libsql://demo-db-acme.turso.io")
    monkeypatch.setattr(settings, "turso_auth_token", "token-123")
    monkeypatch.setattr(settings, "db_url", "")

    db_url, auth_token = db_utils._resolve_db_settings()

    assert db_url.startswith("sqlite+libsql://demo-db-acme.turso.io")
    assert "secure=true" in db_url
    assert auth_token == "token-123"


def test_resolve_db_settings_uses_explicit_local_db_url_when_no_turso(monkeypatch):
    monkeypatch.setattr(settings, "turso_database_url", "")
    monkeypatch.setattr(settings, "turso_auth_token", "")
    monkeypatch.setattr(settings, "db_url", "sqlite:///./hr_demo.db")

    db_url, auth_token = db_utils._resolve_db_settings()

    assert db_url == "sqlite:///./hr_demo.db"
    assert auth_token == ""


def test_resolve_db_settings_normalizes_libsql_db_url(monkeypatch):
    monkeypatch.setattr(settings, "turso_database_url", "")
    monkeypatch.setattr(settings, "turso_auth_token", "token-xyz")
    monkeypatch.setattr(settings, "db_url", "libsql://prod-db-acme.turso.io")

    db_url, auth_token = db_utils._resolve_db_settings()

    assert db_url.startswith("sqlite+libsql://prod-db-acme.turso.io")
    assert "secure=true" in db_url
    assert auth_token == "token-xyz"


def test_resolve_db_settings_raises_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "turso_database_url", "")
    monkeypatch.setattr(settings, "turso_auth_token", "")
    monkeypatch.setattr(settings, "db_url", "")

    try:
        db_utils._resolve_db_settings()
        raise AssertionError("Expected RuntimeError when DB is not configured")
    except RuntimeError as exc:
        assert "Database is not configured" in str(exc)

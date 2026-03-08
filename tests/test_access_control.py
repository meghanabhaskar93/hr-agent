from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api import server


def test_allowlist_blocks_non_member(monkeypatch):
    monkeypatch.setattr(
        server.settings,
        "allowed_test_user_emails",
        "amanda.foster@acme.com,jordan.lee@acme.com",
    )
    server.get_allowed_test_user_emails.cache_clear()

    # Should not be called when allowlist blocks first.
    monkeypatch.setattr(server, "get_requester_context", lambda _email: None)

    with TestClient(server.app) as client:
        response = client.get("/me", headers={"X-User-Email": "alex.kim@acme.com"})
        assert response.status_code == 403
        assert "restricted" in response.json()["detail"].lower()

    server.get_allowed_test_user_emails.cache_clear()


def test_allowlist_allows_member(monkeypatch):
    monkeypatch.setattr(
        server.settings,
        "allowed_test_user_emails",
        "amanda.foster@acme.com,jordan.lee@acme.com",
    )
    server.get_allowed_test_user_emails.cache_clear()

    monkeypatch.setattr(
        server,
        "get_requester_context",
        lambda email: {
            "employee_id": 110,
            "user_email": email,
            "name": "Amanda Foster",
            "role": "HR",
            "department": "HR",
            "direct_reports": [],
            "is_manager": False,
        },
    )

    with TestClient(server.app) as client:
        response = client.get("/me", headers={"X-User-Email": "amanda.foster@acme.com"})
        assert response.status_code == 200
        assert response.json()["email"] == "amanda.foster@acme.com"

    server.get_allowed_test_user_emails.cache_clear()


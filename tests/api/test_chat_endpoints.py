from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from apps.api import server


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, "seed_if_needed", lambda: None)
    server._sessions.clear()
    server.app.dependency_overrides.clear()

    with TestClient(server.app) as api_client:
        yield api_client

    server._sessions.clear()
    server.app.dependency_overrides.clear()


def test_me_requires_x_user_email_header(client, monkeypatch):
    monkeypatch.setattr(server.rate_limiter, "is_allowed", lambda _key: (True, {}))

    response = client.get("/me")

    assert response.status_code == 422
    payload = response.json()
    assert payload["detail"][0]["loc"] == ["header", "X-User-Email"]


def test_me_returns_401_for_unknown_user(client, monkeypatch):
    monkeypatch.setattr(server.rate_limiter, "is_allowed", lambda _key: (True, {}))
    monkeypatch.setattr(
        server,
        "get_requester_context",
        lambda _email: (_ for _ in ()).throw(ValueError("User unknown@acme.com not found")),
    )

    response = client.get("/me", headers={"X-User-Email": "unknown@acme.com"})

    assert response.status_code == 401
    assert "not found" in response.json()["detail"].lower()


def test_chat_endpoint_creates_and_reuses_session(client, monkeypatch):
    async def fake_user():
        return {
            "employee_id": 7,
            "user_email": "alex.kim@acme.com",
            "name": "Alex",
            "role": "EMPLOYEE",
            "department": "Engineering",
            "direct_reports": [],
            "is_manager": False,
        }

    server.app.dependency_overrides[server.get_current_user] = fake_user
    monkeypatch.setattr(
        server,
        "run_hr_agent",
        lambda user_email, question, session_id=None, prior_turns=None: (
            f"Answer for {user_email}: {question}"
        ),
    )

    first = client.post("/chat", json={"message": "What is my PTO balance?"})
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["response"].startswith("Answer for alex.kim@acme.com:")
    assert first_payload["session_id"]

    second = client.post(
        "/chat",
        json={
            "message": "And next quarter?",
            "session_id": first_payload["session_id"],
        },
    )
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["session_id"] == first_payload["session_id"]

    assert len(server._sessions[first_payload["session_id"]]["turns"]) == 2


def test_session_endpoint_rejects_foreign_session_access(client):
    async def alice_user():
        return {
            "employee_id": 10,
            "user_email": "alice.manager@acme.com",
            "name": "Alice",
            "role": "MANAGER",
            "department": "People Ops",
            "direct_reports": [11],
            "is_manager": True,
        }

    async def bob_user():
        return {
            "employee_id": 20,
            "user_email": "bob.employee@acme.com",
            "name": "Bob",
            "role": "EMPLOYEE",
            "department": "Engineering",
            "direct_reports": [],
            "is_manager": False,
        }

    server.app.dependency_overrides[server.get_current_user] = alice_user
    create_response = client.post("/sessions")
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    server.app.dependency_overrides[server.get_current_user] = bob_user
    get_response = client.get(f"/sessions/{session_id}")

    assert get_response.status_code == 403
    assert "access denied" in get_response.json()["detail"].lower()


def test_rate_limit_error_sets_retry_after_header(client, monkeypatch):
    monkeypatch.setattr(
        server.rate_limiter,
        "is_allowed",
        lambda _key: (False, {"reason": "minute_limit_exceeded"}),
    )

    response = client.get("/me", headers={"X-User-Email": "alex.kim@acme.com"})

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert response.json()["error"] == "RATE_LIMIT_EXCEEDED"

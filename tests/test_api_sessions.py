from __future__ import annotations

from datetime import datetime
from uuid import UUID
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api import server
from apps.api.server import app, get_current_user
from hr_agent.configs.config import settings
from hr_agent.utils import db as db_utils


def _override_user():
    return {
        "employee_id": 201,
        "user_email": "alex.kim@acme.com",
        "name": "Alex Kim",
        "role": "EMPLOYEE",
        "department": "Engineering",
        "direct_reports": [],
        "is_manager": False,
    }


def _override_other_user():
    return {
        "employee_id": 212,
        "user_email": "emma.thompson@acme.com",
        "name": "Emma Thompson",
        "role": "EMPLOYEE",
        "department": "Engineering",
        "direct_reports": [],
        "is_manager": False,
    }

def test_get_or_create_session_reuses_owned_session_and_replaces_foreign():
    server._sessions.clear()
    server._sessions["session-1"] = {
        "user_email": "alex.kim@acme.com",
        "created_at": datetime.utcnow(),
        "turns": [{"query": "Hello", "response": "Hi"}],
        "pending_confirmation": {"action": "submit"},
    }

    session_id, session = server.get_or_create_session("session-1", "alex.kim@acme.com")
    assert session_id == "session-1"
    assert session["turns"] == [{"query": "Hello", "response": "Hi"}]

    new_session_id, new_session = server.get_or_create_session(
        "session-1",
        "emma.thompson@acme.com",
    )
    assert new_session_id == "session-1"
    assert new_session["user_email"] == "emma.thompson@acme.com"
    assert new_session["turns"] == []
    assert new_session["pending_confirmation"] is None

    generated_id, generated = server.get_or_create_session(None, "alex.kim@acme.com")
    UUID(generated_id)
    assert generated["user_email"] == "alex.kim@acme.com"

    server._sessions.clear()


def test_build_session_title_trims_whitespace_and_truncates_long_queries():
    title = server.build_session_title(
        {
            "turns": [
                {"query": "   "},
                {
                    "query": "   Please   help   me understand my payroll deduction details for the latest payslip   "
                },
            ]
        }
    )

    assert title == "Please help me understand my payroll deduction d..."
    assert server.build_session_title({"turns": [{"query": "   "}]}) is None


@pytest.fixture(autouse=True)
def _use_local_sqlite_for_api_tests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "api_sessions.db"
    monkeypatch.setattr(settings, "turso_database_url", "")
    monkeypatch.setattr(settings, "turso_auth_token", "")
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    db_utils._engine = None
    yield
    db_utils._engine = None


def test_session_turns_history_endpoint(monkeypatch):
    app.dependency_overrides[get_current_user] = _override_user
    monkeypatch.setattr(server, "seed_if_needed", lambda: None)
    server._sessions.clear()
    server._sessions["session-1"] = {
        "user_email": "alex.kim@acme.com",
        "created_at": datetime.utcnow(),
        "turns": [
            {
                "query": "How many leave days do I have?",
                "response": "You have 18 days remaining.",
                "timestamp": "2026-03-13T09:00:00",
            },
            {
                "query": "Can I carry over days?",
                "response": "Yes, up to 5 days can be carried over.",
                "timestamp": "2026-03-13T09:01:00",
            },
        ],
        "pending_confirmation": None,
    }

    with TestClient(app) as client:
        response = client.get("/sessions/session-1/turns")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 2
        assert payload[0]["query"] == "How many leave days do I have?"
        assert payload[1]["response"] == "Yes, up to 5 days can be carried over."

    app.dependency_overrides.clear()
    server._sessions.clear()


def test_session_turns_forbidden_and_not_found(monkeypatch):
    monkeypatch.setattr(server, "seed_if_needed", lambda: None)
    server._sessions.clear()
    server._sessions["session-1"] = {
        "user_email": "alex.kim@acme.com",
        "created_at": datetime.utcnow(),
        "turns": [],
        "pending_confirmation": None,
    }

    app.dependency_overrides[get_current_user] = _override_other_user
    with TestClient(app) as client:
        forbidden = client.get("/sessions/session-1/turns")
        assert forbidden.status_code == 403

        missing = client.get("/sessions/missing/turns")
        assert missing.status_code == 404

    app.dependency_overrides.clear()
    server._sessions.clear()


def test_chat_follow_up_uses_session_turn_history(monkeypatch):
    app.dependency_overrides[get_current_user] = _override_user
    monkeypatch.setattr(server, "seed_if_needed", lambda: None)
    server._sessions.clear()

    observed_calls: list[dict] = []

    def _fake_run_hr_agent(
        user_email: str,
        question: str,
        session_id: str | None = None,
        prior_turns: list[dict] | None = None,
    ) -> str:
        turns = list(prior_turns or [])
        observed_calls.append(
            {
                "user_email": user_email,
                "question": question,
                "session_id": session_id,
                "prior_turns": turns,
            }
        )
        return f"response-for:{question}|history:{len(turns)}"

    monkeypatch.setattr(server, "run_hr_agent", _fake_run_hr_agent)

    with TestClient(app) as client:
        first = client.post("/chat", json={"message": "I need employee info"})
        assert first.status_code == 200
        first_payload = first.json()
        session_id = first_payload["session_id"]
        assert first_payload["response"] == "response-for:I need employee info|history:0"

        second = client.post(
            "/chat",
            json={"message": "employee 201", "session_id": session_id},
        )
        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload["session_id"] == session_id
        assert second_payload["response"] == "response-for:employee 201|history:1"

    assert len(observed_calls) == 2
    assert observed_calls[0]["session_id"] == session_id
    assert observed_calls[0]["prior_turns"] == []

    assert observed_calls[1]["session_id"] == session_id
    assert len(observed_calls[1]["prior_turns"]) == 1
    assert observed_calls[1]["prior_turns"][0]["query"] == "I need employee info"
    assert (
        observed_calls[1]["prior_turns"][0]["response"]
        == "response-for:I need employee info|history:0"
    )

    app.dependency_overrides.clear()
    server._sessions.clear()


def test_session_crud_and_listing_endpoints(monkeypatch):
    app.dependency_overrides[get_current_user] = _override_user
    monkeypatch.setattr(server, "seed_if_needed", lambda: None)
    server._sessions.clear()

    with TestClient(app) as client:
        create_response = client.post("/sessions")
        assert create_response.status_code == 200
        created = create_response.json()
        session_id = created["session_id"]
        assert created["user_email"] == "alex.kim@acme.com"
        assert created["turn_count"] == 0
        assert created["has_pending_confirmation"] is False
        assert created["title"] is None

        server._sessions[session_id]["turns"].append(
            {
                "query": "   Need   PTO balance details   ",
                "response": "You have 18 days left.",
                "timestamp": "2026-03-13T10:00:00",
            }
        )
        server._sessions[session_id]["pending_confirmation"] = {"action": "submit"}

        info_response = client.get(f"/sessions/{session_id}")
        assert info_response.status_code == 200
        info_payload = info_response.json()
        assert info_payload["turn_count"] == 1
        assert info_payload["has_pending_confirmation"] is True
        assert info_payload["title"] == "Need PTO balance details"

        list_response = client.get("/sessions")
        assert list_response.status_code == 200
        list_payload = list_response.json()
        assert len(list_payload) == 1
        assert list_payload[0]["session_id"] == session_id

        delete_response = client.delete(f"/sessions/{session_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Session deleted successfully"
        assert session_id not in server._sessions

    app.dependency_overrides.clear()
    server._sessions.clear()


def test_session_info_and_delete_forbidden_and_not_found(monkeypatch):
    monkeypatch.setattr(server, "seed_if_needed", lambda: None)
    server._sessions.clear()
    server._sessions["session-1"] = {
        "user_email": "alex.kim@acme.com",
        "created_at": datetime.utcnow(),
        "turns": [],
        "pending_confirmation": None,
    }

    app.dependency_overrides[get_current_user] = _override_other_user
    with TestClient(app) as client:
        assert client.get("/sessions/missing").status_code == 404
        assert client.delete("/sessions/missing").status_code == 404
        assert client.get("/sessions/session-1").status_code == 403
        assert client.delete("/sessions/session-1").status_code == 403

    app.dependency_overrides.clear()
    server._sessions.clear()

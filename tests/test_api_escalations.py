from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.server import app, get_current_user
from hr_agent.configs.config import settings
from hr_agent.utils import db as db_utils


class _FakeEscalationService:
    def __init__(self):
        self.last_create: dict | None = None
        self.last_transition: dict | None = None
        self.last_assign: dict | None = None
        self.last_priority: dict | None = None
        self.last_message: dict | None = None
        self.last_requester_reply: dict | None = None
        self.last_escalate: dict | None = None
        self.transition_result = {"success": True}
        self.generic_result = {"success": True}

    def list_requests(
        self, viewer_email: str, status: str | None = None, limit: int = 100
    ):
        return [
            {
                "escalation_id": 11,
                "requester_employee_id": 201,
                "requester_email": viewer_email,
                "requester_name": "Alex Kim",
                "requester_department": "Engineering",
                "requester_title": "Software Engineer",
                "thread_id": "thread-1",
                "source_message_excerpt": "Need policy clarification",
                "status": "PENDING",
                "created_at": "2026-03-08T10:00:00",
                "updated_at": "2026-03-08T10:00:00",
                "updated_by_employee_id": None,
                "resolution_note": None,
                "priority": "HIGH",
                "category": "Policy",
                "assigned_to_employee_id": None,
                "assigned_to_email": None,
                "assigned_to_name": None,
                "agent_suggestion": "Review policy exception with HRBP.",
                "last_message_to_requester": None,
                "last_message_at": None,
                "escalation_level": 1,
            }
        ]

    def get_request_detail(self, viewer_email: str, escalation_id: int):
        return {
            "success": True,
            "request": self.list_requests(viewer_email)[0] | {"escalation_id": escalation_id},
            "timeline": [
                {
                    "event_id": 1,
                    "escalation_id": escalation_id,
                    "event_type": "CREATED",
                    "event_note": "Escalation request created.",
                    "actor_employee_id": 201,
                    "actor_email": "alex.kim@acme.com",
                    "actor_name": "Alex",
                    "metadata_json": None,
                    "created_at": "2026-03-08T10:00:00",
                }
            ],
            "missing_fields": ["assigned_to_email"],
            "completeness_percent": 75,
        }

    def list_counts(self, viewer_email: str):
        return {"total": 3, "pending": 2, "in_review": 1, "resolved": 0}

    def create_request(
        self,
        requester_employee_id: int,
        requester_email: str,
        thread_id: str,
        source_message_excerpt: str,
        priority: str = "MEDIUM",
        category: str | None = None,
        agent_suggestion: str | None = None,
    ):
        self.last_create = {
            "requester_employee_id": requester_employee_id,
            "requester_email": requester_email,
            "thread_id": thread_id,
            "source_message_excerpt": source_message_excerpt,
            "priority": priority,
            "category": category,
            "agent_suggestion": agent_suggestion,
        }
        return {"success": True, "escalation_id": 77}

    def transition_status(
        self,
        viewer_email: str,
        actor_employee_id: int,
        escalation_id: int,
        new_status: str,
        resolution_note: str | None = None,
    ):
        self.last_transition = {
            "viewer_email": viewer_email,
            "actor_employee_id": actor_employee_id,
            "escalation_id": escalation_id,
            "new_status": new_status,
            "resolution_note": resolution_note,
        }
        return self.transition_result

    def assign_request(
        self,
        viewer_email: str,
        actor_employee_id: int,
        escalation_id: int,
        assignee_email: str | None,
    ):
        self.last_assign = {
            "viewer_email": viewer_email,
            "actor_employee_id": actor_employee_id,
            "escalation_id": escalation_id,
            "assignee_email": assignee_email,
        }
        return self.generic_result

    def update_priority(
        self,
        viewer_email: str,
        actor_employee_id: int,
        escalation_id: int,
        priority: str,
    ):
        self.last_priority = {
            "viewer_email": viewer_email,
            "actor_employee_id": actor_employee_id,
            "escalation_id": escalation_id,
            "priority": priority,
        }
        return self.generic_result

    def message_requester(
        self,
        viewer_email: str,
        actor_employee_id: int,
        escalation_id: int,
        message: str,
    ):
        self.last_message = {
            "viewer_email": viewer_email,
            "actor_employee_id": actor_employee_id,
            "escalation_id": escalation_id,
            "message": message,
        }
        return self.generic_result

    def escalate_request(
        self,
        viewer_email: str,
        actor_employee_id: int,
        escalation_id: int,
        note: str | None = None,
    ):
        self.last_escalate = {
            "viewer_email": viewer_email,
            "actor_employee_id": actor_employee_id,
            "escalation_id": escalation_id,
            "note": note,
        }
        return self.generic_result

    def reply_as_requester(
        self,
        viewer_email: str,
        actor_employee_id: int,
        escalation_id: int,
        message: str,
    ):
        self.last_requester_reply = {
            "viewer_email": viewer_email,
            "actor_employee_id": actor_employee_id,
            "escalation_id": escalation_id,
            "message": message,
        }
        return self.generic_result


def _override_user():
    return {
        "employee_id": 101,
        "user_email": "amanda.foster@acme.com",
        "name": "Amanda Foster",
        "role": "HR",
        "department": "HR",
        "direct_reports": [],
        "is_manager": False,
    }


@pytest.fixture(autouse=True)
def _use_local_sqlite_for_api_tests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "api_escalations.db"
    monkeypatch.setattr(settings, "turso_database_url", "")
    monkeypatch.setattr(settings, "turso_auth_token", "")
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    db_utils._engine = None
    yield
    db_utils._engine = None


def test_escalation_endpoints_list_counts_create_detail_and_transition(monkeypatch):
    fake_service = _FakeEscalationService()
    monkeypatch.setattr("apps.api.server.get_escalation_service", lambda: fake_service)
    app.dependency_overrides[get_current_user] = _override_user

    with TestClient(app) as client:
        list_response = client.get("/escalations")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        detail_response = client.get("/escalations/11/detail")
        assert detail_response.status_code == 200
        assert detail_response.json()["completeness_percent"] == 75

        counts_response = client.get("/escalations/counts")
        assert counts_response.status_code == 200
        assert counts_response.json() == {
            "total": 3,
            "pending": 2,
            "in_review": 1,
            "resolved": 0,
        }

        create_response = client.post(
            "/escalations",
            json={
                "thread_id": "session-abc",
                "source_message_excerpt": "Need manager review on policy edge case.",
                "priority": "HIGH",
                "category": "Policy",
                "agent_suggestion": "Verify against leave policy.",
            },
        )
        assert create_response.status_code == 200
        assert create_response.json() == {
            "success": True,
            "escalation_id": 77,
            "error": None,
        }
        assert fake_service.last_create is not None
        assert fake_service.last_create["requester_employee_id"] == 101
        assert fake_service.last_create["priority"] == "HIGH"

        transition_response = client.post(
            "/escalations/77/transition",
            json={"new_status": "IN_REVIEW", "resolution_note": None},
        )
        assert transition_response.status_code == 200
        assert transition_response.json() == {
            "success": True,
            "escalation_id": None,
            "error": None,
        }
        assert fake_service.last_transition is not None
        assert fake_service.last_transition["new_status"] == "IN_REVIEW"

    app.dependency_overrides.clear()


def test_escalation_action_endpoints(monkeypatch):
    fake_service = _FakeEscalationService()
    monkeypatch.setattr("apps.api.server.get_escalation_service", lambda: fake_service)
    app.dependency_overrides[get_current_user] = _override_user

    with TestClient(app) as client:
        assign_response = client.post(
            "/escalations/11/assign", json={"assignee_email": "james.wilson@acme.com"}
        )
        assert assign_response.status_code == 200
        assert fake_service.last_assign is not None
        assert fake_service.last_assign["assignee_email"] == "james.wilson@acme.com"

        priority_response = client.post("/escalations/11/priority", json={"priority": "CRITICAL"})
        assert priority_response.status_code == 200
        assert fake_service.last_priority is not None
        assert fake_service.last_priority["priority"] == "CRITICAL"

        message_response = client.post(
            "/escalations/11/message", json={"message": "We need one more data point from you."}
        )
        assert message_response.status_code == 200
        assert fake_service.last_message is not None
        assert "one more data point" in fake_service.last_message["message"]

        requester_reply_response = client.post(
            "/escalations/11/requester-reply", json={"message": "Here is the additional context."}
        )
        assert requester_reply_response.status_code == 200
        assert fake_service.last_requester_reply is not None
        assert "additional context" in fake_service.last_requester_reply["message"]

        escalate_response = client.post("/escalations/11/escalate", json={"note": "Urgent"})
        assert escalate_response.status_code == 200
        assert fake_service.last_escalate is not None
        assert fake_service.last_escalate["note"] == "Urgent"

    app.dependency_overrides.clear()


def test_escalation_transition_http_error_mapping(monkeypatch):
    fake_service = _FakeEscalationService()
    monkeypatch.setattr("apps.api.server.get_escalation_service", lambda: fake_service)
    app.dependency_overrides[get_current_user] = _override_user

    with TestClient(app) as client:
        fake_service.transition_result = {
            "success": False,
            "error": "Only HR/Manager can triage requests.",
        }
        denied = client.post("/escalations/1/transition", json={"new_status": "IN_REVIEW"})
        assert denied.status_code == 403

        fake_service.transition_result = {
            "success": False,
            "error": "Escalation request not found.",
        }
        missing = client.post("/escalations/404/transition", json={"new_status": "IN_REVIEW"})
        assert missing.status_code == 404

        fake_service.transition_result = {
            "success": False,
            "error": "Invalid transition: PENDING -> RESOLVED.",
        }
        invalid = client.post("/escalations/1/transition", json={"new_status": "RESOLVED"})
        assert invalid.status_code == 400

    app.dependency_overrides.clear()


def test_escalation_requester_reply_http_error_mapping(monkeypatch):
    fake_service = _FakeEscalationService()
    monkeypatch.setattr("apps.api.server.get_escalation_service", lambda: fake_service)
    app.dependency_overrides[get_current_user] = _override_user

    with TestClient(app) as client:
        fake_service.generic_result = {
            "success": False,
            "error": "Only requester can reply to this escalation.",
        }
        denied = client.post(
            "/escalations/11/requester-reply",
            json={"message": "More context"},
        )
        assert denied.status_code == 403

        fake_service.generic_result = {
            "success": False,
            "error": "Cannot reply to a resolved escalation.",
        }
        invalid = client.post(
            "/escalations/11/requester-reply",
            json={"message": "Please reopen"},
        )
        assert invalid.status_code == 400

    app.dependency_overrides.clear()

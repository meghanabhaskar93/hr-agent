from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.server import app, get_current_user
from hr_agent.configs.config import settings
from hr_agent.utils import db as db_utils


class _FakeHRRequestService:
    def __init__(self):
        self.last_create: dict | None = None
        self.last_assign: dict | None = None
        self.last_priority: dict | None = None
        self.last_status: dict | None = None
        self.last_message: dict | None = None
        self.last_reply: dict | None = None
        self.last_capture: dict | None = None
        self.last_escalate: dict | None = None
        self.status_result = {"success": True}
        self.generic_result = {"success": True}

    def list_requests(
        self, viewer_email: str, status: str | None = None, limit: int = 100
    ):
        return [
            {
                "request_id": 21,
                "tenant_id": "default",
                "requester_user_id": viewer_email,
                "requester_role": "EMPLOYEE",
                "subject_employee_id": None,
                "requester_name": "Alex Kim",
                "requester_department": "Engineering",
                "requester_title": "Software Engineer",
                "subject_employee_name": None,
                "type": "ESCALATION",
                "subtype": "PAYROLL",
                "summary": "Need payroll correction",
                "description": "Net salary mismatch in March run.",
                "priority": "P1",
                "risk_level": "MED",
                "sla_due_at": None,
                "status": "NEW",
                "assignee_user_id": None,
                "assignee_name": None,
                "required_fields": [
                    "summary",
                    "description",
                    "requester_user_id",
                    "type",
                    "subtype",
                    "agent_suggestion",
                ],
                "captured_fields": {"agent_suggestion": "Review payroll adjustments."},
                "missing_fields": [],
                "created_at": "2026-03-13T10:00:00",
                "updated_at": "2026-03-13T10:00:00",
                "last_action_at": "2026-03-13T10:00:00",
                "resolution_text": None,
                "resolution_sources": [],
                "escalation_ticket_id": None,
                "last_message_to_requester": None,
                "last_message_at": None,
            }
        ]

    def get_request_detail(self, viewer_email: str, request_id: int):
        return {
            "success": True,
            "request": self.list_requests(viewer_email)[0] | {"request_id": request_id},
            "timeline": [
                {
                    "event_id": 1,
                    "request_id": request_id,
                    "tenant_id": "default",
                    "event_type": "CREATED",
                    "event_note": "HR request created.",
                    "actor_user_id": viewer_email,
                    "actor_role": "EMPLOYEE",
                    "actor_name": "Alex",
                    "payload": {"missing_fields": []},
                    "created_at": "2026-03-13T10:00:00",
                }
            ],
            "missing_fields": [],
            "completeness_percent": 100,
        }

    def list_counts(self, viewer_email: str):
        return {
            "total": 3,
            "new": 1,
            "needs_info": 1,
            "ready": 0,
            "in_progress": 1,
            "resolved": 0,
            "escalated": 0,
            "cancelled": 0,
        }

    def create_request(
        self,
        requester_user_id: str,
        requester_role: str,
        request_type: str,
        request_subtype: str,
        summary: str,
        description: str,
        tenant_id: str = "default",
        subject_employee_id: int | None = None,
        priority: str = "P2",
        risk_level: str = "LOW",
        sla_due_at: str | None = None,
        required_fields: list[str] | None = None,
        captured_fields: dict | None = None,
    ):
        self.last_create = {
            "requester_user_id": requester_user_id,
            "requester_role": requester_role,
            "request_type": request_type,
            "request_subtype": request_subtype,
            "summary": summary,
            "description": description,
            "tenant_id": tenant_id,
            "subject_employee_id": subject_employee_id,
            "priority": priority,
            "risk_level": risk_level,
            "sla_due_at": sla_due_at,
            "required_fields": required_fields,
            "captured_fields": captured_fields,
        }
        return {"success": True, "request_id": 77}

    def assign_request(
        self, viewer_email: str, request_id: int, assignee_user_id: str | None
    ):
        self.last_assign = {
            "viewer_email": viewer_email,
            "request_id": request_id,
            "assignee_user_id": assignee_user_id,
        }
        return self.generic_result

    def update_priority(self, viewer_email: str, request_id: int, priority: str):
        self.last_priority = {
            "viewer_email": viewer_email,
            "request_id": request_id,
            "priority": priority,
        }
        return self.generic_result

    def transition_status(
        self,
        viewer_email: str,
        request_id: int,
        new_status: str,
        resolution_text: str | None = None,
        resolution_sources: list[str] | None = None,
        escalation_ticket_id: str | None = None,
    ):
        self.last_status = {
            "viewer_email": viewer_email,
            "request_id": request_id,
            "new_status": new_status,
            "resolution_text": resolution_text,
            "resolution_sources": resolution_sources,
            "escalation_ticket_id": escalation_ticket_id,
        }
        return self.status_result

    def message_requester(self, viewer_email: str, request_id: int, message: str):
        self.last_message = {
            "viewer_email": viewer_email,
            "request_id": request_id,
            "message": message,
        }
        return self.generic_result

    def reply_as_requester(self, viewer_email: str, request_id: int, message: str):
        self.last_reply = {
            "viewer_email": viewer_email,
            "request_id": request_id,
            "message": message,
        }
        return self.generic_result

    def capture_fields(self, viewer_email: str, request_id: int, captured_fields: dict):
        self.last_capture = {
            "viewer_email": viewer_email,
            "request_id": request_id,
            "captured_fields": captured_fields,
        }
        return {"success": True, "missing_fields": [], "status": "READY"}

    def escalate_request(
        self,
        viewer_email: str,
        request_id: int,
        escalation_ticket_id: str | None = None,
        note: str | None = None,
    ):
        self.last_escalate = {
            "viewer_email": viewer_email,
            "request_id": request_id,
            "escalation_ticket_id": escalation_ticket_id,
            "note": note,
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
    db_path = tmp_path / "api_hr_requests.db"
    monkeypatch.setattr(settings, "turso_database_url", "")
    monkeypatch.setattr(settings, "turso_auth_token", "")
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    db_utils._engine = None
    yield
    db_utils._engine = None


def test_hr_request_endpoints_list_counts_create_detail_and_status(monkeypatch):
    fake_service = _FakeHRRequestService()
    monkeypatch.setattr("apps.api.server.get_hr_request_service", lambda: fake_service)
    app.dependency_overrides[get_current_user] = _override_user

    with TestClient(app) as client:
        list_response = client.get("/hr-requests")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        detail_response = client.get("/hr-requests/21/detail")
        assert detail_response.status_code == 200
        assert detail_response.json()["completeness_percent"] == 100

        counts_response = client.get("/hr-requests/counts")
        assert counts_response.status_code == 200
        assert counts_response.json() == {
            "total": 3,
            "new": 1,
            "needs_info": 1,
            "ready": 0,
            "in_progress": 1,
            "resolved": 0,
            "escalated": 0,
            "cancelled": 0,
        }

        create_response = client.post(
            "/hr-requests",
            json={
                "tenant_id": "default",
                "type": "ESCALATION",
                "subtype": "PAYROLL",
                "summary": "Need payroll correction",
                "description": "Net salary mismatch in March run.",
                "priority": "P1",
                "risk_level": "MED",
                "required_fields": [
                    "summary",
                    "description",
                    "requester_user_id",
                    "type",
                    "subtype",
                    "agent_suggestion",
                ],
                "captured_fields": {"agent_suggestion": "Check payroll adjustments."},
            },
        )
        assert create_response.status_code == 200
        assert create_response.json() == {"success": True, "request_id": 77, "error": None}
        assert fake_service.last_create is not None
        assert fake_service.last_create["request_type"] == "ESCALATION"
        assert fake_service.last_create["priority"] == "P1"

        status_response = client.post(
            "/hr-requests/77/status",
            json={
                "new_status": "IN_PROGRESS",
                "resolution_text": None,
                "resolution_sources": [],
                "escalation_ticket_id": None,
            },
        )
        assert status_response.status_code == 200
        assert status_response.json() == {"success": True, "request_id": None, "error": None}
        assert fake_service.last_status is not None
        assert fake_service.last_status["new_status"] == "IN_PROGRESS"

    app.dependency_overrides.clear()


def test_hr_request_action_endpoints(monkeypatch):
    fake_service = _FakeHRRequestService()
    monkeypatch.setattr("apps.api.server.get_hr_request_service", lambda: fake_service)
    app.dependency_overrides[get_current_user] = _override_user

    with TestClient(app) as client:
        assign_response = client.post(
            "/hr-requests/21/assign", json={"assignee_user_id": "james.wilson@acme.com"}
        )
        assert assign_response.status_code == 200
        assert fake_service.last_assign is not None
        assert fake_service.last_assign["assignee_user_id"] == "james.wilson@acme.com"

        priority_response = client.post("/hr-requests/21/priority", json={"priority": "P0"})
        assert priority_response.status_code == 200
        assert fake_service.last_priority is not None
        assert fake_service.last_priority["priority"] == "P0"

        message_response = client.post(
            "/hr-requests/21/message-requester",
            json={"message": "Can you share a screenshot of your payslip?"},
        )
        assert message_response.status_code == 200
        assert fake_service.last_message is not None
        assert "screenshot" in fake_service.last_message["message"]

        reply_response = client.post(
            "/hr-requests/21/requester-reply",
            json={"message": "Attaching details now."},
        )
        assert reply_response.status_code == 200
        assert fake_service.last_reply is not None
        assert "Attaching details" in fake_service.last_reply["message"]

        capture_response = client.post(
            "/hr-requests/21/capture-fields",
            json={"captured_fields": {"payslip_month": "2026-03"}},
        )
        assert capture_response.status_code == 200
        assert fake_service.last_capture is not None
        assert fake_service.last_capture["captured_fields"]["payslip_month"] == "2026-03"

        escalate_response = client.post(
            "/hr-requests/21/escalate",
            json={"note": "Needs payroll vendor intervention.", "escalation_ticket_id": "PAY-902"},
        )
        assert escalate_response.status_code == 200
        assert fake_service.last_escalate is not None
        assert fake_service.last_escalate["escalation_ticket_id"] == "PAY-902"

    app.dependency_overrides.clear()


def test_hr_request_http_error_mapping(monkeypatch):
    fake_service = _FakeHRRequestService()
    monkeypatch.setattr("apps.api.server.get_hr_request_service", lambda: fake_service)
    app.dependency_overrides[get_current_user] = _override_user

    with TestClient(app) as client:
        fake_service.status_result = {
            "success": False,
            "error": "Only HR/Manager can triage requests.",
        }
        denied = client.post("/hr-requests/1/status", json={"new_status": "IN_PROGRESS"})
        assert denied.status_code == 403

        fake_service.status_result = {
            "success": False,
            "error": "Only a different HR reviewer can resolve HR-raised requests.",
        }
        self_resolve_denied = client.post(
            "/hr-requests/1/status",
            json={"new_status": "RESOLVED"},
        )
        assert self_resolve_denied.status_code == 403

        fake_service.status_result = {
            "success": False,
            "error": "HR request not found.",
        }
        missing = client.post("/hr-requests/404/status", json={"new_status": "IN_PROGRESS"})
        assert missing.status_code == 404

        fake_service.status_result = {
            "success": False,
            "error": "Invalid transition: NEW -> RESOLVED.",
        }
        invalid = client.post("/hr-requests/1/status", json={"new_status": "RESOLVED"})
        assert invalid.status_code == 400

        fake_service.generic_result = {
            "success": False,
            "error": "Only requester can reply to this request.",
        }
        denied_reply = client.post(
            "/hr-requests/21/requester-reply",
            json={"message": "Please reopen this."},
        )
        assert denied_reply.status_code == 403

    app.dependency_overrides.clear()

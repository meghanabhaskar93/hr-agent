from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.server import app, get_current_user


class _FakeEscalationService:
    def __init__(self):
        self.last_create: dict | None = None
        self.last_transition: dict | None = None
        self.transition_result = {"success": True}

    def list_requests(self, viewer_email: str, status: str | None = None, limit: int = 100):
        return [
            {
                "escalation_id": 11,
                "requester_employee_id": 201,
                "requester_email": viewer_email,
                "thread_id": "thread-1",
                "source_message_excerpt": "Need policy clarification",
                "status": "PENDING",
                "created_at": "2026-03-08T10:00:00",
                "updated_at": "2026-03-08T10:00:00",
                "updated_by_employee_id": None,
                "resolution_note": None,
            }
        ]

    def list_counts(self, viewer_email: str):
        return {"total": 3, "pending": 2, "in_review": 1, "resolved": 0}

    def create_request(
        self,
        requester_employee_id: int,
        requester_email: str,
        thread_id: str,
        source_message_excerpt: str,
    ):
        self.last_create = {
            "requester_employee_id": requester_employee_id,
            "requester_email": requester_email,
            "thread_id": thread_id,
            "source_message_excerpt": source_message_excerpt,
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


def test_escalation_endpoints_list_counts_create_and_transition(monkeypatch):
    fake_service = _FakeEscalationService()
    monkeypatch.setattr("apps.api.server.get_escalation_service", lambda: fake_service)
    app.dependency_overrides[get_current_user] = _override_user

    with TestClient(app) as client:
        list_response = client.get("/escalations")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

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
            },
        )
        assert create_response.status_code == 200
        assert create_response.json() == {"success": True, "escalation_id": 77, "error": None}
        assert fake_service.last_create is not None
        assert fake_service.last_create["requester_employee_id"] == 101

        transition_response = client.post(
            "/escalations/77/transition",
            json={"new_status": "IN_REVIEW", "resolution_note": None},
        )
        assert transition_response.status_code == 200
        assert transition_response.json() == {"success": True, "escalation_id": None, "error": None}
        assert fake_service.last_transition is not None
        assert fake_service.last_transition["new_status"] == "IN_REVIEW"

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

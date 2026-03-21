from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text

from hr_agent.repositories.escalation import EscalationRepository
from hr_agent.services.base import EscalationService


class _TestEscalationRepository(EscalationRepository):
    def __init__(self, engine):
        self._engine = engine

    def _get_engine(self):
        return self._engine


class _FakeEmployeeRepo:
    def __init__(self, role_by_email: dict[str, str]):
        self.role_by_email = role_by_email
        self.employee_by_email = {
            "alex.kim@acme.com": {"employee_id": 201, "email": "alex.kim@acme.com"},
            "victoria.adams@acme.com": {
                "employee_id": 101,
                "email": "victoria.adams@acme.com",
            },
            "amanda.foster@acme.com": {
                "employee_id": 103,
                "email": "amanda.foster@acme.com",
            },
            "james.wilson@acme.com": {
                "employee_id": 112,
                "email": "james.wilson@acme.com",
            },
        }

    def get_role_by_email(self, email: str) -> str:
        return self.role_by_email.get(email, "EMPLOYEE")

    def get_by_email(self, email: str):
        return self.employee_by_email.get(email)


def _build_engine(tmp_path: Path):
    db_path = tmp_path / "escalation_test.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as con:
        con.execute(
            text(
                """
                CREATE TABLE employee (
                    employee_id INTEGER PRIMARY KEY,
                    preferred_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    department TEXT NOT NULL,
                    title TEXT NOT NULL
                )
                """
            )
        )
        con.execute(
            text(
                """
                CREATE TABLE hr_escalation_request (
                    escalation_id INTEGER PRIMARY KEY,
                    requester_employee_id INTEGER NOT NULL,
                    requester_email TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    source_message_excerpt TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by_employee_id INTEGER NULL,
                    resolution_note TEXT NULL,
                    priority TEXT NOT NULL DEFAULT 'MEDIUM',
                    category TEXT NULL,
                    assigned_to_employee_id INTEGER NULL,
                    assigned_to_email TEXT NULL,
                    agent_suggestion TEXT NULL,
                    last_message_to_requester TEXT NULL,
                    last_message_at TEXT NULL,
                    escalation_level INTEGER NOT NULL DEFAULT 1
                )
                """
            )
        )
        con.execute(
            text(
                """
                CREATE TABLE hr_escalation_event (
                    event_id INTEGER PRIMARY KEY,
                    escalation_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    event_note TEXT NULL,
                    actor_employee_id INTEGER NULL,
                    actor_email TEXT NULL,
                    metadata_json TEXT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
        )
        con.execute(
            text(
                """
                INSERT INTO employee VALUES
                (101, 'Victoria', 'victoria.adams@acme.com', 'Executive', 'COO'),
                (103, 'Amanda', 'amanda.foster@acme.com', 'Executive', 'CTO'),
                (112, 'James', 'james.wilson@acme.com', 'HR', 'HR Lead'),
                (201, 'Alex', 'alex.kim@acme.com', 'Engineering', 'Engineer')
                """
            )
        )
    return engine


def test_escalation_repository_create_list_counts_and_transition(tmp_path: Path):
    repo = _TestEscalationRepository(_build_engine(tmp_path))

    first_id = repo.create(
        requester_employee_id=201,
        requester_email="alex.kim@acme.com",
        thread_id="thread-a",
        source_message_excerpt="Need HR support for a policy conflict.",
        priority="HIGH",
        category="Policy",
        agent_suggestion="Check policy exception process.",
    )
    second_id = repo.create(
        requester_employee_id=201,
        requester_email="alex.kim@acme.com",
        thread_id="thread-b",
        source_message_excerpt="Escalate payroll discrepancy.",
    )

    assert first_id != second_id

    all_rows = repo.list_for_requester()
    assert len(all_rows) == 2

    alex_rows = repo.list_for_requester("alex.kim@acme.com")
    assert len(alex_rows) == 2
    assert alex_rows[0]["requester_name"] == "Alex"

    counts_all = repo.list_counts_for_requester()
    assert counts_all == {"total": 2, "pending": 2, "in_review": 0, "resolved": 0}

    changed = repo.transition_status(first_id, "IN_REVIEW", updated_by_employee_id=999)
    assert changed is True

    updated = repo.get_by_id(first_id)
    assert updated is not None
    assert updated["status"] == "IN_REVIEW"
    assert updated["updated_by_employee_id"] == 999

    event_id = repo.add_event(
        escalation_id=first_id,
        event_type="STATUS_CHANGED",
        actor_employee_id=999,
        actor_email="amanda.foster@acme.com",
        event_note="Moved to in review.",
    )
    assert event_id > 0
    events = repo.list_events(first_id)
    assert len(events) == 1
    assert events[0]["event_type"] == "STATUS_CHANGED"


def test_escalation_service_permissions_actions_and_transitions(tmp_path: Path):
    repo = _TestEscalationRepository(_build_engine(tmp_path))
    escalation_id = repo.create(
        requester_employee_id=201,
        requester_email="alex.kim@acme.com",
        thread_id="thread-a",
        source_message_excerpt="Need a manual HR follow-up.",
        category="Leave",
    )

    service = EscalationService()
    service.repo = repo
    service.employee_repo = _FakeEmployeeRepo(
        {
            "alex.kim@acme.com": "EMPLOYEE",
            "victoria.adams@acme.com": "MANAGER",
            "amanda.foster@acme.com": "HR",
            "james.wilson@acme.com": "HR",
        }
    )

    denied = service.assign_request(
        viewer_email="alex.kim@acme.com",
        actor_employee_id=201,
        escalation_id=escalation_id,
        assignee_email="james.wilson@acme.com",
    )
    assert denied["success"] is False

    assigned = service.assign_request(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=escalation_id,
        assignee_email="james.wilson@acme.com",
    )
    assert assigned["success"] is True

    priority = service.update_priority(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=escalation_id,
        priority="CRITICAL",
    )
    assert priority["success"] is True

    messaged = service.message_requester(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=escalation_id,
        message="Can you share additional context?",
    )
    assert messaged["success"] is True

    denied_reply = service.reply_as_requester(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=escalation_id,
        message="This should not pass as HR.",
    )
    assert denied_reply["success"] is False
    assert "Only requester" in denied_reply["error"]

    replied = service.reply_as_requester(
        viewer_email="alex.kim@acme.com",
        actor_employee_id=201,
        escalation_id=escalation_id,
        message="Sure. I was referring to the March payroll cycle.",
    )
    assert replied["success"] is True

    invalid = service.transition_status(
        viewer_email="victoria.adams@acme.com",
        actor_employee_id=101,
        escalation_id=escalation_id,
        new_status="RESOLVED",
    )
    assert invalid["success"] is False
    assert "Invalid transition" in invalid["error"]

    escalated = service.escalate_request(
        viewer_email="victoria.adams@acme.com",
        actor_employee_id=101,
        escalation_id=escalation_id,
        note="Urgent handling required.",
    )
    assert escalated["success"] is True

    resolved = service.transition_status(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=escalation_id,
        new_status="RESOLVED",
    )
    assert resolved["success"] is True

    detail = service.get_request_detail(
        viewer_email="amanda.foster@acme.com", escalation_id=escalation_id
    )
    assert detail["success"] is True
    assert detail["completeness_percent"] >= 75
    assert len(detail["timeline"]) >= 5
    assert any(event["event_type"] == "REQUESTER_REPLY" for event in detail["timeline"])

    row = repo.get_by_id(escalation_id)
    assert row is not None
    assert row["status"] == "RESOLVED"
    assert row["assigned_to_email"] == "james.wilson@acme.com"
    assert row["priority"] == "CRITICAL"

    manager_view = service.list_requests("victoria.adams@acme.com")
    assert len(manager_view) == 1

    employee_view = service.list_requests("alex.kim@acme.com")
    assert len(employee_view) == 1
    assert employee_view[0]["requester_email"] == "alex.kim@acme.com"


def test_escalation_service_edge_cases_and_helper_paths(tmp_path: Path):
    repo = _TestEscalationRepository(_build_engine(tmp_path))
    service = EscalationService()
    service.repo = repo
    service.employee_repo = _FakeEmployeeRepo(
        {
            "alex.kim@acme.com": "EMPLOYEE",
            "victoria.adams@acme.com": "MANAGER",
            "amanda.foster@acme.com": "HR",
            "james.wilson@acme.com": "HR",
        }
    )

    invalid_create = service.create_request(
        requester_employee_id=201,
        requester_email="alex.kim@acme.com",
        thread_id="thread-invalid",
        source_message_excerpt="Need help",
        priority="urgent",
    )
    assert invalid_create["success"] is False
    assert "invalid priority" in invalid_create["error"].lower()

    escalation_id = repo.create(
        requester_employee_id=201,
        requester_email="alex.kim@acme.com",
        thread_id="thread-edge",
        source_message_excerpt="Need manual review.",
    )

    assert service._is_triage_role("amanda.foster@acme.com") is True
    assert service._is_triage_role("alex.kim@acme.com") is False

    visible_to_hr = service._get_visible_request("amanda.foster@acme.com", escalation_id)
    assert visible_to_hr is not None
    assert visible_to_hr["escalation_id"] == escalation_id
    assert service._get_visible_request("james.wilson@acme.com", escalation_id) is not None
    assert service._get_visible_request("nobody@acme.com", escalation_id) is None

    missing_fields = service._compute_missing_fields(
        {
            "priority": "MEDIUM",
            "category": None,
            "assigned_to_email": "",
            "agent_suggestion": "Review with HRBP",
        }
    )
    assert missing_fields == ["category", "assigned_to_email"]

    assert service.list_requests("amanda.foster@acme.com", status="INVALID") == []
    assert service.list_requests("alex.kim@acme.com", status="INVALID") == []

    assign_unknown = service.assign_request(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=escalation_id,
        assignee_email="missing@acme.com",
    )
    assert assign_unknown["success"] is False
    assert "assignee not found" in assign_unknown["error"].lower()

    assign_missing = service.assign_request(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=9999,
        assignee_email="james.wilson@acme.com",
    )
    assert assign_missing["success"] is False
    assert "not found" in assign_missing["error"].lower()

    unassign = service.assign_request(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=escalation_id,
        assignee_email=None,
    )
    assert unassign["success"] is True

    invalid_priority = service.update_priority(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=escalation_id,
        priority="P0",
    )
    assert invalid_priority["success"] is False
    assert "invalid priority" in invalid_priority["error"].lower()

    missing_priority_target = service.update_priority(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=9999,
        priority="LOW",
    )
    assert missing_priority_target["success"] is False
    assert "not found" in missing_priority_target["error"].lower()

    empty_message = service.message_requester(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=escalation_id,
        message="   ",
    )
    assert empty_message["success"] is False
    assert "cannot be empty" in empty_message["error"].lower()

    missing_message_target = service.message_requester(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=9999,
        message="hello",
    )
    assert missing_message_target["success"] is False
    assert "not found" in missing_message_target["error"].lower()

    closed = service.transition_status(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=escalation_id,
        new_status="IN_REVIEW",
    )
    assert closed["success"] is True

    resolved = service.transition_status(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=escalation_id,
        new_status="RESOLVED",
    )
    assert resolved["success"] is True

    reply_closed = service.reply_as_requester(
        viewer_email="alex.kim@acme.com",
        actor_employee_id=201,
        escalation_id=escalation_id,
        message="Can I add more?",
    )
    assert reply_closed["success"] is False
    assert "resolved escalation" in reply_closed["error"].lower()

    reply_empty = service.reply_as_requester(
        viewer_email="alex.kim@acme.com",
        actor_employee_id=201,
        escalation_id=9999,
        message="   ",
    )
    assert reply_empty["success"] is False
    assert "not found" in reply_empty["error"].lower()

    invalid_status = service.transition_status(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=escalation_id,
        new_status="DONE",
    )
    assert invalid_status["success"] is False
    assert "invalid status" in invalid_status["error"].lower()

    missing_transition_target = service.transition_status(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=9999,
        new_status="IN_REVIEW",
    )
    assert missing_transition_target["success"] is False
    assert "not found" in missing_transition_target["error"].lower()

    escalate_missing = service.escalate_request(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=9999,
    )
    assert escalate_missing["success"] is False
    assert "not found" in escalate_missing["error"].lower()

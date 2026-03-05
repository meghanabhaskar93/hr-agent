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

    def get_role_by_email(self, email: str) -> str:
        return self.role_by_email.get(email, "EMPLOYEE")


def _build_engine(tmp_path: Path):
    db_path = tmp_path / "escalation_test.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as con:
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
                    resolution_note TEXT NULL
                )
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
    )
    second_id = repo.create(
        requester_employee_id=202,
        requester_email="sam.lee@acme.com",
        thread_id="thread-b",
        source_message_excerpt="Escalate payroll discrepancy.",
    )

    assert first_id != second_id

    all_rows = repo.list_for_requester()
    assert len(all_rows) == 2

    alex_rows = repo.list_for_requester("alex.kim@acme.com")
    assert len(alex_rows) == 1
    assert alex_rows[0]["thread_id"] == "thread-a"

    counts_all = repo.list_counts_for_requester()
    assert counts_all == {"total": 2, "pending": 2, "in_review": 0, "resolved": 0}

    changed = repo.transition_status(first_id, "IN_REVIEW", updated_by_employee_id=999)
    assert changed is True

    updated = repo.get_by_id(first_id)
    assert updated is not None
    assert updated["status"] == "IN_REVIEW"
    assert updated["updated_by_employee_id"] == 999


def test_escalation_service_permissions_and_transitions(tmp_path: Path):
    repo = _TestEscalationRepository(_build_engine(tmp_path))
    escalation_id = repo.create(
        requester_employee_id=201,
        requester_email="alex.kim@acme.com",
        thread_id="thread-a",
        source_message_excerpt="Need a manual HR follow-up.",
    )

    service = EscalationService()
    service.repo = repo
    service.employee_repo = _FakeEmployeeRepo(
        {
            "alex.kim@acme.com": "EMPLOYEE",
            "victoria.adams@acme.com": "MANAGER",
            "amanda.foster@acme.com": "HR",
        }
    )

    denied = service.transition_status(
        viewer_email="alex.kim@acme.com",
        actor_employee_id=201,
        escalation_id=escalation_id,
        new_status="IN_REVIEW",
    )
    assert denied["success"] is False

    invalid = service.transition_status(
        viewer_email="victoria.adams@acme.com",
        actor_employee_id=101,
        escalation_id=escalation_id,
        new_status="RESOLVED",
    )
    assert invalid["success"] is False
    assert "Invalid transition" in invalid["error"]

    in_review = service.transition_status(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=escalation_id,
        new_status="IN_REVIEW",
    )
    assert in_review["success"] is True

    resolved = service.transition_status(
        viewer_email="amanda.foster@acme.com",
        actor_employee_id=103,
        escalation_id=escalation_id,
        new_status="RESOLVED",
    )
    assert resolved["success"] is True

    row = repo.get_by_id(escalation_id)
    assert row is not None
    assert row["status"] == "RESOLVED"

    manager_view = service.list_requests("victoria.adams@acme.com")
    assert len(manager_view) == 1

    employee_view = service.list_requests("alex.kim@acme.com")
    assert len(employee_view) == 1
    assert employee_view[0]["requester_email"] == "alex.kim@acme.com"

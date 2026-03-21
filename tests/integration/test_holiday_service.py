from __future__ import annotations

from datetime import date, timedelta

import pytest

from hr_agent.services import base as services_mod


class FakeHolidayRepo:
    def __init__(self):
        self.remaining = 20.0
        self.overlap = False
        self.request_for_approval: dict | None = None
        self.request_by_id: dict | None = None
        self.team_calendar_rows: list[dict] = []
        self.created_calls: list[tuple] = []
        self.status_updates: list[tuple] = []

    def get_balance(self, employee_id: int, year: int) -> dict:
        return {"employee_id": employee_id, "year": year, "remaining": self.remaining}

    def has_overlapping_request(self, employee_id: int, start_date: str, end_date: str) -> bool:
        return self.overlap

    def create_request(
        self,
        employee_id: int,
        start_date: str,
        end_date: str,
        days: float,
        reason: str | None = None,
    ) -> int:
        self.created_calls.append((employee_id, start_date, end_date, days, reason))
        return 321

    def get_request_for_approval(self, manager_id: int, request_id: int) -> dict | None:
        return self.request_for_approval

    def get_request_by_id(self, request_id: int) -> dict | None:
        return self.request_by_id

    def update_request_status(
        self,
        request_id: int,
        status: str,
        approver_id: int | None = None,
        reason: str | None = None,
    ) -> None:
        self.status_updates.append((request_id, status, approver_id, reason))

    def get_team_calendar(self, manager_id: int, year: int, month: int | None = None) -> list[dict]:
        return self.team_calendar_rows


@pytest.fixture
def repo_and_service(monkeypatch):
    repo = FakeHolidayRepo()
    monkeypatch.setattr(services_mod, "get_holiday_repo", lambda: repo)
    service = services_mod.HolidayService()
    return repo, service


def test_submit_request_rejects_invalid_date_format(repo_and_service):
    _repo, service = repo_and_service

    result = service.submit_request(7, "03-31-2026", "2026-04-02", 2.0)

    assert result["success"] is False
    assert "invalid date format" in result["error"].lower()


def test_submit_request_succeeds_and_creates_pending_request(repo_and_service):
    repo, service = repo_and_service
    start = (date.today() + timedelta(days=14)).isoformat()
    end = (date.today() + timedelta(days=15)).isoformat()

    result = service.submit_request(7, start, end, 2.0, reason="Family trip")

    assert result["success"] is True
    assert result["request_id"] == 321
    assert repo.created_calls == [(7, start, end, 2.0, "Family trip")]
    assert "status: pending" in result["message"].lower()


def test_submit_request_rejects_end_date_before_start(repo_and_service):
    _repo, service = repo_and_service
    start = (date.today() + timedelta(days=5)).isoformat()
    end = (date.today() + timedelta(days=4)).isoformat()

    result = service.submit_request(7, start, end, 1.0)

    assert result["success"] is False
    assert "end date must be after start date" in result["error"].lower()


def test_submit_request_rejects_past_dates(repo_and_service):
    _repo, service = repo_and_service
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    result = service.submit_request(7, yesterday, tomorrow, 2.0)

    assert result["success"] is False
    assert "past" in result["error"].lower()


def test_submit_request_rejects_insufficient_balance(repo_and_service):
    repo, service = repo_and_service
    repo.remaining = 1.0
    start = (date.today() + timedelta(days=7)).isoformat()
    end = (date.today() + timedelta(days=8)).isoformat()

    result = service.submit_request(7, start, end, 2.0)

    assert result["success"] is False
    assert "insufficient balance" in result["error"].lower()


def test_submit_request_rejects_overlapping_request(repo_and_service):
    repo, service = repo_and_service
    repo.overlap = True
    start = (date.today() + timedelta(days=7)).isoformat()
    end = (date.today() + timedelta(days=8)).isoformat()

    result = service.submit_request(7, start, end, 2.0)

    assert result["success"] is False
    assert "overlapping" in result["error"].lower()


def test_approve_request_requires_pending_request_and_valid_manager(repo_and_service):
    repo, service = repo_and_service

    repo.request_for_approval = None
    missing_result = service.approve_request(manager_id=10, request_id=500)
    assert missing_result["success"] is False
    assert "not found" in missing_result["error"].lower()

    repo.request_for_approval = {"status": "APPROVED", "preferred_name": "Sam"}
    not_pending_result = service.approve_request(manager_id=10, request_id=500)
    assert not_pending_result["success"] is False
    assert "already approved" in not_pending_result["error"].lower()

    repo.request_for_approval = {"status": "PENDING", "preferred_name": "Sam"}
    approved_result = service.approve_request(manager_id=10, request_id=500)
    assert approved_result["success"] is True
    assert repo.status_updates[-1] == (500, "APPROVED", 10, None)


def test_reject_request_requires_pending_request_and_valid_manager(repo_and_service):
    repo, service = repo_and_service

    repo.request_for_approval = {"status": "REJECTED", "preferred_name": "Sam"}
    not_pending_result = service.reject_request(
        manager_id=10,
        request_id=501,
        reason="Team coverage",
    )
    assert not_pending_result["success"] is False
    assert "already rejected" in not_pending_result["error"].lower()

    repo.request_for_approval = {"status": "PENDING", "preferred_name": "Sam"}
    rejected_result = service.reject_request(
        manager_id=10,
        request_id=501,
        reason="Team coverage",
    )
    assert rejected_result["success"] is True
    assert repo.status_updates[-1] == (501, "REJECTED", 10, "Team coverage")


def test_cancel_request_enforces_ownership_and_status_rules(repo_and_service):
    repo, service = repo_and_service

    repo.request_by_id = None
    missing = service.cancel_request(employee_id=7, request_id=10)
    assert missing["success"] is False
    assert "doesn't belong to you" in missing["error"].lower()

    repo.request_by_id = {
        "employee_id": 8,
        "status": "PENDING",
        "start_date": (date.today() + timedelta(days=10)).isoformat(),
    }
    foreign = service.cancel_request(employee_id=7, request_id=10)
    assert foreign["success"] is False
    assert "doesn't belong to you" in foreign["error"].lower()

    repo.request_by_id = {
        "employee_id": 7,
        "status": "CANCELLED",
        "start_date": (date.today() + timedelta(days=10)).isoformat(),
    }
    cancelled = service.cancel_request(employee_id=7, request_id=10)
    assert cancelled["success"] is False
    assert "already cancelled" in cancelled["error"].lower()

    repo.request_by_id = {
        "employee_id": 7,
        "status": "REJECTED",
        "start_date": (date.today() + timedelta(days=10)).isoformat(),
    }
    rejected = service.cancel_request(employee_id=7, request_id=10)
    assert rejected["success"] is False
    assert "cannot cancel a rejected request" in rejected["error"].lower()


def test_cancel_request_rejects_past_time_off_and_allows_future_cancel(repo_and_service):
    repo, service = repo_and_service

    repo.request_by_id = {
        "employee_id": 7,
        "status": "PENDING",
        "start_date": (date.today() - timedelta(days=1)).isoformat(),
    }
    past = service.cancel_request(employee_id=7, request_id=11)
    assert past["success"] is False
    assert "cannot cancel past time off" in past["error"].lower()

    repo.request_by_id = {
        "employee_id": 7,
        "status": "APPROVED",
        "start_date": (date.today() + timedelta(days=3)).isoformat(),
    }
    future = service.cancel_request(employee_id=7, request_id=12)
    assert future["success"] is True
    assert repo.status_updates[-1] == (12, "CANCELLED", None, None)
    assert "has been cancelled" in future["message"].lower()


def test_get_team_calendar_returns_repo_rows(repo_and_service):
    repo, service = repo_and_service
    repo.team_calendar_rows = [
        {
            "request_id": 71,
            "employee_id": 20,
            "preferred_name": "Sam",
            "start_date": "2026-05-04",
            "end_date": "2026-05-05",
            "days": 2.0,
            "status": "APPROVED",
        }
    ]

    result = service.get_team_calendar(manager_id=10, year=2026, month=5)

    assert result == repo.team_calendar_rows

from __future__ import annotations

from datetime import date, timedelta

import pytest

from hr_agent.services import base as services_mod


class FakeHolidayRepo:
    def __init__(self):
        self.remaining = 20.0
        self.overlap = False
        self.request_for_approval: dict | None = None
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

    def update_request_status(
        self,
        request_id: int,
        status: str,
        approver_id: int | None = None,
        reason: str | None = None,
    ) -> None:
        self.status_updates.append((request_id, status, approver_id, reason))


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

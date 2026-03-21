from __future__ import annotations

import pytest

from hr_agent.policies import policy_engine as policy_engine_mod
from hr_agent.policies.policy_engine import PolicyContext, PolicyEngine


@pytest.fixture
def engine() -> PolicyEngine:
    eng = PolicyEngine()
    # Avoid DB lookups in tests; direct-report behavior is controlled by cases below.
    eng._helpers["is_direct_report"] = lambda manager_id, employee_id: (
        manager_id == 10 and employee_id == 20
    )
    return eng


@pytest.mark.parametrize(
    ("context", "expected"),
    [
        (
            PolicyContext(
                requester_id=7,
                requester_email="emp@acme.com",
                requester_role="EMPLOYEE",
                target_id=7,
                action="get_compensation",
            ),
            True,
        ),
        (
            PolicyContext(
                requester_id=7,
                requester_email="emp@acme.com",
                requester_role="EMPLOYEE",
                target_id=8,
                action="get_compensation",
            ),
            False,
        ),
        (
            PolicyContext(
                requester_id=10,
                requester_email="mgr@acme.com",
                requester_role="MANAGER",
                target_id=20,
                action="approve_holiday_request",
            ),
            True,
        ),
        (
            PolicyContext(
                requester_id=10,
                requester_email="mgr@acme.com",
                requester_role="MANAGER",
                target_id=99,
                action="approve_holiday_request",
            ),
            False,
        ),
        (
            PolicyContext(
                requester_id=3,
                requester_email="hr@acme.com",
                requester_role="HR",
                target_id=777,
                action="get_salary_history",
            ),
            True,
        ),
        (
            PolicyContext(
                requester_id=3,
                requester_email="hr@acme.com",
                requester_role="HR",
                target_id=777,
                action="nonexistent_action",
            ),
            False,
        ),
    ],
)
def test_policy_authorization_matrix(engine: PolicyEngine, context: PolicyContext, expected: bool):
    assert engine.is_allowed(context) is expected


def test_confirmation_message_falls_back_when_params_missing():
    msg = policy_engine_mod.get_confirmation_message(
        "approve_holiday_request",
        {},
    )
    assert "approve holiday request" in msg.lower()

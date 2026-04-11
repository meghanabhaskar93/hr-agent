from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

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


def test_requires_confirmation_matches_sensitive_actions():
    assert policy_engine_mod.requires_confirmation("submit_holiday_request") is True
    assert policy_engine_mod.requires_confirmation("get_company_policies") is False


def test_confirmation_message_formats_when_params_present():
    msg = policy_engine_mod.get_confirmation_message(
        "submit_holiday_request",
        {
            "days": 2,
            "start_date": "2026-06-01",
            "end_date": "2026-06-02",
        },
    )

    assert "2 days" in msg
    assert "2026-06-01" in msg
    assert "2026-06-02" in msg


def test_get_policy_engine_caches_singleton(monkeypatch):
    created: list[object] = []

    class FakePolicyEngine:
        def __init__(self):
            created.append(self)

    monkeypatch.setattr(policy_engine_mod, "_policy_engine", None)
    monkeypatch.setattr(policy_engine_mod, "PolicyEngine", FakePolicyEngine)

    first = policy_engine_mod.get_policy_engine()
    second = policy_engine_mod.get_policy_engine()

    assert first is second
    assert len(created) == 1


def test_policy_engine_skips_rules_that_raise_errors():
    engine = PolicyEngine()
    engine.rules = []
    engine.add_rule(
        policy_engine_mod.PolicyRule(
            name="broken",
            description="Raises unexpectedly",
            effect=policy_engine_mod.Effect.DENY,
            condition=lambda _ctx, _helpers: (_ for _ in ()).throw(RuntimeError("boom")),
            actions=["get_company_policies"],
            priority=100,
        )
    )
    engine.add_rule(
        policy_engine_mod.PolicyRule(
            name="fallback-allow",
            description="Allows after broken rule is skipped",
            effect=policy_engine_mod.Effect.ALLOW,
            condition=lambda _ctx, _helpers: True,
            actions=["get_company_policies"],
            priority=10,
        )
    )

    allowed = engine.is_allowed(
        PolicyContext(
            requester_id=1,
            requester_email="alex@acme.com",
            requester_role="EMPLOYEE",
            action="get_company_policies",
        )
    )

    assert allowed is True


def test_finance_cost_center_access_helper_uses_employee_and_access_tables(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "policy_helper.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as con:
        con.execute(
            text(
                """
                CREATE TABLE employee (
                    employee_id INTEGER PRIMARY KEY,
                    cost_center TEXT
                )
                """
            )
        )
        con.execute(
            text(
                """
                CREATE TABLE finance_cost_center_access (
                    user_email TEXT NOT NULL,
                    cost_center TEXT NOT NULL
                )
                """
            )
        )
        con.execute(
            text(
                """
                INSERT INTO employee (employee_id, cost_center) VALUES
                (201, 'ENG'),
                (202, 'HR')
                """
            )
        )
        con.execute(
            text(
                """
                INSERT INTO finance_cost_center_access (user_email, cost_center) VALUES
                ('finance@acme.com', 'ENG')
                """
            )
        )

    monkeypatch.setattr(policy_engine_mod, "get_engine", lambda: engine)

    assert policy_engine_mod._finance_has_cost_center_access("finance@acme.com", None) is True
    assert policy_engine_mod._finance_has_cost_center_access("finance@acme.com", 201) is True
    assert policy_engine_mod._finance_has_cost_center_access("finance@acme.com", 202) is False
    assert policy_engine_mod._finance_has_cost_center_access("finance@acme.com", 999) is False

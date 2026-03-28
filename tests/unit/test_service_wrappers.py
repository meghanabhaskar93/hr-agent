from __future__ import annotations

from types import SimpleNamespace

from hr_agent.services import base as services_mod


def test_employee_service_passthrough_and_requester_context(monkeypatch):
    repo = SimpleNamespace(
        search=lambda query, limit: [{"query": query, "limit": limit}],
        get_by_id=lambda employee_id: (
            {"employee_id": employee_id, "preferred_name": "Alex"}
            if employee_id == 201
            else None
        ),
        get_tenure=lambda employee_id: {"employee_id": employee_id, "years_of_service": 4.2},
        get_manager=lambda employee_id: {"employee_id": 101, "preferred_name": "Morgan"},
        get_direct_reports=lambda manager_id: [{"employee_id": 201}, {"employee_id": 202}],
        get_manager_chain=lambda employee_id, max_depth: [{"employee_id": 101, "depth": max_depth}],
        get_team_overview=lambda manager_id: {"manager_id": manager_id, "total_direct_reports": 2},
        get_department_members=lambda department: [{"department": department, "employee_id": 201}],
        get_org_chart=lambda root_id, max_depth: {"root_id": root_id, "max_depth": max_depth},
        get_cost_center=lambda employee_id: "ENG",
        get_employee_id_by_email=lambda email: {"alex.kim@acme.com": 201, "morgan.manager@acme.com": 101}.get(email),
        get_role_by_email=lambda email: "MANAGER" if email == "morgan.manager@acme.com" else "EMPLOYEE",
        get_direct_report_ids=lambda employee_id: [201, 202] if employee_id == 101 else [],
    )
    monkeypatch.setattr(services_mod, "get_employee_repo", lambda: repo)

    service = services_mod.EmployeeService()

    assert service.search("alex", limit=5) == [{"query": "alex", "limit": 5}]
    assert service.get_basic_info(201)["preferred_name"] == "Alex"
    assert service.get_tenure(201)["years_of_service"] == 4.2
    assert service.get_manager(201)["employee_id"] == 101
    assert service.get_direct_reports(101) == [{"employee_id": 201}, {"employee_id": 202}]
    assert service.get_manager_chain(201, max_depth=4) == [{"employee_id": 101, "depth": 4}]
    assert service.get_team_overview(101)["total_direct_reports"] == 2
    assert service.get_department_directory("Engineering") == [
        {"department": "Engineering", "employee_id": 201}
    ]
    assert service.get_org_chart(root_id=100, max_depth=2) == {"root_id": 100, "max_depth": 2}
    assert service.get_cost_center(201) == "ENG"

    employee_context = service.get_requester_context("alex.kim@acme.com")
    assert employee_context == {
        "user_email": "alex.kim@acme.com",
        "employee_id": 201,
        "name": "Alex",
        "role": "EMPLOYEE",
        "direct_reports": [],
    }

    manager_context = service.get_requester_context("morgan.manager@acme.com")
    assert manager_context["employee_id"] == 101
    assert manager_context["direct_reports"] == [201, 202]


def test_employee_service_requester_context_raises_for_unknown_email(monkeypatch):
    repo = SimpleNamespace(
        get_employee_id_by_email=lambda _email: None,
    )
    monkeypatch.setattr(services_mod, "get_employee_repo", lambda: repo)

    service = services_mod.EmployeeService()

    try:
        service.get_requester_context("missing@acme.com")
        assert False, "Expected ValueError for unknown requester email"
    except ValueError as exc:
        assert "No employee found" in str(exc)


def test_compensation_and_company_service_passthrough(monkeypatch):
    compensation_repo = SimpleNamespace(
        get_by_employee=lambda employee_id: {"employee_id": employee_id, "base_salary": 100000},
        get_salary_history=lambda employee_id: [{"employee_id": employee_id, "effective_date": "2026-01-01"}],
        get_team_summary=lambda manager_id: {"manager_employee_id": manager_id, "team_size": 2},
    )
    company_repo = SimpleNamespace(
        get_policies=lambda: [{"policy_id": 1}],
        get_policy_by_id=lambda policy_id: {"policy_id": policy_id, "title": "Leave Policy"},
        get_holidays=lambda year: [{"year": year, "name": "New Year"}],
        get_announcements=lambda limit: [{"limit": limit, "title": "Town Hall"}],
        get_upcoming_events=lambda days_ahead: [{"days_ahead": days_ahead, "title": "Offsite"}],
    )
    monkeypatch.setattr(services_mod, "get_compensation_repo", lambda: compensation_repo)
    monkeypatch.setattr(services_mod, "get_company_repo", lambda: company_repo)

    compensation_service = services_mod.CompensationService()
    company_service = services_mod.CompanyService()

    assert compensation_service.get_compensation(201)["base_salary"] == 100000
    assert compensation_service.get_salary_history(201)[0]["effective_date"] == "2026-01-01"
    assert compensation_service.get_team_summary(101)["team_size"] == 2

    assert company_service.get_policies() == [{"policy_id": 1}]
    assert company_service.get_policy_details(1)["title"] == "Leave Policy"
    assert company_service.get_holidays(2026) == [{"year": 2026, "name": "New Year"}]
    assert company_service.get_announcements(limit=3) == [{"limit": 3, "title": "Town Hall"}]
    assert company_service.get_upcoming_events(days_ahead=14) == [
        {"days_ahead": 14, "title": "Offsite"}
    ]


def test_service_singletons_cache_instances(monkeypatch):
    counters = {"employee": 0, "holiday": 0, "compensation": 0, "company": 0}

    class FakeEmployeeService:
        def __init__(self):
            counters["employee"] += 1

    class FakeHolidayService:
        def __init__(self):
            counters["holiday"] += 1

    class FakeCompensationService:
        def __init__(self):
            counters["compensation"] += 1

    class FakeCompanyService:
        def __init__(self):
            counters["company"] += 1

    monkeypatch.setattr(services_mod, "_employee_service", None)
    monkeypatch.setattr(services_mod, "_holiday_service", None)
    monkeypatch.setattr(services_mod, "_compensation_service", None)
    monkeypatch.setattr(services_mod, "_company_service", None)
    monkeypatch.setattr(services_mod, "EmployeeService", FakeEmployeeService)
    monkeypatch.setattr(services_mod, "HolidayService", FakeHolidayService)
    monkeypatch.setattr(services_mod, "CompensationService", FakeCompensationService)
    monkeypatch.setattr(services_mod, "CompanyService", FakeCompanyService)

    assert services_mod.get_employee_service() is services_mod.get_employee_service()
    assert services_mod.get_holiday_service() is services_mod.get_holiday_service()
    assert services_mod.get_compensation_service() is services_mod.get_compensation_service()
    assert services_mod.get_company_service() is services_mod.get_company_service()

    assert counters == {"employee": 1, "holiday": 1, "compensation": 1, "company": 1}

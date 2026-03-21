from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text

from hr_agent.repositories.company import CompanyRepository
from hr_agent.repositories.compensation import CompensationRepository
from hr_agent.repositories.employee import EmployeeRepository
from hr_agent.repositories.holiday import HolidayRepository


class _TestEmployeeRepository(EmployeeRepository):
    def __init__(self, engine):
        self._engine = engine

    def _get_engine(self):
        return self._engine


class _TestHolidayRepository(HolidayRepository):
    def __init__(self, engine):
        self._engine = engine

    def _get_engine(self):
        return self._engine


class _TestCompanyRepository(CompanyRepository):
    def __init__(self, engine):
        self._engine = engine

    def _get_engine(self):
        return self._engine


class _TestCompensationRepository(CompensationRepository):
    def __init__(self, engine):
        self._engine = engine

    def _get_engine(self):
        return self._engine


def _build_engine(tmp_path: Path):
    db_path = tmp_path / "repository_layer.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    today = date.today()

    with engine.begin() as con:
        con.execute(
            text(
                """
                CREATE TABLE employee (
                    employee_id INTEGER PRIMARY KEY,
                    preferred_name TEXT NOT NULL,
                    legal_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    title TEXT NOT NULL,
                    department TEXT NOT NULL,
                    location TEXT NOT NULL,
                    employment_status TEXT NOT NULL,
                    hire_date TEXT NOT NULL,
                    cost_center TEXT,
                    manager_employee_id INTEGER
                )
                """
            )
        )
        con.execute(
            text(
                """
                CREATE TABLE manager_reports (
                    manager_employee_id INTEGER NOT NULL,
                    report_employee_id INTEGER NOT NULL
                )
                """
            )
        )
        con.execute(
            text(
                """
                CREATE TABLE identity_map (
                    user_email TEXT NOT NULL,
                    employee_id INTEGER NOT NULL
                )
                """
            )
        )
        con.execute(
            text(
                """
                CREATE TABLE app_role_map (
                    user_email TEXT NOT NULL,
                    app_role TEXT NOT NULL
                )
                """
            )
        )
        con.execute(
            text(
                """
                CREATE TABLE holiday_entitlement (
                    employee_id INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    entitlement_days REAL NOT NULL,
                    carried_over_days REAL NOT NULL
                )
                """
            )
        )
        con.execute(
            text(
                """
                CREATE TABLE holiday_request (
                    request_id INTEGER PRIMARY KEY,
                    employee_id INTEGER NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    days REAL NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT,
                    requested_at TEXT NOT NULL,
                    reviewed_by INTEGER,
                    reviewed_at TEXT,
                    rejection_reason TEXT
                )
                """
            )
        )
        con.execute(
            text(
                """
                CREATE TABLE company_policy (
                    policy_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    full_text TEXT NOT NULL,
                    effective_date TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
        )
        con.execute(
            text(
                """
                CREATE TABLE company_holiday (
                    holiday_date TEXT NOT NULL,
                    name TEXT NOT NULL,
                    is_paid INTEGER NOT NULL
                )
                """
            )
        )
        con.execute(
            text(
                """
                CREATE TABLE announcement (
                    announcement_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    category TEXT NOT NULL,
                    posted_by INTEGER NOT NULL,
                    posted_at TEXT NOT NULL,
                    expires_at TEXT
                )
                """
            )
        )
        con.execute(
            text(
                """
                CREATE TABLE company_event (
                    event_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    event_time TEXT NOT NULL,
                    location TEXT NOT NULL,
                    description TEXT NOT NULL
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
                CREATE TABLE compensation (
                    employee_id INTEGER PRIMARY KEY,
                    currency TEXT NOT NULL,
                    base_salary REAL NOT NULL,
                    bonus_target_pct REAL NOT NULL,
                    equity_shares REAL NOT NULL,
                    last_review_date TEXT NOT NULL,
                    next_review_date TEXT NOT NULL
                )
                """
            )
        )
        con.execute(
            text(
                """
                CREATE TABLE salary_history (
                    employee_id INTEGER NOT NULL,
                    effective_date TEXT NOT NULL,
                    base_salary REAL NOT NULL,
                    currency TEXT NOT NULL,
                    change_reason TEXT NOT NULL,
                    change_pct REAL NOT NULL
                )
                """
            )
        )

        con.execute(
            text(
                """
                INSERT INTO employee VALUES
                (100, 'Casey', 'Casey Chief', 'casey.chief@acme.com', 'CEO', 'Executive', 'Berlin', 'ACTIVE', '2015-01-01', 'EXEC', NULL),
                (101, 'Morgan', 'Morgan Manager', 'morgan.manager@acme.com', 'Engineering Manager', 'Engineering', 'Berlin', 'ACTIVE', '2018-02-15', 'ENG', 100),
                (201, 'Alex', 'Alexander Kim', 'alex.kim@acme.com', 'Software Engineer', 'Engineering', 'Berlin', 'ACTIVE', '2020-03-01', 'ENG', 101),
                (202, 'Taylor', 'Taylor Jones', 'taylor.jones@acme.com', 'Software Engineer', 'Engineering', 'Munich', 'LEAVE', '2021-06-15', 'ENG', 101),
                (301, 'Harper', 'Harper HR', 'harper.hr@acme.com', 'HR Partner', 'HR', 'Berlin', 'ACTIVE', '2019-09-10', 'HR', 100)
                """
            )
        )
        con.execute(
            text(
                """
                INSERT INTO manager_reports VALUES
                (100, 101),
                (100, 301),
                (101, 201),
                (101, 202)
                """
            )
        )
        con.execute(
            text(
                """
                INSERT INTO identity_map VALUES
                ('alex.kim@acme.com', 201),
                ('morgan.manager@acme.com', 101)
                """
            )
        )
        con.execute(
            text(
                """
                INSERT INTO app_role_map VALUES
                ('alex.kim@acme.com', 'EMPLOYEE'),
                ('morgan.manager@acme.com', 'MANAGER'),
                ('harper.hr@acme.com', 'HR')
                """
            )
        )
        con.execute(
            text(
                """
                INSERT INTO holiday_entitlement VALUES
                (201, 2026, 25.0, 3.0),
                (202, 2026, 22.0, 1.0)
                """
            )
        )
        con.execute(
            text(
                """
                INSERT INTO holiday_request VALUES
                (1, 201, '2026-03-10', '2026-03-11', 2.0, 'APPROVED', 'Trip', '2026-02-01T09:00:00', 101, '2026-02-02T09:00:00', NULL),
                (2, 201, '2026-04-15', '2026-04-15', 1.0, 'PENDING', 'Errand', '2026-03-20T09:00:00', NULL, NULL, NULL),
                (3, 202, '2026-04-16', '2026-04-17', 2.0, 'PENDING', 'Family', '2026-03-19T09:00:00', NULL, NULL, NULL),
                (4, 202, '2026-05-03', '2026-05-03', 1.0, 'APPROVED', 'Appointment', '2026-04-20T09:00:00', 101, '2026-04-21T09:00:00', NULL)
                """
            )
        )
        con.execute(
            text(
                """
                INSERT INTO company_policy VALUES
                (1, 'Leave Policy', 'Benefits', 'PTO summary', 'Full PTO policy', '2026-01-01', '2026-02-01', 'ACTIVE'),
                (2, 'Security Policy', 'IT', 'Security summary', 'Full security policy', '2025-01-01', '2025-02-01', 'ARCHIVED')
                """
            )
        )
        con.execute(
            text(
                """
                INSERT INTO company_holiday VALUES
                ('2026-01-01', 'New Year''s Day', 1),
                ('2026-12-25', 'Christmas Day', 1)
                """
            )
        )
        con.execute(
            text(
                """
                INSERT INTO announcement VALUES
                (1, 'Fresh Update', 'Current news', 'Company', 100, '2099-01-10T10:00:00', NULL),
                (2, 'Still Active', 'Expires later', 'HR', 301, '2099-01-11T10:00:00', '2099-12-31T23:59:59'),
                (3, 'Expired', 'Old news', 'IT', 101, '2099-01-01T10:00:00', '2000-01-01T00:00:00')
                """
            )
        )
        con.execute(
            text(
                """
                INSERT INTO company_event VALUES
                (:upcoming_id, 'Town Hall', :upcoming_date, '09:00', 'Berlin', 'Company town hall'),
                (:far_id, 'Long Range Offsite', :far_date, '13:00', 'Munich', 'Far future event')
                """
            ),
            {
                "upcoming_id": 1,
                "upcoming_date": (today + timedelta(days=5)).isoformat(),
                "far_id": 2,
                "far_date": (today + timedelta(days=90)).isoformat(),
            },
        )
        con.execute(
            text(
                """
                INSERT INTO finance_cost_center_access VALUES
                ('finance@acme.com', 'ENG'),
                ('hrbp@acme.com', 'HR')
                """
            )
        )
        con.execute(
            text(
                """
                INSERT INTO compensation VALUES
                (201, 'EUR', 100000, 10, 200, '2026-01-15', '2026-12-15'),
                (202, 'EUR', 120000, 12.5, 300, '2026-01-15', '2026-12-15')
                """
            )
        )
        con.execute(
            text(
                """
                INSERT INTO salary_history VALUES
                (201, '2026-01-01', 100000, 'EUR', 'Annual review', 5.0),
                (201, '2025-01-01', 95000, 'EUR', 'Promotion', 8.0)
                """
            )
        )

    return engine


def test_employee_repository_search_org_structure_and_identity_helpers(tmp_path: Path):
    repo = _TestEmployeeRepository(_build_engine(tmp_path))

    search_results = repo.search("alex")
    assert len(search_results) == 1
    assert search_results[0]["employee_id"] == 201

    employee = repo.get_by_id(201)
    assert employee is not None
    assert employee["cost_center"] == "ENG"
    assert repo.get_by_email("alex.kim@acme.com")["preferred_name"] == "Alex"
    assert repo.get_cost_center(201) == "ENG"

    tenure = repo.get_tenure(201)
    assert tenure is not None
    assert tenure["years_of_service"] > 0

    manager = repo.get_manager(201)
    assert manager is not None
    assert manager["employee_id"] == 101

    direct_reports = repo.get_direct_reports(101)
    assert [row["employee_id"] for row in direct_reports] == [201, 202]
    assert [row["preferred_name"] for row in direct_reports] == ["Alex", "Taylor"]

    chain = repo.get_manager_chain(201)
    assert [row["employee_id"] for row in chain] == [101, 100]

    overview = repo.get_team_overview(101)
    assert overview["manager"]["preferred_name"] == "Morgan"
    assert overview["total_direct_reports"] == 2
    assert set(overview["by_department"].keys()) == {"Engineering"}

    assert repo.get_employee_id_by_email("alex.kim@acme.com") == 201
    assert repo.get_role_by_email("morgan.manager@acme.com") == "MANAGER"
    assert repo.get_role_by_email("unknown@acme.com") == "EMPLOYEE"
    assert repo.get_direct_report_ids(101) == [201, 202]
    assert repo.is_direct_report(101, 201) is True
    assert repo.is_direct_report(101, 301) is False


def test_employee_repository_department_org_chart_and_ui_helpers(tmp_path: Path):
    repo = _TestEmployeeRepository(_build_engine(tmp_path))

    members = repo.get_department_members("engineering")
    assert [row["employee_id"] for row in members] == [201, 101, 202]

    org_chart = repo.get_org_chart(root_id=100, max_depth=2)
    assert org_chart["employee_id"] == 100
    assert len(org_chart["direct_reports"]) == 2
    assert org_chart["direct_reports"][0]["employee_id"] == 101
    assert len(org_chart["direct_reports"][0]["direct_reports"]) == 2

    dropdown = repo.list_all_for_dropdown()
    assert dropdown[0]["legal_name"] == "Alexander Kim"
    assert dropdown[-1]["legal_name"] == "Taylor Jones"

    details = repo.get_details_with_manager("alex.kim@acme.com")
    assert details is not None
    assert details["manager_name"] == "Morgan Manager"


def test_holiday_repository_balance_request_and_manager_views(tmp_path: Path):
    repo = _TestHolidayRepository(_build_engine(tmp_path))

    balance = repo.get_balance(201, 2026)
    assert balance == {
        "year": 2026,
        "entitled": 25.0,
        "carried": 3.0,
        "approved_taken": 2.0,
        "pending": 1.0,
        "remaining": 25.0,
    }
    assert repo.get_balance(999, 2026)["remaining"] == 0.0

    requests = repo.get_requests(201, 2026)
    assert [row["request_id"] for row in requests] == [1, 2]
    assert repo.get_request_by_id(1)["status"] == "APPROVED"

    assert repo.has_overlapping_request(201, "2026-04-15", "2026-04-16") is True
    assert repo.has_overlapping_request(201, "2026-06-01", "2026-06-02") is False

    created_id = repo.create_request(
        employee_id=201,
        start_date="2026-06-10",
        end_date="2026-06-11",
        days=2.0,
        reason="Vacation",
    )
    created = repo.get_request_by_id(created_id)
    assert created is not None
    assert created["status"] == "PENDING"
    assert created["reason"] == "Vacation"

    pending = repo.get_pending_for_manager(101)
    assert [row["employee_id"] for row in pending] == [202, 201, 201]
    assert repo.get_request_for_approval(101, 3)["preferred_name"] == "Taylor"

    team_calendar = repo.get_team_calendar(101, 2026, 5)
    assert len(team_calendar) == 1
    assert team_calendar[0]["request_id"] == 4


def test_holiday_repository_updates_status_for_review_and_non_review_paths(tmp_path: Path):
    repo = _TestHolidayRepository(_build_engine(tmp_path))

    assert repo.update_request_status(2, "CANCELLED") is True
    cancelled = repo.get_request_by_id(2)
    assert cancelled is not None
    assert cancelled["status"] == "CANCELLED"

    assert repo.update_request_status(3, "REJECTED", reviewer_id=101, reason="Coverage") is True
    rejected = repo.get_request_for_approval(101, 3)
    assert rejected is not None
    assert rejected["status"] == "REJECTED"


def test_company_repository_filters_active_current_and_upcoming_records(tmp_path: Path):
    repo = _TestCompanyRepository(_build_engine(tmp_path))

    policies = repo.get_policies()
    assert len(policies) == 1
    assert policies[0]["title"] == "Leave Policy"

    policy = repo.get_policy_by_id(1)
    assert policy is not None
    assert policy["full_text"] == "Full PTO policy"

    holidays = repo.get_holidays(2026)
    assert [row["name"] for row in holidays] == ["New Year's Day", "Christmas Day"]

    announcements = repo.get_announcements(limit=5)
    assert [row["announcement_id"] for row in announcements] == [2, 1]

    events = repo.get_upcoming_events(days_ahead=30)
    assert len(events) == 1
    assert events[0]["title"] == "Town Hall"

    assert repo.has_cost_center_access("finance@acme.com", "ENG") is True
    assert repo.has_cost_center_access("finance@acme.com", "HR") is False


def test_compensation_repository_calculates_employee_and_team_summary(tmp_path: Path):
    repo = _TestCompensationRepository(_build_engine(tmp_path))

    compensation = repo.get_by_employee(201)
    assert compensation is not None
    assert compensation["preferred_name"] == "Alex"
    assert compensation["bonus_target_amount"] == 10000.0
    assert compensation["total_target_compensation"] == 110000.0
    assert repo.get_by_employee(999) is None

    history = repo.get_salary_history(201)
    assert [row["effective_date"] for row in history] == ["2026-01-01", "2025-01-01"]

    summary = repo.get_team_summary(101)
    assert summary["manager_employee_id"] == 101
    assert summary["team_size"] == 2
    assert summary["total_payroll"] == 220000.0
    assert summary["average_salary"] == 110000.0
    assert summary["min_salary"] == 100000.0
    assert summary["max_salary"] == 120000.0
    assert [row["employee_id"] for row in summary["team_members"]] == [202, 201]

    assert repo.get_team_summary(301) == {"error": "No direct reports found"}

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text

from hr_agent.repositories.hr_request import HRRequestRepository
from hr_agent.services.base import HRRequestService


class _TestHRRequestRepository(HRRequestRepository):
    def __init__(self, engine):
        self._engine = engine

    def _get_engine(self):
        return self._engine


class _FakeEmployeeRepo:
    def __init__(self, role_by_email: dict[str, str]):
        self.role_by_email = role_by_email
        self.employee_by_email = {
            "alex.kim@acme.com": {"employee_id": 201, "email": "alex.kim@acme.com"},
            "amanda.foster@acme.com": {
                "employee_id": 103,
                "email": "amanda.foster@acme.com",
            },
            "james.wilson@acme.com": {
                "employee_id": 112,
                "email": "james.wilson@acme.com",
            },
            "emma.thompson@acme.com": {
                "employee_id": 212,
                "email": "emma.thompson@acme.com",
            },
        }

    def get_role_by_email(self, email: str) -> str:
        return self.role_by_email.get(email, "EMPLOYEE")

    def get_by_email(self, email: str):
        return self.employee_by_email.get(email)


def _build_engine(tmp_path: Path):
    db_path = tmp_path / "hr_request_test.db"
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
                CREATE TABLE hr_request (
                    request_id INTEGER PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    requester_user_id TEXT NOT NULL,
                    requester_role TEXT NOT NULL,
                    subject_employee_id INTEGER NULL,
                    type TEXT NOT NULL,
                    subtype TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    description TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    sla_due_at TEXT NULL,
                    status TEXT NOT NULL,
                    assignee_user_id TEXT NULL,
                    required_fields_json TEXT NOT NULL,
                    captured_fields_json TEXT NOT NULL,
                    missing_fields_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_action_at TEXT NOT NULL,
                    resolution_text TEXT NULL,
                    resolution_sources_json TEXT NULL,
                    escalation_ticket_id TEXT NULL,
                    last_message_to_requester TEXT NULL,
                    last_message_at TEXT NULL
                )
                """
            )
        )
        con.execute(
            text(
                """
                CREATE TABLE hr_request_event (
                    event_id INTEGER PRIMARY KEY,
                    request_id INTEGER NOT NULL,
                    tenant_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_note TEXT NULL,
                    actor_user_id TEXT NULL,
                    actor_role TEXT NULL,
                    payload_json TEXT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
        )
        con.execute(
            text(
                """
                INSERT INTO employee VALUES
                (103, 'Amanda', 'amanda.foster@acme.com', 'Executive', 'CTO'),
                (112, 'James', 'james.wilson@acme.com', 'HR', 'HR Lead'),
                (201, 'Alex', 'alex.kim@acme.com', 'Engineering', 'Engineer'),
                (212, 'Emma', 'emma.thompson@acme.com', 'Engineering', 'Engineer')
                """
            )
        )
    return engine


def test_hr_request_service_permissions_transitions_and_audit(tmp_path: Path):
    repo = _TestHRRequestRepository(_build_engine(tmp_path))
    service = HRRequestService()
    service.repo = repo
    service.employee_repo = _FakeEmployeeRepo(
        {
            "alex.kim@acme.com": "EMPLOYEE",
            "amanda.foster@acme.com": "HR",
            "james.wilson@acme.com": "HR",
            "emma.thompson@acme.com": "EMPLOYEE",
        }
    )

    created = service.create_request(
        requester_user_id="alex.kim@acme.com",
        requester_role="EMPLOYEE",
        request_type="ESCALATION",
        request_subtype="PAYROLL",
        summary="Need payroll correction",
        description="My net pay is lower than expected for March.",
        priority="P1",
        risk_level="MED",
        required_fields=[
            "summary",
            "description",
            "requester_user_id",
            "type",
            "subtype",
            "agent_suggestion",
        ],
        captured_fields={"agent_suggestion": "Review payroll adjustment history."},
    )
    assert created["success"] is True
    request_id = created["request_id"]

    denied_assign = service.assign_request(
        viewer_email="alex.kim@acme.com",
        request_id=request_id,
        assignee_user_id="james.wilson@acme.com",
    )
    assert denied_assign["success"] is False
    assert "Only HR/Manager" in denied_assign["error"]

    assigned = service.assign_request(
        viewer_email="amanda.foster@acme.com",
        request_id=request_id,
        assignee_user_id="james.wilson@acme.com",
    )
    assert assigned["success"] is True
    assigned_row = repo.get_by_id(request_id)
    assert assigned_row is not None
    assert assigned_row["status"] == "IN_PROGRESS"

    asked_for_info = service.message_requester(
        viewer_email="amanda.foster@acme.com",
        request_id=request_id,
        message="Please share your March payslip screenshot.",
    )
    assert asked_for_info["success"] is True

    denied_reply = service.reply_as_requester(
        viewer_email="amanda.foster@acme.com",
        request_id=request_id,
        message="This should fail for HR user.",
    )
    assert denied_reply["success"] is False
    assert "Only requester" in denied_reply["error"]

    replied = service.reply_as_requester(
        viewer_email="alex.kim@acme.com",
        request_id=request_id,
        message="Uploaded. The mismatch is on bonus line item.",
    )
    assert replied["success"] is True

    resolved_after_confirmation = service.transition_status(
        viewer_email="amanda.foster@acme.com",
        request_id=request_id,
        new_status="RESOLVED",
        resolution_text="Thanks for the clarification. Resolving now.",
    )
    assert resolved_after_confirmation["success"] is True

    reopened_to_work = service.transition_status(
        viewer_email="amanda.foster@acme.com",
        request_id=request_id,
        new_status="IN_PROGRESS",
    )
    assert reopened_to_work["success"] is True

    captured = service.capture_fields(
        viewer_email="alex.kim@acme.com",
        request_id=request_id,
        captured_fields={"payslip_month": "2026-03", "bonus_line_item": "Missing"},
    )
    assert captured["success"] is True
    assert captured["status"] == "IN_PROGRESS"

    escalated = service.escalate_request(
        viewer_email="amanda.foster@acme.com",
        request_id=request_id,
        escalation_ticket_id="PAY-100",
        note="Handing off to payroll vendor.",
    )
    assert escalated["success"] is True

    resolved = service.transition_status(
        viewer_email="amanda.foster@acme.com",
        request_id=request_id,
        new_status="RESOLVED",
        resolution_text="Payroll corrected in next run.",
        resolution_sources=["Payroll Policy v4.2"],
    )
    assert resolved["success"] is True

    row = repo.get_by_id(request_id)
    assert row is not None
    assert row["status"] == "RESOLVED"
    assert row["assignee_user_id"] == "james.wilson@acme.com"
    assert row["escalation_ticket_id"] == "PAY-100"
    assert row["resolution_text"] == "Payroll corrected in next run."
    assert row["resolution_sources"] == ["Payroll Policy v4.2"]
    assert row["last_message_to_requester"] == "Please share your March payslip screenshot."

    detail = service.get_request_detail("amanda.foster@acme.com", request_id)
    assert detail["success"] is True
    assert detail["completeness_percent"] == 100
    assert len(detail["timeline"]) >= 7
    assert any(event["event_type"] == "REQUESTER_REPLY" for event in detail["timeline"])

    hidden = service.get_request_detail("emma.thompson@acme.com", request_id)
    assert hidden["success"] is False

    created_two = service.create_request(
        requester_user_id="alex.kim@acme.com",
        requester_role="EMPLOYEE",
        request_type="ESCALATION",
        request_subtype="POLICY",
        summary="Need policy clarification",
        description="Need a follow-up on leave policy edge case.",
    )
    assert created_two["success"] is True
    invalid_transition = service.transition_status(
        viewer_email="amanda.foster@acme.com",
        request_id=created_two["request_id"],
        new_status="RESOLVED",
    )
    assert invalid_transition["success"] is False
    assert "Invalid transition" in invalid_transition["error"]

    hr_counts = service.list_counts("amanda.foster@acme.com")
    assert hr_counts["total"] == 2
    assert hr_counts["resolved"] == 1
    assert hr_counts["new"] == 1

    requester_counts = service.list_counts("alex.kim@acme.com")
    assert requester_counts["total"] == 2
    assert requester_counts["resolved"] == 1


def test_hr_request_service_employee_intake_classification_defaults(tmp_path: Path):
    repo = _TestHRRequestRepository(_build_engine(tmp_path))
    service = HRRequestService()
    service.repo = repo
    service.employee_repo = _FakeEmployeeRepo(
        {
            "alex.kim@acme.com": "EMPLOYEE",
            "amanda.foster@acme.com": "HR",
            "james.wilson@acme.com": "HR",
            "emma.thompson@acme.com": "EMPLOYEE",
        }
    )

    travel = service.create_request(
        requester_user_id="alex.kim@acme.com",
        requester_role="EMPLOYEE",
        request_type="ESCALATION",
        request_subtype="GENERAL",
        summary="Reimbursement claim for taxi",
        description="I need to file travel reimbursement for a taxi ride.",
    )
    assert travel["success"] is True
    travel_row = repo.get_by_id(travel["request_id"])
    assert travel_row is not None
    assert travel_row["type"] == "CLAIMS"
    assert travel_row["subtype"] == "TRAVEL"
    assert travel_row["priority"] == "P1"
    assert travel_row["risk_level"] == "MED"
    assert travel_row["sla_due_at"] is not None
    assert "amount" in travel_row["required_fields"]
    assert "date" in travel_row["required_fields"]
    assert "receipt" in travel_row["required_fields"]
    assert "cost_center" not in travel_row["required_fields"]
    assert "cost_center" in (travel_row.get("captured_fields") or {}).get(
        "optional_fields", []
    )

    payroll = service.create_request(
        requester_user_id="alex.kim@acme.com",
        requester_role="EMPLOYEE",
        request_type="ESCALATION",
        request_subtype="GENERAL",
        summary="Why is my salary lower?",
        description="My March payroll seems lower than expected.",
    )
    assert payroll["success"] is True
    payroll_row = repo.get_by_id(payroll["request_id"])
    assert payroll_row is not None
    assert payroll_row["type"] == "PAYROLL"
    assert payroll_row["subtype"] == "DEDUCTION_QUERY"
    assert payroll_row["priority"] == "P0"
    assert payroll_row["risk_level"] == "HIGH"
    assert payroll_row["sla_due_at"] is not None
    assert "month" in payroll_row["required_fields"]
    assert "payslip_id" not in payroll_row["required_fields"]
    assert "payslip_id" in (payroll_row.get("captured_fields") or {}).get(
        "optional_fields", []
    )

    policy = service.create_request(
        requester_user_id="alex.kim@acme.com",
        requester_role="EMPLOYEE",
        request_type="ESCALATION",
        request_subtype="GENERAL",
        summary="What is remote policy?",
        description="Can you share the remote work policy for engineering?",
    )
    assert policy["success"] is True
    policy_row = repo.get_by_id(policy["request_id"])
    assert policy_row is not None
    assert policy_row["type"] == "POLICY"
    assert policy_row["subtype"] == "REMOTE_WORK"
    assert policy_row["priority"] == "P2"
    assert policy_row["risk_level"] == "LOW"
    assert policy_row["sla_due_at"] is not None


def test_hr_request_service_triage_queue_derives_effective_status_and_filtering(
    tmp_path: Path,
):
    repo = _TestHRRequestRepository(_build_engine(tmp_path))
    service = HRRequestService()
    service.repo = repo
    service.employee_repo = _FakeEmployeeRepo(
        {
            "alex.kim@acme.com": "EMPLOYEE",
            "amanda.foster@acme.com": "HR",
            "james.wilson@acme.com": "HR",
            "emma.thompson@acme.com": "EMPLOYEE",
        }
    )

    ready_created = service.create_request(
        requester_user_id="amanda.foster@acme.com",
        requester_role="HR",
        request_type="PAYROLL",
        request_subtype="GENERAL",
        summary="Payroll adjustment request",
        description="Need to adjust one payroll item.",
        priority="P0",
        risk_level="HIGH",
    )
    assert ready_created["success"] is True

    needs_info_created = service.create_request(
        requester_user_id="amanda.foster@acme.com",
        requester_role="HR",
        request_type="PAYROLL",
        request_subtype="GENERAL",
        summary="Payroll deduction missing data",
        description="Need month before processing payroll deduction query.",
        priority="P0",
        risk_level="HIGH",
        required_fields=[
            "summary",
            "description",
            "requester_user_id",
            "type",
            "subtype",
            "month",
        ],
    )
    assert needs_info_created["success"] is True

    queue = service.list_requests("amanda.foster@acme.com")
    assert len(queue) == 2
    assert queue[0]["request_id"] == ready_created["request_id"]
    assert queue[0]["status"] == "READY"
    assert queue[1]["request_id"] == needs_info_created["request_id"]
    assert queue[1]["status"] == "NEEDS_INFO"

    needs_info_only = service.list_requests(
        "amanda.foster@acme.com", status="NEEDS_INFO"
    )
    assert len(needs_info_only) == 1
    assert needs_info_only[0]["request_id"] == needs_info_created["request_id"]
    assert needs_info_only[0]["status"] == "NEEDS_INFO"


def test_hr_request_service_helper_methods_and_edge_cases(tmp_path: Path):
    repo = _TestHRRequestRepository(_build_engine(tmp_path))
    service = HRRequestService()
    service.repo = repo
    service.employee_repo = _FakeEmployeeRepo(
        {
            "alex.kim@acme.com": "EMPLOYEE",
            "amanda.foster@acme.com": "HR",
            "james.wilson@acme.com": "HR",
            "emma.thompson@acme.com": "EMPLOYEE",
        }
    )

    assert service._normalize_required_fields(None) == service.DEFAULT_REQUIRED_FIELDS
    assert service._normalize_required_fields([" summary ", "summary", "", "type"]) == [
        "summary",
        "type",
    ]

    missing = service._compute_missing_fields(
        ["summary", "description", "files", "metadata"],
        {"summary": "ok", "description": "   ", "files": [], "metadata": {}},
    )
    assert missing == ["description", "files", "metadata"]

    assert service._normalize_taxonomy_value("payroll / tax-adjustment", "GENERAL") == "PAYROLL___TAX_ADJUSTMENT"
    assert service._normalize_taxonomy_value(" ", "GENERAL") == "GENERAL"

    assert service._to_datetime("2026-03-21T10:00:00") is not None
    assert service._to_datetime("not-a-date") is None
    assert service._default_sla_hours("P0", "LOW") == 24
    assert service._default_sla_hours("P2", "HIGH") == 24

    resolved_sla = service._resolve_sla_due_at(
        priority="P1",
        risk_level="MED",
        requested_sla_due_at=None,
        created_at="2026-03-01T00:00:00",
    )
    assert resolved_sla.startswith("2026-03-04T00:00:00")

    assert service._is_ready_like("READY") is True
    assert service._is_ready_like("IN_PROGRESS") is True
    assert service._is_ready_like("NEEDS_INFO") is False

    assert (
        service._should_keep_needs_info_ahead(
            {"priority": "P0", "sla_due_at": "2026-03-01T10:00:00"},
            {"priority": "P1", "sla_due_at": "2026-03-02T10:00:00"},
        )
        is True
    )
    assert (
        service._should_keep_needs_info_ahead(
            {"priority": "P1", "sla_due_at": "2026-03-01T10:00:00"},
            {"priority": "P0", "sla_due_at": "2026-03-02T10:00:00"},
        )
        is False
    )

    ready_row = {
        "request_id": 2,
        "priority": "P0",
        "risk_level": "HIGH",
        "sla_due_at": "2026-03-01T10:00:00",
        "status": "READY",
        "created_at": "2026-02-01T10:00:00",
    }
    needs_info_row = {
        "request_id": 3,
        "priority": "P0",
        "risk_level": "HIGH",
        "sla_due_at": "2026-03-02T10:00:00",
        "status": "NEEDS_INFO",
        "created_at": "2026-02-01T11:00:00",
    }
    assert service._compare_queue_rows(ready_row, needs_info_row) == -1

    applied = service._apply_queue_defaults(
        {
            "request_id": 4,
            "priority": "P1",
            "risk_level": "MED",
            "status": "NEW",
            "missing_fields": [],
            "created_at": "2026-03-01T10:00:00",
            "sla_due_at": None,
        }
    )
    assert applied["status"] == "READY"
    assert applied["sla_due_at"] is not None

    invalid_priority = service.create_request(
        requester_user_id="alex.kim@acme.com",
        requester_role="EMPLOYEE",
        request_type="GENERAL",
        request_subtype="GENERAL",
        summary="Hello",
        description="Need help",
        priority="PX",
    )
    assert invalid_priority["success"] is False
    assert "invalid priority" in invalid_priority["error"].lower()

    invalid_risk = service.create_request(
        requester_user_id="alex.kim@acme.com",
        requester_role="EMPLOYEE",
        request_type="GENERAL",
        request_subtype="GENERAL",
        summary="Hello",
        description="Need help",
        risk_level="SEVERE",
    )
    assert invalid_risk["success"] is False
    assert "invalid risk level" in invalid_risk["error"].lower()

    missing_text = service.create_request(
        requester_user_id="alex.kim@acme.com",
        requester_role="EMPLOYEE",
        request_type="GENERAL",
        request_subtype="GENERAL",
        summary="   ",
        description="   ",
    )
    assert missing_text["success"] is False
    assert "summary and description are required" in missing_text["error"].lower()

    request = service.create_request(
        requester_user_id="alex.kim@acme.com",
        requester_role="EMPLOYEE",
        request_type="GENERAL",
        request_subtype="GENERAL",
        summary="Need general help",
        description="Need more information.",
    )
    assert request["success"] is True
    request_id = request["request_id"]

    assert service.list_requests("amanda.foster@acme.com", status="INVALID") == []
    requester_list = service.list_requests("alex.kim@acme.com", status="NEW")
    assert len(requester_list) == 1
    assert requester_list[0]["request_id"] == request_id

    assert service.get_request_detail("emma.thompson@acme.com", request_id)["success"] is False

    assign_missing = service.assign_request(
        viewer_email="amanda.foster@acme.com",
        request_id=request_id,
        assignee_user_id="missing@acme.com",
    )
    assert assign_missing["success"] is False
    assert "assignee not found" in assign_missing["error"].lower()

    invalid_priority_update = service.update_priority(
        viewer_email="amanda.foster@acme.com",
        request_id=request_id,
        priority="PX",
    )
    assert invalid_priority_update["success"] is False
    assert "invalid priority" in invalid_priority_update["error"].lower()

    invalid_status = service.transition_status(
        viewer_email="amanda.foster@acme.com",
        request_id=request_id,
        new_status="DONE",
    )
    assert invalid_status["success"] is False
    assert "invalid status" in invalid_status["error"].lower()

    missing_transition = service.transition_status(
        viewer_email="amanda.foster@acme.com",
        request_id=9999,
        new_status="READY",
    )
    assert missing_transition["success"] is False
    assert "not found" in missing_transition["error"].lower()

    empty_message = service.message_requester(
        viewer_email="amanda.foster@acme.com",
        request_id=request_id,
        message="   ",
    )
    assert empty_message["success"] is False
    assert "cannot be empty" in empty_message["error"].lower()

    empty_reply = service.reply_as_requester(
        viewer_email="alex.kim@acme.com",
        request_id=request_id,
        message="   ",
    )
    assert empty_reply["success"] is False
    assert "cannot be empty" in empty_reply["error"].lower()

    closed = service.transition_status(
        viewer_email="amanda.foster@acme.com",
        request_id=request_id,
        new_status="CANCELLED",
    )
    assert closed["success"] is True

    message_closed = service.message_requester(
        viewer_email="amanda.foster@acme.com",
        request_id=request_id,
        message="Need more info",
    )
    assert message_closed["success"] is False
    assert "closed request" in message_closed["error"].lower()

    reply_closed = service.reply_as_requester(
        viewer_email="alex.kim@acme.com",
        request_id=request_id,
        message="Here you go",
    )
    assert reply_closed["success"] is False
    assert "closed request" in reply_closed["error"].lower()

    capture_closed = service.capture_fields(
        viewer_email="alex.kim@acme.com",
        request_id=request_id,
        captured_fields={"extra": "value"},
    )
    assert capture_closed["success"] is False
    assert "closed request" in capture_closed["error"].lower()


def test_hr_request_service_capture_fields_and_escalation_paths(tmp_path: Path):
    repo = _TestHRRequestRepository(_build_engine(tmp_path))
    service = HRRequestService()
    service.repo = repo
    service.employee_repo = _FakeEmployeeRepo(
        {
            "alex.kim@acme.com": "EMPLOYEE",
            "amanda.foster@acme.com": "HR",
            "james.wilson@acme.com": "HR",
            "emma.thompson@acme.com": "EMPLOYEE",
        }
    )

    created = service.create_request(
        requester_user_id="alex.kim@acme.com",
        requester_role="EMPLOYEE",
        request_type="ESCALATION",
        request_subtype="POLICY",
        summary="Need policy clarification",
        description="Need details for a policy exception.",
        required_fields=["summary", "description", "requester_user_id", "type", "subtype", "details"],
    )
    assert created["success"] is True
    request_id = created["request_id"]

    first_capture = service.capture_fields(
        viewer_email="alex.kim@acme.com",
        request_id=request_id,
        captured_fields={"details": ""},
    )
    assert first_capture["success"] is True
    assert first_capture["status"] == "NEEDS_INFO"
    assert "details" in first_capture["missing_fields"]

    second_capture = service.capture_fields(
        viewer_email="alex.kim@acme.com",
        request_id=request_id,
        captured_fields={"details": "Manager approved exception note"},
    )
    assert second_capture["success"] is True
    assert second_capture["status"] == "READY"
    assert second_capture["missing_fields"] == []

    hidden_capture = service.capture_fields(
        viewer_email="emma.thompson@acme.com",
        request_id=request_id,
        captured_fields={"details": "nope"},
    )
    assert hidden_capture["success"] is False
    assert "not found" in hidden_capture["error"].lower()

    escalated = service.escalate_request(
        viewer_email="amanda.foster@acme.com",
        request_id=request_id,
        escalation_ticket_id="POL-77",
        note="Need policy board review.",
    )
    assert escalated["success"] is True

    row = repo.get_by_id(request_id)
    assert row is not None
    assert row["status"] == "ESCALATED"
    assert row["escalation_ticket_id"] == "POL-77"

    reopen = service.transition_status(
        viewer_email="amanda.foster@acme.com",
        request_id=request_id,
        new_status="IN_PROGRESS",
    )
    assert reopen["success"] is True

    resolved = service.transition_status(
        viewer_email="amanda.foster@acme.com",
        request_id=request_id,
        new_status="RESOLVED",
        resolution_text="Policy board approved exception.",
        resolution_sources=["Policy Handbook"],
    )
    assert resolved["success"] is True

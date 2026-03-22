"""
Service Layer - Business Logic

This layer contains all business logic and uses repositories for data access.
Services are the main interface that tools/agent should use.

Benefits:
- Business logic is separated from data access
- Easy to test with mock repositories
- Clear, readable operations without SQL
"""

from datetime import datetime, date, timedelta
from functools import cmp_to_key
from typing import Any
from ..repositories import (
    EmployeeRepository,
    HolidayRepository,
    CompensationRepository,
    CompanyRepository,
    EscalationRepository,
    HRRequestRepository,
    get_employee_repo,
    get_holiday_repo,
    get_compensation_repo,
    get_company_repo,
    get_escalation_repo,
    get_hr_request_repo,
)


# ============================================================================
# EMPLOYEE SERVICE
# ============================================================================


class EmployeeService:
    """Service for employee and organization operations."""

    def __init__(self) -> None:
        self.repo: EmployeeRepository = get_employee_repo()

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search employees by name, email, or title."""
        return self.repo.search(query, limit)

    def get_basic_info(self, employee_id: int) -> dict | None:
        """Get basic employee information."""
        return self.repo.get_by_id(employee_id)

    def get_tenure(self, employee_id: int) -> dict | None:
        """Get employee tenure information."""
        return self.repo.get_tenure(employee_id)

    def get_manager(self, employee_id: int) -> dict | None:
        """Get the direct manager of an employee."""
        return self.repo.get_manager(employee_id)

    def get_direct_reports(self, manager_id: int) -> list[dict]:
        """Get all direct reports for a manager."""
        return self.repo.get_direct_reports(manager_id)

    def get_manager_chain(self, employee_id: int, max_depth: int = 6) -> list[dict]:
        """Get the full management chain up to CEO."""
        return self.repo.get_manager_chain(employee_id, max_depth)

    def get_team_overview(self, manager_id: int) -> dict:
        """Get a summary of a manager's team."""
        return self.repo.get_team_overview(manager_id)

    def get_department_directory(self, department: str) -> list[dict]:
        """Get all employees in a department."""
        return self.repo.get_department_members(department)

    def get_org_chart(self, root_id: int | None = None, max_depth: int = 3) -> dict:
        """Get organizational chart."""
        return self.repo.get_org_chart(root_id, max_depth)

    def get_cost_center(self, employee_id: int) -> str | None:
        """Get employee's cost center."""
        return self.repo.get_cost_center(employee_id)

    def get_requester_context(self, user_email: str) -> dict:
        """Get full context for a requester (used by agent)."""
        emp_id = self.repo.get_employee_id_by_email(user_email)
        if emp_id is None:
            raise ValueError(f"No employee found for email: {user_email}")

        role = self.repo.get_role_by_email(user_email)
        emp = self.repo.get_by_id(emp_id)
        name = emp["preferred_name"] if emp else "Unknown"

        direct_reports = []
        if role in ("MANAGER", "HR"):
            direct_reports = self.repo.get_direct_report_ids(emp_id)

        return {
            "user_email": user_email,
            "employee_id": emp_id,
            "name": name,
            "role": role,
            "direct_reports": direct_reports,
        }


# ============================================================================
# HOLIDAY SERVICE
# ============================================================================


class HolidayService:
    """Service for holiday/time-off operations."""

    def __init__(self) -> None:
        self.repo: HolidayRepository = get_holiday_repo()

    def get_balance(self, employee_id: int, year: int) -> dict:
        """Get holiday balance for an employee."""
        return self.repo.get_balance(employee_id, year)

    def get_requests(self, employee_id: int, year: int) -> list[dict]:
        """Get all holiday requests for an employee."""
        return self.repo.get_requests(employee_id, year)

    def submit_request(
        self,
        employee_id: int,
        start_date: str,
        end_date: str,
        days: float,
        reason: str | None = None,
    ) -> dict:
        """Submit a new holiday request."""
        # Validate dates
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return {"success": False, "error": "Invalid date format. Use YYYY-MM-DD."}

        if end < start:
            return {"success": False, "error": "End date must be after start date."}
        if start < date.today():
            return {"success": False, "error": "Cannot request time off in the past."}

        # Check balance
        balance = self.get_balance(employee_id, start.year)
        if balance["remaining"] < days:
            return {
                "success": False,
                "error": f"Insufficient balance. You have {balance['remaining']} days remaining but requested {days} days.",
            }

        # Check for overlapping requests
        if self.repo.has_overlapping_request(employee_id, start_date, end_date):
            return {
                "success": False,
                "error": "You already have a request overlapping these dates.",
            }

        # Create request
        request_id = self.repo.create_request(
            employee_id, start_date, end_date, days, reason
        )

        return {
            "success": True,
            "request_id": request_id,
            "message": f"Holiday request submitted for {days} days ({start_date} to {end_date}). Status: PENDING.",
        }

    def cancel_request(self, employee_id: int, request_id: int) -> dict:
        """Cancel a holiday request."""
        request = self.repo.get_request_by_id(request_id)

        if not request or request["employee_id"] != employee_id:
            return {
                "success": False,
                "error": "Request not found or doesn't belong to you.",
            }

        if request["status"] == "CANCELLED":
            return {"success": False, "error": "This request is already cancelled."}
        if request["status"] == "REJECTED":
            return {"success": False, "error": "Cannot cancel a rejected request."}

        start = datetime.strptime(request["start_date"], "%Y-%m-%d").date()
        if start < date.today():
            return {"success": False, "error": "Cannot cancel past time off."}

        self.repo.update_request_status(request_id, "CANCELLED")

        return {
            "success": True,
            "message": f"Holiday request {request_id} has been cancelled.",
        }

    def get_pending_approvals(self, manager_id: int) -> list[dict]:
        """Get pending requests for a manager's direct reports."""
        return self.repo.get_pending_for_manager(manager_id)

    def approve_request(self, manager_id: int, request_id: int) -> dict:
        """Approve a holiday request."""
        request = self.repo.get_request_for_approval(manager_id, request_id)

        if not request:
            return {
                "success": False,
                "error": "Request not found or you're not the manager.",
            }
        if request["status"] != "PENDING":
            return {
                "success": False,
                "error": f"Request is already {request['status']}.",
            }

        self.repo.update_request_status(request_id, "APPROVED", manager_id)

        return {
            "success": True,
            "message": f"Holiday request for {request['preferred_name']} has been approved.",
        }

    def reject_request(
        self, manager_id: int, request_id: int, reason: str | None = None
    ) -> dict:
        """Reject a holiday request."""
        request = self.repo.get_request_for_approval(manager_id, request_id)

        if not request:
            return {
                "success": False,
                "error": "Request not found or you're not the manager.",
            }
        if request["status"] != "PENDING":
            return {
                "success": False,
                "error": f"Request is already {request['status']}.",
            }

        self.repo.update_request_status(request_id, "REJECTED", manager_id, reason)

        return {
            "success": True,
            "message": f"Holiday request for {request['preferred_name']} has been rejected.",
        }

    def get_team_calendar(
        self, manager_id: int, year: int, month: int | None = None
    ) -> list[dict]:
        """Get approved time off for the team."""
        return self.repo.get_team_calendar(manager_id, year, month)


# ============================================================================
# COMPENSATION SERVICE
# ============================================================================


class CompensationService:
    """Service for compensation operations."""

    def __init__(self) -> None:
        self.repo: CompensationRepository = get_compensation_repo()

    def get_compensation(self, employee_id: int) -> dict | None:
        """Get compensation details for an employee."""
        return self.repo.get_by_employee(employee_id)

    def get_salary_history(self, employee_id: int) -> list[dict]:
        """Get salary history for an employee."""
        return self.repo.get_salary_history(employee_id)

    def get_team_summary(self, manager_id: int) -> dict:
        """Get compensation summary for a manager's team."""
        return self.repo.get_team_summary(manager_id)


# ============================================================================
# COMPANY SERVICE
# ============================================================================


class CompanyService:
    """Service for company-wide information."""

    def __init__(self) -> None:
        self.repo: CompanyRepository = get_company_repo()

    def get_policies(self) -> list[dict]:
        """Get list of company policies."""
        return self.repo.get_policies()

    def get_policy_details(self, policy_id: int) -> dict | None:
        """Get full details of a company policy."""
        return self.repo.get_policy_by_id(policy_id)

    def get_holidays(self, year: int) -> list[dict]:
        """Get company holidays for a year."""
        return self.repo.get_holidays(year)

    def get_announcements(self, limit: int = 10) -> list[dict]:
        """Get recent announcements."""
        return self.repo.get_announcements(limit)

    def get_upcoming_events(self, days_ahead: int = 30) -> list[dict]:
        """Get upcoming company events."""
        return self.repo.get_upcoming_events(days_ahead)


# ============================================================================
# ESCALATION SERVICE
# ============================================================================


class EscalationService:
    """Service for human-in-the-loop escalation workflow."""

    ALLOWED_STATUSES = {"PENDING", "IN_REVIEW", "RESOLVED"}
    ALLOWED_PRIORITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    ALLOWED_TRANSITIONS: dict[str, set[str]] = {
        "PENDING": {"IN_REVIEW"},
        "IN_REVIEW": {"RESOLVED"},
        "RESOLVED": {"IN_REVIEW"},
    }
    TRIAGE_ROLES = {"HR", "MANAGER"}

    def __init__(self) -> None:
        self.repo: EscalationRepository = get_escalation_repo()
        self.employee_repo: EmployeeRepository = get_employee_repo()

    def _get_viewer_role(self, viewer_email: str) -> str:
        return self.employee_repo.get_role_by_email(viewer_email)

    def _is_triage_role(self, viewer_email: str, viewer_role: str | None = None) -> bool:
        role = viewer_role if viewer_role is not None else self._get_viewer_role(viewer_email)
        return role in self.TRIAGE_ROLES

    def _get_visible_request(
        self, viewer_email: str, escalation_id: int, viewer_role: str | None = None
    ) -> dict | None:
        row = self.repo.get_by_id(escalation_id)
        if not row:
            return None
        if self._is_triage_role(viewer_email, viewer_role):
            return row
        if row["requester_email"] == viewer_email:
            return row
        return None

    @staticmethod
    def _compute_missing_fields(row: dict) -> list[str]:
        required_fields = {
            "priority": row.get("priority"),
            "category": row.get("category"),
            "assigned_to_email": row.get("assigned_to_email"),
            "agent_suggestion": row.get("agent_suggestion"),
        }
        return [key for key, value in required_fields.items() if not value]

    def create_request(
        self,
        requester_employee_id: int,
        requester_email: str,
        thread_id: str,
        source_message_excerpt: str,
        priority: str = "MEDIUM",
        category: str | None = None,
        agent_suggestion: str | None = None,
    ) -> dict:
        """Create a PENDING escalation request."""
        normalized_priority = priority.upper()
        if normalized_priority not in self.ALLOWED_PRIORITIES:
            return {"success": False, "error": "Invalid priority."}

        escalation_id = self.repo.create_with_event(
            requester_employee_id=requester_employee_id,
            requester_email=requester_email,
            thread_id=thread_id,
            source_message_excerpt=source_message_excerpt,
            status="PENDING",
            priority=normalized_priority,
            category=category,
            agent_suggestion=agent_suggestion,
            event_type="CREATED",
            event_note="Escalation request created.",
        )
        return {"success": True, "escalation_id": escalation_id}

    def list_requests(
        self,
        viewer_email: str,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """List escalation requests visible to the viewer."""
        role = self._get_viewer_role(viewer_email)
        if status and status not in self.ALLOWED_STATUSES:
            return []
        if role in self.TRIAGE_ROLES:
            return self.repo.list_for_requester(None, status=status, limit=limit)
        return self.repo.list_for_requester(viewer_email, status=status, limit=limit)

    def list_counts(self, viewer_email: str) -> dict:
        """List aggregate escalation counts visible to the viewer."""
        viewer_role = self._get_viewer_role(viewer_email)
        if self._is_triage_role(viewer_email, viewer_role):
            return self.repo.list_counts_for_requester(None)
        return self.repo.list_counts_for_requester(viewer_email)

    def get_top_categories(self, month: str | None = None, limit: int = 5) -> dict:
        """Return escalation category analytics for the requested month."""
        normalized_month = (month or datetime.now().strftime("%Y-%m")).strip()
        try:
            datetime.strptime(normalized_month, "%Y-%m")
        except ValueError:
            return {"error": "Invalid month format. Use YYYY-MM."}

        safe_limit = max(1, min(int(limit), 20))
        rows = self.repo.list_category_counts_for_month(
            month=normalized_month,
            requester_email=None,
            limit=safe_limit,
        )
        status_counts = self.repo.list_status_counts_for_month(
            month=normalized_month,
            requester_email=None,
        )
        total = int(status_counts.get("total") or 0)
        per_category_status_rows = self.repo.list_category_status_counts_for_month(
            month=normalized_month,
            requester_email=None,
        )
        per_category_status: dict[str, dict[str, int]] = {}
        for row in per_category_status_rows:
            category = row.get("category", "Uncategorized")
            status = str(row.get("status") or "PENDING").upper()
            count = int(row.get("count") or 0)
            bucket = per_category_status.setdefault(
                category,
                {"pending": 0, "in_review": 0, "resolved": 0},
            )
            if status == "PENDING":
                bucket["pending"] += count
            elif status == "IN_REVIEW":
                bucket["in_review"] += count
            elif status == "RESOLVED":
                bucket["resolved"] += count
        categories: list[dict[str, Any]] = []
        for row in rows:
            status_bucket = per_category_status.get(
                row["category"],
                {"pending": 0, "in_review": 0, "resolved": 0},
            )
            categories.append(
                {
                    "category": row["category"],
                    "count": row["count"],
                    "percentage": round((row["count"] / total) * 100, 1)
                    if total > 0
                    else 0.0,
                    "status_breakdown": status_bucket,
                    "open_count": status_bucket["pending"] + status_bucket["in_review"],
                    "resolved_count": status_bucket["resolved"],
                }
            )
        shown_count = sum(int(row["count"]) for row in rows)
        resolved_total = int(status_counts.get("resolved") or 0)
        return {
            "month": normalized_month,
            "total_escalations": total,
            "status_breakdown": {
                "pending": int(status_counts.get("pending") or 0),
                "in_review": int(status_counts.get("in_review") or 0),
                "resolved": resolved_total,
            },
            "open_escalations": int(status_counts.get("pending") or 0)
            + int(status_counts.get("in_review") or 0),
            "resolution_rate_percent": round((resolved_total / total) * 100, 1)
            if total > 0
            else 0.0,
            "top_categories_limit": safe_limit,
            "other_categories_count": max(total - shown_count, 0),
            "categories": categories,
        }

    def get_request_detail(self, viewer_email: str, escalation_id: int) -> dict:
        """Fetch escalation request detail with timeline and completeness metadata."""
        viewer_role = self._get_viewer_role(viewer_email)
        row = self._get_visible_request(viewer_email, escalation_id, viewer_role)
        if not row:
            return {"success": False, "error": "Escalation request not found."}

        events = self.repo.list_events(escalation_id)
        missing_fields = self._compute_missing_fields(row)
        total_fields = 4
        completeness_percent = int(((total_fields - len(missing_fields)) / total_fields) * 100)

        return {
            "success": True,
            "request": row,
            "timeline": events,
            "missing_fields": missing_fields,
            "completeness_percent": completeness_percent,
        }

    def assign_request(
        self,
        viewer_email: str,
        actor_employee_id: int,
        escalation_id: int,
        assignee_email: str | None,
    ) -> dict:
        """Assign or unassign an escalation request."""
        viewer_role = self._get_viewer_role(viewer_email)
        if not self._is_triage_role(viewer_email, viewer_role):
            return {"success": False, "error": "Only HR/Manager can triage requests."}

        existing = self.repo.get_by_id(escalation_id)
        if not existing:
            return {"success": False, "error": "Escalation request not found."}

        if assignee_email:
            assignee = self.employee_repo.get_by_email(assignee_email)
            if not assignee:
                return {"success": False, "error": "Assignee not found."}
            ok = self.repo.update_assignment_with_event(
                escalation_id=escalation_id,
                updated_by_employee_id=actor_employee_id,
                assigned_to_employee_id=assignee["employee_id"],
                assigned_to_email=assignee["email"],
                actor_email=viewer_email,
                event_type="ASSIGNED",
                event_note=f"Assigned to {assignee['email']}.",
            )
            if not ok:
                return {"success": False, "error": "Failed to assign escalation request."}
            return {"success": True}

        ok = self.repo.update_assignment_with_event(
            escalation_id=escalation_id,
            updated_by_employee_id=actor_employee_id,
            assigned_to_employee_id=None,
            assigned_to_email=None,
            actor_email=viewer_email,
            event_type="UNASSIGNED",
            event_note="Request unassigned.",
        )
        if not ok:
            return {"success": False, "error": "Failed to unassign escalation request."}
        return {"success": True}

    def update_priority(
        self,
        viewer_email: str,
        actor_employee_id: int,
        escalation_id: int,
        priority: str,
    ) -> dict:
        """Change escalation priority."""
        viewer_role = self._get_viewer_role(viewer_email)
        if not self._is_triage_role(viewer_email, viewer_role):
            return {"success": False, "error": "Only HR/Manager can triage requests."}

        priority = priority.upper()
        if priority not in self.ALLOWED_PRIORITIES:
            return {"success": False, "error": "Invalid priority."}

        existing = self.repo.get_by_id(escalation_id)
        if not existing:
            return {"success": False, "error": "Escalation request not found."}

        ok = self.repo.update_priority_with_event(
            escalation_id=escalation_id,
            priority=priority,
            updated_by_employee_id=actor_employee_id,
            actor_email=viewer_email,
        )
        if not ok:
            return {"success": False, "error": "Failed to update priority."}
        return {"success": True}

    def message_requester(
        self,
        viewer_email: str,
        actor_employee_id: int,
        escalation_id: int,
        message: str,
    ) -> dict:
        """Log a message sent to the original requester."""
        viewer_role = self._get_viewer_role(viewer_email)
        if not self._is_triage_role(viewer_email, viewer_role):
            return {"success": False, "error": "Only HR/Manager can triage requests."}

        existing = self.repo.get_by_id(escalation_id)
        if not existing:
            return {"success": False, "error": "Escalation request not found."}

        if not message.strip():
            return {"success": False, "error": "Message cannot be empty."}

        ok = self.repo.record_message_to_requester_with_event(
            escalation_id=escalation_id,
            message=message.strip(),
            updated_by_employee_id=actor_employee_id,
            actor_email=viewer_email,
        )
        if not ok:
            return {"success": False, "error": "Failed to record requester message."}
        return {"success": True}

    def reply_as_requester(
        self,
        viewer_email: str,
        actor_employee_id: int,
        escalation_id: int,
        message: str,
    ) -> dict:
        """Allow the original requester to reply on an active escalation."""
        existing = self.repo.get_by_id(escalation_id)
        if not existing:
            return {"success": False, "error": "Escalation request not found."}

        if existing.get("requester_email") != viewer_email:
            return {"success": False, "error": "Only requester can reply to this escalation."}

        if existing.get("status") == "RESOLVED":
            return {"success": False, "error": "Cannot reply to a resolved escalation."}

        if not message.strip():
            return {"success": False, "error": "Message cannot be empty."}

        ok = self.repo.record_requester_reply_with_event(
            escalation_id=escalation_id,
            message=message.strip(),
            updated_by_employee_id=actor_employee_id,
            actor_email=viewer_email,
        )
        if not ok:
            return {"success": False, "error": "Failed to record requester reply."}
        return {"success": True}

    def escalate_request(
        self,
        viewer_email: str,
        actor_employee_id: int,
        escalation_id: int,
        note: str | None = None,
    ) -> dict:
        """Escalate severity for a request."""
        viewer_role = self._get_viewer_role(viewer_email)
        if not self._is_triage_role(viewer_email, viewer_role):
            return {"success": False, "error": "Only HR/Manager can triage requests."}

        existing = self.repo.get_by_id(escalation_id)
        if not existing:
            return {"success": False, "error": "Escalation request not found."}

        ok = self.repo.escalate_case_with_event(
            escalation_id=escalation_id,
            updated_by_employee_id=actor_employee_id,
            actor_email=viewer_email,
            note=note,
        )
        if not ok:
            return {"success": False, "error": "Failed to escalate request."}
        return {"success": True}

    def transition_status(
        self,
        viewer_email: str,
        actor_employee_id: int,
        escalation_id: int,
        new_status: str,
        resolution_note: str | None = None,
    ) -> dict:
        """Transition escalation status with role and state checks."""
        viewer_role = self._get_viewer_role(viewer_email)
        if not self._is_triage_role(viewer_email, viewer_role):
            return {"success": False, "error": "Only HR/Manager can triage requests."}

        if new_status not in self.ALLOWED_STATUSES:
            return {"success": False, "error": "Invalid status."}

        existing = self.repo.get_by_id(escalation_id)
        if not existing:
            return {"success": False, "error": "Escalation request not found."}

        current_status = existing["status"]
        allowed_next = self.ALLOWED_TRANSITIONS.get(current_status, set())
        if new_status not in allowed_next:
            return {
                "success": False,
                "error": f"Invalid transition: {current_status} -> {new_status}.",
            }

        ok = self.repo.transition_status_with_event(
            escalation_id=escalation_id,
            status=new_status,
            updated_by_employee_id=actor_employee_id,
            actor_email=viewer_email,
            resolution_note=resolution_note,
        )
        if not ok:
            return {"success": False, "error": "Failed to update escalation request."}
        return {"success": True}


class HRRequestService:
    """Service for canonical HRRequest workflow and audit events."""

    ALLOWED_STATUSES = {
        "NEW",
        "NEEDS_INFO",
        "READY",
        "IN_PROGRESS",
        "RESOLVED",
        "ESCALATED",
        "CANCELLED",
    }
    TERMINAL_STATUSES = {"RESOLVED", "CANCELLED"}
    ALLOWED_PRIORITIES = {"P0", "P1", "P2"}
    ALLOWED_RISK_LEVELS = {"HIGH", "MED", "LOW"}
    ALLOWED_TRANSITIONS: dict[str, set[str]] = {
        "NEW": {"NEEDS_INFO", "READY", "IN_PROGRESS", "ESCALATED", "CANCELLED"},
        "NEEDS_INFO": {"READY", "IN_PROGRESS", "ESCALATED", "CANCELLED"},
        "READY": {"IN_PROGRESS", "NEEDS_INFO", "RESOLVED", "ESCALATED", "CANCELLED"},
        "IN_PROGRESS": {"NEEDS_INFO", "READY", "RESOLVED", "ESCALATED", "CANCELLED"},
        "ESCALATED": {"IN_PROGRESS", "NEEDS_INFO", "RESOLVED", "CANCELLED"},
        "RESOLVED": {"IN_PROGRESS"},
        "CANCELLED": set[str](),
    }
    AUTO_PROGRESS_ON_ASSIGN_STATUSES = {"NEW", "NEEDS_INFO", "READY", "ESCALATED"}
    TRIAGE_ROLES = {"HR", "MANAGER"}
    DEFAULT_REQUIRED_FIELDS = [
        "summary",
        "description",
        "requester_user_id",
        "type",
        "subtype",
    ]
    EMPLOYEE_INTAKE_PROFILES: list[dict[str, Any]] = [
        {
            "type": "CLAIMS",
            "subtype": "TRAVEL",
            "keywords": [
                "reimbursement",
                "reimburs",
                "expense claim",
                "travel claim",
                "taxi",
                "uber",
                "lyft",
            ],
            "priority": "P1",
            "risk_level": "MED",
            "sla_hours": 72,
            "required_fields": ["amount", "date", "receipt"],
            "optional_fields": ["cost_center"],
        },
        {
            "type": "PAYROLL",
            "subtype": "DEDUCTION_QUERY",
            "keywords": [
                "salary lower",
                "why is my salary lower",
                "net pay lower",
                "payroll deduction",
                "deduction",
                "salary less",
                "paid less",
            ],
            "priority": "P0",
            "risk_level": "HIGH",
            "sla_hours": 24,
            "required_fields": ["month"],
            "optional_fields": ["payslip_id"],
        },
        {
            "type": "POLICY",
            "subtype": "REMOTE_WORK",
            "keywords": [
                "remote policy",
                "work from home policy",
                "wfh policy",
                "remote work policy",
                "what is remote policy",
            ],
            "priority": "P2",
            "risk_level": "LOW",
            "sla_hours": 120,
            "required_fields": [],
            "optional_fields": [],
        },
    ]

    def __init__(self) -> None:
        self.repo: HRRequestRepository = get_hr_request_repo()
        self.employee_repo: EmployeeRepository = get_employee_repo()

    def _get_viewer_role(self, viewer_email: str) -> str:
        return self.employee_repo.get_role_by_email(viewer_email)

    def _is_triage_role(self, viewer_email: str, viewer_role: str | None = None) -> bool:
        role = viewer_role if viewer_role is not None else self._get_viewer_role(viewer_email)
        return role in self.TRIAGE_ROLES

    def _get_visible_request(
        self, viewer_email: str, request_id: int, viewer_role: str | None = None
    ) -> dict | None:
        row = self.repo.get_by_id(request_id)
        if not row:
            return None
        if self._is_triage_role(viewer_email, viewer_role):
            return row
        if row["requester_user_id"] == viewer_email:
            return row
        return None

    @staticmethod
    def _normalize_required_fields(required_fields: list[str] | None) -> list[str]:
        default_fields = HRRequestService.DEFAULT_REQUIRED_FIELDS
        if not required_fields:
            return default_fields
        normalized: list[str] = []
        for item in required_fields:
            key = item.strip()
            if key and key not in normalized:
                normalized.append(key)
        return normalized or default_fields

    @staticmethod
    def _compute_missing_fields(
        required_fields: list[str], captured_fields: dict[str, Any]
    ) -> list[str]:
        missing: list[str] = []
        for key in required_fields:
            value = captured_fields.get(key)
            if value is None:
                missing.append(key)
                continue
            if isinstance(value, str) and not value.strip():
                missing.append(key)
                continue
            if isinstance(value, (list, dict)) and not value:
                missing.append(key)
        return missing

    @staticmethod
    def _normalize_taxonomy_value(value: str | None, fallback: str) -> str:
        raw = (value or "").strip()
        if not raw:
            raw = fallback
        normalized = (
            raw.upper()
            .replace("&", "AND")
            .replace("/", "_")
            .replace("-", "_")
            .replace(" ", "_")
        )
        return normalized or fallback

    @staticmethod
    def _compute_sla_due_at(hours_from_now: int) -> str:
        return (datetime.now() + timedelta(hours=hours_from_now)).isoformat()

    def _match_employee_profile(self, text: str) -> dict[str, Any] | None:
        lower = text.lower()
        for profile in self.EMPLOYEE_INTAKE_PROFILES:
            if any(keyword in lower for keyword in profile["keywords"]):
                return profile
        return None

    def _derive_initial_request_profile(
        self,
        requester_role: str,
        summary: str,
        description: str,
        requested_type: str,
        requested_subtype: str,
        requested_priority: str,
        requested_risk: str,
        requested_sla_due_at: str | None,
        requested_required_fields: list[str] | None,
    ) -> dict[str, Any]:
        normalized_type = self._normalize_taxonomy_value(requested_type, "GENERAL")
        normalized_subtype = self._normalize_taxonomy_value(
            requested_subtype, "GENERAL"
        )
        normalized_priority = requested_priority.upper()
        normalized_risk = requested_risk.upper()
        normalized_required = self._normalize_required_fields(requested_required_fields)

        role = requester_role.upper()
        # Employee requests are enriched with deterministic intake profiles.
        if role not in self.TRIAGE_ROLES:
            combined_text = f"{summary}\n{description}"
            matched = self._match_employee_profile(combined_text)
            if matched:
                profile_required = [
                    *self.DEFAULT_REQUIRED_FIELDS,
                    *matched.get("required_fields", []),
                ]
                return {
                    "request_type": matched["type"],
                    "request_subtype": matched["subtype"],
                    "priority": matched["priority"],
                    "risk_level": matched["risk_level"],
                    "sla_due_at": self._compute_sla_due_at(matched["sla_hours"]),
                    "required_fields": self._normalize_required_fields(profile_required),
                    "optional_fields": matched.get("optional_fields", []),
                    "classification_source": "employee_intake_profile",
                }

        return {
            "request_type": normalized_type,
            "request_subtype": normalized_subtype,
            "priority": normalized_priority,
            "risk_level": normalized_risk,
            "sla_due_at": requested_sla_due_at,
            "required_fields": normalized_required,
            "optional_fields": [],
            "classification_source": "request_payload",
        }

    @staticmethod
    def _to_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _default_sla_hours(priority: str, risk_level: str) -> int:
        by_priority = {"P0": 24, "P1": 72, "P2": 120}
        by_risk = {"HIGH": 24, "MED": 72, "LOW": 120}
        return min(by_priority.get(priority, 120), by_risk.get(risk_level, 120))

    def _resolve_sla_due_at(
        self,
        priority: str,
        risk_level: str,
        requested_sla_due_at: str | None,
        created_at: str | None = None,
    ) -> str:
        if requested_sla_due_at:
            return requested_sla_due_at
        base = self._to_datetime(created_at) or datetime.now()
        return (base + timedelta(hours=self._default_sla_hours(priority, risk_level))).isoformat()

    def _is_ready_like(self, status: str) -> bool:
        return status in {"READY", "IN_PROGRESS"}

    def _should_keep_needs_info_ahead(
        self, needs_info_row: dict[str, Any], other_row: dict[str, Any]
    ) -> bool:
        if needs_info_row.get("priority") != "P0":
            return False
        needs_info_sla = self._to_datetime(needs_info_row.get("sla_due_at"))
        if not needs_info_sla:
            return False
        other_sla = self._to_datetime(other_row.get("sla_due_at"))
        if not other_sla:
            return True
        return needs_info_sla < other_sla

    def _compare_queue_rows(self, left: dict[str, Any], right: dict[str, Any]) -> int:
        priority_rank = {"P0": 0, "P1": 1, "P2": 2}
        risk_rank = {"HIGH": 0, "MED": 1, "LOW": 2}

        left_priority = priority_rank.get(left.get("priority", "P2"), 3)
        right_priority = priority_rank.get(right.get("priority", "P2"), 3)
        if left_priority != right_priority:
            return left_priority - right_priority

        left_sla = self._to_datetime(left.get("sla_due_at")) or datetime.max
        right_sla = self._to_datetime(right.get("sla_due_at")) or datetime.max
        if left_sla != right_sla:
            return -1 if left_sla < right_sla else 1

        left_risk = risk_rank.get(left.get("risk_level", "LOW"), 3)
        right_risk = risk_rank.get(right.get("risk_level", "LOW"), 3)
        if left_risk != right_risk:
            return left_risk - right_risk

        left_status = left.get("status", "NEW")
        right_status = right.get("status", "NEW")
        left_is_needs_info = left_status == "NEEDS_INFO"
        right_is_needs_info = right_status == "NEEDS_INFO"
        left_is_ready_like = self._is_ready_like(left_status)
        right_is_ready_like = self._is_ready_like(right_status)

        if left_is_needs_info and right_is_ready_like:
            if not self._should_keep_needs_info_ahead(left, right):
                return 1
        elif right_is_needs_info and left_is_ready_like:
            if not self._should_keep_needs_info_ahead(right, left):
                return -1

        def _status_group(status: str) -> int:
            if status in {"READY", "IN_PROGRESS"}:
                return 0
            if status == "NEEDS_INFO":
                return 1
            return 2

        left_group = _status_group(left_status)
        right_group = _status_group(right_status)
        if left_group != right_group:
            return left_group - right_group

        left_created = self._to_datetime(left.get("created_at")) or datetime.max
        right_created = self._to_datetime(right.get("created_at")) or datetime.max
        if left_created != right_created:
            return -1 if left_created < right_created else 1

        return int(left.get("request_id", 0)) - int(right.get("request_id", 0))

    def _apply_queue_defaults(self, row: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(row)
        status = str(enriched.get("status") or "NEW")
        if status == "NEW":
            missing = enriched.get("missing_fields") or []
            enriched["status"] = "NEEDS_INFO" if missing else "READY"
        priority = str(enriched.get("priority") or "P2")
        risk_level = str(enriched.get("risk_level") or "LOW")
        enriched["sla_due_at"] = self._resolve_sla_due_at(
            priority=priority,
            risk_level=risk_level,
            requested_sla_due_at=enriched.get("sla_due_at"),
            created_at=enriched.get("created_at"),
        )
        return enriched

    def create_request(
        self,
        requester_user_id: str,
        requester_role: str,
        request_type: str,
        request_subtype: str,
        summary: str,
        description: str,
        tenant_id: str = "default",
        subject_employee_id: int | None = None,
        priority: str = "P2",
        risk_level: str = "LOW",
        sla_due_at: str | None = None,
        required_fields: list[str] | None = None,
        captured_fields: dict[str, Any] | None = None,
    ) -> dict:
        """Create one canonical HR request with field-tracking metadata."""
        profile = self._derive_initial_request_profile(
            requester_role=requester_role,
            summary=summary,
            description=description,
            requested_type=request_type,
            requested_subtype=request_subtype,
            requested_priority=priority,
            requested_risk=risk_level,
            requested_sla_due_at=sla_due_at,
            requested_required_fields=required_fields,
        )
        final_type = profile["request_type"]
        final_subtype = profile["request_subtype"]
        normalized_priority = profile["priority"]
        normalized_risk = profile["risk_level"]
        final_sla_due_at = profile["sla_due_at"]
        final_required_fields = profile["required_fields"]
        optional_fields = profile["optional_fields"]

        if normalized_priority not in self.ALLOWED_PRIORITIES:
            return {"success": False, "error": "Invalid priority."}

        if normalized_risk not in self.ALLOWED_RISK_LEVELS:
            return {"success": False, "error": "Invalid risk level."}

        if not summary.strip() or not description.strip():
            return {"success": False, "error": "Summary and description are required."}

        merged_captured = dict(captured_fields or {})
        merged_captured.setdefault("summary", summary.strip())
        merged_captured.setdefault("description", description.strip())
        merged_captured.setdefault("requester_user_id", requester_user_id)
        merged_captured.setdefault("type", final_type)
        merged_captured.setdefault("subtype", final_subtype)
        if optional_fields:
            merged_captured.setdefault("optional_fields", optional_fields)
        missing = self._compute_missing_fields(final_required_fields, merged_captured)
        initial_status = "NEW"
        final_sla_due_at = self._resolve_sla_due_at(
            priority=normalized_priority,
            risk_level=normalized_risk,
            requested_sla_due_at=final_sla_due_at,
        )

        request_id = self.repo.create_with_event(
            tenant_id=tenant_id,
            requester_user_id=requester_user_id,
            requester_role=requester_role,
            subject_employee_id=subject_employee_id,
            request_type=final_type,
            request_subtype=final_subtype,
            summary=summary.strip(),
            description=description.strip(),
            priority=normalized_priority,
            risk_level=normalized_risk,
            sla_due_at=final_sla_due_at,
            status=initial_status,
            assignee_user_id=None,
            required_fields=final_required_fields,
            captured_fields=merged_captured,
            missing_fields=missing,
            event_type="CREATED",
            event_note="HR request created.",
            actor_user_id=requester_user_id,
            actor_role=requester_role,
            event_payload={
                "missing_fields": missing,
                "classification_source": profile["classification_source"],
                "initial_status": initial_status,
            },
        )
        return {"success": True, "request_id": request_id}

    def list_requests(
        self, viewer_email: str, status: str | None = None, limit: int = 100
    ) -> list[dict]:
        """List visible HR requests for current user scope."""
        viewer_role = self._get_viewer_role(viewer_email)
        if status and status not in self.ALLOWED_STATUSES:
            return []
        if self._is_triage_role(viewer_email, viewer_role):
            repo_status = status
            if status in {"READY", "NEEDS_INFO"}:
                repo_status = "NEW"
            rows = self.repo.list_for_requester(None, status=repo_status, limit=limit)
            enriched = [self._apply_queue_defaults(row) for row in rows]
            if status in {"READY", "NEEDS_INFO"}:
                enriched = [row for row in enriched if row.get("status") == status]
            return sorted(enriched, key=cmp_to_key(self._compare_queue_rows))
        return self.repo.list_for_requester(viewer_email, status=status, limit=limit)

    def list_counts(self, viewer_email: str) -> dict:
        """List aggregate request counts by status."""
        viewer_role = self._get_viewer_role(viewer_email)
        if self._is_triage_role(viewer_email, viewer_role):
            return self.repo.list_counts_for_requester(None)
        return self.repo.list_counts_for_requester(viewer_email)

    def get_request_detail(self, viewer_email: str, request_id: int) -> dict:
        """Fetch full request detail and event timeline."""
        viewer_role = self._get_viewer_role(viewer_email)
        row = self._get_visible_request(viewer_email, request_id, viewer_role)
        if not row:
            return {"success": False, "error": "HR request not found."}
        events = self.repo.list_events(request_id)
        required_fields = row.get("required_fields") or []
        missing_fields = row.get("missing_fields") or []
        total_fields = max(len(required_fields), 1)
        completeness_percent = int(
            ((total_fields - len(missing_fields)) / total_fields) * 100
        )
        return {
            "success": True,
            "request": row,
            "timeline": events,
            "missing_fields": missing_fields,
            "completeness_percent": completeness_percent,
        }

    def assign_request(
        self,
        viewer_email: str,
        request_id: int,
        assignee_user_id: str | None,
    ) -> dict:
        """Assign/unassign request owner (triage roles only)."""
        viewer_role = self._get_viewer_role(viewer_email)
        if not self._is_triage_role(viewer_email, viewer_role):
            return {"success": False, "error": "Only HR/Manager can triage requests."}
        existing = self.repo.get_by_id(request_id)
        if not existing:
            return {"success": False, "error": "HR request not found."}
        normalized_assignee = assignee_user_id.strip().lower() if assignee_user_id else None
        if normalized_assignee:
            assignee = self.employee_repo.get_by_email(normalized_assignee)
            if not assignee:
                return {"success": False, "error": "Assignee not found."}
        ok = self.repo.update_assignment_with_event(
            request_id=request_id,
            assignee_user_id=normalized_assignee,
            actor_user_id=viewer_email,
            actor_role=viewer_role,
        )
        if not ok:
            return {"success": False, "error": "HR request not found."}
        current_status = str(existing.get("status") or "NEW")
        if (
            normalized_assignee
            and current_status in self.AUTO_PROGRESS_ON_ASSIGN_STATUSES
        ):
            progressed = self.repo.update_status_with_event(
                request_id=request_id,
                status="IN_PROGRESS",
                actor_user_id=viewer_email,
                actor_role=viewer_role,
                event_note="Auto-moved to IN_PROGRESS after assignment.",
            )
            if not progressed:
                return {"success": False, "error": "Failed to auto-start assigned request."}
        return {"success": True}

    def update_priority(
        self, viewer_email: str, request_id: int, priority: str
    ) -> dict:
        """Update request priority (triage roles only)."""
        viewer_role = self._get_viewer_role(viewer_email)
        if not self._is_triage_role(viewer_email, viewer_role):
            return {"success": False, "error": "Only HR/Manager can triage requests."}
        normalized = priority.upper()
        if normalized not in self.ALLOWED_PRIORITIES:
            return {"success": False, "error": "Invalid priority."}
        ok = self.repo.update_priority_with_event(
            request_id=request_id,
            priority=normalized,
            actor_user_id=viewer_email,
            actor_role=viewer_role,
        )
        if not ok:
            return {"success": False, "error": "HR request not found."}
        return {"success": True}

    def transition_status(
        self,
        viewer_email: str,
        request_id: int,
        new_status: str,
        resolution_text: str | None = None,
        resolution_sources: list[str] | None = None,
        escalation_ticket_id: str | None = None,
    ) -> dict:
        """Transition request status with role and state checks."""
        viewer_role = self._get_viewer_role(viewer_email)
        if not self._is_triage_role(viewer_email, viewer_role):
            return {"success": False, "error": "Only HR/Manager can triage requests."}
        normalized = new_status.upper()
        if normalized not in self.ALLOWED_STATUSES:
            return {"success": False, "error": "Invalid status."}
        existing = self.repo.get_by_id(request_id)
        if not existing:
            return {"success": False, "error": "HR request not found."}

        requester_role = str(existing.get("requester_role") or "").upper()
        requester_user_id = str(existing.get("requester_user_id") or "").strip().lower()
        viewer_normalized = viewer_email.strip().lower()
        if (
            normalized == "RESOLVED"
            and requester_role == "HR"
            and requester_user_id
            and requester_user_id == viewer_normalized
        ):
            return {
                "success": False,
                "error": "Only a different HR reviewer can resolve HR-raised requests.",
            }

        current = str(existing.get("status") or "NEW")
        allowed = self.ALLOWED_TRANSITIONS.get(current, set[str]())
        if normalized not in allowed:
            return {
                "success": False,
                "error": f"Invalid transition: {current} -> {normalized}.",
            }
        ok = self.repo.update_status_with_event(
            request_id=request_id,
            status=normalized,
            actor_user_id=viewer_email,
            actor_role=viewer_role,
            resolution_text=resolution_text,
            resolution_sources=resolution_sources,
            escalation_ticket_id=escalation_ticket_id,
        )
        if not ok:
            return {"success": False, "error": "Failed to update request status."}
        return {"success": True}

    def message_requester(
        self,
        viewer_email: str,
        request_id: int,
        message: str,
    ) -> dict:
        """Send/log clarifying message to requester (triage roles only)."""
        viewer_role = self._get_viewer_role(viewer_email)
        if not self._is_triage_role(viewer_email, viewer_role):
            return {"success": False, "error": "Only HR/Manager can triage requests."}
        existing = self.repo.get_by_id(request_id)
        if not existing:
            return {"success": False, "error": "HR request not found."}
        if existing.get("status") in self.TERMINAL_STATUSES:
            return {"success": False, "error": "Cannot message on a closed request."}
        clean = message.strip()
        if not clean:
            return {"success": False, "error": "Message cannot be empty."}
        ok = self.repo.record_message_to_requester_with_event(
            request_id=request_id,
            message=clean,
            actor_user_id=viewer_email,
            actor_role=viewer_role,
            set_status="NEEDS_INFO",
        )
        if not ok:
            return {"success": False, "error": "Failed to message requester."}
        return {"success": True}

    def reply_as_requester(
        self,
        viewer_email: str,
        request_id: int,
        message: str,
    ) -> dict:
        """Allow the original requester to send additional clarification."""
        viewer_role = self._get_viewer_role(viewer_email)
        existing = self.repo.get_by_id(request_id)
        if not existing:
            return {"success": False, "error": "HR request not found."}
        if existing.get("requester_user_id") != viewer_email:
            return {"success": False, "error": "Only requester can reply to this request."}
        if existing.get("status") in self.TERMINAL_STATUSES:
            return {"success": False, "error": "Cannot reply to a closed request."}
        clean = message.strip()
        if not clean:
            return {"success": False, "error": "Message cannot be empty."}
        ok = self.repo.record_requester_reply_with_event(
            request_id=request_id,
            message=clean,
            actor_user_id=viewer_email,
            actor_role=viewer_role,
        )
        if not ok:
            return {"success": False, "error": "Failed to record requester reply."}
        return {"success": True}

    def capture_fields(
        self,
        viewer_email: str,
        request_id: int,
        captured_fields: dict[str, Any],
    ) -> dict:
        """Merge captured fields and refresh missing field status."""
        viewer_role = self._get_viewer_role(viewer_email)
        existing = self._get_visible_request(viewer_email, request_id, viewer_role)
        if not existing:
            return {"success": False, "error": "HR request not found."}
        if existing.get("status") in self.TERMINAL_STATUSES:
            return {"success": False, "error": "Cannot update fields on a closed request."}
        merged = dict(existing.get("captured_fields") or {})
        merged.update(captured_fields)
        required = existing.get("required_fields") or []
        missing = self._compute_missing_fields(required, merged)

        current_status = existing.get("status", "NEW")
        if missing:
            next_status = "NEEDS_INFO"
        elif current_status in {"NEW", "NEEDS_INFO"}:
            next_status = "READY"
        else:
            next_status = current_status

        ok = self.repo.update_field_tracking_with_event(
            request_id=request_id,
            captured_fields=merged,
            missing_fields=missing,
            status=next_status,
            actor_user_id=viewer_email,
            actor_role=viewer_role,
        )
        if not ok:
            return {"success": False, "error": "Failed to update captured fields."}
        return {"success": True, "missing_fields": missing, "status": next_status}

    def escalate_request(
        self,
        viewer_email: str,
        request_id: int,
        escalation_ticket_id: str | None = None,
        note: str | None = None,
    ) -> dict:
        """Escalate request to external or higher-severity workflow."""
        return self.transition_status(
            viewer_email=viewer_email,
            request_id=request_id,
            new_status="ESCALATED",
            resolution_text=note,
            escalation_ticket_id=escalation_ticket_id,
        )


# ============================================================================
# SERVICE SINGLETONS
# ============================================================================

_employee_service: EmployeeService | None = None
_holiday_service: HolidayService | None = None
_compensation_service: CompensationService | None = None
_company_service: CompanyService | None = None
_escalation_service: EscalationService | None = None
_hr_request_service: HRRequestService | None = None


def get_employee_service() -> EmployeeService:
    global _employee_service
    if _employee_service is None:
        _employee_service = EmployeeService()
    return _employee_service


def get_holiday_service() -> HolidayService:
    global _holiday_service
    if _holiday_service is None:
        _holiday_service = HolidayService()
    return _holiday_service


def get_compensation_service() -> CompensationService:
    global _compensation_service
    if _compensation_service is None:
        _compensation_service = CompensationService()
    return _compensation_service


def get_company_service() -> CompanyService:
    global _company_service
    if _company_service is None:
        _company_service = CompanyService()
    return _company_service


def get_escalation_service() -> EscalationService:
    global _escalation_service
    if _escalation_service is None:
        _escalation_service = EscalationService()
    return _escalation_service


def get_hr_request_service() -> HRRequestService:
    global _hr_request_service
    if _hr_request_service is None:
        _hr_request_service = HRRequestService()
    return _hr_request_service

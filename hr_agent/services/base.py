"""
Service Layer - Business Logic

This layer contains all business logic and uses repositories for data access.
Services are the main interface that tools/agent should use.

Benefits:
- Business logic is separated from data access
- Easy to test with mock repositories
- Clear, readable operations without SQL
"""

from datetime import datetime, date
from ..repositories import (
    get_employee_repo,
    get_holiday_repo,
    get_compensation_repo,
    get_company_repo,
    get_escalation_repo,
)


# ============================================================================
# EMPLOYEE SERVICE
# ============================================================================


class EmployeeService:
    """Service for employee and organization operations."""

    def __init__(self):
        self.repo = get_employee_repo()

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

    def __init__(self):
        self.repo = get_holiday_repo()

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

    def __init__(self):
        self.repo = get_compensation_repo()

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

    def __init__(self):
        self.repo = get_company_repo()

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
    ALLOWED_TRANSITIONS = {
        "PENDING": {"IN_REVIEW"},
        "IN_REVIEW": {"RESOLVED"},
        "RESOLVED": {"IN_REVIEW"},
    }
    TRIAGE_ROLES = {"HR", "MANAGER"}

    def __init__(self):
        self.repo = get_escalation_repo()
        self.employee_repo = get_employee_repo()

    def _is_triage_role(self, viewer_email: str) -> bool:
        role = self.employee_repo.get_role_by_email(viewer_email)
        return role in self.TRIAGE_ROLES

    def _get_visible_request(self, viewer_email: str, escalation_id: int) -> dict | None:
        row = self.repo.get_by_id(escalation_id)
        if not row:
            return None
        if self._is_triage_role(viewer_email):
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
        role = self.employee_repo.get_role_by_email(viewer_email)
        if status and status not in self.ALLOWED_STATUSES:
            return []
        if role in self.TRIAGE_ROLES:
            return self.repo.list_for_requester(None, status=status, limit=limit)
        return self.repo.list_for_requester(viewer_email, status=status, limit=limit)

    def list_counts(self, viewer_email: str) -> dict:
        """List aggregate escalation counts visible to the viewer."""
        if self._is_triage_role(viewer_email):
            return self.repo.list_counts_for_requester(None)
        return self.repo.list_counts_for_requester(viewer_email)

    def get_request_detail(self, viewer_email: str, escalation_id: int) -> dict:
        """Fetch escalation request detail with timeline and completeness metadata."""
        row = self._get_visible_request(viewer_email, escalation_id)
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
        if not self._is_triage_role(viewer_email):
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
        if not self._is_triage_role(viewer_email):
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
        if not self._is_triage_role(viewer_email):
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
        if not self._is_triage_role(viewer_email):
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
        if not self._is_triage_role(viewer_email):
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


# ============================================================================
# SERVICE SINGLETONS
# ============================================================================

_employee_service: EmployeeService | None = None
_holiday_service: HolidayService | None = None
_compensation_service: CompensationService | None = None
_company_service: CompanyService | None = None
_escalation_service: EscalationService | None = None


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
